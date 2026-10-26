# RepoScope — Architecture

## Two Components
A) Builder: IBM Bob (dev-time only).
B) Runtime: React + FastAPI + OpenRouter/Groq/NIM + code graph + GitHub API.

## Data Flow
React UI → POST /api/chat/stream (SSE) → FastAPI
  → orchestrator → mcp_client (codebase-memory-mcp, GitHub API)
  → runtime_config.ask_llm (OpenRouter → Groq → NIM fallback chain)
  → SSE back to React (context, token, tracking, done)

## API Endpoints
POST /api/repo/load       — clone + index a GitHub repo
GET  /api/repo/status     — current repo + last check
GET  /api/repo/check      — poll GitHub for changes
GET  /api/repo/graph      — full graph (nodes + edges)
POST /api/chat/stream     — SSE: LLM answer + graph
POST /api/byok/set        — set user's GitHub PAT (BYOK)
POST /api/repo/commit     — commit from the app (BYOK)
GET  /api/health          — health check

## SSE Events
context  : {nodes, edges, mode}
token    : string
tracking : {commits, prs, issues, releases}
done     : [DONE]
error    : {message}

## Ports
React 5173 | FastAPI 8000 | codebase-memory-mcp UI 9749

## LLM Provider Chain
1. OpenRouter  (OPENROUTER_API_KEY)  — primary, free models available
2. Groq        (GROQ_API_KEY)        — secondary
3. NVIDIA NIM  (NVIDIA_API_KEY)      — tertiary fallback

## Failure Fallbacks
OpenRouter 429 → Groq
Groq 429       → NVIDIA NIM
NIM 429        → cached answer + error toast
GitHub 403     → cached data + warn
MCP down       → empty graph, LLM answers from GitHub metadata
