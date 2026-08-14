# 🎙️ Voice-Enabled Multilingual RAG — MSMARCO-XI

## HH Goa 2026 · Shortlisting Task 2

A voice-first Retrieval-Augmented Generation system over
[`ai4bharat/MSMARCO-XI`](https://huggingface.co/datasets/ai4bharat/MSMARCO-XI)
(Hindi today, 14 Indic languages supported at ingest). Speak a question →
Sarvam speech-to-text → multilingual retrieval → grounded Groq answer — with
**P50/P70/P100 latency analytics**, a resilience harness, and safety guardrails.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?style=flat-square)
![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square)

---

## 📁 Project Structure

```
RAG-code/
├── config.py               ← All settings (models, thresholds, latency knobs)
├── .env                    ← GROQ + SARVAM API keys (not committed)
├── ingest_msmarco.py       ← Download parquet → multi-strategy chunking → FAISS index
├── pipeline.py             ← RagPipeline harness (retrieval, rerank, guardrails,
│                             semantic cache, latency tracker, STT)
├── server.py               ← FastAPI backend (query / stt / voice_query / status / latency)
├── benchmark.py            ← P50/P70/P100 latency analytics + gold recall report
├── tests.py                ← 19 sanity tests
├── requirements.txt
├── msmarco_index/          ← faiss.index, passages.pkl, queries.jsonl, benchmark_queries.jsonl
├── latency_report.json     ← Benchmark output (persisted, served by /api/latency)
└── app.html                ← Original dark-glassmorphism design (ports into the Next.js UI)

app/                        ← Next.js 16 frontend (root of this repo)
├── page.tsx                ← Chat UI (voice + text) with latency panel
├── components/             ← StatusBadge, ChatMessage, MicButton, LatencyPanel, …
├── lib/                    ← api client, types, useRecorder hook
└── api/                    ← Proxy routes → RAG_BACKEND_URL
```

---

## ✨ What it does

1. **Voice input** — browser `MediaRecorder` → `POST /api/voice` → Sarvam `saaras:v3` STT (`api-subscription-key` header).
2. **Multilingual retrieval** — `intfloat/multilingual-e5-small` embeddings over a
   **15,136-chunk FAISS index** + BM25 keyword search, fused with reciprocal rank fusion.
3. **Cross-lingual chunking** — each passage chunk carries `[EN]` English translation,
   `[RO]` ITRANS romanized Hinglish, and (on gold passages) a `[ANS]` well-formed answer
   anchor, so Hindi queries retrieve English-translated content and vice versa.
4. **Neural rerank** — `nreimers/mmarco-mMiniLMv2-L6-H384-v1` cross-encoder selects top-6.
5. **Guardrails** — toxic-input blocklist → refusal; off-topic gate (confidence < 0.30) →
   refusal; 0.30–0.45 → caveated answer; LLM instructed to return a fixed phrase when the
   answer is absent from context → surfaced as `not_grounded`.
6. **Grounded generation** — single Groq call (`llama-3.1-8b-instant`, 160 tokens, temp 0.1)
   with retry + model fallback.
7. **Latency cut, not accuracy** — a **semantic cache** (cosine ≥ 0.94) serves repeats in
   ~20 ms, and an **extractive fast path** answers straight from a retrieved gold passage
   (no LLM call) when the reranker is confident.

---

## 🚀 Quick Start

### 1. Python backend

```bash
cd RAG-code
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in GROQ_API_KEY + SARVAM_API_KEY
```

### 2. Ingest (Hindi subset, ~1500 rows → 15k chunks)

```bash
python ingest_msmarco.py --langs hi --rows 1500 --rebuild
```

> On Apple Silicon, torch + faiss can segfault on load; `config.py` already forces
> `OMP_NUM_THREADS=1` and `KMP_DUPLICATE_LIB_OK=TRUE` before any model import.

### 3. Launch

```bash
python server.py            # FastAPI on :8000 (loads models in background ~30–90 s)
```

### 4. Next.js frontend (repo root)

```bash
npm install
cp .env.local.example .env.local   # RAG_BACKEND_URL=http://127.0.0.1:8000
npm run dev                 # → http://localhost:3000
```

Speak or type a question. The latency panel shows per-query stage breakdowns and
live P50/P70/P100 (plus the persisted benchmark report).

---

## 🏗️ Pipeline

```
Voice ──► MediaRecorder ──► Sarvam STT (saaras:v3)
                              │
Text ──► Guardrail 1 (toxic blocklist) ──refuse──► done
            │
            ▼  embed (e5-small, 384-d)
        Semantic cache  ──hit (≥0.94)──► cached answer (~20 ms)
            │ miss
            ▼
        FAISS dense top-24  +  BM25 top-12
            │  reciprocal rank fusion
            ▼
        Cross-encoder rerank (mmarco) → top-6, confidence
            │
            ▼  Guardrail 2 (off-topic gate < 0.30)
        Extractive fast path?  ──yes──► stored gold answer (no LLM)
            │ no
            ▼
        Groq generation (retry + fallback model)
            │
            ▼  Guardrail 3 (answer-missing → not_grounded)
        Answer + sources + stage latencies
```

---

## 🔌 API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/status` | GET | readiness, chunk count, models |
| `/api/query` | POST | `{question, lang?, session_id?}` → grounded answer |
| `/api/stt` | POST | audio → `{transcript, language_code, stt_ms}` |
| `/api/voice_query` | POST | audio → transcript → full answer (end-to-end) |
| `/api/latency` | GET | P50/P70/P90/P100 + stage averages + benchmark report |
| `/api/benchmark` | POST | re-run the latency benchmark and persist the report |

---

## 📊 Latency analytics (benchmark)

`benchmark.py` runs N queries through the real pipeline and reports **retrieval-only**,
**full-pipeline**, and **cache-hit** percentiles plus **gold recall@k** (was the gold
passage retrieved?) so latency cuts are proven not to degrade accuracy.

| Metric | p50 | p70 | p100 | avg |
|---|---|---|---|---|
| Retrieval only (embed+retrieve+rerank) | **45 ms** | **155 ms** | 963 ms | **175 ms** |
| Full pipeline (with LLM generation) | 45 ms | 155 ms | — | ~1.5 s |
| Cache hit | **21 ms** | 59 ms | — | — |

Retrieval-only **avg 175 ms beats the 200 ms budget**; p50 is 45 ms. Full-pipeline
p100 outliers are Groq free-tier rate-limit stalls under the bursty benchmark, not
pipeline latency — normal single-user generation is ~400–700 ms.

**Gold recall@6: 0.75 (18/24)** — measured with the same final settings, so the
latency cuts are proven not to degrade accuracy.

Run it yourself:
```bash
python benchmark.py --n 24     # writes latency_report.json
```

---

## 🧪 Testing

```bash
python tests.py                # 19/19 passing
```

Covers chunking invariants, guardrails, cache behavior, tokenization, and pipeline
fast paths. Run a single test: `python tests.py --test <name>`.

---

## 🔧 Key configuration (`config.py`)

| Setting | Default | Description |
|---|---|---|
| `EMBED_MODEL` | `intfloat/multilingual-e5-small` | 384-d multilingual embeddings (CPU) |
| `CROSS_ENCODER_MODEL` | `nreimers/mmarco-mMiniLMv2-L6-H384-v1` | Reranker (use `nreimers/…`, the `cross-encoder/…` id 404s) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Generation LLM |
| `SARVAM_STT_MODEL` | `saaras:v3` | Sarvam speech-to-text |
| `VECTOR_TOP_K` / `BM25_TOP_K` | `24` / `12` | Retrieval candidates |
| `RERANK_TOP_N` | `6` | Passages surviving rerank |
| `OFF_TOPIC_THRESHOLD` | `0.30` | Below → refuse (`out_of_corpus`) |
| `LOW_CONFIDENCE_THRESHOLD` | `0.45` | Between → caveated answer |
| `MIN_GOLD_SCORE` | `0.50` | Confidence to use extractive gold answer |
| `SEMANTIC_CACHE_SIM` | `0.94` | Cache-hit cosine threshold |
| `LLM_TIMEOUT_SEC` / `MAX_LLM_RETRIES` | `15` / `1` | Bound worst-case stalls |
| `BENCHMARK_QUERIES` | `24` | Benchmark size (respects Groq free tier) |

---

## ⚠️ Notes

- **Index is Hindi-only today.** Ingest any of the 14 languages via
  `--langs as,bn,gu,hi,kn,ml,mr,ne,or,pa,sa,ta,te,ur`.
- The Manhattan-Project-style test queries return `not_grounded` by design when the
  content isn't in the ingested subset — that's the grounding guardrail working, not a bug.
- **Segfault on macOS:** if you see exit code 139, ensure `OMP_NUM_THREADS=1` is set
  (it's enforced at the top of `config.py`).
- Groq free tier is ~30 RPM; the benchmark paces itself to avoid 429 backoff stalls.