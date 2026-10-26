# RepoScope documentation

This is the index for the **current** RepoScope documentation. It separates
docs that describe the shipped v2.0 product from reference material and from
historical build artifacts.

## Start here

| Document | What it covers |
|---|---|
| [README](../README.md) | Product overview, quick start, screenshots, verification status |
| [Architecture](ARCHITECTURE.md) | Modules, data flow, API surface, graph layout, MCP transports |
| [Features](FEATURES.md) | Every shipped feature, how to use it, and its limits |
| [Verification checklist](VERIFICATION_CHECKLIST.md) | The four manual checks still pending; deliberately unchecked |
| [QA report](QA_REPORT.md) | Automated coverage and the honest gaps |
| [Screenshots](SCREENSHOTS.md) | Current screenshots, brand assets, dimensions, and capture notes |

## Development and operations

| Document | What it covers |
|---|---|
| [Development](DEVELOPMENT.md) | Local setup, tests, frontend build, extension build, QA harness |
| [Deployment](DEPLOYMENT.md) | Render, Vercel, Open VSX, environment variables |
| [Troubleshooting](TROUBLESHOOTING.md) | Known failure modes and fixes |
| [Runbooks](RUNBOOKS.md) | Reindex, restart, publish, and rollback procedures |
| [Demo script](DEMO.md) | A current three-minute walkthrough |
| [Extension README](../extensions/vscode/README.md) | Install and use the VS Code / Cursor / VSCodium extension |
| [Contributing](../CONTRIBUTING.md) | Development workflow and commit conventions |
| [Code of Conduct](../CODE_OF_CONDUCT.md) | Community standards and reporting |
| [License](../LICENSE) | RepoScope Source-Available License 1.0 |

## Reference

| Document | What it covers |
|---|---|
| [v2.0 roadmap](ROADMAP_V2.md) | The plan, delivered sprints, and remaining gaps |
| [Knowledge graph schema](KNOWLEDGE_GRAPH_SCHEMA.md) | Node ids, edge types, and rendering rules |
| [Repository tracking](REPO_TRACKING.md) | GitHub change tracking and state |
| [Agent instructions](AGENT_INSTRUCTIONS.md) | Runtime agent behaviour and MCP usage |
| [MCP client config](reposcope-mcp.json) | A copy-paste MCP client entry |
| [OpenCode MCP config](opencode-mcp.json) | The working local OpenCode server entry |
| [Fixtures and demo repositories](SEED_REPO.md) | Committed fixtures and how to load one |
| [Ownership](OWNERSHIP.md) | Status of the planned ownership overlay |
| [Changelog](../CHANGELOG.md) | Release history |

## Documentation rules

1. **Current state only in current docs.** Mark historical material as
   historical instead of silently updating it.
2. **No verified claim without a command.** Test counts, build results, and
   benchmark numbers should say how they were produced.
3. **Manual checks stay unchecked.** The checklist is not a marketing page;
   a human signs each item.
4. **Limits are part of the feature.** If a feature needs an LLM key, a native
   dialog, or a marketplace account, say so where the feature is described.
5. **One index.** Features are implemented once in the backend graph and read
   by the canvas, CLI, MCP server, and extension. Documentation should not
   imply separate indexes.

Last reviewed: 2026-10-25.
