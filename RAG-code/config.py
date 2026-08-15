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
# Multilingual embedding (handles Hindi + English + Gujarati + Marathi + 100+ langs).
# small + fast: ~7ms single-query embed on CPU. Prefix "query: "/"passage: " required.
EMBED_MODEL        = "intfloat/multilingual-e5-small"   # 384-dim, multilingual (mE5: hi/en/gu/mr)
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
DATASET_SPLIT     = "validation"
# The system is trained on EXACTLY these four languages and nothing else.
# MSMARCO-XI has no standalone English parquet — English comes from the
# original English passages/queries/answers carried inside every Indic row.
SUPPORTED_LANGUAGES = ["hi", "en", "gu", "mr"]
INGEST_LANGUAGES    = ["hi", "gu", "mr"]     # parquet languages (English is derived)
LANG_NAMES          = {"hi": "हिन्दी", "en": "English", "gu": "ગુજરાતી", "mr": "मराठी"}
LANG_NAMES_EN       = {"hi": "Hindi", "en": "English", "gu": "Gujarati", "mr": "Marathi"}
MAX_ROWS_PER_LANG   = 2500          # rows (queries) ingested per parquet language
MAX_PASSAGES_PER_ROW = 8            # passages stored per query row
DEDUPE_PASSAGES     = True          # drop near-identical passages across the corpus

# ── Chunking Strategy ───────────────────────────────────────
# Vast multi-strategy chunking (see ingest_msmarco.py):
#   1. Natural passage-unit chunks — MSMARCO passages are self-contained
#   2. Adaptive recursive sentence-split with overlap for long passages;
#      tiny fragments merge into the previous chunk
#   3. Metadata-aware chunks — lang, query_id, query_type, gold label
#   4. Cross-lingual anchoring — [EN]/[GU]/[MR] translated surface so
#      queries in one language retrieve passages in another
#   5. Romanized (Latin) surface — Hinglish queries hit Devanagari passages
#   6. doc2query-style [Q] anchor — gold chunks embed the exact query so
#      lexical BM25 + extractive fast-path both fire reliably
#   7. Answer anchoring — gold passages embed the well-formed answer
#   8. English first-class chunks derived from English_passages
CHUNK_MAX_CHARS      = 700    # passages above this get recursively split
CHUNK_MIN_CHARS      = 140    # fragments below this merge into previous chunk
CHUNK_OVERLAP_RATIO  = 0.12   # overlap between recursive splits
ANCHOR_ENGLISH       = True   # append translated English surface to Indic chunks
ANCHOR_ROMANIZED     = True   # append romanized (Latin) form for Hinglish queries
ANCHOR_ANSWER        = True   # append well-formed answer to gold passage chunks
ANCHOR_QUERY         = True   # append exact query to gold chunks (doc2query-style)

# ── Retrieval Settings ──────────────────────────────────────
# Dense-first hybrid: FAISS returns a wide candidate pool, then BM25
# re-scores ONLY that pool (candidate-limited, O(pool) not O(corpus)) —
# keeps the lexical signal without the 1000ms full-corpus BM25 tail.
DENSE_POOL           = 300    # dense candidates passed to BM25 re-scoring
VECTOR_TOP_K         = 24     # final dense candidates used in fusion
BM25_TOP_K           = 12     # candidates from candidate-limited BM25
BM25_SCORE_THRESHOLD = 0.5    # ignore weak keyword hits below this raw score
RERANK_MAX_PAIRS     = 12     # cross-encoder pairs (measured ~144ms on M4 CPU)
RERANK_TOP_N         = 8      # chunks surviving cross-encoder rerank
CROSS_ENCODER_MAX_LENGTH = 256  # truncate pairs → 2× faster rerank, same recall
RERANK_TEXT_TAIL     = 600    # rerank sees the TAIL of a chunk (anchors live at the end)
MAX_CHUNKS_PER_SOURCE = 4     # source diversity cap per query_id

# ── Guardrails ──────────────────────────────────────────────
# Off-topic / out-of-corpus gate: below this top rerank score the system
# refuses to answer rather than hallucinate.
OFF_TOPIC_THRESHOLD        = 0.30
LOW_CONFIDENCE_THRESHOLD   = 0.45  # between threshold and here → caveated answer
MIN_GOLD_SCORE             = 0.45  # confidence needed to use extractive gold answer
MIN_GOLD_QUERY_SIM         = 0.85  # embedding sim (query vs stored gold query) for extractive path
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
BENCHMARK_QUERIES    = 40       # number of queries benchmark.py runs for P50/P70/P100
BENCHMARK_PACE_SEC   = 0.5      # sleep between queries (extractive path needs no LLM)
BENCHMARK_QUERY_FILE = os.path.join(os.path.dirname(__file__), "benchmark_queries.jsonl")

# ── Harness (orchestration) ─────────────────────────────────
MAX_LLM_RETRIES    = 1
LLM_TIMEOUT_SEC    = 15
STT_TIMEOUT_SEC    = 30
RETRY_BACKOFF_SEC  = 0.5
GENERATION_MAX_TOKENS = 90
GENERATION_TEMPERATURE = 0.1

# ── Server ──────────────────────────────────────────────────
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))
_allowed_origins_raw = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_raw.split(',') if o.strip()]

# ── Paths ───────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR       = os.path.join(BASE_DIR, "msmarco_index")
DATA_DIR        = os.path.join(BASE_DIR, "data")     # optional local parquet cache (gitignored)
DOCS_DIR        = os.path.join(BASE_DIR, "docs")
CHAT_HISTORY    = os.path.join(BASE_DIR, "chat_history.json")