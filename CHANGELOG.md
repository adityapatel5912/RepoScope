# Changelog

## [Unreleased] — v2.0 roadmap
### Added
- `docs/ROADMAP_V2.md` — v2.0 technical architecture upgrade plan, written against an audit of the current codebase
  - Audit baseline: verified inventory of existing features, gaps, and installed dependencies
  - Ten binding corrections to the original specification (MCP transport, git-churn module placement, breaking-change detector consolidation, shared architecture rules, node-id contract, and more)
  - Milestones M1–M6: Tree-sitter polyglot engine, IDE deep linking, local CLI ingestion, MCP server, VS Code/Cursor extension, PR Impact Bot 2.0, graph storage and incremental indexing
  - Milestones M7–M10: PageRank centrality, cycle and unreachable-symbol detection, repo map and token-efficiency measurement, CI quality gate with SARIF, architecture-as-code rules, and PR-bot repositioning onto architecture governance
  - Competitive audit and strategic positioning against the 2026 code-graph/MCP field
  - Sprint plan, agent execution prompts, risk register, and definition of done

### Notes
- No runtime behaviour changed in this release — documentation only.

## [1.0.0] — 2026-09-26
### Added
- Initial release for the IBM Bob 2.0 Hackathon
- Architecture graph with dagre layered layout (client / backend / storage / external / compute)
- Conversational Q&A with file, function, and commit citations (SSE streaming)
- Conversational Code Tours with step badges and progress bar
- What-If Impact Analysis with blast-radius rings and legend
- Repo tracking — commits, PRs, issues, releases on demand
- Reverse Build Prompt — turn any repo into an agent-ready prompt
- File Tree with GitIngest-style formatting and single-file download
- Graph export to PNG and SVG
- BYOK — GitHub PAT for private repos, stored in memory only
- Multi-key API rotation (OpenRouter → Groq → NVIDIA NIM)
- Health check endpoint with uptime, memory, and key counts
- One-click demo repositories (Verdict, StudyRot)
- Deployment configs (Render + Vercel)
