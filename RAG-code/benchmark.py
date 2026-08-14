# ============================================================
#  benchmark.py — Latency analytics (requirement 4)
#
#  Runs a reasonable number of test queries (default 120) and
#  reports P50 / P70 / P100 latency for:
#    • retrieval-only  (embed → retrieve → rerank)
#    • full pipeline    (retrieval → LLM generation → answer)
#    • cache-hit        (second pass over the same queries)
#  plus a recall@k accuracy check (was the gold passage retrieved)
#  so we can prove latency cuts did not degrade accuracy.
#
#  Run:  python benchmark.py [--n 120]
# ============================================================

import os
import json
import time
import argparse

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import numpy as np
import config
from pipeline import get_pipeline, detect_script


def percentile(values, p):
    if not values:
        return 0.0
    arr = np.array(sorted(values), dtype=float)
    k = max(0, int(np.ceil((p / 100.0) * len(arr))) - 1)
    return round(float(arr[k]), 1)


def load_queries(n):
    path = config.BENCHMARK_QUERY_FILE
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
    if not rows:
        return []
    rng = np.random.RandomState(42)
    if len(rows) > n:
        rows = [rows[i] for i in rng.choice(len(rows), n, replace=False)]
    return rows


def run_benchmark(pipeline=None, n=None):
    pipeline = pipeline or get_pipeline()
    n = n or config.BENCHMARK_QUERIES
    if not pipeline.load():
        return {"error": f"Pipeline failed to load: {pipeline.error}"}

    rows = load_queries(n)
    if not rows:
        return {"error": "No benchmark queries found. Run ingest_msmarco.py first."}

    # Groq free tier rate-limits at ~30 requests/min; pace generation calls so
    # the benchmark doesn't stall on 429 backoff and doesn't starve the server.
    pace = getattr(config, "BENCHMARK_PACE_SEC", 2.2)

    cold_total, cold_retrieval, cache_total = [], [], []
    recall_hits = 0

    for i, row in enumerate(rows):
        q = (row.get("query") or "").strip()
        if not q:
            continue
        lang = detect_script(q)
        r = pipeline.run(q, lang=lang, session_id="benchmark")
        lat = r.get("latency", {})
        stages = lat.get("stages", {})
        ret_ms = sum(stages.get(k, 0) for k in ("embed", "retrieve", "rerank"))
        cold_total.append(lat.get("total_ms", 0))
        cold_retrieval.append(ret_ms)
        if any(s.get("is_gold") for s in r.get("sources", [])):
            recall_hits += 1
        time.sleep(pace)

    # Second pass → cache-hit latency (no LLM calls, so it is fast)
    for i, row in enumerate(rows[: min(len(rows), n)]):
        q = (row.get("query") or "").strip()
        if not q:
            continue
        r = pipeline.run(q, lang=detect_script(q), session_id="benchmark")
        cache_total.append(r.get("latency", {}).get("total_ms", 0))
        time.sleep(0.15)

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_queries": len(rows),
        "pipeline": {
            "retrieval_only_ms": {
                "p50": percentile(cold_retrieval, 50),
                "p70": percentile(cold_retrieval, 70),
                "p100": percentile(cold_retrieval, 100),
                "avg": round(float(np.mean(cold_retrieval)), 1) if cold_retrieval else 0.0,
            },
            "full_pipeline_ms": {
                "p50": percentile(cold_total, 50),
                "p70": percentile(cold_total, 70),
                "p100": percentile(cold_total, 100),
                "avg": round(float(np.mean(cold_total)), 1) if cold_total else 0.0,
            },
            "cache_hit_ms": {
                "p50": percentile(cache_total, 50),
                "p70": percentile(cache_total, 70),
                "p100": percentile(cache_total, 100),
            },
        },
        "accuracy": {
            "gold_recall_at_k": round(recall_hits / len(rows), 3) if rows else 0.0,
            "gold_retrieved": f"{recall_hits}/{len(rows)}",
        },
        "target_ms": 200,
    }

    with open(config.LATENCY_REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    args = ap.parse_args()
    run_benchmark(n=args.n)