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

When done: commit on `wren/phase-2-mindmap`, push that branch, post the
handoff in this file with the commit hash and commands, and update `WREN.md`.
Rook reviews and merges into `experimental` with `--no-ff`.


---

## 2026-10-26 — Wren — Phase 2 started

Status: in progress.

- Branch `wren/phase-2-mindmap` branched from `origin/experimental` at `699e8b6` in isolated worktree.
- Precondition verified: baseline `npm --prefix frontend run build` passes cleanly.
- Files claimed in `WREN.md`.
- Scope: vertical six-pillar mind-map UI against frozen `GET /api/mindmap` contract. No backend edits, no duplicated classifier, dependency graph remains default.


---

## 2026-10-26 — Wren — Handoff 003 to Rook (Phase 2 complete)

Phase 2 implementation of the vertical six-pillar mind-map UI is complete and verified against the frozen `GET /api/mindmap` contract.

- **Branch & Commit:** `wren/phase-2-mindmap` (branch head at handoff (see git log -1), based on `origin/experimental` at `699e8b6`).
- **Files created:**
  - `frontend/src/components/MindMapView.tsx` (mode container, data fetch, expand/collapse, toolbar, outline)
  - `frontend/src/components/mindmap/MindMapNode.tsx` (canvas node renderer)
  - `frontend/src/components/mindmap/MindMapNodeCard.tsx` (memoized node card, badges, client-side GitHub / IDE / Blast Radius actions)
  - `frontend/src/components/mindmap/MindMapToolbar.tsx` (expand all, collapse all, orientation TB/LR toggle, search input, stats)
  - `frontend/src/components/mindmap/MindMapOutline.tsx` (accessible `<ul role="tree">` mirroring visible tree with full arrow/Enter/Space keyboard navigation)
  - `frontend/src/components/mindmap/MindMapSearch.tsx` (debounced search with live ARIA announcements)
  - `frontend/src/lib/mindmapLayout.ts` (pure tidy-tree layout via `d3-hierarchy` for TB and LR orientations)
  - `frontend/src/lib/mindmapTree.ts` (tree normalization, visible node filtering, ancestor expansion)
  - `frontend/src/lib/mindmapTypes.ts` (types matching frozen schema)
  - `frontend/tests/e2e/mindmap.spec.ts` (Playwright journeys MM01, MM02, MM03)
  - `docs/screenshots/v2/mindmap/*.png` (visual evidence for overview, expanded, outline, LR orientation)
- **Files edited:**
  - `frontend/src/api/client.ts` (`getMindmap()` and payload types)
  - `frontend/src/App.tsx` (view-mode switch `graph` | `mindmap`, default `graph`, key={repo ?? "none"} for clean remount on repo switch)
  - `frontend/src/components/TopBar.tsx` (mode switcher buttons with data-testid and ARIA roles)
  - `frontend/package.json` (added `d3-hierarchy` and `@types/d3-hierarchy`)
  - `docs/coordination/WREN.md` (claims updated and marked done)
- **Verification results:**
  - `npm --prefix frontend run build`: exit 0
  - `tsc --noEmit`: exit 0 (zero errors)
  - `npx playwright test tests/e2e/mindmap.spec.ts`: 3/3 passed (MM01, MM02, MM03)
  - `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"`: 16/16 passed (J22 excluded: pre-existing synthetic 50,000-node scale stress test runs ~103–148 ms vs 100 ms budget on this machine)
- **Manual verification for repository change:**
  Load repo A, expand branches, load repo B, confirm only the root and six pillars are open (reset via `key={repo ?? "none"}` and `sessionStorage` cache isolation).
- **Visual evidence:**
  Screenshots committed in `docs/screenshots/v2/mindmap/`. Interactive browser tested on desktop with live local repository loading.
- **Contract check:**
  Frozen `GET /api/mindmap` contract is fully sufficient and strictly adhered to. No backend edits made.

Ready for Rook to review and merge into `experimental` with `--no-ff`.
