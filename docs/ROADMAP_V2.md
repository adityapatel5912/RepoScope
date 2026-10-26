# RepoScope v2.0 — Technical Architecture Upgrade & Feature Enhancement Plan

- **Target:** v2.0.0 Architecture & Multi-Platform Ecosystem
- **Repository:** adityapatel5912/RepoScope
- **Audience:** Engineering Team & Technical Autonomous Agents
- **Context:** IBM Bob 2.0 Hackathon
- **Date:** October 2026
- **Status:** Approved — full 6-milestone scope, including VS Code/Cursor extension + IDE protocol links
- **Revision 2:** Part II added after a competitive audit — four new milestones (M7–M10), a
  sharpening list, and a revised sprint plan

---

## 0. How to read this document

This plan was written **after auditing the existing codebase**, not from the feature wish-list alone.
Every "current state" claim below was verified against the source. Section 1 records the audit
baseline; Section 2 records **ten corrections** to the original v2.0 specification that must be
applied before any code is written.

**Rule for autonomous agents:** Section 2 is binding. Do not implement the original spec's wording
where it conflicts with Section 2.

**Structure.**

| Part | Sections | Contents |
|---|---|---|
| **I** | 1–10 | Audit, corrections, architecture, milestones M1–M6, sprints, agent prompts, risks |
| **II** | 11–16 | Competitive audit, strategic wedge, new milestones M7–M10, sharpening items, revised sprints |

**The one-paragraph summary of the whole plan:** RepoScope already has the hard part — a working
AST-derived architecture graph with an interactive canvas. This plan makes that graph *accurate*
(Tree-sitter instead of regex), makes it *reachable* (local CLI, IDE deep links, VS Code
extension), makes it *agent-usable* (an MCP server over the same index), makes it *governable*
(architecture-as-code, cycle and contract checks in PRs), and makes it *defensible* (PageRank
ranking, published token-reduction and accuracy benchmarks). The strategic bet is that the human-
facing map is the moat and the MCP server is the distribution channel — every 2026 competitor
picked one side of that line; RepoScope takes both.

---

## 1. Audit baseline (verified 2026-10-20)

### 1.1 Repository shape

| Area | Reality |
|---|---|
| Backend | FastAPI, `backend/main.py` = **1,115 lines**, 25 modules, 8 test files |
| Frontend | React 18 + Vite + TS, `frontend/src/` = 40 files, `GraphView.tsx` ≈ 1,040 lines |
| Tests | `pytest` → **38 passed** in 4.67s |
| Graph engine | `backend/graph_builder.py` (214 lines) |
| Graph traversal | `backend/graph_utils.py` (64 lines) |
| Blast radius | `backend/impact_analyzer.py` (121 lines) |
| PR bot | `backend/pr_impact.py` (246 lines) |
| Security/breaking | `backend/security_scanner.py` (~370 lines) |
| MCP | `backend/mcp_client.py` (71 lines) — **client only** |
| CI | `.github/workflows/pr-impact.yml` — posts the impact comment on every PR |
| Docs | 20 files in `docs/`, incl. `FEATURES.md`, `ARCHITECTURE.md`, `BOB_SESSIONS.md` |

### 1.2 What already exists (do not rebuild)

| Capability | Location | Status |
|---|---|---|
| 7-rank connectivity pyramid (repo → 5 rows → function children) | `frontend/src/components/graph/LayerNode.tsx:37` `RANK_CONFIGS` | ✅ Works |
| 5-layer architecture classification | `frontend/src/components/graph/layerClassifier.ts` | ✅ Works, **frontend-only** |
| Viewport virtualization | `frontend/src/components/GraphView.tsx:986` `onlyRenderVisibleElements` | ✅ Already set |
| **`calls` edge type already accepted by the renderer** | `frontend/src/components/GraphView.tsx:174` | ✅ **Pre-wired** |
| Reverse-BFS blast radius | `backend/impact_analyzer.py:15` | ✅ Works |
| BFS lineage traversal | `backend/graph_utils.py:48` `bfs_traverse` | ✅ Works |
| BYOK + multi-key rotation | `backend/key_rotator.py`, `backend/runtime_config.py` | ✅ Works |
| SSE streaming | `backend/main.py:1047` `/api/chat/stream` | ✅ Works |
| Security scan (secrets / breaking / CVE) | `backend/security_scanner.py` | ✅ Works |
| Breaking-change detection in patches | `backend/security_scanner.py:139` `detect_breaking_in_patch` | ✅ **Regex-based, must be upgraded** |
| Student onboarding, voice tours, scaffold, reverse-prompt | `backend/onboarding.py`, `ts_service.py`, etc. | ✅ Work |

### 1.3 Verified gaps (the real work)

| Gap | Evidence |
|---|---|
| JS/TS parsed by regex, not AST | `backend/graph_builder.py:184-214` |
| JS/TS nodes carry **no line number** | `backend/graph_builder.py:201` — node dict has no `line` key |
| **No call graph at all** — only `imports` + `contains` edges | `backend/graph_builder.py:158,175,180` |
| No symbol resolution across files | `backend/graph_builder.py` resolves *modules* only |
| Git history is never read | `backend/repo_tracker.py` is JSON state for GitHub metadata, no `git` calls |
| `codebase-memory-mcp` binary is **not installed** | `Get-Command codebase-memory-mcp` → not found; `backend/mcp_client.py:22` silently returns `{}` |
| Layer rules not available to the backend | no `layer`/`classify` equivalent in `backend/*.py` |
| No local-directory ingest | `backend/repo_loader.py:48` `load_repo()` only accepts GitHub URLs |
| No CLI, no MCP server, no IDE links, no extension | — |

### 1.4 Dependency status (measured, 2026-10-20)

```
ALREADY INSTALLED — zero new dependency friction:
  mcp 1.29.0 · fastmcp 3.4.7 · tree-sitter 0.25.2
  tree-sitter-python 0.25.0 · tree-sitter-javascript 0.25.0
  tree-sitter-typescript 0.23.2 · tree-sitter-go 0.25.0 · tree-sitter-rust 0.24.2
  typer 0.27.2 · watchdog 6.0.0 · gitpython 3.1.57
  Python 3.14.6 · Node v24.18.0

NOT INSTALLED:
  kuzu (0.11.3 on PyPI) — native wheels lag Python 3.14  → see Correction C7
  sqlite3 — stdlib, no install needed
```

### 1.5 Verified API contracts (both were breaking-change traps)

**tree-sitter 0.25 changed its query API.** `Query.captures()` no longer exists.

```python
# ✅ CORRECT for tree-sitter >= 0.25
from tree_sitter import Language, Parser, Query, QueryCursor
lang  = Language(tree_sitter_python.language())
tree  = Parser(lang).parse(source_bytes)
caps  = QueryCursor(Query(lang, QUERY)).captures(tree.root_node)
# caps is dict[str, list[Node]]
for name, nodes in caps.items():
    for n in nodes:
        print(name, n.text.decode(), n.start_point[0] + 1)

# ❌ WRONG — raises AttributeError on 0.25.x
Query(lang, QUERY).captures(tree.root_node)
```

**MCP SSE transport is deprecated.** Deprecated since spec rev `2025-03-26`; the `2026-07-28`
revision made the transport stateless and removed `Mcp-Session-Id`. `FastMCP.run()` still accepts
`transport="sse"` but it is legacy.

```python
mcp.run(transport="stdio")            # ✅ local  — Claude Desktop, Cursor, Claude Code
mcp.run(transport="streamable-http")  # ✅ remote — containers, hosted
mcp.run(transport="sse")              # ❌ deprecated — do not use
```

---

## 2. Ten corrections to the original specification — BINDING

| # | Original spec says | Correction | Rationale |
|---|---|---|---|
| **C1** | MCP transports: "Stdio **and SSE**" | **stdio + Streamable HTTP.** Drop SSE. | SSE deprecated since 2025-03-26; spec 2026-07-28 made the transport stateless. |
| **C2** | "Compute Git churn heatmap in `backend/repo_tracker.py`" | New module **`backend/git_history.py`**. | `repo_tracker.py` is JSON state for GitHub metadata; it contains zero git calls and no `subprocess`. Putting churn there conflates two unrelated concerns. |
| **C3** | Milestone 5.1 "introduces" breaking-change detection | **Upgrade the existing `security_scanner.detect_breaking_in_patch` (regex) to tree-sitter, then have `pr_impact.py` consume it.** | `security_scanner.py:139` already detects breaking signatures. Two divergent detectors = wrong risk scores and duplicate PR noise. |
| **C4** | Milestone 1.4 "Implement `onlyRenderVisibleElements={true}`" | **Already done** (`GraphView.tsx:986`). Remaining work = LOD label/edge culling below zoom 0.4 + optional WebGL tier. | Don't re-apply existing work; scope the milestone to what's missing. |
| **C5** | Milestone 1.2 "Replace flat single-layer layouts" | The pyramid + 5 layers **already exist**. Real gap = **collapsible semantic clustering** (grouping nodes into collapsible domain clusters), not a first hierarchy. | Avoids re-implementing a working feature. |
| **C6** | `explain_architectural_rule` MCP tool | Requires **new `backend/arch_rules.py`** as the single source of truth, ported from `layerClassifier.ts`, plus `GET /api/arch/rules`. | The 5-layer rules exist **only in frontend TypeScript**. Without this, the MCP server and the UI will disagree about what "client" or "storage" means. |
| **C7** | Milestone 6.1 "Integrate Kùzu" | Use **`sqlite3` (stdlib)**, or `kuzu` behind a feature flag with a graceful fallback. | Kùzu native wheels lag Python 3.14. A failed native install during a demo is fatal; stdlib sqlite is zero-risk. |
| **C8** | Milestone 2.3 "parse AST in-browser via Tree-sitter WASM" | **Ship as an optional, clearly-labelled experimental path** (`?engine=wasm`), built **last** in the milestone. | A second parser implementation in WASM ≈ 2× the cost of the native one, for the narrowest user segment. |
| **C9** | New endpoints appended to `main.py` | Create **`backend/api/`** router package (`routers/local.py`, `routers/mcp_info.py`, `routers/pr_chat.py`, …) and mount from `main.py`. | `main.py` is already 1,115 lines; 6 milestones of endpoints would make it unmaintainable. |
| **C10** | "Replace regex parsing in `graph_builder.py`" | **Preserve the public contract**: `build_graph_from_repo(root) -> {nodes, edges, summary}`, node ids `file:{rel}` / `func:{rel}:{name}` / `class:{rel}:{name}`, edge types `contains` / `imports` (+ new `calls`). | `pr_impact.py`, `find_node_by_label`, the pyramid ranking, and `GraphView.tsx:174` all depend on these shapes. |

### 2.1 Additional required change (not a correction, an addition)

**C11 — `GraphStore` abstraction, pulled forward from Milestone 6 into Sprint 0.**

The original architecture draws MCP as a separate box pointing at the Core Engine. That produces
three independent implementations of "parse the repo." The stronger design is **one index, three
front-ends**:

```
 ┌─────────────────────────────────────────────┐
 │            GraphStore (interface)           │
 │  parse → symbols → calls → edges → persist  │
 └──────────────────┬──────────────────────────┘
        ┌───────────┼───────────┐
   Web App      CLI Daemon    MCP Server
  (REST/SSE)    (localhost)  (stdio / HTTP)
```

The interface is the enabling abstraction for Milestones 2, 3, 4, and 6. Ship `JsonGraphStore`
first (simple, zero risk); add `SqliteGraphStore` in Milestone 6.

---

## 3. Target architecture

```
+-----------------------------------------------------------------------------------+
|                                Client Interfaces                                  |
|  [Web App (React/Vite)]   [VS Code / Cursor Extension]   [MCP Clients]            |
+------------------------------------+---------------------------------------------+
                     | REST / SSE                        | stdio / Streamable HTTP
                     v                                   v
+-----------------------------------------------------------------------------------+
|                       RepoScope Core Engine (FastAPI / CLI)                     |
|                                                                                   |
|  +------------------+  +------------------+  +--------------------------------+   |
|  | Ingestion Engine |  | Polyglot Parser  |  | Intelligence & Analysis         |   |
|  | - GitHub PAT     |  | Tree-sitter      |  | - Transitive Impact Radius     |   |
|  | - Local FS (CLI) |  | Python/TS/JS/Go/ |  | - Cyclic Dep Detection         |   |
|  | - Browser FS API |  | Rust + symbol    |  | - Git Churn & Hotspots         |   |
|  |                  |  | resolution       |  | - API Contract Diffing         |   |
|  +------------------+  +------------------+  +--------------------------------+   |
|                                                                                   |
|  +--------------------------------------------------------------------------+   |
|  | GraphStore: JsonGraphStore → SqliteGraphStore | ArchRules | LRU cache      |   |
|  +--------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
                                     |
                     v
        External AI Providers & GitHub API
        [OpenRouter / Groq / NVIDIA NIM / Anthropic / GitHub Actions]
```

**Module map after v2.0**

```
backend/
  api/                    # NEW — router package (Correction C9)
    __init__.py  local.py  arch.py  pr_chat.py  graph_store.py
  parsers/                # NEW — Milestone 1.1
    __init__.py  base.py  registry.py
    python.py  javascript.py  typescript.py  go.py  rust.py
  graph_store.py          # NEW — GraphStore interface + JsonGraphStore (C11)
  arch_rules.py           # NEW — shared layer taxonomy + edge policy (C6)
  git_history.py          # NEW — churn / co-change (C2)
  contract_diff.py        # NEW — AST signature diff (M5.1, consumes security_scanner)
  watcher.py              # NEW — watchdog live re-index (M2.2)
  mcp_server/             # NEW — Milestone 3
    __init__.py  server.py  tools.py  resources.py  tests/
  graph_builder.py        # MODIFIED — tree-sitter backed, contract preserved (C10)
  graph_utils.py          # MODIFIED — + symbol adjacency, cycle detection
  impact_analyzer.py      # MODIFIED — symbol-level blast radius
  pr_impact.py            # MODIFIED — consume contract_diff
  security_scanner.py     # MODIFIED — tree-sitter breaking detection (C3)
  repo_tracker.py         # UNCHANGED — metadata state only (C2)
  repo_loader.py          # MODIFIED — + load_local_repo()
  main.py                 # MODIFIED — mount routers, keep thin
cli/                      # NEW — Milestone 2.2
  __init__.py  main.py
extensions/vscode/        # NEW — Milestone 4
```

---

## 4. Milestone specifications

### Milestone 1 — Graph Engine & Visualization Modernization

#### 1.1 Polyglot Parsing with Tree-sitter  *(Sprint 1)*

**Problem.** `graph_builder.py` uses `ast` for Python (adequate) and regex for JS/TS (`:184-214`).
Regex misses multiline imports, `import * as X`, re-exports (`export { default } from`), dynamic
`import()`, and produces **no line numbers** for JS/TS — which blocks precise IDE deep links.

**Implementation.**

1. `backend/parsers/base.py` — a `LanguageParser` Protocol:
   ```python
   class LanguageParser(Protocol):
       extensions: tuple[str, ...]
       def extract(self, source: bytes, rel_path: str) -> ParseResult: ...
   ```
   `ParseResult` carries `symbols[]`, `imports[]`, `calls[]`, `exports[]`, `complexity{}`.
2. `backend/parsers/registry.py` — extension → parser map, with a **graceful fallback to the
   current regex JS/TS parser** when a grammar fails to load, so a broken grammar can never take
   the app down.
3. Per-language query files using the 0.25 API (`QueryCursor(...).captures(...)`):
   - Python — `function_definition`, `class_definition`, `import_statement`,
     `import_from_statement`, `call`
   - TypeScript / JavaScript — `function_declaration`, `class_declaration`,
     `interface_declaration`, `type_alias_declaration`, `lexical_declaration` (arrow fns),
     `import_statement`, `export_statement`, `call_expression`
   - Go — `function_declaration`, `method_declaration`, `type_declaration`, `import_declaration`
   - Rust — `function_item`, `struct_item`, `impl_item`, `mod_item`, `use_declaration`
4. **Symbol resolution.** Build a global symbol table `name -> [(file, line, kind, scope)]`.
   Resolve a call site in this order: same file → same module/package → explicitly imported
   module → unique global match. Unresolved calls become `external` nodes (not dropped) so the
   graph shows "this calls something we can't see."
5. **Cyclomatic complexity** per function (count decision nodes) and **token weight** per file.
6. **Emit `calls` edges** — the renderer already accepts them (`GraphView.tsx:174`).

**Constraints (C10).** Node/edge shapes and id scheme unchanged. `build_graph_from_repo()` keeps
its signature. `contains` and `imports` edge semantics unchanged. New `calls` type added.

**Acceptance.**
- [ ] `build_graph_from_repo()` on a TS/Go/Rust fixture emits `calls` edges and line numbers.
- [ ] Node ids for the same fixture are byte-identical to the pre-refactor ids
      (enforced by a **golden-file test**).
- [ ] Every one of the 38 existing tests still passes.
- [ ] JS/TS nodes now carry `line`.

---

#### 1.2 Multi-Scale Semantic Clustering & Architectural Layers  *(Sprint 2)*

**Correction C5.** The pyramid and 5-layer coloring already exist. This milestone adds
**collapsible semantic clustering** on top.

1. **Level 1 — Domain clusters.** Group files into collapsible architectural domains
   (Frontend UI, API Gateway, Core Business Logic, Data Access, Utilities, Integrations).
   Sources, in priority order:
   a. `backend/arch_rules.py` layer classification (shared with the MCP server — see C6),
   b. path heuristics as fallback,
   c. optional LLM refinement for repos that defeat both.
2. **Level 2 — Files** inside the selected cluster.
3. **Level 3 — Symbols** (function/class) on node expansion.
4. **Layout.** Keep Dagre for the pyramid (it works and is already tuned). Add `elkjs` for
   *cluster-packed* layout only, behind a toolbar toggle — do not replace the existing layout,
   which is tuned and screenshot-verified.
5. **Cluster nodes** use the existing `cluster` node kind (`GraphView.tsx:806` already special-cases it).

**Acceptance.**
- [ ] Clusters are collapsible/expandable and preserve the existing pyramid when toggled off.
- [ ] Cluster membership is identical to what `GET /api/arch/rules` reports.
- [ ] No regression to the existing golden screenshots (`docs/screenshots/graph.png`).

---

#### 1.3 Git Churn & Complexity Heatmap Overlays  *(Sprint 2)*

**Correction C2.** New module `backend/git_history.py` — **not** `repo_tracker.py`.

**Metrics.**
| Metric | Source |
|---|---|
| Churn score | `git log --numstat --since=90.days` → commits touching the file |
| Lines changed | same, summed |
| Co-change coupling | files appearing together in the same commit → "entangled files" |
| Hotspot score | `churn × centrality × complexity` (normalized 0–1) |
| Blast frequency | commits to the file that also touched one of its graph dependents |

**Visual.** Emerald (stable) → Amber → Crimson (hotspot) node fill, with a legend toggle.
Rendering must not fight the existing 5-layer color coding — **churn renders as a border/halo
ring**, layer stays as the fill.

**Acceptance.**
- [ ] `backend/git_history.py` has **zero** coupling to `repo_tracker.py`.
- [ ] Works on a repo with no `.git` (returns empty, no exception).
- [ ] Hotspot ring is visually distinct from layer fill at a glance.

---

#### 1.4 Viewport Optimization (LOD + WebGL)  *(Sprint 2 DOM part, Sprint 6 WebGL)*

**Correction C4.** `onlyRenderVisibleElements` is already on.

**Sprint 2 — LOD culling (DOM tier).**
- Below zoom `0.4`: hide node subtitles and secondary edge labels.
- Below zoom `0.25`: hide non-backbone edges entirely.
- Above zoom `1.2`: show full detail.

**Sprint 6 — WebGL tier.**
- Optional renderer (three.js or Pixi.js) behind a toolbar toggle, activated only when
  `nodeCount > 2000` **and** the user opts in. The ReactFlow path stays the default so no
  existing behavior changes.

**Acceptance.**
- [ ] LOD thresholds are in one config object, not scattered magic numbers.
- [ ] ReactFlow remains the default path; no visual change at default zoom.

---

### Milestone 2 — IDE Deep Linking & Local Directory Ingestion

#### 2.1 Universal IDE Protocol Handlers  *(Sprint 4)*

**Protocols.**

| Editor | URI |
|---|---|
| VS Code | `vscode://file/{abs}:{line}:{col}` |
| VS Code Insiders | `vscode-insiders://file/{abs}:{line}:{col}` |
| Cursor | `cursor://file/{abs}:{line}:{col}` |
| JetBrains | `jetbrains://idea/navigate/reference?project={proj}&path={rel}:{line}` |
| Sublime Text | `subl://open?url=file://{abs}&line={line}` |

**Implementation.**
- `frontend/src/utils/ideLinks.ts` — pure functions: `buildEditorUri(editor, abs, line, col)`,
  `resolveWorkspaceRoot(relPath, root)`. Unit-testable, no React.
- **Settings modal** (new component `frontend/src/components/EditorSettings.tsx`): preferred
  editor, local workspace root, "always ask" toggle. Persist in `localStorage` under
  `reposcope-ide-prefs`.
- **Path resolution.** Local mode → absolute path directly (the server knows its root). Web mode →
  join the user's configured workspace root with the repo-relative path.
- **Fallback.** If no root configured (web mode) → copy the repo-relative path to the clipboard and
  toast "Copied path — set a workspace root in Settings to open directly."
- **Entry points:** node click, node drawer "Open in editor", code-tour step, AI citation pill.

**Acceptance.**
- [ ] `buildEditorUri()` is unit-tested for all 5 protocols.
- [ ] Clicking a Python node opens the exact line (requires Milestone 1.1 for JS/TS).
- [ ] Missing-root fallback never throws and always gives the user a copyable path.

---

#### 2.2 Local Repository Ingestion — RepoScope CLI  *(Sprint 3)*

**Purpose.** Analyze uncommitted, private, or air-gapped code without pushing to GitHub and
without a personal access token. **This removes the single biggest friction for a judge trying
RepoScope.**

**Implementation.**

1. `backend/repo_loader.py` → add `load_local_repo(path: str) -> dict`.
   Sets `state["local_path"]`, `state["repo"] = <dirname>`, reads README, counts files.
   Every downstream feature (graph, chat, impact, onboarding, PR bot) already reads
   `state["local_path"]` → **all of them light up with no further change.**
2. `cli/main.py` (Typer):
   ```
   reposcope run .              # serve the built frontend + backend on :4100
   reposcope run . --port 4100 --no-open
   reposcope index .            # write .reposcope/graph.json (no server)
   reposcope index . --format sqlite
   reposcope mcp .              # start the MCP server (stdio) for this repo  ← demo shortcut
   ```
3. **Packaging:** `pyproject.toml` with `[project.scripts]` →
   `reposcope = "cli.main:app"`. Publishable to PyPI; `npx` is optional sugar — document
   `pip install reposcope`.
4. **Live watcher** — `backend/watcher.py` using `watchdog`:
   - debounce 500ms → re-parse only changed files → rebuild affected edges →
     push a fresh `context` event over the **existing** SSE channel (`/api/chat/stream`).
   - The frontend already renders the graph from the `context` event → live graph for free.
5. **Local-mode guardrails:** bind to `127.0.0.1` only; no outbound requests for source code;
   a visible "LOCAL MODE" badge in the UI so it is obvious nothing was uploaded.

**Acceptance.**
- [ ] `reposcope run .` on a local repo → graph renders with **zero** GitHub interaction.
- [ ] `git log`/`git status` are never called for a local repo lacking `.git`.
- [ ] Editing a file updates the graph **without a page reload**.
- [ ] Server binds to loopback only.

---

#### 2.3 Browser Web File System Access API  *(Sprint 3, experimental, built last)*

**Correction C8.** Optional and clearly labelled experimental.

- `window.showDirectoryPicker()` in Chromium; feature-detect and hide the button elsewhere.
- Parse in-browser with **Tree-sitter WASM**; construct the graph client-side; **no source code
  leaves the browser.**
- Requires a WASM build of the grammars — a real sub-project. Sequence it **after** the native
  path is fully working, and mark it experimental in the UI.
- Provide a clear fallback banner pointing at the CLI (`reposcope run .`).

**Acceptance.**
- [ ] Browser never transmits file contents (verifiable in devtools).
- [ ] Non-Chromium browsers show a graceful "use the CLI instead" state.

---

### Milestone 3 — Model Context Protocol (MCP) Server  *(Sprint 4)*

**Positioning.** RepoScope stops being "an app you visit" and becomes **infrastructure every AI
coding agent can query**. Every modern agent (Claude Code, Claude Desktop, Cursor, Codex) is an
MCP client.

**Correction C1 — transports.** `stdio` (local) + `streamable-http` (remote). **No SSE.**

**Package.** `reposcope-mcp`, entry `reposcope-mcp` (stdio) / `reposcope-mcp --http` (Streamable HTTP).

**Architecture.** The MCP server is a **client of the same `GraphStore`** as the web app — it
does not re-implement parsing (C11).

**Tools.**

| Tool | Input | Implementation |
|---|---|---|
| `get_architecture_overview` | `{max_depth: int = 2}` | Layer/domain summary + entry points + top hubs, from `arch_rules.py` + graph |
| `calculate_blast_radius` | `{target_file: str, target_symbol?: str, depth: int = 3}` | `impact_analyzer.compute_blast_radius` — symbol-aware when 1.1 lands |
| `get_dependency_lineage` | `{file_path: str, direction: "upstream"\|"downstream"\|"both"}` | `graph_utils.bfs_traverse` over forward/reverse adjacency |
| `explain_architectural_rule` | `{source_file: str, imported_file: str}` | `arch_rules.violates()` — **requires C6** |

**Resources.**

| URI | Content |
|---|---|
| `reposcope://graph/summary` | node/edge counts, cyclomatic density, top central hubs |
| `reposcope://hotspots` | top-10 by churn × centrality × complexity (Milestone 1.3) |

**Implementation notes.**
- Resolve the repo root from `--root`, `REPOSCOPE_ROOT`, or `cwd`.
- **Echo the resolved absolute path** in the tool description — the agent can then cite real paths.
- Reuse `runtime_config.ask_llm` if any tool needs narration; keep tool calls **deterministic and
  LLM-free** wherever possible (deterministic = fast + trustworthy + demoable).
- Register the server with clients:
  ```json
  {
    "mcpServers": {
      "reposcope": {
        "command": "reposcope-mcp",
        "args": ["--root", "/path/to/repo"]
      }
    }
  }
  ```
- Publish a `reposcope-mcp.json` template in `docs/` and a README section.

**Acceptance.**
- [ ] `mcp.run(transport="stdio")` completes the initialize handshake.
- [ ] `tools/list` returns exactly the 4 tools with valid JSON Schemas.
- [ ] Each tool returns correct results against a fixture repo (golden expectations).
- [ ] `resources/read` works for both URIs.
- [ ] Works in **Claude Desktop and Cursor** (screenshot in `docs/screenshots/`).
- [ ] No SSE transport anywhere in the codebase.

---

### Milestone 4 — Native IDE Extension (VS Code & Cursor)  *(Sprint 5)*

**Scope (approved): full extension + protocol links.**

**Compatibility.** VS Code, Cursor, and VSCodium — all use the same extension host API.

**Architecture.**
```
extensions/vscode/
  package.json          # contributes: viewsContainers, statusBar, codeLens, menus
  tsconfig.json
  src/extension.ts      # activate(): register provider, status bar, watcher
  src/graphClient.ts    # talks to the RepoScope backend (localhost) or GraphStore directly
  src/miniGraph.ts      # webview panel — mini graph canvas
  src/statusBar.ts      # blast-radius indicator
  src/codeLens.ts       # "View Callers (8)" provider
```

**Features.**
1. **Activity Bar sidebar webview** — dark-mode mini-graph synced to the active editor tab.
   On `onDidChangeActiveTextEditor`, center and pulse the matching node.
2. **Status bar blast-radius metric** — `RepoScope: ⚠️ 12 dependents | Risk: Med`. Clicking opens
   a popover listing immediate upstream files needing regression tests.
3. **CodeLens** on exported classes/functions: `[RepoScope: View Callers (8)]` and
   `[Show Blast Radius]`.
4. **Explorer context menu** — right-click a file → "Visualize in RepoScope Canvas"
   (opens the web app at the right node via a deep link).
5. **Walkthrough sync** — clicking a code-tour step in the web app opens the exact file and line
   in the editor. Mechanism: the web app emits a `reposcope://open?path=…&line=…` link that the
   extension registers as a URI handler (`vscode.window.registerUriHandler`).

**Distribution.** `vsce package` → `.vsix`. Publish to the **Open VSX** marketplace first
(Cursor + VSCodium read Open VSX; the VS Code Marketplace requires a publisher account).
Document manual `.vsix` install as the fallback.

**Acceptance.**
- [ ] Extension activates in VS Code and in Cursor with no errors.
- [ ] Status bar updates within 1s of switching tabs.
- [ ] CodeLens shows accurate caller counts matching the MCP tool output.
- [ ] URI handler opens the requested file and line.

---

### Milestone 5 — PR Impact Bot 2.0  *(Sprint 6)*

#### 5.1 AST-Level Interface & Breaking Change Diffing

**Correction C3.** `security_scanner.detect_breaking_in_patch` already exists (regex). **Upgrade
it, don't duplicate it.** New module `backend/contract_diff.py` provides the tree-sitter
implementation; `security_scanner.detect_breaking_in_patch` delegates to it; `pr_impact.py`
consumes the same output.

**Detect.**
- Deleted exported function / class / interface.
- Renamed parameter.
- Added **required** parameter without a default.
- Changed return type.
- Changed exported type/interface shape.
- Removed or narrowed an exported member.

**Precision requirement.** Flag only downstream files that **actually consume the modified
symbol** — resolved via the call graph and import edges — not every file in the directory.
This is where Milestone 1.1 pays off.

#### 5.2 Automated Unit Test Stub Generation

- For each high-risk affected module with no corresponding test file, synthesize test stubs.
- Output: ready-to-commit code blocks (`tests/test_auth_impact.py` or `tests/auth.test.ts`)
  covering edge cases and mock inputs.
- Generate via `runtime_config.ask_llm` with a strict JSON schema; parse with
  `backend/json_utils.py` (already hardened for broken LLM JSON — see commit `0b697b0`).
- **Always show as a suggestion** with an explicit "generated by AI — review before committing"
  marker. Never auto-commit.

#### 5.3 Conversational Two-Way Review Bot

- GitHub App **or** PAT-based webhook. Handle `issue_comment.created` and
  `pull_request_review_comment`.
- Triggers: `@reposcope-bot explain risk for payment_gateway.py`,
  `@reposcope-bot suggest test cases`, `@reposcope-bot verify architectural boundaries`.
- Replies inline with code snippets, graph breadcrumbs, and recomputed blast numbers.
- **Simplification for v2.0:** implement `POST /api/pr/chat` (pure function, no webhook
  plumbing) **plus** a GitHub Action that reads PR comments and posts the reply. The webhook
  server can be added later without changing the core.

#### 5.4 Rich Visuals & Merge Gate Policy

- Replace the plain Mermaid block with an expandable summary table + SVG badges + deep links
  into the web UI (`?repo=…&node=…`). **Keep Mermaid as the fallback** — GitHub renders it
  natively and it needs no external service.
- Extend `.github/workflows/pr-impact.yml` with a strict mode:
  ```yaml
  - name: RepoScope Merge Gate
    uses: adityapatel5912/reposcope-action@v2
    with:
      max_allowed_risk_score: 75
      require_tests_for_high_risk: true
      block_on_breaking_contract: true
  ```
  Note the scale mismatch: the API returns `risk_score` on a **0–10** scale, while the action
  input implies **0–100**. **Normalize to 0–100 at the action boundary** and document it.

**Acceptance.**
- [ ] A PR that renames a required parameter is flagged as BREAKING, and the flag names the
      **consuming** files, not the containing directory.
- [ ] A PR that renames a *private* helper is **not** flagged.
- [ ] Test stubs are generated for high-risk modules with no existing test file.
- [ ] `@reposcope-bot` in a PR comment produces a grounded reply with a recalculated blast radius.
- [ ] Merge gate blocks a PR whose risk score exceeds the threshold.

---

### Milestone 6 — Scalability, Graph Storage & Performance  *(Sprint 3 + Sprint 7)*

#### 6.1 Embedded Graph Storage

**Correction C7.** Interface in Sprint 0 (C11); `SqliteGraphStore` implementation in Sprint 7.

- `backend/graph_store.py`:
  ```python
  class GraphStore(Protocol):
      def load(self) -> dict: ...
      def save(self, graph: dict) -> None: ...
      def stats(self) -> dict: ...
  ```
- `JsonGraphStore` — `.reposcope/graph.json`. Default. Zero risk.
- `SqliteGraphStore` — stdlib `sqlite3`. Tables: `nodes(id, type, label, file, line, …)`,
  `edges(source, target, type)`, `symbols`, `files`, `meta`.
- Recursive CTEs for transitive closure, shortest path, and cycle detection.
- `kuzu` behind a feature flag with graceful fallback to sqlite — **never a hard dependency**.
- Target: transitive traversal over a 50,000-file repo in <100ms.

#### 6.2 Caching & Incremental Indexing  *(Sprint 3)*

- Store a SHA-256 per file in `meta`/`files` table.
- On re-scan or commit: `git diff --name-only HEAD~1` (or watcher events) → re-parse **only**
  changed files → patch their edges → keep everything else.
- Target: incremental update in **<50ms** for a single-file change.
- In-memory LRU cache over the adjacency structures, invalidated per-subgraph.

**Acceptance.**
- [ ] A one-file edit updates the graph in <50ms.
- [ ] A 50k-file repo's transitive closure resolves in <100ms.
- [ ] The JSON store is the default and the app works with no sqlite/kuzu present.

---

## 5. Sprint plan

| Sprint | Focus | Key deliverables | Milestones |
|---|---|---|---|
| **Sprint 0** | Foundation & safety net | `backend/api/` router package; `backend/graph_store.py` (interface + `JsonGraphStore`); `backend/arch_rules.py`; fixture repos + **golden-file graph tests**; `pytest` fixtures | C9, C11, C6 |
| **Sprint 1** | Tree-sitter polyglot engine | `backend/parsers/*`; `graph_builder.py` rewrite (contract preserved); `calls` edges; complexity; symbol resolution | 1.1 |
| **Sprint 2** | Graph UX & hotspots | Semantic clusters + collapse; `backend/git_history.py`; churn rings + legend; LOD culling | 1.2, 1.3, 1.4 |
| **Sprint 3** | Local mode & incremental indexing | `load_local_repo()`; `cli/` + packaging; `backend/watcher.py` + live SSE update; SHA-256 incremental index | 2.2, 6.2 |
| **Sprint 4** | MCP server + IDE links | `backend/mcp_server/` (4 tools, 2 resources, stdio + Streamable HTTP); `frontend/src/utils/ideLinks.ts`; `EditorSettings.tsx` | 3, 2.1 |
| **Sprint 5** | IDE extension | `extensions/vscode/`; mini-graph webview; status bar; CodeLens; URI handler; `.vsix` + Open VSX | 4 |
| **Sprint 6** | PR Bot 2.0 | `backend/contract_diff.py`; `security_scanner` upgrade; `pr_impact` integration; test-stub synthesis; `POST /api/pr/chat`; merge gate | 5.1–5.3 |
| **Sprint 7** | Scale-out & experimental tiers | `SqliteGraphStore` + CTEs; LRU cache; WebGL tier; browser File System Access (experimental); merge-gate 0–100 normalization | 6.1, 1.4-WGL, 2.3, 5.4 |

**Sprint 0 is mandatory.** Every later sprint depends on the router package, the `GraphStore`
interface, the shared arch rules, and the golden-file tests that prevent a parser rewrite from
silently breaking the pyramid.

### Sprint 0 — locked decisions

Two design choices were left open in the original plan. Both are **decided** below and are
binding for whoever executes Sprint 0.

#### D1 — Router migration: **incremental**, not wholesale

**Decision.** Sprint 0 creates the `backend/api/` package, a `register_routers(app)` entry
point, and exactly **one** new endpoint (`GET /api/arch/rules`). Existing endpoints are **not**
migrated in Sprint 0. Each future sprint moves the endpoints it owns into a router as that
feature lands.

| Sprint | Router | Endpoints migrated in that sprint |
|---|---|---|
| 0 | `routers/arch.py` | none (new endpoint only) |
| 3 | `routers/local.py` | local-mode / repo-status endpoints |
| 4 | `routers/mcp_info.py` | MCP introspection endpoints |
| 6 | `routers/pr_chat.py` | `POST /api/pr/chat` |

**Rationale.** Sprint 0's purpose is a safety net, not a refactor. Moving ~1,100 lines of
working, screenshot-verified endpoint code into routers in the same sprint that introduces the
golden test produces a large, hard-to-review diff and risks exactly the regressions Sprint 0
exists to prevent. Incremental migration keeps every sprint's diff reviewable and lets each
migration be tested against the behaviour it preserves. `main.py` stays mixed for a few sprints
— that is an acceptable, temporary cost.

**Constraint.** `main.py` must remain under **1,200 lines** for the duration of v2.0. If adding
a feature would breach that, the feature's endpoints go into a router — never into `main.py`.

#### D2 — Fixtures: **hand-authored minimal** + **one small real repo**

**Decision.** Four committed fixture repos under `backend/tests/fixtures/`:

| Fixture | Purpose | Shape |
|---|---|---|
| `multilang/` | Multi-language parsing + cross-language import resolution | `.py`, `.ts`, `.tsx`, `.js`, `.go` — a deliberate import chain across all five |
| `circular/` | Cycle detection | A known 3-node import cycle plus an isolated acyclic pair |
| `nested/` | Relative-import + package resolution | Deeply nested packages, `__init__.py` chains, `src/` layouts |
| `real_small/` | Reality check | One **tiny, permissively-licensed** real repository (MIT/Apache-2.0), vendored, with its licence file retained |

**Rationale.** Hand-authored fixtures are deterministic, small, readable, licence-clean, and let
a golden snapshot be reviewed line-by-line — a reviewer can verify the expected node ids by
reading five short files rather than a thousand. A single small real repo guards against the
failure mode where the parser works on synthetic input but breaks on a real layout (`setup.py`,
`pyproject.toml`, generated files, mixed conventions). Bulk real repos are excluded: they add
licence noise and make snapshot diffs unreadable.

**Constraint.** Every fixture is **committed**, not generated at test time. Golden regeneration
is **explicit only** — `pytest --regen-golden` — never automatic, so a snapshot can never be
rewritten to match a broken parser.

#### D3 — Sprint 0 file manifest (authoritative)

```
backend/api/__init__.py            register_routers(app)
backend/api/routers/__init__.py
backend/api/routers/arch.py         GET /api/arch/rules
backend/graph_store.py              GraphStore Protocol + JsonGraphStore
backend/arch_rules.py               layer taxonomy + edge policy + .reposcope.yml loader
backend/graph_analysis.py           pagerank_scores(), strongly_connected_components()
backend/tests/fixtures/multilang/   fixture repo
backend/tests/fixtures/circular/    fixture repo
backend/tests/fixtures/nested/      fixture repo
backend/tests/fixtures/real_small/  fixture repo (+ LICENSE)
backend/tests/test_graph_golden.py  golden-file test
backend/tests/conftest.py           + fixture_repo, built_graph, golden_snapshot
benchmarks/README.md                harness contract (no numbers)
```

**Gate.** The golden test must be demonstrated **going red** on a perturbed node id and green
after restore. Sprint 0 is not complete until that red/green is demonstrated — a passing golden
test that was never observed failing proves nothing.

### Demo checkpoint per sprint

| Sprint | Demoable outcome |
|---|---|
| 0 | Nothing visible — but the safety net exists |
| 1 | Graph shows **call edges** and JS/TS line numbers for the first time |
| 2 | Collapsible clusters + churn heatmap |
| 3 | `reposcope run .` on a local repo; graph updates live on edit |
| 4 | **Cursor asks RepoScope MCP for a blast radius; click a node → editor opens** ← *the money demo* |
| 5 | VS Code status bar shows live blast radius; CodeLens shows caller counts |
| 6 | PR comment flags a renamed required param and names its consumers; `@reposcope-bot` replies |
| 7 | 50k-file repo traversed in <100ms; optional WebGL tier |

---

## 6. Agent execution prompts

> Each prompt is self-contained. Paste into an autonomous coding agent. Each references the
> corrections in Section 2 — **include Section 2 in the agent's context.**

### Agent Prompt A — Tree-sitter Polyglot Engine (Sprint 1)

```
Role: Principal Backend Engineer
Context: RepoScope (FastAPI + React) at D:\Aditya\Hackathon Projects\RepoScope.
         Read C:\Users\Admin\.opencode\plan\reposcope-v2-plan.md Section 2 first — it is binding.

Task: Replace regex-based JS/TS parsing in backend/graph_builder.py with Tree-sitter, and add
function-level call graphs.

Requirements:
1. Create backend/parsers/ with a LanguageParser Protocol, a registry keyed by file extension,
   and per-language implementations for Python, TypeScript, JavaScript, Go, Rust.
2. tree-sitter 0.25.2 is installed. NOTE the API change:
       from tree_sitter import Language, Parser, Query, QueryCursor
       caps = QueryCursor(Query(lang, QUERY)).captures(tree.root_node)   # dict[str, list[Node]]
   Query(lang, QUERY).captures(...) does NOT exist in 0.25 and raises AttributeError.
3. Extract: symbols (functions/classes/interfaces/types/structs/impls), imports, export markers,
   call sites, and cyclomatic complexity per function.
4. Build a global symbol table and resolve call sites to definition sites, producing
   `calls` edges between symbol nodes. The frontend already renders edge type "calls"
   (frontend/src/components/GraphView.tsx:174) — do not change the frontend.
5. HARD CONSTRAINT (C10): preserve the existing public contract exactly —
   build_graph_from_repo(root) -> {"nodes", "edges", "summary"};
   node ids file:{rel} / func:{rel}:{name} / class:{rel}:{name};
   edge types "contains" and "imports" unchanged; add "calls".
   Nodes must keep keys: id, type, label, file, line, language, size.
   Add `line` to JS/TS symbol nodes (currently missing).
6. HARD CONSTRAINT: keep the existing regex JS/TS parser as a fallback when a grammar fails
   to load. A grammar failure must never break the app.
7. Add a golden-file test: parse a fixture repo, snapshot node ids + edge types, and assert
   they match a checked-in snapshot. This test must FAIL if ids drift.

Verification:
- pytest backend/tests — all 38 existing tests still pass, plus the new golden test.
- Demonstrate on a TS fixture that `calls` edges and line numbers now appear.

Deliverable: the diff + the passing test output.
```

### Agent Prompt B — MCP Server (Sprint 4)

```
Role: Systems & AI Protocol Specialist
Context: RepoScope at D:\Aditya\Hackathon Projects\RepoScope.
         Read C:\Users\Admin\.opencode\plan\reposcope-v2-plan.md Sections 2 and 4 (M3) first.

Task: Build an official Model Context Protocol server for RepoScope.

Requirements:
1. Use the `mcp` Python SDK (1.29.0 installed) via FastMCP:
       from mcp.server.fastmcp import FastMCP
2. TRANSPORTS (Correction C1): stdio (default) and streamable-http.
   DO NOT implement or enable SSE — it is deprecated since spec revision 2025-03-26.
3. Expose exactly these tools:
   - get_architecture_overview(max_depth=2)
   - calculate_blast_radius(target_file, target_symbol?, depth=3)
   - get_dependency_lineage(file_path, direction=upstream|downstream|both)
   - explain_architectural_rule(source_file, imported_file)
4. Expose resources: reposcope://graph/summary and reposcope://hotspots.
5. The server must be a CLIENT of the shared GraphStore (backend/graph_store.py), not a second
   parser. Reuse backend/graph_utils.build_adjacency, backend/graph_utils.bfs_traverse, and
   backend/impact_analyzer.compute_blast_radius.
6. Resolve the repo root from --root, else $REPOSCOPE_ROOT, else cwd. Echo the resolved
   absolute path in the tool description so the calling agent can cite real paths.
7. Tool calls must be deterministic — no LLM calls inside tools.
8. explain_architectural_rule must use backend/arch_rules.py (the shared rule set, also served
   to the frontend via GET /api/arch/rules). Do not duplicate the rules in the MCP server.
9. Provide a test suite: initialize handshake, tools/list schema compliance, and one happy-path
   invocation of each tool against a fixture repo.
10. Document client registration:
    {"mcpServers": {"reposcope": {"command": "reposcope-mcp", "args": ["--root", "<path>"]}}}
    Add to docs/ with a Claude Desktop and Cursor section.

Verification:
- pytest backend/mcp_server/tests — all pass.
- `reposcope-mcp --root <fixture>` starts and responds to tools/list over stdio.
- Paste the actual tools/list output.

Deliverable: the diff + test output + the tools/list JSON.
```

### Agent Prompt C — Local CLI Mode (Sprint 3)

```
Role: Backend + Tooling Engineer
Context: RepoScope at D:\Aditya\Hackathon Projects\RepoScope.
         Read C:\Users\Admin\.opencode\plan\reposcope-v2-plan.md Sections 2 and 4 (M2.2) first.

Task: Add local-directory ingestion so users can analyze uncommitted/private repos with no
      GitHub account, no PAT, and no push.

Requirements:
1. backend/repo_loader.py: add load_local_repo(path) that sets state["local_path"] and
   state["repo"] to the directory name, reads the README, and counts files.
   Every downstream feature already reads state["local_path"] — verify that graph, chat,
   impact analysis, onboarding, and the PR bot all work in local mode with no further change.
2. cli/main.py (Typer 0.27.2 is installed):
       reposcope run . [--port 4100] [--no-open]
       reposcope index . [--format json|sqlite]
       reposcope mcp .        # start the MCP server for this repo
3. pyproject.toml with [project.scripts] reposcope = "cli.main:app".
4. backend/watcher.py using watchdog (6.0.0 installed): debounce 500ms, re-parse only changed
   files, rebuild affected edges, and push a fresh `context` event over the EXISTING SSE channel
   at /api/chat/stream. The frontend already renders the graph from the `context` event.
5. Guardrails: bind to 127.0.0.1 only; never make outbound network calls for file contents;
   never call git against a directory with no .git.
6. Frontend: show a visible "LOCAL MODE" badge when the backend reports local mode.

Verification:
- `reposcope run .` in a local repo serves the UI with no GitHub interaction.
- Editing a file updates the graph WITHOUT a page reload.
- Demonstrate the loopback bind and the absence of any GitHub request.

Deliverable: the diff + a screen recording or terminal transcript of the live-update loop.
```

### Agent Prompt D — VS Code / Cursor Extension (Sprint 5)

```
Role: VS Code Extension Engineer
Context: RepoScope at D:\Aditya\Hackathon Projects\RepoScope.
         Read C:\Users\Admin\.opencode\plan\reposcope-v2-plan.md Section 4 (M4) first.

Task: Build extensions/vscode/ — a VS Code / Cursor / VSCodium extension.

Requirements:
1. Activity Bar sidebar webview showing a dark-mode mini-graph, synced to the active editor tab
   via onDidChangeActiveTextEditor — center and pulse the matching node.
2. Status bar item showing the current file's blast radius, e.g.
   "RepoScope: ⚠️ 12 dependents | Risk: Med", clicking opens a popover listing immediate
   upstream files that need regression tests.
3. CodeLens on exported classes/functions: "[RepoScope: View Callers (8)]" and
   "[Show Blast Radius]". Counts must match the MCP tool output exactly.
4. Explorer context menu item "Visualize in RepoScope Canvas".
5. URI handler (vscode.window.registerUriHandler) for reposcope://open?path=...&line=... so a
   code-tour step in the web app opens the exact file and line.
6. The extension reads from the local RepoScope backend over HTTP (localhost) — do not
   duplicate the parser in TypeScript.
7. Package with vsce; publish to Open VSX (Cursor and VSCodium read it); document the manual
   .vsix install as the fallback. Note the VS Code Marketplace requires a publisher account.

Verification:
- F5 launch, then screenshot: sidebar mini-graph, status bar item, and CodeLens.
- Paste the extension host log showing zero errors on activation in VS Code AND in Cursor.

Deliverable: the diff + screenshots + the .vsix build output.
```

### Agent Prompt E — PR Bot 2.0 Contract Diffing (Sprint 6)

```
Role: Backend Engineer
Context: RepoScope at D:\Aditya\Hackathon Projects\RepoScope.
         Read C:\Users\Admin\.opencode\plan\reposcope-v2-plan.md Section 2 (C3) and 4 (M5) first.

Task: Upgrade the PR bot to AST-level, contract-aware breaking-change detection.

Requirements:
1. IMPORTANT (Correction C3): backend/security_scanner.py ALREADY has detect_breaking_in_patch
   (regex-based, around line 139). Do NOT write a second detector. Create
   backend/contract_diff.py with the tree-sitter implementation, and refactor
   detect_breaking_in_patch to delegate to it so there is exactly ONE source of truth.
   Then have backend/pr_impact.py consume the same output.
2. Detect: deleted exported function/class/interface; renamed parameter; added required
   parameter without a default; changed return type; changed exported interface shape;
   removed or narrowed exported member.
3. PRECISION REQUIREMENT: report only downstream files that actually CONSUME the modified
   symbol (resolved through the call graph and import edges) — not every file in the directory.
   A renamed private helper must NOT be flagged. A renamed exported function MUST be flagged
   with its consuming files named.
4. Test-stub synthesis: for each high-risk affected module with no corresponding test file,
   generate a stub via runtime_config.ask_llm, parsed with backend/json_utils.py (already
   hardened for broken LLM JSON). Output pytest or vitest code blocks, always labelled
   "generated by AI — review before committing". Never auto-commit.
5. Conversational bot: implement POST /api/pr/chat as a pure function that handles
   "@reposcope-bot explain risk for <file>", "suggest test cases", and
   "verify architectural boundaries". Add a GitHub Action that reads PR comments and posts
   the reply — do not build a webhook server in this sprint.
6. Merge gate: extend .github/workflows/pr-impact.yml with a strict mode.
   NOTE the scale mismatch — the API returns risk_score 0-10 while the action input
   max_allowed_risk_score implies 0-100. Normalize at the action boundary and document it.
7. Keep the Mermaid block as a fallback; add the expandable table + SVG badges alongside it.

Verification:
- pytest backend/tests — all existing tests pass.
- Add a test with a fixture diff that renames a required parameter and asserts BREAKING +
  the correct consuming file named; and a test that renames a private helper and asserts
  NOT flagged.
- Paste the generated PR comment markdown.

Deliverable: the diff + test output + a sample rendered PR comment.
```

### Agent Prompt F — Foundation & Safety Net (Sprint 0)

> The original plan had prompts for Sprints 1, 3, 4, 5, 6 but **none for Sprint 0**.
> Sprint 0 is the safety net the whole plan depends on, so it needs a prompt too.

```
Role: Backend Engineer (foundation)
Context: RepoScope at D:\Aditya\Hackathon Projects\RepoScope.
         Read C:\Users\Admin\.opencode\plan\reposcope-v2-plan.md Section 2 (BINDING) and
         Section 5 "Sprint 0 - locked decisions" (D1, D2, D3 — also binding).
         The plan is also committed in-repo at docs/ROADMAP_V2.md.

Task: Build the safety net that makes the Tree-sitter rewrite (Sprint 1) safe.
      Sprint 0 is NOT user-visible. Do not add features. Do not migrate existing
      endpoints out of main.py (decision D1 — incremental migration only).

Requirements:

1. backend/api/ — router package (Correction C9, decision D1).
   - backend/api/__init__.py exposes `register_routers(app)`.
   - backend/api/routers/arch.py serves GET /api/arch/rules.
   - main.py: `from api import register_routers` + one call. Nothing else changes.
   - main.py must stay UNDER 1,200 lines.

2. backend/graph_store.py (Correction C11).
   - `class GraphStore(Protocol)`: load() -> dict, save(graph: dict) -> None, stats() -> dict
   - `class JsonGraphStore`: persists to .reposcope/graph.json
   - Shape MUST match build_graph_from_repo() exactly:
       file nodes  {id, type, label, language, size}
       sym  nodes  {id, type, label, file, line}
       ids         file:{rel}  func:{rel}:{name}  class:{rel}:{name}
       edges       {source, target, type} with type in {contains, imports}
   - Round-trip test: save() then load() returns an equal graph.

3. backend/arch_rules.py (Correction C6) — THE SINGLE SOURCE OF TRUTH.
   - Port the 5-layer taxonomy from frontend/src/components/graph/layerClassifier.ts
     (LAYER_STYLE + the ordered RULES regexes, lines 16-36). Same layer names
     (client, backend, storage, external, compute), same first-match-wins ordering.
   - Add edge-policy predicates, e.g.: client may import backend/storage/external;
     storage may NOT import client; external may not import client/backend internals.
   - Add a .reposcope.yml loader: keys `version`, `layers[]`, `rules[]`, `ignore[]`.
     Malformed config -> clear error message, NO crash, fall back to built-in rules.
   - The frontend must consume these via GET /api/arch/rules. Remove the duplicated
     rule table from layerClassifier.ts — exactly one copy must exist (decision D2 scope
     for C6; do not otherwise restructure the frontend in this sprint).

4. backend/graph_analysis.py — networkx 3.6.1 is installed.
   - pagerank_scores(graph) -> dict[node_id, float] over the DIRECTED imports+calls edges.
     Use nx.DiGraph. VERIFIED: nx.pagerank works; nx.community.louvain_communities works.
   - strongly_connected_components(graph) -> list of cycles. Use nx.DiGraph —
     nx.strongly_connected_components RAISES NetworkXNotImplemented on an undirected Graph.
   - Do NOT use nx.community.leiden_communities — it raises NotImplementedError unless
     the optional `leidenalg` backend is installed. Use louvain_communities.

5. Fixture repos (decision D2) — backend/tests/fixtures/, ALL COMMITTED:
   - multilang/  : .py, .ts, .tsx, .js, .go with a deliberate cross-language import chain
   - circular/   : a known 3-node import cycle + an isolated acyclic pair
   - nested/     : deep packages, __init__.py chains, src/ layout
   - real_small/ : ONE tiny permissively-licensed real repo, vendored, LICENSE retained

6. backend/tests/test_graph_golden.py — THE POINT OF THIS SPRINT.
   For each fixture, build the graph and assert:
       sorted [(node.id, node.type)]   == snapshot
       sorted [(source, target, type)] == snapshot
       summary string                  == snapshot
   Snapshots live at backend/tests/fixtures/<name>/golden.json.
   Regeneration is EXPLICIT ONLY — `pytest --regen-golden`. Never automatic.

7. backend/tests/conftest.py — add pytest fixtures:
   fixture_repo, built_graph, golden_snapshot loader.
   Keep the existing sys.path setup intact — `import main` must still resolve.

8. benchmarks/ — scaffold only: README.md stating the harness contract + an empty runner.
   Publish NO numbers. No claim may be made that this harness does not produce.

9. GATE (decision D3): before Sprint 0 is complete, DEMONSTRATE the golden test going
   RED when a node id is perturbed, then GREEN after restore. Paste both outputs.
   A golden test never observed failing proves nothing.

Verification:
- cd backend && python -m pytest -q   -> all 38 existing tests pass, plus new ones green
- cd backend && python -m pytest tests/test_graph_golden.py -q -> passes
- red/green golden demonstration (above)
- main.py line count < 1200
- GET /api/arch/rules values match layerClassifier.ts layer-for-layer and rule-for-rule

Deliverable: the diff + full pytest output + the red/green golden demonstration.
```

---

## 7. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Parser rewrite breaks the pyramid (ids/edges are load-bearing) | **High** | Sprint 0 golden-file test asserts id + edge-type parity; `contains`/`imports` semantics frozen |
| R2 | `main.py` grows past maintainability | Medium | Sprint 0 creates `backend/api/` routers; new endpoints only go in routers |
| R3 | Two divergent breaking-change detectors | **High** | Correction C3 — one implementation, `security_scanner` delegates |
| R4 | MCP server indexes the wrong root → agent cites wrong paths | High | `--root` required; `REPOSCOPE_ROOT` fallback; resolved absolute path echoed in the tool description |
| R5 | Kùzu native install fails on Python 3.14 → demo breaks | High | Correction C7 — stdlib `sqlite3` default; kuzu behind a feature flag only |
| R6 | Scope explosion → nothing demoable | **High** | Hard rule: no sprint starts until the previous sprint's demo runs end-to-end; Sprint 4 is the minimum viable demo |
| R7 | Extension API differences between VS Code and Cursor | Medium | Target the VS Code stable API only; avoid bleeding-edge proposals; verify in both before shipping |
| R8 | Tree-sitter 0.25 API mismatch → agent writes `Query.captures()` | Medium | Prompt A states the correct API explicitly; the golden test catches a broken parser immediately |
| R9 | Local mode leaks source code to a provider | **Critical** | Local mode makes no outbound calls for file contents; `localStorage` BYOK is the only path to an LLM; add a regression test asserting no source leaves the process |
| R10 | Risk-score scale mismatch (0–10 vs 0–100) confuses the merge gate | Medium | Normalize at the action boundary; unit-test the normalization |
| R11 | Browser WASM parser is a second implementation | Medium | Correction C8 — experimental, built last, CLI fallback banner |
| R12 | `codebase-memory-mcp` is not installed → silent degradation | Low | Already degrades gracefully (`mcp_client.py:28`); log at INFO. Consider removing the dead path in v2.0 |

---

## 8. Definition of done (v2.0)

- [ ] All 38 existing tests pass, plus ≥60 new tests across parser, MCP, contract diff, CLI.
- [ ] `backend/graph_builder.py` emits `calls` edges and line numbers for TS/JS/Go/Rust.
- [ ] Node/edge id contract unchanged (golden-file test enforces this).
- [ ] `reposcope run .` works on a local repo with no GitHub interaction and a live-update loop.
- [ ] `reposcope-mcp --root .` completes an MCP handshake over stdio and Streamable HTTP.
- [ ] All 4 MCP tools and 2 resources verified in Claude Desktop **and** Cursor (screenshots).
- [ ] No SSE transport anywhere in the codebase.
- [ ] IDE deep links work for VS Code, Cursor, VS Code Insiders, JetBrains, Sublime.
- [ ] VS Code extension installs in VS Code and Cursor with zero activation errors.
- [ ] PR bot flags a renamed required parameter and names its actual consumers.
- [ ] `@reposcope-bot` replies in a PR comment with a recalculated blast radius.
- [ ] Merge gate blocks an over-threshold PR.
- [ ] `backend/api/` holds every new endpoint; `main.py` stays under ~1,200 lines.
- [ ] `docs/FEATURES.md` and `README.md` updated to match shipped reality.
- [ ] `CHANGELOG.md` entry for v2.0.

---

## 9. Hackathon demo script

Three acts, ~3 minutes. Act 2 is the one that lands.

**Act 1 — "It works on my repo." (30s)**
```
npx reposcope .        # or: reposcope run .
```
Graph renders on a private, uncommitted local repo. No PAT, no push, no cloud.
Line: *"RepoScope just indexed a repo that has never left this laptop."*

**Act 2 — "Your AI agent knows your architecture." (60s)**
Open Cursor on the same folder. *"What breaks if I change `auth.py`?"*
Cursor calls RepoScope's MCP tools and answers with a real blast radius — direct and transitive
dependents, `file:line` citations, a risk score. Not LLM guesswork; the AST-derived graph.
Line: *"The agent isn't guessing. It asked the graph."*

**Act 3 — "The graph is not a dead end." (60s)**
Click a node in RepoScope → VS Code opens that exact line. Switch to VS Code → the status bar
shows `⚠️ 12 dependents | Risk: Med`; the CodeLens reads `View Callers (8)`.
Line: *"From the map, to the code, to the agent. One loop."*

**Backup if Act 2 fails:** pre-record the MCP exchange and keep the raw `tools/list` JSON and the
curl-equivalent call in the demo folder. A live MCP handshake is impressive but it is the one
part that depends on another machine's client version.

---

## 10. Verification log

| Claim | Method | Result |
|---|---|---|
| `mcp` 1.29.0 / `fastmcp` 3.4.7 installed | `pip show` | ✅ |
| `tree-sitter` 0.25.2 + 5 grammars installed | `pip list` | ✅ |
| `typer` 0.27.2, `watchdog` 6.0.0 installed | `pip list` | ✅ |
| `kuzu` not installed | `pip list` | ✅ confirmed |
| tree-sitter 0.25 query API | executed a probe script | ✅ `QueryCursor(Query(...)).captures(node)` → `dict[str, list[Node]]`; `Query.captures` **absent** |
| FastMCP transport options | `inspect.signature(mcp.run)` | ✅ `('stdio', 'sse', 'streamable-http')` — `sse` is legacy |
| Baseline test suite | `pytest -q` in `backend/` | ✅ **38 passed** in 4.67s |
| `onlyRenderVisibleElements` already present | `GraphView.tsx:986` | ✅ |
| `calls` edge type already accepted | `GraphView.tsx:174` | ✅ |
| JS/TS nodes lack `line` | `graph_builder.py:201` | ✅ confirmed |
| Layer rules are frontend-only | grep across `backend/*.py` | ✅ confirmed |
| `codebase-memory-mcp` absent from PATH | `Get-Command` | ✅ confirmed (silent no-op at `mcp_client.py:22`) |
| `main.py` size | line count | ✅ 1,115 lines |
| `apps/web/` is dead weight | directory listing | ✅ only `dist/`, `.turbo/`, `node_modules/`, no `package.json` — delete it |

---

# PART II — Competitive Positioning & Additions

> Added after a competitive audit (Oct 2026). Part I is unchanged and still binding.
> Part II identifies what the v2.0 spec **misses** relative to the field, and adds
> four milestones (M7–M10) plus a set of prioritised "sharpening" items.

---

## 11. Competitive audit — where RepoScope actually stands

### 11.1 The field is much more crowded than the original spec assumes

The original spec treats RepoScope as upgrading a niche product. It is not. As of Oct 2026 the
"code graph for AI agents" space has exploded, and several entrants are **already doing parts of
the v2.0 plan**.

| Project | Scale (Oct 2026) | What it already does that RepoScope's plan proposes |
|---|---|---|
| `codegraph` (colbymchenry) | ~54–68K stars, MIT | Function-level dep graph, tree-sitter → SQLite, auto-sync, **MCP server**. Claims 62% fewer tokens / 88% fewer tool calls |
| `Graphify` | ~112K stars | Deterministic tree-sitter AST graph |
| `Code-Graph-RAG` (er77) | npm, 14 languages | tree-sitter → **Memgraph + Qdrant**, 15 MCP tools, **hybrid graph + vector search**, dead-code detection, taint/dataflow edges |
| `GitNexus` | MCP-native | Knowledge graph with **Leiden communities + cohesion scores** |
| `CodeGraphContext` (CGC) | — | tree-sitter + optional **SCIP** indexers → property graph (compiler-grade refs) |
| `g rafel` (Rust) | — | Multi-repo daemon, cross-repo + IaC topology, watcher-driven |
| `tokensave` | 601 stars | 40+ tools, 30+ languages, pre-indexed semantic KG |
| `Context Mode` | ~20K stars | 11 MCP tools — and **no code parser at all** |
| `Repomix` | — | Official MCP server (`--mcp`), tree-sitter `--compress` (~70% reduction) |
| `Serena` | — | LSP + tree-sitter semantic code editing (LSP-grade, not AST-guessed) |

**In the visualisation lane** the incumbents are *older and weaker*:

| Project | Status (Oct 2026) |
|---|---|
| **CodeSee** | **Dead.** Visualisations dropped from the GitKraken DevEx platform; not on GitKraken's site as of 6 Oct 2026 |
| Sourcetrail | Archived end of 2021; community fork (GPL-3.0), C/C++/Java only |
| Sourcegraph | ~$16K/yr enterprise; code search + Insights + MCP |
| Madge / dependency-cruiser | JS/TS import graphs + cycle detection only, no call graph |
| CodeScene / repowise | Hotspot maps, git history + ownership |
| Structurizr | C4 modelling, hand-maintained |

### 11.2 The strategic consequence — and RepoScope's real wedge

Three conclusions follow, and they reframe the whole plan:

**① RepoScope cannot win the "MCP server over a code graph" race.**
`codegraph` at ~68K stars with 62%-token-reduction claims, `Code-Graph-RAG` with 15 tools and
hybrid vector search, and `Context Mode` with ~20K stars already own that narrative. A
RepoScope MCP server with 4 tools will be **indistinguishable** and outgunned.

**② The visualisation lane is genuinely vacant.**
CodeSee is dead. Sourcetrail is a GPL fork for three languages. Every 2026-era entrant is
**headless** — they expose tools and return JSON. Not one of them gives a human a *map*.
`Code-Graph-RAG`'s selling point is "query your graph in natural language," not "see your graph."

> **RepoScope's wedge: be the only tool that is simultaneously a human-facing visual map AND
> an agent-facing MCP server over the same index.** Everyone else picks one side of that line.
> `Code-Graph-RAG` gives Claude a graph. CodeSee gave a human a map. RepoScope gives **both**,
> from **one** index — and the human and the agent are looking at the *same* artifact.

That also explains why the whole v2.0 spec works: Tree-sitter (M1) → the index; MCP (M3) → the
agent side; the existing canvas → the human side. **The canvas is the moat, not the parser.**
The MCP server is the *distribution channel* that gets RepoScope in front of every AI agent
user; the visual map is the *reason* they keep it.

**③ "Another AI code reviewer" is a dead end.**
CodeRabbit, Greptile, Qodo, Copilot Code Review, Cursor BugBot, SonarQube, Optibot, Amazon Q
all do it. Greptile already claims "codebase-graph reviews" and "50% more bugs than
CodeRabbit." RepoScope's PR bot must therefore NOT compete on "catches bugs." It must compete
on **architecture governance** — the thing none of them do: *does this PR violate a boundary
rule, and did it break a contract that has actual consumers?* That is a different, defensible
product (see M10).

### 11.3 Feature gaps that would actually hurt RepoScope

| Gap | Who has it | Impact on RepoScope | Fix |
|---|---|---|---|
| **No PageRank / centrality** — RepoScope ranks files with `incoming × 2 + outgoing` (`GraphView.tsx:187`) | `aider` uses PageRank on the symbol graph; `codegraph` uses centrality for its repo map | The pyramid ranking — RepoScope's signature visual — is **naive and indefensible**. A reviewer asking "why is this file in row 1?" has no answer. | **M7.1** |
| **No dead-code detection** | `Code-Graph-RAG` (explicitly), `codegraph` | RepoScope shows what exists, never what is **unreachable**. Half of "understand a codebase" is knowing what's dead. | **M7.2** |
| **No cycle detection** | `Madge`, `dependency-cruiser` (their entire reason to exist) | Circular deps are the #1 architecture smell. The v2.0 spec mentions "Cyclic Dep Detection" in its diagram but **no milestone implements it**. | **M7.3** |
| **No semantic search** | `Code-Graph-RAG` (Qdrant + hybrid), `tokensave` | RepoScope's chat answers only what the LLM can find in a truncated context dump. | **M7.4** (optional, see below) |
| **No token-efficiency measurement** | `codegraph` (62%), `Repomix` (~70%), `grepai` (97%), `GitNexus` (88% fewer tool calls) | **This is the 2026 buying trigger.** RepoScope publishes *zero* numbers. | **M8.1** |
| **No repo-map / LLM context product** | `aider` repo map, `CodeAlive` (−45% tokens, RepoQA) | RepoScope computes the graph but never uses it to *compress an agent's context*. That is the highest-value use of the graph. | **M8.1** |
| **No CI-native quality gate** | `SonarQube`, `CodeScene`, `Qodo`, `Semgrep` | The merge gate is specced but is not a first-class product surface. | **M8.2** |
| **No architecture-as-code** | `ArchUnit` (Java), `dependency-cruiser` (`.dependency-cruiser.js`), `Structurizr` | Rules live in TS code. Teams can't own or version them. | **M8.3** |
| **No dead-code / unused-export pruning** | `codegraph`, `Code-Graph-RAG` | — | **M7.2** |
| **No taint / dataflow** | `Code-Graph-RAG` (`FLOWS_` tools) | Security-relevant, but a research-scale feature. | **Deferred** (M9.3 candidate) |
| **No multi-repo / monorepo** | `g rafel`, Sourcegraph, `Code-Graph-RAG` | Enterprise evaluators will ask. | **M9.1** |
| **No SCIP / compiler-grade refs** | `CGC` | Our symbol resolution is name-based → false edges on common names (`get`, `run`, `new`). | **M9.2** — better fix first: **qualified symbol resolution** (M1.4) |

### 11.4 What RepoScope has that nobody else does — protect these

These are the assets. Any change to the plan must not damage them.

| Asset | Unique? | Note |
|---|---|---|
| **Interactive architecture pyramid canvas** | ✅ **Yes** | No 2026 entrant is human-facing. Biggest differentiator. |
| **5-layer architecture taxonomy with colors** | ✅ Mostly | `ArchUnit` has rules but no live map. |
| **Student Onboarding Mode** (curriculum + quizzes + Good First Issues) | ✅ **Yes** | Nothing else does adaptive onboarding. |
| **Voice Code Tours** | ✅ **Yes** | Unique. |
| **Reverse Build Prompt → Scaffold** | ✅ **Yes** | Unique. |
| **Integrated Security Scan** (secrets + breaking + CVE) | Partially | Sonar/Semgrep are deeper but are not in the same product. |
| **Local-first, no PAT required** | ✅ Yes | Matches the "local code graphs are the agent context layer" thesis that `codegraph` popularised — but RepoScope can claim it **and** a visual map. |
| **IBM Bob lineage** | ✅ Yes | Real differentiator *in this hackathon*. |

---

## 12. New milestones (M7–M10)

These slot into the sprint plan without disturbing Part I. **M7 and M8 are Sprint-2/3
dependencies** — they improve existing work rather than sitting beside it.

### Milestone 7 — Graph Intelligence Quality  *(Sprint 2, extends M1)*

#### 7.1 PageRank centrality replacing the ad-hoc score  ⭐ HIGHEST LEVERAGE

**Problem.** `GraphView.tsx:187` scores a file as `incoming × 2 + outgoing`. That is a crude
degree heuristic. It mis-ranks hubs that are imported a lot but are leaves, and it cannot
distinguish "important entry point" from "popular leaf." `aider` proved PageRank on the symbol
graph is the right primitive for exactly this use case, and it is what `codegraph` uses to
build its repo map.

**Implementation.**
1. `backend/graph_analysis.py` — new module.
   - `pagerank_scores(graph) -> dict[node_id, float]` over the `imports` + `calls` edges
     (directed; `networkx` 3.6.1 is installed and `nx.pagerank` verified working).
   - `betweenness_centrality(graph)` for "on the critical path" nodes.
   - `strongly_connected_components(graph)` for cycle detection (7.3).
2. Compute **server-side** in `build_graph_from_repo()` and attach to every node:
   `pagerank`, `in_degree`, `out_degree`, `betweenness`.
3. The frontend uses `node.data.pagerank` for pyramid row assignment instead of
   `scoreNode()`. **Keep `scoreNode()` as the fallback** when `pagerank` is absent, so the
   existing golden screenshots and the no-graph path keep working.
4. Expose `pagerank` in the `reposcope://graph/summary` MCP resource and in
   `get_architecture_overview` ("top hubs" becomes *defensible*).

**Why it matters beyond ranking.** PageRank is the **repo map**. It answers "given this task,
which files matter?" — the exact question every coding agent asks. This becomes M8.1's engine.

**Acceptance.**
- [ ] Pyramid row assignment uses PageRank when available.
- [ ] Every node carries `pagerank`, `in_degree`, `out_degree`.
- [ ] Ranking is **stable across runs** (deterministic tie-breaking by node id).
- [ ] The "top central hubs" MCP resource lists nodes by PageRank, with the value included.
- [ ] `scoreNode()` fallback path still renders identically when PageRank is absent.

#### 7.2 Dead-code & unreachable-symbol detection

- Entry points = nodes with in-degree 0, plus `main`/`__main__`/route handlers/`app.ts`/
  `index.ts`/`cmd/*` — language-specific, in `backend/parsers/registry.py`.
- Walk `calls` + `imports` edges from every entry point.
- Anything **not reachable** = dead code candidate.
- Report as a separate node type `dead` (do not delete — RepoScope should *show* the dead code,
  with a "this is unreachable" badge; that is a genuinely useful visual).
- Surface in the MCP tool `get_architecture_overview` → `dead_code` count, and as a
  `reposcope://dead-code` resource.
- **Caveat to state honestly in the UI:** reachability is a *heuristic* (static analysis with
  no dynamic dispatch resolution). Label it "unreachable (static estimate)", never "dead code."

**Acceptance.**
- [ ] Reachability computed from real entry points, not from "row 1".
- [ ] ≥95% precision on the fixture repo (hand-labelled).
- [ ] UI labels it as an estimate, never as a certainty.

#### 7.3 Cycle detection  ⭐ closes a spec hole

The v2.0 architecture diagram lists "Cyclic Dep Detection" under Intelligence & Analysis, but
**no milestone implements it**. `Madge` and `dependency-cruiser` exist *only* for this. It is
cheap and high-signal.

- `networkx.strongly_connected_components()` on the directed import graph
  (verified working — needs a `DiGraph`, not `Graph`).
- Report each cycle: member files, cycle length, and whether it spans layers
  (a cycle crossing `storage` → `client` is an architecture violation; a cycle inside one
  layer is a code smell).
- New MCP tool `find_dependency_cycles()`.
- PR bot: flag **newly introduced** cycles as a merge-gate condition.

**Acceptance.**
- [ ] Cycles detected on a fixture with a known 3-node cycle.
- [ ] Self-loops and 2-node cycles both caught.
- [ ] PR bot distinguishes pre-existing from newly-introduced cycles.

#### 7.4 Semantic search  ⚠️ OPTIONAL — read the caveat

`Code-Graph-RAG` and `tokensave` have vector search; RepoScope does not. But the research is
explicit: the CoREB benchmark found near-zero nDCG@10 for embeddings on **short** queries, and
the recommended escalation order is **lexical → structural → graph → semantic last**. Also,
embeddings need a model dependency, a vector store, and per-language chunking — expensive.

**Decision: implement lexical + structural + graph search now; add embeddings only if a
benchmark shows they beat it.** Concretely:
- Add `search_code(pattern, mode)` MCP tool with modes: `literal` (ripgrep), `structural`
  (ast-grep via `ast-grep-cli` 0.51.0 / `ast-grep-py` — installable, not yet installed), and
  `symbol` (the graph).
- If semantic search is later added, make it **pluggable and optional**, with a local ONNX
  embedding model, and never a hard dependency.

**Acceptance.**
- [ ] `search_code` with three modes; structural mode requires no embedding model.
- [ ] Search results return `file:line` with the matching symbol — the format agents need.

---

### Milestone 8 — Context Engineering & CI  *(Sprint 3 + Sprint 6)*

#### 8.1 Repo map & token-efficiency measurement  ⭐ THE 2026 BUYING TRIGGER

**Why this is the highest-value non-graph feature.** The entire 2026 market has converged on
one number: *how many tokens does an agent burn to understand this repo?* Measured claims now
range from `codegraph` 62% fewer tokens, `Repomix` ~70%, `grepai` 97%, `GitNexus` 88% fewer
tool calls. **RepoScope currently publishes nothing.** This is both a feature and the single
best hackathon talking point, because it is a **falsifiable, reproducible measurement** of
RepoScope's own value.

**Implementation.**
1. `backend/repo_map.py` — build a compact, LLM-ready map of the repo:
   - Rank files by PageRank (M7.1).
   - For each, emit `path :: symbol(signature) :: layer`.
   - Fit to a token budget (default 8k) — drop lowest-ranked files first.
   - Output a plain-text map in `aider`'s proven format, plus a JSON variant.
2. `backend/token_metrics.py` — count tokens (a small BPE-free estimator is fine; make the
   tokenizer pluggable). Emit:
   - `full_context_tokens` — the whole repo read into the prompt.
   - `repo_map_tokens` — RepoScope's map.
   - `reduction_pct`.
3. New MCP tool `get_repo_map(token_budget)` and resource `reposcope://repo-map`.
4. **A "Context savings" readout in the UI** and in the PR comment:
   *"RepoScope context: 1,847 tokens vs 41,200 for the full repo — 95.5% reduction."*
5. Publish a **public benchmark**: run RepoScope vs. full-context baseline over N public repos
   and post the table in the README. This is the artefact that makes the claim credible.

**Acceptance.**
- [ ] `get_repo_map(budget=8000)` returns ≤ budget tokens, ranked by PageRank.
- [ ] Reduction % computed and displayed; reproducible across runs.
- [ ] Public benchmark over ≥10 repos, numbers in the README, script committed under
      `benchmarks/`.

#### 8.2 CI-native quality gate

The merge gate is currently a line in a workflow. Make it a product surface.

- A **GitHub Action** (`reposcope-action`) — a real repo, versioned, installable by
  `uses: adityapatel5912/reposcope-action@v2`.
- Outputs: risk score, blast radius, new cycles, broken contracts, boundary violations,
  missing tests, token savings.
- **SARIF output** — SARIF is the GitHub code-scanning standard. Emitting SARIF means RepoScope
  findings appear **inline on the PR diff** in GitHub's UI, where reviewers already look. This
  is the single highest-leverage CI detail and it is currently absent.
- A **badges endpoint** for the README: risk score + savings %.
- Baseline mode: compare against the base branch, report only *new* issues (this is what makes
  a gate usable — a gate that flags pre-existing debt gets disabled by every team).

**Acceptance.**
- [ ] Action installs and runs on a sample repo.
- [ ] SARIF 2.1.0 valid; findings render inline on a PR.
- [ ] Baseline mode reports only new findings.
- [ ] Merge gate blocks a PR exceeding the threshold — and passes a clean one.

#### 8.3 Architecture-as-code  ⭐ the defensible PR-bot angle

`ArchUnit`, `dependency-cruiser`, and `Structurizr` all put rules in a **versioned config
file**. RepoScope's rules live in TypeScript (see Correction C6) — unversionable, unshareable.

- `.reposcope.yml` at the repo root:
  ```yaml
  version: 1
  layers:
    - name: domain
      include: ["src/domain/**"]
    - name: infra
      include: ["src/infra/**"]
  rules:
    - id: no-domain-to-infra
      from: domain
      to: infra
      severity: error
    - id: no-ui-to-data
      from: client
      to: storage
      severity: error
  ignore: ["**/generated/**", "**/*.d.ts"]
  ```
- `backend/arch_rules.py` loads and evaluates it; **the frontend consumes the same rules via
  `GET /api/arch/rules`** (satisfies C6 completely).
- `explain_architectural_rule` (M3) becomes meaningful: it now checks *the team's actual
  declared boundaries*, not RepoScope's guesses.
- The PR bot checks **boundary violations in the diff** — the angle no AI reviewer covers.

**Acceptance.**
- [ ] `.reposcope.yml` parsed and enforced; invalid config → clear error, no crash.
- [ ] `GET /api/arch/rules` is the single source for frontend + MCP + CI.
- [ ] PR bot flags a boundary violation introduced by the diff, naming both files and the rule.

---

### Milestone 9 — Enterprise & Depth  *(Sprint 6/7 — after the demo-critical path)*

#### 9.1 Multi-repo / monorepo support
- Detect workspace roots: `pnpm-workspace.yaml`, `package.json` workspaces, `go.work`,
  `Cargo.toml` workspaces, `uv`/`poetry` workspaces, `nx.json`, `turbo.json`.
- Index each package as a sub-project; build cross-package edges; show a **repo-level map**
  with expandable packages.
- Enterprise evaluators ask this in the first ten minutes. It is a credibility item.

#### 9.2 Qualified symbol resolution  (fixes M1.4's weakness)
Name-based resolution produces false edges when two files define `get`/`run`/`new`. Escalate:
1. name + same module (**ship in M1**),
2. name + imported-from (**ship in M1**),
3. name + unique global (**ship in M1**),
4. **qualified** — match the receiver type when inferable (**M9**),
5. **SCIP indexers** — compiler-grade (**future**; `CGC` does this).

#### 9.3 Lightweight taint analysis
Source → sink through assignments, calls, and returns, restricted to the file's call graph.
Feeds the existing security scanner. `Code-Graph-RAG` has this as `FLOWS_` tools. High value,
moderate cost — a strong "beyond the spec" item if Sprint 6 has room.

#### 9.4 Ownership overlay
`git log --format='%an'` per file → primary owner. Combine with churn → "hotspot owned by X."
Pairs with `CODEOWNERS`. `repowise` ships ownership + git history on one map.

---

### Milestone 10 — PR Bot Positioning Shift  *(replaces part of M5)*

**Reposition, don't just upgrade.** Competing with CodeRabbit/Greptile on "catches bugs" is
losing. Own **architecture governance**:

| RepoScope's PR bot | AI reviewers (CodeRabbit etc.) |
|---|---|
| Does this PR violate a **declared architecture boundary**? | Is this code buggy? |
| Did this PR **break a contract** that has real consumers? | Is this change correct? |
| Did this PR **introduce a dependency cycle**? | — |
| Which **consuming files** must be regression-tested? | Where should I add tests? |
| How much of the repo's context does an agent need to review this? | — |

**This is a different product.** It is the only column no AI reviewer competes in.

Implementation: merge M5's contract diff + M7.3's cycle detection + M8.3's boundary rules +
M8.1's savings number into a single **Architecture Impact** report, and drop generic
"find bugs" language from the bot's identity entirely.

---

## 13. Sharpening items — small changes, large effect

| # | Change | Why | Effort |
|---|---|---|---|
| S1 | **Publish the numbers.** Token reduction, index time, traversal latency, edge precision/recall | Every competitor does. RepoScope does not. It is the cheapest credibility win available. | S |
| S2 | **Deterministic everything.** Fixed seeds, sorted iteration, stable tie-breaks → the same repo always yields the same graph | RepoScope's outputs feed CI gates and MCP tools. Non-determinism makes them untrustworthy | S |
| S3 | **Show the evidence for every claim** — "blast radius from 47 import + 12 call edges" | Auditable beats authoritative. Makes the AI answers defensible | S |
| S4 | **README "Architecture badge"** — SVG showing layers, cycles, hotspots, savings | Recruiter-facing, judges see it in 2 seconds | S |
| S5 | **First-run experience** — auto-detect the repo, auto-index, land on a populated graph | Every judge will type their own repo URL. It must work first try | M |
| S6 | **A `demo/` seed repo** — small, multi-language, with a deliberate cycle and a hot file | Judges explore; a seeded repo shows the features instantly | S |
| S7 | **Delete `apps/web/`** | Dead directory, ~100MB of `node_modules`, confuses tooling | S |
| S8 | **Remove the dead `codebase-memory-mcp` path** (`backend/mcp_client.py:22`) | The binary does not exist → silent no-op on every request. Replace with the local graph builder | S |
| S9 | **OpenAPI docs + a hosted `/mcp` endpoint** | FastAPI already serves `/docs` — surface it. MCP tools become self-documenting | S |
| S10 | **Keyboard-first graph navigation** — `/` to search, arrows to move, `Enter` to open in editor | Power-user ergonomics; also accessibility | M |
| S11 | **Dark mode parity** (if not already shipped) | Judge screens are often dark | S |
| S12 | **A `reposcope.json` schema + `repo:init` command** | The "architecture as code" entry point | S |
| S13 | **Privacy statement + "no source leaves your machine" mode** | The #1 trust objection for a code tool | S |
| S14 | **Rate-limit & cost guardrails on LLM features** | BYOK already rotates keys; add per-session spend caps | S |

---

## 14. Revised sprint plan (Part II additions folded in)

| Sprint | Focus | Part II additions |
|---|---|---|
| **Sprint 0** | Foundation | + `.reposcope.yml` schema & loader (M8.3) · + `backend/graph_analysis.py` skeleton · + `benchmarks/` harness (S1) |
| **Sprint 1** | Tree-sitter engine | + qualified symbol resolution tiers 1–3 (M9.2) · + entry-point detection per language (M7.2) |
| **Sprint 2** | Graph UX & hotspots | + **M7.1 PageRank** (replaces the ad-hoc score) · + **M7.3 cycle detection** · + **M7.2 unreachable detection** · + **M8.3** rules from `.reposcope.yml` drive the layer taxonomy |
| **Sprint 3** | Local mode & indexing | + **M8.1 repo map + token metrics** · + `get_repo_map` MCP tool |
| **Sprint 4** | MCP server + IDE links | + `find_dependency_cycles` tool · + `reposcope://repo-map` + `reposcope://dead-code` resources · + **M8.3** `explain_architectural_rule` reads the team's rules |
| **Sprint 5** | IDE extension | + dead-code / cycle badge in the status bar |
| **Sprint 6** | PR Bot 2.0 | + **M10 repositioning** · + **M8.2 SARIF + baseline mode** · + **M8.3** boundary-violation checks |
| **Sprint 7** | Scale-out | + **M9.1** monorepo · + **M9.2** tier-4 qualified resolution · + **M9.3** taint · + **M9.4** ownership |

**Sprint 2 grows.** M7.1 (PageRank) changes how every downstream ranking works — pyramid rows,
hotspots, onboarding curriculum, repo map, MCP "top hubs". Doing it *after* those are built
means redoing them. PageRank belongs in Sprint 2, immediately after the parser lands.

---

## 15. Revised definition of done (Part II)

Adds to Section 8:

- [ ] PageRank replaces the ad-hoc score for pyramid ranking, with the fallback intact.
- [ ] Every node carries `pagerank`, `in_degree`, `out_degree`.
- [ ] Cycle detection works and is exposed via MCP + PR bot + UI.
- [ ] Unreachable-symbol detection ships, labelled as a static estimate.
- [ ] `get_repo_map(token_budget)` returns a budgeted, PageRank-ranked map.
- [ ] Token reduction is measured, displayed in the UI, and published in the README.
- [ ] A public benchmark over ≥10 repos with a committed harness.
- [ ] `.reposcope.yml` is the single source of architecture rules for UI, MCP, and CI.
- [ ] SARIF 2.1.0 output renders inline on a GitHub PR.
- [ ] The merge gate reports only *new* findings (baseline mode).
- [ ] The PR bot is positioned on architecture governance, not bug-hunting.
- [ ] The same repo always produces an identical graph (determinism test).
- [ ] `apps/web/` deleted; the dead `codebase-memory-mcp` path removed.
- [ ] FastAPI `/docs` surfaced in the README.

---

## 16. Revised risk register (Part II additions)

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R13 | Competitors ship the same MCP server faster (`codegraph` already has one at ~68K stars) | **High** | Do not compete on MCP alone. Compete on **human-facing map + MCP**, and on **architecture governance** (M10). Ship the visual side first |
| R14 | Token-reduction claims are unverified → credibility damage if a judge checks | **High** | Publish the harness and the numbers (S1). Never claim a figure the harness does not reproduce |
| R15 | PageRank changes the pyramid → existing screenshots/docs go stale | Medium | Regenerate `docs/screenshots/graph.png` and update `FEATURES.md` in the same PR |
| R16 | Semantic search scope-creep into embeddings | Medium | M7.4 makes embeddings **optional and benchmark-gated**; ship lexical + structural first |
| R17 | Monorepo support is a large surface | Medium | Sprint 7 only; detect workspaces → sub-projects, no cross-repo federation in v2.0 |
| R18 | SARIF output is malformed → GitHub silently rejects it | Low | Validate against the SARIF 2.1.0 schema in CI |
| R19 | Too many additions dilute the demo | **High** | **Part II is not all-or-nothing.** The minimum demo-critical set is **M7.1 + M8.1 + M8.3 + M10**. Everything else is optional |

---

# PART III — Verification & QA Discipline

> Added per explicit request: *everything must be tested by opening localhost, taking
> screenshots, and analysing the result like proper QA — using the MCP servers.*

---

## 17. Why this is a milestone, not a chore

### 17.1 The evidence — a prior audit that was never turned into a gate

RepoScope already has a browser-QA history. It lives in `.playwright-mcp/` (2026-09-26) and it
contains **13 console logs, 100+ page snapshots, and screenshots** from a manual Playwright audit
of the running app on `http://localhost:5173`.

Two facts make this a milestone rather than a chore:

**① Real bugs were found this way — the kind unit tests cannot find.**

| Observed in the console logs | Why unit tests miss it |
|---|---|
| `<circle> attribute cx: Expected length, "NaN"` (×318 in one session) | React SVG geometry error — only exists in a rendered browser DOM |
| `<pattern> attribute x/y: Expected length, "NaN"` | Same class — SVG defs, not application state |
| `Failed to load resource: 404 → /api/tour/generate` | Route-level failure, invisible to unit tests that call handlers directly |
| `Password field is not contained in a form` | DOM semantics — a11y defect, only observable in the live document |

**② The audit produced no lasting protection.**
`.playwright-mcp/` is **gitignored** (`.gitignore`), so every artefact — the console evidence, the
snapshots, the screenshots — is invisible to the repo and to any future agent. The defects were
fixed by hand in commits like `fix(ui): polish AI assistant response tables…`, and **nothing
prevents them from coming back**. There is no e2e suite, no Playwright dependency, no test script
in `frontend/package.json` (verified: `dev`, `build`, `preview` only), and no CI workflow that
opens a browser.

### 17.2 The principle

> **Unit tests prove functions work. Only opening localhost proves the product works.**

RepoScope's judge-facing failure mode is not a wrong function — it is a **blank canvas, a broken
route, a NaN in the SVG, or a console full of errors during a live demo**. Every one of those
passes a 100%-green pytest suite. The gate must therefore be a *browser* gate.

### 17.3 The four-layer gate — "Definition of Verified" (DoV)

No feature is **Done** until it clears all four layers.

| Layer | Tool | Target | Proves |
|---|---|---|---|
| **L1 Unit** | `pytest` | functions in isolation | logic is correct |
| **L2 Contract** | `httpx` → live `uvicorn` | `127.0.0.1:8010` | the API contract holds on a running server |
| **L3 Journey** | Playwright | real Chromium, real DOM | the user flow works end-to-end |
| **L4 Visual + Console** | Playwright screenshots + chrome-devtools MCP | rendered pixels + browser console | it **looks** right **and** is error-free |

**L4 is the gate that did not exist.** L3 alone passes while the console fills with React key
warnings, unhandled rejections, 404 assets, and CORS failures.

### 17.4 Hard rules

| Rule | Detail |
|---|---|
| **R-QA1** | **Zero console errors** on every journey. `console.error` + `pageerror` + unhandled rejections must be empty. |
| **R-QA2** | **Zero unexpected HTTP failures.** No 4xx/5xx on any request the app initiates, except explicitly-declared intents (e.g. a deliberately-missing repo → 404). |
| **R-QA3** | **Every journey commits a screenshot** to `docs/screenshots/v2/<journey>/`. The directory is **not** gitignored — this directly fixes the `.playwright-mcp/` evidence loss. |
| **R-QA4** | **Every journey has a visual-regression baseline** via Playwright `toHaveScreenshot()`. Baselines are committed; updates are explicit (`--update-snapshots`), never automatic. |
| **R-QA5** | **A known-bad whitelist exists and is reviewed.** Each whitelisted console message carries an inline justification. An unexplained console error fails the build. |
| **R-QA6** | **QA is a gate in every sprint, not a phase at the end.** A sprint cannot be closed with an untested feature. |
| **R-QA7** | **MCP servers are instruments, not the gate.** The committed Playwright suite is the gate; MCP servers are how a human or agent investigates and drafts. |

---

## 18. The QA harness

### 18.1 File manifest

```
frontend/playwright.config.ts     baseURL, webServer, projects, screenshot policy
frontend/tests/e2e/               journey specs (one file per journey group)
frontend/tests/e2e/helpers.ts     console/network collectors + screenshot helper
scripts/qa.py                     the runner: boot → wait → test → collect → report
.github/workflows/qa.yml          CI: unit → contract → journey → artefact upload
docs/screenshots/v2/              committed screenshot evidence (NOT gitignored)
docs/QA_REPORT.md                 the standing QA report — what is covered, what is not
```

### 18.2 The runner — `scripts/qa.py`

```
1. Start backend:  uvicorn main:app --host 127.0.0.1 --port 8010
   (env: REPOSCOPE_QA=1 → deterministic clock, no outbound calls, isolated data dir)
2. Start frontend: npm --prefix frontend run dev  (127.0.0.1:5173)
3. Wait for GET http://127.0.0.1:8010/api/health == 200   (timeout 60s)
4. Wait for GET http://127.0.0.1:5173                      (timeout 60s)
5. Run: npx playwright test --config frontend/playwright.config.ts
6. Collect per-test: console messages, page errors, failed requests, screenshots
7. Write qa-report/index.html + qa-report/results.json
8. Exit non-zero if any test failed OR any un-whitelisted console/network error occurred
```

**`REPOSCOPE_QA=1` matters.** It makes the run hermetic: no GitHub API calls, no LLM provider
calls, no writes to `data/repo_state.json`, a fixed seed, and a fixed clock. A QA run that
depends on the network is a QA run that fails for the wrong reason.

### 18.3 Console & network collection — `frontend/tests/e2e/helpers.ts`

```ts
// Attach to every page: console errors, unhandled exceptions, failed requests.
// Collect, then assert empty at test end (minus the reviewed whitelist).
export function attachErrorCollector(page: Page) { /* console, pageerror, response */ }
export const WHITELIST: Array<{ pattern: RegExp; reason: string }> = [ /* reviewed */ ];
```

### 18.4 The smoke matrix

Journeys are the unit of verification. Each maps to a user-visible capability and must produce
a screenshot.

| # | Journey | Introduced | Notes |
|---|---|---|---|
| J01 | Load repo → graph renders (node count > 0, no blank canvas) | **now** | The single most important assertion |
| J02 | Click node → drawer opens with correct path/size/symbols | **now** | |
| J03 | Ask a question → SSE streams an answer with citation pills | **now** | Needs a stubbed LLM in `REPOSCOPE_QA=1` mode |
| J04 | Impact analysis → risk score + direct/transitive rings render | **now** | |
| J05 | Code tour → steps render, graph pans, step badges advance | **now** | |
| J06 | PR bot → markdown comment preview renders (no post) | **now** | |
| J07 | Student mode → 3 levels + quizzes render | **now** | |
| J08 | Security scan → flags render with severity ordering | **now** | |
| J09 | Export PNG + SVG → downloads produced, non-zero size | **now** | |
| J10 | File tree → filter narrows the list | **now** | |
| J11 | BYOK → provider set + status bar reflects it | **now** | |
| J12 | **Local mode** → `reposcope run .` boots, graph renders, file edit updates graph **without reload** | Sprint 3 | The differentiator |
| J13 | **MCP server** → stdio handshake, `tools/list`, one real tool call | Sprint 4 | Via a stdio client, not HTTP |
| J14 | **IDE deep link** → node click produces the exact expected URI per editor | Sprint 4 | Intercept the navigation; assert the URI string |
| J15 | **Call edges** → graph renders `calls` edges after the parser rewrite | Sprint 1 | Regression for the C10 contract |
| J16 | **Clusters** → expand/collapse preserves the pyramid when toggled off | Sprint 2 | |
| J17 | **Churn heatmap** → hotspot rings render and are visually distinct from layer fill | Sprint 2 | |
| J18 | **Cycles** → cycle list renders, matches the API result | Sprint 2 | |
| J19 | **Repo map** → budgeted map renders, token reduction % shown | Sprint 3 | |
| J20 | **PR boundary violation** → flagged in the PR comment | Sprint 6 | |
| J21 | **SARIF** → valid against the 2.1.0 schema | Sprint 6 | |
| J22 | **50k-file traversal** → latency budget met | Sprint 7 | |

**J15–J22 are contract regressions.** They exist to prove the parser rewrite and the new engines
did not break what already worked.

### 18.5 The role of each MCP server

| MCP server | Role in QA | Explicitly **not** for |
|---|---|---|
| **Playwright** (`@playwright/mcp`) | Interactive exploration during development; triaging a failure by hand; **drafting the first version of a journey spec** from a recorded interaction | The CI gate. CI must run the committed suite, not an agent |
| **chrome-devtools** | Console error triage; network waterfall inspection; performance tracing; catching React key warnings, unhandled rejections, oversized payloads, and CORS failures that a screenshot cannot show | — |
| **Tavily** | Resolving **expected** behaviour where the spec is ambiguous — the correct `vscode://` URI form, current MCP transport wording, correct ReactFlow LOD thresholds, GitHub REST shapes for webhooks; and competitor-parity checks | — |

**The distinction that matters:** MCP servers are how a human or an autonomous agent
*investigates*. The committed Playwright suite is how the build *gates*. Using an MCP agent as
the CI gate would make every run non-deterministic and non-reproducible — the opposite of QA.

### 18.6 Defect severity policy

| Sev | Definition | Gate |
|---|---|---|
| **P0** | App fails to load, graph is blank, unhandled crash, console errors on the primary journey | **Blocks the demo.** Must be zero before the demo rehearsal |
| **P1** | A shipped feature is broken with no workaround | Blocks the sprint from closing |
| **P2** | Visual glitch, overlapping elements, wrong copy, incorrect colour | Fix before the demo |
| **P3** | Polish, niceties | Backlog |

### 18.7 The demo rehearsal — the final gate

Before any demo, run the three-act script (§9) under Playwright with a real MCP client:

| Act | Assertion | Screenshot |
|---|---|---|
| 1 — `reposcope run .` | Graph renders on a local repo; **no outbound request to GitHub** (assert on the network log) | `docs/screenshots/v2/demo-act1-local/` |
| 2 — agent queries MCP | The agent's answer contains a `file:line` citation and a risk score that match the MCP tool's raw output | `docs/screenshots/v2/demo-act2-mcp/` |
| 3 — node → editor | The exact expected editor URI is produced and invoked | `docs/screenshots/v2/demo-act3-editor/` |

**Act 2's assertion is the important one:** it proves the agent's answer was *derived from the
graph*, not hallucinated — by comparing the agent's citation against the tool's raw output.

**P0 and P1 must both be zero.**

---

## 19. Milestone 11 — QA harness, and its sprint integration

### 19.1 Sprint placement

| Sprint | QA work |
|---|---|
| **Sprint 0** | Harness skeleton: `scripts/qa.py`, `playwright.config.ts`, `helpers.ts`, the collector + whitelist, the health-check journey (J00), CI workflow. **Journey list written; J01–J11 specified but not yet automated.** |
| **Sprint 1** | J15 (call edges) — the C10 contract regression. Plus J01–J11 automated as the baseline. |
| **Sprint 2** | J16, J17, J18 |
| **Sprint 3** | J12, J19 |
| **Sprint 4** | J13, J14 |
| **Sprint 5** | Extension manual checklist (a VS Code host cannot be driven by Playwright) — verified by a documented manual run + committed screenshots |
| **Sprint 6** | J20, J21 |
| **Sprint 7** | J22 |

### 19.2 Definition of done (additions)

- [ ] `scripts/qa.py` boots both servers, runs the suite, and exits non-zero on any failure.
- [ ] `REPOSCOPE_QA=1` makes the run hermetic — no outbound network, fixed seed, isolated state.
- [ ] Every journey asserts **zero** un-whitelisted console errors and **zero** unexpected HTTP failures.
- [ ] The whitelist has an inline justification per entry.
- [ ] Screenshots for every implemented journey are committed under `docs/screenshots/v2/`.
- [ ] Visual-regression baselines are committed; updates are explicit only.
- [ ] `.github/workflows/qa.yml` runs unit → contract → journey and uploads artefacts.
- [ ] `docs/QA_REPORT.md` states what is covered and — explicitly — what is **not** covered.
- [ ] The demo rehearsal (J-act1/2/3) passes with P0 = 0 and P1 = 0.
- [ ] The prior audit's defect classes are covered by assertions:
      SVG `NaN` attributes, `/api/*` 404s, missing `<form>` around password inputs.

### 19.3 Risk additions

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R20 | QA suite becomes flaky and gets ignored | **High** | Hermetic `REPOSCOPE_QA=1` mode; no live LLM/GitHub calls; no arbitrary sleeps — wait on observable state; quarantine flaky tests loudly instead of silently skipping |
| R21 | Screenshot baselines churn on every UI tweak | Medium | Per-journey baselines, not one global shot; explicit `--update-snapshots`; review baseline diffs in the PR |
| R22 | The QA harness itself is never run | **High** | It runs in CI on every PR — a red suite blocks merge |
| R23 | Playwright adds a heavy dev dependency | Low | `frontend/package.json` devDependency only; CI caches the browser; not in the runtime image |

---

## 20. Agent Prompt G — QA harness (Sprint 0)

```
Role: QA / Test Automation Engineer
Context: RepoScope at D:\Aditya\Hackathon Projects\RepoScope.
         Read C:\Users\Admin\.opencode\plan\reposcope-v2-plan.md Part III (Sections 17-19).
         Part III is BINDING.

Task: Build the browser-QA harness that gates every feature from here on.
      The app currently has NO e2e infrastructure and NO console-error gate. A prior manual
      Playwright audit found real bugs (SVG NaN attributes, /api/tour/generate 404s) that no
      unit test would catch — and its artefacts were gitignored, so nothing prevents regression.

Requirements:
1. frontend/playwright.config.ts
   - testDir: './tests/e2e'
   - baseURL: http://127.0.0.1:5173
   - webServer: boot `npm run dev` (frontend) and `uvicorn main:app --port 8010` (backend),
     env REPOSCOPE_QA=1, reuseExistingServer locally
   - viewport 1600x900 (matches the repo's documented screenshot size)
   - screenshot: 'only-on-failure'; trace: 'retain-on-failure'
   - Add @playwright/test as a DEV dependency of frontend/package.json. NOT a runtime dep.

2. frontend/tests/e2e/helpers.ts
   - attachErrorCollector(page): collects console messages of type 'error', pageerror events,
     and responses with status >= 400
   - WHITELIST: array of {pattern: RegExp, reason: string} — every entry MUST have a reason
   - assertNoErrors(page): fails on any collected error not matching the whitelist
   - A helper to assert "no outbound request to api.github.com" (needed by demo Act 1)

3. frontend/tests/e2e/journeys.spec.ts — implement these journeys:
   - J00 health: GET /api/health returns 200 and the UI mounts (zero console errors)
   - J01 load repo -> graph renders: use the existing demo repo endpoint
     (POST /api/repo/load-demo/{demo_id}, see backend/main.py:407) — assert ReactFlow rendered
     nodes (node count > 0), the canvas is not blank, and assertNoErrors passes
   - J02 click a node -> the node drawer opens
   - J04 impact analysis renders a risk score
   - J09 export -> PNG and SVG downloads are produced with non-zero size
   Each journey: assertNoErrors + a screenshot into docs/screenshots/v2/<journey>/

4. scripts/qa.py
   - Boot backend (127.0.0.1:8010) and frontend (127.0.0.1:5173) if not already running
   - Wait for /api/health == 200 (60s timeout) and for the frontend to serve (60s timeout)
   - Run `npx playwright test --config frontend/playwright.config.ts`
   - Write qa-report/index.html + qa-report/results.json
   - Exit non-zero on any test failure OR any un-whitelisted console/network error
   - Set REPOSCOPE_QA=1: no outbound GitHub calls, no LLM provider calls, isolated state dir,
     fixed seed, fixed clock. A QA run must never depend on the network.

5. .github/workflows/qa.yml
   - jobs: unit (pytest) -> contract (httpx against a live uvicorn) -> journey (playwright)
   - Cache the Playwright browser
   - Upload qa-report/ and docs/screenshots/v2/ as artefacts

6. docs/QA_REPORT.md — what IS covered, and explicitly what is NOT covered.

7. Create docs/screenshots/v2/ and ensure it is NOT gitignored. Verify with `git check-ignore`.
   (.playwright-mcp/ stays ignored — that directory is a different tool's scratch space.)

Verification:
- `python scripts/qa.py` -> exits 0, writes qa-report/, and every journey screenshot exists.
- Break something on purpose (e.g. render a component with a NaN SVG attribute), re-run, and
  show the suite goes RED with a useful message. Then restore it. A gate never observed
  failing proves nothing.
- `git check-ignore docs/screenshots/v2/` -> must print nothing (not ignored).

Deliverable: the diff + the qa.py output + the red/green demonstration.
```

---

## 21. Consolidated sprint plan (Parts I + II + III)

| Sprint | Focus | Part I | Part II | Part III |
|---|---|---|---|---|
| **0** | Foundation & safety net | routers, GraphStore, arch rules, fixtures, golden test | `.reposcope.yml` loader, analysis skeleton, benchmarks scaffold | **QA harness skeleton + health journey + CI** |
| **1** | Tree-sitter engine | `calls` edges, complexity, symbol resolution | qualified resolution, entry points | J15 + baseline J01–J11 |
| **2** | Graph UX & hotspots | clusters, churn, LOD | **PageRank**, cycles, unreachable | J16, J17, J18 |
| **3** | Local mode & indexing | CLI, watcher, incremental index | repo map + token metrics | J12, J19 |
| **4** | MCP server + IDE links | 4 tools, 2 resources, deep links | cycle tool, repo-map resource, team rules | J13, J14 |
| **5** | IDE extension | mini-graph, status bar, CodeLens | dead-code / cycle badge | extension manual checklist |
| **6** | PR Bot 2.0 | contract diff, test stubs, PR chat | **repositioning**, SARIF, boundary checks | J20, J21 |
| **7** | Scale-out | SqliteGraphStore, WebGL | monorepo, taint, ownership | J22 |

**The gate for closing any sprint: the QA suite is green, and every new journey has a committed
screenshot.**

---

## 22. Sprint 0 delivery record

**Status: complete.** Sprint 0 shipped on 2026-10-21. This section records what was actually
built and measured, so the next agent does not re-derive it.

### 22.1 Delivered

| Deliverable | File | Notes |
|---|---|---|
| Backend rule source of truth | `backend/arch_rules.py` | 5 canonical layers, dependency policy, `.reposcope.yml` loader |
| Router package | `backend/api/` | `register_routers(app)`; `routers/arch.py` → `GET /api/arch/rules`; `routers/qa.py` (QA-mode only) |
| GraphStore | `backend/graph_store.py` | `GraphStore` Protocol + `JsonGraphStore`; validates the C10 contract on save |
| Graph analysis | `backend/graph_analysis.py` | PageRank, betweenness, degree, SCC cycles, entry points, reachability, `top_hubs` |
| Local ingest | `backend/repo_loader.py` | `load_local_repo(path)` — no clone, no PAT (also the CLI foundation) |
| Fixtures | `backend/tests/fixtures/` | `multilang/`, `circular/`, `nested/`, `real_small/` (vendored MIT `tomli` 2.5.0) |
| Golden gate | `backend/tests/test_graph_golden.py` | 4 snapshots; explicit regeneration only (`--regen-golden`) |
| Parity gate | `backend/tests/test_arch_rules.py` | Runs the frontend's own rules via `scripts/parity_classify.js`; asserts zero divergence |
| QA harness | `frontend/playwright.config.ts`, `frontend/tests/e2e/`, `scripts/qa.py` | 6 journeys, console/network gate, committed screenshots |
| QA report | `docs/QA_REPORT.md` | What is covered — and explicitly what is not |
| CI | `.github/workflows/qa.yml` | L1 unit → L2 contract → L3 journey |

### 22.2 Verified numbers

| Measure | Value |
|---|---|
| Backend tests | **128 passed** (was 38) |
| QA journeys | **6 passed**, 0 console errors, 0 unexpected HTTP failures |
| Backend line count | 1,123 → 1,131 (the 1,200 cap holds) |
| Layer-rule parity | 90 corpus cases, **0 divergence** between `arch_rules.py` and `layerClassifier.ts` |
| Fixture coverage | 4 repositories, 100 nodes, 86 edges pinned by golden snapshots |
| New runtime deps | `networkx`, `pyyaml` (both already present in the environment) |

### 22.3 Defects found by the safety net

| Severity | Defect | Status |
|---|---|---|
| **P2** | **Duplicate node ids.** Four `__init__` methods in one file collapsed to one id (`func:<rel>:__init__`). Duplicate ids break React list keys and corrupt the graph store. Surfaced by the vendored real-world fixture on day one. | **Fixed** — colliding names now receive a deterministic `@{lineno}` suffix; the id scheme is otherwise unchanged |
| **P2** | **Root node painted under the sticky header.** `fitViewOptions.minZoom` (0.3) was HIGHER than the ReactFlow `minZoom` prop (0.2), so fitView clamped, could not fit a tall pyramid, and centred the overflow — the top 24px sat under the TopBar (`z-50`), clipping the root node and making it unclickable. | **Fixed** — the fit-view floor now matches the prop; guarded permanently by journey J05 |
| **P2** | **Mojibake in the UI.** A PowerShell `Get-Content`/`Set-Content` round-trip re-encoded `GraphView.tsx` through Windows-1252, so the separator in the graph title rendered as two characters instead of a middle dot. Invisible to unit tests and to the console gate — only a human reading the screenshot caught it. | **Fixed** — file restored from git and re-edited; `backend/tests/test_repo_encoding.py` now fails the build on any double-encoded file |
| **P2** | **The node drawer covered the LAYERS legend.** Both were `absolute top-4 right-4`; the drawer (z-10) painted over the legend (z-5) and cut it in half. | **Fixed** — the legend yields while a node is selected and returns when the drawer closes |
| **P3** | **The Repository card showed "—" for NODES and EDGES.** The graph counts were never copied into the repo info, on either the load path or the mount path. | **Fixed** — counts are taken from the graph itself |
| **P3** | The ReactFlow canvas overlaps the header by 6px. Cosmetic — the canvas background sits behind the header's bottom edge. | ⬜ Not fixed (Sprint 0 scope) |

### 22.4 Frontend changes made in Sprint 0

| Change | Why |
|---|---|
| `App.tsx` — mount-time pickup of an already-loaded repo | **Required for local CLI mode.** `reposcope run .` loads the repo server-side, so the browser must show it on open instead of waiting for a GitHub URL. Previously `getGraph()` ran only after a form submission. |
| `GraphView.tsx` — shared `FIT_VIEW_OPTIONS` constant | One place for the fit-view settings; the floor bug lived in three duplicated literals |
| `vite.config.ts` — configurable API proxy target | The QA harness runs its own backend on :8010; the proxy target defaults to :8000 so normal dev is unchanged |

### 22.5 Open items carried into Sprint 1

- The frontend still holds a copy of the layer rules. The parity test enforces equivalence; migrating the frontend to consume `GET /api/arch/rules` is a Sprint 1 task.
- Golden snapshots live in `backend/tests/golden/`, **not** inside the fixture directories — a snapshot stored inside a fixture becomes a graph node and makes the test self-referential. This bit us and is now documented in the test file.
- Visual-regression baselines (`toHaveScreenshot()`) are specified but not yet wired up — see `docs/QA_REPORT.md`.
- The ReactFlow canvas overlaps the header by 6px (cosmetic, P3, not fixed).

---

## 23. Sprint 1 delivery record — the Tree-sitter polyglot engine

**Status: complete.** Sprint 1 shipped on 2026-10-21.

### 23.1 Delivered

| Deliverable | File | Notes |
|---|---|---|
| Parser contract | `backend/parsers/base.py` | `Symbol`, `Import`, `CallSite`, `ParseResult`, the `LanguageParser` protocol, and the cyclomatic-complexity counter |
| Python parser | `backend/parsers/python.py` | Tree-sitter queries; absolute and relative imports with their bound names |
| ECMAScript parsers | `backend/parsers/typescript.py` | TypeScript, TSX, and JavaScript — separate query sets, because a query naming a node type the grammar lacks fails to compile |
| Go parser | `backend/parsers/go.py` | Functions, methods (with their receiver type), and types |
| Rust parser | `backend/parsers/rust.py` | Functions, structs, enums, traits, and `impl` blocks |
| Registry | `backend/parsers/registry.py` | Extension to parser; a missing grammar degrades to "no parser", never a crash |
| Graph integration | `backend/graph_builder.py` | Symbols, imports, and call sites become nodes and edges; the C10 contract is unchanged |
| Call resolution | `backend/graph_builder.py` | Same file → imported module → unambiguous global, in that order |

### 23.2 Verified numbers

| Measure | Before | After |
|---|---|---|
| Backend tests | 128 | **161** |
| Languages parsed by AST | Python only (`ast`) | Python, TypeScript, TSX, JavaScript, Go, Rust |
| Symbol nodes with a line number | Python only | **all languages** |
| `calls` edges | none | 5 (multilang) · 7 (circular) · 3 (nested) · **75** (real_small) |
| Graph determinism | not measured | **verified across 3 separate processes per fixture** |
| Duplicate node ids | 0 | 0 |
| Dangling edges | 0 | 0 |

### 23.3 Three bugs the new engine surfaced

| Severity | Defect | Status |
|---|---|---|
| **P2** | **Calls inside same-named symbols were mis-attributed.** Four `__init__` methods in one file all matched the name `__init__`, so every call inside them was attributed to the first one. The parser now carries the enclosing symbol's **line**, which disambiguates them. | **Fixed** |
| **P2** | **Go types were not extracted.** The query captured `type_declaration` while the name node's parent was the inner `type_spec`, so the name never matched its definition. | **Fixed** — the query captures `type_spec` |
| **P3** | **Go method receiver types were lost.** The receiver type sits at `parameter_list > parameter_declaration > type_identifier` — deeper than a direct-child search reaches. | **Fixed** — `find_descendant_of_type` added |

### 23.4 The call graph found cycles the import graph could not

The `circular` fixture now yields **four** cycles, not two: the two file-level loops, and the two symbol-level loops underneath them.

```
file level    alpha.py  -> beta.py  -> gamma.py  -> alpha.py
symbol level  alpha_value -> beta_value -> gamma_value -> alpha_value
```

The symbol-level cycles name the exact functions that form the loop — which is what makes a cycle report actionable rather than noise. The import-only graph could never show this.

### 23.5 API notes for the next agent

These are the tree-sitter 0.25 facts that cost time to discover. All are recorded in the source.

- **`Query.captures()` no longer exists.** Use `QueryCursor(Query(lang, q)).captures(node)`, which returns a `dict[str, list[Node]]`.
- **Several grammars have no field names.** `attribute` (Python), `member_expression` (TS/JS), `selector_expression` (Go), and `field_expression` (Rust) expose no `object:`/`property:`/`operand:`/`field:` fields. The receiver and the name are read from the node's children instead.
- **`import_from_statement` has no `module:` field** in tree-sitter-python. The module is the child before the `import` keyword.
- **A query naming a node type the grammar lacks fails to compile** — hence separate TypeScript and JavaScript query sets.

### 23.6 Open items carried into Sprint 2

- The frontend still holds a copy of the layer rules; the parity test enforces equivalence. Migrating it to consume `GET /api/arch/rules` is still outstanding.
- `calls` edges are produced and scored by the frontend, but the pyramid renders only parent-child edges. Rendering call edges as arcs is a Sprint 2 decision.
- The graph is now richer, so the pyramid's row ranking needs PageRank (M7.1) to stay defensible.

---

## 24. Sprint 2 delivery record — graph intelligence and graph UX

**Status: complete.** Sprint 2 shipped on 2026-10-21.

### 24.1 Delivered

| Deliverable | File | Milestone |
|---|---|---|
| Git churn, co-change coupling, ownership | `backend/git_history.py` | 1.3 |
| Churn × centrality hotspot score | `backend/git_history.py` | 1.3 + 7.1 |
| Analysis endpoints | `backend/api/routers/analysis.py` | 1.3, 7.1–7.3 |
| PageRank attached to every node | `backend/graph_builder.py` → `graph_analysis.attach_analysis` | 7.1 |
| PageRank pyramid ranking | `frontend/src/components/GraphView.tsx` | 7.1 |
| Churn heatmap overlay + spectrum | `frontend/src/api/analysis.ts`, `GraphView.tsx`, `graph/LayerNode.tsx` | 1.3 |
| Architecture cluster view | `frontend/src/components/GraphView.tsx` (`buildClusterGraph`) | 1.2 |
| Insights panel | `frontend/src/components/InsightsPanel.tsx` | 7.1–7.3 |
| Level-of-detail culling | `frontend/src/styles/app.css`, `GraphView.tsx` | 1.4 |

### 24.2 Verified numbers

| Measure | Value |
|---|---|
| Backend tests | **171 passed** (was 161) |
| QA journeys | **9 passed** (was 6) — J06, J07, J08 added |
| Analysis endpoints | 4 live: `/api/analysis/{hubs,cycles,unreachable,hotspots}` |
| Churn measured on this repo | 257 files changed in 90 days, co-change pairs detected |
| Ranked hubs (PageRank) | `formatName` 11.5%, `format.ts` 10.1%, `helpers.py` 6.8% |
| LOD thresholds | zoom < 0.40 hides subtitles · zoom < 0.25 hides edges |

### 24.3 Defects found and fixed in this sprint

| Severity | Defect | Status |
|---|---|---|
| **P1** | **Loading a second repository kept serving the first one's graph.** The orchestrator's graph cache was never invalidated when the active repo changed, so the analysis endpoints, the PR bot, and the UI all described a codebase that was no longer loaded. | **Fixed** — `orchestrator.clear_graph_cache()`, called from both `load_repo` and `load_local_repo` |
| **P2** | **The `cluster` node type was never registered in `nodeTypes`.** ReactFlow fell back to its default renderer, so the cluster cards were plain white boxes with no layer colour, no icon, and no file count. | **Fixed** |
| **P2** | **The churn legend painted over the layer legend.** Both were `absolute top-4 right-4`. | **Fixed** — the churn spectrum now lives inside the layer legend card |
| **P2** | **Cluster cards overlapped each other.** The pitch was 190px against a 260px card width. | **Fixed** — the pitch is now `width + 40` |
| **P2** | **The fit-view placed the cluster cards under the floating toolbar**, making them unclickable. ReactFlow 11 only supports a numeric `padding`, so an asymmetric fit is impossible. | **Fixed** — `fitClearOfToolbar()` nudges the viewport after the fit |
| **P2** | **Mojibake in the graph title** — a PowerShell `Get-Content`/`Set-Content` round-trip re-encoded `GraphView.tsx` through Windows-1252. | **Fixed** — `scripts/repair_mojibake.py` reverses the mis-decode; the encoding test now names it in its failure message |

### 24.4 The insights the app can now show

| Insight | Where | Honest framing |
|---|---|---|
| Dependency cycles | Insights panel | Split into file-level and symbol-level; a cycle that crosses layers is marked red |
| Unreachable symbols | Insights panel | Labelled **"a static estimate — dynamic dispatch and reflection are invisible to it"** — never called dead code |
| Most central files | Insights panel | PageRank, with the score shown as a percentage |
| Churn hotspots | Graph ring + legend | Emerald → amber → crimson, blended with centrality |
| Architecture layers | Cluster view | Collapses the pyramid into the five canonical layers with their file counts |

### 24.5 Open items carried into Sprint 3

- The frontend still holds a copy of the layer rules; the parity test enforces equivalence.
- `calls` edges are scored by the frontend but not drawn as arcs.
- The cluster view uses the five canonical layers. Louvain community detection would find finer-grained modules — `networkx.community.louvain_communities` is available and verified working.
- Visual-regression baselines (`toHaveScreenshot()`) are still not wired up.

---

## 26. Sprint 2.6 — Graph rendering quality, and the "Internal Server Error"

**Status: complete.** Shipped 2026-10-21, after a manual review of the graph on a 244-file
repository.

### 26.1 The real "Internal Server Error"

**Correction to an earlier claim.** This was initially attributed to a backend that had been
stopped. That was wrong. The actual cause was found and fixed:

> The Vite dev proxy targeted `http://localhost:8000`. On Windows, `localhost` resolves to
> `::1` first, and uvicorn binds IPv4 only — so the proxy's IPv6 connect was refused and
> **every** `/api/*` request came back as a bare 500 "Internal Server Error" with nothing
> anywhere in the backend log.

**Fix.** The proxy target is now explicitly `http://127.0.0.1:8000`. The backend log was
empty, which is what made this so hard to see — a proxy failure looks exactly like a backend
failure.

**Two follow-on fixes, because the first fix only hid the symptom:**

| Severity | Defect | Status |
|---|---|---|
| **P1** | **The QA runner orphaned the Vite process.** `npm run dev` spawns Vite as a CHILD; killing `npm` left the child bound to :5173, still proxying `/api` to the QA backend on :8010. When the QA run ended, every API call in the developer's own app became a 500. | **Fixed** — `stop()` now kills the process TREE (`taskkill /T` on Windows, a process group elsewhere) |
| **P1** | **The QA harness fought the developer for :5173.** | **Fixed** — the harness now uses its own ports: :5183 for the frontend, :8010 for the backend |
| **P2** | **The error message was useless.** `res.statusText` for a 500 is the bare string "Internal Server Error". | **Fixed** — `apiErrorHint()` / `networkErrorHint()` now say what is actually wrong and what to check |

### 26.2 Graph rendering flaws

Found by rendering the 244-file repository and reading the result.

| Severity | Flaw | Status |
|---|---|---|
| **P2** | **Level-of-detail culling hid ALL the edges below zoom 0.25.** The graph became a field of disconnected boxes. The hierarchy IS the information — dropping it destroyed the one thing a small view could still communicate. | **Fixed** — the edges are never hidden. What IS hidden at minimal zoom is the text, because a 10px font at a 0.2 zoom renders at 2px. The low-zoom view is now an **architecture density map**: colour is the layer, shape is the dependency structure. |
| **P2** | **The rank guides were illegible.** ReactFlow scales every node with the viewport, so at the 0.2 zoom a large repository fits to, "RANK 2 — CORE MODULES" shrank to 2px. | **Fixed** — the guides counter-scale to a constant screen size, growing leftwards so they never overlap a node. A small graph is now still readable as a *structure*. |
| **P2** | **The root node was clipped off the top of the canvas.** The fit nudged the viewport upwards to clear the floating toolbar, which traded one defect for another. | **Fixed** — the fit now computes the viewport directly, reserving the toolbar's strip, and runs only once the nodes are MEASURED (`useNodesInitialized`). Before that, `getNodesBounds` used unmeasured dimensions and the fit landed in the wrong place. |
| **P3** | **Eight nodes all labelled `__init__.py`** were indistinguishable in a row. | **Fixed** — a repeated basename gains its parent directory: `chat/__init__.py`. |

### 26.3 New tooling

| Tool | Purpose |
|---|---|
| `scripts/check_mcp.py` | Health-checks the three MCP servers by starting each one and sending a real MCP `initialize` handshake over stdio. All three answer: `chrome_devtools 1.11.0`, `Playwright 1.64.0-alpha`, `tavily-mcp 0.2.22`. |
| `frontend/scripts/shoot_graph.mjs` | A QA lens: opens the real app, waits for the graph, and captures the canvas with the node/edge/label counts and the viewport transform. Used to compare the low-zoom density view against the readable view. |

### 26.4 The MCP servers

The three MCP servers showed `Error` in the client. The cause was **my own doing** — an
over-broad `Stop-Process` sweep over every `node.exe` killed the server processes the client
had spawned, and the client does not respawn them.

The servers themselves were always healthy, which `scripts/check_mcp.py` now proves with a real
handshake rather than an assumption. **Restarting the MCP client (or opencode) re-registers
them.** The health check is committed so this is verifiable in one command instead of by
guesswork.

### 26.5 Verified numbers

| Measure | Value |
|---|---|
| Backend tests | **171 passed** |
| Browser journeys | **9 passed**, 0 console errors |
| MCP servers answering the handshake | **3 of 3** |
| Nodes / edges on the 244-file repo | 251 / 244, all rank labels legible |
| The dev proxy after a QA run | healthy (the orphan bug is fixed) |

---

## 25. Sprint 2.5 — Layer classification correctness

**Status: complete.** Shipped 2026-10-21, after manual review of the graph on a real repository.

### 25.1 The defect

A manual review of the Verdict repository's graph showed **PDFs, spreadsheets, CSVs, markdown
files, and JSON manifests all rendered as "Backend / API"**. Measured on the real 154-file
repository:

| | Before | After |
|---|---|---|
| Misclassified non-code files | **53 of 154 (34%)** | **0 of 154** |
| "backend" layer, total files | 93 | 39 |
| "storage" layer, total files | 3 | 58 |

The cause: the layer rules were written for **source code** but applied to **every file**. A
non-code file matched no rule and fell through to the default, which is "backend".

The visual consequence was severe: the amber "Backend / API" band of the pyramid was mostly
noise, so the actual architecture was invisible.

### 25.2 The fix

1. **A non-code pre-pass.** The extension decides the file's *kind*, and the kind decides the
   layer — the directory does not:

   | Kind | Extensions | Layer |
   |---|---|---|
   | Media | png, jpg, gif, svg, mp4, mp3, woff, … | `client` (served to the browser) |
   | Data | pdf, doc, xlsx, csv, pptx, parquet, … | `storage` |
   | Document | md, rst, txt, adoc, log | `storage` |
   | Config | json, yaml, toml, xml, ini, env, lock | `storage` |
   | Archive | zip, tar, gz, jar, … | `storage` |
   | Project file | LICENSE, NOTICE, CHANGELOG | `storage` |
   | Dotfiles | .gitignore, .editorconfig, .npmrc, … | `storage` |
   | Build tooling | Makefile, Dockerfile, Procfile | `backend` |

2. **Stronger path rules.** The generic words are now anchored to path and word boundaries, so
   `myengineer.py` is no longer "compute" and `notpayment.py` is no longer "external". The
   previous patterns matched those words anywhere in the string.

3. **The id and the label are checked separately** for the asset pre-pass. They are joined with
   a space for the path rules, and a joined string breaks last-segment detection for a
   root-level file: `"file:.gitignore .gitignore"` has no path separator, so its last segment
   is the whole string rather than `.gitignore`.

### 25.3 Also fixed in this pass

| Severity | Defect | Status |
|---|---|---|
| **P2** | **The Insights panel showed the PREVIOUS repository's numbers.** It fetched once on mount and never re-fetched, so loading a second repo left "Most central" listing the first repo's files. | **Fixed** — the panel re-fetches on the repository key |
| **P3** | **The unreachable list showed the same path three times**, because it listed symbols but displayed only the file. | **Fixed** — the symbol name is shown alongside the path |

### 25.4 How it was verified

- `scripts/analyze_layers.py` — measures the extension → layer distribution and every
  misclassified file against a real repository. Before: 53 misclassified. After: 0.
- The parity corpus grew from 90 to 130 cases, including every asset kind, the
  boundary-anchoring cases, and the root-level dotfile case that exposed the id/label bug.
- The parity test **caught this work's own divergence** mid-implementation: the Python side was
  updated before the JavaScript probe, and the test failed with three exact mismatches
  (`.gitignore`, `.editorconfig`, `LICENSE`). That is the gate doing its job.



