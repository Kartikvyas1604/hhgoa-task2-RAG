# ============================================================
#  config.py — Voice-Enabled Multilingual RAG (MSMARCO-XI)
#  All settings live here. Edit before running.
# ============================================================

import os
# macOS libomp conflict between torch and faiss → limit OpenMP threads
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from dotenv import load_dotenv
load_dotenv()  # reads .env file into os.environ

# ── API Keys (free tiers) ──────────────────────────────────
GROQ_API_KEY   = os.getenv('GROQ_API_KEY', 'your_groq_key_here')     # https://console.groq.com
SARVAM_API_KEY = os.getenv('SARVAM_API_KEY', 'your_sarvam_key_here') # https://dashboard.sarvam.ai

# ── Model Selection ─────────────────────────────────────────
# Multilingual embedding (handles Hindi + English + 100+ langs).
# small + fast: ~30ms embed on CPU. Prefix "query: "/"passage: " required.
EMBED_MODEL        = "intfloat/multilingual-e5-small"   # 384-dim, multilingual
EMBED_QUERY_PREFIX = "query: "
EMBED_PASS_PREFIX  = "passage: "

# Multilingual cross-encoder reranker (25MB) — fine-grained relevance
CROSS_ENCODER_MODEL = "nreimers/mmarco-mMiniLMv2-L6-H384-v1"

# Fast generation — Groq free tier, llama-3.1-8b-instant is among the fastest.
GROQ_MODEL     = "llama-3.1-8b-instant"
GROQ_BASE_URL  = "https://api.groq.com/openai/v1"
# Fallback list used by the harness if the primary model is unavailable/429s
GROQ_FALLBACK_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

# ── Sarvam Speech-to-Text ───────────────────────────────────
SARVAM_STT_URL    = "https://api.sarvam.ai/speech-to-text"
SARVAM_STT_MODEL  = "saaras:v3"
SARVAM_STT_MODE   = "transcribe"   # transcribe | translate | verbatim | translit | codemix

# ── Dataset (MSMARCO-XI) ────────────────────────────────────
DATASET_NAME      = "ai4bharat/MSMARCO-XI"
# Validation split keeps ingestion lightweight; each row carries its own
# query, well-formed answer, and ~10 passages (translated + English).
DATASET_SPLIT     = "validation"
LANGUAGES         = ["hi"]         # 13 Indic languages available: as bn gu hi kn ml mr ne or pa sa ta te ur
MAX_ROWS_PER_LANG = 3000           # rows (queries) ingested per language
MAX_PASSAGES_PER_ROW = 10          # passages stored per query row
DEDUPE_PASSAGES   = True           # drop near-identical passages across the corpus

# ── Chunking Strategy ───────────────────────────────────────
# Vast multi-strategy chunking (see ingest_msmarco.py):
#   1. Natural passage-unit chunks (MSMARCO passages are self-contained)
#   2. Adaptive recursive sentence split w/ overlap for long passages
#   3. Metadata-aware chunks (lang, query_id, gold label, answer anchor)
#   4. Cross-lingual anchoring (Hindi + English + romanized surface)
CHUNK_MAX_CHARS      = 700    # passages above this get recursively split
CHUNK_MIN_CHARS      = 140    # fragments below this merge into previous chunk
CHUNK_OVERLAP_RATIO  = 0.12   # overlap between recursive splits
ANCHOR_ENGLISH       = True   # append "[EN] " english passage for cross-lingual recall
ANCHOR_ROMANIZED     = True   # append romanized (Latin) form for Hinglish queries
ANCHOR_ANSWER        = True   # append well-formed answer to gold passage chunks

# ── Retrieval Settings ──────────────────────────────────────
VECTOR_TOP_K          = 24    # candidates from dense FAISS search
BM25_TOP_K            = 12    # candidates from BM25 keyword search (hybrid recall)
BM25_SCORE_THRESHOLD  = 0.5   # ignore weak keyword hits below this raw score
RERANK_MAX_PAIRS      = 36    # soft cap on cross-encoder pairs (no practical effect at 24+12)
RERANK_TOP_N          = 6     # chunks surviving cross-encoder rerank
MAX_CHUNKS_PER_SOURCE  = 4    # source diversity cap per query_id

# ── Guardrails ──────────────────────────────────────────────
# Off-topic / out-of-corpus gate: below this top rerank score the system
# refuses to answer rather than hallucinate.
OFF_TOPIC_THRESHOLD        = 0.30
LOW_CONFIDENCE_THRESHOLD   = 0.45  # between threshold and here → caveated answer
MIN_GOLD_SCORE             = 0.50  # confidence needed to use extractive gold answer
TOXIC_WORDS                = os.getenv('TOXIC_WORDS', 'kill,die,suicide,threat,fuck,sex,ass,rape,porn,violence,hate,terror').lower().split(',')
TOXIC_SCORE_THRESHOLD      = 0.6   # optional LLM moderation score gate
MAX_QUERY_CHARS            = 500

# ── Semantic Cache (latency) ────────────────────────────────
# Near-duplicate queries reuse a stored answer → single-digit ms latency.
SEMANTIC_CACHE_ENABLED = True
SEMANTIC_CACHE_SIM     = 0.94   # cosine sim threshold to treat queries as identical
SEMANTIC_CACHE_MAX     = 20000  # cap on cached entries

# ── Latency Analytics ───────────────────────────────────────
LATENCY_RECORD_LIMIT = 5000     # keep this many per-query records in memory
LATENCY_REPORT_FILE  = os.path.join(os.path.dirname(__file__), "latency_report.json")
BENCHMARK_QUERIES    = 24       # number of queries benchmark.py runs for P50/P70/P100
BENCHMARK_PACE_SEC   = 2.2      # sleep between queries to respect Groq ~30 RPM free tier
BENCHMARK_QUERY_FILE = os.path.join(os.path.dirname(__file__), "benchmark_queries.jsonl")

# ── Harness (orchestration) ─────────────────────────────────
MAX_LLM_RETRIES    = 1
LLM_TIMEOUT_SEC    = 15
STT_TIMEOUT_SEC    = 30
RETRY_BACKOFF_SEC  = 0.5
GENERATION_MAX_TOKENS = 160
GENERATION_TEMPERATURE = 0.1

# ── Server ──────────────────────────────────────────────────
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))
_allowed_origins_raw = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_raw.split(',') if o.strip()]

# ── Paths ───────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR       = os.path.join(BASE_DIR, "msmarco_index")
DOCS_DIR        = os.path.join(BASE_DIR, "docs")
CHAT_HISTORY    = os.path.join(BASE_DIR, "chat_history.json")