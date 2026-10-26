# Development

## Prerequisites

- Python **3.11+**
- Node **20+** and npm
- Git
- Windows, macOS, or Linux

No LLM key is required to work on the graph, local mode, CLI, MCP server, or
extension. Chat and the other generated features need at least one provider
key.

## Install from a checkout

```bash
git clone https://github.com/adityapatel5912/RepoScope.git
cd RepoScope

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

`pip install -e .` installs the backend modules, the `reposcope` CLI, and the
`reposcope-mcp` entry point. The PyPI name currently resolves to an unrelated
older package; install from this checkout.

RepoScope is source-available, not OSI Open Source. You may use and modify it
under the terms in [`LICENSE`](../LICENSE); do not republish, distribute, or
commercially exploit it without written permission.

## Local mode

```bash
python -m cli.main run . --port 4100 --no-open
```

Or, after installation:

```bash
reposcope run . --port 4100 --no-open
```

- Canvas: <http://127.0.0.1:4100>
- Health: <http://127.0.0.1:4100/api/health>
- Watcher: on by default; edits trigger a re-index and an SSE event.

`--no-open` is useful in tests and CI. `reposcope index .` writes the graph
without starting a server.

## Full stack

Terminal 1:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to the backend. Add at least
one LLM key to `.env` for chat, tours, Student Mode, security narrative,
scaffolding, and PR Bot.

## Environment

See [`.env.example`](../.env.example). The important variables:

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEYS` | Primary provider; comma-separated |
| `GROQ_API_KEYS` | Secondary provider; comma-separated |
| `NVIDIA_API_KEYS` | Fallback provider; comma-separated |
| `Models_*` | Optional model overrides |
| `Base_URL_*` | Optional OpenAI-compatible endpoints |
| `GITHUB_TOKENS` | Raises GitHub API limits |
| `OVSX_TOKEN` | Open VSX publish token; never commit it |

Legacy single-key variables are still accepted. `.env` is gitignored.

## Tests and checks

### Backend

```bash
cd backend
python -m pytest -q
```

Expected current baseline: **335 passed**.

### Frontend

```bash
cd frontend
npx tsc --noEmit
npm run build
```

### Extension

```bash
cd extensions/vscode
npm install
npm test          # 20 node:test unit tests, no editor host
npm run compile
npx @vscode/vsce package --no-dependencies
```

The VSIX is written to `extensions/vscode/reposcope-<version>.vsix`.

### QA harness

```bash
python scripts/qa.py          # boot, wait, test, report
python scripts/qa.py --grep J01
python scripts/qa.py --headed # watch the browser
```

It writes `qa-report/index.html` and `qa-report/results.json`. QA runs on ports
**8010/5183** so it does not collide with development on 8000/5173.

## MCP server

```bash
cd backend
python -m mcp_server.server --root ..
```

- Default transport: stdio.
- Streamable HTTP: `--http --port 8765`.
- Tools: 8; resources: 5.
- The server reads `.reposcope/graph.json` and rebuilds it when stale.

Example client config: [`reposcope-mcp.json`](reposcope-mcp.json).

## Project layout

```
backend/
  main.py                 FastAPI composition root
  api/routers/            analysis, arch, local, pr_chat, qa
  parsers/                Tree-sitter parsers and registry
  graph_builder.py        parse + resolve + build
  graph_store.py          snapshot loading/freshness
  graph_analysis.py       PageRank, cycles, reachability
  watcher.py              local re-index session
  mcp_server/server.py    MCP tools/resources/transports
  tests/                  pytest suite

frontend/
  src/App.tsx             workspace shell
  src/components/         GraphView, Sidebar, ChatPanel, ...
  src/api/localBrowser.ts browser preview (showDirectoryPicker)
  src/api/client.ts       typed API client

cli/                      reposcope CLI
extensions/vscode/        VS Code/Cursor/VSCodium extension
docs/                     current docs, screenshots, checklist
scripts/                  QA and maintenance scripts
```

## Graph development notes

- The layout in `GraphView.tsx` is custom; do not reintroduce a generic
  auto-layout dependency.
- Large repositories collapse top-level modules into cluster cards. The
  backend still returns every node and edge.
- The grouping threshold is deliberate; test both a small repository and a
  large one when changing layout code.
- Edge handles flow from parent bottom (`out`) to child top (`in`).
- The browser preview is a separate, lighter parser path. It has no
  cross-file symbol resolution and must stay labelled as a preview.
- The production CSP must keep `'wasm-unsafe-eval'` in `script-src` so the
  browser parser can compile Tree-sitter WebAssembly. Do not replace it with
  the broader `'unsafe-eval'`; `backend/tests/test_health.py` guards both
  directions.
- `/api/health` must report the same version as `pyproject.toml`.
  `test_health_version_matches_package_metadata` enforces it.

## Documentation

Update the current docs, not the historical archive:

- [Documentation index](README.md)
- [Architecture](ARCHITECTURE.md)
- [Features](FEATURES.md)
- [Verification checklist](VERIFICATION_CHECKLIST.md)
- [QA report](QA_REPORT.md)

After a documentation change, check links and screenshot paths. A docs-only
change does not require a backend test run, but do not claim a test result
that was not produced in the current session.

## Commit convention

```text
feat(scope): short imperative summary
fix(scope): short imperative summary
docs: short summary
test(scope): short summary
```

Do not commit `.env`, `.reposcope/`, `node_modules/`, build output, or QA
artifacts. Do not push without explicit instruction.
