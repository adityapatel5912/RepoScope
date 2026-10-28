# RepoScope: The Code Graph Engine for Humans and Agents

> **One unified code graph. Four ways in: The Interactive Canvas, The Terminal CLI, An MCP Server, and Your Editor.**

## Inspiration

Autonomous AI coding agents (Claude, Cursor, Devin, OpenCode) have revolutionized software development—yet they are fundamentally crippled by how they read code. Today, when an agent is asked *"What breaks if I change this function?"* or *"How does authentication flow through this repository?"*, it is forced to brute-force the codebase. It reads hundreds of files, burns millions of tokens, hallucinates call chains, and frequently exceeds the context window.

Meanwhile, human engineers face cognitive overload onboarding into massive, tangled repositories, manually tracing imports across dozens of tabs.

Existing developer tools picked one side of the line:

* Some built visual architecture diagrams for humans (static, quickly outdated).
* Others built CLI indexing tools for LLMs (opaque, invisible to developers).

We asked ourselves: **Why should humans and AI agents look at code through different lenses?**

We were inspired to build **RepoScope**: a single, high-fidelity polyglot code graph derived from Abstract Syntax Trees (ASTs). The human gets an interactive canvas, an explainable blast-radius simulator, and a live VS Code extension; the AI agent gets a native Model Context Protocol (MCP) server reading the **exact same index**.

## What it does

RepoScope indexes a local workspace or GitHub repository into an AST-derived knowledge graph and exposes that single index across four unified interfaces:

### 1. The Architecture Canvas & Collapsible MindMap V2

* **Dynamic D3 Force Graph**: Clusters code into architectural layers (Client/UI, Backend/API, Storage/Data, Integrations, Workers).
* **Collapsible Hierarchical MindMap**: Instant Left-to-Right and Top-to-Bottom orientation switching with real-time cluster search.
* **Topological Student Onboarding**: Organizes codebase files into progressive dependency tiers using Kahn's Topological Sort (Foundations → Domain Models → Services → Public APIs) with auto-evaluated architectural quizzes.

### 2. The Terminal CLI (`reposcope`, `reposcope-ai`)

* **Zero-Upload Privacy**: 100% offline local mode with zero telemetry.
* **Live File Watcher**: Incremental AST graph updates as you write code.
* **Terminal Security Auditor**: Inter-procedural security scanner outputting human summaries or standard OASIS SARIF 2.1.0 reports.

### 3. The Model Context Protocol (MCP) Server (`reposcope-mcp`, `npx reposcope-mcp`)

* **Native Agent Intelligence**: 13 high-order tools and 8 resources serving the graph directly to Claude Desktop, Cursor, OpenCode, and autonomous agents.
* **99.8% Measured Token Reduction**: Compresses repository context while preserving structural fidelity (e.g. compressing `psf/black` from 2,006,931 tokens down to 7,926 tokens).

### 4. The Editor Extension (VS Code / Cursor / VSCodium)

* **Activity Bar Mini-Map**: Live neighborhood architecture map focused on the active file.
* **CodeLens Caller Counts**: Shows incoming callers directly above exported symbols.
* **Status-Bar Risk Gauge**: Real-time blast-radius calculation for uncommitted changes.

### 5. Advanced Architectural & Security Intelligence

* **Six-Engine Graph-Contextual Security Suite**: Cross-File Taint Tracking (sources → sinks across module boundaries), High-Entropy Secrets (Shannon entropy H ≥ 4.2) with strict `<redacted>` masking, Offline Dependency CVE scanning, AST injection sink detection, insecure configurations, and route authentication bypass guards. Produces non-destructive, AST syntax-verified Unified Diff patches.
* **Explainable 3-Hop Impact Simulator**: Decomposes proposed edits into Hop 1 (direct callers), Hop 2 (transitive consumers), and Hop 3 (boundary API endpoints), incorporating historical Git co-change frequency and pinpointing downstream test coverage gaps.
* **Symbol-Level PR Impact & Contract Diff**: Inspects PR revisions without file caps to flag breaking method signatures, removed endpoints, and altered contracts, posting structured markdown reviews to GitHub.
* **Reverse Prompt Compiler**: Compiles codebase subgraphs into four deterministic prompt blueprints (`context`, `rebuild`, `spec`, and `feature`) for downstream AI coding workflows.
* **Interactive Architecture Scaffolder**: Generates production-ready starter kits (Clean Architecture, Ports & Adapters, Modular Monolith) with live file tree inspection and CLI bootstrap commands.

## How we built it

We engineered RepoScope with a strict, local-first, low-latency architecture:

* **Parsing & AST Layer**: Polyglot parsing across Python, TypeScript, TSX, JavaScript, Go, and Rust built on **Tree-sitter 0.25+**. It extracts file nodes, symbol definitions, `imports` edges, inter-file `calls`, and class inheritance hierarchies.
* **Graph Engine & Topology**: Built with **NetworkX** and custom adjacency algorithms. We compute PageRank structural centrality, Tarjan's Strongly Connected Components (SCC) for cycle detection, and Kahn's algorithm for topological DAG ordering.
* **Backend API**: High-performance **FastAPI (Python 3.11+)** server with Server-Sent Events (SSE) for live graph streaming, GitPython for commit churn and Shannon entropy author diversity, and an offline CVE knowledge base.
* **Frontend Canvas**: **React 18**, **TypeScript 5 (strict)**, and **Vite**, powered by **D3-hierarchy** and **React Flow** for butter-smooth visual interactions and collapsible mindmaps.
* **Agent Integration**: Standard **Model Context Protocol (MCP)** using the official Python SDK (stdio + Streamable HTTP) coupled with a zero-install Node runner (`packages/reposcope-mcp`).
* **VS Code Extension**: Written in TypeScript using the VS Code Extension API (`WebviewViewProvider`, `CodeLensProvider`, status bar items), packaged as a standalone `.vsix` artifact.

## Challenges we ran into

1. **Tree-Sitter Query API Breaking Changes**: Tree-sitter 0.25 deprecated the legacy `Query.captures()` API in favor of `QueryCursor(Query(lang, q)).captures(node)`. Migrating multi-language query captures across Python, TypeScript, JavaScript, Go, and Rust while maintaining millisecond parsing speed required rewriting query cursors from the ground up.
2. **Cross-File Inter-Procedural Taint Tracking**: Tracking untrusted data flows across module boundaries without a full compiler intermediate representation (IR) is notoriously difficult. We solved this by building an inter-procedural function registry (`FuncSummary`) that analyzes parameter → sink, parameter → return, and ambient return flows, linking call sites across the code graph.
3. **Graph Layout Performance on Large Repositories**: Visualizing repositories with thousands of files and tens of thousands of edges can easily cause browser DOM freezing. We designed a dual-mode layout: large repositories automatically group into top-level module cards and layer clusters (Client, API, Storage, Workers), while the D3 hierarchy utilizes virtualized node collapsing.
4. **SSE Streaming vs Playwright Automation**: Live Server-Sent Events (`/api/local/events`) continuously hold HTTP streaming connections open, causing Playwright's `networkidle` lifecycle event to hang indefinitely. We resolved this by re-architecting the E2E test harness to synchronize via DOM content loaded and specific event bus listeners.

## Accomplishments that we're proud of

* **99.8% Measured Token Reduction**: Benchmarking over 14 production repositories proved that RepoScope's PageRank-pruned repo map slashes agent context token consumption by 98.5% to 99.8% while eliminating hallucinated dependencies.
* **The "One Index" Guarantee**: A single shared knowledge store (`.reposcope/`) powers four distinct developer experiences simultaneously—the canvas, the terminal CLI, the MCP server, and the editor extension.
* **Zero-Upload Local Privacy**: Complete code graph generation, 6-engine security scans, and blast radius simulations run 100% locally on the developer's machine with zero telemetry or cloud dependencies.
* **Rigorous Test Suite**: Over **590 automated pytest unit tests**, 20 VS Code extension tests, and a complete Playwright browser E2E test battery running in CI with 100% green passing status.

## What we learned

* **ASTs Beat Regex Every Time**: Early code analysis tools relied on regular expressions, which constantly broke on multi-line imports, aliased namespaces, and dynamic re-exports. Tree-sitter's concrete syntax trees provided the rock-solid foundation needed for deterministic taint tracking and contract diffing.
* **Graph Topology Is the True Antidote to Agent Hallucinations**: When LLMs are given raw text, they guess at architecture. When given topological graph evidence (directed call chains, boundary interfaces, and caller counts), hallucination rates drop to near zero.
* **High-DPI Visual Polish Matters**: Developer tools must not only be technically sound but visually intuitive. Designing high-contrast node palettes, interactive unified diff viewers, and responsive D3 collapsible trees transformed RepoScope from a raw compiler into a joy to use.

## What's next for RepoScope

* **High-Scale Graph Engine & Enterprise CI**:
  * WebGL-accelerated canvas rendering capable of visualizing 100,000+ node enterprise monorepos at 60 FPS.
  * Native **Kùzu graph database** storage backend for persistent disk-backed graph queries.
  * Automated **GitHub Actions PR Bot** that comments symbol-level contract breaks and security findings directly on pull requests.
* **Public Distribution & Ecosystem Rollout**:
  * Official publication of the `reposcope-2.8.0.vsix` extension to the **Visual Studio Code Marketplace** and **Open VSX Registry**.
  * Public package distribution of global CLI commands on **PyPI** (`pip install reposcope`) and **npm** (`npx reposcope-mcp`).
* **Self-Healing Autonomous Refactoring**:
  * Integrating autonomous agents with RepoScope's AST-verified patch engine to automatically generate and test pull requests that remediate architectural drift and cross-file vulnerabilities.
