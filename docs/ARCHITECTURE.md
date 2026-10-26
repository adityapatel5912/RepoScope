# RepoScope — architecture

RepoScope builds **one code graph** and serves it through four surfaces:

1. the React architecture canvas;
2. the local CLI and watcher;
3. the MCP server;
4. the VS Code / Cursor / VSCodium extension.

No surface has its own parser or its own index. A number shown in the canvas,
quoted by an agent through MCP, or displayed in the editor comes from the same
`GraphStore`.

![RepoScope local mode](screenshots/v2/readme-hero.png)

---

## 1. Component map

```
repository on disk ──► local loader ──┐
                                      ├──► parser registry ──► graph builder
GitHub repository ────► repo loader ──┘          │
                                                 ▼
                                         GraphStore / .reposcope
                                                 │
            ┌────────────────────────────────────┼──────────────────────────┐
            ▼                                    ▼                          ▼
      FastAPI API                         MCP server                 VS Code extension
      (SSE + JSON)                        (stdio / HTTP)             (HTTP client)
            │                                    │                          │
            ▼                                    ▼                          ▼
      React canvas                       agents and editors          Activity Bar view
```

### Backend modules

| Module | Responsibility |
|---|---|
| `backend/main.py` | FastAPI composition root, CORS, security headers, legacy endpoints |
| `backend/api/routers/` | `analysis`, `arch`, `local`, `mindmap`, `pr_chat`, `qa` routers |
| `backend/repo_loader.py` | Clone/read a repository, load a local directory, write repo state |
| `backend/parsers/` | Tree-sitter parsers for Python, TypeScript/TSX, JavaScript, Go, Rust |
| `backend/symbol_resolver.py` | Deterministic route, API-call, heritage, and alias scanners |
| `backend/graph_builder.py` | Orchestrates parsing, resolves imports/calls, finalizes schema v2 nodes and edges |
| `backend/graph_store.py` | Loads `.reposcope/graph.json`, validates schema v1/v2 and freshness, serves snapshots |
| `backend/parse_cache.py` | Content-addressed per-file parse cache (routes, calls, heritage; cache v3) |
| `backend/mindmap_classifier.py` | Six-pillar and role taxonomy |
| `backend/mindmap.py` | Deterministic root → pillar → folder → file → symbol projection |
| `backend/graph_analysis.py` | PageRank, SCC cycles, reachability, hubs, critical path |
| `backend/repo_map.py` | Budgeted, ranked context map |
| `backend/arch_rules.py` | `.reposcope.yml` architecture-rule loading and checks |
| `backend/impact_analyzer.py` | Blast radius and reverse dependency traversal |
| `backend/watcher.py` | Local file watcher and re-index session |
| `backend/live_events.py` | In-process SSE event bus for local re-index events |
| `backend/mcp_server/server.py` | MCP tools, resources, stdio and Streamable HTTP |
| `backend/orchestrator.py` | Prompt/context assembly for the chat and report flows |
| `backend/runtime_config.py` | Provider chain and model selection |
| `backend/key_rotator.py` | Multi-key rotation on rate limits |

### Frontend modules

| Module | Responsibility |
|---|---|
| `frontend/src/App.tsx` | Workspace shell, tabs, local session, graph state |
| `frontend/src/components/GraphView.tsx` | Architecture canvas, rank layout, grouping, edges |
| `frontend/src/components/Sidebar.tsx` | File tree, insights, local folder panel, PR Bot |
| `frontend/src/components/ChatPanel.tsx` | Cited chat, streaming, report views |
| `frontend/src/lib/localBrowser.ts` | Browser-side Tree-sitter preview using `showDirectoryPicker` |
| `frontend/src/api/client.ts` | Typed API client and SSE plumbing |

### Extension modules

| Module | Responsibility |
|---|---|
| `extensions/vscode/src/extension.ts` | Activation, commands, URI handler, status bar |
| `extensions/vscode/src/graphView.ts` | Activity Bar `WebviewViewProvider` |
| `extensions/vscode/src/model.ts` | Pure graph helpers (tested with `node --test`) |

---

## 2. Ingestion and graph construction

### Local mode

`reposcope run .` calls `POST /api/local/load` internally (the CLI and the web
UI share the same route). The loader:

1. resolves the folder;
2. walks it while applying ignore rules (`.git`, `node_modules`, build output,
   virtual environments);
3. parses supported files with the parser registry;
4. resolves relative and aliased imports against the module index;
5. adds file nodes, symbol nodes, `imports`, `calls`, and `contains` edges,
   then the schema v2 route/role evidence and `inherits`/`exports`/`api_calls`
   edges;
6. writes `.reposcope/graph.json` and the parse cache;
7. starts the watcher.

The watcher re-parses only changed files. It then publishes an event on the
local SSE bus; the browser updates the graph without a page reload. A local
session never calls GitHub.

### GitHub mode

`POST /api/repo/load` clones a repository (or updates an existing clone),
reads its README, builds the same graph, and stores repo state in
`data/repo_state.json`. GitHub API access is optional and only raises rate
limits. The BYOK panel can set a token for private repositories; it is held in
memory for the session and is not written to disk.

### Supported languages

| Language | Extensions | Parser |
|---|---|---|
| Python | `.py` | Tree-sitter Python |
| TypeScript | `.ts`, `.tsx` | Tree-sitter TypeScript / TSX |
| JavaScript | `.js`, `.jsx`, `.mjs`, `.cjs` | Tree-sitter JavaScript |
| Go | `.go` | Tree-sitter Go |
| Rust | `.rs` | Tree-sitter Rust |

Files in other languages are still indexed as file nodes, but they have no
symbol or call extraction.

### Node and edge model

```json
{
  "id": "backend/graph_builder.py",
  "label": "graph_builder.py",
  "type": "file",
  "path": "backend/graph_builder.py",
  "rank": 3,
  "symbols": ["build_graph", "resolve_imports"]
}
```

Edges are `imports`, `calls`, and `contains`, plus the schema v2 edges
`inherits`, `exports`, and `api_calls`. The v2 edges carry evidence; v1 ids
and edge meanings are unchanged. See
[`KNOWLEDGE_GRAPH_SCHEMA.md`](KNOWLEDGE_GRAPH_SCHEMA.md) for the stable ids,
evidence rules, and rendering rules.

---

## 3. Analysis layer

All analysis runs on the graph snapshot:

- **PageRank centrality** ranks files by dependency importance.
- **Strongly connected components** identify import cycles.
- **Reverse BFS** computes blast radius and dependents.
- **Reachability** estimates unreachable symbols from entry points.
- **Hotspots** combine centrality with git churn.
- **Critical path** walks the most central dependency chain.
- **Architecture rules** compare each import with `.reposcope.yml`.
- **Repo map** ranks nodes and stops at a token budget.

The same functions back the API, MCP tools, and the extension, which is why
their answers agree.

---

## 4. HTTP API

The API is JSON-first; chat and local updates use Server-Sent Events.

### Core

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Uptime, memory, provider key counts |
| `GET` | `/api/ai/providers` | Configured providers (no key material) |
| `POST` | `/api/chat/stream` | SSE answer with citations |
| `POST` | `/api/byok/set` | Session-only GitHub token |
| `POST` | `/api/repo/load` | Clone and index a GitHub repository |
| `POST` | `/api/repo/load-demo/{demo_id}` | Load a bundled demo repository |
| `GET` | `/api/repo/status` | Current repository state |
| `GET` | `/api/repo/check` | Poll GitHub for changes |
| `GET` | `/api/repo/graph` | Full graph snapshot |
| `GET` | `/api/mindmap` | Six-pillar mind-map projection; see [API.md](API.md#get-apimindmap) |
| `GET` | `/api/repo/file` | File content for the viewer |
| `GET` | `/api/repo/demos` | Available demo repositories |
| `POST` | `/api/repo/commit` | Commit from the app (BYOK) |
| `POST` | `/api/repo/reverse-prompt` | Reverse build prompt |

### Analysis (`/api/analysis`)

`GET /hotspots`, `/cycles`, `/unreachable`, `/hubs`, `/workspaces`,
`/ownership`, `/critical-path`, `/callers`, `/callers-batch`, `/dependents`,
`/repo-map`, `/fixtures`, `/scale-traversal`; `POST /load-fixture`.

### Architecture (`/api/arch`)

Rule listing and checks, plus the SARIF export used by CI. See the router source
for the exact request shapes.

### Local mode (no prefix)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/local/status` | Is the watcher on? What changed? |
| `POST` | `/api/local/load` | Analyse a directory on disk and watch it |
| `GET` | `/api/local/events` | SSE stream of re-index events |

### PR and QA (`/api/pr`, `/api/qa`)

`POST /api/pr/chat`, `POST /api/pr/report`, `GET /api/pr/sarif`,
`POST /api/pr/load-fixture`; QA endpoints cover scale traversal and fixtures.

### Impact, tours, tracking, security

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/impact/analyze` | Blast radius and narrative |
| `POST` | `/api/impact/pr` | GitHub-ready PR comment |
| `POST` | `/api/tour/generate` | Code tour stops |
| `POST` | `/api/tts` | Voice narration |
| `POST` | `/api/onboard` | Student Mode path, quizzes, GFIs |
| `POST` | `/api/security/scan` | Secrets, breaking changes, CVEs |
| `POST` | `/api/security/taint` | Taint analysis |
| `POST` | `/api/scaffold` | Stage 1/2/3 starter scaffold |

The API exposes `X-Request-Id` and security headers on every response. The
global exception handler returns JSON, never a stack trace.

---

## 5. Local mode and the watcher

```
reposcope run .
  ├─ load local repo -> GraphStore
  ├─ start uvicorn on 127.0.0.1:4100
  ├─ serve frontend/dist
  ├─ start watchdog
  └─ publish re-index events over /api/local/events
```

- The watcher debounces changes and ignores build output and dependencies.
- The parse cache means an unchanged file is not parsed again.
- The browser holds an `EventSource`; the event carries the new graph counts.
- The CLI prints the repository path, file count, serving URL, and watcher
  state.
- `--no-open` disables the browser launch; useful in tests and CI.

The default local port is **4100**. The full stack uses **8000** (FastAPI) and
**5173** (Vite).

---

## 6. MCP server

The MCP server is a client of `GraphStore`. It reads the same
`.reposcope/graph.json` and builds it if it is missing or stale. It offers
**stdio** (default) and **Streamable HTTP**; SSE is not offered.

### Tools

| Tool | Answer |
|---|---|
| `get_architecture_overview` | Layers, central files, entry points |
| `calculate_blast_radius` | What breaks if a file or symbol changes |
| `get_dependency_lineage` | What a file needs and what needs it |
| `explain_architectural_rule` | Does an import cross a declared boundary? |
| `get_repo_map` | Budgeted, ranked context map |
| `find_dependency_cycles` | Import loops and the layers they span |
| `get_hotspots` | Frequently changed, widely depended-upon files |
| `find_unreachable_symbols` | Static reachability estimate |

### Resources

`reposcope://graph/summary`, `reposcope://hotspots`,
`reposcope://repo-map`, `reposcope://dead-code`, `reposcope://cycles`.

### Transports

```bash
# stdio
reposcope-mcp --root /absolute/path/to/repo

# Streamable HTTP
reposcope-mcp --root /absolute/path/to/repo --http --port 8765
```

A client configuration example is in
[`reposcope-mcp.json`](reposcope-mcp.json). OpenCode can run the server from a
checkout by setting `cwd` to `backend`.

---

## 7. Frontend graph layout

`GraphView.tsx` owns the layout. It is a custom rank layout, not a generic
DAG library.

- **Small repositories:** a connectivity pyramid. The repository is the root;
  ranks descend through backbone files, core modules, routers/services, UI,
  config, and docs/data. Edges flow from a parent's bottom handle to a child's
  top handle.
- **Large repositories:** when the file count crosses the grouping threshold,
  top-level modules become cluster cards. The cards carry file counts and the
  rank labels stay on the canvas. Every file is still available in the drawer.
- **Grouping is a view, not a second graph.** The backend still returns every
  file node and every edge; the canvas collapses them for rendering.
- **Drawer:** clicking a cluster or a node opens its details, edge lists, and
  actions.
- **Export:** PNG and SVG are rendered from the canvas.

The canvas is 1600x900 in the screenshots. The default view fits the full map;
zoom and fit are available in the toolbar.

### Browser preview

The **Open a local folder** panel uses `window.showDirectoryPicker` and a
Tree-sitter WebAssembly parser in the browser. This preview:

- has imports and symbols;
- has no cross-file symbol resolution;
- never sends the folder to the backend;
- is labelled as a browser preview in the UI.

The native folder picker is outside Playwright and requires a secure context
(`localhost` or HTTPS). The final pass drove the OS dialog with Win32
automation; see
[`QA_REPORT.md`](QA_REPORT.md#agent-run-evidence--2026-10-25).

---

## 8. Extension

The extension is an HTTP client, not a parser.

- **Activity Bar view:** `reposcope.graph`, a focus-first mini-graph for the
  open file.
- **Status bar:** blast radius and risk for the current file.
- **CodeLens:** caller count above exported symbols; it asks before enabling.
- **Explorer context menu:** **RepoScope: Focus this node in the canvas**.
- **URI handler:** `reposcope://open?path=...&line=...`.
- **Settings:** `reposcope.backendUrl` (default `http://127.0.0.1:8000`),
  `reposcope.canvasUrl` (default `http://127.0.0.1:4100`),
  `reposcope.statusBar`, `reposcope.codeLens`.

When the backend is unreachable, the extension reports **offline**; it never
shows zero dependents as if the index were empty.

---

## 9. Optional LLM layer

The graph works without any API key. Chat, tours, Student Mode, security
narrative, scaffolding, and PR Bot need an LLM.

- Provider chain: OpenRouter → Groq → NVIDIA NIM.
- Comma-separated keys rotate on rate limits.
- Provider/model/base URL are configurable in `.env`.
- Chat streams SSE frames: `context`, `token`, `tracking`, `done`, `error`.
- Prompts are assembled from the graph and cited file context, not from a
  whole-repository dump.

If no key is configured, those features fail with a clear message and the
graph remains usable.

---

## 10. Storage and state

| Path | Contents |
|---|---|
| `.reposcope/graph.json` | Current graph snapshot |
| `.reposcope/parse-cache.json` | Per-file parse cache |
| `.reposcope/local-session.json` | Local session state (resume after restart) |
| `data/repo_state.json` | GitHub repository state and last load |
| `data/metrics.json` | Token/usage metrics |
| `qa-report/` | QA harness output |
| `docs/screenshots/` | Screenshot evidence |

The `.reposcope` directory is local state and should not be committed.

---

## 11. Ports and deployment

| Surface | Default |
|---|---|
| Local mode | `127.0.0.1:4100` |
| FastAPI (full stack) | `127.0.0.1:8000` |
| Vite dev server | `127.0.0.1:5173` |
| MCP Streamable HTTP | `127.0.0.1:8765` |
| QA backend / frontend | `8010` / `5183` |

Production uses Render for the API and Vercel for the frontend. The extension
is published to Open VSX. See [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## 12. Security and privacy

- Local mode makes no outbound request; the local router has no GitHub code
  path.
- The browser preview never uploads the selected folder.
- BYOK GitHub tokens are memory-only.
- API keys stay in `.env`, which is gitignored.
- The API sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  and a restrictive CSP.
- The MCP server reads only the configured root.
- Logs redact key material; never paste a key into an issue.

---

## 13. Failure modes

| Symptom | Likely cause |
|---|---|
| Graph has nodes but no edges | Unsupported language or unresolved imports; check the parser registry |
| Local graph is stale | Watcher disabled or ignored directory; restart or `reposcope index .` |
| MCP server slow on first call | Cold index build; the warm call is fast |
| MCP resource read stalls in a client | Client resource-bridge issue; direct stdio read and tool calls are the control |
| Status bar says offline | Backend URL/port wrong or backend not running |
| Canvas is blank after a large load | Grouping threshold/fit state; use Fit view and check the console |
| LLM feature returns 503 | No provider key or all keys exhausted |

See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for the full list.
