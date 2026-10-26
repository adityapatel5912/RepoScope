# Handoff

**Current release:** package **2.0.0**, extension **2.0.1**.
**State:** code complete for the v2.0 scope; documentation updated; the
automated evidence is recorded. The four manual checks remain open.
**License:** RepoScope Source-Available License 1.0 — use and modify in your
own projects, but no republishing or commercial exploitation without written
permission. It is **not** OSI Open Source.

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

- backend: **335 tests passed**;
- frontend TypeScript: clean;
- frontend production build: success (`assets/index-CMSb0cnC.js`);
- health contract: `/api/health` returns **2.0.0**, matching `pyproject.toml`;
- local mode: health 200, **348 files, 1,863 nodes, 3,419 edges**, watcher on;
- browser preview: native picker selected **75 files, 315 nodes, 310 edges**;
  cancel and refusal paths behaved correctly; no upload was observed;
- VS Code extension **2.0.1** in VS Code 1.143.0: Activity map, status bar,
  CodeLens, Explorer menu, URI handler, offline/recovery;
- Open VSX: **2.0.1**, **288 downloads**, searchable, direct page HTTP 200;
- CSP / WebAssembly: parser and five grammars load under production CSP;
- MCP stdio sweep: **8 tools, 5 resources, 3 read rounds, clean ping**;
- OpenCode MCP status: `✓ reposcope connected`.

The remaining manual checks are:

- Cursor/VSCodium extension testing;
- Open VSX namespace verification and the verified badge;
- Render redeployment showing version 2.0.0;
- VS Code Marketplace publishing (Azure DevOps PAT).

The authoritative list is
[`VERIFICATION_CHECKLIST.md`](VERIFICATION_CHECKLIST.md). Do not mark an item
complete without evidence. Agent-run evidence is in
[`QA_REPORT.md`](QA_REPORT.md#agent-run-evidence--2026-10-25).

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
- The Open VSX listing is searchable; the namespace is still `verified:false`,
  so the verified badge and stable ranking are not guaranteed.
- The VS Code Marketplace needs an Azure DevOps PAT.
- The health endpoint must report **2.0.0**; Render still runs the old
  `1.0.0` build until a deploy is approved.
- The license is source-available, not OSI Open Source. Do not describe it as
  MIT or "open source" in release copy.
- The already-published extension **2.0.1** and the existing
  `reposcope-2.0.1.vsix` were released under MIT. Those grants cannot be
  revoked. The source tree and future builds use the source-available license;
  bump the extension version before publishing the new terms.
- Some MCP clients have a resource-read bridge issue; the server's direct
  stdio reads and tool calls work.
- Do not commit `.env`, `.reposcope/`, `node_modules/`, or build output.
- The working tree is committed locally only. Do not push, deploy, or publish
  without explicit instruction.

## Where to look next

| Question | Document |
|---|---|
| How does it work? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What ships? | [FEATURES.md](FEATURES.md) |
| What is verified? | [QA_REPORT.md](QA_REPORT.md) |
| What is still manual? | [VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md) |
| How do I run/publish it? | [DEVELOPMENT.md](DEVELOPMENT.md), [DEPLOYMENT.md](DEPLOYMENT.md) |
| What is still planned? | [ROADMAP_V2.md](ROADMAP_V2.md) |
