# RepoScope — Deployment

RepoScope deploys as two services: the FastAPI backend on **Render** and the
Vite frontend on **Vercel** (which proxies `/api/*` to Render).

## Backend — Render

1. Push the repo to GitHub.
2. Render → **New → Blueprint** → pick the repo (uses [`render.yaml`](../render.yaml)).
3. Fill the secret env vars when prompted (marked `sync: false`):
   - `OPENROUTER_API_KEYS`, `GROQ_API_KEYS`, `NVIDIA_API_KEYS` (comma-separated)
   - `GITHUB_TOKENS` (optional)
4. Deploy. Build: `pip install -r backend/requirements.txt`;
   Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   (Render's build runs from the repo root — the start command `cd`s into
   `backend/`; see the `startCommand` in render.yaml).
5. Verify: `curl https://<service>.onrender.com/api/health` →
   `{"status":"healthy", ...,"checks":{...}}`

## Frontend — Vercel

1. Vercel → **Add New → Project** → pick the repo.
2. **Root Directory**: `frontend` (framework: Vite — build `npm run build`,
   output `dist`).
3. Edit [`frontend/vercel.json`](../frontend/vercel.json) — point the `/api/*`
   rewrite at your Render URL:
   ```json
   { "source": "/api/:path*", "destination": "https://<your-service>.onrender.com/api/:path*" }
   ```
4. Deploy. SPA routing is handled by the `/(.*)` → `/index.html` rewrite.

## Environment variables per platform

| Platform | Where | Keys |
|---|---|---|
| Render | Dashboard → Environment | `OPENROUTER_API_KEYS`, `GROQ_API_KEYS`, `NVIDIA_API_KEYS`, `GITHUB_TOKENS`, `PYTHON_VERSION` |
| Vercel | Project → Settings → General | none required (proxy only) |

## Health check
- `GET /api/health` — full snapshot (uptime, memory, key counts). Used as
  Render's `healthCheckPath`.
- `GET /health` — minimal liveness probe.

## CORS
The backend allows `http://localhost:5173` by default. For production, add
your Vercel domain to `CORSMiddleware.allow_origins` in `backend/main.py`.

## Custom domain
- Vercel: Project → Domains → add + DNS CNAME.
- Render: Settings → Custom Domains (paid plans).

## Common errors
| Symptom | Fix |
|---|---|
| `502` from Render on cold start | Free tier sleeps; first request wakes it (~30 s) |
| CORS errors in console | Add the frontend origin to `allow_origins` |
| `All LLM providers failed` | Set at least one valid key; check `/api/health` counts |
| Frontend loads but no data | `vercel.json` rewrite missing or pointing at the wrong Render URL |
