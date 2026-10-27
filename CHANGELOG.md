# Changelog

All notable changes to RepoScope are recorded here. Versions follow
[Semantic Versioning](https://semver.org/). The backend package and the CLI are
versioned together; the VS Code extension has its own version because it ships
on a separate marketplace.

## [Unreleased]

### Added

- **v2.0 pitch deck** in PDF and editable PPTX form, linked from the README
  and the documentation index.
- **V2.5–V2.8 implementation plan and two-agent coordination board.** The
  plan is additive to the shipped v2.0 tree and keeps the existing graph,
  endpoints, extension, and provider chain.
- **Nine-agent harness configurator (Phase 3).** `GET /api/harness/agents`,
  `GET /api/harness/config`, `POST /api/harness/apply`, and
  `GET /api/harness/skills` generate and preview MCP configuration for Claude
  Code, Cursor, VS Code / Copilot, Codex CLI, Kiro, Antigravity,
  Windsurf / Devin, Cline / Roo, and OpenCode. Preview never writes. Apply is
  off unless `REPOSCOPE_HARNESS_APPLY=1`; existing files require a diff and
  `force`, JSON/TOML merges preserve unrelated keys, global paths are
  display-only, and absolute or escaping paths are rejected. The SKILL.md
  bodies remain Phase 4 work.
- **Graph schema v2 (Phase 1).** `inherits`, `exports`, and `api_calls` edges
  now carry repository-relative evidence (file, 1-based line, confidence);
  files and symbols carry `pillar` and `role`, handlers carry their routes,
  and the graph exposes an `api_routes` table. Existing v1 node ids, edge
  meanings, endpoints, and MCP tool names are unchanged. The builder writes
  `schema_version: 2`; v1 graphs still load, and the JSON/SQLite stores
  preserve `metadata` and `api_routes` across a round trip.
- **Deterministic route, API-call, heritage, and alias resolution.** The
  parse cache is v3 and records routes, client calls, and class bases.
  tsconfig/jsconfig aliases are loaded with comments and trailing commas.
  Ambiguous targets are omitted rather than guessed. Incremental and full
  builds finalize through the same path, so their v2 graphs match.
- **Frozen mind-map contract.** `GET /api/mindmap` returns the
  `root → pillar → folder → file → symbol` projection with six
  server-classified pillars, deterministic pruning, and `truncated`/
  `omitted` counts. The Phase 2 vertical view is not part of this change.
- **API reference.** `docs/API.md` documents the graph schema, health
  payload, and the full mind-map contract.

### Fixed

- **CI is hermetic and green on every gate.** Endpoint tests resolve a
  synthetic provider instead of depending on a developer `.env`; the unit job
  fetches full history so co-change tests measure real commits; the MCP stdio
  harness keeps the pipe open until every response; and the QA harness owns
  the Playwright servers and isolates their process group, so cleanup cannot
  terminate the CI runner. CI run 40322052797 passes Python 3.11, Python 3.12,
  L2 contract, L3 journeys, frontend build, and extension.
- **CI baseline restored.** `backend/requirements.txt` now declares the
  numerical stack (`numpy`, `scipy`), the MCP server (`mcp>=1.29,<2`), the
  CLI/watcher (`typer`, `watchdog`), and `sse-starlette`. The previous
  clean Python 3.11 install failed 30 tests; it now passes all 343.
- **The L2 health contract now checks the right endpoint.** `/health` must
  return `"ok"` (liveness); `/api/health` must return `"healthy"` (the
  application contract). Installing the latest MCP 2.x is no longer
  possible by accident, so `mcp.server.fastmcp.FastMCP` cannot disappear
  during a deploy.
- **`/api/health` reports `schema_version` and the cached graph counts**
  without building a graph on the health path.
- **`/api/health` now reports `2.0.0`, matching `pyproject.toml`.** A new
  regression test fails if the health response and package version drift.
- **The production CSP allows the browser parser's WebAssembly** via
  `'wasm-unsafe-eval'` without re-enabling JavaScript `'unsafe-eval'`.
  Verified with the parser and all five grammars.
- **A refused folder picker no longer looks like a cancel.** `AbortError`
  stays quiet; denied or blocked access shows an actionable message.
- **A browser preview hides server-backed surfaces** (chat, Track/Incident,
  Student Mode, Insights, Repo Map, Security, Commit, Tour, Impact) so it
  cannot describe a different repository. The folder name no longer gets a
  server owner prefix.
- **Long Student Mode quiz text wraps instead of overflowing** its card.
- The extension docs now use the actual Explorer menu label:
  **RepoScope: Focus this node in the canvas**.

### Changed

- **License changed from MIT to the RepoScope Source-Available License 1.0.**
  The code is still available to read, run, modify, and use in your own
  projects, including internal business projects, but republishing,
  distributing, or commercially exploiting it requires written permission.
  RepoScope is no longer described as OSI Open Source. Releases already
  published under MIT — including Open VSX extension 2.0.1 and the existing
  `reposcope-2.0.1.vsix` — keep their MIT grants; those grants cannot be
  revoked. Bump the extension version before publishing the new terms.
- Final v2 verification recorded: **335 backend tests**, **20 extension tests**,
  native picker **75 files / 315 nodes / 310 edges**, local mode **348 files /
  1,863 nodes / 3,419 edges**, and VS Code **2.0.1** exercised in VS Code
  1.143.0. The four remaining manual checks stay separate and unchecked.
- Open VSX **2.0.1** is searchable with **288 downloads**; the namespace
  remains `verified:false`.

## [2.0.1] — 2026-10-22

The extension release that makes the Activity Bar view installable and quiet.

### Fixed

- **The Activity Bar map is declared as a webview.** `views["reposcope"].type`
  was missing, so VS Code treated the view as a tree view and never mounted
  the HTML. The extension now activates and shows the focus-first mini-graph.
- **The CodeLens asks once per document.** It no longer re-requests every
  caller list on each editor refresh.
- **The map lives where the documentation says it does** — the RepoScope
  Activity Bar container, not a floating panel.

### Changed

- Extension version `2.0.1`; rebuilt VSIX at
  `extensions/vscode/reposcope-2.0.1.vsix`.
- Extension tests: **20 passing** (`npm test`, no extension host required).

## [2.0.0] — 2026-10-22

The v2.0 release: one Tree-sitter index served by the canvas, the CLI, an MCP
server, and an editor extension.

### Added

- **Tree-sitter parser engine** for Python, TypeScript, TSX, JavaScript, Go,
  and Rust, with a shared `LanguageParser` interface, per-language queries, a
  graceful fallback to the previous JS/TS parser, and `line` information for
  every symbol.
- **Cross-file symbol resolution and `calls` edges**, including qualified and
  imported symbols. Static limits are documented: dynamic dispatch, reflection,
  and generated code can produce false negatives.
- **Graph intelligence**: PageRank centrality, in/out degree, strongly
  connected components for dependency cycles, unreachable-symbol estimates,
  git-churn hotspots, and reverse-BFS blast radius.
- **Local mode**: `reposcope run .`, `reposcope index .`, and `reposcope mcp .`
  over a local folder. The watcher re-parses changed files and pushes a fresh
  graph without a page reload. Nothing is uploaded; no GitHub account or PAT
  is required.
- **JSON and SQLite graph stores** behind a shared `GraphStore` interface.
  JSON is the default; SQLite is opt-in with `--format sqlite`.
- **Repo map** ranked by PageRank and bounded by a token budget, with measured
  context reductions committed under `benchmarks/results/`.
- **MCP server** with **8 tools** and **5 resources**, over **stdio** and
  **Streamable HTTP**. SSE is not offered.
  - Tools: `get_architecture_overview`, `calculate_blast_radius`,
    `get_dependency_lineage`, `explain_architectural_rule`, `get_repo_map`,
    `find_dependency_cycles`, `get_hotspots`, `find_unreachable_symbols`.
  - Resources: `reposcope://graph/summary`, `reposcope://hotspots`,
    `reposcope://repo-map`, `reposcope://dead-code`, `reposcope://cycles`.
- **VS Code / Cursor / VSCodium extension**: Activity Bar mini-graph, status
  bar blast-radius indicator, View Callers CodeLens, Explorer context menu,
  and the `reposcope://open` URI handler. It reads the backend over HTTP and
  never parses code itself.
- **Architecture as code**: shared rules in `backend/arch_rules.py`, served by
  `GET /api/arch/rules` and checked per import; project overrides in
  `.reposcope.yml`.
- **PR Bot 2.0 surfaces**: contract diffing for changed exported symbols,
  `POST /api/pr/chat`, `POST /api/pr/report`, SARIF output, and the merge-gate
  path.
- **Canvas modes**: grouped-by-module view for large repositories, a module
  drawer that lists every file, architecture clusters, flat inspection mode,
  churn overlay, fit-to-view with toolbar clearance, and honest labelling for
  browser-parsed previews.
- **Documentation set** for the shipped product: architecture, features,
  development, deployment, QA, troubleshooting, runbooks, demo script,
  handoff, verification checklist, screenshot index, and this changelog.

### Changed

- The graph is built once in the backend and read by every surface. The canvas,
  MCP tools, and extension no longer maintain separate interpretations of the
  same repository.
- Large repositories are grouped by top-level module by default. Small
  repositories still render the full connectivity pyramid.
- The local CLI is the recommended first-run path. A PyPI package named
  `reposcope` currently resolves to an unrelated older project, so the
  supported install is from this checkout with `pip install -e .`.
- The MCP client template is `docs/reposcope-mcp.json`; the working OpenCode
  configuration is `opencode.json` at the repository root.

### Fixed

- MCP startup no longer wedges when `git` is slow or absent; a git timeout is
  reported instead of hanging the server.
- Indexing skips browser-QA artifacts, and the watcher shares the same skip
  list.
- A stale graph is never served after the active repository changes.
- Import resolution handles relative, alias, and unqualified imports that the
  repository does not name explicitly.
- Duplicate `__init__` symbol ids are disambiguated with a deterministic line
  suffix.
- The canvas fit accounts for the floating toolbar, the sticky header, the
  legend, and the drawer, so nodes are not painted underneath them.
- Mojibake introduced by a Windows-1252 round-trip is repaired and guarded by
  an encoding test.

### Known limitations

- The native folder picker requires a human in the OS dialog; Playwright can
  verify the panel but cannot select a folder.
- The browser preview has imports and symbols but no cross-file symbol
  resolution. The UI labels it as a preview.
- Open VSX search visibility waits on publisher email verification. The VSIX
  is published and installable.
- The VS Code Marketplace requires an Azure DevOps publisher PAT; it is not
  published there yet.
- One OpenCode `read_mcp_resource` bridge stalled on
  `reposcope://graph/summary` and returned an unknown message ID. Direct stdio
  reads and tool calls work. The limitation is documented in
  [`docs/VERIFICATION_CHECKLIST.md`](docs/VERIFICATION_CHECKLIST.md).
- Visual-regression baselines, the WebGL tier, `kuzu`, monorepo cross-package
  edges, the ownership overlay, and the critical-path panel remain open.

## [1.0.0] — 2026-09-26

### Added

- Initial public release.
- Architecture graph with a layered dagre layout.
- Conversational Q&A with file, function, and commit citations (SSE streaming).
- Conversational Code Tours with step badges and progress.
- What-If Impact Analysis with blast-radius rings and a legend.
- Repository tracking for commits, PRs, issues, and releases on demand.
- Reverse Build Prompt.
- File tree with GitIngest-style formatting and single-file download.
- Graph export to PNG and SVG.
- BYOK for GitHub private repositories, stored in memory only.
- Multi-key API rotation (OpenRouter → Groq → NVIDIA NIM).
- Health endpoint with uptime, memory, and key counts.
- One-click demo repositories.
- Render and Vercel deployment configurations.
