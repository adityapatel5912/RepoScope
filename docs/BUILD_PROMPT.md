# RepoScope — Build Prompt

This file is the original IBM Bob build prompt used to generate this project.
Saved here for reference and reproducibility.

---

## Project

**Name**: RepoScope  
**Tagline**: See your repo. Understand it. Track it.  
**Purpose**: GitHub repository intelligence tool — answers questions about any
repo, visualizes it as an interactive graph, and tracks changes on demand.

---

## Env Vars (from `.env.example`)

```
OPENROUTER_API_KEY   — primary LLM (free models)
Base_URL_OPENROUTER  — https://openrouter.ai/api/v1/chat/completions
Models_OPENROUTER    — google/gemma-4-31b-it:free,qwen/qwen3.8-27b:free

GROQ_API_KEY         — secondary LLM
Base_URL_GROQ        — https://api.groq.com/openai/v1
Models_GROQ          — qwen/qwen3.8-27b,openai/gpt-oss-120b

NVIDIA_API_KEY       — tertiary LLM fallback
Base_URL_NVIDIA      — https://integrate.api.nvidia.com/v1
Models_NVIDIA        — meta/muse-glimmer-30b,...

GITHUB_PAT           — GitHub REST API + BYOK
```

---

## LLM provider chain

`runtime_config.py` tries providers in order:
1. OpenRouter → first model in `Models_OPENROUTER`
2. Groq       → first model in `Models_GROQ`
3. NVIDIA NIM → first model in `Models_NVIDIA`

Each provider falls through to the next on any exception (rate limit, auth
error, network error).

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health`      | Health check |
| POST | `/api/repo/load`   | Clone + index a GitHub repo |
| GET  | `/api/repo/status` | Current repo + last check timestamp |
| GET  | `/api/repo/check`  | Poll GitHub for changes since last check |
| GET  | `/api/repo/graph`  | Return graph nodes + edges |
| POST | `/api/chat/stream` | SSE: stream LLM answer + graph context |
| POST | `/api/byok/set`    | Store user's GitHub PAT (session-only) |
| POST | `/api/repo/commit` | Simulated commit (requires BYOK token) |

---

## SSE Event Types

| Event      | Payload |
|------------|---------|
| `context`  | `{nodes, edges, mode, graph_summary}` |
| `token`    | `string` (streamed word-by-word) |
| `tracking` | `{commits, pulls, issues, releases}` |
| `done`     | `"[DONE]"` |
| `error`    | `{message: string}` |

---

## Folder structure

```
reposcope/
├── .env.example
├── .gitignore
├── README.md
├── CONTRIBUTING.md
├── HANDOFF.md
├── .bob/mcp.json
├── docs/BUILD_PROMPT.md   ← this file
├── md/                    ← 7 agent + architecture docs
├── backend/               ← FastAPI + Python
├── frontend/              ← React + Vite + TypeScript
├── data/                  ← JSON state + mock data
└── demo-repo/             ← Tiny Python project for testing
```

---

## Rules followed during build

1. No API keys hardcoded — all read via `os.getenv()`
2. Env var names match `.env.example` exactly
3. No `git` commands run — version control left to developer
4. BYOK implemented — session-only, never persisted to disk
5. `demo-repo/` included for immediate testing
6. OpenRouter added as primary provider (was in `.env.example`)
7. `.bob/mcp.json` written; global merge skipped (Bob tool limitation)
