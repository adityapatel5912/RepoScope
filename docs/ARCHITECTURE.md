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

## Graph Layout Algorithm
The pyramid is a deterministic manual layout in `GraphView.tsx`
(`buildPyramidGraph`) — no dagre, no force simulation.

1. **Connectivity ranking.** Every file node is scored from the backend's
   `imports` edges: `score = incoming × 2 + outgoing`. Files with no import
   edges fall back to a path-based heuristic (entry points > services >
   components > utils > config > docs). Files sort by score desc, then id.
2. **Bucketing.** Sorted files fill five ranks — the top 5% (max 6), next
   10% (max 12), next 15% (max 20), next 20% (max 30), remainder last.
   `repo:root` is synthesized at row 0; each rank wraps into continuation
   slots of ≤ 18 nodes (`MAX_PER_ROW`).
3. **Placement.** Rows sit at `y = rank × RANK_GAP_Y`, centered horizontally
   at `NODE_GAP_X` pitch. Core files (rows 1–2) expand their top functions
   as child nodes at `y + RANK_GAP_Y / 2` (`CHILD_DY`), centered under the
   parent at `CHILD_GAP_X` pitch.
4. **Collision pass.** `fixOverlaps` sweeps each row left→right and enforces
   a minimum center-to-center gutter of `(widthA + widthB) / 2 + MIN_CLEAR_X`
   using real node widths — guaranteeing no two nodes overlap.
5. **Edges.** Backend edges (`imports`, `contains`) are kept only when both
   endpoints were placed, capped at 1,000, and rendered as smoothstep paths
   with arrowheads. The layout adds synthesized `repo:root → top-row`
   containment edges at render time; the backend graph carries no structural
   dir/repo edges on purpose — they would pollute the impact analyzer's
   reverse-BFS (every file's blast radius would include `repo` and `dir:*`).
6. **Diagnostics.** In dev builds, `[EDGE DIAG]` logs node count, edge count,
   and matched-endpoint count to the console (see Troubleshooting).

## Failure Fallbacks
OpenRouter 429 → Groq
Groq 429       → NVIDIA NIM
NIM 429        → cached answer + error toast
GitHub 403     → cached data + warn
MCP down       → empty graph, LLM answers from GitHub metadata
