# RepoScope

![RepoScope hero](docs/screenshots/hero.png)

> See your repo. Understand it. Track it.

![License](https://img.shields.io/badge/License-MIT-yellow) ![React](https://img.shields.io/badge/React-18-61DAFB) ![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688) ![IBM%20Bob](https://img.shields.io/badge/Built%20with-IBM%20Bob%20%2B%20Z%20Code-F0503C)

RepoScope turns any GitHub repository into an interactive architecture graph,
answers questions about it in plain English with citations, and tracks changes
over time. Built with **IBM Bob** (most tasks) and **Z Code** (complex tasks)
for the IBM Bob 2.0 Hackathon.

---

## 📸 Screenshots

### Full workspace
![RepoScope hero](docs/screenshots/hero.png)
*File tree, layered architecture graph, cited chat answers, and stats in one view.*

### Architecture graph
![Graph](docs/screenshots/graph.png)
*Layered graph — client, backend, storage, external, compute — with legend, cluster bands, and right-angle edges.*

### Chat with citations
![Chat](docs/screenshots/chat.png)
*Ask anything — every answer cites files, functions, and line numbers pulled from the real code graph.*

### Code tours
![Tour](docs/screenshots/tour.png)
*Guided walkthroughs step through any module — the graph pans to each stop with numbered badges and a progress bar.*

### Impact analysis
![Impact](docs/screenshots/impact.png)
*See the blast radius of a change before you make it — target, direct, transitive, and unaffected states on the graph.*

### Tracking
![Tracking](docs/screenshots/tracking.png)
*Commits, PRs, issues, and releases — checked on demand, grouped by change type.*

---

## 🎬 Demo

### One-click demo repos
Click either button in the sidebar to load a real repository instantly:

- **[Verdict](https://github.com/adityapatel5912/Verdict)** — Decision stress-test lab (Python + React)
- **[StudyRot](https://github.com/adityapatel5912/StudyRot)** — Study rotation scheduler

![Demo repos](docs/screenshots/demo-repos.png)

### Or load your own
Paste any public GitHub URL in the top bar. For private repos, add a GitHub
PAT in the sidebar (BYOK — stored in memory only, never written to disk).

---

## 🎥 Pitch Deck

- 📊 **[pitch-deck.pdf](frontend/public/pitch/pitch-deck.pdf)** — 10 slides
- 🎞️ **[pitch-deck.pptx](frontend/public/pitch/pitch-deck.pptx)** — editable
- 📝 **[pitch-deck.md](frontend/public/pitch/pitch-deck.md)** — text version
- 🎤 **[pitch-script.md](frontend/public/pitch/pitch-script.md)** — 3-minute video script
- 🗒️ **[slide-notes.md](frontend/public/pitch/slide-notes.md)** — per-slide talking points
- 🖼️ **[thumbnail.png](frontend/public/pitch/thumbnail.png)** — video thumbnail

---

## 🤖 Built with IBM Bob + Z Code

RepoScope's primary build was driven through **IBM Bob 2.0** across 8 guided
sessions. **Z Code (GLM)** paired on the complex tasks: the editorial UI
redesign, the dagre graph layout diagnosis and camera fix, the hardening and
regression passes, and the submission assets.

| Session | Task | Screenshot |
|---|---|---|
| 1 | Full build — all Bob-owned tasks complete | ![s1](docs/bob_sessions/session-01-build-complete.png) |
| 2 | Frontend + graph renderer (Aurora UI) | ![s2](docs/bob_sessions/session-02-frontend-ui.png) |
| 3 | Critical bug fixes (SSE · graph · README) | ![s3](docs/bob_sessions/session-03-critical-bugfixes.png) |

Full session log: [docs/bob_sessions/bob-session-export.md](docs/bob_sessions/bob-session-export.md) ·
Details: [docs/BOB_SESSIONS.md](docs/BOB_SESSIONS.md)

---

## ✨ Features

- **Architecture Graph** — layered pastel graph (client / backend / storage /
  external / compute), dagre layout, right-angle edges, cluster bands, legend,
  zoom controls, PNG + SVG export
- **Conversational Q&A** — SSE-streamed answers with file/function/line
  citations, dark code blocks with copy buttons, voice input
- **Code Tours** — guided step-by-step walkthroughs of any module, numbered
  badges on the graph, progress bar, auto-pan camera
- **What-If Impact Analysis** — blast radius (direct + transitive) with
  risk score, narrative, suggested tests, and on-graph highlighting
- **Repo Tracking** — new commits, PRs, issues, releases on demand, grouped
  by change type with breaking-change flags
- **Reverse Build Prompt** — one click turns any repo into an agent-ready
  "Build me a…" prompt (copy or save as .md)
- **File Tree** — GitIngest-style tree, search filter, single-file download
- **BYOK** — GitHub PAT for private repos; memory-only storage
- **Multi-key rotation** — comma-separated keys per LLM provider; 429s rotate
  automatically, providers chain OpenRouter → Groq → NVIDIA NIM
- **Health system** — `GET /api/health` reports uptime, memory, key counts

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/adityapatel5912/RepoScope.git
cd RepoScope

# 2. Configure environment
cp .env.example .env
# Edit .env — add at least one LLM key (OpenRouter / Groq / NVIDIA)

# 3. Backend
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev

# 5. Open http://localhost:5173 and click a demo repo
```

---

## ⚙️ Configuration

| Variable | Required | Purpose |
|---|---|---|
| `OPENROUTER_API_KEYS` | Yes* | Primary LLM — comma-separate for rotation |
| `GROQ_API_KEYS` | Yes* | Secondary LLM — comma-separate for rotation |
| `NVIDIA_API_KEYS` | Fallback | Tertiary LLM — comma-separate for rotation |
| `Models_OPENROUTER` / `Models_GROQ` / `Models_NVIDIA` | No | Model overrides (first entry wins) |
| `Base_URL_OPENROUTER` / `Base_URL_GROQ` / `Base_URL_NVIDIA` | No | OpenAI-compatible endpoints |
| `GITHUB_TOKENS` | Optional | Raises GitHub API limits — comma-separate |
| `CODEBASE_MEMORY_PATH` | No | MCP codebase-memory binary (graph fallback) |

\* At least one provider needs a key. Legacy single-key variables
(`OPENROUTER_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`, `GITHUB_PAT`) are
still supported as fallbacks. See [.env.example](.env.example).

---

## 🏗️ Architecture

```
React UI (Vite + TS)
   │  SSE: context → token → tracking → done | error
   ▼
FastAPI (Python 3.11)
   ├─ repo_loader      clone + README + state
   ├─ graph_builder    AST/regex → nodes + edges
   ├─ orchestrator     graph + README → LLM context
   ├─ key_rotator      multi-key round-robin per provider
   ├─ runtime_config   OpenRouter → Groq → NVIDIA NIM chain
   ├─ mcp_client       GitHub REST + codebase-memory MCP
   └─ tour_generator / impact_analyzer / repo_tracker
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full reference.

---

## ☁️ Deployment

- **Backend**: Render (via [`render.yaml`](render.yaml)) — health check `/api/health`
- **Frontend**: Vercel (via [`frontend/vercel.json`](frontend/vercel.json)) — proxies `/api/*` to the Render service

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Features](docs/FEATURES.md)
- [Development](docs/DEVELOPMENT.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Screenshots](docs/SCREENSHOTS.md)
- [Bob Sessions](docs/BOB_SESSIONS.md)
- [Knowledge Graph Schema](docs/KNOWLEDGE_GRAPH_SCHEMA.md)
- [Runbooks](docs/RUNBOOKS.md)
- [Contributing](CONTRIBUTING.md)

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 6, TypeScript (strict), React Flow, dagre, Tailwind |
| Backend | Python 3.11, FastAPI, SSE (StreamingResponse), httpx, GitPython |
| LLM | OpenRouter (primary) → Groq → NVIDIA NIM, multi-key rotation |
| Code graph | AST (Python) + regex (JS/TS) via graph_builder, MCP fallback |
| Repo data | GitHub REST API v3 |

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

## 🙏 Acknowledgments

Built with **IBM Bob 2.0** and **Z Code**. Graph aesthetic inspired by
GitDiagram. Reverse prompt inspired by GitReverse. Repo structure format
inspired by Gitingest.
