# RepoScope HTTP API

This is the reference for the HTTP surface that the canvas, the CLI, and the
VS Code extension read. The API is JSON-first. Chat and local re-index updates
use Server-Sent Events.

The working schema is **graph schema v2** (package **2.0.0**). Schema v1
graphs are still accepted by the store; see [Version policy](#version-policy).

The running application also exposes FastAPI's generated OpenAPI document at
`/openapi.json` and its interactive UI at `/docs`. This page documents the
contracts that clients depend on, not every request model.

## Conventions

- Base URL in local mode: `http://127.0.0.1:4100`.
- Base URL for the hosted API: the deployment URL, normally
  `https://reposcope-api.onrender.com`.
- Every response carries `X-Request-Id`. Security headers are added globally.
- Errors are JSON. A stack trace is never returned to a client.
- No endpoint returns provider keys or repository tokens.
- Endpoints that read the graph use the **active repository** only. There is
  no hidden second index.

---

## Core endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Minimal liveness probe. Returns `{"status": "ok"}`. |
| `GET` | `/api/health` | Application health, version, schema version, cached graph counts. |
| `GET` | `/api/repo/graph` | The full graph for the active repository. |
| `GET` | `/api/mindmap` | The frozen six-pillar mind-map projection. |
| `GET` | `/api/harness/agents` | The nine supported agent targets and their paths. |
| `GET` | `/api/harness/config` | Preview the files and command for one agent. |
| `POST` | `/api/harness/apply` | Dry run by default; write only when the server flag allows it. |
| `GET` | `/api/harness/skills` | The five skill descriptors. Bodies are Phase 4. |
| `POST` | `/api/repo/load` | Clone and index a GitHub repository. |
| `POST` | `/api/repo/load-demo/{demo_id}` | Load a bundled demo repository. |
| `GET` | `/api/repo/status` | Current repository state. |
| `GET` | `/api/repo/check` | Poll GitHub for changes. |
| `GET` | `/api/repo/file` | File content for the viewer. |
| `GET` | `/api/repo/demos` | Available demo repositories. |
| `POST` | `/api/chat/stream` | SSE answer with citations. |
| `POST` | `/api/impact/analyze` | Blast radius and impact narrative. |
| `POST` | `/api/onboard` | Student Mode path, quizzes, and Good First Issues. |

Analysis routers live under `/api/analysis` and `/api/arch`; local mode uses
`/api/local/*`. See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete route
map and the routers' source for request models.

---

## `GET /api/health`

A health check must never trigger a clone or a full parse. The response
reports what the process already knows.

```json
{
  "status": "healthy",
  "service": "reposcope-api",
  "version": "2.0.0",
  "schema_version": 2,
  "graph": {"loaded": true, "nodes": 1863, "edges": 3419},
  "uptime_seconds": 42,
  "uptime_human": "0h 0m",
  "memory_mb": 118.4,
  "timestamp": "2026-10-26T12:00:00Z",
  "checks": {
    "openrouter_keys": 1,
    "groq_keys": 0,
    "nvidia_keys": 0,
    "github_keys": 1
  }
}
```

`schema_version` is the version the **server writes** (`2`). `graph.loaded`
is `false` and both counts are `0` when no graph is cached. The `checks`
object contains counts only; it never contains key material.

`GET /health` remains the tiny liveness probe and returns `{"status": "ok"}`.

---

## `GET /api/repo/graph`

Returns the graph for the active repository. The response is the graph object
described in [Graph schema v2](#graph-schema-v2), not a wrapper.

If no repository has ever been loaded, the endpoint returns an empty graph
with the v2 fields present. The canvas is responsible for an empty state.

---

## `GET /api/mindmap`

The frozen contract for Phase 2 of V2.5. This endpoint is read-only and
deterministic; the only field that changes between identical calls is
`generated_at`.

```
GET /api/mindmap?include_symbols=true&max_nodes=20000
```

### Query parameters

| Name | Type | Default | Rules |
|---|---|---|---|
| `include_symbols` | boolean | `true` | When `false`, the tree stops at files and `stats.symbols` still reports the full symbol count. |
| `max_nodes` | integer | `20000` | `1` to `200000`. The cap is applied to the returned tree. |

### Response fields

| Field | Meaning |
|---|---|
| `schema_version` | Graph schema version used to build the payload (`2`). |
| `generated_at` | UTC ISO-8601 timestamp ending in `Z`. |
| `source.nodes` | Node count of the graph the projection read. |
| `source.edges` | Edge count of the graph the projection read. |
| `source.root` | Absolute local repository path, or `null`. |
| `stats.files` | File nodes in the graph. |
| `stats.symbols` | Function and class nodes in the graph. |
| `stats.pillars` | Always `6`. |
| `stats.routes` | Declared HTTP/WebSocket routes. |
| `stats.api_calls` | Resolved cross-stack `api_calls` edges. |
| `pillars` | Fixed-order pillar descriptors with a `file_count`. |
| `root` | The tree root described below. |
| `truncated` | `true` when at least one node was left out by `max_nodes`. |
| `omitted` | Number of nodes left out. `0` when not truncated. |
| `max_nodes` | The effective cap used for this response. |

### Tree shape

The hierarchy is strict:

```
root → pillar → folder → file → symbol
```

Only the six pillars are direct children of the root. Folders may nest. A file
is always a child of a pillar or folder. Symbols are children of their file.

Common node fields:

| Field | Present on | Meaning |
|---|---|---|
| `id` | every node | Stable node id. File and symbol ids are the graph ids. |
| `kind` | every node | `root`, `pillar`, `folder`, `file`, or `symbol`. |
| `label` | every node | Display name. |
| `parent_id` | every node except root | Parent id, or `null` for the root. |
| `children` | every node | Child nodes; always an array, possibly empty. |

Kind-specific fields:

| Field | Present on | Meaning |
|---|---|---|
| `pillar` | pillar, file | Pillar id: `frontend`, `backend`, `data`, `infrastructure`, `tests`, or `docs`. |
| `description` | pillar | Human-readable pillar description. |
| `metrics` | pillar | `{files, symbols, routes}` for the whole repository, not the pruned tree. |
| `path` | folder, file, symbol | Repository-relative path. |
| `line` | file, symbol | 1-based source line. Files use `1`. |
| `end_line` | symbol | 1-based end line. |
| `role` | file, symbol | Server-classified role; never invented by the client. |
| `language` | file | `py`, `ts`, `tsx`, `js`, `go`, `rs`, or empty. |
| `pagerank` | file | PageRank score when analysis ran. |
| `route_count` | file, symbol | Number of routes attached to the file or handler. |

Folder ids are `folder:<pillar>:<repo-relative-folder-path>`, for example
`folder:backend:backend/api/routers`. Every directory level is a folder. A
top-level directory that names the pillar is not repeated as a separate level,
but the full repository-relative path stays in the folder's `path`.

Roles currently include `entry_point`, `api_controller`, `service`,
`repository`, `model`, `utility`, `ui_component`, `hook`, `test`, `docs`, and
`config`.

### Ordering and pruning

The tree is built in this order:

1. root;
2. the six pillars in fixed order (`frontend`, `backend`, `data`,
   `infrastructure`, `tests`, `docs`);
3. folders, shallow to deep, by path inside each pillar;
4. files, by repository-relative path inside each pillar;
5. symbols, by line, inside each file.

`max_nodes` keeps a node only when its parent is already kept. A capped tree
therefore remains a valid tree; it never contains an orphan. A client must
show `truncated: true` rather than presenting the capped tree as complete.

A file in a pillar root directory is not given a redundant folder level:
`backend/api/routers/x.py` appears under the backend pillar at
`backend/api/routers`, not under an additional `backend` folder.

### Status codes

| Status | Meaning |
|---|---|
| `200` | Success. An active repository with an empty graph is still `200` and returns a root with six empty pillars. |
| `422` | `max_nodes` is outside `1..200000`, or a query value cannot be parsed. |
| `503` | No repository is active (`current_graph()` has neither nodes nor a root). |

### Example

```json
{
  "schema_version": 2,
  "generated_at": "2026-10-26T12:00:00Z",
  "source": {"nodes": 19, "edges": 18, "root": "/work/v2_contract"},
  "stats": {
    "files": 9,
    "symbols": 10,
    "pillars": 6,
    "routes": 3,
    "api_calls": 2
  },
  "pillars": [
    {
      "id": "frontend",
      "label": "Frontend & UI",
      "description": "Browser and editor clients, components, hooks, and styles.",
      "file_count": 4
    }
  ],
  "root": {
    "id": "root",
    "kind": "root",
    "label": "RepoScope",
    "parent_id": null,
    "children": [
      {
        "id": "pillar:backend",
        "kind": "pillar",
        "label": "Backend & Core",
        "pillar": "backend",
        "parent_id": "root",
        "description": "Servers, ingestion, graph analysis, and domain logic.",
        "metrics": {"files": 4, "symbols": 7, "routes": 3},
        "children": [
          {
            "id": "file:server.py",
            "kind": "file",
            "label": "server.py",
            "path": "server.py",
            "line": 1,
            "role": "entry_point",
            "pillar": "backend",
            "language": "py",
            "route_count": 3,
            "parent_id": "pillar:backend",
            "children": [
              {
                "id": "func:server.py:health",
                "kind": "symbol",
                "label": "health",
                "path": "server.py",
                "line": 8,
                "end_line": 9,
                "role": "api_controller",
                "route_count": 1,
                "parent_id": "file:server.py",
                "children": []
              }
            ]
          }
        ]
      }
    ]
  },
  "truncated": false,
  "omitted": 0,
  "max_nodes": 20000
}
```

The example is shortened to one branch. The complete response always has all
six `pillars` entries, even when a pillar has no files.

### Contract rules for clients

- Never classify a file in the browser. Use the server's `pillar` and `role`.
- Never build the hierarchy from `/api/repo/graph`.
- Never infer a symbol's parent from its name. Use `parent_id`.
- Treat an empty pillar as valid, not an error.
- Do not cache a payload across a repository change.

---

## Harness configurator (Phase 3)

Generate exact MCP configuration for nine agents, preview every file and
command, and write only when the server operator has enabled writes.

The nine targets are `claude`, `cursor`, `vscode`, `codex`, `kiro`,
`antigravity`, `windsurf`, `cline`, and `opencode`. Each target supports
`stdio` (the default) and Streamable HTTP. The HTTP endpoint is
`http://127.0.0.1:8765/mcp` unless `REPOSCOPE_MCP_HTTP_URL` overrides it.

**Safety contract**

- Preview reads files; it never writes and never calls the network.
- `apply: true` is refused with `403` unless `REPOSCOPE_HARNESS_APPLY=1`.
- An existing file that would change requires `force: true`; otherwise the
  request is refused with `409` and nothing is written.
- Every config path is project-relative. An absolute path, `..`, or a symlink
  or junction that resolves outside the repository root is rejected with
  `400`.
- Global paths (for example `~/.codeium/windsurf/mcp_config.json`) are
  display-only and are never written.
- JSON and TOML files are merged: unrelated keys and servers survive.
  Markdown instruction files get one delimited RepoScope section.
- Writes are atomic: a temporary file in the target directory, then replace.

### `GET /api/harness/agents`

Returns the registry and the server's write flag.

```json
{
  "agents": [
    {
      "id": "claude",
      "label": "Claude Code",
      "config_paths": [".mcp.json", "CLAUDE.md"],
      "transport": ["stdio", "http"],
      "default_transport": "stdio",
      "global_preview_paths": [],
      "docs_url": "https://docs.claude.com/en/docs/claude-code/mcp",
      "verified_at": "2026-10-26",
      "notes": ["Project scope is .mcp.json; the CLI needs --scope project."]
    }
  ],
  "apply_enabled": false
}
```

`config_paths` are repository-relative. `global_preview_paths` are shown to
the user but are never written. `apply_enabled` reflects the server
environment, not a client preference.

### `GET /api/harness/config`

```
GET /api/harness/config?agent=claude&transport=stdio&root=D:\repo
```

`root` is optional only when an active local repository supplies one. It must
be an existing absolute directory; a relative path is never interpreted
against the server's current directory.

The response is a preview:

```json
{
  "ok": true,
  "agent": "claude",
  "label": "Claude Code",
  "transport": "stdio",
  "root": "D:\\repo",
  "command": "claude mcp add --scope project --transport stdio reposcope -- reposcope-mcp --root D:\\repo",
  "command_kind": "install",
  "command_note": "Writes the project-scoped .mcp.json. Review the diff before running it.",
  "apply_enabled": false,
  "requires_force": false,
  "files": [
    {
      "path": ".mcp.json",
      "format": "json",
      "content": "{...}\n",
      "exists": false,
      "diff": null,
      "will_write": true
    }
  ],
  "warnings": []
}
```

- `format` is `json`, `toml`, or `markdown`.
- `content` is the exact text that would be written.
- `exists` is whether the target file is present.
- `diff` is a unified diff when an existing file would change; otherwise
  `null`.
- `will_write` is false for an identical file.
- `requires_force` is true when any existing file would change.
- `warnings` reports unparseable files, lost TOML comments, legacy OpenCode
  keys, and display-only global paths.

### `POST /api/harness/apply`

```json
{
  "agent": "claude",
  "transport": "stdio",
  "root": "D:\\repo",
  "apply": false,
  "force": false
}
```

`apply: false` is a dry run and writes nothing. When `apply: true` is allowed,
the response is the preview shape plus:

```json
{
  "apply": true,
  "applied": [".mcp.json", "CLAUDE.md"],
  "unchanged": []
}
```

| Status | Meaning |
|---|---|
| `400` | Unknown agent, unsupported transport, invalid root, or unsafe path. |
| `403` | `apply: true` while `REPOSCOPE_HARNESS_APPLY` is not `1`. |
| `409` | An existing file would change and `force` is false. |
| `422` | The request body is missing a required field. |

### `GET /api/harness/skills`

Returns the five skill descriptors with `content_available: false`. Phase 3
shows what will be available; it does not write `SKILL.md` bodies, and it does
not expose `.agents/skills/*` files. Those are Phase 4 work.

### Registry deltas from Appendix E

- **OpenCode** uses `mcp.<name>` with `type: local | remote`. There is no
  `mcp.servers` key in the current schema.
- **Windsurf/Devin** project configuration lives at
  `.devin/mcp_config.json`; the legacy Cascade global path is display-only.
- **Cline/Roo** writes Roo Code's project file `.roo/mcp.json`. Cline's global
  settings path `~/.cline/data/settings/cline_mcp_settings.json` is
  display-only.
- **Antigravity** skills belong to Phase 4. Phase 3 writes only
  `.agents/mcp_config.json`.

---

## Graph schema v2

The graph is persisted at `.reposcope/graph.json` and returned by
`/api/repo/graph`. Schema v2 is **additive** to v1.

### Top level

```json
{
  "schema_version": 2,
  "summary": "19 nodes, 18 edges",
  "nodes": [],
  "edges": [],
  "metadata": {
    "builder": "graph_builder",
    "capabilities": ["roles", "pillars", "routes", "api_calls", "inherits", "exports"]
  },
  "api_routes": []
}
```

### Nodes

The v1 ids, types, and required fields are unchanged:

| Type | Id | Required fields |
|---|---|---|
| file | `file:<rel-path>` | `id`, `type`, `label`, `language`, `size` |
| function | `func:<rel-path>:<name>` | `id`, `type`, `label`, `file`, `line` |
| class | `class:<rel-path>:<name>` | `id`, `type`, `label`, `file`, `line` |

Schema v2 adds optional fields:

| Field | On | Meaning |
|---|---|---|
| `path` | file, symbol | Repository-relative path. |
| `pillar` | file, symbol | One of the six pillar ids. |
| `role` | file, symbol | Deterministic role. |
| `route_count` | file, symbol | Number of routes the file or handler declares. |
| `routes` | symbol | The handler's routes as `{method, path, line}`. |
| `end_line` | symbol | Last source line of the symbol. |
| `pagerank`, `in_degree`, `out_degree`, `betweenness` | where analysis ran | Existing analysis fields. |

Node ids are load-bearing. v2 does not rename or re-mint them.

### Edges

| Type | Source → target | Meaning | Evidence |
|---|---|---|---|
| `contains` | file → function/class | The file defines the symbol. | Optional |
| `imports` | file → file | A resolved import. | Optional |
| `calls` | function/method → function/method | A resolved static call. | Optional |
| `inherits` | class → class | A resolvable base class or implemented interface. | Required |
| `exports` | file → file | A barrel/re-exporting file re-exports from the target. | Required |
| `api_calls` | caller symbol (or file) → handler symbol (or file) | A client call that resolves to a declared route. | Required |

v2 edges carry:

```json
{
  "source": "func:client.ts:fetchHealth",
  "target": "func:server.py:health",
  "type": "api_calls",
  "evidence": {
    "kind": "http_call",
    "file": "client.ts",
    "line": 2,
    "method": "GET",
    "path": "/api/health",
    "route": "/api/health",
    "confidence": 1.0
  }
}
```

Evidence rules:

- `file` is repository-relative.
- `line` is 1-based.
- `confidence` is a number in `[0, 1]`.
- A resolver that cannot identify exactly one target leaves the edge out.
- A v2 edge must reference known nodes.
- `contains`, `imports`, and `calls` may omit evidence so an old v1 graph
  remains readable.

### Routes

`api_routes` is the graph-level route table:

```json
{
  "method": "GET",
  "path": "/api/health",
  "file": "server.py",
  "line": 8,
  "handler": "health",
  "node_id": "func:server.py:health"
}
```

`method` is uppercase, or `WS` for a WebSocket route. `node_id` always points
at a real node; when the handler cannot be resolved, the route is attributed
to the file node.

### Version policy

- The builder writes `schema_version: 2`.
- `JsonGraphStore.load()` accepts a wrapped v1 or v2 payload and a bare graph.
- A v1 graph loaded and re-saved without enrichment is recorded as v1, not
  silently relabeled v2.
- `JsonGraphStore.stats()` reports the stored schema version.
- `metadata` and `api_routes` survive a JSON and SQLite round trip.
- A v1 reader may ignore additive node fields and should ignore unknown edge
  types.

### Determinism and failure behaviour

The graph is derived from source bytes, not an LLM. Scanners are conservative:
a missing edge is preferred to a guessed one. The graph reports parser
warnings rather than failing the whole build for one bad file. Analysis
(PageRank and related fields) is attached best-effort; a failure there never
prevents the graph from being returned.

The golden test pins the v1 node set and the v1 edge subset. New v2 edges are
validated separately, so a snapshot can never hide a v1 drift.
