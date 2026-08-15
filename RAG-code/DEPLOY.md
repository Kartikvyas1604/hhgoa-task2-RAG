# ☁️ Deploying the live link

The submission requires a **live working link**. This repo has two deployable
pieces:

1. **`RAG-code/`** — Python FastAPI backend (models + index + Sarvam STT + Groq LLM).
2. **repo root** — Next.js frontend (chat UI, voice recorder, latency panel).

---

## Option A · Railway / Render / Fly (Docker)

### Backend

1. Push this repo to GitHub.
2. On Railway/Render, create a new service → **Dockerfile** → point at
   `RAG-code/Dockerfile`.
3. Set environment variables:

   | Var | Value |
   |---|---|
   | `GROQ_API_KEY` | from https://console.groq.com (free tier is fine) |
   | `SARVAM_API_KEY` | from https://dashboard.sarvam.ai (100 free credits) |
   | `PORT` | `8000` |

4. First build runs `python ingest_msmarco.py --rebuild --lite` (~20k-chunk
   index) at **image build time**, so the container starts instantly. Full
   index: edit the Dockerfile to drop `--lite`.

The service URL is your backend, e.g. `https://voice-rag.up.railway.app`.

### Frontend

1. `npm run build` locally to confirm it compiles.
2. Deploy to Vercel (`vercel` or push to a GitHub-linked project). Vercel
   auto-detects Next.js.
3. Set env var `RAG_BACKEND_URL=https://voice-rag.up.railway.app`.
4. The app proxies everything through `/api/*` routes, so no CORS issues.

---

## Option B · Hugging Face Spaces (all-in-one Python)

The backend alone can run as a Space (static GPU not required):

1. Create a Space → **Docker** template.
2. Copy `RAG-code/Dockerfile`, `requirements.txt`, `server.py`, `pipeline.py`,
   `config.py`, `benchmark.py`, `ingest_msmarco.py`, `docker-entrypoint.sh`,
   `.env.example` into the Space.
3. Add `GROQ_API_KEY` and `SARVAM_API_KEY` as Space secrets.
4. The Space URL is your backend; deploy the Next.js app to Vercel as above.

---

## Option C · Run it yourself (for the demo)

```bash
# backend
cd RAG-code && python server.py            # :8000

# frontend (another terminal)
cd .. && npm run dev                       # :3000
open http://localhost:3000
```

---

## Verifying a deployment

```bash
curl https://<your-backend>/api/status
# → { "ready": true, "chunks": 20472, "languages": ["hi","en","gu","mr"], ... }

curl -X POST https://<your-backend>/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"क्यूबा की मुद्रा क्या है?","lang":"hi"}'
# → { "answer": "...", "latency": { "total_ms": 42, ... }, ... }
```

If `ready` stays `false`, wait — the models download on first boot
(~500 MB) and build the index.

---

## Cost notes

- **Groq** free tier: ~30 requests/min, no card required.
- **Sarvam** free credits: 100 on signup (each STT call ~ a few paise).
- The `--lite` index keeps RAM ≤ ~300 MB, so free-tier containers are fine.