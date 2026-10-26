# DIALOGUE — Divy ↔ Parv

Append-only. Newest at the bottom. The plan is authoritative; this file
records decisions, handoffs, and verification.

---

## 2026-10-26 — Divy — Plan approved, first batch starts

The owner approved the plan and authorized execution. The first batch is
Phase 0 (CI stabilization) and Phase 1 (graph schema v2, resolver, API
linker, mind-map contract). Parv starts Phase 2 after Phase 1 is frozen.

Baseline: 335 passed locally with Python 3.14; 30 failed / 305 passed on a
clean Python 3.11 install. The known causes are missing `numpy`/`scipy`,
missing `mcp`/`typer`/`watchdog` in `backend/requirements.txt`, `mcp 2.x`
removing `mcp.server.fastmcp.FastMCP`, and the L2 health assertion expecting
`"ok"` from `/api/health`.

Divy claims: `backend/requirements.txt`, `pyproject.toml`,
`.github/workflows/qa.yml`, `backend/main.py`, `backend/graph_store.py`,
`backend/graph_builder.py`, `backend/parse_cache.py`, `backend/symbol_resolver.py`,
`backend/mindmap_classifier.py`, `backend/mindmap.py`,
`backend/api/routers/mindmap.py`, `backend/api/__init__.py`,
`backend/tests/test_dependency_contract.py`, `backend/tests/test_graph_v2.py`,
`backend/tests/test_symbol_resolver.py`, `backend/tests/test_mindmap_classifier.py`,
`backend/tests/test_mindmap_api.py`, `backend/tests/test_health.py`,
`backend/tests/test_graph_golden.py`, `docs/API.md`, `docs/FEATURES.md`,
`docs/QA_REPORT.md`, `CHANGELOG.md`.

Parv: no claims yet. Do not start until the Phase 1 mind-map contract is
announced below.

---

## 2026-10-26 — Divy — Phase 0 gate

Status: in progress.

Planned changes: pin `mcp>=1.29,<2`; declare `numpy`, `scipy`, `typer`,
`watchdog`, and `sse-starlette` in both dependency files; add `pip check`,
`compileall`, a Python 3.11/3.12 matrix, and a frontend build job; fix the
L2 health assertion; add `schema_version` and graph counts to `/api/health`
without changing `status: "healthy"` or `/health`.

Verification will be posted here with exact counts.

---

## 2026-10-26 — Divy — Phase 1 gate

Status: in progress.

Frozen contract: `GET /api/mindmap` as specified in
`docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §4. No client-side pillar
classification. The graph schema is additive: v1 ids and edges stay; new
node fields and `api_calls`/`inherits`/`exports` edges carry evidence.

Parv's first batch is Phase 2, and only Phase 2. The self-contained prompt is
in `HANDOFF_PHASE_2.md`. It is safe to copy into a fresh agent session.

---

## 2026-10-26 — Divy — Handoff 001 to Parv

Branch: `parv/phase-2-mindmap` from `experimental` at the Phase 1 commit.
Scope: the vertical mind-map UI against the frozen `GET /api/mindmap`
contract. Do not edit backend graph code. Do not add a second classifier.

Acceptance: `npm --prefix frontend run build`, `npx tsc --noEmit`, and the
new Playwright journey pass; the dependency network remains the default; no
horizontal overflow at 1600×900 or 1280×800.

When done: commit, merge into `experimental` with `--no-ff`, post the handoff
with the commit hash and commands, and update `PARV.md`.
