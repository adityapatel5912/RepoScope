# DIALOGUE — Rook ↔ Wren

Append-only. Newest at the bottom. The plan is authoritative; this file
records decisions, handoffs, and verification.

---

## 2026-10-26 — Rook — Plan approved, first batch starts

The owner approved the plan and authorized execution. The first batch is
Phase 0 (CI stabilization) and Phase 1 (graph schema v2, resolver, API
linker, mind-map contract). Wren starts Phase 2 after Phase 1 is frozen.

Baseline: 335 passed locally with Python 3.14; 30 failed / 305 passed on a
clean Python 3.11 install. The known causes are missing `numpy`/`scipy`,
missing `mcp`/`typer`/`watchdog` in `backend/requirements.txt`, `mcp 2.x`
removing `mcp.server.fastmcp.FastMCP`, and the L2 health assertion expecting
`"ok"` from `/api/health`.

Rook claims: `backend/requirements.txt`, `pyproject.toml`,
`.github/workflows/qa.yml`, `backend/main.py`, `backend/graph_store.py`,
`backend/graph_builder.py`, `backend/parse_cache.py`, `backend/symbol_resolver.py`,
`backend/mindmap_classifier.py`, `backend/mindmap.py`,
`backend/api/routers/mindmap.py`, `backend/api/__init__.py`,
`backend/tests/test_dependency_contract.py`, `backend/tests/test_graph_v2.py`,
`backend/tests/test_symbol_resolver.py`, `backend/tests/test_mindmap_classifier.py`,
`backend/tests/test_mindmap_api.py`, `backend/tests/test_health.py`,
`backend/tests/test_graph_golden.py`, `docs/API.md`, `docs/FEATURES.md`,
`docs/QA_REPORT.md`, `CHANGELOG.md`.

Wren: no claims yet. Do not start until the Phase 1 mind-map contract is
announced below.

---

## 2026-10-26 — Rook — Phase 0 gate

Status: in progress.

Planned changes: pin `mcp>=1.29,<2`; declare `numpy`, `scipy`, `typer`,
`watchdog`, and `sse-starlette` in both dependency files; add `pip check`,
`compileall`, a Python 3.11/3.12 matrix, and a frontend build job; fix the
L2 health assertion; add `schema_version` and graph counts to `/api/health`
without changing `status: "healthy"` or `/health`.

Verification will be posted here with exact counts.

---

## 2026-10-26 — Rook — Phase 1 gate

Status: in progress.

Frozen contract: `GET /api/mindmap` as specified in
`docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §4. No client-side pillar
classification. The graph schema is additive: v1 ids and edges stay; new
node fields and `api_calls`/`inherits`/`exports` edges carry evidence.

Wren's first batch is Phase 2, and only Phase 2. The self-contained prompt is
in `HANDOFF_PHASE_2.md`. It is safe to copy into a fresh agent session.

---

## 2026-10-26 — Rook — Handoff 001 to Wren

Branch: `wren/phase-2-mindmap` from `experimental` at the Phase 1 commit.
Scope: the vertical mind-map UI against the frozen `GET /api/mindmap`
contract. Do not edit backend graph code. Do not add a second classifier.

Acceptance: `npm --prefix frontend run build`, `npx tsc --noEmit`, and the
new Playwright journey pass; the dependency network remains the default; no
horizontal overflow at 1600×900 or 1280×800.

When done: commit, merge into `experimental` with `--no-ff`, post the handoff
with the commit hash and commands, and update `WREN.md`.

---

## 2026-10-26 — Rook — Phase 0 complete

`facbf86 chore(ci): restore green baseline and pin runtime dependencies`.

- Pinned `mcp>=1.29,<2`; declared `numpy`, `scipy`, `typer`, `watchdog`, and
  `sse-starlette` in both dependency files.
- CI now runs `pip check`, `compileall`, Python 3.11/3.12, frontend build, and
  extension jobs on `main` and `experimental`.
- `/api/health` adds `schema_version` and cached graph counts without changing
  `status: "healthy"`; `/health` stays `{"status": "ok"}`.
- Verified: **343 passed** on Python 3.11, 3.12, and 3.14 locally; L2 health
  probe passed live.

---

## 2026-10-26 — Rook — Phase 1 complete; CI hermeticity fixes

`d885d92 feat(graph): add schema v2 evidence, resolver, and mind-map contract`.

- Schema v2 is additive; `GET /api/mindmap` is frozen in `docs/API.md` and
  plan §4. Folder ids keep the repository-relative path and do not repeat the
  pillar root.
- Local gate: **405 passed** on Python 3.11, 3.12, and 3.14; frontend build;
  extension 20/20; 17/17 Playwright journeys.
- CI run 40319380840 failed **7 / 398** on both Python versions. The causes
  were test-environment leaks, not product regressions: six endpoint tests
  resolved a real AI provider before their stubbed LLM (CI has no `.env`), and
  one churn test read a one-commit shallow checkout.
- `275d66b fix(ci): isolate endpoint provider resolution and fetch full
  history` adds a synthetic-provider fixture and `fetch-depth: 0`.
- CI run 40320122480 then exposed a stdio test that closed stdin before
  `tools/list` could be read. `25ba011 test(mcp): keep the stdio pipe open
  until every response` makes the harness wait for each response.
- CI run 40320667722 exposed two L3 harness defects: Playwright tried to start
  a second backend on the port `scripts/qa.py` already owned, then the
  harness's process-group cleanup terminated the CI runner. `da0e892` and
  `7c5b467` fix server ownership and process isolation.
- Final CI run 40322052797 is **green on all six jobs** (Python 3.11, Python
  3.12, L2 contract, L3 journeys, frontend build, extension).
- The fixes after `d885d92` are test/CI infrastructure only. They do not
  change the graph schema, the mind-map payload, or any endpoint.

---

## 2026-10-26 — Rook — Handoff 002 to Wren (Phase 2)

Phase 1 is frozen at `d885d92`; `experimental` is CI-green at `7c5b467` plus
this documentation commit.

Branch `wren/phase-2-mindmap` from `origin/experimental` (at or after
`7c5b467`). Scope is Phase 2 only: the vertical six-pillar mind map against
the frozen `GET /api/mindmap` contract in `docs/API.md` and plan §4. Do not
edit backend graph code, do not add a second classifier, and keep
`GraphView.tsx` as the default dependency canvas.

Acceptance: `npm --prefix frontend run build`, `npx tsc --noEmit`, and the new
Playwright journey pass; the dependency network remains the default; no
horizontal overflow at 1600×900 or 1280×800.

When done: commit, merge into `experimental` with `--no-ff`, post the handoff
in this file with the commit hash and commands, and update `WREN.md`.
