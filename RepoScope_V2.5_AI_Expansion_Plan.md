# **RepoScope V2.5+: Universal Agent Harness & Architectural Mind-Map Plan**

**Target Repository:** `adityapatel5912/RepoScope-V2` (Clean Repository Migration from [adityapatel5912/RepoScope](https://github.com/adityapatel5912/RepoScope/))  
**Core Focus:** Universal Agent Harness (9 Agents), NotebookLM Vertical Mind-Map UI, TOON Context Efficiency & Zero-Clone Ecosystem  
**Live Reference Endpoints:** [RepoScope Web App](https://repo-scope-nu.vercel.app/) \| [RepoScope Render API Health](https://reposope.onrender.com/api/health)

# **\# RepoScope V2.5 Master Plan: Universal Agent Harness, Vertical NotebookLM Mind-Map UI & Zero-Clone Ecosystem**

**Target Repository:** `adityapatel5912/RepoScope-V2` (Upgraded from [adityapatel5912/RepoScope](https://github.com/adityapatel5912/RepoScope/))  
**Live Reference Endpoints:** [RepoScope Web App](https://repo-scope-nu.vercel.app/) \| [RepoScope Render API Health](https://reposope.onrender.com/api/health)  
**Target Competitions Ready:** [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) (\$50k, Oct 30\) and [Kiroween 2026](https://kiroween.devpost.com/) (\$100k, Oct 30 \- Dec 4\)

## **\#\# 1\. Executive Summary (Removing Single-Vendor Lock-In)**

Instead of tying RepoScope V2 to the Meta hackathon, this updated specification transforms RepoScope into a **Universal Architectural Mind-Map Explorer and MCP Context Harness** for every major AI coding agent.  
Key upgrades over RepoScope v3.0 ([RepoScope Weaknesses and Roadmap](https://docs.google.com/document/d/1mTjCseWSQkRBcTQOr7RCCJ36AOWdC36gFlQAvuFCiwQ/edit?usp=drivesdk&ouid=115448831606209536315)):

* **Universal 9-Agent One-Click Harness (`reposcope init` and Web UI Modal):** Supports **Claude Code**, **Google Antigravity**, **Cursor**, **AWS Kiro**, **Windsurf (Cascade)**, **GitHub Copilot**, **OpenAI Codex CLI**, **Cline / Roo Code**, and **Zed** ([MCP Configuration Across AI Agents](https://platform.uno/blog/mcp-configuration-across-ai-agents/), [Antigravity MCP Docs](https://antigravity.google/docs/mcp/), [Kiro MCP Docs](https://kiro.dev/docs/mcp/configuration/)).  
* **Vertical Gemini NotebookLM-Style Collapsible Mind-Map Graph (`KnowledgeGraphView.tsx`):** Adapts the clean, progressive expand/collapse tree of [NotebookLM Mind Maps](https://www.tenorshare.ai/ai-tips/notebooklm-mind-map.html) into a **Vertical Top-Down (TB)** hierarchy:  
  * **Tier 0 (Root Pill):** Repository name, tech stack badges, file count, and overall risk score.  
  * **Tier 1 (Domain Classification Pillars):** `Backend`, `Frontend`, `AI & MCP`, `Assets & Config`, `Deployment & CI/CD`, and `Tests & QA`.  
  * **Tier 2 (Sub-Modules / Folders):** Revealed smoothly downward when clicking the expand arrow on any Tier 1 pillar.  
  * **Tier 3 (Interactive File Cards):** Revealed when expanding a folder; every file card includes one-click buttons to **Open in GitHub**, **Open in VS Code / Cursor** (`vscode://file/...`), or **Highlight Blast Radius**.  
  * **Tier 4 (Functions & Classes):** Expands exported functions, line numbers, and caller counts below any selected file card.  
* **85% Token-Saving MCP Context Efficiency (TOON \+ AST Skeletons):** Uses **TOON (Token-Oriented Object Notation)** ([TOON MCP Efficiency](https://medium.com/@adhungel2/toon-making-mcp-server-responses-actually-efficient-947a8038af0f)) and function signature skeletons so AI agents get full architectural context in \~250 tokens instead of 4,000+ tokens.  
* **Zero-Clone Standalone Packages (`npx reposcope-mcp`, `pip install reposcope-ai`, VS Code Extension):** Publishes standalone packages so any developer can use RepoScope inside their own project without ever cloning the RepoScope repository.

## **\#\# 2\. Pillar 1: Universal 9-Agent One-Click Harness Configurator**

Implement `backend/harness_generator.py` (`GET /api/harness/config`) and `frontend/src/components/HarnessModal.tsx` to support one-click setup across all 9 coding agents:

* **Claude Code:** Project config `.claude/mcp.json` (and `.mcp.json`), global `~/.claude.json`, instructions in `CLAUDE.md`, skills in `.claude/skills/`, and CLI one-liner `claude mcp add reposcope -- npx -y reposcope-mcp@latest`.  
* **Google Antigravity:** Project config `mcp_config.json`, global `~/.gemini/config/mcp_config.json`, instructions in `AGENTS.md`, and skills in `.agents/skills/`.  
* **Cursor:** Project config `.cursor/mcp.json`, global `~/.cursor/mcp.json`, rules in `.cursor/rules/reposcope.mdc`, skills in `.cursor/skills/`, plus one-click `cursor://anysphere.cursor-deeplink/mcp/install` URI.  
* **AWS Kiro:** Project config `.kiro/settings/mcp.json`, global `~/.kiro/settings/mcp.json`, and steering rules in `.kiro/steering/reposcope.md`.  
* **Windsurf (Cascade):** Project config `.windsurf/mcp_config.json`, global `~/.codeium/windsurf/mcp_config.json`, and rules in `.windsurfrules`.  
* **GitHub Copilot / VS Code:** Project config `.vscode/mcp.json` and `.github/mcp.json`, plus `.github/copilot-instructions.md` and `vscode:mcp/install` URI.  
* **OpenAI Codex CLI:** Project config `.codex/config.toml` (TOML format) and `AGENTS.md`.  
* **Cline / Roo Code:** Project config `.roo/mcp.json` and `.clinerules` / `.roorules`.  
* **Zed Editor:** Project config `.zed/settings.json` (`context_servers` block) and `.rules`.

## **\#\# 3\. Pillar 2: Research-Backed MCP Skills & Context Efficiency Engine**

### **\#\#\# 3.1 Five Bundled MCP Skills (skills/\*/SKILL.md)**

* **`blast-radius-guard`:** Calls `get_symbol_blast_radius` before modifying any shared file or function; if risk score \>= 45 or callers \>= 3, checks caller signatures via `get_dependency_lineage` and updates affected unit tests automatically.  
* **`zero-grep-architect`:** Replaces 15+ blind `grep`/`find` calls at the start of an agent session with a single call to `get_mindmap_hierarchy(format="toon")` and `get_ast_skeleton(file_path)`.  
* **`pr-contract-shield`:** Calls `diff_interface_contracts` and `run_security_scan` prior to committing or opening a PR, catching broken function signatures and layer violations (such as UI importing DB directly).  
* **`onboarding-navigator`:** Calls `get_ranked_reading_path` (Row 0 entry points to Row 5 leaf modules) and generates an interactive guide with clickable `vscode://file/...` and GitHub links.  
* **`dead-code-surgeon`:** Calls `find_orphan_nodes_and_cycles` to surface unused exports, orphan files, and circular dependencies.

### **\#\#\# 3.2 MCP Context Efficiency (backend/context\_compressor.py)**

* **TOON Format (`format="toon"` default):** Indentation-scoped compact table output that strips repetitive JSON keys and cuts MCP response tokens by 80-85%.  
* **AST Skeleton Mode (`detail_level="skeleton"`):** Returns only imports, class/function signatures, line numbers, docstrings, and caller counts without dumping raw function bodies.  
* **Delta Hash Caching (`since_hash`):** Returns `"UNCHANGED"` (5 tokens) when the workspace AST hash has not changed since the previous tool call.

## **\#\# 4\. Pillar 3: Vertical Gemini NotebookLM Mind-Map Graph UX**

### **\#\#\# 4.1 Deterministic 6-Pillar Classification (backend/mindmap\_classifier.py)**

Every file in any loaded repository is classified into one of 6 top-level pillars under the Root Repository Node:

* **`backend` (Backend & Core Engine):** `backend/`, `server/`, `api/`, `services/`, `routes/`, `models/`, `db/`, `.py`, `.go`, `.rs`, `.java`.  
* **`frontend` (Frontend & UI):** `frontend/`, `client/`, `web/`, `src/components/`, `src/pages/`, `.tsx`, `.jsx`, `.vue`, `.css`.  
* **`ai_mcp` (AI, Agents & MCP):** `*mcp*`, `*agent*`, `*llm*`, `*orchestrat*`, `.agents/`, `.claude/`, `.cursor/`, `.kiro/`.  
* **`assets` (Assets, Docs & Config):** `assets/`, `public/`, `docs/`, `README.md`, `package.json`, `pyproject.toml`, `.json`, `.svg`, `.md`.  
* **`deployment` (Deployment & CI/CD):** `.github/workflows/`, `Dockerfile`, `docker-compose*`, `render.yaml`, `vercel.json`, `scripts/`.  
* **`tests` (Tests & Verification):** `tests/`, `__tests__/`, `e2e/`, `test_*.py`, `*.test.ts`, `*.spec.ts`.

### **\#\#\# 4.2 Vertical Top-Down Interactive Layout (KnowledgeGraphView.tsx)**

* **Orientation:** Uses Dagre / ELK with `rankdir: 'TB'` (Top-to-Bottom vertical mind map) and smooth bezier connectors (with a toolbar toggle to switch between Vertical `TB` and Horizontal `LR`).  
* **Progressive Expand / Collapse Arrows:** Initially renders only Tier 0 (Repo Root) and Tier 1 (the 6 Classification Pillars). Clicking the expand arrow button on a pillar reveals its folders/files downward; clicking a file's function badge reveals its functions/classes.  
* **Direct File Actions:** Every file card includes three buttons:  
  * **1\. Open in GitHub:** Opens `https://github.com/{owner}/{repo}/blob/{branch}/{rel_path}`.  
  * **2\. Open in VS Code / Cursor:** Opens `vscode://file/{local_root}/{rel_path}:{line}:1` (or `cursor://file/...`, or native `vscode.window.showTextDocument` inside the VS Code extension).  
  * **3\. Show Blast Radius:** Highlights upstream callers in amber/crimson and downstream dependencies in cyan on the mind map.

## **\#\# 5\. Pillar 4: Zero-Clone Standalone Packages (VS Code, npm, PyPI)**

* **npm Package (`packages/reposcope-mcp` \-\> `npx reposcope-mcp`):**  
  * `npx reposcope-mcp init` — Auto-detects or prompts for Claude Code, Antigravity, Cursor, Kiro, Windsurf, Copilot, or Codex and writes the MCP config \+ 5 skills into the current project without cloning RepoScope.  
  * `npx reposcope-mcp serve` — Runs the local stdio MCP server in any repository.  
* **PyPI Package (`pyproject.toml` \-\> `pip install reposcope-ai` / `uvx reposcope-ai`):**  
  * Provides `reposcope init`, `reposcope serve . --port 4100`, `reposcope mcp`, and `reposcope blast`.  
* **VS Code / Cursor / Kiro Extension (`extensions/vscode/` \-\> `reposcope-vscode`):**  
  * Bundles a zero-backend local workspace scanner so opening any folder in VS Code, Cursor, or Kiro displays the Vertical Mind-Map Sidebar, Status Bar Blast-Radius counter, CodeLens caller badges, and One-Click Agent Harness Configurator without needing to clone RepoScope.

## **\#\# 6\. THE MASTER ONE-SHOT AGENT PROMPT (Copy-Paste to Execute Everything)**

Copy and paste the block below into **Claude Code**, **Antigravity**, **Cursor**, or **Kiro** to execute all 8 phases in one uninterrupted run:

```
ROLE & OBJECTIVE:
You are a Principal Full-Stack Systems, AI Protocol, and UX Architect. Execute a complete, end-to-end upgrade of this repository into RepoScope V2: The Universal Architectural Mind-Map Explorer & MCP Safety Harness for AI Coding Agents. Do NOT stop after planning: execute all 8 phases sequentially, run the verification suite at the end, fix any failures immediately, and do not conclude until all L1/L2/L3 tests, frontend builds, and package builds pass with zero errors.

PHASE 1 — FIX ALL 9 FAILING L1 UNIT TESTS & UNBLOCK L2/L3 CI:
1. Run `pytest -q` and inspect all failing assertions in `backend/tests/`.
2. Add deterministic mocked fixtures for external LLM and GitHub API calls (`ask_llm`, `key_rotator`, `repo_loader`) so `L1 · unit tests` pass 100% offline in CI runners without requiring external API keys.
3. Align all Pydantic v2 response schemas across `/api/load-repo`, `/api/chat`, `/api/impact/pr`, `/api/security`, and `/api/scaffold` so `L2 · API contract` tests pass.
4. Create a deterministic static fixture graph at `backend/tests/fixtures/demo_repo_graph.json` so `L3 · browser journeys` pass reliably.

PHASE 2 — VERTICAL GEMINI NOTEBOOKLM MIND-MAP GRAPH & UI/UX OVERHAUL:
1. Create `backend/mindmap_classifier.py` and integrate it into `backend/graph_builder.py`:
   - Classify every repository file into 6 top-level domain pillars: `backend` (Backend & Core), `frontend` (Frontend & UI), `ai_mcp` (AI, Agents & MCP), `assets` (Assets, Docs & Config), `deployment` (Deployment & CI/CD), and `tests` (Tests & QA).
   - Emit a hierarchical Mind-Map tree structure alongside dependency graph edges (`imports`, `calls`, `inherits`, `exports`), including `github_url` and `vscode_uri` metadata on every file and symbol node.
2. Overhaul `frontend/src/components/KnowledgeGraphView.tsx`:
   - Default to a Vertical Top-Down (`rankdir: 'TB'`) NotebookLM-style Collapsible Mind Map using Dagre and smooth bezier connectors.
   - Render only Tier 0 (Repository Root Pill) and Tier 1 (the 6 Domain Classification Pillars) initially so initial load is <50ms and clutter-free.
   - Add an interactive Expand / Collapse arrow button on every Pillar, Folder, and File node: clicking a Pillar's arrow expands its folders/files downward; clicking a file's function badge expands its classes/functions.
   - Add three direct action buttons on every File Card: (1) Open in GitHub (`https://github.com/...`), (2) Open in VS Code / Cursor (`vscode://file/...` or `cursor://file/...` with a local workspace root setting saved in `localStorage`), and (3) Highlight Blast Radius.
   - Add a Mind-Map Toolbar with: Expand All, Collapse to Pillars, Toggle Vertical TB / Horizontal LR, Toggle Mind Map / Dependency Network, and live search auto-expand.

PHASE 3 — UNIVERSAL 9-AGENT ONE-CLICK HARNESS CONFIGURATOR:
1. Create `backend/harness_generator.py` and route `GET /api/harness/config`:
   - Generate exact MCP config files and skill bundles for all 9 harnesses:
     (1) Claude Code (`.claude/mcp.json`, `CLAUDE.md`, `claude mcp add`),
     (2) Google Antigravity (`mcp_config.json`, `~/.gemini/config/mcp_config.json`, `AGENTS.md`, `.agents/skills/`),
     (3) Cursor (`.cursor/mcp.json`, `.cursor/rules/reposcope.mdc`, `cursor://anysphere.cursor-deeplink/mcp/install`),
     (4) AWS Kiro (`.kiro/settings/mcp.json`, `.kiro/steering/reposcope.md`),
     (5) Windsurf (`.windsurf/mcp_config.json`, `.windsurfrules`),
     (6) GitHub Copilot / VS Code (`.vscode/mcp.json`, `.github/mcp.json`, `.github/copilot-instructions.md`),
     (7) OpenAI Codex CLI (`.codex/config.toml`, `AGENTS.md`),
     (8) Cline / Roo Code (`.roo/mcp.json`, `.clinerules`),
     (9) Zed (`.zed/settings.json`).
2. Create `frontend/src/components/HarnessModal.tsx` wired to a top-bar "Connect AI Agent (1-Click)" button with tabs for all 9 agents, one-click CLI copy (`npx reposcope-mcp init --agent all`), one-click Config Zip download, and a Cloud HTTP vs. Local Stdio toggle.

PHASE 4 — TOKEN-COMPACT MCP SERVER (TOON + SKELETON MODE) & 5 SKILLS:
1. Create `backend/context_compressor.py` implementing TOON (Token-Oriented Object Notation, `format="toon"` default for 85% token reduction), AST Signature Skeleton extraction (`detail_level="skeleton"`), and SHA-256 delta caching (`since_hash`).
2. Replace `backend/mcp_client.py` with `backend/mcp_server.py` supporting both `stdio` and `streamable_http` (mounted at `/mcp` in `backend/main.py`) exposing 7 tools: `get_mindmap_hierarchy`, `get_symbol_blast_radius`, `get_ast_skeleton`, `get_dependency_lineage`, `diff_interface_contracts`, `get_ranked_reading_path`, and `run_security_scan`.
3. Create 5 production `SKILL.md` playbooks in `.agents/skills/` and `.claude/skills/`: `blast-radius-guard`, `zero-grep-architect`, `pr-contract-shield`, `onboarding-navigator`, and `dead-code-surgeon`.

PHASE 5 — ZERO-CLONE STANDALONE PACKAGES (NPM, PYPI & VS CODE EXTENSION):
1. Create `packages/reposcope-mcp/` (`name: "reposcope-mcp"`, `version: "2.0.0"`) with zero-clone CLI commands: `npx reposcope-mcp init`, `npx reposcope-mcp serve`, and `npx reposcope-mcp inspect .`. Compile and verify with `npm pack --dry-run`.
2. Create/update root `pyproject.toml` (`name = "reposcope-ai"`, `version = "2.0.0"`) and `backend/cli.py` supporting `reposcope init`, `reposcope serve .`, `reposcope mcp`, and `reposcope blast`.
3. Upgrade `extensions/vscode/` (`reposcope-vscode` v2.0.0) with a standalone local workspace scanner, Vertical Mind-Map Sidebar Webview, Status Bar Blast-Radius badge, CodeLens caller counts, and Command Palette `RepoScope: Configure AI Agent Harness`.

PHASE 6 — MULTI-PROVIDER BYOK & NEBIUS x NVIDIA NEMOTRON ROUTING:
1. Upgrade `backend/ai_byok.py` and `backend/key_rotator.py` with HTTP 429 `Retry-After` cooldowns and support for Nebius Token Factory (`https://api.studio.nebius.ai/v1`) + NVIDIA NIM (`https://integrate.api.nvidia.com/v1`) running NVIDIA Nemotron 3 Ultra and Nemotron Super/Nano, alongside Groq, OpenRouter, Gemini, Anthropic, OpenAI, and local Ollama.

PHASE 7 — PRE-CACHED INSTANT DEMO REPOSITORIES:
1. Pre-seed 3 instant-load cached repositories (`adityapatel5912/RepoScope`, `Verdict`, and `StudyRot`) in `backend/fixtures/preloaded_repos/` with pre-computed Vertical Mind-Map trees so landing page demo chips render in <50ms.

PHASE 8 — END-TO-END VERIFICATION & README:
1. Run and verify exit code 0 on:
   - `python3 -m compileall -q backend/`
   - `pytest -q backend/tests/ --maxfail=1 --disable-warnings`
   - `npm --prefix frontend run build`
   - `npm --prefix packages/reposcope-mcp run build`
   - `npm --prefix extensions/vscode run compile`
2. Update `README.md` with the Vertical Mind-Map architecture, the 9-Agent One-Click Harness table, and zero-clone `npx reposcope-mcp` / `pip install reposcope-ai` instructions.
```

* 

# **RepoScope V2.6 Addendum: High-Precision Graph Accuracy, Verified Chat Citations 2.0, Reverse Prompt 2.0 & Executable Scaffolding \+ Updated Master One-Shot Prompt**

## **1\. Pillar A: Spot-On Graph Accuracy & Deep Architectural Understanding (`backend/graph_builder.py` & `backend/symbol_resolver.py`)**

To eliminate missing edges, false dead-code flags, and shallow file-only graphs ([CodeTruth Verification Layer](https://github.com/AlaikAsif/CodeTruth), [Aider PageRank RepoMap](https://aider.chat/docs/repomap.html)), upgrade the graph engine with five deterministic resolution passes:

### **1.1 Cross-File Symbol & Alias Resolution (`backend/symbol_resolver.py`)**

* **TypeScript / JavaScript Path Alias & Barrel Unwrapping:**  
  * Parse `tsconfig.json` and `jsconfig.json` (`compilerOptions.baseUrl` and `compilerOptions.paths` such as `@/* -> src/*` or `@components/* -> src/components/*`) so aliased imports resolve to exact physical file nodes instead of being dropped as external packages.  
  * Unwrap barrel files (`index.ts`, `index.js`, `__init__.py`): trace `export * from './module'` and `export { X } from './Y'` chains so callers importing from a barrel link directly to the concrete symbol definition.  
* **Python Relative & Package Import Resolver:**  
  * Resolve multi-dot relative imports (`from ..services.auth import verify_token`), `pyproject.toml` / `setup.py` package roots, and FastAPI `Depends(...)` / decorator injections (`@router.get`, `@app.post`) into explicit `calls` and `routes_to` edges.  
* **Cross-Boundary Frontend-to-Backend API Linker (`api_calls` Edge Type):**  
  * Scan frontend `fetch()`, `axios.*()`, and `EventSource()` calls for route paths (such as `/api/load-repo`, `/api/chat`, `/api/impact/pr`) and automatically wire **Cross-Stack Edges (`frontend_file -> backend_route_function`)** so clicking a React component shows which FastAPI endpoint it calls, and modifying a FastAPI route highlights the broken React components in the blast radius.

### **1.2 PageRank Architectural Importance & Semantic Role Tagging**

* Compute **Personalized PageRank (PPR)** and **Betweenness Centrality** across the symbol call graph ([PageRank Repo Map](https://github.com/NousResearch/hermes-agent/issues/535)) to rank every file and symbol by true architectural criticality rather than simple line count.  
* Assign deterministic **Architectural Role Badges** to every node: `Entry Point`, `API Controller`, `Core Domain Engine`, `State / Store`, `Data Model / Schema`, `External Adapter`, `Shared Utility`, or `Test Suite`.

## **2\. Pillar B: Verified Chat Citations 2.0 (`backend/citation_verifier.py` & `frontend/src/components/ChatPanel.tsx`)**

### **2.1 Zero-Hallucination AST Citation Grounding (`backend/citation_verifier.py`)**

* **Exact Line-Number Injection Before LLM Prompting:** When `orchestrator.py` retrieves AST chunks for a question, prepend exact 1-indexed line numbers and symbol headers to every code line (`[backend/graph_builder.py:L42-L89 | def build_graph_from_repo]`) so the LLM never guesses line numbers.  
* **Post-Generation AST Citation Resolver & Auto-Healer:**  
  * Parse every `[file_path:Lstart-Lend]` or `(file_path:line)` citation emitted in the SSE stream.  
  * Verify the cited file and line range against the in-memory AST Symbol Table: if the LLM cites `services/auth.py:40` or `verify_token` with a slightly shifted line number, automatically snap the citation to the exact AST `start_line` and `end_line` of `verify_token` (`backend/services/auth.py:L42-L68`) and attach a **Verified AST Badge (`verified: true`, `confidence: 1.0`)**.

### **2.2 Interactive Citation Chips & Mind-Map Auto-Focus (`ChatPanel.tsx`)**

Replace plain text citations in `ChatPanel.tsx` with interactive **Citation Pills** (`[📄 graph_builder.py:42-89 · build_graph_from_repo ✓]`):

1. **1\. Hover Code Preview Popover:** Hovering any citation pill opens an instant syntax-highlighted 15-line code preview tooltip showing the exact AST function without leaving the chat.  
2. **2\. 1-Click Mind-Map Auto-Expand & Camera Pan:** Clicking a citation pill automatically expands the corresponding Tier-1 Pillar (`Backend`), Tier-2 Folder, and Tier-3 File Card on the **Vertical NotebookLM Mind Map**, centers the React Flow camera on that node, and pulses its border in emerald green.  
3. **3\. Direct Split-Button Actions:** Each citation pill includes mini icons for **\[Open in VS Code at Line 42\]** (`vscode://file/{root}/{path}:42:1`) and **\[Open on GitHub \#L42-L89\]**.

## **3\. Pillar C: Reverse Prompt 2.0 — Multi-Mode Agent Blueprint Compiler (`backend/reverse_prompt.py` & `ReversePromptPanel.tsx`)**

Currently, RepoScope's Reverse Prompt generates a single generic text summary. Upgrade `/api/reverse-prompt` into a deterministic **4-Mode Agent Blueprint Compiler** backed by the PageRank AST graph:

1. **1\. Mode 1: Full-System Agent Rebuild Blueprint (`REBUILD_SPEC.md`):** Compiles the repository's complete system architecture, tech stack versions, environment variables, database schemas, API endpoint contracts (request/response schemas), and step-by-step Dependency-Ordered Build Sequence (Row 0 foundation models \-\> Row 5 UI views) so any coding agent can recreate the entire system from scratch.  
2. **2\. Mode 2: Feature-Scoped Subgraph Slice Prompt (`Clone Just This Feature`):** Lets the user select any node or feature cluster on the Mind Map (for example, *"Extract only the SSE Streaming Chat \+ Key Rotator system"*). Traces the 2-hop dependency closure of that feature and generates a self-contained prompt \+ exact interface signatures to transplant that feature into a brand-new project.  
3. **3\. Mode 3: Spec-Driven Development Bundle (`CLAUDE.md` / `AGENTS.md` / `.kiro/specs/` / `llms.txt`):** Generates a downloadable specification bundle matching industry standards (`llms.txt`, `AGENTS.md`, and `.kiro/specs/requirements.md` \+ `design.md` \+ `tasks.md`).  
4. **4\. Mode 4: Visual \+ Structural Prompt Export:** Embeds the TOON Mind-Map hierarchy, Mermaid sequence diagrams of core execution flows, and top-20 PageRank AST function signatures into a single copy-pasteable prompt with a live token counter (`Compact 2k Tokens` \| `Standard 8k Tokens` \| `Full 32k Tokens`).

## **4\. Pillar D: Executable Scaffolding 2.0 (`backend/scaffolder.py` & `ScaffoldPanel.tsx`)**

Currently, RepoScope's Scaffold feature generates a single starter file snippet (`backend/main.py`). Upgrade `/api/scaffold` into an **Executable Multi-File Starter Kit & Feature Injector**:

1. **1\. Full Multi-File Project Tree Synthesis (Derived from the Live Graph):**  
   * Generates a complete, runnable project tree (10–25 files) mirroring the analyzed repository's real architecture patterns: `Dockerfile`, `docker-compose.yml`, `pyproject.toml` / `package.json`, `.env.example`, `README.md`, FastAPI/Express entry point, typed route controllers, database session layer, React frontend shell, and a pre-configured `pytest` / `vitest` test suite.  
   * Pre-bundles the **RepoScope MCP Config & 5 Agent Skills** (`.claude/mcp.json`, `mcp_config.json`, `.cursor/mcp.json`, `.agents/skills/`) right inside every generated starter kit.  
2. **2\. 3-Way Instant Delivery in `ScaffoldPanel.tsx`:**  
   * **Interactive File-Tree Previewer:** Browse every generated file with syntax highlighting before downloading.  
   * **1-Click .zip Download (`POST /api/scaffold/download-zip`):** Streams an in-memory `zipfile` archive ready to unzip and run (`docker compose up` or `npm run dev`).  
   * **1-Click Terminal Bootstrap Command:** Generates a single copy-paste terminal command (`npx reposcope-mcp scaffold --from <owner/repo> --out ./my-new-app`) that materializes the entire folder structure locally in 2 seconds.

## **5\. UPDATED MASTER ONE-SHOT AGENT PROMPT (Append/Use This Complete Block in Your Coding Agent)**

Copy and paste the complete block below into **Claude Code**, **Antigravity**, **Cursor**, or **Kiro** to execute everything—including the **Spot-On Graph Resolver**, **Verified Chat Citations 2.0**, **Reverse Prompt 2.0**, **Executable Scaffolding 2.0**, **Vertical NotebookLM Mind Map**, **9-Agent Harness**, **TOON MCP Server**, and **Zero-Clone Packages**—in one shot:

```
ROLE & OBJECTIVE:
You are a Principal Full-Stack Systems, Compiler/AST, AI Protocol, and UX Architect. Execute a complete, end-to-end upgrade of this repository into RepoScope V2.6: The High-Precision Architectural Mind-Map, Verified Citation Engine, Reverse-Prompt Compiler, and Universal MCP Safety Harness for AI Coding Agents.

Do NOT stop after planning. Execute all 9 phases sequentially, run all verification commands at the end, fix any test or build failures immediately, and do not conclude until all L1/L2/L3 tests, frontend builds, and package builds pass with zero errors.

---

### PHASE 1: FIX ALL 9 FAILING L1 UNIT TESTS & UNBLOCK L2/L3 CI
1. Run `pytest -q` and inspect all failing assertions in `backend/tests/`.
2. Add deterministic mocked fixtures for external LLM and GitHub API calls (`ask_llm`, `key_rotator`, `repo_loader`) so `L1 · unit tests` pass 100% offline in CI runners without requiring external API keys.
3. Align all Pydantic v2 response schemas across `/api/load-repo`, `/api/chat`, `/api/impact/pr`, `/api/security`, `/api/reverse-prompt`, and `/api/scaffold` so `L2 · API contract` tests pass.
4. Create a deterministic static fixture graph at `backend/tests/fixtures/demo_repo_graph.json` so `L3 · browser journeys` pass reliably.

---

### PHASE 2: SPOT-ON GRAPH ACCURACY & CROSS-STACK SYMBOL RESOLUTION (`backend/symbol_resolver.py` & `backend/graph_builder.py`)
1. Create `backend/symbol_resolver.py` and integrate it into `backend/graph_builder.py`:
   - **TypeScript / JavaScript Alias & Barrel Resolver:** Parse `tsconfig.json` / `jsconfig.json` (`baseUrl` and `paths` aliases like `@/*`) and unwrap barrel re-exports (`index.ts`, `export * from`, `export { X } from`) so imports connect directly to the true target file and symbol.
   - **Python Relative Import & Decorator Resolver:** Resolve relative imports (`from ..module import X`) and FastAPI route/dependency decorators (`@router.get`, `@app.post`, `Depends(...)`).
   - **Cross-Stack Frontend-to-Backend API Linker (`api_calls` edges):** Detect frontend `fetch()`, `axios`, and `EventSource` calls targeting `/api/...` routes and wire explicit `api_calls` edges connecting the frontend component node directly to the backend route handler node.
   - **PageRank Centrality & Architectural Role Tagging:** Compute PageRank importance scores and tag every node with its semantic role (`Entry Point`, `API Controller`, `Core Engine`, `State/Store`, `Data Model`, `External Adapter`, `Utility`, `Test Suite`).

---

### PHASE 3: VERTICAL GEMINI NOTEBOOKLM MIND-MAP GRAPH & UI/UX OVERHAUL (`backend/mindmap_classifier.py` & `KnowledgeGraphView.tsx`)
1. Create `backend/mindmap_classifier.py` to classify every repository file into 6 top-level domain pillars: `backend` (Backend & Core), `frontend` (Frontend & UI), `ai_mcp` (AI, Agents & MCP), `assets` (Assets, Docs & Config), `deployment` (Deployment & CI/CD), and `tests` (Tests & QA). Attach `github_url` and `vscode_uri` to every file and symbol node.
2. Overhaul `frontend/src/components/KnowledgeGraphView.tsx`:
   - Default to a **Vertical Top-Down (`rankdir: 'TB'`) NotebookLM-Style Collapsible Mind Map** with smooth bezier curves.
   - **Initial Progressive State:** Render only Tier 0 (Repository Root Pill with tech stack + health score) and Tier 1 (the 6 Domain Classification Pillars) so initial render is <50ms and clutter-free.
   - **Expand / Collapse Chevron Buttons:** Clicking the arrow on a Tier 1 Pillar smoothly expands its Tier 2 folders and Tier 3 File Cards downward; clicking a file's function badge expands Tier 4 (functions/classes).
   - **Direct Action Bar on Every File Card:** Render 3 buttons on every file node: (1) `[GitHub ↗]` (`https://github.com/{owner}/{repo}/blob/{branch}/{path}`), (2) `[VS Code ⚡]` (`vscode://file/{localRoot}/{path}:{line}:1` or `cursor://file/...`), and (3) `[Blast Radius 🎯]`.
   - Add a Mind-Map Toolbar: `Expand All`, `Collapse to Pillars`, `Vertical TB / Horizontal LR`, `Mind Map / Dependency Network`, and live search auto-expand.

---

### PHASE 4: VERIFIED CHAT CITATIONS 2.0 (`backend/citation_verifier.py` & `ChatPanel.tsx`)
1. Create `backend/citation_verifier.py` and integrate into `backend/orchestrator.py`:
   - Prepend exact 1-indexed AST line numbers and symbol headers (`[path:Lstart-Lend | def symbol]`) to all retrieved code chunks before calling the LLM, using 2-hop PageRank AST GraphRAG instead of raw 4,000-character truncation.
   - Parse every citation in the LLM response, verify and snap line numbers against the indexed AST symbol table, and return structured citation metadata (`file_path`, `start_line`, `end_line`, `symbol_name`, `code_preview`, `verified: true`, `github_url`, `vscode_uri`, `node_id`).
2. Upgrade `frontend/src/components/ChatPanel.tsx`:
   - Render interactive **Verified Citation Pills** (`[📄 file.py:L42-89 · func_name ✓]`).
   - **Hover Preview:** Show a syntax-highlighted code snippet popover on hover.
   - **1-Click Mind-Map Sync:** Clicking a citation pill automatically expands the parent pillar on the Vertical Mind Map, pans/zooms the React Flow camera to that exact file node, and highlights it, alongside quick buttons to open the exact line in VS Code (`vscode://`) or GitHub (`#L42-L89`).

---

### PHASE 5: REVERSE PROMPT 2.0 & EXECUTABLE SCAFFOLDING 2.0 (`backend/reverse_prompt.py`, `backend/scaffolder.py`, Frontend Panels)
1. Upgrade `backend/reverse_prompt.py` and `ReversePromptPanel.tsx` into a **4-Mode Agent Blueprint Compiler**:
   - **Mode 1 (`Full System Rebuild Spec`):** Dependency-ordered build order (Row 0 -> Row 5), API contracts, data models, and architecture rules.
   - **Mode 2 (`Feature Subgraph Slice`):** Select any module/feature node on the Mind Map and export a self-contained prompt + 2-hop interface closure to clone just that feature.
   - **Mode 3 (`Agent Spec Bundle`):** Export `CLAUDE.md`, `AGENTS.md`, `llms.txt`, and `.kiro/specs/` (`requirements.md`, `design.md`, `tasks.md`).
   - **Mode 4 (`Token-Budgeted Context Pack`):** Toggle between `Compact TOON (2k tokens)`, `Standard Signatures (8k tokens)`, and `Full Blueprint (32k tokens)`.
2. Upgrade `backend/scaffolder.py` and `ScaffoldPanel.tsx` into an **Executable Multi-File Starter Kit Generator**:
   - Synthesize a complete, runnable 12–20 file starter project matching the repo's stack (backend routes, models, frontend shell, `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`, tests, and pre-installed `.claude/mcp.json` + `.agents/skills/`).
   - Add an interactive **Multi-File Tree & Code Previewer** in the UI, a **`POST /api/scaffold/download-zip`** endpoint for 1-click `.zip` download, and a 1-click terminal generator command (`npx reposcope-mcp scaffold --from <repo> --out ./my-app`).

---

### PHASE 6: UNIVERSAL 9-AGENT ONE-CLICK HARNESS CONFIGURATOR (`backend/harness_generator.py` & `HarnessModal.tsx`)
1. Create `backend/harness_generator.py` (`GET /api/harness/config`) and `frontend/src/components/HarnessModal.tsx` supporting 1-click setup for all 9 coding agents:
   - **Claude Code** (`.claude/mcp.json`, `CLAUDE.md`, `claude mcp add`), **Google Antigravity** (`mcp_config.json`, `~/.gemini/config/mcp_config.json`, `AGENTS.md`, `.agents/skills/`), **Cursor** (`.cursor/mcp.json`, `.cursor/rules/reposcope.mdc`, `cursor://` deep link), **AWS Kiro** (`.kiro/settings/mcp.json`, `.kiro/steering/reposcope.md`), **Windsurf** (`.windsurf/mcp_config.json`, `.windsurfrules`), **GitHub Copilot / VS Code** (`.vscode/mcp.json`, `.github/mcp.json`), **OpenAI Codex CLI** (`.codex/config.toml`), **Cline / Roo Code** (`.roo/mcp.json`, `.clinerules`), and **Zed** (`.zed/settings.json`).

---

### PHASE 7: TOKEN-COMPACT MCP SERVER (`TOON` + SKELETON MODE) & 5 RESEARCH-BACKED SKILLS
1. Create `backend/context_compressor.py` implementing **TOON (Token-Oriented Object Notation, 85% token reduction)**, **AST Signature Skeletons**, and **SHA-256 Delta Caching (`since_hash`)**.
2. Replace `backend/mcp_client.py` with `backend/mcp_server.py` (`stdio` + `streamable_http` at `/mcp`) exposing 8 tools: `get_mindmap_hierarchy`, `get_symbol_blast_radius`, `get_ast_skeleton`, `get_dependency_lineage`, `diff_interface_contracts`, `get_ranked_reading_path`, `compile_reverse_prompt`, and `run_security_scan`.
3. Create 5 `SKILL.md` playbooks in `.agents/skills/` and `.claude/skills/`: `blast-radius-guard`, `zero-grep-architect`, `pr-contract-shield`, `onboarding-navigator`, and `dead-code-surgeon`.

---

### PHASE 8: ZERO-CLONE PACKAGES (`npx reposcope-mcp`, `pip install reposcope-ai`, VS CODE `.vsix`) & MULTI-PROVIDER BYOK
1. Build standalone npm package `packages/reposcope-mcp/` (`v2.0.0`) supporting `npx reposcope-mcp init`, `npx reposcope-mcp serve`, `npx reposcope-mcp scaffold`, and `npx reposcope-mcp inspect .` without cloning RepoScope.
2. Update root `pyproject.toml` (`reposcope-ai` v2.0.0) and `backend/cli.py`.
3. Upgrade `extensions/vscode/` (`reposcope-vscode` v2.0.0) with standalone workspace scanning, Vertical Mind-Map Sidebar, Status Bar Blast-Radius badge, CodeLens caller badges, and 1-Click Agent Harness setup.
4. Upgrade `backend/ai_byok.py` & `backend/key_rotator.py` with HTTP 429 `Retry-After` cooldowns and support for **Nebius Token Factory + NVIDIA Nemotron** (`Nemotron 3 Ultra` / `Super`), Groq, OpenRouter, Gemini, Anthropic, OpenAI, and Ollama, plus 3 pre-cached instant demo repos (`adityapatel5912/RepoScope`, `Verdict`, `StudyRot`).

---

### PHASE 9: END-TO-END VERIFICATION & GREEN CI GATE
Run and verify exit code 0 on all checks:
1. `python3 -m compileall -q backend/`
2. `pytest -q backend/tests/ --maxfail=1 --disable-warnings`
3. `npm --prefix frontend run build`
4. `npm --prefix packages/reposcope-mcp run build`
5. `npm --prefix extensions/vscode run compile`
```

* 

# **RepoScope V2.7 Complete Feature Suite Upgrade: Code Tours, PR Bot, Student Mode, Repo Tracking & Deep Analysis**

This addendum upgrades every remaining feature in RepoScope ([RepoScope Pitch Deck v3.0](https://drive.google.com/file/d/1WYhSbkMT8UA8srCG5U27n4bXKShMPmYm/view?usp=drivesdk), [RepoScope Weaknesses and Roadmap](https://docs.google.com/document/d/1mTjCseWSQkRBcTQOr7RCCJ36AOWdC36gFlQAvuFCiwQ/edit?usp=drivesdk&ouid=115448831606209536315)) into a cohesive, production-grade developer intelligence suite.

## **1\. Code Tours & Voice Walkthroughs 2.0 (`backend/tour_generator.py` & `frontend/src/components/TourPanel.tsx`)**

### **Current v3.0 Limitations**

* Static linear stop list that only pans across top-level files without tracing actual runtime request-to-database execution flows.  
* One-way browser `speechSynthesis` narration: if a user has a question at Stop 3, they cannot interrupt the tour or see the exact highlighted code lines inside the canvas.

### **V2.7 Technical Upgrades**

* **Execution-Flow & Scenario-Driven Tour Tracks (`backend/tour_generator.py`):**  
  * Instead of a single generic tour, automatically generate **4 selectable Tour Tracks** from the AST call graph:  
    * **Track 1: Architecture & Entry-Point Overview** (Tier 0 Root \-\> Tier 1 Pillars \-\> Core Controllers).  
    * **Track 2: End-to-End Request Lifecycle** (Follows a real user action from `Frontend Component -> fetch('/api/...') -> FastAPI Route -> Service Orchestrator -> Database / External API`).  
    * **Track 3: High-Risk Hotspots & Security Critical Path** (Walks through the top 5 PageRank / high-blast-radius modules and auth boundaries).  
    * **Track 4: Custom Prompt-Generated Tour** (User types *"Show me how authentication and key rotation work"* and RepoScope synthesizes a custom 5-stop AST path on the fly).  
* **Synchronized Split-View Code Spotlight & Auto-Unfolding Mind Map (`TourPanel.tsx`):**  
  * At each Tour Stop, the **Vertical NotebookLM Mind Map** automatically unfolds the parent pillar (`Backend`, `Frontend`, etc.), centers the active file card, draws an animated glowing pulse along the incoming edge from the previous stop, and opens a synchronized **Code Spotlight Drawer** highlighting the exact AST function lines (`L42-L89`).  
* **Interactive "Ask Mid-Tour" Interrupt & Resume \+ IDE Sync:**  
  * Users can click **"Pause & Ask Here"** (by text or microphone) at any stop. The AI answers using the current stop's AST context, highlights any referenced helper functions, and then clicks **"Resume Tour"** from the exact same stop.  
  * Includes a **"Follow Along in VS Code"** toggle that automatically fires `vscode://file/{root}/{path}:{line}` on each stop change so the developer's local editor scrolls in sync with the voice narration.  
  * **Export Tour as CodeTour (`.tours/*.tour`):** 1-click export to the standard VS Code CodeTour JSON format so teams can commit guided walkthroughs directly into their repository.

## **2\. PR Impact Bot 2.0 (`backend/pr_impact.py`, `frontend/src/components/PRImpactPanel.tsx` & `.github/workflows/pr-impact.yml`)**

### **Current v3.0 Limitations**

* Hard `MAX_FILES_ANALYZED = 25` cap with sequential REST calls, file-level-only blast radius (flagging an entire file even if an untouched helper was imported), static image/comment output, and no automated unit test generation or architectural drift enforcement.

### **V2.7 Technical Upgrades**

* **Symbol-Level Breaking Contract Diffing (Removing the 25-File Cap):**  
  * Fetch the unified PR diff in a single async HTTP request and parse modified hunks with Tree-sitter / AST to identify **exact modified symbols** (altered function signatures, removed parameters, changed return types, modified Pydantic/TypeScript interfaces).  
  * Trace `calls` and `api_calls` edges from those exact modified symbols to flag **Broken Downstream Callers** (including frontend React components calling a modified backend FastAPI route).  
* **Architectural Drift & Layer Violation Detector:**  
  * Automatically detect and flag **Architectural Rule Violations** introduced by the PR:  
    * **Layer Bypass:** e.g., a `frontend` or `routes` module importing a low-level `db` model directly instead of going through `services`.  
    * **New Circular Dependencies:** Detects any newly introduced import cycle (`A -> B -> A`).  
    * **New Uncovered High-Risk Symbols:** Flags modified functions with `blast_radius >= 5` that lack corresponding test calls in `tests/`.  
* **Automated Unit Test Stub Synthesis & Ready-to-Commit Patch:**  
  * For every high-risk modified function lacking test coverage, automatically synthesize a runnable `pytest` or `vitest`/`jest` unit test block and include it inside a collapsible `<details><summary>🧪 Ready-to-Commit Unit Test Stubs</summary>...</details>` block in the GitHub PR comment and in `PRImpactPanel.tsx`.  
* **Interactive Mermaid Subgraph \+ CI Merge Gate Policy:**  
  * Embed a clean, self-contained **Mermaid Blast-Radius Diagram** directly inside the GitHub PR markdown comment (colour-coding changed nodes in amber, broken callers in crimson, and impacted tests in blue) alongside a 1-click **"Inspect Live in RepoScope Mind Map"** deep link.  
  * Support `reposcope ci-gate --max-risk 75 --block-on-breaking-contract` for GitHub Actions status checks.

## **3\. Student Onboarding Mode 2.0 (`backend/onboarding.py` & `frontend/src/components/StudentModePanel.tsx`)**

### **Current v3.0 Limitations**

* Ranks files by `rank = incoming * 2 + outgoing` into Rows 0–5 with 3 multiple-choice quizzes per level, but quizzes are generic, Good First Issues aren't paired with concrete starter code patches, and progress isn't tied to real code navigation challenges.

### **V2.7 Technical Upgrades**

* **Topological Curriculum Graph (Row 0 Foundations \-\> Row 5 Good First Issues):**  
  * Improve the curriculum ranking algorithm by combining **Dependency Depth**, **Cyclomatic Complexity**, and **PageRank Centrality**:  
    * **Level 1 (Row 0–1 — Leaf Utilities & Configs):** Low blast radius, zero downstream dependents—safest files for a student's first edit.  
    * **Level 2 (Row 2–3 — Domain Services & UI Components):** Moderate connectivity; teaches how data flows between layers.  
    * **Level 3 (Row 4–5 — Core Orchestrators & Entry Points):** High centrality hubs unlocked after mastering Levels 1–2.  
* **3-Mode Interactive Challenges (Beyond Multiple Choice):**  
  * Upgrade each level's verification from basic multiple-choice into **3 Interactive Challenge Types**:  
    * **Code Scavenger Hunt ("Find the Line"):** *"Which function in key\_rotator.py quarantines a rate-limited API key? Click the node on the Mind Map or select the exact line range."*  
    * **Blast-Radius Prediction Quiz:** *"If you rename build\_graph\_from\_repo(), which of these 4 files will break immediately?"* (Verified deterministically from the AST graph—works 100% offline with zero LLM latency).  
    * **Micro-Refactor Sandbox Challenge:** Student spots a bug or missing docstring in a real snippet from the repo and validates their fix.  
* **"First PR Coach" & Live GitHub Issue Matcher:**  
  * Match open GitHub issues (especially `good first issue` / `help wanted` labels, or auto-detected TODO/FIXME/missing-test hotspots in Row 0–2 files) to exact nodes on the Vertical Mind Map.  
  * Clicking **"Start My First PR"** on any matched issue generates a step-by-step **First Contribution Cheat Sheet**: which 2 files to edit, which local test command to run (`pytest backend/tests/...`), what not to break, and a 1-click button to open those exact files in VS Code (`vscode://`).  
  * **Exportable Onboarding Certificate / Badge:** Upon completing all 3 levels, generates a shareable **RepoScope Codebase Mastery Badge (SVG/Markdown)** summarizing the student's verified architectural understanding of that repository.

## **4\. Live Repo Tracking & Evolution Timeline 2.0 (`backend/repo_tracker.py` & `frontend/src/components/TrackerPanel.tsx`)**

### **Current v3.0 Limitations**

* Displays a flat feed of recent GitHub commits, PRs, issues, and releases without linking them visually to the knowledge graph or calculating how the codebase's health is trending over time.

### **V2.7 Technical Upgrades**

* **Interactive Commit & PR Time-Machine on the Mind Map:**  
  * Clicking any commit, merged PR, or release in `TrackerPanel.tsx` **lights up the exact touched files and their blast-radius ripple** directly on the **Vertical NotebookLM Mind Map**.  
  * Adds a **"Compare Commits / Branches (base...head)"** selector that overlays added nodes in emerald green, modified nodes in amber, and deleted nodes in dashed red.  
* **Git Churn, Hotspot & Bus-Factor Analytics (`backend/repo_tracker.py`):**  
  * Compute 3 high-value engineering metrics per file and pillar:  
    * **Churn Velocity:** Commit frequency and lines changed over the last 30/90 days.  
    * **Hotspot Danger Score (Churn \* Complexity \* Blast\_Radius):** Automatically surfaces fragile files that change constantly AND have high downstream impact.  
    * **Knowledge Ownership / Bus Factor:** Identifies "Single-Owner Silos" (critical high-PageRank modules touched by only 1 contributor) so teams know where documentation or code tours are urgently needed.  
* **Release & Changelog Impact Summarizer:**  
  * One-click **"Generate Architectural Release Notes"** that groups commits between two tags/branches by Mind-Map Pillar (`Backend`, `Frontend`, `AI/MCP`, `Deployment`, `Tests`) and flags any breaking API or schema changes.

## **5\. Deep Impact & Security Analysis 2.0 (`backend/impact_analyzer.py`, `backend/security_scanner.py` & Frontend Panels)**

### **Current v3.0 Limitations**

* `impact_analyzer.py` only traces file-level imports without distinguishing direct function callers from unused file imports or cross-stack API calls.  
* `security_scanner.py` runs basic regex detectors without tracing whether a vulnerability sits on an exposed public route or checking AI/MCP-specific security risks.

### **V2.7 Technical Upgrades**

* **Multi-Hop Blast Radius Simulator with "What-If" Ripple Animation (`impact_analyzer.py` & `ImpactAnalysisPanel.tsx`):**  
  * **3-Layer Ripple Breakdown:**  
    * **Hop 1 (Direct Symbol Callers — Critical):** Functions and classes that directly invoke the modified symbol.  
    * **Hop 2 (Transitive Module Dependents & Cross-Stack UI Callers — High/Moderate):** Downstream modules and React components consuming the affected API route.  
    * **Hop 3 (Impacted Test Suites & CI Workflows — Verification Layer):** Exact test files (`test_*.py`, `*.test.ts`) that cover the affected subgraph, plus a **Test Coverage Gap Warning** if `impacted_tests == 0`.  
  * **"Simulate Change" Interactive Mode:** Users can toggle *"What if I change the return type / delete this symbol / change this route path?"* and watch the animated ripple propagate down the Vertical Mind Map with a composite **Risk Score (0–100)** explained by formula (`Direct_Callers*8 + Transitive_Callers*3 + Cross_Stack_UI*5 + Uncovered_Penalty*15`).  
* **Graph-Aware Security & AI/MCP Vulnerability Scanner (`backend/security_scanner.py`):**  
  * Expand regex detectors into a **5-Category Graph-Contextual Security Engine**:  
    * **1\. Hardcoded Secrets & High-Entropy Tokens:** AWS, GitHub PAT, OpenAI, Groq, Anthropic, Nebius, Private Keys, JWT secrets.  
    * **2\. Code & Injection Sinks (OWASP Top 10):** SQL string interpolation, `subprocess(..., shell=True)`, `eval()`/`exec()`, `dangerouslySetInnerHTML`, unvalidated `pickle`/`yaml.load`, and SSRF/path-traversal sinks.  
    * **3\. AI & MCP Security Audit (Novel Differentiator):** Scans for **Prompt Injection sinks**, unauthenticated MCP HTTP endpoints, overly permissive agent tool execution (`--yolo` / unsandboxed shell tools), and leaked API keys in `.mcp.json` or agent config files.  
    * **4\. Dependency & Lockfile Risk Audit:** Checks `requirements.txt`, `pyproject.toml`, and `package.json` for unpinned wildcards, deprecated packages, and known risky version ranges.  
    * **5\. Reachability / Exposure Multiplier:** Cross-references every security finding with the AST Graph—a vulnerability inside an exposed `API Controller` (Row 0/1) with 10 callers gets upgraded to **CRITICAL (Exploitable via Public Route)**, and generates a 1-click **"Copy Safe Remediation Patch"** snippet.

## **6\. THE ULTIMATE 10-PHASE MASTER ONE-SHOT AGENT PROMPT (Copy-Paste This Single Block to Build Everything)**

Copy and paste the complete block below into **Claude Code**, **Antigravity**, **Cursor**, or **Kiro**. It includes **every single upgrade** across the entire conversation in one cohesive, self-verifying execution plan:

```
ROLE & OBJECTIVE:
You are a Principal Full-Stack Systems, Compiler/AST, AI Protocol, Security, and UX Architect. Execute a complete, end-to-end upgrade of this repository into RepoScope V2.7: The Universal Architectural Mind-Map Explorer, Verified Citation Engine, Full-Lifecycle Developer Intelligence Suite, and 9-Agent MCP Safety Harness.

Do NOT stop after planning. Execute all 10 phases sequentially, run the verification commands at the end, fix any test or build failures immediately, and do not conclude until all L1/L2/L3 tests, frontend builds, and standalone packages pass with zero errors.

---

### PHASE 1: FIX ALL 9 FAILING L1 UNIT TESTS & UNBLOCK L2/L3 CI
1. Run `pytest -q` and inspect all failing assertions in `backend/tests/`.
2. Add deterministic mocked fixtures for external LLM and GitHub API calls (`ask_llm`, `key_rotator`, `repo_loader`) so `L1 · unit tests` pass 100% offline in CI runners without requiring external API keys.
3. Align all Pydantic v2 response schemas across `/api/load-repo`, `/api/chat`, `/api/impact`, `/api/impact/pr`, `/api/security`, `/api/onboarding`, `/api/tours`, `/api/tracker`, `/api/reverse-prompt`, and `/api/scaffold` so `L2 · API contract` tests pass.
4. Create a deterministic static fixture graph at `backend/tests/fixtures/demo_repo_graph.json` so `L3 · browser journeys` pass reliably.

---

### PHASE 2: SPOT-ON GRAPH ACCURACY & CROSS-STACK SYMBOL RESOLUTION (`backend/symbol_resolver.py` & `backend/graph_builder.py`)
1. Create `backend/symbol_resolver.py` and integrate it into `backend/graph_builder.py`:
   - **TypeScript / JavaScript Alias & Barrel Unwrapping:** Parse `tsconfig.json` / `jsconfig.json` (`baseUrl` and `paths` aliases like `@/*`) and unwrap barrel re-exports (`index.ts`, `export * from`, `export { X } from`) so imports connect directly to the true target file and symbol.
   - **Python Relative Import & Decorator Resolver:** Resolve relative imports (`from ..module import X`) and FastAPI route/dependency decorators (`@router.get`, `@app.post`, `Depends(...)`).
   - **Cross-Stack Frontend-to-Backend API Linker (`api_calls` edges):** Scan frontend `fetch()`, `axios`, and `EventSource` calls targeting `/api/...` routes and wire explicit `api_calls` edges connecting the frontend component node directly to the backend route handler node.
   - **PageRank Centrality & Architectural Role Tagging:** Compute PageRank importance scores and tag every node with its semantic role (`Entry Point`, `API Controller`, `Core Engine`, `State/Store`, `Data Model`, `External Adapter`, `Utility`, `Test Suite`).

---

### PHASE 3: VERTICAL GEMINI NOTEBOOKLM MIND-MAP GRAPH & UI/UX OVERHAUL (`backend/mindmap_classifier.py` & `KnowledgeGraphView.tsx`)
1. Create `backend/mindmap_classifier.py` to classify every repository file into 6 top-level domain pillars: `backend` (Backend & Core), `frontend` (Frontend & UI), `ai_mcp` (AI, Agents & MCP), `assets` (Assets, Docs & Config), `deployment` (Deployment & CI/CD), and `tests` (Tests & QA). Attach `github_url` and `vscode_uri` to every file and symbol node.
2. Overhaul `frontend/src/components/KnowledgeGraphView.tsx`:
   - Default to a **Vertical Top-Down (`rankdir: 'TB'`) NotebookLM-Style Collapsible Mind Map** with smooth bezier connectors.
   - **Initial Progressive State:** Render only Tier 0 (Repository Root Pill with tech stack + health score) and Tier 1 (the 6 Domain Classification Pillars) so initial render is <50ms and clutter-free.
   - **Expand / Collapse Chevron Buttons:** Clicking the arrow on a Tier 1 Pillar smoothly expands its Tier 2 folders and Tier 3 File Cards downward; clicking a file's function badge expands Tier 4 (functions/classes).
   - **Direct Action Bar on Every File Card:** Render 3 buttons on every file node: (1) `[GitHub ↗]` (`https://github.com/{owner}/{repo}/blob/{branch}/{path}`), (2) `[VS Code ⚡]` (`vscode://file/{localRoot}/{path}:{line}:1` or `cursor://file/...`), and (3) `[Blast Radius 🎯]`.
   - Add a Mind-Map Toolbar: `Expand All`, `Collapse to Pillars`, `Vertical TB / Horizontal LR`, `Mind Map / Dependency Network`, `Hotspot Heatmap Overlay`, and live search auto-expand.

---

### PHASE 4: VERIFIED CHAT CITATIONS 2.0 (`backend/citation_verifier.py` & `ChatPanel.tsx`)
1. Create `backend/citation_verifier.py` and integrate into `backend/orchestrator.py`:
   - Prepend exact 1-indexed AST line numbers and symbol headers (`[path:Lstart-Lend | def symbol]`) to all retrieved code chunks before calling the LLM, using 2-hop PageRank AST GraphRAG instead of raw 4,000-character truncation.
   - Parse every citation in the LLM response, verify and snap line numbers against the indexed AST symbol table, and return structured citation metadata (`file_path`, `start_line`, `end_line`, `symbol_name`, `code_preview`, `verified: true`, `github_url`, `vscode_uri`, `node_id`).
2. Upgrade `frontend/src/components/ChatPanel.tsx`:
   - Render interactive **Verified Citation Pills** (`[📄 file.py:L42-89 · func_name ✓]`) with a syntax-highlighted **Hover Code Preview Popover**.
   - **1-Click Mind-Map Sync:** Clicking a citation pill automatically unfolds the parent pillar on the Vertical Mind Map, pans the camera to that file card, and provides 1-click buttons to open the exact line in VS Code (`vscode://`) or GitHub (`#L42-L89`).

---

### PHASE 5: CODE TOURS 2.0, STUDENT MODE 2.0 & LIVE REPO TRACKING 2.0
1. **Code Tours 2.0 (`backend/tour_generator.py` & `TourPanel.tsx`):**
   - Generate 4 selectable Tour Tracks from the AST graph: (1) `Architecture & Pillars Overview`, (2) `End-to-End Request Lifecycle (Frontend -> API -> Service -> DB)`, (3) `High-Risk Hotspots & Auth Path`, and (4) `Custom Prompt-Generated Tour`.
   - Sync each Tour Stop with the Vertical Mind Map (auto-unfolding the branch and highlighting the incoming edge), display a **Code Spotlight Drawer** with exact AST lines, support **"Pause & Ask Mid-Tour"** Q&A, add a **"Follow Along in VS Code (`vscode://`)"** toggle, and support exporting `.tours/reposcope.tour` JSON.
2. **Student Onboarding Mode 2.0 (`backend/onboarding.py` & `StudentModePanel.tsx`):**
   - Rank files into a 3-Level Topological Curriculum (Row 0–1 Leaf Utilities -> Row 2–3 Domain Services -> Row 4–5 Core Hubs) using Dependency Depth + Cyclomatic Complexity + PageRank.
   - Include 3 interactive challenge types (Code Scavenger Hunt, Deterministic Blast-Radius Prediction Quiz, and Micro-Refactor Check), a **"First PR Coach"** that pairs Good First Issues / TODOs with exact files + test commands + `vscode://` links, and an exportable **Codebase Mastery Badge (SVG/Markdown)**.
3. **Live Repo Tracking 2.0 (`backend/repo_tracker.py` & `TrackerPanel.tsx`):**
   - Compute per-file **Git Churn Velocity**, **Hotspot Danger Score (`Churn * Complexity * Blast_Radius`)**, and **Bus-Factor / Single-Owner Silo** warnings.
   - Clicking any commit or PR in `TrackerPanel.tsx` highlights the modified files and their blast-radius ripple directly on the Vertical Mind Map. Add a 1-click **"Generate Architectural Release Notes"** summary grouped by Mind-Map Pillar.

---

### PHASE 6: PR IMPACT BOT 2.0, DEEP IMPACT SIMULATOR & GRAPH-AWARE SECURITY 2.0
1. **PR Impact Bot 2.0 (`backend/pr_impact.py` & `PRImpactPanel.tsx`):**
   - Remove the 25-file cap and add **Symbol-Level Breaking Contract Diffing** (detecting altered function signatures, removed exports, and broken cross-stack `api_calls` callers).
   - Detect **Architectural Drift** (layer bypasses like `ui -> db` and new circular dependencies).
   - Automatically synthesize **Ready-to-Commit Unit Test Stubs (`pytest` / `vitest`)** for uncovered high-risk modified functions and embed an inline **Mermaid Blast-Radius Diagram** in PR comments.
2. **Multi-Hop Impact Simulator (`backend/impact_analyzer.py` & `ImpactAnalysisPanel.tsx`):**
   - Separate impact into **Hop 1 (Direct Symbol Callers)**, **Hop 2 (Transitive & Cross-Stack UI Dependents)**, and **Hop 3 (Impacted Test Suites + Test Coverage Gap Warning)** with an explainable 0–100 Risk Score formula and animated Mind-Map ripple.
3. **Graph-Aware Security Scanner 2.0 (`backend/security_scanner.py` & `SecurityPanel.tsx`):**
   - Scan across 5 categories: (1) Hardcoded Secrets/Tokens, (2) OWASP Injection/SSRF/Eval Sinks, (3) **AI & MCP Security Risks** (prompt injection sinks, unauthenticated MCP endpoints, leaked keys in `.mcp.json`), (4) Dependency Lockfile Risks, and (5) **Graph Reachability Multiplier** (boosting severity when a sink sits on a public API route), complete with 1-click **Safe Remediation Patch** snippets.

---

### PHASE 7: REVERSE PROMPT 2.0 & EXECUTABLE SCAFFOLDING 2.0 (`backend/reverse_prompt.py` & `backend/scaffolder.py`)
1. Upgrade `backend/reverse_prompt.py` and `ReversePromptPanel.tsx` into a **4-Mode Agent Blueprint Compiler**:
   - Mode 1: `Full System Rebuild Spec` (Row 0 -> Row 5 dependency build order + API contracts).
   - Mode 2: `Feature Subgraph Slice` (select any Mind-Map node/pillar to export a self-contained prompt + 2-hop interface closure to clone just that feature).
   - Mode 3: `Agent Spec Bundle` (`CLAUDE.md`, `AGENTS.md`, `llms.txt`, and `.kiro/specs/`).
   - Mode 4: `Token-Budgeted Context Pack` (`Compact TOON 2k` | `Standard 8k` | `Full 32k`).
2. Upgrade `backend/scaffolder.py` and `ScaffoldPanel.tsx` into an **Executable Multi-File Starter Kit Generator**:
   - Synthesize a runnable 12–20 file starter project (`Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`, backend routes, models, frontend shell, tests, and pre-configured `.claude/mcp.json` + `.agents/skills/`), with an in-app **Multi-File Code Previewer**, **`POST /api/scaffold/download-zip`**, and CLI command `npx reposcope-mcp scaffold`.

---

### PHASE 8: UNIVERSAL 9-AGENT ONE-CLICK HARNESS, TOON MCP SERVER & 5 SKILLS
1. Create `backend/harness_generator.py` (`GET /api/harness/config`) and `frontend/src/components/HarnessModal.tsx` supporting 1-click setup for all 9 coding agents: **Claude Code**, **Google Antigravity**, **Cursor**, **AWS Kiro**, **Windsurf**, **GitHub Copilot / VS Code**, **OpenAI Codex CLI**, **Cline / Roo Code**, and **Zed**.
2. Create `backend/context_compressor.py` implementing **TOON (Token-Oriented Object Notation, 85% token reduction)**, **AST Signature Skeletons (`detail_level="skeleton"`)**, and **SHA-256 Delta Caching (`since_hash`)**.
3. Replace `backend/mcp_client.py` with `backend/mcp_server.py` (`stdio` + `streamable_http` at `/mcp`) exposing 8 tools (`get_mindmap_hierarchy`, `get_symbol_blast_radius`, `get_ast_skeleton`, `get_dependency_lineage`, `diff_interface_contracts`, `get_ranked_reading_path`, `compile_reverse_prompt`, `run_security_scan`).
4. Create 5 production `SKILL.md` playbooks in `.agents/skills/` and `.claude/skills/`: `blast-radius-guard`, `zero-grep-architect`, `pr-contract-shield`, `onboarding-navigator`, and `dead-code-surgeon`.

---

### PHASE 9: ZERO-CLONE PACKAGES (`npx reposcope-mcp`, `pip install reposcope-ai`, VS CODE `.vsix`) & MULTI-PROVIDER BYOK
1. Build standalone npm package `packages/reposcope-mcp/` (`v2.0.0`) supporting `npx reposcope-mcp init`, `npx reposcope-mcp serve`, `npx reposcope-mcp scaffold`, and `npx reposcope-mcp inspect .` without cloning RepoScope.
2. Update root `pyproject.toml` (`reposcope-ai` v2.0.0) and `backend/cli.py`.
3. Upgrade `extensions/vscode/` (`reposcope-vscode` v2.0.0) with standalone workspace scanning, Vertical Mind-Map Sidebar, Status Bar Blast-Radius badge, CodeLens caller badges, and 1-Click Agent Harness setup.
4. Upgrade `backend/ai_byok.py` & `backend/key_rotator.py` with HTTP 429 `Retry-After` cooldowns and support for **Nebius Token Factory + NVIDIA Nemotron** (`Nemotron 3 Ultra` / `Super`), Groq, OpenRouter, Gemini, Anthropic, OpenAI, and Ollama, plus 3 pre-cached instant demo repos (`adityapatel5912/RepoScope`, `Verdict`, `StudyRot`).

---

### PHASE 10: END-TO-END VERIFICATION & GREEN CI GATE
Run and verify exit code 0 on all checks:
1. `python3 -m compileall -q backend/`
2. `pytest -q backend/tests/ --maxfail=1 --disable-warnings`
3. `npm --prefix frontend run build`
4. `npm --prefix packages/reposcope-mcp run build`
5. `npm --prefix extensions/vscode run compile`
```

* 

# **RepoScope V2.8 Deep Security & Vulnerability Intelligence Suite (`backend/security_scanner.py` & `SecurityPanel.tsx`)**

### **Current v3.0 Security Limitations**

In RepoScope v3.0 ([RepoScope Pitch Deck v3.0](https://drive.google.com/file/d/1WYhSbkMT8UA8srCG5U27n4bXKShMPmYm/view?usp=drivesdk)), `routes/security.py` / `backend/security_scanner.py` only runs 3 basic regular-expression detectors on individual files. This produces high false-positive noise on test/mock files, misses real multi-file attack chains, does not query live CVE databases, and does not generate ready-to-apply code patches or industry-standard security reports.

## **1\. Six-Engine Graph-Contextual Security Architecture**

Upgrade `backend/security_scanner.py` and `frontend/src/components/SecurityPanel.tsx` into a **6-Engine Graph-Contextual Security Suite**:

### **Engine 1: Cross-File AST Source-to-Sink Taint Analysis (`backend/taint_analyzer.py`)**

Instead of flagging isolated keywords, trace **Taint Propagation Paths (Source \-\> Sanitizer? \-\> Sink)** across the RepoScope call graph ([Multi-Agent Taint Specification Extraction](https://arxiv.org/html/2601.10865v1), [Cross-Boundary Source-to-Sink](https://www.ostering.com/src2sink/)):

* **Untrusted Sources (`TAINT_SOURCES`):** FastAPI `Request`, `Query`, `Body`, `Header`, `UploadFile`, Flask `request.args`/`request.json`, Express `req.body`/`req.query`/`req.params`, CLI `sys.argv`, and unvalidated external webhook payloads.  
* **Dangerous Sinks (`TAINT_SINKS`):**  
  * **Command / Code Execution (`CWE-78` / `CWE-94`):** `subprocess.run(..., shell=True)`, `os.system()`, `eval()`, `exec()`, `child_process.exec()`.  
  * **SQL & NoSQL Injection (`CWE-89`):** Raw f-string or `%`\-formatted SQL passed into `cursor.execute(f"SELECT ... {user_input}")` or `session.execute(text(f"..."))`.  
  * **SSRF & Arbitrary File Read/Write (`CWE-918` / `CWE-22`):** Unvalidated user URLs passed into `httpx.get(url)` / `requests.get(url)` or user paths passed into `open(user_path)` / `send_file()` without `.resolve()` prefix confinement.  
  * **Unsafe Deserialization & XSS (`CWE-502` / `CWE-79`):** `pickle.loads()`, `yaml.load()` (without `SafeLoader`), and React `dangerouslySetInnerHTML`.  
* **Visual Attack-Chain Highlighting on the Vertical Mind Map:** When a user clicks any taint finding in `SecurityPanel.tsx`, the **Vertical NotebookLM Mind Map** automatically unfolds and draws a pulsing **Crimson Attack Path (Frontend Form \-\> API Route \-\> Service \-\> Vulnerable Sink)** across the exact files involved.

### **Engine 2: Live Dependency CVE & Supply-Chain Scanner via OSV.dev Batch API**

* Parse `requirements.txt`, `pyproject.toml`, `poetry.lock`, `package.json`, `package-lock.json`, `go.mod`, and `Cargo.lock` to extract `(package_name, version, ecosystem)` tuples.  
* Send a single sub-second batch `POST` request to the free, zero-auth **OpenSSF OSV API** (`https://api.osv.dev/v1/querybatch`) ([OpenSSF OSV API Guide](https://openssf.org/blog/2026/05/20/detecting-malicious-packages-using-the-osv-api/), [osv-scan](https://github.com/SpiderCob/osv-scan)) with an offline built-in advisory fallback for air-gapped CI runs.  
* **Reachable CVE Prioritization (Killer Feature):** Cross-reference vulnerable packages against RepoScope's `imports` and `calls` AST graph. Distinguish between a **Dormant Dependency CVE** (installed in `package.json` but never imported) and a **Reachable Exploitable CVE** (actively imported and called by an exposed `API Controller` node), and output the exact safe upgrade command (`pip install "fastapi>=0.115.0"` or `npm install axios@latest`).

### **Engine 3: Shannon-Entropy Secret Scanner & Context-Aware False-Positive Filter**

* Combine 25+ provider signature patterns (AWS `AKIA...`, GitHub `ghp_`/`github_pat_`, OpenAI `sk-proj-`, Groq `gsk_`, Anthropic `sk-ant-`, Nebius, Slack, Stripe, Private RSA/PEM keys, Postgres/Mongo connection URIs) with **Shannon Entropy calculation** (`H > 4.2` on string literals) to catch custom high-entropy secrets.  
* **Smart Test/Mock De-Noising:** Automatically downgrade findings inside `tests/`, `fixtures/`, `.env.example`, or strings containing `mock`, `dummy`, `example`, or `placeholder` from `CRITICAL` to `INFO (Test Fixture)` so real production leaks stand out with zero noise.

### **Engine 4: AI Agent, LLM & MCP Security Auditor (`CWE-LLM01` to `LLM10`)**

A signature differentiator tailored for 2026 AI engineering repositories:

* **Prompt Injection & Unbounded Context Sinks:** Detects raw user input concatenated directly into system prompts without delimiter tagging or structured message roles.  
* **MCP Server & Agent Harness Audit:** Scans `.claude/mcp.json`, `mcp_config.json`, `.cursor/mcp.json`, `.kiro/settings/mcp.json`, and `backend/mcp_server.py` for:  
  * Hardcoded plaintext API tokens committed inside MCP config files (instead of `${ENV_VAR}` interpolation).  
  * Unauthenticated remote MCP HTTP endpoints missing `Authorization` / Bearer token middleware.  
  * Destructive MCP tools missing `readOnlyHint: false` / human-in-the-loop confirmation guards or unsafe `--yolo` / `--disable-sandbox` flags in CI scripts.

### **Engine 5: Infrastructure, CORS & Auth-Boundary Misconfiguration Audit**

* **Exposed API Routes Missing Auth Dependency:** Uses the FastAPI / Express AST decorator table to flag state-mutating routes (`@app.post`, `@app.delete`, `@app.put`) that lack authentication dependencies (`Depends(get_current_user)` or auth middleware).  
* **CORS, Docker & CI Hardening:** Flags `allow_origins=["*"]` combined with `allow_credentials=True`, Dockerfiles running as `root` (missing non-root `USER`), and GitHub Actions workflows vulnerable to `pull_request_target` script injection.

### **Engine 6: 1-Click Unified Diff Auto-Patcher, OWASP/CWE Scorecard & SARIF 2.1.0 Export**

* **Ready-to-Apply Unified Code Patch (`patch_diff`):** Every security finding includes a concrete **Before vs. After Code Diff** (e.g., rewriting `subprocess.run(cmd, shell=True)` into `subprocess.run(shlex.split(cmd), shell=False, check=True)` or replacing a hardcoded key with `os.environ["API_KEY"]`) plus a **\[Copy Fix Patch\]** and **\[Open Vulnerable Line in VS Code ⚡\]** button.  
* **Security Posture Scorecard (A+ to F Grade):** Computes an overall Security Grade (`A+` to `F`) broken down across **Secrets**, **Code Sinks (OWASP)**, **Supply-Chain CVEs**, **AI/MCP Safety**, and **Auth & Infra**.  
* **1-Click SARIF 2.1.0 Export (`GET /api/security/sarif`):** Exports findings in the official **SARIF 2.1.0 JSON schema** ([GitHub SARIF Code Scanning](https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support)) so developers can upload RepoScope security scans directly into GitHub's native **Security \-\> Code Scanning** tab (`github/codeql-action/upload-sarif`).

---

## **2\. APPEND THIS BLOCK INTO PHASE 6 OF YOUR MASTER ONE-SHOT AGENT PROMPT**

When running the Master One-Shot Agent Prompt in **Claude Code**, **Antigravity**, **Cursor**, or **Kiro**, include this exact Phase 6 block (already integrated below for one-copy execution):

```
### PHASE 6 (EXPANDED): DEEP AST SECURITY SUITE 2.8 (`backend/security_scanner.py`, `backend/taint_analyzer.py` & `SecurityPanel.tsx`)
1. Create `backend/taint_analyzer.py` and upgrade `backend/security_scanner.py` into a 6-Engine Graph-Contextual Security Scanner:
   - **Engine 1 (AST Source-to-Sink Taint Analysis):** Trace untrusted inputs (`Request`, `Query`, `Body`, `req.body`, `req.query`) across call edges to dangerous sinks (`subprocess(..., shell=True)`, `eval`/`exec`, raw SQL string formatting, SSRF `httpx`/`requests` calls, path traversal `open()`, `pickle.loads`, `dangerouslySetInnerHTML`). Emit the ordered `attack_path_node_ids` (`[source_node, ..., sink_node]`) so clicking a finding highlights the full red attack chain on the Vertical Mind Map.
   - **Engine 2 (Live OSV.dev Batch CVE + Reachability Scanner):** Parse `requirements.txt`, `pyproject.toml`, and `package.json`; query `https://api.osv.dev/v1/querybatch` (with a deterministic offline advisory fallback for tests/CI); cross-reference vulnerable packages against the AST `imports`/`calls` graph to badge each CVE as `REACHABLE_EXPLOITABLE` vs. `DORMANT_DEPENDENCY`, and provide the exact upgrade command.
   - **Engine 3 (Entropy + Pattern Secret Scanner with Test De-Noising):** Detect 25+ secret formats + Shannon entropy (`H > 4.2`), automatically downgrading mock keys inside `tests/`, `fixtures/`, or `.env.example` to `INFO` to eliminate false positives.
   - **Engine 4 (AI, LLM & MCP Security Audit):** Scan for prompt injection concatenation sinks, hardcoded secrets in `.mcp.json` / `mcp_config.json`, unauthenticated MCP endpoints, and unsandboxed agent shell tools.
   - **Engine 5 (Auth-Boundary, CORS & Infra Audit):** Flag state-mutating API routes (`POST`/`PUT`/`DELETE`) lacking auth dependencies, permissive CORS (`allow_origins=["*"]` with credentials), and root-user `Dockerfile` configs.
   - **Engine 6 (Auto-Patch Diffs, OWASP/CWE Badges & SARIF 2.1.0 Export):** Attach `cwe_id`, `owasp_category`, `reachability_status`, `before_snippet`, `after_patch_snippet`, `github_url`, and `vscode_uri` to every finding. Add `GET /api/security/sarif` to export a valid SARIF 2.1.0 JSON report for GitHub Code Scanning.
2. Overhaul `frontend/src/components/SecurityPanel.tsx`:
   - Display a top **Security Posture Scorecard (`Grade A+ to F`)** with filter tabs: `All`, `Exploitable Taint Paths`, `Reachable CVEs`, `Secrets`, `AI & MCP Safety`, and `Auth & Infra`.
   - For every finding card, render: `[Highlight Attack Path on Mind Map 🎯]`, `[View Before/After Fix Patch 🛠️]`, `[Open Line in VS Code ⚡]`, `[Open on GitHub ↗]`, and a top-bar `[Export SARIF 2.1.0 Report 📥]` button.
   - Write comprehensive unit tests in `backend/tests/test_security_scanner.py` verifying taint detection, OSV CVE reachability, secret de-noising, and SARIF 2.1.0 schema compliance.
```

* 