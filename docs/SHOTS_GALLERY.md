# RepoScope Visual Verification Gallery (V2.7 & V2.8)

This visual gallery consolidates the end-to-end visual verification artifacts captured across RepoScope V2.7 and V2.8. Every screenshot represents a live, tested capability validated across our Playwright browser automation battery.

---

## Table of Contents

1. [Phase 13: Six-Engine Graph-Contextual Security Suite](#phase-13-six-engine-graph-contextual-security-suite)
2. [Phase 12: Explainable 3-Hop Impact Simulator](#phase-12-explainable-3-hop-impact-simulator)
3. [Phase 11: Symbol-Level PR Impact & Contract Diff](#phase-11-symbol-level-pr-impact--contract-diff)
4. [Phase 10: Hotspots, Bus Factor & Churn Time Machine](#phase-10-hotspots-bus-factor--churn-time-machine)
5. [Phase 9: Topological Student Onboarding & Verified Katas](#phase-9-topological-student-onboarding--verified-katas)
6. [Phase 8: Architectural Guided Tours & Universal Chat Action Cards](#phase-8-architectural-guided-tours--universal-chat-action-cards)
7. [Phase 7: Interactive Architecture Scaffolder](#phase-7-interactive-architecture-scaffolder)
8. [Phase 6: Reverse Prompt Compiler](#phase-6-reverse-prompt-compiler)
9. [Phase 5: MindMap V2 & D3 Graph Visualizer](#phase-5-mindmap-v2--d3-graph-visualizer)
10. [Phase 4: Verified Chat Citations & Line Range Previews](#phase-4-verified-chat-citations--line-range-previews)

---

## Phase 13: Six-Engine Graph-Contextual Security Suite

The Six-Engine Security Suite provides zero-hallucination vulnerability auditing directly within the architecture visualizer.

### Key Capabilities Verified:
- **Engine Filter Tabs**: Filter across Cross-File Taint, Hardcoded Secrets, Dependency CVEs, AST Injections, Insecure Configs, and Auth Bypass.
- **Taint Flow Trace**: Visualizes the exact propagation path from input source (`request.args`) through inter-procedural functions (`run_command`) into dangerous sinks (`subprocess.run`).
- **Syntax-Verified Remediation Diff**: Generates non-destructive unified diff patches with AST syntax validation and one-click clipboard copying.
- **OASIS SARIF 2.1.0 Export**: One-click download of standardized security reports for CI/CD ingestion.

![Security Suite Panel](screenshots/v2/gallery/security_suite_panel.png)

---

## Phase 12: Explainable 3-Hop Impact Simulator

Predicts the cascading blast radius of proposed code edits before modifying a single line of code.

### Key Capabilities Verified:
- **3-Hop Downstream Tree**: Categorizes impacted nodes into Hop 1 (direct callers), Hop 2 (transitive consumers), and Hop 3 (boundary API endpoints).
- **Mathematical Score Breakdown**: Displays weighted risk points (direct callers × 3, transitive × 1, boundaries × 2, test gaps × 2).
- **Historical Git Co-Change Weighting**: Highlights files that historically change together in Git commits.
- **Downstream Test Gaps**: Flags un-tested downstream modules to prevent silent regressions.

![Impact Simulator Panel](screenshots/v2/gallery/impact_simulator_panel.png)

---

## Phase 11: Symbol-Level PR Impact & Contract Diff

Goes beyond raw git diffs to detect exact class, function, and interface contract breaks across pull request revisions.

### Key Capabilities Verified:
- **AST Symbol-Level Diffing**: Detects altered route decorators (`GET /api/v1/users` → `GET /api/v2/users`) and modified function signatures (added mandatory parameters).
- **Risk Tiers & Consumer Tracing**: Identifies all affected client and server consumer files across the repository graph.
- **Automated PR Review Comment**: Previews structured markdown comments ready to post to GitHub pull requests.

![PR Impact Symbols Panel](screenshots/v2/gallery/pr_impact_symbols_panel.png)

---

## Phase 10: Hotspots, Bus Factor & Churn Time Machine

Correlates structural graph metrics with Git commit history to surface architectural risks before they cause production outages.

### Key Capabilities Verified:
- **Hotspot Risk Scoring**: Combines PageRank structural centrality with 90-day Git churn velocity.
- **Bus Factor Entropy Warning**: Calculates author diversity via Shannon entropy, flagging files maintained by a single contributor.
- **Time Machine Architectural Drift**: Compares arbitrary Git revisions (`HEAD~10` vs `HEAD`) to highlight newly introduced circular dependencies and architectural sprawl.

![Metrics & Hotspots Panel](screenshots/v2/gallery/metrics_hotspots_panel.png)

---

## Phase 9: Topological Student Onboarding & Verified Katas

Converts the complex code graph into an optimal, non-circular reading order based on directed acyclic graph (DAG) dependencies.

### Key Capabilities Verified:
- **Kahn's Topological Tiers**: Groups repository files into 4 progressive tiers: Foundations (L1), Domain Models (L2), Services (L3), and Public APIs (L4).
- **Interactive Architectural Katas**: Multiple-choice challenges verifying comprehension of leaf modules, data models, and entry points.
- **AST Graph Verification**: Automated grading validating answers against live graph topology with instant feedback and tier unlocks.

![Topological Onboarding Tiers](screenshots/v2/gallery/onboarding_tiers_panel.png)

---

## Phase 8: Architectural Guided Tours & Universal Chat Action Cards

Provides directed, narrative walkthroughs across codebase concepts with deep-link graph navigation and universal chat action cards.

### Key Capabilities Verified:
- **Four Curated Tour Tracks**: Pre-configured paths for Request Lifecycle, Data Flow, Blast Radius Impact, and Onboarding.
- **Interactive Step Navigation**: Highlights active files, line numbers, and architectural rationale on each step.
- **Universal Chat Action Cards**: Context-aware intent detection in chat conversations emitting one-click interactive action cards (`[Launch Architecture Tour]`, `[Run 6-Engine Audit]`, `[Export SARIF]`).

![Tour Tracks Panel](screenshots/v2/gallery/tour_tracks_panel.png)

![Universal Chat Action Card](screenshots/v2/gallery/chat_tour_action_card.png)

---

## Phase 7: Interactive Architecture Scaffolder

Generates clean, production-ready architectural starter kits based on detected project conventions.

### Key Capabilities Verified:
- **Starter Kit Templates**: Clean Architecture, Ports & Adapters, Modular Monolith, Microservice Core.
- **Multi-File Preview**: Real-time syntax-highlighted code preview of generated boilerplate and architecture documentation.
- **CLI Bootstrap Banner**: One-click terminal execution command (`npx reposcope-mcp scaffold`) and ZIP bundle download.

![Scaffolder Modal Code Preview](screenshots/v2/gallery/scaffold_modal_code.png)

![Scaffolder Modal README Preview](screenshots/v2/gallery/scaffold_modal_readme.png)

![Scaffolder Copied CLI Command](screenshots/v2/gallery/scaffold_modal_copied_cmd.png)

---

## Phase 6: Reverse Prompt Compiler

Compiles repository subgraphs into dense, high-signal prompt templates tailored for autonomous coding agents.

### Key Capabilities Verified:
- **Four Compilation Modalities**:
  - `context`: Comprehensive topological overview with structural dependency hierarchy.
  - `rebuild`: Green-field reproduction specification detailing interfaces and invariants.
  - `spec`: Formal API contracts and data schemas for test-driven development.
  - `feature`: Targeted context slice designed for ticket implementation without context window bloat.
- **Token Count Estimator**: Displays precise token budgets and markdown export capabilities.

![Reverse Prompt - Feature Mode](screenshots/v2/gallery/rp_feature_mode.png)

![Reverse Prompt - Context Mode](screenshots/v2/gallery/rp_context_mode.png)

![Reverse Prompt - Rebuild Mode](screenshots/v2/gallery/rp_rebuild_mode.png)

![Reverse Prompt - Spec Mode](screenshots/v2/gallery/rp_spec_mode.png)

---

## Phase 5: MindMap V2 & D3 Graph Visualizer

Dynamic D3 hierarchical tree navigation offering instant structural clarity across polyglot repositories.

### Key Capabilities Verified:
- **Orientation Switching**: Toggle between Horizontal (Left-to-Right) and Vertical (Top-to-Bottom) layouts.
- **Collapsible Subtree Clusters**: Expand and collapse directory-level clusters with zero frame lag.
- **Directory Clustering**: Graph grouping by architectural layers and top-level modules.

![MindMap V2 First Paint](screenshots/v2/gallery/mm_v2_first_paint.png)

![MindMap V2 Backend Expanded](screenshots/v2/gallery/mm_v2_backend_expanded.png)

![MindMap V2 Left-to-Right Orientation](screenshots/v2/gallery/mm_v2_lr_mode.png)

![Graph Directory Clustering](screenshots/v2/gallery/graph_fixed_directories.png)

![Graph Ungrouped Topology](screenshots/v2/gallery/graph_ungrouped.png)

---

## Phase 4: Verified Chat Citations & Line Range Previews

Streams conversational answers with AST-verified file, symbol, and line-range citation pills.

### Key Capabilities Verified:
- **Interactive Citation Pills**: File and line references (`backend/main.py:450`) rendered as clickable interactive chips.
- **Hover Card Previews**: Instant tooltip showing snippet code, line ranges, and deep-navigation links into the canvas visualizer.

![Chat Citations Overview](screenshots/v2/gallery/chat_citations_overview.png)

![Chat Citation Hover Preview](screenshots/v2/gallery/chat_citations_hover.png)

![Chat Message Closeup](screenshots/v2/gallery/chat_message_closeup.png)
