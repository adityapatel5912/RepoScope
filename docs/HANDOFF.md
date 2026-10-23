# Handoff

**Current release:** package **2.0.0**, extension **2.0.1**.
**State:** code complete for the v2.0 scope; documentation updated; manual
verification is still open.

## What exists

| Path | Contents |
|---|---|
| `backend/` | FastAPI app, Tree-sitter parsers, graph builder/store, local watcher, analysis, MCP server |
| `frontend/` | React + Vite + TypeScript canvas, chat, impact, tours, Student Mode, PR Bot |
| `cli/` | `reposcope` and `reposcope-mcp` entry points |
| `extensions/vscode/` | VS Code / Cursor / VSCodium extension, version 2.0.1 |
| `docs/` | Current documentation, screenshots, QA report, verification checklist |
| `scripts/` | QA and maintenance scripts |
| `benchmarks/` | Repo-map token-saving benchmark and committed results |

## Run it

### Local mode

```bash
python -m cli.main run . --port 4100 --no-open
```

Health: <http://127.0.0.1:4100/api/health>
Canvas: <http://127.0.0.1:4100>

### Full stack

```bash
# Terminal 1
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend && npm install && npm run dev
```

### MCP

```bash
cd backend
python -m mcp_server.server --root ..
```

## Current verification

Verified in this session:

- backend: **333 tests passed**;
- frontend TypeScript: clean;
- frontend production build: success;
- local mode: health 200, graph loaded, watcher on;
- MCP stdio sweep: **8 tools, 5 resources, 3 read rounds, clean ping**;
- OpenCode MCP status: `✓ reposcope connected`.

Not manually verified yet:

- native folder picker / browser preview;
- live PR Bot comment;
- VS Code extension in a real editor window;
- Open VSX search visibility;
- VS Code Marketplace publishing;
- LLM-backed flows with a live key.

The authoritative list is
[`VERIFICATION_CHECKLIST.md`](VERIFICATION_CHECKLIST.md). Do not mark an item
complete without evidence.

## Architecture in one paragraph

A repository is parsed by Tree-sitter into file and symbol nodes with
`imports`, `calls`, and `contains` edges. The graph is written to
`.reposcope/graph.json`. PageRank, SCC cycles, reachability, hotspots, and
blast radius run over that snapshot. The FastAPI canvas, the MCP server, and
the extension all read the same index. Local mode watches the folder and pushes
re-index events to the browser. LLM features are optional and use the
OpenRouter → Groq → NVIDIA chain.

## Key constraints

- Local mode must not make outbound requests.
- The browser folder preview must stay labelled as a preview; it has no
  cross-file symbol resolution.
- The Open VSX listing is hidden from search until the publisher namespace
  email is verified.
- The VS Code Marketplace needs an Azure DevOps PAT.
- Some MCP clients have a resource-read bridge issue; the server's direct
  stdio reads and tool calls work.
- Do not commit `.env`, `.reposcope/`, `node_modules/`, or build output.
- Do not push without explicit instruction.

## Where to look next

| Question | Document |
|---|---|
| How does it work? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What ships? | [FEATURES.md](FEATURES.md) |
| What is verified? | [QA_REPORT.md](QA_REPORT.md) |
| What is still manual? | [VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md) |
| How do I run/publish it? | [DEVELOPMENT.md](DEVELOPMENT.md), [DEPLOYMENT.md](DEPLOYMENT.md) |
| What is still planned? | [ROADMAP_V2.md](ROADMAP_V2.md) |
