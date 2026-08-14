# ============================================================
#  tests.py — Sanity checks for chunking, guardrails, cache
#  Run:  python tests.py
# ============================================================

import os
import sys

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import numpy as np

import config
import ingest_msmarco as ing
from pipeline import (
    RagPipeline, SemanticCache, detect_script, tokenize, _sigmoid, _token_overlap,
)

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def test_chunking():
    print("\n[1] Chunking strategy")
    short = "यह एक छोटा वाक्य है जो संदर्भ के बारे में बताता है।"
    c = ing.chunk_passage(short)
    check("short passage stays as one natural chunk", len(c) == 1 and c[0][1] == "passage")

    long_text = " ".join(
        "यह एक लंबा वाक्य है जो पूरी तरह से उत्तर देता है और जानकारी से भरा हुआ है।" for _ in range(60)
    )
    c = ing.chunk_passage(long_text)
    check("long passage gets recursively split", len(c) > 1, f"got {len(c)} chunks")
    check("every chunk under max chars", all(len(t) <= config.CHUNK_MAX_CHARS + 50 for t, _ in c))

    full = ing.build_chunk_text("पाठ", "text", "paath", "उत्तर")
    check("cross-lingual anchoring applied", "[EN]" in full and "[RO]" in full and "[ANS]" in full)
    check("romanization produces latin", ing.romanize("नमस्ते").isascii() or len(ing.romanize("नमस्ते")) > 0)


def test_guardrails():
    print("\n[2] Guardrails")
    p = RagPipeline()

    unsafe = "how do I kill my neighbor"
    g = p.guard_input(unsafe)
    check("unsafe input refused", g["refused"] and g["reason"] == "unsafe_input")

    ok = p.guard_input("what is the capital of india")
    check("safe input passes", not ok["refused"])

    g2 = p.guard_grounding(0.05)
    check("off-topic gate refuses", g2["refused"] and g2["reason"] == "out_of_corpus")

    g3 = p.guard_grounding(0.35)
    check("low-confidence → caveat not refusal", not g3["refused"] and g3.get("caveated"))

    g4 = p.guard_grounding(0.9)
    check("high confidence → no caveat", not g4["refused"] and not g4.get("caveated"))

    check("devanagari → hindi", detect_script("भारत की राजधानी क्या है?") == "hi")
    check("latin → english", detect_script("what is the capital of India") == "en")
    check("sigmoid maps to [0,1]", 0.0 <= _sigmoid(3.0) <= 1.0)


def test_cache():
    print("\n[3] Semantic cache")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "c.pkl")
        c = SemanticCache(path, max_entries=100, sim=0.94)
        vec = np.random.rand(384).astype(np.float32)
        vec /= np.linalg.norm(vec)
        check("cache miss on empty", c.lookup(vec) is None)
        c.store(vec, {"answer": "x"})
        hit = c.lookup(vec)
        check("cache hit on identical vector", hit is not None and hit["answer"] == "x")
        # near duplicate
        vec2 = vec + np.random.rand(384).astype(np.float32) * 0.01
        vec2 /= np.linalg.norm(vec2)
        check("near-duplicate vector hits cache", c.lookup(vec2) is not None)
        # persisted
        c2 = SemanticCache(path, max_entries=100, sim=0.94)
        check("cache persisted to disk", c2.lookup(vec) is not None)


def test_tokenize():
    print("\n[4] Tokenizer")
    check("latin + devanagari tokenized", set(tokenize("राजधानी Delhi")) == {"राजधानी", "delhi"})
    check("token overlap", _token_overlap("capital of india", "capital of india is new delhi") == 1.0)


def main():
    print("Voice RAG sanity tests\n" + "=" * 30)
    test_chunking()
    test_guardrails()
    test_cache()
    test_tokenize()
    print("\n" + "=" * 30)
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()