# RepoScope — Development Guide

## Prerequisites
- Python 3.11+
- Node.js 18+ / npm
- Git (repo cloning uses GitPython)
- At least one LLM key (OpenRouter / Groq / NVIDIA) in `.env`

## Local setup
```bash
cp .env.example .env          # add keys
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000

# second terminal
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Project structure
```
backend/     FastAPI app + graph builder + LLM chain + MCP client
frontend/    Vite + React + TS (strict) + React Flow + dagre
  src/api/       client.ts (SSE + REST), features.ts, sse.ts
  src/components/  TopBar, LeftPanel, ChatPanel, GraphView, graph/
  src/styles/      tokens.css (design tokens) + app.css
docs/        architecture, features, runbooks, screenshots, bob_sessions
demo-repo/   tiny local repo for offline testing
data/        runtime state (repo_state.json — gitignored)
```

## How to add a feature
1. **Backend endpoint** — add to `backend/main.py` (or a new module imported
   there). Follow the existing pattern: request-id logging, JSON errors via
   `HTTPException`, no secrets in logs.
2. **Frontend API** — add a typed wrapper in `frontend/src/api/features.ts`
   with a response-shape guard and a timeout.
3. **UI** — components in `frontend/src/components/`. Every new component
   needs loading, empty, and error states. Use tokens from
   `src/styles/tokens.css`; buttons via `.btn-primary/.btn-secondary/.btn-ghost`,
   cards via `.card`.
4. **Graph work** — nodes render through `components/graph/LayerNode.tsx`;
   classify layers in `graph/layerClassifier.ts`; layout is dagre
   (`applyDagre`) with the camera owned by `buildGraph` (never re-add the
   ReactFlow `fitView` prop — it collapses wide trees; see Troubleshooting).

## Adding an MCP server
1. Install the binary and note its command (e.g. `codebase-memory-mcp`).
2. Point `CODEBASE_MEMORY_PATH` at it (or edit `.bob/mcp.json`).
3. `mcp_client.py` spawns it with a 15 s timeout and falls back to the local
   graph builder when unavailable.

## Debugging tips
- Backend log: `backend/logs/app.log` (rotating, request-id per line).
- Frontend: open DevTools; SSE events appear in the status bar's last-event
  field and (with debug mode on, `?` → Toggle debug logs) in the chat debug pane.
- Health: `curl localhost:8000/api/health` → uptime, memory, key counts.
- Vite oddities (duplicate-React "invalid hook call"): stop every Vite
  process, `rm -rf frontend/node_modules/.vite`, restart one dev server.
