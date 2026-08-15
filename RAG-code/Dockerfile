# ============================================================
#  Dockerfile — Voice-Enabled Multilingual RAG backend
#  Builds a small index on first start (--lite), then serves
#  FastAPI on :8000.
#  Run:  docker build -t voice-rag . && docker run -p 8000:8000 \
#        -e GROQ_API_KEY=... -e SARVAM_API_KEY=... voice-rag
# ============================================================
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libomp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build a small index at IMAGE BUILD time so the container starts instantly.
# Set MAX_ROWS/MAX_PASSAGES to taste; drop --lite for a much larger index
# (takes longer to build). The entrypoint re-builds only if no index exists.
RUN mkdir -p data msmarco_index \
    && python ingest_msmarco.py --rebuild --lite

EXPOSE 8000

ENV OMP_NUM_THREADS=1 \
    KMP_DUPLICATE_LIB_OK=TRUE \
    PYTHONUNBUFFERED=1

CMD ["sh", "docker-entrypoint.sh"]