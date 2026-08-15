# ============================================================
#  server.py — FastAPI backend for the voice-enabled RAG app
#
#  Endpoints:
#    GET  /api/status              — readiness, index stats
#    POST /api/query               — text query → grounded answer + latency
#    POST /api/stt                 — audio → transcript (Sarvam saaras:v3)
#    POST /api/voice_query         — audio → transcript → RAG answer (E2E)
#    GET  /api/latency             — P50 / P70 / P90 / P100 analytics
#    POST /api/benchmark           — run N-query benchmark, refresh report
#
#  Run:  python server.py   →  http://localhost:8000
# ============================================================

import os
import json
import time
import threading

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import config
from pipeline import get_pipeline, transcribe_audio

app = FastAPI(title="Voice RAG — MSMARCO-XI", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS + ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODELS_LOADED = False
LOAD_ERROR = None


@app.on_event("startup")
async def startup():
    def _load():
        global MODELS_LOADED, LOAD_ERROR
        print("\n🧠 Loading embedding + reranker models (first run downloads ~500MB)...")
        ok = get_pipeline().load()
        MODELS_LOADED = ok
        LOAD_ERROR = None if ok else get_pipeline().error
        print(f"✅ Ready — {len(get_pipeline().passages or [])} chunks loaded." if ok else f"❌ {LOAD_ERROR}")
    threading.Thread(target=_load, daemon=True).start()


@app.get("/api/status")
async def status():
    p = get_pipeline()
    return {
        "ready": MODELS_LOADED,
        "loading": not MODELS_LOADED and LOAD_ERROR is None,
        "error": LOAD_ERROR,
        "chunks": len(p.passages) if p.passages else 0,
        "languages": config.SUPPORTED_LANGUAGES,
        "language_names": config.LANG_NAMES,
        "language_names_en": config.LANG_NAMES_EN,
        "embed_model": config.EMBED_MODEL,
        "generation_model": config.GROQ_MODEL,
        "stt_model": config.SARVAM_STT_MODEL,
    }


@app.post("/api/query")
async def query(request: Request):
    body = await request.json()
    question = (body.get("question") or "").strip()
    lang = body.get("lang") or None
    session_id = body.get("session_id") or None
    if not question:
        return JSONResponse(status_code=400, content={"error": "Empty question"})
    if not MODELS_LOADED:
        return JSONResponse(status_code=503, content={"error": "Models are still loading."})
    result = get_pipeline().run(question, lang=lang, session_id=session_id)
    return result


@app.post("/api/stt")
async def stt(file: UploadFile = File(...), mode: str = Form("transcribe")):
    audio = await file.read()
    if not audio:
        return JSONResponse(status_code=400, content={"error": "Empty audio"})
    t0 = time.time()
    out = transcribe_audio(audio, file.content_type or "audio/webm")
    out["stt_ms"] = round((time.time() - t0) * 1000, 1)
    return out


@app.post("/api/voice_query")
async def voice_query(
    file: UploadFile = File(...),
    lang: str = Form(None),
    session_id: str = Form(None),
):
    """End-to-end voice → answer in one call."""
    audio = await file.read()
    if not audio:
        return JSONResponse(status_code=400, content={"error": "Empty audio"})
    if not MODELS_LOADED:
        return JSONResponse(status_code=503, content={"error": "Models are still loading."})

    t_all = time.time()
    stt_out = transcribe_audio(audio, file.content_type or "audio/webm")
    stt_ms = round((time.time() - t_all) * 1000, 1)
    stt_code = stt_out.get("language_code")
    query_lang = lang or (stt_code or "").split("-")[0].lower()
    if query_lang:
        gl = get_pipeline().guard_language(query_lang)
        if gl["refused"]:
            return {
                "answer": gl["detail"],
                "refused": True,
                "reason": "unsupported_language",
                "sources": [],
                "guardrails": [gl],
                "transcript": stt_out["transcript"],
                "stt_language_code": stt_code,
                "end_to_end_ms": round((time.time() - t_all) * 1000, 1),
            }
    result = get_pipeline().run(stt_out["transcript"], lang=query_lang, session_id=session_id, stt_ms=stt_ms)
    result["transcript"] = stt_out["transcript"]
    result["stt_language_code"] = stt_code
    result["end_to_end_ms"] = round((time.time() - t_all) * 1000, 1)
    return result


@app.get("/api/latency")
async def latency_stats():
    stats = get_pipeline().latency.stats()
    # Merge persisted benchmark report if present
    if os.path.exists(config.LATENCY_REPORT_FILE):
        try:
            with open(config.LATENCY_REPORT_FILE) as f:
                stats["benchmark_report"] = json.load(f)
        except Exception:
            pass
    return stats


@app.post("/api/benchmark")
async def run_benchmark():
    """Run the latency benchmark now (N queries) and persist the report."""
    from benchmark import run_benchmark
    report = run_benchmark(get_pipeline(), n=config.BENCHMARK_QUERIES)
    return report


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")