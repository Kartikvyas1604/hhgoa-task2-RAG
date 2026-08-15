#!/bin/sh
# docker-entrypoint.sh — build the index once, then serve the API.
set -e

if [ ! -f msmarco_index/faiss.index ]; then
  echo "[entrypoint] Building lite index (no index shipped with the image) ..."
  python ingest_msmarco.py --rebuild --lite
fi

echo "[entrypoint] Starting server on :${PORT:-8000}"
exec python server.py