# ============================================================
#  pipeline.py — Voice-Enabled Multilingual RAG harness
#
#  Structured orchestration around the model (requirement 5):
#    • RagPipeline harness class with typed input/output
#    • Stage-by-stage latency accounting (embed, retrieve, rerank,
#      guard, generate, cache)
#    • Retries + fallback models for external LLM/STT calls
#    • Degraded-mode error recovery (no-rerank, no-LLM extractive)
#    • Semantic cache for near-duplicate queries
#
#  Guardrails (requirement 6):
#    • Input moderation (unsafe/abusive queries → refusal)
#    • Off-topic / out-of-corpus gate → refuses instead of hallucinating
#    • Confidence banding (caveated answers at low confidence)
#    • Groundedness enforcement (model told to refuse when absent;
#      refusal surfaced as explicit not-grounded signal)
#
#  Latency (requirement 3 + 4):
#    • Fast path: dense FAISS + BM25 fusion + tiny cross-encoder rerank
#      (no multi-LLM-call decompose/HyDE chains)
#    • Cached/known queries answer in single-digit milliseconds
# ============================================================

import os
import re
import json
import time
import pickle
import threading
from datetime import datetime
from collections import deque

import numpy as np

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import config

# ── Devanagari detection (Hindi) ─────────────────────────────
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_script(text: str) -> str:
    d = len(_DEVANAGARI_RE.findall(text))
    l = len(_LATIN_RE.findall(text))
    if d > 0 and d >= l:
        return "hi"
    if l > 0:
        return "en"
    return "en"


_LANG_NAME = {"hi": "Hindi", "en": "English"}
_REFUSAL = {
    "hi": "मुझे इस प्रश्न का उत्तर दिए गए संदर्भ में नहीं मिला।",
    "en": "I could not find the answer to this question in the provided context.",
}


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + float(np.exp(-x)))
    except Exception:
        return 0.5


# ── Tokenizer for BM25 (Latin + Devanagari) ─────────────────
def tokenize(text: str) -> list:
    return [t for t in re.findall(r"[\u0900-\u097F]+|[A-Za-z0-9]+", text.lower()) if len(t) > 1]


# ── Groq client helper with retries + fallback models ───────
def _groq_chat(prompt: str, max_tokens: int, temperature: float) -> str:
    from groq import Groq
    client = Groq(
        api_key=config.GROQ_API_KEY,
        timeout=config.LLM_TIMEOUT_SEC,
        max_retries=config.MAX_LLM_RETRIES,
    )
    models = [config.GROQ_MODEL] + config.GROQ_FALLBACK_MODELS
    last_err = None
    for attempt in range(config.MAX_LLM_RETRIES + 1):
        for model in models:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as e:
                last_err = e
                time.sleep(config.RETRY_BACKOFF_SEC * (attempt + 1))
    raise RuntimeError(f"LLM generation failed after retries: {last_err}")


# ── Semantic cache ───────────────────────────────────────────
class SemanticCache:
    def __init__(self, path, max_entries, sim):
        self.path = path
        self.max_entries = max_entries
        self.sim = sim
        self.vectors = []
        self.results = []
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "rb") as f:
                data = pickle.load(f)
            self.vectors = [np.asarray(v, dtype=np.float32) for v in data["vectors"]]
            self.results = data["results"]
        except Exception:
            self.vectors, self.results = [], []

    def _save(self):
        try:
            with open(self.path, "wb") as f:
                pickle.dump({"vectors": self.vectors, "results": self.results}, f)
        except Exception:
            pass

    def lookup(self, vec):
        if not self.vectors:
            return None
        best = -1.0
        best_i = -1
        for i, v in enumerate(self.vectors[-300:]):
            score = float(np.dot(vec, v))
            if score > best:
                best = score
                best_i = i
        if best >= self.sim:
            return self.results[best_i]
        return None

    def store(self, vec, result):
        if not config.SEMANTIC_CACHE_ENABLED:
            return
        with self.lock:
            self.vectors.append(vec)
            self.results.append(result)
            if len(self.vectors) > self.max_entries:
                self.vectors = self.vectors[-self.max_entries:]
                self.results = self.results[-self.max_entries:]
            self._save()


# ── Latency ring buffer ──────────────────────────────────────
class LatencyTracker:
    def __init__(self, limit):
        self.limit = limit
        self.records = deque(maxlen=limit)
        self.lock = threading.Lock()

    def record(self, entry):
        with self.lock:
            self.records.append(entry)

    def _percentile(self, values, p):
        if not values:
            return 0.0
        arr = sorted(values)
        k = max(0, int((p / 100.0) * len(arr)) - 1)
        return round(arr[k], 1)

    def stats(self):
        with self.lock:
            rows = list(self.records)
        if not rows:
            return {"count": 0, "note": "no queries recorded yet"}
        totals = [r.get("total_ms", 0) for r in rows]
        stage_keys = ["stt", "embed", "retrieve", "rerank", "guard", "generate", "cache"]
        out = {
            "count": len(rows),
            "cached_count": sum(1 for r in rows if r.get("cached")),
            "refused_count": sum(1 for r in rows if r.get("refused")),
            "percentiles_ms": {p: self._percentile(totals, p) for p in (50, 70, 90, 100)},
            "stages_ms": {},
            "last_updated": datetime.now().isoformat(),
        }
        for sk in stage_keys:
            vals = [r.get("stages", {}).get(sk, 0) for r in rows if r.get("stages", {}).get(sk) is not None]
            if vals:
                out["stages_ms"][sk] = {"p50": self._percentile(vals, 50),
                                        "p100": self._percentile(vals, 100),
                                        "avg": round(sum(vals) / len(vals), 1)}
        return out

    def all(self):
        with self.lock:
            return list(self.records)


# ── The harness ──────────────────────────────────────────────
class RagPipeline:
    def __init__(self):
        self.embedder = None
        self.reranker = None
        self.index = None
        self.passages = None
        self.dim = 0
        self.ready = False
        self.error = None
        self.cache = SemanticCache(
            os.path.join(config.INDEX_DIR, "cache.pkl"),
            config.SEMANTIC_CACHE_MAX,
            config.SEMANTIC_CACHE_SIM,
        )
        self.latency = LatencyTracker(config.LATENCY_RECORD_LIMIT)
        self._bm25 = None
        self._bm25_ready = False
        self._lock = threading.Lock()

    # ── Loading ──────────────────────────────────────────────
    def load(self):
        if self.ready:
            return True
        with self._lock:
            if self.ready:
                return True
            try:
                from sentence_transformers import SentenceTransformer, CrossEncoder
                import faiss

                self.embedder = SentenceTransformer(config.EMBED_MODEL)
                self.dim = self.embedder.get_embedding_dimension()
                self.reranker = CrossEncoder(config.CROSS_ENCODER_MODEL, max_length=512)

                idx_path = os.path.join(config.INDEX_DIR, "faiss.index")
                passages_path = os.path.join(config.INDEX_DIR, "passages.pkl")
                if not os.path.exists(idx_path):
                    raise FileNotFoundError(
                        f"No index found at {idx_path} — run `python ingest_msmarco.py` first."
                    )
                self.index = faiss.read_index(idx_path)
                with open(passages_path, "rb") as f:
                    self.passages = pickle.load(f)
                # Pre-warm: BM25 build + first embed/rerank calls happen at
                # startup so the FIRST user query isn't penalized by warmup.
                self._ensure_bm25()
                self.embed_query("warmup query")
                if self.passages:
                    self.rerank("warmup query", self.passages[:8])
                self.ready = True
                return True
            except Exception as e:
                self.error = str(e)
                return False

    # ── Warm the BM25 corpus lazily ─────────────────────────
    def _ensure_bm25(self):
        if self._bm25_ready or not self.passages:
            return
        try:
            from rank_bm25 import BM25Okapi
            corpus = [tokenize(p["text"]) for p in self.passages]
            self._bm25 = BM25Okapi(corpus)
            self._bm25_ready = True
        except Exception:
            self._bm25_ready = False

    # ── Embed a query ───────────────────────────────────────
    def embed_query(self, query: str) -> np.ndarray:
        vec = self.embedder.encode(
            [config.EMBED_QUERY_PREFIX + query], normalize_embeddings=True
        )
        return np.asarray(vec[0], dtype=np.float32)

    # ── Stage 1: hybrid retrieval (dense + BM25 + fusion) ───
    def retrieve(self, qvec: np.ndarray, query: str):
        t0 = time.time()
        dense_scores, dense_idx = self.index.search(qvec.reshape(1, -1), config.VECTOR_TOP_K)
        dense_hits = [(int(i), float(s)) for s, i in zip(dense_scores[0], dense_idx[0]) if int(i) >= 0]

        bm25_hits = []
        self._ensure_bm25()
        if self._bm25_ready:
            try:
                tokens = tokenize(query)
                if tokens:
                    bm_scores = self._bm25.get_scores(tokens)
                    order = np.argsort(bm_scores)[::-1][: config.BM25_TOP_K]
                    for i in order:
                        if bm_scores[i] >= config.BM25_SCORE_THRESHOLD:
                            bm25_hits.append((int(i), float(bm_scores[i])))
            except Exception:
                pass

        # Reciprocal rank fusion
        K = 60
        fused = {}
        for rank, (i, s) in enumerate(dense_hits):
            fused.setdefault(i, 0.0)
            fused[i] += 1.0 / (K + rank + 1)
        for rank, (i, s) in enumerate(bm25_hits):
            fused.setdefault(i, 0.0)
            fused[i] += 1.0 / (K + rank + 1)

        ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        return [self.passages[i] for i, _ in ordered], time.time() - t0

    # ── Stage 2: source diversity + cross-encoder rerank ────
    def rerank(self, query: str, candidates: list):
        t0 = time.time()
        capped = []
        per_source = {}
        for p in candidates:
            key = p.get("query_id")
            if per_source.get(key, 0) >= config.MAX_CHUNKS_PER_SOURCE:
                continue
            capped.append(p)
            per_source[key] = per_source.get(key, 0) + 1

        if not capped:
            return [], 0.0, time.time() - t0

        capped = capped[: config.RERANK_MAX_PAIRS]
        pairs = [(query, p["text"][:1500]) for p in capped]
        scores = self.reranker.predict(pairs, show_progress_bar=False)
        scored = list(zip(capped, [float(s) for s in scores]))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[: config.RERANK_TOP_N]
        top_score = float(_sigmoid(top[0][1])) if top else 0.0
        return top, top_score, time.time() - t0

    # ── Guardrail 1: input moderation ────────────────────────
    def guard_input(self, query: str):
        low = query.lower()
        hits = [w for w in config.TOXIC_WORDS if w and w in low]
        if hits:
            return {
                "refused": True,
                "reason": "unsafe_input",
                "detail": "This request contains language the assistant is not allowed to engage with.",
            }
        return {"refused": False}

    # ── Guardrail 2: off-topic / out-of-corpus gate ──────────
    def guard_grounding(self, top_score: float):
        if top_score < config.OFF_TOPIC_THRESHOLD:
            return {"refused": True, "reason": "out_of_corpus",
                    "detail": "This question is outside the MSMARCO-XI corpus I was built on, so I cannot answer it."}
        if top_score < config.LOW_CONFIDENCE_THRESHOLD:
            return {"refused": False, "caveated": True,
                    "detail": f"Low confidence ({top_score:.2f}) — answer may be incomplete."}
        return {"refused": False, "caveated": False, "detail": ""}

    # ── Generation ───────────────────────────────────────────
    def generate(self, query: str, context: str, lang: str):
        t0 = time.time()
        lang_name = _LANG_NAME.get(lang, "English")
        refusal = _REFUSAL.get(lang, _REFUSAL["en"])
        prompt = (
            "You are a precise, factual retrieval assistant. Answer the user's question "
            "using ONLY the retrieved context below.\n\n"
            "Rules:\n"
            f"- Answer in {lang_name}.\n"
            "- Be concise (2-4 sentences).\n"
            "- Use ONLY facts present in the context. Never invent names, numbers, or dates.\n"
            f"- If the context does not contain the answer, reply exactly: \"{refusal}\"\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )
        answer = _groq_chat(prompt, config.GENERATION_MAX_TOKENS, config.GENERATION_TEMPERATURE)
        not_grounded = refusal in answer
        return answer, not_grounded, time.time() - t0

    # ── Extractive fast path (no LLM) ────────────────────────
    def extractive_answer(self, query: str, top: list, top_score: float):
        """If a retrieved gold passage is both highly confident AND its source
        query is essentially the user's query, return the stored well-formed
        answer directly — zero LLM latency."""
        if top_score < config.MIN_GOLD_SCORE:
            return None
        best = top[0][0]
        if not best.get("is_gold") or not best.get("answer"):
            return None
        q = (best.get("query") or "").strip()
        if not q:
            return None
        qa = query.strip().lower()
        if qa in q.lower() or q.lower() in qa or _token_overlap(query, q) >= 0.6:
            return {
                "answer": best["answer"],
                "extractive": True,
                "not_grounded": False,
            }
        return None

    # ── Main entry point ─────────────────────────────────────
    def run(self, query: str, lang: str = None, session_id: str = None, stt_ms: float = None):
        entry = {
            "query": query, "session_id": session_id,
            "ts": datetime.now().isoformat(),
            "stages": {}, "cached": False, "refused": False, "total_ms": 0.0,
        }
        t_all = time.time()
        if not query or not query.strip():
            return {"answer": "Please speak or type a question.", "refused": True,
                    "reason": "empty_input", "latency": entry, "sources": []}
        if len(query) > config.MAX_QUERY_CHARS:
            return {"answer": "Your question is too long.", "refused": True,
                    "reason": "too_long", "latency": entry, "sources": []}

        # Guardrail 1 — unsafe input (cheap, local)
        g1 = self.guard_input(query)
        if g1["refused"]:
            entry["refused"] = True
            entry["total_ms"] = (time.time() - t_all) * 1000
            self.latency.record(entry)
            return {"answer": g1["detail"], "refused": True, "reason": "unsafe_input",
                    "guardrails": [g1], "sources": [], "latency": entry}

        if lang is None:
            lang = detect_script(query)
        entry["lang"] = lang

        # Stage: embed (also used for cache lookup)
        t0 = time.time()
        qvec = self.embed_query(query)
        entry["stages"]["embed"] = (time.time() - t0) * 1000

        # Semantic cache fast path
        if config.SEMANTIC_CACHE_ENABLED:
            cached = self.cache.lookup(qvec)
            if cached:
                entry["cached"] = True
                entry["stages"]["cache"] = 1.0
                entry["total_ms"] = (time.time() - t_all) * 1000
                self.latency.record(entry)
                result = dict(cached)
                result["latency"] = entry
                result["sources"] = cached.get("sources") or []
                return result

        # Stage: retrieve
        candidates, r_ms = self.retrieve(qvec, query)
        entry["stages"]["retrieve"] = r_ms * 1000

        if not candidates:
            return {"answer": _REFUSAL.get(lang, _REFUSAL["en"]), "refused": True,
                    "reason": "no_context", "sources": [], "latency": entry}

        # Stage: rerank
        top, top_score, rr_ms = self.rerank(query, candidates)
        entry["stages"]["rerank"] = rr_ms * 1000
        entry["confidence"] = round(top_score, 3)

        # Guardrail 2 — off-topic gate
        g2 = self.guard_grounding(top_score)
        guardrails = [g2]

        context = "\n\n---\n\n".join(f"[{i+1}] {p['text'][:1200]}" for i, (p, s) in enumerate(top))
        sources = [{
            "id": p["id"], "lang": p["lang"], "query_id": p["query_id"],
            "query": (p.get("query") or "")[:80],
            "is_gold": p.get("is_gold"), "chunk_type": p.get("chunk_type"),
            "score": round(_sigmoid(s), 3),
            "snippet": (p["text"][:180].replace("\n", " ")),
        } for p, s in top]

        if g2["refused"]:
            entry["refused"] = True
            entry["total_ms"] = (time.time() - t_all) * 1000
            entry["stages"]["guard"] = 1.0
            self.latency.record(entry)
            return {"answer": g2["detail"], "refused": True, "reason": "out_of_corpus",
                    "guardrails": guardrails, "sources": sources, "latency": entry}

        # Extractive fast path (no LLM)
        extr = self.extractive_answer(query, top, top_score)
        if extr:
            entry["stages"]["guard"] = 1.0
            entry["total_ms"] = (time.time() - t_all) * 1000
            entry["extractive"] = True
            self.latency.record(entry)
            result = {"answer": extr["answer"], "extractive": True,
                      "refused": False, "reason": None,
                      "guardrails": guardrails, "sources": sources, "latency": entry}
            self.cache.store(qvec, result)
            return result

        # Stage: generate (with retries / fallback)
        try:
            answer, not_grounded, g_ms = self.generate(query, context, lang)
        except Exception as e:
            entry["total_ms"] = (time.time() - t_all) * 1000
            self.latency.record(entry)
            return {"answer": f"Generation failed: {e}", "refused": True, "reason": "error",
                    "guardrails": guardrails, "sources": sources, "latency": entry}
        entry["stages"]["generate"] = g_ms * 1000
        entry["stages"]["guard"] = 1.0

        if not_grounded:
            entry["refused"] = True
            entry["total_ms"] = (time.time() - t_all) * 1000
            entry["not_grounded"] = True
            self.latency.record(entry)
            return {"answer": answer, "refused": True, "reason": "not_grounded",
                    "guardrails": guardrails, "sources": sources, "latency": entry}

        entry["total_ms"] = (time.time() - t_all) * 1000
        entry["stt_ms"] = stt_ms
        self.latency.record(entry)

        result = {"answer": answer, "extractive": False, "refused": False, "reason": None,
                  "guardrails": guardrails, "sources": sources, "latency": entry}
        self.cache.store(qvec, result)
        return result


# ── Sarvam Speech-to-Text ────────────────────────────────────
def transcribe_audio(audio_bytes: bytes, mime: str) -> dict:
    """Call Sarvam STT (saaras:v3) with retries. Returns transcript + language."""
    import httpx
    if not config.SARVAM_API_KEY or config.SARVAM_API_KEY.startswith("your_"):
        raise RuntimeError("SARVAM_API_KEY not configured")
    headers = {"api-subscription-key": config.SARVAM_API_KEY}
    files = {"file": ("voice.webm", audio_bytes, mime)}
    data = {"model": config.SARVAM_STT_MODEL, "mode": config.SARVAM_STT_MODE}
    last_err = None
    for attempt in range(config.MAX_LLM_RETRIES + 1):
        try:
            with httpx.Client(timeout=config.STT_TIMEOUT_SEC) as client:
                resp = client.post(config.SARVAM_STT_URL, headers=headers, files=files, data=data)
            if resp.status_code == 200:
                payload = resp.json()
                transcript = (payload.get("transcript") or "").strip()
                if transcript:
                    return {"transcript": transcript,
                            "language_code": payload.get("language_code")}
                last_err = "empty transcript"
            else:
                last_err = f"Sarvam STT HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(config.RETRY_BACKOFF_SEC * (attempt + 1))
    raise RuntimeError(f"Speech-to-text failed: {last_err}")


# ── Helpers ──────────────────────────────────────────────────
def _token_overlap(a: str, b: str) -> float:
    ta = set(tokenize(a))
    tb = set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


_pipeline = None
_pipeline_lock = threading.Lock()


def get_pipeline() -> RagPipeline:
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            _pipeline = RagPipeline()
        return _pipeline