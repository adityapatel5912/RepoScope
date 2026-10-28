# Contributing to RepoScope

Thank you for your interest in contributing to **RepoScope**!

RepoScope is an autonomous code intelligence and architecture platform. Its defining design principle is **one code graph, four ways in**:
1. **The Architecture Canvas** (Vite + React 18 + D3 interactive graph & collapsible mindmap)
2. **The Terminal CLI** (`reposcope` and `reposcope-ai` via Typer)
3. **The Model Context Protocol Server** (`reposcope-mcp` and `npx reposcope-mcp`)
4. **The Editor Extension** (VS Code, Cursor, and VSCodium)

Every surface reads from the **exact same index**. Any contribution should preserve this property: any structural insight available in the UI should be accessible via MCP and the CLI.

---

## Development Environment Setup

### Prerequisites
- **Python**: 3.11+ (Python 3.11, 3.12, or 3.14 with C build tools for tree-sitter grammars)
- **Node.js**: 20+ (Node 20 or 22 LTS recommended)
- **Git**: 2.40+

### Clone & Bootstrap

```bash
# 1. Clone the repository
git clone https://github.com/adityapatel5912/RepoScope.git
cd RepoScope

# 2. Setup Python virtual environment
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# 3. Install Python dependencies in editable mode
pip install -e ".[dev]"

# 4. Copy environment configuration
cp .env.example .env

# 5. Install frontend dependencies
cd frontend
npm install
cd ..
```

> **Note on LLM API Keys**:
> RepoScope functions in **100% offline local mode** without any API keys (graph building, mindmap, blast radius simulation, 6-engine security audit, and topological ordering require zero cloud calls).
> An LLM API key (OpenRouter, Groq, NVIDIA, or OpenAI) is only required for natural language chat, automated PR comment narratives, and AI prompt compilation.

---

## Running the Application Locally

### 1. Local Mode (All-in-One CLI Server)
The fastest way to test changes locally:
```bash
python -m cli.main run . --port 4100 --no-open
```
Open [http://127.0.0.1:4100](http://127.0.0.1:4100) in your browser.

### 2. Dual-Process Dev Mode (Hot Reloading)
For active frontend or backend development:

**Terminal 1 (Backend API):**
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Terminal 2 (Frontend Dev Server):**
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173). Vite will proxy all `/api/*` requests to port 8000.

### 3. Model Context Protocol (MCP) Server
To run and test the MCP server over standard I/O:
```bash
# Python direct:
python -m mcp_server.server

# Or via CLI:
reposcope mcp .

# Or via Node NPX launcher:
node packages/reposcope-mcp/bin/reposcope-mcp.js
```

### 4. Six-Engine Security Audit CLI
Run the graph-contextual security audit directly in your terminal:
```bash
# Human-readable summary:
reposcope security .

# OASIS SARIF 2.1.0 output:
reposcope security . --sarif > results.sarif
```

---

## Test Suites & Quality Gates

Before opening a pull request, run the following verification battery:

### 1. Backend Pytest Battery
```bash
python -m pytest backend/tests -q
```
Runs 590+ unit tests across the graph builder, PageRank centrality, inter-procedural taint propagation, 6-engine security scanners, 3-hop impact simulator, and topological onboarding.

### 2. Python Bytecode & Dependency Check
```bash
python -m compileall -q backend cli
python -m pip check
```

### 3. Frontend Type-Check & Build
```bash
cd frontend
npx tsc --noEmit
npm run build
cd ..
```

### 4. VS Code Extension Tests & Packaging
```bash
cd extensions/vscode
npm install
npm test
npx @vscode/vsce package --no-dependencies
cd ../..
```

### 5. Playwright Browser QA Battery (E2E)
```bash
cd frontend
npx playwright test tests/e2e/security-suite.spec.ts
npx playwright test tests/e2e/impact-simulator.spec.ts
npx playwright test tests/e2e/pr-impact.spec.ts
npx playwright test tests/e2e/scaffold.spec.ts
npx playwright test tests/e2e/tour-tracks.spec.ts
npx playwright test tests/e2e/onboarding.spec.ts
npx playwright test tests/e2e/metrics-hotspots.spec.ts
cd ..
```

### 6. Git Diff Check
Ensure no whitespace, BOM, or CRLF anomalies:
```bash
git diff --check
```

---

## Architectural Guidelines

When adding or refactoring code:

1. **One Index Principle**: The backend graph store (`backend/graph_store.py`) is the source of truth. Do not build UI-specific or agent-specific shadow indices.
2. **Deterministic Security Engines**: The 6 security engines (`backend/security_scanner.py` and `backend/taint.py`) must produce deterministic results with zero LLM hallucinations. AST sinks, Shannon entropy, CVE lookup maps, and taint flows are static-analysis driven.
3. **Redaction by Default**: High-entropy strings and credentials must be masked with `<redacted>` before entering memory stores, log files, or API payloads.
4. **Topological Invariants**: Dependency ordering in `backend/onboarding.py` must maintain DAG properties (Kahn's topological sort).
5. **No Destructive Operations**: Scaffolder (`backend/scaffolder.py`) and patch generators (`generate_security_patch`) must never overwrite user code silently without explicit confirmation.
6. **Preserve Documentation & Comments**: Always preserve existing file comments, license headers, and architectural docstrings.

---

## Commit Message Convention

RepoScope follows the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat(scope): ...` — New feature or major capability
- `fix(scope): ...` — Bug fix or error resolution
- `docs(scope): ...` — Documentation updates
- `test(scope): ...` — Unit or E2E test additions
- `refactor(scope): ...` — Code restructuring without feature or bug changes
- `chore(scope): ...` — Build, release, or dependency maintenance

*Example*:
`feat(security): add AST injection sink scanner and SARIF 2.1.0 exporter`

---

## Pull Request Guidelines

1. **Focused Scope**: One logical change or milestone per PR.
2. **Automated Verification**: Ensure all backend tests, frontend builds, and extension tests pass.
3. **No Secrets**: Never commit `.env` files, API keys, or proprietary test repositories.
4. **Update Documentation**: When introducing or updating an API endpoint, update [`docs/API.md`](docs/API.md) and [`README.md`](README.md).

---

## Community & Code of Conduct

All contributors are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any concerns to the maintainer [@adityapatel5912](https://github.com/adityapatel5912).
