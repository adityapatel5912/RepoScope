# Model Context Protocol (MCP) Server Reference

RepoScope provides an in-process, deterministic Model Context Protocol (MCP) server that exposes codebase intelligence, AST structural skeletons, interface diffs, and context packs directly to AI coding agents (such as Claude Code, Antigravity, Cursor, Windsurf, OpenCode, and Cline).

The MCP server exposes exactly **13 tools** and **8 resources**.

---

## 1. Connection Configurations

RepoScope supports two transport mechanisms: **stdio** (direct subprocess) and **Streamable HTTP** (for remote / network setups).

> [!NOTE]
> Server-Sent Events (SSE) is not used for MCP transport. The HTTP transport uses standard Streamable HTTP endpoints.

Every command accepts `--root /absolute/path/to/repo`. When omitted, the root is `$REPOSCOPE_ROOT`, then the current working directory.

### Stdio Transport (Recommended for Local Agents)

#### Claude Code (project `.mcp.json`, or `claude mcp add`)

```json
{
  "mcpServers": {
    "reposcope": {
      "command": "reposcope-mcp",
      "args": ["--root", "/absolute/path/to/repo"]
    }
  }
}
```

Equivalent CLI form:

```bash
claude mcp add reposcope -- reposcope-mcp --root /absolute/path/to/repo
```

#### Antigravity / Cursor / Windsurf (`.cursor/mcp.json` or client configuration)

```json
{
  "mcpServers": {
    "reposcope": {
      "command": "reposcope-mcp",
      "args": ["--root", "/absolute/path/to/repo"]
    }
  }
}
```

The nine-agent harness configurator in the web UI generates the correct file for each client, including the project-relative `--root` argument.

### Streamable HTTP Transport

Start the dedicated MCP server:

```bash
reposcope-mcp --http --root /absolute/path/to/repo
```

The default endpoint is `http://127.0.0.1:8765/mcp`; `--host` and `--port` change the bind address. This is a separate process from the web UI server (`reposcope run .`, default `http://127.0.0.1:4100`).

```json
{
  "mcpServers": {
    "reposcope-http": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

---

## 2. Tools Reference (13 Tools)

| Tool Name | Arguments | Returns | Description & Caveats |
|---|---|---|---|
| `get_architecture_overview` | `max_depth: int = 2` | `available`, counts, `layers`, `top_hubs`, `entry_points`, `reachable_within_depth` | High-level shape: layers, centrality hubs, entry points, and reachability. Static graph only. |
| `calculate_blast_radius` | `target_file: str`, `target_symbol: str \| None = None`, `depth: int = 3` | `available`, target impact with direct and transitive dependents, depth, truncation | Traces dependents of a file or of one symbol in that file. `depth` is clamped to 1..10. Dynamic calls and reflection are invisible. |
| `get_dependency_lineage` | `file_path: str`, `direction: str = "both"` | `available`, `target`, `direction`, `upstream` and/or `downstream` node lists | Shows what a file needs (`upstream`) and what needs it (`downstream`), traversed to depth 5. |
| `explain_architectural_rule` | `source_file: str`, `imported_file: str` | `source_layer`, `imported_layer`, `violated`, `violation`, `rules_in_effect` | Checks one import against the declared layer rules (`.reposcope.yml` or the built-in defaults). |
| `get_repo_map` | `token_budget: int = 8000` | Budgeted repo map with context-saving metrics | Centrality-ranked file map that fits the requested token budget. |
| `find_dependency_cycles` | *None* | File-level and symbol-level cycles, including layer spans | Detects import/call cycles from statically analyzed edges only. |
| `get_hotspots` | `limit: int = 10` | Churn x centrality hotspot report | Requires git history. `limit` is clamped to 1..100. |
| `find_unreachable_symbols` | *None* | `unreachable` candidates plus `entry_points`, `total`, and `caveat` | **Caveat**: Static reachability is an estimate, not proof of dead code. Dynamic dispatch, reflection, plugin registration, and external consumers are invisible. |
| `get_mindmap_hierarchy` | `include_symbols: bool = True`, `max_nodes: int = 2000` | Hierarchical tree: root -> pillars -> folders -> files -> symbols | Deterministic projection. `max_nodes` is clamped to 1..200000. |
| `get_ast_skeleton` | `file_path: str`, `max_symbols: int = 200` | File metadata plus `symbols` (`name`, `kind`, `line`, `end_line`, `exported`, `complexity`, `role`, `signature`), `counts`, `truncated` | Returns symbol declarations without bodies. `max_symbols` is clamped to 1..1000. |
| `get_context_pack` | `paths: str = ""`, `detail: str = "skeleton"`, `budget: int = 8000`, `since_hash: str \| None = None` | Deterministic context pack object with files, omissions, caps, counts, hash, and token accounting | **JSON only over MCP** (TOON is an HTTP export). `detail` is `skeleton` or `full`; `budget` must be 500..200000. See [Context Pack Contract](#4-context-pack-contract). |
| `diff_interface_contracts` | `file_path: str`, `patch: str \| None = None`, `old_source: str \| None = None`, `new_source: str \| None = None`, `include_consumers: bool = True` | `findings`, `counts` (`breaking`/`warning`/`info`/`total`), `consumers_attached`, `note` | Supply either `patch` or both `old_source` and `new_source`. **Caveat**: No finding is not proof that no consumer breaks; unsupported languages and dynamic calls are invisible. |
| `get_ranked_reading_path` | `max_files: int = 12` | Three levels (`Entry Points`, `Core Modules`, `Utils & Leaves`), a flat ranked `path`, totals, and `caveat` | `max_files` is clamped to 1..50. Ranking uses static connectivity; it is a starting path, not a measure of code quality. |

---

## 3. Resources Reference (8 Resources)

All resources return `application/json` text.

| Resource URI | Payload | Recommended Usage |
|---|---|---|
| `reposcope://graph/summary` | Node and edge counts, file/symbol counts, edge types, and top hubs | Cheapest overview of the graph's shape. |
| `reposcope://hotspots` | Churn x centrality top-10 report | Find files most likely to regress. |
| `reposcope://repo-map` | Budgeted repo map (8,000 tokens) with metrics | Compact centrality-ranked file registry. |
| `reposcope://dead-code` | Statically unreachable symbol candidates | Treat as candidates for review, not proof of dead code. |
| `reposcope://cycles` | File and symbol dependency cycles with layer spans | Architecture cleanup and boundary checks. |
| `reposcope://mindmap` | Full semantic hierarchy (`include_symbols=true`, `max_nodes=2000`) | Hierarchical navigation from pillars to symbols. |
| `reposcope://api-routes` | Detected HTTP routes with methods, paths, and handlers (first 500, plus `total`/`truncated`) | API surface discovery. |
| `reposcope://context-pack` | Default skeleton context pack (`detail=skeleton`, `budget=8000`) | Cache-friendly default context for a new session. |

---

## 4. Context Pack Contract

The `get_context_pack` MCP tool and the `GET /api/context/pack` endpoint share the same deterministic pack builder:

- **Defaults**: `detail="skeleton"`, `budget=8000`. The HTTP endpoint additionally defaults to `format="json"`.
- **Detail Levels**:
  - `skeleton`: Includes symbol declarations, signatures, line numbers, and roles. Symbol bodies are omitted.
  - `full`: Includes symbol bodies, each capped at **120 lines** or **12,000 characters** (per symbol, not per file). Applied caps are recorded in `caps` with `reason` `max-lines` or `max-chars`, and the symbol's `body_truncated` flag is set.
- **Budget Accounting**: The budget is validated between 500 and 200,000 tokens (inclusive). Files are added only while the encoded pack stays within budget. Files that do not fit are listed in `omitted` with reason `budget`.
- **Omission Reasons**: `budget`, `not-indexed`, `ambiguous`, `outside-root`, and `unreadable`. Absolute paths, drive-qualified paths, and `..` escapes are omitted as `outside-root`; they are not returned as an HTTP 400.
- **Payload Fields**: `schema_version`, `available`, `detail`, `budget`, `files`, `omitted`, `caps`, `truncated`, `counts` (`files_included`, `files_requested`, `symbols_included`), `hash`, `tokens` (`pack`, `budget`), `format`, and `root`. On a `since_hash` mismatch, `since_hash` is echoed.
- **Content Hash & Delta Sync**:
  - `hash` is `sha256:` plus a SHA-256 digest over a normalized payload that **excludes** volatile fields (`format`, `since_hash`, `root`, `hash`, token-count fields, and timestamps).
  - `format=json` and `format=toon` yield the same `hash`.
  - When the client supplies `since_hash=<current_hash>`, the server returns an unchanged envelope:
    ```json
    {
      "schema_version": 1,
      "available": true,
      "unchanged": true,
      "detail": "skeleton",
      "budget": 8000,
      "hash": "sha256:...",
      "format": "json"
    }
    ```
  - The REST response sets `X-RepoScope-Context-Hash` on every pack and `X-RepoScope-Context-Unchanged: 1` on a match. The unchanged envelope is always JSON, even when `format=toon` was requested.
- **HTTP Validation**: Out-of-range `budget` or an invalid `format`/`detail` returns `422` from query validation. `400` is reserved for a disabled TOON export or a missing `toon-format` dependency. `503` means no repository is loaded.

---

## 5. JSON vs TOON Policy

- **Default Format**: Compact JSON (`format=json`) is the default. It requires zero external dependencies and provides universal compatibility across all LLMs.
- **TOON Opt-in**: Token-Oriented Object Notation (`format=toon`) is available on the REST endpoint via the optional dependency `reposcope[toon]` (`toon-format>=1.2,<2`). The MCP `get_context_pack` tool has no `format` argument and always returns JSON.
- **Measured Compression**: As documented in [TOON Compression Benchmark](TOON_BENCHMARK.md), TOON measured a **median +39.1% token reduction** over compact JSON across five repositories at exact commits. RepoScope makes no unverified claims (such as 85%).
- **Kill Switch**: Setting `REPOSCOPE_TOON=0` disables the REST TOON export; requesting `format=toon` then returns `400`. It has no effect on the JSON-only MCP tool.

---

## 6. Skill Integration

RepoScope ships 5 specialized agent skills:

1. `blast-radius-guard`: First tool call is `get_ast_skeleton`. Verifies impact before modifying shared modules.
2. `zero-grep-architect`: First tool call is `get_architecture_overview`. Navigates architectural boundaries without brute-force grep.
3. `pr-contract-shield`: First tool call is `diff_interface_contracts`. Validates breaking API and export changes before pull requests.
4. `onboarding-navigator`: First tool call is `get_ranked_reading_path`. Generates a prioritized reading itinerary.
5. `dead-code-surgeon`: First tool call is `find_unreachable_symbols`. Identifies unreferenced code candidates and states: "Static reachability is an estimate, not proof of dead code."

### Skill Invocation Notes

- **Claude Code**: Reads skills installed at `.claude/skills/<id>/SKILL.md`.
- **Antigravity**: Reads skills installed at `.agents/skills/<id>/SKILL.md`.
- **OpenCode**: Reads skills from both directories. Invocation in OpenCode is explicit via its skill tool; RepoScope does not claim automatic metadata-only invocation.
- RepoScope does not write `.opencode/skills`.

---

## 7. What Changed in Phase 4

Phase 4 preserved the existing 8 MCP tools and 5 resources while adding:

- **5 New Tools**: `get_mindmap_hierarchy`, `get_ast_skeleton`, `get_context_pack`, `diff_interface_contracts`, `get_ranked_reading_path`.
- **3 New Resources**: `reposcope://mindmap`, `reposcope://api-routes`, `reposcope://context-pack`.
- **Delta Sync**: `since_hash` support with content-hashed unchanged envelopes.
- **Optional TOON Adapter**: Lazily loaded, REST-only, opt-in format with a measured ~39% token reduction.
