# Model Context Protocol (MCP) Server Reference

RepoScope provides an in-process, deterministic Model Context Protocol (MCP) server that exposes codebase intelligence, AST structural skeletons, interface diffs, and context packs directly to AI coding agents (such as Claude Code, Antigravity, Cursor, Windsurf, OpenCode, and Cline).

The MCP server exposes exactly **13 tools** and **8 resources**.

---

## 1. Connection Configurations

RepoScope supports two transport mechanisms: **stdio** (direct subprocess) and **Streamable HTTP** (for remote / network setups).

> [!NOTE]
> Server-Sent Events (SSE) is not used for MCP transport. The HTTP transport uses standard Streamable HTTP endpoints.

### Stdio Transport (Recommended for Local Agents)

#### Claude Code (`~/.claude/claude_desktop_config.json` or `.claude.json`)
```json
{
  "mcpServers": {
    "reposcope": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "REPOSCOPE_TOON": "1"
      }
    }
  }
}
```

#### Antigravity / Cursor / Windsurf (`.cursor/mcp.json` or global configuration)
```json
{
  "mcpServers": {
    "reposcope": {
      "command": "reposcope-mcp",
      "args": []
    }
  }
}
```

### Streamable HTTP Transport

When RepoScope runs with its web API server (`reposcope run .` on default port 8010), the MCP endpoint is available over Streamable HTTP:

```json
{
  "mcpServers": {
    "reposcope-http": {
      "url": "http://127.0.0.1:8010/mcp"
    }
  }
}
```

---

## 2. Tools Reference (13 Tools)

| Tool Name | Arguments | Returns | Description & Caveats |
|---|---|---|---|
| `get_symbol_impact` | `path: str`, `symbol: str`, `max_depth: int = 3` | Blast radius JSON with `direct_dependents`, `transitive_dependents`, `depth`, `truncated` | Traces callers of a symbol. Dynamic invocation, reflection, or unindexed callers are not included. |
| `get_file_impact` | `path: str`, `max_depth: int = 3` | Blast radius JSON for file imports | Measures file-level downstream dependencies. |
| `get_architecture_overview` | *None* | Summary of layers, component counts, entry points, and coupling | Architectural high-level view. Does not guarantee completeness for dynamically generated code. |
| `find_circular_dependencies` | `layer: str \| None = None` | List of strongly connected cycles | Detects import/call cycles. Limited to statically analyzed edges. |
| `find_unreachable_symbols` | `include_entry_points: bool = False`, `include_tests: bool = False`, `max_symbols: int = 100` | Unreachable symbols list with file, line, kind, and total counts | **Caveat**: Static reachability is an estimate, not proof of dead code. Dynamic dispatch, reflection, plugin registration, and external consumers are invisible. |
| `explain_architecture_rules` | *None* | Active layer hierarchy, allowed crossings, and violated edges | Checks codebase boundaries against `.reposcope.yml` rules. |
| `get_active_tour` | *None* | Steps, files, lines, and narrative descriptions | Guided architectural tour. Returns empty step array if no tour is active. |
| `calculate_churn_metrics` | `days: int = 30`, `top_n: int = 20` | Hotspots with commit count, churn, and coupling | Git-based churn statistics. Requires git history in the target repository. |
| `get_mindmap_hierarchy` | `depth: int = 4`, `max_children: int = 50` | Hierarchical tree nodes (`name`, `kind`, `role`, `children`, `metrics`) | Returns the semantic hierarchy from pillars down to files/symbols. |
| `get_ast_skeleton` | `path: str`, `max_symbols: int = 200` | File symbol skeleton (`symbols`, `signatures`, `line`, `kind`, `exported`) | Returns symbol definitions without bodies. Clamped to 1..1000 symbols. Never dumps raw implementation code. |
| `get_context_pack` | `paths: str = ""`, `format: str = "json"`, `detail: str = "skeleton"`, `budget: int = 8000`, `since_hash: str \| None = None` | Deterministic context pack string (compact JSON or TOON) | Budgeted context packing. Omits bodies in `skeleton` mode; truncates files at 120 lines / 12,000 characters in `full` mode. |
| `diff_interface_contracts` | `base_ref: str = "HEAD"` | Changed exports, parameter types, return types, and route changes | **Caveat**: No finding is not proof that no consumer breaks. Unsupported languages and dynamic calls are invisible. |
| `get_ranked_reading_path` | `goal: str = "onboarding"`, `max_files: int = 10` | Ordered list of critical files with rank, score, role, and rationale | Graph-guided traversal for code comprehension. |

---

## 3. Resources Reference (8 Resources)

| Resource URI | Payload Format | Recommended Usage |
|---|---|---|
| `reposcope://repo-map` | `application/json` | File and symbol registry with roles, export status, and entry-point flags. |
| `reposcope://arch-rules` | `application/json` | Defined architectural layers, forbidden dependencies, and rule violations. |
| `reposcope://active-tour` | `application/json` | Current interactive tour step sequence. |
| `reposcope://churn-report` | `application/json` | High-frequency churn files and co-change clusters from git logs. |
| `reposcope://dead-code` | `application/json` | Candidates with zero incoming static references. Treat as candidates for review, not proof of dead code. |
| `reposcope://mindmap` | `application/json` | Full semantic tree for codebase overview and hierarchical navigation. |
| `reposcope://api-routes` | `application/json` | Detected API endpoints (FastAPI, Express, etc.) with methods, paths, and handler symbols. |
| `reposcope://context-pack` | `application/json` | Default budgeted skeleton context pack (`format=json`, `detail=skeleton`, `budget=8000`). |

---

## 4. Context Pack Contract

The `get_context_pack` tool and `/api/context/pack` endpoint share a strict deterministic contract:

- **Defaults**: `format="json"`, `detail="skeleton"`, `budget=8000`.
- **Detail Levels**:
  - `skeleton`: Includes exported and internal symbol declarations, signatures, line numbers, and roles. Symbol bodies are completely omitted.
  - `full`: Includes file source code, capped strictly at **120 lines** or **12,000 characters** per file. Caps are reported in the `caps` metadata array.
- **Budget Accounting**: Token consumption is budgeted from **500 to 200,000 tokens**. When the budget is exhausted, remaining files are omitted and enumerated under `omitted: [{"path": "...", "reason": "budget_exceeded"}]`.
- **Content Hash & Delta Sync**:
  - The SHA-256 hash `hash` is computed over a normalized representation that **excludes** volatile fields (`format`, `since_hash`, `root`, `tokens`).
  - Both `format=json` and `format=toon` yield the exact same `hash`.
  - When the client supplies `since_hash=<current_hash>`, the server returns an unchanged envelope:
    ```json
    {
      "schema_version": 1,
      "available": true,
      "unchanged": true,
      "hash": "<sha256>",
      "message": "Context unchanged since provided hash"
    }
    ```
- **Safety**: Relative path traversal (e.g. `../`) is rejected and flagged as `path_traversal`. Unindexed or missing files are marked `file_not_found`.

---

## 5. JSON vs TOON Policy

- **Default Format**: Compact JSON (`format=json`) is the default. It requires zero external dependencies and provides universal compatibility across all LLMs.
- **TOON Opt-in**: Token-Oriented Object Notation (`format=toon`) is available via the optional dependency `reposcope[toon]` (`toon-format>=1.2,<2`).
- **Measured Compression**: As documented in [TOON Compression Benchmark](file:///docs/TOON_BENCHMARK.md), TOON delivers a **median +39.0% token reduction** over compact JSON. RepoScope makes no unverified claims (such as 85%).
- **Kill Switch**: Setting `REPOSCOPE_TOON=0` completely disables TOON generation and instructs clients to use `format=json`.

---

## 6. Skill Integration

RepoScope ships 5 specialized agent skills:

1. `blast-radius-guard`: First tool call is `get_ast_skeleton`. Verifies impact before modifying shared modules.
2. `zero-grep-architect`: First tool call is `get_architecture_overview`. Navigates architectural boundaries without brute-force grep.
3. `pr-contract-shield`: First tool call is `diff_interface_contracts`. Validates breaking API and export changes before pull requests.
4. `onboarding-navigator`: First tool call is `get_ranked_reading_path`. Generates a prioritized reading itinerary.
5. `dead-code-surgeon`: First tool call is `find_unreachable_symbols`. Identifies unreferenced code candidates.

### Skill Invocation Notes
- **Claude Code**: Reads skills installed at `.claude/skills/<id>/SKILL.md`.
- **Antigravity**: Reads skills installed at `.agents/skills/<id>/SKILL.md`.
- **OpenCode**: Reads skills from both directories. Invocation in OpenCode is explicit via its skill tool; RepoScope does not claim automatic metadata-only invocation.

---

## 7. What Changed in Phase 4

Phase 4 preserved the existing 8 MCP tools and 5 resources while adding:
- **5 New Tools**: `get_mindmap_hierarchy`, `get_ast_skeleton`, `get_context_pack`, `diff_interface_contracts`, `get_ranked_reading_path`.
- **3 New Resources**: `reposcope://mindmap`, `reposcope://api-routes`, `reposcope://context-pack`.
- **Delta Sync**: `since_hash` support with content-hashed unchanged envelopes.
- **Optional TOON Adapter**: Lazily loaded, opt-in format with a ~39% measured token reduction.
