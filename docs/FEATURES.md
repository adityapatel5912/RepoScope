# RepoScope — features

This is the current feature set (package **2.0.0**, extension **2.0.1**).
Every feature below is either implemented and verified, implemented with a
stated limit, or explicitly marked as planned. The manual checks live in
[`VERIFICATION_CHECKLIST.md`](VERIFICATION_CHECKLIST.md).

---

## 1. The code graph

**What it is:** one Tree-sitter index of a repository, stored as
`.reposcope/graph.json`.

- File nodes for every indexed file.
- Function, method, and class nodes.
- `imports` edges resolved through a module index, including relative and
  aliased imports.
- `calls` edges resolved across files where the parser can see the target.
- `contains` edges from a file to its symbols.
- PageRank centrality, dependency cycles, reachability, hubs, critical path,
  and git-churn hotspots.
- Architecture rules loaded from `.reposcope.yml`.

**Languages:** Python, TypeScript, TSX, JavaScript, Go, Rust. Other files are
indexed as file nodes without symbol extraction.

**Limit:** call resolution is static. Dynamic dispatch, reflection, and
generated code can be missed. This is stated rather than hidden.

---

## 2. Architecture canvas

![Architecture canvas](screenshots/v2/readme-hero.png)

- **Small repositories:** a connectivity pyramid. The repository is the root;
  ranks descend through backbone files, core modules, routers/services, UI,
  config, and docs/data.
- **Large repositories:** top-level modules become cluster cards when the file
  count crosses the grouping threshold. The cards show file counts; every file
  remains reachable in the drawer. The RepoScope repository itself resolves to
  a set of top-level module cards; the count is shown in the UI at load time.
- **Module drawer:** click a cluster to see its files, edges, and actions.
- **Node details:** select a file for its symbols, importers, dependencies, and
  actions.
- **Canvas controls:** zoom, fit view, export PNG, export SVG.
- **Rank labels:** visible on the canvas.
- **Edit:** double-click or use the drawer action to open a file in the editor
  integration.

**Limits:** the grouped view is a rendering collapse, not a second graph. The
full graph is still returned by the API. Very large repositories beyond the
tested range may need the WebGL tier, which is still planned.

---

## 3. Local mode

![Local folder panel](screenshots/v2/readme-local-panel.png)

```bash
reposcope run .
```

- Parses the current folder; no GitHub account, token, or clone.
- Serves the canvas on `http://127.0.0.1:4100`.
- Watches for edits and re-indexes changed files.
- Streams re-index events to the browser over `/api/local/events`; no page
  reload.
- Resumes a local session after a server restart.
- Prints file, node, and edge counts plus the watcher state.
- `--no-open` suppresses the browser launch.

**Privacy:** nothing from the repository is uploaded. The local router has no
outbound GitHub code path.

**Limit:** the watcher is best-effort; ignored directories and generated files
are not tracked. Use `reposcope index .` to rebuild deliberately.

---

## 4. CLI

| Command | Purpose |
|---|---|
| `reposcope run .` | Index, serve, and watch a local folder |
| `reposcope index .` | Write `.reposcope/graph.json` without a server |
| `reposcope index . --format sqlite` | Write the alternate store format |
| `reposcope mcp .` | Serve the graph over MCP (stdio) |

From a checkout, the same commands run as `python -m cli.main ...`.

---

## 5. MCP server

The same index, exposed to agents.

**Tools (8):**

- `get_architecture_overview`
- `calculate_blast_radius`
- `get_dependency_lineage`
- `explain_architectural_rule`
- `get_repo_map`
- `find_dependency_cycles`
- `get_hotspots`
- `find_unreachable_symbols`

**Resources (5):**

- `reposcope://graph/summary`
- `reposcope://hotspots`
- `reposcope://repo-map`
- `reposcope://dead-code`
- `reposcope://cycles`

**Transports:** stdio (default) and Streamable HTTP. SSE is not offered.

**Limit:** one OpenCode bridge build has shown a resource-read stall (several
minutes, then `Received a response for an unknown message ID`). Direct stdio
reads are instant and the tool calls work. Treat this as a client bridge issue
until reproduced against the server.

---

## 6. VS Code / Cursor / VSCodium extension

The extension reads the backend over HTTP; it never parses code.

- **Activity Bar view:** a focus-first mini-graph for the open file.
- **Status bar:** blast radius and risk for the current file.
- **View Callers CodeLens:** caller count above exported symbols; asks before
  enabling.
- **Explorer context menu:** **Visualize in RepoScope Canvas**.
- **URI handler:** `reposcope://open?path=...&line=...`.
- **Offline state:** says **RepoScope: offline** instead of showing zero.

Settings: `reposcope.backendUrl`, `reposcope.canvasUrl`,
`reposcope.statusBar`, `reposcope.codeLens`.

**Distribution:** VSIX is built locally; version 2.0.1 is published to Open
VSX. The listing is hidden from search until the publisher namespace email is
verified. The VS Code Marketplace still needs an Azure DevOps PAT.

**Limit:** the extension cannot be driven by Playwright; it has a manual
checklist and committed screenshots.

---

## 7. Browser preview: open a local folder

The left panel's **Open a local folder** action uses
`window.showDirectoryPicker` and Tree-sitter WebAssembly.

- Imports and symbols are extracted in the browser.
- The folder never reaches the backend.
- The UI labels the result a **browser preview**.
- It has no cross-file symbol resolution, so it is lighter than the server
  graph.

**Limit:** the OS dialog is manual. Chrome or Edge on `localhost`/HTTPS is
required; Firefox does not implement the API.

---

## 8. Chat with citations

- SSE-streamed answers.
- Context assembled from the graph and cited files.
- File, function, and line citations.
- Markdown, tables, and code blocks with copy buttons.
- Model/provider chain: OpenRouter → Groq → NVIDIA NIM.
- Multi-key rotation on 429s.
- BYOK GitHub token for private repositories (memory-only).
- Voice input where the browser supports it.

**Limit:** requires a provider key. The graph and local mode do not.

---

## 9. Impact analysis and PR Bot

- Blast radius: direct and transitive dependents.
- Risk score, narrative, and suggested tests.
- On-canvas highlighting of affected files.
- GitHub-ready PR comment with a Mermaid impact graph.
- Included GitHub Action posts the comment on pull requests.

**Limit:** the live comment path needs a real PR and a token with
`pull-requests: write`. Test on a repository you own.

---

## 10. Code tours and voice

- Guided walkthroughs of a module.
- Numbered stops on the canvas.
- Camera pans and highlights each step.
- Optional voice narration through OpenRouter TTS, with browser speech as a
  fallback.

**Limit:** requires an LLM/TTS provider for generated tours; the browser
fallback is lower quality.

---

## 11. Tracking

- Commits, pull requests, issues, and releases.
- On-demand GitHub polling.
- Grouped by change type.
- Breaking-change flags.
- State persisted in `data/repo_state.json`.

**Limit:** GitHub API rate limits apply; a token raises them.

---

## 12. Student Mode

- Three-level path: entry points → core modules → utilities.
- Per-file “why it matters” notes.
- Checkpoint quizzes.
- Good First Issue suggestions mined from low-traffic files.

**Limit:** generated content needs an LLM. The ranking itself comes from the
graph.

---

## 13. Security scan

- Committed secrets, redacted in output.
- Leaked `.env` files.
- Breaking signature changes.
- Vulnerable dependency pins.
- Taint analysis endpoint.
- Remediation guidance.

**Limit:** heuristic detection, not a replacement for a dedicated scanner. It
does not execute untrusted code.

---

## 14. Reverse build prompt and scaffold

- **Reverse prompt:** turn a repository into a “Build me a…” Markdown prompt.
- **Scaffold:** Stage 1/2/3 starter with boilerplate and TODOs.
- **Download:** ZIP.
- **Open:** StackBlitz.
- Never downloads the full codebase.

**Limit:** generated scaffold quality depends on the provider; review it
before use.

---

## 15. File tree and exports

- GitIngest-style tree.
- Search filter.
- Single-file download.
- PNG and SVG graph export.
- Repository tree generation.

---

## 16. Health and configuration

- `GET /api/health`: uptime, memory, provider key counts.
- Provider/model/base URL configuration through `.env`.
- Legacy single-key variables accepted.
- No key material is returned by the API.

---

## 17. Known gaps

These are intentionally not presented as shipped:

- WebGL rendering tier for very large graphs.
- The `kuzu` graph-store flag.
- Monorepo cross-package edges.
- Ownership overlay (the endpoint exists; the data is not populated).
- Critical-path panel in the UI (analysis endpoint exists).
- Visual-regression baselines.
- An unbounded 50k-file measurement.
- Excluding test fixtures from “architecture” by default.
- VS Code Marketplace publishing (blocked on an Azure DevOps PAT).

The roadmap tracks these. The verification checklist tracks the manual work.
