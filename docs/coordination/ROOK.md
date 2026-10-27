# ROOK — work log and claims

Owner: Rook. Integrator for the schema, contracts, CI, packaging, and merges.
This file records claims, commits, tests, and limits. It is not a substitute
for the commit history.

## Current assignment

- Phase 0 — CI stabilization and dependency truth. **Complete.**
- Phase 1 — graph schema v2, deterministic resolver, API linker, mind-map
  contract. **Complete and frozen.**
- Phase 2 — vertical six-pillar mind map. **Complete and merged into `main`
  at `ff4ac6a`; CI green (`40339282947`).**
- Phase 3 — nine-agent harness configurator. **Complete; merged into `main`
  and `experimental`.** Backend `69b9620`, handoff docs `5d1f3f0`, UI
  `4a8a5de`; the review fixes and final gate are recorded in the Phase 3
  section below and in `DIALOGUE.md`.
- Phase 4 — token-compact context, MCP surface, and skills. **Merged into
  `main` at `74bd2fb` and pushed.** Wren implemented at `bb4b268` + `cae15fb`;
  Rook reviewed on `rook/phase-4-review`, corrected the documentation, added
  the missing cap test, normalized the benchmark root, and re-ran the full
  gate. Details in the Phase 4 section below.
- Phase 5–14 — execution and publishing plan plus per-phase Wren prompts
  prepared on local `rook/phase-5-14-plan`, based on `main` at `839bb6e`.
  Not pushed. Awaiting the owner's verifier and the integration-target
  decision.

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

## Claims (Phase 3 — complete)

| File | Status | Notes |
|---|---|---|
| `backend/harness_generator.py` | complete | Nine-agent registry, preview/merge/apply, five skill descriptors. |
| `backend/api/routers/harness.py` | complete | Four endpoints; no network. |
| `backend/api/__init__.py` | complete | Mounted the harness router. |
| `backend/tests/test_harness_generator.py` | complete | Registry, formats, merge, path safety. |
| `backend/tests/test_harness_api.py` | complete | L2 contract and apply behavior. |
| `docs/API.md` | complete | Documented the four endpoints. |
| `docs/FEATURES.md` | complete | Apply flag, global-path limits, Phase 4 boundary. |
| `CHANGELOG.md` | complete | Phase 3 entry. |
| `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` | done | Phase 3 status and frozen contract. |
| `docs/coordination/ROOK.md`, `DIALOGUE.md` | done | This planning record. |

## Claims (Phase 4 review — complete)

| File | Status | Notes |
|---|---|---|
| `README.md` | complete | Real 13 tools / 8 resources; corrected benchmark median. |
| `docs/FEATURES.md` | complete | Real MCP surface and context behavior. |
| `docs/MCP.md` | complete | Full reference rewrite; JSON-only MCP pack; omitted reasons. |
| `docs/API.md` | complete | Correct context-pack contract, caps, and status codes. |
| `docs/TOON_BENCHMARK.md` | complete | Normalized root, exact-commit rerun, runbook. |
| `CHANGELOG.md` | complete | Per-symbol caps and measured median. |
| `benchmarks/toon_benchmark.py` | complete | Normalize volatile `root` before measuring. |
| `backend/tests/test_context_compressor.py` | complete | Add `MAX_BODY_CHARS` coverage. |
| `docs/screenshots/v2/*` | complete | Reverted 16 unrelated binaries; kept the Skills preview. |
| `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` | complete | Phase 4 status and gate. |
| `docs/coordination/COMS.md`, `DIALOGUE.md`, `ROOK.md` | complete | Verification record. |

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

### Phase 2 review

Status: accepted at Wren's amended head `478376d`; merge follows.

- Wren's fixes verified: the mind map remounts on repository change
  (`key={repo ?? "none"}`), the storage effect falls back to root + six pillars
  when the new key has no saved state, and the handoff no longer cites a stale
  hash. Item 3 was skipped because Rook had already covered it.
- Gate on the rebased `rook/phase-2-minor`: `npm --prefix frontend run build`
  pass; `tsc --noEmit -p frontend/tsconfig.json` pass; `mindmap.spec.ts` 3/3;
  `journeys.spec.ts` 16/16 with J22 excluded.
- A combined run of both specs reports 19/20: only J22 fails. Standalone J22
  measured 165.2 ms and 137 ms; base `699e8b6` measured 103.3/147.8 ms and
  Wren's first head 114.6/158.7 ms. Under full-suite load the first attempt
  exceeded the 15 s request timeout and the retry measured 246.3 ms. Phase 2
  changes no backend code, so this is an environmental machine-speed failure,
  not a Phase 2 regression. The 100 ms threshold stays unchanged; CI remains
  the authoritative gate.
- Rook minor fixes on `rook/phase-2-minor`: `data-selected` and
  `aria-current` on every node card; GitHub links fall back to `HEAD` instead
  of `main`; symbol route-count badge; MM01 asserts the first search result is
  selected and in view; MM03 asserts the full folder → file → symbol chain.
  Wren should skip the optional search-focus item; Rook has covered it.
  `HANDOFF_PHASE_2.md` now lists the gate commands that actually run
  (`tsc --noEmit -p frontend/tsconfig.json`, Playwright from `frontend/`).
- Merge `rook/phase-2-minor` into `experimental` with `--no-ff`, preserving
  Wren's single implementation commit. `main` stays untouched until the user
  tests `experimental`.

### Phase 3 (complete; merged into main and experimental)

Status: complete. Rook's frozen backend is `69b9620`; the handoff docs are
`5d1f3f0`; Wren's UI is `4a8a5de`. Rook reviewed the UI, fixed the findings
below, ran the independent gate, squashed the three commits and fixes into one
Phase 3 commit, and merged it into local `experimental` with `--no-ff`.
The owner authorized pushing `experimental` on 2026-10-27, then authorized the
main merge and branch cleanup. `experimental` was merged into `main` with
`--no-ff` at `4d39537`; both branches now carry the same Phase 3 tree.

- Scope: the nine-agent harness generator from plan §6, the `HarnessModal`
  UI, `docs/AGENT_INTEGRATION.md`, five evidence screenshots, and the L3
  journey. No backend contract change was required.
- Review fixes: apply success is preserved across the post-write preview
  refresh; initial focus enters the dialog and Shift+Tab cannot escape it; the
  nine-target loop asserts fresh content per target; H02 exercises the diff,
  warning, force checkbox, disabled/enabled action, and second confirmation
  without a POST; H05 proves the success banner survives the refresh.
- Gate: harness 5/5 (H01–H05); journeys 16/16 with J22 excluded; mindmap 3/3;
  frontend build pass; `tsc` 0 errors; backend 473 passed, 1 skipped;
  `compileall` and `pip check` clean; `git diff --check` clean.
- J22's 100 ms threshold is unchanged and remains excluded from the local gate
  because of the recorded environmental timings. The single pytest skip is the
  Windows unprivileged symlink test.
- Apply is off by default (`REPOSCOPE_HARNESS_APPLY=1` enables writes);
  preview never writes; global paths are display-only; existing files need a
  diff and `force: true`.
- Registry deltas: OpenCode uses `mcp.<name>` (not `mcp.servers`),
  Windsurf/Devin uses `.devin/mcp_config.json`, Cline/Roo writes
  `.roo/mcp.json`, and Antigravity skills remain Phase 4.
- Wren's self-contained prompt is `WREN_PROMPT_PHASE_3.md`.
- Explicit non-goals remain: MCP tool/resource changes, `SKILL.md` bodies,
  npm/PyPI packaging, any write outside the project root, and any main-branch
  change before owner approval.

### Phase 4 review (complete; owner authorized the main merge)

Status: merged into `main` at `74bd2fb` and pushed to `origin/main`. Rook
verified Wren's head `cae15fb` in the fresh `RepoScope-rook-phase4-verify`
worktree on `rook/phase-4-review`, fixed the findings, and re-ran the full
gate.

- Review findings: `README.md`, `docs/FEATURES.md`, and `docs/MCP.md` listed
  eight tool names and five resource URIs that do not exist; `docs/API.md` and
  `docs/MCP.md` described the wrong context-pack fields, applied the body caps
  per file instead of per symbol, invented an unchanged-envelope `message`
  field, and returned HTTP 400 for path traversal. The benchmark embedded the
  absolute `root`, so byte counts depended on the checkout path. The
  `MAX_BODY_CHARS` branch had no test.
- Fixes: corrected all documentation against the implementation, normalized
  `root` to `<repo>` in `benchmarks/toon_benchmark.py`, added
  `test_context_pack_full_detail_char_cap`, restored 16 unrelated screenshot
  binaries to `5b881b4`, and kept only the Skills preview as Phase 4 evidence.
- Gate: **509 passed, 1 skipped**; `compileall` and `pip check` clean;
  frontend build pass; `tsc` 0 errors; harness **5/5**; journeys **16/16**
  with J22 excluded; mindmap **3/3**; `git diff --check` clean.
- Independent TOON rerun at the five exact commits: **5/5 roundtrip PASS**,
  **median +39.1% token saving**, **median +26.8% byte saving** against
  compact JSON. No 85% claim remains.
- No graph/schema, edge, existing tool, existing resource, or existing
  endpoint change was introduced by the review fixes. The Phase 4 surface
  remains 13 tools and 8 resources.
- The owner authorized the `main` merge and push. `rook/phase-4-review`
  (`74bd2fb`) was fast-forwarded into `main` and pushed (`7ff5291..74bd2fb`)
  on 2026-10-27. `experimental` remains at `7ff5291` and is intentionally not
  part of this merge.

## Open decisions

- None for Phase 2. The mind-map contract is frozen; Wren consumes it without
  editing backend graph code.
- Phase 3 is merged into `main` and `experimental`; only those two branches
  remain.
- Phase 3 registry deltas are resolved; Wren's verification is the input,
  Rook's contract is the authority.
- Phase 4 is merged into `main` at `74bd2fb`; `experimental` is unchanged.
  The Phase 5+ integration target is **decided: `experimental`** (owner,
  2026-10-27). One phase per commit; no per-phase branch. Local `experimental`
  is fast-forwarded to include Phase 4 and the Phase 5–14 plan.
- Phase 5–14 workflow: Wren implements each phase; an independent verifier
  (to be introduced by the owner) runs the gate; Rook plans, writes the prompt,
  and pushes. Wren may start Phase 5; the verifier must be named before the
  Phase 5 gate and push.
- The Phase 5–14 plan and prompts are on local `rook/phase-5-14-plan`, based on
  `839bb6e`; not pushed. The plan excludes extension publishing.
