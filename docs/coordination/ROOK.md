# ROOK — work log and claims

Owner: Rook. Integrator for the schema, contracts, CI, packaging, and merges.
This file records claims, commits, tests, and limits. It is not a substitute
for the commit history.

## Current assignment

- Phase 0 — CI stabilization and dependency truth. **Complete.**
- Phase 1 — graph schema v2, deterministic resolver, API linker, mind-map
  contract. **Complete and frozen.**
- Review Wren's Phase 2 handoff against the gate, then start Phase 3.

## Claims (Phase 0)

| File | Status | Notes |
|---|---|---|
| `backend/requirements.txt` | claimed | Add runtime dependencies. |
| `pyproject.toml` | claimed | Mirror dependencies and pin MCP. |
| `.github/workflows/qa.yml` | claimed | Health assertion, matrix, build job. |
| `backend/main.py` | claimed | Additive health fields only. |
| `backend/tests/test_health.py` | claimed | Explicit endpoint assertions. |
| `backend/tests/test_dependency_contract.py` | claimed | New dependency contract test. |
| `docs/QA_REPORT.md` | claimed | Before/after baseline. |
| `CHANGELOG.md` | claimed | Unreleased CI entry. |

## Claims (Phase 1)

| File | Status | Notes |
|---|---|---|
| `backend/graph_store.py` | claimed | Schema v2, additive persistence, evidence validation. |
| `backend/parse_cache.py` | claimed | Routes, API calls, heritage; cache v3. |
| `backend/symbol_resolver.py` | claimed | New resolver/scanners. |
| `backend/mindmap_classifier.py` | claimed | Six pillars and roles. |
| `backend/mindmap.py` | claimed | Payload builder. |
| `backend/api/routers/mindmap.py` | claimed | Frozen API. |
| `backend/api/__init__.py` | claimed | Mount router. |
| `backend/graph_builder.py` | claimed | Finalization and v2 edges. |
| `backend/graph_analysis.py` | claimed | Dependency edge types. |
| `backend/tests/test_graph_v2.py` | claimed | New schema tests. |
| `backend/tests/test_symbol_resolver.py` | claimed | New resolver tests. |
| `backend/tests/test_mindmap_classifier.py` | claimed | New classifier tests. |
| `backend/tests/test_mindmap_api.py` | claimed | New L2 test. |
| `backend/tests/test_graph_golden.py` | claimed | Pin v1 subset, assert v2 additivity. |
| `docs/API.md` | claimed | Additive endpoint docs. |
| `docs/FEATURES.md` | claimed | Limits and flags. |

## Claims (CI hermeticity)

| File | Status | Notes |
|---|---|---|
| `.github/workflows/qa.yml` | complete | Full-history checkout for churn tests. |
| `backend/tests/conftest.py` | complete | Synthetic provider fixture. |
| `backend/tests/test_feature_2_onboard.py` | complete | Use the provider fixture. |
| `backend/tests/test_feature_3_voice.py` | complete | Use the provider fixture. |
| `backend/tests/test_feature_5_scaffold.py` | complete | Use the provider fixture. |
| `backend/tests/test_mcp_server.py` | complete | Hold the stdio pipe open; wait per response. |
| `frontend/playwright.config.ts` | complete | Let the QA harness own the servers. |
| `scripts/qa.py` | complete | Isolate harness servers in their own process group. |

## Results

### Phase 0

Status: complete — `facbf86 chore(ci): restore green baseline and pin runtime dependencies`.

- Declared `numpy`, `scipy`, `typer`, `watchdog`, `sse-starlette`, and
  `mcp>=1.29,<2` in both dependency files.
- CI matrix is Python 3.11/3.12 with `pip check`, `compileall`, a frontend
  build job, and triggers on `main` and `experimental`.
- `/api/health` adds `schema_version` and cached graph counts; `/health` stays
  the liveness probe.
- Verification: 343 passed on Python 3.11, 3.12, and 3.14; `pip check` clean;
  `compileall` clean; live L2 health passed; frontend build passed; extension
  20/20 tests passed.

### Phase 1

Status: complete and frozen — `d885d92 feat(graph): add schema v2 evidence,
resolver, and mind-map contract`. CI is green at `7c5b467`; the commits after
`d885d92` are test/CI infrastructure only.

- Schema v2 is additive: v1 ids, edge directions, endpoints, and MCP tool
  names are unchanged. New `inherits`, `exports`, and `api_calls` edges carry
  evidence; node enrichment adds `path`, `pillar`, `role`, `route_count`,
  `routes`, and `end_line`; the graph exposes `api_routes`.
- Parse cache is v3. tsconfig/jsconfig aliases, Express and Python routes,
  fetch/axios/EventSource calls, and Python/TS heritage are scanned
  deterministically. Ambiguous targets are omitted.
- `GET /api/mindmap` is frozen and documented in `docs/API.md` and plan §4.
  Folder ids preserve the repository-relative path; the pillar root is not a
  second folder level.
- Full and incremental builds finalize through the same path.
- Verification: **405 passed** on Python 3.11, 3.12, and 3.14; `pip check`
  clean; `compileall` clean; frontend build passed; extension 20/20 tests
  passed; **17/17 Playwright journeys** passed under `CI=1`. Golden v1
  snapshots were not regenerated.
- Fixture evidence: `v2_contract` builds 19 nodes / 18 edges, including 3
  routes, 2 `api_calls`, 1 `inherits`, and 1 `exports` edge.
- CI run **40322052797** is green on all six jobs: Python 3.11, Python 3.12,
  L2 contract, L3 journeys, frontend build, and extension.
- CI hermeticity fixes: `275d66b` removes the dependency on a developer
  `.env` and fetches full history; `25ba011` holds the MCP stdio pipe open
  until every response; `da0e892` and `7c5b467` make the QA harness own the
  Playwright servers and isolate their process group. None changes the graph
  schema, the mind-map payload, or an endpoint.
- Limits: the L3 gate runs on push and nightly, not on pull requests; Python
  3.13/3.14 are local checks, not CI targets.

## Open decisions

- None. The mind-map contract is frozen; Wren consumes it without editing
  backend graph code.
