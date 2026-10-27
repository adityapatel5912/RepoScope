# RepoScope V2.5–V2.8 — Implementation Plan

**Status:** Approved - Phase 0-4 complete; Phase 4 is verified and owner-authorized for the `main` merge. `experimental` remains at the Phase 3 tree (`7ff5291`).
**Source draft:** [`RepoScope_V2.5_AI_Expansion_Plan.md`](../RepoScope_V2.5_AI_Expansion_Plan.md) (preserved unchanged).
**Target repository:** this repository, `adityapatel5912/RepoScope`. The plan does **not** migrate to `RepoScope-V2`.
**Integration branch:** `experimental` remains the planned integration branch for V2.6+. The owner authorized a direct Phase 4 merge into `main`, so `main` and `experimental` intentionally diverge until the Phase 5 integration target is decided.
**Baseline measured:** 2026-10-26.
**Rule:** do not start a phase until the prior phase's acceptance gate is green. Commit once per phase. Do not mix two phases in one commit.

---

## 0. How to read this plan

This document is the authoritative implementation plan for V2.5 through V2.8. It keeps the full scope of the source draft but corrects its stale assumptions and turns the work into ordered, testable phases.

Every phase has the same shape:

1. **Goal** — the user-visible outcome.
2. **Non-goals** — what must not creep into the phase.
3. **Files and ownership** — exact files, and who may edit them.
4. **Interfaces** — request/response and data contracts.
5. **Implementation steps** — ordered work.
6. **Tests and evidence** — what proves it works.
7. **Acceptance gate** — the objective condition for calling the phase done.
8. **Commit** — the one commit (or small commit series) that lands the phase.
9. **Rollback** — how to undo it without losing the previous phase.

**All previously selected options remain A.** This plan does not reopen the choices about the repository, the mind-map component, the extension architecture, the provider chain, the nine agent targets, or the TOON approach.

### 0.1 Decisions locked by this plan

| ID | Decision |
|---|---|
| D1 | Stay in `adityapatel5912/RepoScope`. One parser, one `GraphStore`, one index. The VS Code extension remains an HTTP client. |
| D2 | Build `frontend/src/components/MindMapView.tsx` as a separate graph mode. Do not extend the 1,810-line `GraphView.tsx` into a second renderer. |
| D3 | The mind map is a strict hierarchy (root → pillar → folder → file → symbol) laid out with `d3-hierarchy` tidy-tree. Dependency-network layout stays in `GraphView`. |
| D4 | The nine targets are Claude Code, Cursor, VS Code/Copilot, Codex CLI, Kiro, Antigravity, Windsurf/Devin, Cline/Roo, and **OpenCode**. Zed is removed. |
| D5 | Agent configs use the latest official formats and paths verified on 2026-10-26. They are re-verified again at the start of Phase 3. |
| D6 | TOON uses the official Python package `toon-format` (`toon_format`) behind a flag. The 85% claim is a hypothesis to measure, not a promise. |
| D7 | Deterministic graph evidence is the source of truth. The LLM writes prose and may resolve low-confidence tie-breaks, but it never invents paths, lines, symbols, or edges. |
| D8 | The existing provider chain stays: Groq → OpenRouter → NVIDIA NIM, plus BYOK. Nebius is not added. |
| D9 | The VS Code extension never parses code and never writes agent configs itself. It calls the backend. |
| D10 | Phase 0 is a CI-stabilization phase before any feature work. |
| D11 | Graph schema v2 is additive. Existing IDs, edge types, endpoints, and MCP tool names remain valid. V1 graphs remain readable. |
| D12 | The server returns `path` and `line`. The frontend builds `vscode://`, `cursor://`, and GitHub URLs because only the client knows the local root, owner, and branch. |
| D13 | The npm package `reposcope-mcp` is a launcher/configurator that delegates to the Python package. It is never a second parser or a second config generator. |
| D14 | The source draft's V2.7 security scope is consolidated into the V2.8 six-engine implementation. There will not be two security rewrites. |
| D15 | Execution was authorized on 2026-10-26. The first batch is Phase 0 and Phase 1. No phase after Phase 1 starts until its handoff gate is green. |
| D16 | Rook and Wren work in separate worktrees with a single writer per file. `experimental` is the only integration branch. `main` is merged only by the owner after testing. |
| D17 | The coordination Markdown files are a record, not the source of truth. Git commits, tests, and the graph schema are authoritative. |

### 0.2 Release map

| Release | Phases | Outcome |
|---|---|---|
| V2.5 | 0–4 | Green CI; graph accuracy/evidence v2; mind map; nine-agent harness; TOON/context packs behind a flag; zero-clone packaging. |
| V2.6 | 5–7 | Verified citations; four-mode reverse-prompt compiler; deterministic multi-file scaffolding. |
| V2.7 | 8–12 | Four tour tracks; topological onboarding; churn/bus-factor tracking; symbol-level PR impact; explainable impact simulator. |
| V2.8 | 13 | Six-engine graph-contextual security suite, scorecard, auto-patch diffs, SARIF 2.1.0. |
| Release | 14 | Hardening, cross-platform verification, docs, packaging, release tags. |

### 0.3 What “done” means for every phase

A phase is done only when all of the following are true:

- The phase's new tests pass locally and in CI on Python 3.11 and 3.12.
- Existing tests still pass; no test is deleted to make a gate green.
- `python -m compileall -q backend/` and the frontend build pass.
- The phase's API contract is documented in `docs/` and covered by an L2 contract test.
- The phase's user-visible surface has an L3 Playwright journey or an explicit, documented reason it cannot be automated.
- No known P1 defect is left behind. Known limits are written in `docs/FEATURES.md`, not hidden.
- The commit message follows the phase's prescribed message.
- The rollback path has been exercised or at least verified by reading the code path.

### 0.4 Why the plan is ordered this way

The dependencies are real, not bureaucratic:

- The mind map needs deterministic pillars, roles, and evidence from the graph. Building it first would force the frontend to duplicate classification and then diverge from the backend.
- The nine-agent harness needs the final MCP tool names and stable config generation. Writing configs before the tool surface is frozen would ship wrong configs.
- Citations need exact AST ranges. Those ranges come from the graph v2 work.
- Reverse prompt, scaffolding, tours, onboarding, PR impact, and the impact simulator all read the same evidence layer. Building them before it would produce seven different notions of “what depends on what”.
- Security needs cross-file call edges and route metadata. The six engines are only credible after Phase 1.
- Parallel work is allowed only where the contract is frozen first. See §18.

---

## 1. Current-state audit

### 1.1 Shipped features and their real limits

This is the baseline the plan must preserve. It is based on the repository as it exists on 2026-10-26, not on the source draft's description of “v3.0”.

| # | Feature | Current implementation | Current limit the plan must address |
|---|---|---|---|
| 1 | Tree-sitter code graph | `backend/graph_builder.py`, `backend/parsers/`, `backend/graph_store.py` | Schema v1; edge types only `contains`, `imports`, `calls`; no `api_calls`, `inherits`, `exports`, route metadata, roles, or per-edge evidence. |
| 2 | Architecture canvas | `frontend/src/components/GraphView.tsx` (~1,810 lines) | One graph mode. No strict hierarchical mind map. Grouping is a rendering collapse, not a tree. |
| 3 | Local mode | `backend/api/routers/local.py`, `backend/watcher.py`, `cli/` | Best-effort watcher; no analytics beyond re-index events. |
| 4 | MCP server | `backend/mcp_server/server.py` using `mcp.server.fastmcp.FastMCP` | 8 tools, 5 resources. No mind map, skeleton, context pack, reverse prompt, contract diff, or security tool. MCP 2.x breaks the import. |
| 5 | VS Code extension | `extensions/vscode/` v2.0.1 | HTTP-only mini-graph, status bar, CodeLens, URI handler. The source draft's standalone scanner is rejected. |
| 6 | Browser preview | `frontend/src/api/localBrowser.ts` and WebAssembly parser | No cross-file resolution; not the server graph. Must not be confused with the full analysis. |
| 7 | Chat citations | `ChatPanel.tsx` client-side `citation-chip` regex | Citations are text, not verified. No AST range check, no hover preview, no mind-map focus. |
| 8 | Impact analysis and PR bot | `backend/impact_analyzer.py`, `backend/pr_impact.py`, `backend/architecture_impact.py` | File-level reverse BFS; risk 0–10; `MAX_FILES_ANALYZED = 25`; no symbol-level diff, no cross-stack callers, no test-gap warning, no CI gate. |
| 9 | Code tours | `backend/tour_generator.py`, `frontend/src/components/TourPanel.tsx` | One generic BFS tour. LLM explanation per stop. No tracks, no lifecycle follow, no mid-tour ask, no CodeTour export. |
| 10 | Student onboarding | `backend/onboarding.py`, `StudentModePanel.tsx` | Hub-first ranking, LLM quizzes, generic Good First Issues. Not topological, not deterministic, no verified challenges. |
| 11 | Repo tracking | `backend/repo_tracker.py`, `TrackerPanel.tsx` | Event feed only. No churn velocity, hotspot score, bus factor, time-machine overlay, or release notes. |
| 12 | Security | `backend/security_scanner.py`, `backend/taint.py`, `SecurityPanel.tsx` | Regex secrets/CVEs and same-file taint. No OSV, no cross-file taint, no AI/MCP audit, no auth/CORS audit, no scorecard, no SARIF for security findings. |
| 13 | Repo map / token metrics | `backend/repo_map.py`, `backend/token_metrics.py` | Token counts use a deterministic estimator, not a BPE tokenizer; no TOON; no skeleton mode; no delta hash. |
| 14 | Reverse prompt / scaffold | Inline handlers in `backend/main.py` | One generic LLM prompt; one LLM-generated scaffold. Not deterministic, not mode-aware, not a multi-file kit. |
| 15 | Harness | None | No agent config generator, no skills bundle, no npm/PyPI zero-clone path. |

### 1.2 Confirmed blockers and defects

These are not speculative. They were reproduced locally.

1. **CI is red before feature work.** With Python 3.11 and the current `backend/requirements.txt`, the suite is **30 failed, 305 passed**. Locally, with a fuller environment, it is **335 passed, 1 warning in ~49s**.
2. **Missing `numpy` and `scipy`.** PageRank uses `networkx.pagerank`, which needs the optional numerical stack. The missing packages explain 6 PageRank failures and contribute to the 30 failures.
3. **`mcp` is in `pyproject.toml` but not in `backend/requirements.txt`.** A `pip install -r backend/requirements.txt` environment has no MCP server dependency.
4. **`mcp 2.3.0` is not a fix.** It removes or moves `mcp.server.fastmcp.FastMCP`, so even installing the latest `mcp` leaves 22 failures. Phase 0 pins `mcp>=1.29,<2`.
5. **`typer` and `watchdog` are also missing from `backend/requirements.txt`.** They are in `pyproject.toml`, so a deployment installed from requirements cannot run the CLI/watcher path reliably.
6. **Health contract mismatch.** `.github/workflows/qa.yml` asserts `/api/health` returns `"status": "ok"`, while `backend/main.py` returns `"status": "healthy"` and `backend/tests/test_health.py` asserts `"healthy"`. L2 fails even when the server is healthy.
7. **`render.yaml` installs only `backend/requirements.txt`.** Dependency omissions affect production, not just CI.
8. **No frontend unit-test runner.** The frontend has Playwright but no Vitest/Testing Library. New pure layout/tree logic should not be tested only through a browser.
9. **Package and extension versions diverge.** `pyproject.toml` is 2.0.0; the VS Code extension is 2.0.1. The release train needs one version source.
10. **The source draft is stale in several load-bearing places.** See Appendix J. The most important: it targets a different repository, names `KnowledgeGraphView.tsx`, includes Zed, uses several wrong MCP paths, proposes a standalone VS Code scanner, and proposes replacing `mcp_client.py` (a GitHub client) with an MCP server.

### 1.3 What must not regress

- Node IDs: `file:<rel>`, `func:<rel>:<name>`, `class:<rel>:<name>`.
- Edge semantics: `contains`, `imports`, `calls` keep their direction and meaning.
- Existing HTTP endpoints and response fields. New fields are additive.
- Existing MCP tool names and resource URIs.
- The local-mode privacy guard: the local router performs no outbound request.
- The extension's HTTP-only design.
- The existing provider chain and BYOK behavior.
- The browser preview's explicit “preview, not full analysis” labeling.

---

## 2. Target architecture

### 2.1 One index, three front-ends

The architecture stays:

```
                 ┌──────────────────────────────┐
                 │  Tree-sitter parser + Graph  │
                 │  Builder (one implementation) │
                 └──────────────┬───────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  GraphStore (JSON)    │
                    │  schema v1 → v2       │
                    │  evidence + metrics   │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
  ┌─────▼─────┐          ┌──────▼──────┐         ┌──────▼──────┐
  │ Web app   │          │ CLI daemon  │         │ MCP server  │
  │ REST/SSE  │          │ localhost   │         │ stdio/HTTP  │
  └───────────┘          └─────────────┘         └─────────────┘
```

No second parser. No second graph. No extension-side scanner.

### 2.2 The evidence layer

Every user-visible claim must be traceable to one of:

- a graph node with `path`, `line`, `end_line`;
- an edge with a source file/line and a resolution confidence;
- a file read with a verified line range;
- a deterministic metric with a named formula.

The LLM may explain those facts. It may not create them. This is the rule that separates RepoScope from a chat wrapper.

### 2.3 New backend modules

| Module | Responsibility | First phase |
|---|---|---|
| `backend/symbol_resolver.py` | Alias/barrel/relative import resolution, call resolution, inheritance, exports. | 1 |
| `backend/mindmap_classifier.py` | Deterministic six-pillar classification and tree projection. | 1 |
| `backend/mindmap.py` | Mind-map query API and ancestor paths. | 1/2 |
| `backend/harness_generator.py` | Nine-agent registry, preview, merge, apply, skills. | 3 |
| `backend/context_compressor.py` | TOON, skeleton mode, delta hash, context packs. | 4 |
| `backend/citation_verifier.py` | AST-grounded citation parsing, snapping, confidence. | 5 |
| `backend/reverse_prompt.py` | Four-mode deterministic blueprint compiler. | 6 |
| `backend/scaffolder.py` | Deterministic 12–20 file starter kits. | 7 |
| `backend/tour_generator.py` (rewrite) | Four deterministic tracks + CodeTour export. | 8 |
| `backend/onboarding.py` (rewrite) | Topological curriculum + verified challenges. | 9 |
| `backend/repo_metrics.py` (new) | Churn, hotspot, bus factor, commit compare. | 10 |
| `backend/pr_impact.py` (rewrite) | Symbol-level diff and no file cap. | 11 |
| `backend/impact_analyzer.py` (extend) | Three-hop simulator with explainable score. | 12 |
| `backend/security/` (new package) | Six engines, models, scoring, SARIF adapter. | 13 |
| `backend/version.py` (new) | One version source for API, CLI, SARIF. | 0/14 |

### 2.4 New frontend modules

| Module | Responsibility | First phase |
|---|---|---|
| `frontend/src/components/MindMapView.tsx` | Separate mind-map mode. | 2 |
| `frontend/src/components/mindmap/MindMapNode.tsx` | Memoized node card, actions, risk badges. | 2 |
| `frontend/src/components/mindmap/MindMapToolbar.tsx` | Orientation, expand/collapse, search, overlays. | 2 |
| `frontend/src/components/mindmap/MindMapOutline.tsx` | Accessible semantic tree / keyboard navigation. | 2 |
| `frontend/src/components/mindmap/MindMapSearch.tsx` | Debounced search, result focus, auto-expand. | 2 |
| `frontend/src/lib/mindmapLayout.ts` | `d3-hierarchy` layout, TB/LR, stable positions. | 2 |
| `frontend/src/lib/mindmapTree.ts` | Tree normalization, ancestor paths, visible nodes. | 2 |
| `frontend/src/components/HarnessModal.tsx` | Nine-agent preview/apply UI. | 3 |
| `frontend/src/components/CitationPill.tsx` | Verified citation chip + hover preview. | 5 |
| `frontend/src/components/ReversePromptPanel.tsx` | Four modes, budget, preview/download. | 6 |
| `frontend/src/components/ScaffoldPanel.tsx` | File tree, preview, zip, command. | 7 |
| `frontend/src/components/TourPanel.tsx` (rewrite) | Tracks, stops, spotlight, ask, export. | 8 |
| `frontend/src/components/StudentModePanel.tsx` (rewrite) | Curriculum, challenges, badge. | 9 |
| `frontend/src/components/TrackerPanel.tsx` (extend) | Metrics, timeline, compare overlay. | 10 |
| `frontend/src/components/PRImpactPanel.tsx` | Symbol-level report, test stubs, gate. | 11 |
| `frontend/src/components/ImpactPanel.tsx` (extend) | Simulator, three hops, score breakdown. | 12 |
| `frontend/src/components/SecurityPanel.tsx` (rewrite) | Scorecard, filters, attack path, SARIF. | 13 |

### 2.5 API compatibility policy

- Existing paths stay. New behavior is opt-in via a new field or a new path.
- Existing response keys stay. New keys are additive.
- A v1 graph is accepted. A v2 graph is written.
- Existing MCP tools keep their names. New tools are added.
- A feature flag may hide a new UI surface, but it must not silently change an old response.

---

## 3. Phase 0 — CI stabilization and dependency truth

**Release:** V2.5 prerequisite
**Depends on:** none
**Risk:** low
**Owner:** integrator

### Goal

Make the repository's test suite green on a clean Python 3.11/3.12 install using only the declared dependencies, and make the CI health contract match the application.

### Non-goals

- No feature work.
- No graph schema changes.
- No frontend redesign.
- No MCP 2 migration.

### Files

| File | Change |
|---|---|
| `backend/requirements.txt` | Add `numpy`, `scipy`, `mcp>=1.29,<2`, `typer`, `watchdog`; document why. |
| `pyproject.toml` | Pin `mcp>=1.29,<2`; mirror the requirement set; keep `pytest` in dev extras, but requirements may keep it for CI. |
| `.github/workflows/qa.yml` | Fix health assertion; remove redundant installs; add `pip check`, compileall, frontend build. |
| `backend/main.py` | Add additive fields to `/api/health`; keep `status: "healthy"`. Do not change `/health`. |
| `backend/tests/test_health.py` | Add explicit assertions for both endpoints. |
| `backend/tests/test_dependency_contract.py` (new) | Assert the runtime imports required by the app are declared. |
| `docs/QA_REPORT.md` | Record the before/after baseline. |
| `CHANGELOG.md` | Add an “Unreleased — CI baseline” entry. |

### Interfaces

Canonical health responses:

```json
GET /health
{"status": "ok"}

GET /api/health
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime_seconds": 123.4,
  "graph": {"loaded": true, "nodes": 1863, "edges": 3419},
  "schema_version": 1
}
```

The CI assertion must be explicit:

```yaml
curl -fsS http://127.0.0.1:8010/api/health \
  | python -c "import json,sys; d=json.load(sys.stdin); assert d.get('status') == 'healthy', d"
curl -fsS http://127.0.0.1:8010/health \
  | python -c "import json,sys; d=json.load(sys.stdin); assert d.get('status') == 'ok', d"
```

Do not “fix” this by accepting any status. The two endpoints have different jobs: `/health` is a liveness probe; `/api/health` is the application contract.

### Implementation steps

1. Create a clean Python 3.11 virtual environment. Install only `backend/requirements.txt`.
2. Run `pytest -q`. Record the exact failures in `docs/QA_REPORT.md`.
3. Add `numpy>=1.26,<3` and `scipy>=1.11,<2`. Re-run. Confirm the PageRank failures disappear.
4. Add `mcp>=1.29,<2`. Re-run. Confirm the MCP server tests import and pass.
5. Add `typer>=0.12,<1` and `watchdog>=4,<7`. Re-run.
6. Add `python -m pip check` to CI.
7. Fix the L2 health assertion as above.
8. Add a frontend build job: `npm ci`, `npm run build` on Node 20.
9. Add a Python matrix: 3.11 and 3.12. Do not add 3.13/3.14 yet; the local 3.14 pass is useful but not the deployment target.
10. Add `python -m compileall -q backend/`.
11. Keep the extension job unchanged; it already compiles and tests.
12. Run the full local gate: `pytest -q`, `npm --prefix frontend run build`, `npm --prefix extensions/vscode run compile`, and the L2 curl script.
13. Confirm `render.yaml` installs the same requirements and therefore gets the same fixes.

### Tests and evidence

- `pytest -q` → at least 335 passed, 0 failed on Python 3.11 and 3.12.
- `pip check` → no broken requirements.
- L2 health contract → both assertions pass.
- Frontend build → exit 0.
- Extension compile/test → exit 0.
- A dependency test that asserts `numpy`, `scipy`, `mcp`, `typer`, and `watchdog` are declared in `backend/requirements.txt`.

### Acceptance gate

- [ ] Clean 3.11 environment from requirements only: 0 failures.
- [ ] Clean 3.12 environment from requirements only: 0 failures.
- [ ] L2 contract job passes.
- [ ] Frontend build job passes.
- [ ] Extension job passes.
- [ ] `pip check` passes.
- [ ] `docs/QA_REPORT.md` contains the before/after numbers.
- [ ] No feature code changed outside health additive fields.

### Commit

```
chore(ci): restore green baseline and pin runtime dependencies
```

### Rollback

Revert the dependency pins and CI changes. No product behavior depends on them. If a dependency pin causes an unexpected conflict, pin the narrowest working range and document it; do not delete tests.

## 4. Phase 1 — Graph schema v2, deterministic resolver, API linker, mind-map contract

**Release:** V2.5
**Depends on:** Phase 0
**Risk:** high — this is the evidence layer every later phase reads
**Owner:** Rook (contract and backend); Wren consumes the frozen mind-map contract in Phase 2
**Branch:** `experimental`

### Goal

Make the graph describe the repository more truthfully without breaking a single v1 node id, edge direction, endpoint, or MCP tool name. A v1 reader must still accept the graph; a v2 reader must see the new evidence, roles, pillars, route metadata, and cross-stack `api_calls` edges. Freeze the mind-map HTTP contract so the frontend can be built against it without duplicating classification.

### Non-goals

- No mind-map React component in this phase (Phase 2).
- No harness generator (Phase 3).
- No TOON encoder (Phase 4).
- No LLM call in the graph builder. Every new fact is deterministic.
- No change to the v1 edge directions or the existing `contains`, `imports`, `calls` semantics.
- No change to the browser preview parser. It remains a preview, not the server graph.

### Files

| File | Change |
|---|---|
| `backend/graph_store.py` | `SCHEMA_VERSION = 2`; accept v1 and v2; add `api_calls`, `inherits`, `exports`; persist additive top-level keys; validate evidence. |
| `backend/parse_cache.py` | `CACHE_VERSION = 3`; add `routes`, `api_calls`, `heritage` to `FileFacts`. |
| `backend/symbol_resolver.py` (new) | tsconfig/jsconfig alias loading, relative import resolution, barrel unwrapping, route/API-call/heritage scanners, conservative symbol resolution helpers. |
| `backend/mindmap_classifier.py` (new) | Six-pillar classification, role taxonomy, deterministic tree projection. |
| `backend/mindmap.py` (new) | Mind-map payload builder and ancestor lookup. |
| `backend/api/routers/mindmap.py` (new) | `GET /api/mindmap` contract. |
| `backend/api/__init__.py` | Mount the mind-map router. |
| `backend/graph_builder.py` | `finalize_graph()` shared by full builds and `GraphIndexer`; node enrichment; new edge types; schema metadata. |
| `backend/graph_analysis.py` | Include `inherits`, `exports`, `api_calls` in dependency traversal. |
| `backend/main.py` | Health reports schema version from the store constant; no behavior change. |
| `backend/tests/test_graph_v2.py` (new) | Schema, evidence, additive-edge, incremental parity tests. |
| `backend/tests/test_symbol_resolver.py` (new) | Alias, barrel, relative import, route matching tests. |
| `backend/tests/test_mindmap_classifier.py` (new) | Pillar/role/tree determinism tests. |
| `backend/tests/test_mindmap_api.py` (new) | L2 contract test. |
| `backend/tests/test_graph_golden.py` | Golden comparison pins the v1 edge subset; a new assertion covers additive v2 edges. Do not regenerate v1 snapshots to hide drift. |
| `docs/API.md`, `docs/FEATURES.md`, `CHANGELOG.md` | Document the additive contract. |

### Graph schema v2

The graph is a superset of v1. The v1 keys and values are unchanged.

```json
{
  "schema_version": 2,
  "metadata": {
    "builder": "graph_builder",
    "capabilities": ["roles", "pillars", "routes", "api_calls", "inherits", "exports"]
  },
  "nodes": [
    {
      "id": "file:backend/main.py",
      "type": "file",
      "label": "backend/main.py",
      "path": "backend/main.py",
      "language": "py",
      "size": 12345,
      "sha256": "…",
      "pillar": "backend",
      "role": "entry_point",
      "route_count": 12
    },
    {
      "id": "func:backend/main.py:health",
      "type": "function",
      "label": "health",
      "file": "backend/main.py",
      "path": "backend/main.py",
      "line": 391,
      "end_line": 414,
      "pillar": "backend",
      "role": "api_controller",
      "routes": [{"method": "GET", "path": "/api/health", "line": 391}]
    }
  ],
  "edges": [
    {
      "source": "func:frontend/src/components/ChatPanel.tsx:send",
      "target": "func:backend/main.py:chat",
      "type": "api_calls",
      "evidence": {
        "kind": "http_call",
        "file": "frontend/src/components/ChatPanel.tsx",
        "line": 214,
        "method": "POST",
        "path": "/api/chat",
        "confidence": 0.9
      }
    }
  ],
  "api_routes": [
    {
      "method": "GET",
      "path": "/api/health",
      "file": "backend/main.py",
      "line": 391,
      "handler": "health",
      "node_id": "func:backend/main.py:health"
    }
  ],
  "summary": "…"
}
```

**Edge types.** `contains`, `imports`, `calls` keep their v1 meaning. `api_calls` goes from the frontend caller (symbol, or its file when the call is module-level) to the backend route handler (symbol, or the route's file). `inherits` goes from a class to a resolvable base class. `exports` goes from a barrel/re-exporting file to the file it re-exports from. New edges always carry an `evidence` object. Missing evidence is allowed for v1 edges so an old graph remains valid.

**Evidence rules.** `file` is repo-relative. `line` is 1-based. `confidence` is in `[0, 1]`. A resolver that cannot identify the target with confidence leaves the edge out; it never guesses. No new edge may reference an unknown node.

**Version policy.** `JsonGraphStore.load()` accepts a wrapped v1 or v2 payload and a bare graph. `save()` writes `schema_version` from the graph when it is valid, otherwise `SCHEMA_VERSION`. `stats()` reports the stored schema version. A v1 graph loaded and re-saved without enrichment is upgraded to v2 only if its nodes/edges were enriched; otherwise the store records the truth it was given. The builder always writes v2.

### Mind-map API contract (frozen for Phase 2)

`GET /api/mindmap?include_symbols=true&max_nodes=20000`

Response:

```json
{
  "schema_version": 2,
  "generated_at": "2026-10-26T12:00:00Z",
  "source": {"nodes": 1863, "edges": 3419, "root": "/abs/path"},
  "stats": {
    "files": 348,
    "symbols": 1515,
    "pillars": 6,
    "routes": 63,
    "api_calls": 41
  },
  "pillars": [
    {"id": "backend", "label": "Backend & Core", "description": "…", "file_count": 120}
  ],
  "root": {
    "id": "root",
    "kind": "root",
    "label": "RepoScope",
    "parent_id": null,
    "children": [
      {
        "id": "pillar:backend",
        "kind": "pillar",
        "label": "Backend & Core",
        "pillar": "backend",
        "parent_id": "root",
        "metrics": {"files": 120, "symbols": 600, "routes": 63},
        "children": [
          {
            "id": "folder:backend:backend/api",
            "kind": "folder",
            "label": "api",
            "path": "backend/api",
            "parent_id": "pillar:backend",
            "children": [
              {
                "id": "folder:backend:backend/api/routers",
                "kind": "folder",
                "label": "routers",
                "path": "backend/api/routers",
                "parent_id": "folder:backend:backend/api",
                "children": [
                  {
                    "id": "file:backend/api/routers/analysis.py",
                    "kind": "file",
                    "label": "analysis.py",
                    "path": "backend/api/routers/analysis.py",
                    "line": 1,
                    "role": "api_controller",
                    "pillar": "backend",
                    "language": "py",
                    "pagerank": 0.0021,
                    "route_count": 4,
                    "parent_id": "folder:backend:backend/api/routers",
                    "children": [
                      {
                        "id": "func:backend/api/routers/analysis.py:hotspots",
                        "kind": "symbol",
                        "label": "hotspots",
                        "path": "backend/api/routers/analysis.py",
                        "line": 66,
                        "end_line": 88,
                        "role": "api_controller",
                        "parent_id": "file:backend/api/routers/analysis.py",
                        "children": []
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

The API is additive and read-only. It returns `503` only when no repository is active; an empty graph returns `200` with an empty pillar tree. `include_symbols=false` truncates at file level. `max_nodes` caps the returned tree deterministically: pillars and folders first, then files by path, then symbols by line. The response always says `truncated: true|false` and the counts that were omitted.

Folder ids are `folder:<pillar>:<repo-relative-folder-path>`, for example `folder:backend:backend/api/routers`. Every directory level is a folder. A top-level directory that names the pillar is not repeated as a separate level, but the full repository-relative path stays in the folder's `path`. File symbols always sit under their file, and handler symbols carry the routes that resolve to them.

### Implementation steps

1. Add the new `FileFacts` fields and bump `CACHE_VERSION`. A v2 cache and a v3 cache must never be mixed.
2. Implement `symbol_resolver.py` scanners:
   - Python route decorators via `ast` (`get`, `post`, `put`, `patch`, `delete`, `route`, `api_route`, `websocket`).
   - Express-style `app|router.(get|post|put|patch|delete|all)` routes.
   - Client `fetch`, `axios.*`, `EventSource`, and same-origin `/api/...` calls. Full URLs are normalized to their path. Template expressions become `*` and only match parameterized routes.
   - Python `ClassDef` bases and TS/JS `extends`/`implements` clauses.
   - tsconfig/jsconfig loading with comments/trailing commas, `baseUrl`, and `paths` aliases. Merge root and `frontend/` configs.
   - Barrel unwrapping for `index.ts`, `index.js`, and `__init__.py` re-exports, bounded to 8 hops to prevent cycles.
3. Add `finalize_graph(graph, facts, resolver_config)` and call it from `assemble_graph`, `GraphIndexer.index`, and `GraphIndexer._publish`.
4. Enrich nodes with `path`, `end_line`, `pillar`, `role`, `route_count`, and handler `routes`. Do not change ids or labels.
5. Add `inherits`, `exports`, and `api_calls` edges with evidence. Resolve inheritance and API targets only when unique; otherwise skip.
6. Attach route metadata to handler nodes and aggregate `api_routes` at graph level.
7. Add the mind-map classifier and payload builder; mount `GET /api/mindmap`.
8. Add the new edge types to `DEPENDENCY_EDGE_TYPES` so blast radius and cycles see them, but keep `contains` excluded.
9. Update the store’s validation and persistence. Preserve `schema_version`, `metadata`, and `api_routes` through a JSON round trip.
10. Add tests, API docs, and a CHANGELOG entry.

### Tests and evidence

- Golden snapshots: the v1 node set and the v1 edge subset are unchanged. The test explicitly filters `contains|imports|calls` for the snapshot comparison and separately asserts that any v2 edge is valid and does not dangle.
- `test_graph_v2.py`:
  - a v2 graph has `schema_version == 2`;
  - a v1 graph still validates;
  - an unknown edge type is rejected;
  - malformed evidence is rejected;
  - a v2 store round trip preserves `metadata` and `api_routes`;
  - `inherits` resolves a two-file fixture;
  - `exports` follows a barrel;
  - `api_calls` links a frontend `fetch` to the backend handler;
  - the incremental graph equals a full rebuild, including v2 edges.
- `test_symbol_resolver.py`: alias, relative import, barrel, route normalization, parameter matching, and “no guess” behavior.
- `test_mindmap_classifier.py`: every pillar rule, precedence, role rules, stable ordering, and folder nesting.
- `test_mindmap_api.py`: 200 + schema, empty graph, `include_symbols=false`, `max_nodes` truncation, and no duplicate ids.
- `pytest -q` green on Python 3.11 and 3.12; `python -m compileall -q backend/`.

### Acceptance gate

- [ ] All v1 node ids, edge directions, existing endpoint fields, and MCP tool names are unchanged.
- [ ] `SCHEMA_VERSION == 2`; v1 graphs still load.
- [ ] Golden v1 snapshots pass without regeneration.
- [ ] New edge types are evidence-bearing and never dangle.
- [ ] The mind-map API is documented and frozen; Wren can build against it without reading `graph_builder.py`.
- [ ] Incremental and full graphs are identical.
- [ ] Python 3.11/3.12 CI green.

### Commit

```
feat(graph): add schema v2 evidence, resolver, and mind-map contract
```

### Rollback

Revert the phase commit. The v1 builder and store are unchanged in shape; the only persistent effect is a v2 graph file, which the reverted v1 store can still read because v1 validation ignores extra node keys and rejects only the three new edge types. If a v1 reader is deployed against a v2 graph, it must ignore additive keys; the compatibility policy already requires this. Do not delete the new tests.

---

## 5. Phase 2 — Vertical mind-map UI (Wren, Rook reviews)

**Release:** V2.5
**Depends on:** Phase 1 (frozen `GET /api/mindmap`)
**Risk:** medium
**Owner:** Wren; Rook reviews and merges

### Goal

Add a second, strict hierarchical view beside the dependency network: root → six pillars → folders → files → symbols. The first paint shows the root and pillars only. Expand/collapse, search, orientation, file actions, and blast-radius highlighting are wired to the real graph. `GraphView.tsx` is not rewritten into a second renderer.

### Non-goals

- No replacement of the dependency network.
- No new parser, no client-side classification.
- No new graph endpoint beyond the frozen Phase 1 contract.
- No GitHub or editor URL construction on the server.

### Files

| File | Change |
|---|---|
| `frontend/src/components/MindMapView.tsx` (new) | The mode container, data fetch, expand/collapse state, toolbar, outline. |
| `frontend/src/components/mindmap/MindMapNode.tsx` (new) | Memoized node card and action bar. |
| `frontend/src/components/mindmap/MindMapToolbar.tsx` (new) | Expand all, collapse, orientation, search, network toggle. |
| `frontend/src/components/mindmap/MindMapOutline.tsx` (new) | Accessible `<ul role="tree">` alternative and keyboard navigation. |
| `frontend/src/components/mindmap/MindMapSearch.tsx` (new) | Debounced search and auto-expand. |
| `frontend/src/lib/mindmapLayout.ts` (new) | Pure tidy-tree layout for TB and LR. |
| `frontend/src/lib/mindmapTree.ts` (new) | Normalization, visible-node filtering, ancestor path. |
| `frontend/src/api/client.ts` | `getMindmap()` and typed payload. |
| `frontend/src/App.tsx` | A view-mode switch; keep the graph as the default. |
| `frontend/src/components/TopBar.tsx` | The mode switch and search entry point. |
| `frontend/tests/e2e/mindmap.spec.ts` (new) | L3 journey. |
| `frontend/src/lib/__tests__/mindmapTree.test.ts` (new, if Vitest is added) | Pure tree tests. |
| `frontend/package.json` | Add `d3-hierarchy`; add Vitest only if the phase budget allows. |

### Interface

`getMindmap(params?: {includeSymbols?: boolean; maxNodes?: number}): Promise<MindmapPayload>` in `client.ts`. The payload is the Phase 1 contract. `MindMapView` never calls `/api/repo/graph` to derive pillars.

Layout contract:

- TB is the default. LR is a toolbar toggle.
- Only root + pillars render on first paint. Expanding a pillar reveals its folders; expanding a folder reveals its files; expanding a file reveals its symbols.
- The expanded set is persisted in `sessionStorage` keyed by repository name.
- Search matches label and path, auto-expands ancestors, and focuses the first result.
- Every file card exposes GitHub, VS Code/Cursor, and Blast Radius actions. The client knows `owner`, `repo`, branch, and local root; the server does not.
- Blast Radius calls the existing impact endpoint and highlights direct callers amber and transitive callers cyan.
- Keyboard: `Enter` expands, `Space` selects, arrow keys move in the outline, `Escape` closes search.

### Acceptance gate

- [ ] `npm run build` and `npx tsc --noEmit` pass.
- [ ] L3 journey: load the QA fixture, switch to Mind Map, expand the backend pillar, search for `main.py`, open the file card, and assert the outline mirrors the visible tree.
- [ ] No horizontal overflow at 1600×900 and 1280×800.
- [ ] The dependency network remains the default and still passes its journeys.
- [ ] No frontend file contains a hard-coded pillar classifier.

### Commit

```
feat(ui): add vertical six-pillar mind map
```

### Rollback

Hide the mode switch behind `localStorage` / a feature flag and leave `MindMapView.tsx` unused. Do not delete the graph mode.

---

## 6. Phase 3 — Nine-agent harness generator

**Release:** V2.5
**Depends on:** Phase 1 (stable MCP tool names) and Phase 2 (a place to surface the modal)
**Risk:** medium — wrong configs are worse than no configs
**Owner:** Wren (registry research, fixture validation, UI); Rook (API contract, generator, apply safety, tests, merge)
**Status (2026-10-27):** complete. Backend `69b9620`, handoff docs `5d1f3f0`, and UI `4a8a5de` were reviewed, squashed into one Phase 3 commit, and merged into `experimental`. The owner authorized pushing `experimental`, then authorized the main merge; `main` was merged at `4d39537` and both branches carry the same Phase 3 tree.

### Goal

Generate exact, copy-pasteable MCP configuration for all nine targets, preview every file before writing, and never invent a path. One-click apply writes only known files under the repository root, with a dry-run default.

### Ownership and sequence

| Work | Owner | Notes |
|---|---|---|
| Re-verify nine targets against official docs; record path, format, transport, docs URL, `verified_at` | Wren | First task; post the registry handoff in `DIALOGUE.md` before code. |
| Freeze the API contract and implement the generator, router, safety, and backend tests | Rook | `rook/phase-3-harness`; one backend commit. |
| Build `HarnessModal`, the entry point, the L3 journey, `docs/AGENT_INTEGRATION.md`, and screenshots | Wren | `wren/phase-3-harness`, based on Rook's announced backend commit. |
| Review, run the clean gate, squash the UI commit into the phase commit, merge `--no-ff` into `experimental` | Rook | Sole integrator; `main` is untouched until the owner authorizes it. |

Order: owner signal → Wren registry handoff → Rook backend commit → Wren UI
commit → Rook review and integration. Wren must not start the UI against a
guessed contract; if the backend preview is missing or differs from this
section, stop and report it.

### Targets and paths

| Target | Project file | Global / note |
|---|---|---|
| Claude Code | `.mcp.json`, `CLAUDE.md` | `claude mcp add` command in the preview. |
| Cursor | `.cursor/mcp.json`, `.cursor/rules/reposcope.mdc` | Deep-link command in the preview. |
| VS Code / Copilot | `.vscode/mcp.json` (`servers`), portable `.mcp.json`, `.github/copilot-instructions.md` | Use the `servers` key. |
| Codex CLI | `.codex/config.toml`, `AGENTS.md` | `[mcp_servers.reposcope]`. |
| Kiro | `.kiro/settings/mcp.json`, `.kiro/steering/reposcope.md` | Project-scoped. |
| Antigravity | `.agents/mcp_config.json`, `AGENTS.md`, `.agents/skills/` | Also dogfood the config against RepoScope. |
| Windsurf / Devin | `.devin/mcp_config.json`, `.windsurf/rules/reposcope.md` | Global `~/.codeium/windsurf/mcp_config.json` and `~/.config/devin/mcp_config.json` are shown, never written. |
| Cline / Roo | `.roo/mcp.json`, `.clinerules` | Cline's global `~/.cline/data/settings/cline_mcp_settings.json` is shown, never written. |
| OpenCode | `opencode.json` with `mcp.reposcope` | Current schema is `mcp.<name>` with `type: local \| remote`; there is no `mcp.servers` key. |

### Files

Rook owns:

- `backend/harness_generator.py` (new)
- `backend/api/routers/harness.py` (new)
- `backend/api/__init__.py` (mount the router)
- `backend/tests/test_harness_generator.py` (new)
- `backend/tests/test_harness_api.py` (new)
- `docs/API.md`, `docs/FEATURES.md`, `CHANGELOG.md`

Wren owns:

- `frontend/src/components/HarnessModal.tsx` (new)
- `frontend/src/components/harness/*` (new, only if the modal is split)
- `frontend/src/api/client.ts` (harness types and calls)
- `frontend/src/App.tsx`, `frontend/src/components/TopBar.tsx` (entry point and modal state)
- `frontend/tests/e2e/harness.spec.ts` (new)
- `docs/AGENT_INTEGRATION.md` (new)
- `docs/screenshots/v2/harness/*.png` (new)

Do not touch `frontend/src/components/GraphView.tsx` or
`frontend/src/components/mindmap/*` in this phase. Do not add `SKILL.md`
bodies or `.agents/skills/*` files; those are Phase 4.

### API

All endpoints are read-only unless the request explicitly sets `apply: true`,
and `apply: true` is refused unless `REPOSCOPE_HARNESS_APPLY=1`. No endpoint
calls the network.

#### `GET /api/harness/agents`

```json
{
  "agents": [
    {
      "id": "claude",
      "label": "Claude Code",
      "config_paths": [".mcp.json", "CLAUDE.md"],
      "transport": ["stdio", "http"],
      "default_transport": "stdio",
      "global_preview_paths": [],
      "docs_url": "https://...",
      "verified_at": "2026-10-26"
    }
  ],
  "apply_enabled": false
}
```

`config_paths` are project-relative. `global_preview_paths` are displayed and
never written. `apply_enabled` reflects the server flag, not the UI.

#### `GET /api/harness/config?agent=<id>&transport=stdio&root=<absolute path>`

Preview only; never writes. `root` is optional when the active repository has
a local path. Otherwise it is required and must be an existing absolute
directory.

```json
{
  "ok": true,
  "agent": "claude",
  "label": "Claude Code",
  "transport": "stdio",
  "root": "D:\\repo",
  "command": "claude mcp add --scope project --transport stdio reposcope -- reposcope-mcp --root \"D:\\repo\"",
  "apply_enabled": false,
  "requires_force": false,
  "files": [
    {
      "path": ".mcp.json",
      "format": "json",
      "content": "{...}\n",
      "exists": false,
      "diff": null,
      "will_write": true
    }
  ],
  "warnings": []
}
```

- `format` is `json`, `toml`, or `markdown`.
- `content` is the exact text that would be written.
- `exists` says whether the target file is already present.
- `diff` is a unified diff when `exists` is true and the content differs;
  otherwise `null`.
- `will_write` is false for an identical file or a global preview path.
- `requires_force` is true when any existing file would change.

#### `POST /api/harness/apply`

Body:

```json
{
  "agent": "claude",
  "transport": "stdio",
  "root": "D:\\repo",
  "apply": false,
  "force": false
}
```

The response is the preview shape plus:

```json
{
  "apply": true,
  "applied": [".mcp.json"],
  "unchanged": [],
  "warnings": []
}
```

- `apply: false` is a dry run and returns the same file list as the preview.
- `apply: true` writes only the files listed as writable under `root`.
- `403` when the flag is off; `409` when an existing file differs and `force`
  is false; `400` for an unknown agent, unsupported transport, invalid root,
  or an unsafe path.
- Existing JSON/TOML configs are merged, not replaced: unrelated keys and
  servers survive. An unparseable existing config is a warning and requires
  `force: true` to replace.
- Markdown instruction files get one delimited RepoScope section; a second
  apply is a no-op.
- Writes are atomic (temporary file in the same directory, then replace).

#### `GET /api/harness/skills`

Returns the five bundle descriptors: `blast-radius-guard`,
`zero-grep-architect`, `pr-contract-shield`, `onboarding-navigator`, and
`dead-code-surgeon`. Each has `id`, `label`, `description`, `targets`,
`files`, and `content_available: false`. The `SKILL.md` bodies land in Phase 4.

### Safety rules

- Reject absolute paths, `..`, symlinks or junctions that resolve outside the
  root, and unknown config paths.
- Never overwrite an existing file without returning a diff and requiring
  `force: true`.
- The preview always includes the exact command, the exact JSON/TOML, and the
  paths that would change.
- The backend does not call the network to “verify” a config.
- Configs use the Python package or the npm launcher, never a second parser.
- `apply` is off by default; `REPOSCOPE_HARNESS_APPLY=1` is the only way to
  enable writes.
- Global paths (Windsurf, Cline) are shown as text and never written.
- No secret is read from `.env` or copied into a config; placeholders only.

### Acceptance gate

- [ ] Every target has a fixture assertion for path, format, and transport.
- [ ] Claude’s `.mcp.json`, VS Code’s `servers`, Codex’s TOML, and OpenCode’s
  `mcp.reposcope` parse successfully in tests.
- [ ] A path-traversal attempt is rejected (absolute path, `..`, and
  symlink/junction escape).
- [ ] No `apply` writes outside the root; preview never writes.
- [ ] Existing files require a diff and `force: true`; an unchanged file is a
  no-op.
- [ ] The modal previews all nine without writing.
- [ ] Antigravity’s own config is dogfooded against RepoScope (Wren reports
  whether it works, or why it could not be run).
- [ ] `GET /api/harness/agents`, `GET /api/harness/config`,
  `POST /api/harness/apply`, and `GET /api/harness/skills` have L2 contract
  coverage.
- [ ] The Phase 3 Playwright journey passes with zero un-whitelisted console
  errors.
- [ ] Existing tests, the frontend build, `tsc`, `compileall`, and `pip check`
  pass.
- [ ] No Phase 4 file (context compressor, MCP tools, `SKILL.md` bodies) is
  changed.

### Non-goals

- No MCP tool or resource changes (Phase 4).
- No `SKILL.md` bodies or `.agents/skills/*` files (Phase 4).
- No npm package, PyPI packaging, or zero-clone work (Phase 14).
- No writes to global agent config paths.
- No LLM call and no network call to validate a config.

### Commit

Phase commit (exactly one commit on `experimental`):

```
feat(harness): generate and safely apply nine agent configs
```

Wren's UI commit is reviewed on `wren/phase-3-harness`, then squashed into
the phase commit at integration with a `Co-authored-by: Wren` trailer. The
phase branch is merged into `experimental` with `--no-ff`.

---

## 7. Phase 4 — Token-compact context, MCP surface, and skills

**Release:** V2.5
**Depends on:** Phases 1–3
**Risk:** medium — token claims must be measured
**Owner:** Wren (implementation: compressor, MCP, skills, harness, frontend);
Rook (contract review, verification, integration)

### Goal

Add TOON behind an explicit opt-in, a deterministic AST skeleton, a delta
hash, context packs, five new MCP tools, three new MCP resources, and the five
real `SKILL.md` bundles. JSON remains the default. No token-saving claim ships
until a RepoScope-specific benchmark measures compact JSON against TOON with
round-trip fidelity.

Phase 4 is one Wren implementation pass followed by one Rook verification
pass. Wren works on `wren/phase-4-context`, based on the local
`rook/phase-4-context` planning branch. Rook does not edit implementation
files while the claim is active. The owner approves any merge into
`experimental` or `main`.

### Files

- `backend/context_compressor.py` — skeleton, full-body caps, budget,
  deterministic hash, context pack, lazy TOON adapter.
- `backend/skill_library.py` — the five canonical `SKILL.md` bodies and
  validation.
- `backend/api/routers/context.py` — `GET /api/context/pack`.
- `backend/api/__init__.py` — mount the context router.
- `backend/mcp_server/tools.py` and `backend/mcp_server/server.py` — five
  tools and three resources.
- `backend/harness_generator.py` — skill bodies in the registry and skill
  files in preview/apply.
- `backend/tests/test_context_compressor.py`,
  `backend/tests/test_context_api.py`,
  `backend/tests/test_skill_library.py`,
  `backend/tests/test_mcp_v25.py`, and updates to
  `backend/tests/test_mcp_server.py`, `test_harness_generator.py`, and
  `test_harness_api.py`.
- `.claude/skills/*/SKILL.md`, `.agents/skills/*/SKILL.md` — ten checked-in
  copies of the canonical bodies.
- `frontend/src/api/client.ts`,
  `frontend/src/components/harness/SkillsSection.tsx`,
  `frontend/tests/e2e/harness.spec.ts`.
- `benchmarks/toon_benchmark.py`, `docs/MCP.md`,
  `docs/TOON_BENCHMARK.md`, `docs/API.md`, `docs/AGENT_INTEGRATION.md`,
  `docs/FEATURES.md`, `README.md`, `CHANGELOG.md`.
- `pyproject.toml` and `.github/workflows/qa.yml` for the optional TOON
  dependency. Do not add TOON to `backend/requirements.txt`.

### API and tools

```
GET /api/context/pack
  ?paths=<comma-separated repo-relative paths>
  &format=json|toon          (default json)
  &detail=skeleton|full      (default skeleton)
  &budget=8000               (500..200000)
  &since_hash=sha256:...     (optional)
```

New MCP tools:

- `get_mindmap_hierarchy(include_symbols=True, max_nodes=2000)`
- `get_ast_skeleton(file_path, max_symbols=200)`
- `get_context_pack(paths="", detail="skeleton", budget=8000, since_hash=None)`
- `diff_interface_contracts(file_path, patch=None, old_source=None,
  new_source=None, include_consumers=True)`
- `get_ranked_reading_path(max_files=12)`

New MCP resources:

- `reposcope://mindmap`
- `reposcope://api-routes`
- `reposcope://context-pack`

The existing 8 tools and 5 resources keep their names, signatures, and URIs.
The final surface is exactly 13 tools and 8 resources.

### Context-pack contract

The pack is deterministic for the same graph, paths, detail, and budget. It
contains:

- `schema_version`, `available`, `detail`, `budget`;
- ordered `files`, each with `path`, `role`, `pillar`, `route_count`, and
  ordered `symbols`;
- `omitted` with reasons `budget`, `not-indexed`, `ambiguous`, `outside-root`,
  or `unreadable`;
- `caps` with `max-lines` or `max-chars` and the applied limit;
- `truncated`, `counts`, `hash`, `tokens`, `format`, and `root`.

Skeleton mode preserves paths, lines, end lines, roles, kinds, and normalized
signatures; it omits bodies only. Full mode reads source bodies capped at 120
lines and 12,000 characters per symbol and reports every cap.

The hash is SHA-256 over canonical compact JSON with `format`, `since_hash`,
`hash`, `root`, and all token-count fields removed. JSON and TOON therefore
share the same content hash. `tokens.pack` is estimated from the content with
the token fields neutralized, so it is not circular. A matching `since_hash`
returns a compact JSON envelope with `unchanged: true` and no files.

Path safety is part of the contract: absolute paths, drive-qualified paths,
`..` components, and symlink escapes are omitted, never read.

### TOON policy

- `toon-format` is an optional dependency (`[project.optional-dependencies].toon`)
  and is imported lazily, never at module import time.
- `format=toon` returns HTTP 400 with clear install guidance when the package
  is absent.
- `REPOSCOPE_TOON=0` is a kill switch; JSON remains available.
- JSON is the default in every case.
- The benchmark records bytes, estimated tokens, and round-trip equality on
  at least five real repositories with exact commit SHAs. The baseline is
  compact JSON, not pretty-printed JSON.
- No 85% claim ships. If median saving is below 20%, the docs state the
  measured result and TOON remains opt-in. If round-trip fails, the phase
  stops rather than shipping a lossy path.

### Skills

The five IDs are frozen: `blast-radius-guard`, `zero-grep-architect`,
`pr-contract-shield`, `onboarding-navigator`, `dead-code-surgeon`.

Each body is a real 60-100 line workflow with frontmatter, a token budget, a
frozen first tool call, an output contract, and stop conditions. Canonical
bodies live in `backend/skill_library.py`; checked-in copies live in both
`.claude/skills/<id>/SKILL.md` and `.agents/skills/<id>/SKILL.md`. There is no
`.opencode/skills/` copy. `dead-code-surgeon` must state that static
reachability is an estimate, not proof of dead code.

The harness generator returns bodies from `list_skills()` and includes the
five skill files in Claude and Antigravity preview/apply. The other seven
agents are unchanged. Existing force, diff, atomic-write, and path-safety
rules still apply. The Skills panel shows `Ready` and a real body preview.

### Acceptance gate

- [x] 13 MCP tools and 8 resources exactly; all existing names and URIs
      unchanged.
- [x] Context pack is deterministic: same graph + same params → same hash.
- [x] Skeleton mode preserves signatures, paths, lines, and roles; it omits
      bodies only. Full mode caps bodies and reports caps.
- [x] Budget, omissions, unreadable files, and traversal attempts are
      reported safely.
- [x] JSON and TOON share the content hash; `since_hash` returns the compact
      unchanged envelope.
- [x] TOON round-trips on the benchmark corpus; the measured table has at
      least five real repositories and exact commits.
- [x] No 85% claim remains; token numbers are measured.
- [x] Five real skill bodies exist in canonical form and in both checked-in
      locations; frontmatter, allowlist, size, and caveats are tested.
- [x] Harness preview/apply writes skill files for Claude and Antigravity;
      the UI shows `Ready` and previews the body.
- [x] Backend tests, compileall, pip check, frontend build, tsc, harness,
      journeys (J22 excluded locally), mindmap, and `git diff --check` pass.
- [x] No Phase 5+ files, packaging, citation verifier, reverse prompt, or
      security suite are touched.

### Commit

```
feat(context): add skeleton, context packs, TOON flag, and MCP tools
```

Phase 4 is one implementation commit plus a coordination handoff commit. It is
reviewed on a fresh worktree and merged only after owner approval. Rollback is
`git revert <phase-4-commit>`; there is no graph or schema migration.

## 8. Phase 5 — Verified chat citations

**Release:** V2.6
**Depends on:** Phase 1 (exact node paths, lines, end lines)
**Risk:** medium
**Owner:** Rook (verifier, orchestrator); Wren (CitationPill, hover preview)

### Goal

Turn citations from decorative regex chips into verified, structured evidence. The server parses every citation, checks the path and line range against the indexed symbol table, snaps a near miss to the symbol’s real range, and returns `verified`, `confidence`, and the exact snippet. The model writes prose; the AST writes citations.

### Files

`backend/citation_verifier.py`, `backend/orchestrator.py`, `backend/api/routers/chat.py` (or the existing chat path), `backend/tests/test_citation_verifier.py`, `backend/tests/test_chat_citations.py`, `frontend/src/components/CitationPill.tsx`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/api/client.ts`, `frontend/tests/e2e/citations.spec.ts`.

### Contract

The existing `POST /api/chat/stream` event names stay. Add one final event:

```json
{
  "type": "citations",
  "citations": [
    {
      "raw": "[backend/main.py:391-414]",
      "path": "backend/main.py",
      "start_line": 391,
      "end_line": 414,
      "symbol": "health",
      "node_id": "func:backend/main.py:health",
      "verified": true,
      "confidence": 1.0,
      "reason": "exact symbol range",
      "preview": "…15 lines…"
    }
  ]
}
```

`GET /api/citation/verify?path=...&line=...` is a read-only debug endpoint for the UI. It returns the same citation object or a well-formed miss.

### Rules

- A citation to a non-existent path is `verified: false`, never invented.
- A line inside a known symbol with a near-miss start (within 5 lines) snaps to that symbol and records `reason: "snapped"`.
- A range that spans two symbols is split or marked `partial`.
- A citation with no symbol but a valid file line is `verified: true` with the file node and a narrow preview.
- The verifier never calls an LLM.
- The UI must visually distinguish verified and unverified pills; unverified must not look authoritative.

### Acceptance gate

- [ ] The verifier passes exact, snapped, partial, and hallucinated cases.
- [ ] The final SSE event never breaks an old client.
- [ ] Citation clicks expand the mind map and focus the file.
- [ ] Hover previews never read outside the repository root.
- [ ] No raw model text is trusted as a citation without verification.

### Commit

```
feat(citations): verify and snap AST citations
```

---

## 9. Phase 6 — Four-mode reverse-prompt compiler

**Release:** V2.6
**Depends on:** Phase 1 (evidence), Phase 4 (skeleton/context pack), Phase 5 (citation verifier)
**Risk:** high — an unverified blueprint is a hallucination factory
**Owner:** Rook (compiler); Wren (panel)

### Goal

Replace the single generic LLM prompt with a deterministic compiler that can emit four modes from the real graph: full rebuild spec, feature slice, agent spec bundle, and budgeted context pack. The LLM may polish prose only after the structure is assembled and verified.

### Modes

| Mode | Output | Determinism |
|---|---|---|
| `rebuild` | `REBUILD_SPEC.md`: stack, build order, routes, models, env keys, test commands | 100% graph-derived; LLM optional for prose |
| `feature` | A self-contained prompt for a selected node/feature and its 2-hop interface closure | deterministic subgraph + signatures |
| `spec` | `CLAUDE.md`, `AGENTS.md`, `llms.txt`, `.kiro/specs/*` bundle | deterministic templates |
| `context` | Compact/standard/full context pack with token count | deterministic; TOON only if Phase 4 proves it |

### Files

`backend/reverse_prompt.py`, `backend/api/routers/reverse_prompt.py`, `backend/tests/test_reverse_prompt.py`, `frontend/src/components/ReversePromptPanel.tsx`, `frontend/src/api/client.ts`, `docs/REVERSE_PROMPT.md`.

### Contract

`POST /api/reverse-prompt` keeps the existing body and adds optional `mode`, `target_node_id`, `budget`, `format`. Response:

```json
{
  "ok": true,
  "mode": "feature",
  "content": "…",
  "files": [{"path": "REBUILD_SPEC.md", "content": "…"}],
  "tokens": 4210,
  "format": "json",
  "source": {"nodes": 42, "edges": 88, "root": "…"},
  "warnings": []
}
```

Existing `{prompt: "..."}` callers keep working: `mode` defaults to `context`, and `prompt` is the same string as `content`.

### Acceptance gate

- [ ] The same graph and parameters produce byte-identical output; no timestamps inside the content hash.
- [ ] Build order is topological with cycles called out, not hidden.
- [ ] Every route/model/signature in a blueprint exists in the graph.
- [ ] A feature slice includes its 2-hop interface closure and no unrelated files.
- [ ] The token counter is deterministic and within 2% of the context pack.
- [ ] The panel previews, copies, and downloads every mode.

### Commit

```
feat(reverse-prompt): compile four deterministic blueprint modes
```

---

## 10. Phase 7 — Executable multi-file scaffolder

**Release:** V2.6
**Depends on:** Phase 4 (skeleton), Phase 6 (blueprint conventions)
**Risk:** medium — a broken starter kit is a bad first impression
**Owner:** Rook (generator); Wren (file tree preview, zip UX)

### Goal

Generate a runnable 12–20 file starter kit from the analyzed repository’s real stack, with a preview tree, a zip download, and a terminal bootstrap command. Templates are deterministic; the LLM is not allowed to invent the file set.

### Files

`backend/scaffolder.py`, `backend/api/routers/scaffold.py`, `backend/tests/test_scaffolder.py`, `frontend/src/components/ScaffoldPanel.tsx`, `frontend/src/api/client.ts`, `docs/SCAFFOLD.md`.

### Contract

- `POST /api/scaffold` keeps its path. New optional `mode=preview|zip|command`; the default preserves the current response fields.
- Response: `{ok, project_type, files: [{path, content, language}], file_tree, entry_files, warnings, token_estimate}`.
- `POST /api/scaffold/download-zip` streams `application/zip` with a path-safe archive.
- `npx reposcope-mcp scaffold --from <owner/repo> --out ./app` is generated as text, not executed by the backend.

### Rules

- Path traversal is rejected in both generator and zip.
- The kit includes a test file, an `.env.example` with placeholders only, a README, and the chosen harness config + skills.
- No secret is ever copied from `.env`.
- A stack with no template gets a documented generic kit, not a broken one.
- The generated kit is validated by writing it to a temp directory and running the language’s syntax check (`compileall` for Python, `tsc --noEmit` when available).

### Acceptance gate

- [ ] The generated Python kit compiles; the TypeScript kit type-checks when Node is available.
- [ ] Zip round trip preserves the preview exactly.
- [ ] No file escapes the output root.
- [ ] The preview tree is interactive and keyboard accessible.
- [ ] The existing scaffold tests still pass.

### Commit

```
feat(scaffold): generate executable multi-file starter kits
```

## 11. Phase 8 — Four deterministic tour tracks

**Release:** V2.7
**Depends on:** Phase 1 (roles, routes, API edges), Phase 5 (citations)
**Risk:** medium
**Owner:** Wren (tour UI); Rook (generator contract and merge)

### Goal

Replace the single generic BFS tour with four tracks that answer different questions:

1. `request_lifecycle` — browser/CLI entry point → route → handler → service → storage.
2. `data_flow` — a model/table/state node and the code that reads and writes it.
3. `change_impact` — a high-risk file/symbol and the blast radius that depends on it.
4. `onboarding` — the shortest path from an entry point to the core domain concepts.

The LLM writes a short explanation per stop. The stop order, paths, and lines are deterministic.

### Files

`backend/tour_generator.py` (rewrite), `backend/api/routers/tour.py`, `backend/tests/test_tour_tracks.py`, `frontend/src/components/TourPanel.tsx` (rewrite), `frontend/src/api/client.ts`, `frontend/tests/e2e/tour.spec.ts`, `docs/TOURS.md`.

### Contract

`POST /api/tour/generate` keeps its path. Body gains `track`, `target_node_id`, `max_stops`. Response keeps `stops` and adds `track`, `track_label`, `why_this_order`, `source` evidence. `GET /api/tour/export?format=codetour` returns a CodeTour-compatible JSON file.

### Rules

- A track with no valid start returns `available: false` and a reason; it never fabricates a stop.
- Stops are unique; a cycle is cut at the repeated node with a warning.
- Each stop carries `path`, `line`, `end_line`, `role`, `reason`, and `verified` (Phase 5 verifier).
- “Ask about this stop” sends the stop’s exact node/line context, not just its label.

### Acceptance gate

- [ ] All four tracks produce different, deterministic orders on the fixture.
- [ ] Every stop resolves to a real node and line.
- [ ] CodeTour export validates against the schema subset.
- [ ] The tour survives a file edit without referencing a stale line.
- [ ] The existing tour endpoint remains backward compatible.

### Commit

```
feat(tour): add four deterministic guided tracks
```

---

## 12. Phase 9 — Topological student onboarding

**Release:** V2.7
**Depends on:** Phase 1 (roles), Phase 8 (routes/tour ordering)
**Risk:** medium
**Owner:** Wren (curriculum UI); Rook (ranking and verification)

### Goal

Replace hub-first ranking and LLM quizzes with a deterministic curriculum: topological layers over real dependencies, prerequisite chains, and challenges whose answers are verified against the repository, not generated prose.

### Files

`backend/onboarding.py` (rewrite), `backend/api/routers/onboarding.py`, `backend/tests/test_onboarding.py`, `frontend/src/components/StudentModePanel.tsx` (rewrite), `frontend/src/components/OnboardingPath.tsx`, `frontend/tests/e2e/onboarding.spec.ts`, `docs/ONBOARDING.md`.

### Curriculum contract

- Layers are computed by SCC condensation then topological order. A cycle is one layer with an explicit note.
- A lesson is `{id, layer, title, node_ids, reading_order, prerequisite_ids, challenge}`.
- A challenge is one of: locate a symbol, trace a call, identify a route, or explain a boundary. The verifier checks the answer against the graph, not a hidden LLM rubric.
- Progress is stored in `localStorage`; no account, no server-side personal data.
- “Skip ahead” is allowed but shows the prerequisites that were skipped.

### Acceptance gate

- [ ] Every lesson node exists and every prerequisite layer precedes its dependents.
- [ ] Challenges are reproducible and graded by graph evidence.
- [ ] A cycle is displayed as a cycle, not silently flattened.
- [ ] The curriculum is deterministic across runs.
- [ ] Keyboard and screen-reader labels pass the outline journey.

### Commit

```
feat(onboarding): build a verified topological curriculum
```

---

## 13. Phase 10 — Churn, hotspots, bus factor, and the time machine

**Release:** V2.7
**Depends on:** Phase 1 (evidence), Phase 8 (tour ordering)
**Risk:** medium
**Owner:** Rook (metrics engine); Wren (Tracker panel)

### Goal

Extend the event feed into a repository-health view: churn velocity, hotspot score, ownership/bus factor, commit comparison, and a time-machine overlay. Every metric has a named formula and a date window.

### Files

`backend/repo_metrics.py` (new), `backend/git_history.py` (extend), `backend/api/routers/metrics.py`, `backend/tests/test_repo_metrics.py`, `frontend/src/components/TrackerPanel.tsx` (extend), `frontend/src/api/client.ts`, `frontend/tests/e2e/tracker.spec.ts`, `docs/METRICS.md`.

### Metrics

- **Churn:** added + deleted lines per file per window, from `git log --numstat`.
- **Hotspot:** `normalized_churn × normalized_pagerank`, both min-max scaled; the formula is shown in the API and UI.
- **Bus factor:** the smallest number of authors whose combined line ownership exceeds 50% of a file; ownership is attributed by `git blame` or a documented fallback when blame is unavailable.
- **Time machine:** a commit SHA / date selects a graph snapshot; the diff is node/edge-level, not file-only.
- **Release notes:** commits between two refs grouped by conventional-commit type and affected pillar.

### Contract

- `GET /api/metrics/summary?window_days=90`
- `GET /api/metrics/files?metric=hotspot&limit=20`
- `GET /api/metrics/compare?base=<sha>&head=<sha>`
- `GET /api/metrics/release-notes?from=<ref>&to=<ref>`

All endpoints return `available: false` with a reason when the repository has no git history. They never fail the whole panel.

### Acceptance gate

- [ ] Metrics are computed from git, not from an LLM.
- [ ] Formula and window are present in every response.
- [ ] A repository with one author reports bus factor 1, not an error.
- [ ] The time machine can select a commit and show the node/edge delta.
- [ ] No history command runs outside the loaded repository root.

### Commit

```
feat(metrics): add churn, hotspots, bus factor, and history compare
```

---

## 14. Phase 11 — Symbol-level PR impact

**Release:** V2.7
**Depends on:** Phase 1 (symbols, routes, api_calls), Phase 5 (ranges)
**Risk:** high — this is a release gate
**Owner:** Rook (engine, CI gate); Wren (PR panel)

### Goal

Replace the 25-file cap and file-level risk with a symbol-level contract diff: removed/changed signatures, removed exports, changed routes, broken cross-stack callers, and missing tests. Keep the existing endpoint and add the deeper fields.

### Files

`backend/pr_impact.py` (rewrite), `backend/impact_analyzer.py` (extend), `backend/api/routers/pr_impact.py`, `backend/tests/test_pr_impact_symbols.py`, `backend/tests/test_pr_impact_api.py`, `frontend/src/components/PRImpactPanel.tsx`, `frontend/src/api/client.ts`, `docs/PR_IMPACT.md`, `.github/workflows/qa.yml` (optional CI gate).

### Contract

`POST /api/impact/pr` keeps its path. Additive fields:

```json
{
  "schema_version": 2,
  "base": "main",
  "head": "feature",
  "files_analyzed": 132,
  "truncated": false,
  "breaking": [
    {
      "kind": "signature_changed",
      "node_id": "func:backend/main.py:chat",
      "path": "backend/main.py",
      "old_signature": "chat(req: ChatReq)",
      "new_signature": "chat(req: ChatReq, model: str)",
      "callers": [{"node_id": "…", "path": "…", "line": 42, "verified": true}],
      "missing_tests": ["backend/tests/test_chat.py"]
    }
  ],
  "api_contracts": {"added": [], "removed": [], "changed": []},
  "test_gaps": [],
  "risk": {"score": 7.4, "band": "high", "breakdown": []}
}
```

### Rules

- Remove `MAX_FILES_ANALYZED = 25`. Use a time/byte budget instead; if the budget is exceeded, return `truncated: true` with the exact cutoff and never claim completeness.
- A breaking change requires evidence: an old/new signature, a removed node, or a changed route.
- A test gap is a heuristic with a reason, not a certainty.
- CI can run the endpoint in report-only mode first; blocking mode is opt-in per repository.
- Private code never leaves the machine; the diff and graph are local.

### Acceptance gate

- [ ] A fixture PR that changes a function signature reports every caller, including a frontend `api_calls` caller.
- [ ] A removed route is reported as an API contract break.
- [ ] The 25-file cap is gone; budget truncation is explicit.
- [ ] The SARIF/JSON report is stable and path-safe.
- [ ] Existing PR-bot tests pass.

### Commit

```
feat(pr-impact): analyze symbol-level contract breaks without a file cap
```

---

## 15. Phase 12 — Explainable impact simulator

**Release:** V2.7
**Depends on:** Phase 11 (symbol-level diff), Phase 1 (api_calls, inherits)
**Risk:** medium
**Owner:** Wren (simulator UI); Rook (scoring contract)

### Goal

Turn “what breaks?” into a three-hop, scored, explainable simulation. The user selects a file, symbol, or route; the engine returns direct and transitive impact with the exact paths that explain each hop, plus a score breakdown.

### Files

`backend/impact_analyzer.py` (extend), `backend/api/routers/impact.py`, `backend/tests/test_impact_simulator.py`, `frontend/src/components/ImpactPanel.tsx` (extend), `frontend/src/api/client.ts`, `frontend/tests/e2e/impact.spec.ts`, `docs/IMPACT.md`.

### Score

`score = min(10, 2.0*breaking + 1.0*direct + 0.5*transitive + 0.5*api_boundary + 0.5*test_gap - 0.5*covered)`

The coefficients, the inputs, and every contributing node are returned. The score is deterministic; the LLM writes at most a narrative, clearly labelled as commentary.

### Contract

`POST /api/impact/analyze` keeps its path and adds `hops`, `paths`, `score_breakdown`, `api_boundaries`, `test_gaps`, and `explanation_ids`. A hop is `{from, to, edge_type, evidence}`.

### Acceptance gate

- [ ] Direct/transitive sets are correct on a hand-built fixture.
- [ ] Every path is a real graph path; no edge is invented.
- [ ] The score breakdown sums to the score.
- [ ] Three hops are enforced and documented; no unbounded BFS.
- [ ] The panel shows why a node is included and lets the user open it.

### Commit

```
feat(impact): add a three-hop explainable impact simulator
```

## 16. Phase 13 — Six-engine graph-contextual security suite

**Release:** V2.8
**Depends on:** Phase 1 (cross-file calls, routes), Phase 11 (symbol/contract diffs), Phase 10 (history)
**Risk:** high — false positives destroy trust
**Owner:** Rook (engines, scoring, SARIF); Wren (security panel, adversarial tests)

### Goal

Replace regex-only security with six deterministic engines that use the graph, a scorecard, auto-patch diffs, and SARIF 2.1.0. Consolidate the source draft’s V2.7 security scope here; there is no second security rewrite.

### The six engines

1. **Secrets** — entropy + known-pattern scan, excluding fixtures and lockfiles; evidence includes path/line/matched rule, never the secret value.
2. **Dependencies** — parse lockfiles/manifests, query OSV only when the network is allowed, cache the result; offline mode returns “not checked”, not “clean”.
3. **Taint** — cross-file source → sink propagation using `imports`, `calls`, `api_calls`; same-file behavior is preserved; every path is shown.
4. **AI/MCP audit** — prompt-injection surfaces, tool-permission overreach, unpinned/unsafe MCP configs, secrets in agent configs, and risky `npx`/`uvx` launchers.
5. **Auth/CORS/session** — route auth coverage, permissive CORS, missing rate limits, cookie flags, and unauthenticated state changes, mapped to real handlers.
6. **Architecture/CI** — layer violations, cycles, unreachable dangerous code, and unsafe workflow permissions, using the same `arch_rules` taxonomy.

### Files

`backend/security/` (new package: `__init__.py`, `models.py`, `secrets_engine.py`, `dependency_engine.py`, `taint_engine.py`, `ai_mcp_engine.py`, `auth_engine.py`, `architecture_engine.py`, `scoring.py`, `sarif.py`, `patcher.py`), `backend/api/routers/security.py`, `backend/tests/test_security_engines.py`, `backend/tests/test_security_sarif.py`, `backend/tests/test_security_patch.py`, `frontend/src/components/SecurityPanel.tsx` (rewrite), `frontend/tests/e2e/security.spec.ts`, `docs/SECURITY.md`, `docs/SARIF.md`.

### Contract

- `POST /api/security/scan` keeps its path; body gains `engines`, `min_severity`, `offline`, `include_patches`.
- Response: `{schema_version, available, scorecard, findings, engines, generated_at, limits}`.
- Finding: `{id, engine, severity, confidence, title, path, line, end_line, node_id, evidence, remediation, patch?}`.
- `GET /api/security/sarif?scan_id=...` returns SARIF 2.1.0 with `runs[0].tool.driver.rules`.
- `POST /api/security/patch` returns a unified diff; it never writes to the repository.
- Finding IDs are deterministic hashes of `(engine, path, line, rule)` so a re-scan is comparable.

### Rules

- No secret value in logs, responses, SARIF, or the UI.
- Offline mode is explicit: dependency checks show `skipped`, not `passed`.
- Each engine returns `available` + `reason` independently.
- A patch is a suggestion, never auto-applied.
- A finding without evidence is dropped before scoring.
- The scorecard formula is published: severity weights, confidence weighting, and a cap per file.

### Acceptance gate

- [ ] Every engine has positive and negative fixtures.
- [ ] Cross-file taint finds a path that the old same-file scanner missed.
- [ ] OSV is never called in tests; the cache/offline path is tested.
- [ ] SARIF validates against the 2.1.0 schema and points at real lines.
- [ ] Patch diffs apply to a temp copy and pass the language syntax check.
- [ ] The scorecard is deterministic and explainable.
- [ ] No P1 false positive on the repository’s own fixtures.

### Commit

```
feat(security): add six graph-contextual security engines
```

---

## 17. Phase 14 — Hardening, packaging, and release

**Release:** V2.8 / release train
**Depends on:** Phases 0–13
**Risk:** medium
**Owner:** Rook; Wren runs adversarial verification

### Goal

Make the release reproducible: one version source, clean packages, cross-platform checks, documentation, performance budgets, and a tested rollback. No new feature scope.

### Work

- Add `backend/version.py` as the single version source; make `/api/health`, CLI, SARIF, and package metadata agree.
- Publish `reposcope-ai` as a thin metapackage; keep the PyPI `reposcope` package.
- Add `packages/reposcope-mcp/` as a launcher/configurator that delegates to Python; never parse code in Node.
- Add `CHANGELOG.md` entries, migration notes, `docs/FEATURES.md` limits, and `docs/KNOWN_LIMITS.md`.
- Run the full matrix: Python 3.11/3.12, Node 20, Windows + Linux, extension compile/test, frontend build, Playwright journeys.
- Add performance budgets: graph build on the RepoScope repository, mind-map render, PageRank, security scan, and context pack. Record the numbers.
- Add a release checklist and a rollback rehearsal.
- Verify `main` is untouched; tag `experimental` as `v2.5.0-rc.1` only when the owner approves.

### Acceptance gate

- [ ] One version source; no drift between API, CLI, SARIF, and package.
- [ ] Clean install from the packaged artifacts, not the checkout.
- [ ] All L1/L2/L3 gates green on both operating systems.
- [ ] Performance budgets recorded with hardware and repository size.
- [ ] `docs/QA_REPORT.md` reflects the final numbers.
- [ ] The owner has tested `experimental` and approved the merge.

### Commit

```
chore(release): harden, package, and verify the v2.5–v2.8 train
```

---

# Appendices

## Appendix A — File ownership matrix

| Area | Rook | Wren |
|---|---|---|
| Graph schema, resolver, store, parser facts | owner | read-only |
| Mind-map API contract | owner | consumer |
| Mind-map components and layout | review | owner |
| Harness API and safety | owner | registry/fixtures/UI |
| Phase 4 TOON/context compressor, MCP surface, skill bodies | verify and integrate | owner (implementation) |
| Citation verifier | owner | UI |
| Reverse prompt/scaffolder | owner | UI |
| Tour/onboarding/metrics/impact/security UI | review | owner |
| CI, packaging, merges, release tags | owner | read-only |
| Adversarial verification | review | owner |

One writer per file at a time. A claim is recorded in the work MD before editing. The integrator can reassign a file, but not silently edit a claimed file.

## Appendix B — Compatibility checklist for every phase

- v1 node ids unchanged: `file:<rel>`, `func:<rel>:<name>`, `class:<rel>:<name>`.
- v1 edge meanings unchanged: `contains`, `imports`, `calls`.
- Existing endpoint paths and keys unchanged; new keys additive.
- Existing MCP tool names and resource URIs unchanged.
- Browser preview remains labelled as a preview.
- Local mode performs no outbound request.
- Extension remains HTTP-only.
- Provider chain remains Groq → OpenRouter → NVIDIA NIM + BYOK; no Nebius.
- TOON is opt-in until benchmarked.
- Deterministic graph evidence is the source of truth.

## Appendix C — API surface added by this plan

| Phase | Method | Path | Purpose |
|---|---|---|---|
| 1 | GET | `/api/mindmap` | Frozen hierarchical mind-map payload. |
| 3 | GET | `/api/harness/agents` | Nine-agent registry. |
| 3 | GET | `/api/harness/config` | Preview config files. |
| 3 | POST | `/api/harness/apply` | Safe preview/apply. |
| 4 | GET | `/api/context/pack` | Budgeted context pack. |
| 5 | GET | `/api/citation/verify` | Verify one citation. |
| 6 | POST | `/api/reverse-prompt` | Existing path, four modes. |
| 7 | POST | `/api/scaffold/download-zip` | Starter kit archive. |
| 8 | GET | `/api/tour/export` | CodeTour export. |
| 10 | GET | `/api/metrics/*` | Churn, hotspots, compare, release notes. |
| 11 | POST | `/api/impact/pr` | Existing path, symbol-level report. |
| 12 | POST | `/api/impact/analyze` | Existing path, explainable hops. |
| 13 | GET | `/api/security/sarif` | SARIF 2.1.0. |
| 13 | POST | `/api/security/patch` | Suggested unified diff. |

## Appendix D — MCP surface policy

Existing tools keep their names: `get_architecture_overview`, `calculate_blast_radius`, `get_dependency_lineage`, `explain_architectural_rule`, `get_repo_map`, `find_dependency_cycles`, `get_hotspots`, `find_unreachable_symbols`.

New tools are additive: `get_mindmap_hierarchy`, `get_ast_skeleton`, `get_context_pack`, `diff_interface_contracts`, `get_ranked_reading_path`, `run_security_scan`.

Existing resources keep their URIs. New resources: `reposcope://mindmap`, `reposcope://api-routes`, `reposcope://context-pack`.

Every tool response carries `path` and `line` where applicable. A tool that cannot answer says so; it does not return an empty success that looks like a fact.

## Appendix E — Nine-agent paths (verified 2026-10-26)

| Agent | Project config | Notes |
|---|---|---|
| Claude Code | `.mcp.json` | `claude mcp add` preview. |
| Cursor | `.cursor/mcp.json` | `.cursor/rules/reposcope.mdc`. |
| VS Code / Copilot | `.vscode/mcp.json` | `servers` key; portable `.mcp.json`. |
| Codex CLI | `.codex/config.toml` | `[mcp_servers.reposcope]`. |
| Kiro | `.kiro/settings/mcp.json` | `.kiro/steering/reposcope.md`. |
| Antigravity | `.agents/mcp_config.json` | `.agents/skills/`; dogfood against RepoScope. |
| Windsurf / Devin | `.devin/mcp_config.json` | Global `~/.codeium/windsurf/mcp_config.json` and `~/.config/devin/mcp_config.json` shown, never written. |
| Cline / Roo | `.roo/mcp.json` | Cline global preview `~/.cline/data/settings/cline_mcp_settings.json`. |
| OpenCode | `opencode.json` | `mcp.reposcope`; current schema is `mcp.<name>` with `type: local \| remote`. No Zed target. |

## Appendix F — Phase gate test matrix

| Gate | Command | Required |
|---|---|---|
| L1 | `python -m pytest -q` | 0 failures on 3.11 and 3.12 |
| Compile | `python -m compileall -q backend/` | exit 0 |
| Deps | `python -m pip check` | no broken requirements |
| Frontend | `npm --prefix frontend run build` | exit 0 |
| Extension | `npm --prefix extensions/vscode run compile && npm test` | exit 0 |
| L2 | live `/health`, `/api/health`, `/api/mindmap`, phase endpoints | exact assertions |
| L3 | Playwright journeys | no console errors, no blank canvas |
| Packaging | `npm pack --dry-run`, `python -m build` | installable artifacts |

## Appendix G — Feature flags and rollback

- `REPOSCOPE_TOON=0` — disable the opt-in `format=toon` path; JSON is the default and is always available.
- `REPOSCOPE_MINDMAP=1` — expose the mind-map mode; default on after Phase 2, off if the gate fails.
- `REPOSCOPE_SECURITY_ENGINES` — comma-separated allowlist; default all six.
- `REPOSCOPE_HARNESS_APPLY=1` — enable writes; preview is always available.
- Every phase is one commit. Rollback is `git revert <phase-commit>` on `experimental`, never a force-push.
- A schema change is rolled back by restoring the previous `SCHEMA_VERSION` and keeping the additive fields readable; never delete user graph files.

## Appendix H — Coordination protocol

1. **Two worktrees, one integration branch.** `experimental` is the only shared branch. Each agent works on a short-lived child branch and merges into `experimental` when the phase gate is green. `main` is merged only by the owner.
2. **One writer per file.** Claim the file in the work MD before editing. If a file is claimed, do not edit it; send a handoff instead.
3. **Contract first.** The integrator publishes the schema/API before implementation. A consumer does not infer the contract from code.
4. **Small handoffs.** A handoff includes: branch, commit, files changed, tests run, known limits, and the next open decision.
5. **The MD is a record.** Git commits and tests are authoritative. If the MD and the code disagree, the code wins and the MD is corrected.
6. **No force-push, no rebase of shared branches, no simultaneous edits.**
7. **Independent verification.** The reviewer runs the gate on a clean checkout; the author does not self-certify a merge.
8. **Names.** The coordination files use only the aliases Rook and Wren. Do not expose the underlying harness names.

The working files are `docs/coordination/README.md` (rules), `DIALOGUE.md` (conversation and handoffs), `ROOK.md` (Rook claims/results), and `WREN.md` (Wren claims/results).

## Appendix I — Source-draft corrections

| Source draft claim | Correction |
|---|---|
| Target `RepoScope-V2` | Stay in `adityapatel5912/RepoScope`. |
| `KnowledgeGraphView.tsx` | The real file is `GraphView.tsx`; the mind map is a separate `MindMapView.tsx`. |
| Zed is a target | Zed is replaced by OpenCode. |
| `.claude/mcp.json` | Claude Code uses project `.mcp.json`. |
| `.github/mcp.json` for Copilot | Use `.vscode/mcp.json` with `servers`, plus portable `.mcp.json`. |
| Standalone VS Code scanner | Rejected; the extension remains an HTTP client. |
| Replace `mcp_client.py` | It is the GitHub client; the MCP server lives in `backend/mcp_server/`. |
| TOON default with 85% savings | Unverified. JSON stays default until a RepoScope benchmark proves it. |
| Nebius routing | Not added; the provider chain stays Groq → OpenRouter → NVIDIA NIM + BYOK. |
| “9 failing tests” | The reproduced CI baseline was 30 failed / 305 passed on Python 3.11 with the declared requirements. |
| Rewrite the security feature twice | Consolidated into the six-engine Phase 13. |

## Appendix J — Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Graph v2 changes a v1 edge | medium | high | Golden v1 subset test; one-writer rule; incremental parity. |
| API linker creates false edges | medium | high | Conservative matching, confidence evidence, no-guess rule, negative tests. |
| Two agents edit one file | medium | high | Claims, worktrees, integrator merge, no force-push. |
| TOON is slower or lossy | medium | medium | Opt-in flag, benchmark, round-trip test. |
| Security false positives | high | high | Evidence required, confidence, allowlist, offline labels. |
| Frontend bundle grows | medium | medium | Lazy-load the mind map; measure bundle size. |
| CI time grows | medium | medium | Cache deps, separate jobs, nightly journeys. |
| Packaging drifts from source | medium | high | One version source, build-from-artifact test. |
| Agent config paths go stale | high | medium | Re-verify at Phase 3 kickoff; fixture tests; `verified_at`. |

## Appendix K — Definition of done (one line)

A phase is done when the gate is green on a clean checkout, the contract is documented, the user-visible surface is tested, the rollback is understood, and the commit is the only change in that phase.




