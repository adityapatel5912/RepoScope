# Handoff

RepoScope is fully built and ready for review.

## What exists

| Path | Contents |
|------|----------|
| `backend/` | FastAPI app — SSE, LLM chain, BYOK, repo loader/tracker |
| `frontend/` | React + Vite + TypeScript + React Flow UI |
| `md/` | 7 documentation files |
| `data/` | Mock metrics, logs, repo state JSON |
| `demo-repo/` | Tiny Python project for instant testing |
| `docs/BUILD_PROMPT.md` | Original build prompt for reference |
| `README.md` | Quick start + feature overview |
| `CONTRIBUTING.md` | Dev setup + commit convention |

## LLM provider chain
1. **OpenRouter** (`OPENROUTER_API_KEY`) — primary, uses first model in
   `Models_OPENROUTER` (free models available)
2. **Groq** (`GROQ_API_KEY`) — secondary
3. **NVIDIA NIM** (`NVIDIA_API_KEY`) — tertiary fallback

All provider config reads from `.env` using the exact variable names in
`.env.example`. No keys are hardcoded.

## GitHub auth
- Env var: `GITHUB_PAT`
- Also accepted via BYOK panel (`POST /api/byok/set`) — session-only,
  never persisted to disk.

## MCP servers
`.bob/mcp.json` configures `codebase-memory-mcp` and the GitHub MCP server.
The GitHub server reads `${GITHUB_PAT}` — if Bob doesn't expand env vars in
MCP config at runtime, paste the token value directly or set it as a system
environment variable before starting Bob.

## Next steps for the developer
1. Copy `.env.example` → `.env` and fill in real API keys.
2. `cd backend && pip install -r requirements.txt`
3. `cd frontend && npm install`
4. Start backend: `uvicorn main:app --reload --port 8000`
5. Start frontend: `npm run dev`
6. Open http://localhost:5173 and test with `demo-repo/` or any public GitHub URL.
7. Review code, then handle version control manually (`git init`, etc.).

## Notes
- No `git` commands were run. All version control is left to the developer.
- All credentials are read via `os.getenv(...)` — never hardcoded.
