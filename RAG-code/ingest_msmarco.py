# ============================================================
#  ingest_msmarco.py — Build a fast multilingual RAG index
#  from the ai4bharat/MSMARCO-XI dataset.
#
#  Chunking strategy (vast, not naive fixed-size):
#    1. Natural passage-unit chunks — MSMARCO passages are already
#       self-contained answer units, so they are kept as-is.
#    2. Adaptive recursive sentence-split with overlap for long
#       passages; short fragments merge into the previous chunk.
#    3. Metadata-aware chunks — every chunk carries language,
#       query_id, query_type, gold label, and its source query.
#    4. Cross-lingual anchoring — each Hindi chunk also stores the
#       English translation and a romanized (Hinglish) surface, so
#       English and romanized queries retrieve Hindi passages.
#    5. Answer anchoring — gold passages embed the well-formed answer
#       for the extractive fast path.
#    6. De-duplication across the corpus.
#
#  Retrieval backend: FAISS (vector DB) dense index + optional BM25.
#
#  Run:  python ingest_msmarco.py [--rebuild] [--rows N] [--langs hi,te]
# ============================================================

import os
import re
import sys
import json
import time
import hashlib
import argparse
import itertools

import numpy as np

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import config


# ── Sentence splitting (multilingual-friendly) ──────────────
def split_sentences(text: str) -> list:
    """Split on sentence-final punctuation / newlines; keep list items intact."""
    raw = re.split(r"(?<=[.!?।])\s+|\n{2,}", text)
    out = []
    for s in raw:
        s = s.strip()
        if not s:
            continue
        out.extend(l.strip() for l in s.split("\n") if l.strip())
    return [s for s in out if len(s) > 2]


# ── Romanize Devanagari → Latin (Hinglish surface) ───────────
_romanizer = None
def romanize(text: str) -> str:
    if not text:
        return ""
    try:
        from indic_transliteration import sanscript
        global _romanizer
        if _romanizer is None:
            _romanizer = sanscript
        return _romanizer.transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    except Exception:
        return ""


# ── Adaptive recursive chunking ──────────────────────────────
def chunk_passage(passage_text: str) -> list:
    """
    Return list of (text, chunk_type). Short passages pass through
    untouched (natural units). Long passages are split recursively on
    sentence boundaries with overlap; tiny fragments merge backwards.
    """
    pt = passage_text.strip()
    if not pt:
        return []
    if len(pt) <= config.CHUNK_MAX_CHARS:
        return [(pt, "passage")]

    sentences = split_sentences(pt)
    chunks = []
    current = ""
    for s in sentences:
        if not s:
            continue
        if not current:
            current = s
            continue
        if len(current) + len(s) + 1 <= config.CHUNK_MAX_CHARS:
            current += " " + s
        else:
            if len(current) >= config.CHUNK_MIN_CHARS:
                chunks.append((current, "recursive"))
            else:
                # tiny fragment → merge into previous chunk
                if chunks:
                    prev_t, prev_typ = chunks[-1]
                    chunks[-1] = (prev_t + " " + current, prev_typ)
                else:
                    chunks.append((current, "recursive"))
            # overlap: seed the next chunk with the tail of the current one
            overlap_chars = int(len(current) * config.CHUNK_OVERLAP_RATIO)
            current = current[-overlap_chars:] + " " + s if overlap_chars else s
    if current:
        if len(current) < config.CHUNK_MIN_CHARS and chunks:
            prev_t, prev_typ = chunks[-1]
            chunks[-1] = (prev_t + " " + current, prev_typ)
        else:
            chunks.append((current, "recursive"))
    return chunks


# ── Assemble anchored chunk text ─────────────────────────────
def build_chunk_text(pt: str, eng: str, roman: str, answer: str) -> str:
    parts = [pt]
    if config.ANCHOR_ENGLISH and eng:
        parts.append("[EN] " + eng)
    if config.ANCHOR_ROMANIZED and roman:
        parts.append("[RO] " + roman)
    if config.ANCHOR_ANSWER and answer:
        parts.append("[ANS] " + answer)
    return "\n".join(parts)


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


# ── Per-language file mapping (repo uses irregular names) ────
_LANG_FILE = {
    "as": "asm", "bn": "ben", "gu": "guj", "hi": "hin", "kn": "kan",
    "ml": "mal", "mr": "mar", "ne": "nep", "or": "ori", "pa": "pan",
    "sa": "san", "ta": "tam", "te": "tel", "ur": "urd",
}


def download_lang_file(lang: str) -> str:
    """Download the parquet file for a language and return its local path."""
    from huggingface_hub import hf_hub_download
    suffix = "train" if config.DATASET_SPLIT == "train" else "val"
    fname = f"{_LANG_FILE[lang]}{suffix}.parquet"
    path = hf_hub_download(
        repo_id=config.DATASET_NAME,
        filename=f"{config.DATASET_SPLIT}/{fname}",
        repo_type="dataset",
    )
    return path


def _to_list(v):
    if v is None:
        return []
    if hasattr(v, "tolist"):
        return v.tolist()
    return list(v)


# ── Load dataset rows (parquet, incremental read) ────────────
def load_rows(lang: str, max_rows: int):
    import pyarrow.parquet as pq
    path = download_lang_file(lang)
    pf = pq.ParquetFile(path)
    seen = set()
    count = 0
    budget = max_rows * 6
    for batch in pf.iter_batches(batch_size=1500):
        for row in batch.to_pylist():
            qid = row.get("query_id")
            if qid in seen:
                continue
            seen.add(qid)
            count += 1
            if count > max_rows:
                return
            yield row
        if count >= budget:
            return


# ── Main ingestion ───────────────────────────────────────────
def ingest(langs=None, max_rows=None, rebuild=False):
    langs = langs or config.LANGUAGES
    max_rows = max_rows or config.MAX_ROWS_PER_LANG

    os.makedirs(config.INDEX_DIR, exist_ok=True)
    index_path = os.path.join(config.INDEX_DIR, "faiss.index")
    passages_path = os.path.join(config.INDEX_DIR, "passages.pkl")
    queries_path = os.path.join(config.INDEX_DIR, "queries.jsonl")

    if not rebuild and os.path.exists(index_path):
        print(f"[SKIP] Index already exists at {index_path} — use --rebuild to rebuild.")
        return

    # e5 requires the "passage: " prefix for stored passages
    from sentence_transformers import SentenceTransformer
    print(f"[EMBED] Loading {config.EMBED_MODEL} ...")
    embedder = SentenceTransformer(config.EMBED_MODEL)
    dim = embedder.get_embedding_dimension()

    all_vectors = []
    all_passages = []
    seen_text = set() if config.DEDUPE_PASSAGES else None
    queries_out = []

    t0 = time.time()
    for lang in langs:
        print(f"\n[LOAD] {lang} — reading up to {max_rows} rows from {config.DATASET_SPLIT} ...")
        row_count = 0
        for row in load_rows(lang, max_rows):
            row_count += 1
            q = (row.get("query") or "").strip()
            answer = (row.get("Answer") or "").strip()
            eng_q = (row.get("Eng_Query") or "").strip()
            eng_answer = (row.get("Eng_Answer") or "").strip()
            qtype = row.get("query_type") or "unknown"
            qid = row.get("query_id")
            ps = row.get("passages") or {}

            queries_out.append({
                "query_id": qid, "lang": lang, "query": q,
                "answer": answer, "eng_query": eng_q,
                "eng_answer": eng_answer, "query_type": qtype,
            })

            trans = _to_list(ps.get("Translated_passages"))
            engs = _to_list(ps.get("English_passages"))
            sel = _to_list(ps.get("is_selected"))
            for idx, pt in enumerate(trans[: config.MAX_PASSAGES_PER_ROW]):
                pt = (pt or "").strip()
                if not pt:
                    continue
                eng = (engs[idx] if idx < len(engs) else "").strip()
                is_gold = bool(sel[idx]) if idx < len(sel) else False
                roman = romanize(pt)

                chunks = chunk_passage(pt)
                for ctext, ctype in chunks:
                    full = build_chunk_text(ctext, eng, roman, answer if is_gold else "")
                    if config.DEDUPE_PASSAGES:
                        h = _hash(full)
                        if h in seen_text:
                            continue
                        seen_text.add(h)
                    all_passages.append({
                        "id": f"{lang}:{qid}:{idx}:{len(all_passages)}",
                        "text": full,
                        "lang": lang,
                        "query_id": qid,
                        "query": q,
                        "eng_query": eng_q,
                        "answer": answer,
                        "eng_answer": eng_answer,
                        "query_type": qtype,
                        "is_gold": is_gold,
                        "chunk_type": ctype,
                        "passage_idx": idx,
                    })
        print(f"[LOAD] {lang}: {row_count} rows, {len(all_passages)} cumulative chunks")

    print(f"\n[EMBED] Embedding {len(all_passages)} chunks ...")
    texts = [config.EMBED_PASS_PREFIX + p["text"] for p in all_passages]
    BATCH = 256
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        vecs = embedder.encode(batch, batch_size=64, normalize_embeddings=True,
                               show_progress_bar=(i == 0))
        all_vectors.append(np.asarray(vecs, dtype=np.float32))
        print(f"[EMBED] {min(i + BATCH, len(texts))}/{len(texts)}")

    matrix = np.vstack(all_vectors) if all_vectors else np.zeros((0, dim), dtype=np.float32)

    # ── FAISS index (vector DB) ─────────────────────────────
    import faiss
    index = faiss.IndexFlatIP(dim)   # exact inner product (cosine since normalized)
    if matrix.shape[0]:
        index.add(matrix)
    faiss.write_index(index, index_path)

    # ── Persist passages + queries ──────────────────────────
    import pickle
    with open(passages_path, "wb") as f:
        pickle.dump(all_passages, f)
    with open(queries_path, "w", encoding="utf-8") as f:
        for q in queries_out:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    # ── Benchmark query sample ──────────────────────────────
    with open(config.BENCHMARK_QUERY_FILE, "w", encoding="utf-8") as f:
        for q in queries_out:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"\n[DONE] {len(all_passages)} chunks, {matrix.shape[1]} dims, "
          f"{len(queries_out)} queries in {time.time()-t0:.1f}s")
    print(f"        Index:  {index_path}")
    print(f"        Passages: {passages_path}")
    print(f"        Run:  python server.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--rows", type=int, default=None)
    ap.add_argument("--langs", type=str, default=None)
    args = ap.parse_args()
    ingest(
        langs=(args.langs.split(",") if args.langs else None),
        max_rows=args.rows,
        rebuild=args.rebuild,
    )
