# IBM Bob Sessions

RepoScope was built with **IBM Bob 2.0** as the primary AI SDLC partner, with
**Z Code (GLM)** pairing on the complex tasks (graph layout debugging,
hardening, and this submission's docs/deck).

## Full Session Log

See [bob-session-export.md](bob_sessions/bob-session-export.md) for Bob's
complete verbatim task export.

## Screenshots

All session summary screenshots are in [docs/bob_sessions/](bob_sessions/).

| # | Session | Screenshot |
|---|---|---|
| 1 | Full build — all Bob-owned tasks complete | `session-01-build-complete.png` |
| 2 | Aurora UI build (frontend + graph renderer) | `session-02-frontend-ui.png` |
| 3 | Critical bug fixes (SSE · graph · README injection) | `session-03-critical-bugfixes.png` |

## Division of Work

| Partner | Scope |
|---|---|
| **IBM Bob 2.0** | Most tasks — repo scaffold, FastAPI backend, React components, SSE client, code tours, impact analysis, tracking, BYOK, docs, deployment configs |
| **Z Code (GLM)** | Complex tasks — editorial UI redesign (4 reference files), dagre graph layout diagnosis + camera fix, hardening & regression passes, graph export / file tree / reverse build prompt, pitch deck & submission assets |

Every feature was human-directed; both agents worked from detailed build
prompts archived in [BUILD_PROMPT.md](BUILD_PROMPT.md).
