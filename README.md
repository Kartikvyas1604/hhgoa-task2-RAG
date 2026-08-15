# 🎙️ ShabdVani — Voice-Enabled Multilingual RAG over MSMARCO-XI

## HH Goa 2026 · Shortlisting Task 2

A voice-first **Retrieval-Augmented Generation** system. Speak or type a
question in **Hindi, English, Gujarati or Marathi** (only these four — nothing
else) and get a grounded, guardrailed answer end-to-end:

```
Voice ─► Sarvam STT (saaras:v3) ─► multilingual retrieval (FAISS + BM25 hybrid)
      ─► cross-encoder rerank ─► grounded answer (extractive fast path / Groq LLM)
```

Built on the [`ai4bharat/MSMARCO-XI`](https://huggingface.co/datasets/ai4bharat/MSMARCO-XI)
dataset — every engineering decision is aimed at the submission's six technical
requirements:

| # | Requirement | How this repo satisfies it |
|---|---|---|
| 1 | Speech-to-text (Sarvam or ElevenLabs) | **Sarvam `saaras:v3`** (`transcribe` mode), retried + timeboxed |
| 2 | Vast, thoughtful chunking | 8-strategy chunking: natural units, adaptive recursive split w/ overlap, metadata-aware chunks, cross-lingual `[EN]/[HI]/[GU]/[MR]` anchors, romanized (Hinglish) surface, doc2query-style `[Q]` gold anchors, answer anchoring, English chunks derived from `English_passages` |
| 3 | < 200 ms end-to-end | Exact FAISS index + **candidate-limited BM25** (O(pool), not O(corpus)) + tiny cross-encoder rerank + **extractive fast path** (gold answers, no LLM) + semantic cache |
| 4 | P50 / P70 / P100 analytics | `benchmark.py` measures retrieval-only, full-pipeline and cache-hit percentiles across N queries, per language, plus gold recall@k + MRR@k |
| 5 | Proper harness | `RagPipeline` orchestration: typed input/output, stage latency accounting, LLM retries + fallback models, degraded-mode recovery, semantic cache, benchmark endpoint |
| 6 | Guardrails | language whitelist (only hi/en/gu/mr), toxic-input refusal, off-topic confidence gate (refuses rather than hallucinates), low-confidence caveats, not-grounded refusal, over-length limit |

---

## Quick start

### 1 · Backend (FastAPI)

```bash
cd RAG-code
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in GROQ_API_KEY + SARVAM_API_KEY
```

### 2 · Ingest the 4-language index

```bash
python ingest_msmarco.py --rebuild          # full index (hi + en + gu + mr)
python ingest_msmarco.py --rebuild --lite   # ~20k-chunk index for free-tier deploys
```

> Downloads ~1.4 GB of parquet into `RAG-code/data/` (gitignored) and embeds
> ~120k chunks. `--rows N` and `--langs hi,gu,mr` tune the build.

### 3 · Launch

```bash
python server.py     # → http://localhost:8000 (models load in the background)
```

### 4 · Frontend (Next.js)

```bash
npm install
cp .env.local.example .env.local   # RAG_BACKEND_URL=http://127.0.0.1:8000
npm run dev                        # → http://localhost:3000
```

Pick a language (Auto / हिन्दी / English / ગુજરાતી / मराठी), type or hold the mic,
and watch the latency panel stream live P50/P70/P100 plus the persisted benchmark.

## Measured latency & accuracy

`python benchmark.py --n 40` on the full 4-language index (~120k chunks,
M4 CPU):

| Metric | p50 | p70 | p100 | avg |
|---|---|---|---|---|
| Retrieval only (embed+retrieve+rerank) | 175.3 ms | 187.6 ms | 211.8 ms | 151.5 ms |
| Full pipeline (with answer generation) | 181.6 ms | 190.6 ms | 723.1 ms | 182.2 ms |
| Cache hit | 12.2 ms | 13.0 ms | 14.0 ms | — |

- Retrieval is at the **~200 ms target** in every language
  (en p50 104 ms · hi 177 ms · mr 184 ms · gu 188 ms).
- Accuracy did not regress with the speed cuts — **gold recall@8 = 0.925**,
  **MRR@8 = 0.823** (37/40 judged queries).
- Full-pipeline p70 is 190.6 ms; known queries answer via the zero-LLM
  extractive path in ~12 ms, only genuinely novel phrasings call the LLM
  (that is the p100 tail).

---

## Repo layout

```
├── app/            Next.js 16 frontend (chat UI, voice recorder, latency panel)
│   ├── api/        proxy routes → RAG_BACKEND_URL
│   └── components/ LanguageSelector, Composer, ChatMessage, LatencyPanel, …
├── components/     shared UI components
├── lib/            api client, types, useRecorder (WAV encoder)
└── RAG-code/       Python backend
    ├── config.py          all settings (languages, models, latency/guardrail knobs)
    ├── ingest_msmarco.py  4-language multi-strategy chunking → FAISS index
    ├── pipeline.py        RagPipeline harness + STT + guardrails + semantic cache
    ├── server.py          FastAPI (query / stt / voice_query / status / latency / benchmark)
    ├── benchmark.py       P50/P70/P100 analytics + recall/MRR
    ├── tests.py           31 sanity checks
    ├── Dockerfile         builds a lite index at image build time
    └── latency_report.json  latest benchmark output (served by /api/latency)
```

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/status` | GET | readiness, chunk count, supported languages |
| `/api/query` | POST | `{question, lang?, session_id?}` → grounded answer + sources + stage latency |
| `/api/stt` | POST | audio → `{transcript, language_code, stt_ms}` |
| `/api/voice_query` | POST | audio → transcript → answer (end-to-end) |
| `/api/latency` | GET | live P50/P70/P100 + stage averages + benchmark report |
| `/api/benchmark` | POST | re-run the N-query benchmark and persist the report |

## Languages — exactly four

The system is trained **only** on Hindi, English, Gujarati and Marathi:

- MSMARCO-XI has no standalone English split, so English is ingested as a
  first-class language derived from the original `English_passages` /
  `Eng_Query` / `Eng_Answer` carried inside each Indic row.
- Every other language is refused at the guardrail (script + `langdetect`):
  Bengali, Tamil, Telugu, Urdu, etc. return a polite "I only speak Hindi,
  English, Gujarati, Marathi" refusal.

## Deploying the live link

- **Backend** — build `RAG-code/Dockerfile` on Railway/Render/HF Spaces
  (adds the two API keys as env vars). The image builds a small index at build
  time so it starts instantly.
- **Frontend** — `npm run build` + deploy to Vercel with
  `RAG_BACKEND_URL` pointing at the deployed backend (the API routes already
  use `process.env.RAG_BACKEND_URL`).

## Submission checklist

- [x] GitHub repo
- [ ] Live working link (deploy `RAG-code` + frontend)
- [ ] 90s team/process video → Instagram, X, LinkedIn (#RAGInGoa)
- [ ] Demo video → Instagram, X, LinkedIn (#RAGInGoa)
- [x] Submission form: https://forms.gle/MNvCjcv23Hn2Eeu58

_See `RAG-code/README.md` for the full latency report and tuning guide._