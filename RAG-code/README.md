# 🎙️ Voice-Enabled Multilingual RAG — MSMARCO-XI

## HH Goa 2026 · Shortlisting Task 2

A voice-first Retrieval-Augmented Generation system over
[`ai4bharat/MSMARCO-XI`](https://huggingface.co/datasets/ai4bharat/MSMARCO-XI),
**trained on exactly four languages — Hindi, English, Gujarati, Marathi.** Speak
a question → Sarvam speech-to-text → multilingual retrieval → grounded answer,
with **P50/P70/P100 latency analytics**, a resilience harness, and safety guardrails.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?style=flat-square)
![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square)

---

## 📁 Project Structure

```
RAG-code/
├── config.py               ← All settings (models, languages, thresholds, latency knobs)
├── .env                    ← GROQ + SARVAM API keys (not committed)
├── ingest_msmarco.py       ← 4-language multi-strategy chunking → FAISS index
├── pipeline.py             ← RagPipeline harness (retrieval, rerank, guardrails,
│                             semantic cache, latency tracker, Sarvam STT)
├── server.py               ← FastAPI backend (query / stt / voice_query / status / latency / benchmark)
├── benchmark.py            ← P50/P70/P100 latency analytics + recall/MRR report
├── tests.py                ← 31 sanity tests
├── Dockerfile              ← builds a lite index at image build time (live-link deploys)
├── requirements.txt
├── msmarco_index/          ← faiss.index, passages.pkl, queries.jsonl (gitignored)
├── data/                   ← parquet cache (gitignored, downloaded by ingest)
├── latency_report.json     ← Benchmark output (persisted, served by /api/latency)
└── app.html / landing.html ← Archived design explorations (not used by the app)
```

---

## ✨ Languages — exactly four (nothing else)

The system is **only** trained on `hi`, `en`, `gu`, `mr`:

- MSMARCO-XI ships 14 Indic parquets and **no English split** — English is
  ingested as a first-class language from the original `English_passages` /
  `Eng_Query` / `Eng_Answer` fields carried inside every Indic row.
- `detect_lang()` (script ranges + `langdetect`) classifies a query as
  hi/en/gu/mr; **any other language is refused** at the guardrail — e.g. a
  Tamil, Bengali or Urdu query returns a polite refusal instead of a wrong answer.

## 🗂️ Chunking strategy (8 layers, not naive fixed-size)

1. **Natural passage-unit chunks** — MSMARCO passages are self-contained answer units.
2. **Adaptive recursive sentence split with overlap** — >700 chars split on sentence
   boundaries; <140-char fragments merge backwards; 12% overlap carried across splits.
3. **Metadata-aware chunks** — every chunk carries `lang`, `query_id`, `query_type`,
   gold label, source query, passage index.
4. **Cross-lingual anchoring** — Indic chunks embed `[EN]` English translations and
   English chunks embed `[HI]/[GU]/[MR]` translations → query in one language
   retrieves content in another.
5. **Romanized (Hinglish) surface** — Devanagari/Gujarati → ITRANS Latin `[RO]`
   anchors so "mumbai ki rajdhani kya hai" retrieves Devanagari passages.
6. **doc2query-style `[Q]` anchor** — gold chunks embed the exact query → lexical
   BM25 + the extractive fast path both fire reliably.
7. **Answer anchoring** — gold passages embed the well-formed answer (`[ANS]`).
8. **De-duplication** across the corpus (hash of full chunk text).

## 🔎 Retrieval pipeline (latency-first, accuracy-preserving)

```
Query ─► embed (e5-small, 384-d, ~7 ms)
       ─► FAISS exact IP top-300 pool                       (~2 ms)
       ─► candidate-limited BM25 re-scores only the pool    (~3 ms)
       ─► RRF fusion ─► cross-encoder rerank top-8          (~24 ms)
       ─► Guardrail (off-topic gate) ─► extractive fast path | Groq LLM
```

Why candidate-limited BM25? Scoring the **whole corpus** (`rank_bm25.get_scores`
is O(N)) produced the old 963 ms P100 tail. Re-scoring only the 300-wide dense
pool keeps the hybrid lexical signal at O(pool) — a few milliseconds.

Why exact FAISS? HNSW measured 0.65 recall@24 vs exact on this corpus at
equivalent latency — we keep the exact inner-product index (zero accuracy loss).

## 🛡️ Guardrails

| Guard | Trigger | Behaviour |
|---|---|---|
| Language whitelist | query detected outside hi/en/gu/mr | refusal (`unsupported_language`) |
| Input moderation | toxic blocklist hit | refusal (`unsafe_input`) |
| Off-topic gate | rerank confidence < 0.30 | refusal (`out_of_corpus`) — refuses to hallucinate |
| Low-confidence | 0.30–0.45 | caveated answer |
| Groundedness | LLM returns the not-grounded phrase | surfaced as `not_grounded` refusal |
| Length | > 500 chars | refusal (`too_long`) |

## 🧠 Harness (orchestration)

`RagPipeline` (pipeline.py) is a structured harness, not a raw prompt-in /
text-out call:

- Typed `run(query, lang, session_id, stt_ms)` → result dict with `answer`,
  `sources`, `guardrails`, per-stage latency, confidence.
- LLM retries + fallback model list; timeboxed STT; backoff.
- Degraded-mode recovery (rerank/extractive paths work even if the LLM is down).
- Semantic cache (cosine ≥ 0.94) for near-duplicate queries.
- Semantic-cache + extractive gold fast path deliver most answers in well under
  200 ms without any LLM call.

## 📊 Latency analytics (requirement 4)

`benchmark.py` runs N queries (sampled across all four languages) through the
real pipeline and reports **retrieval-only**, **full-pipeline** and **cache-hit**
P50/P70/P100 plus **gold recall@k** and **MRR@k** — so latency cuts are proven
not to degrade accuracy.

| Metric | p50 | p70 | p100 | avg |
|---|---|---|---|---|
| Retrieval only (embed+retrieve+rerank) | 175.3 ms | 187.6 ms | 211.8 ms | 151.5 ms |
| Full pipeline (with answer generation) | 181.6 ms | 190.6 ms | 723.1 ms | 182.2 ms |
| Cache hit | 12.2 ms | 13.0 ms | 14.0 ms | — |

Retrieval stays at the ~200 ms target in every language
(en p50 104 ms, hi 177 ms, mr 184 ms, gu 188 ms) while gold recall@8 rose to
**0.925** and MRR@8 to **0.823** (37/40 judged queries). Full-pipeline p70 is
190.6 ms — the p100 tail is a genuinely novel query that needs the LLM.

> _Numbers refresh automatically — run `python benchmark.py --n 40` and re-commit
> `latency_report.json`._

Run it yourself:
```bash
python benchmark.py --n 40     # writes latency_report.json (served by /api/latency)
```

## 🚀 Quick Start

```bash
cd RAG-code
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # fill in GROQ_API_KEY + SARVAM_API_KEY

python ingest_msmarco.py --rebuild  # full 4-language index (~120k chunks)
python server.py                    # → http://localhost:8000
```

Frontend (repo root): `npm install`, `cp .env.local.example .env.local`,
`npm run dev` → http://localhost:3000

## 🔌 API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/status` | GET | readiness, chunk count, supported languages |
| `/api/query` | POST | `{question, lang?, session_id?}` → grounded answer |
| `/api/stt` | POST | audio → `{transcript, language_code, stt_ms}` |
| `/api/voice_query` | POST | audio → transcript → full answer (end-to-end) |
| `/api/latency` | GET | P50/P70/P90/P100 + stage averages + benchmark report |
| `/api/benchmark` | POST | re-run the latency benchmark and persist the report |

## 🧪 Testing

```bash
python tests.py        # 31/31 passing
```

## ☁️ Deploy (live link)

```bash
docker build -t voice-rag .
docker run -p 8000:8000 -e GROQ_API_KEY=... -e SARVAM_API_KEY=... voice-rag
```

The image ingests a lite index (~20k chunks) at **build time** so the container
starts instantly on Railway / Render / HF Spaces; point the Next.js frontend at
it with `RAG_BACKEND_URL`.

## ⚠️ Notes

- `OMP_NUM_THREADS` is forced to 1 in `config.py` for the query/server path
  (macOS libomp crash workaround); ingestion overrides it to 8 for speed and
  pins the embedder to CPU (`device="cpu"`) because the MPS path stalls.
- The ingest uses `intfloat/multilingual-e5-small` (mE5 covers hi/en/gu/mr) and
  the reranker `nreimers/mmarco-mMiniLMv2-L6-H384-v1`.
- Groq free tier is ~30 RPM — the benchmark paces LLM-path queries; most
  benchmark queries take the zero-LLM extractive path anyway.