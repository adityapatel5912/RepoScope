# Knowledge graph schema

RepoScope stores one graph in `.reposcope/graph.json`. The canvas, MCP server,
and extension read that snapshot. There is no separate “MCP index” or
“extension index”.

The builder writes **schema v2**. Schema v2 is additive: every v1 node id,
edge direction, and edge meaning is unchanged, and a v1 graph still loads.
The additions are evidence-bearing dependency edges, route metadata, and
node roles/pillars.

## Node types

| Type | Id | Example | Notes |
|---|---|---|---|
| `file` | `file:<rel-path>` | `file:backend/graph_store.py` | Every indexed file |
| `function` | `func:<rel-path>:<name>` | `func:backend/graph_store.py:load` | Functions and methods |
| `class` | `class:<rel-path>:<name>` | `class:backend/graph_store.py:GraphStore` | Classes |
| virtual root | `repo:root` | `repo:root` | Canvas-only root node |

The backend stores only `file`, `function`, and `class` nodes. `repo:root` is
added by the canvas so the pyramid has a top.

Node fields include `label`, `language`, `size`, `sha256`, `pagerank`,
`in_degree`, `out_degree`, and `betweenness` where applicable.

Schema v2 adds optional `path`, `pillar`, `role`, `route_count`, `routes`
(handlers only), and `end_line` (symbols only). `pillar` is one of
`frontend`, `backend`, `data`, `infrastructure`, `tests`, or `docs`. `role` is
a deterministic classification such as `entry_point`, `api_controller`,
`service`, `repository`, `model`, `utility`, `ui_component`, `hook`, `test`,
`docs`, or `config`.

## Edge types

| Type | Source → target | Meaning |
|---|---|---|
| `contains` | file → function/class | The file defines the symbol |
| `imports` | file → file | A resolved import |
| `calls` | function/method → function/method | A resolved static call |
| `inherits` | class → class | A resolvable base class or implemented interface |
| `exports` | file → file | A barrel/re-exporting file re-exports from the target |
| `api_calls` | caller symbol or file → handler symbol or file | A client call that resolves to a declared route |

`inherits`, `exports`, and `api_calls` always carry an `evidence` object:
repository-relative `file`, 1-based `line`, and `confidence` in `[0, 1]`.
The three v1 edge types may omit evidence so an old graph stays readable. No
v2 edge may reference an unknown node. Ambiguous targets are omitted rather
than guessed.

`contains` is membership, not a dependency. The dependency-aware analyses
exclude it; `imports`, `calls`, `inherits`, `exports`, and `api_calls` are the
dependency edge types.

## Routes

The graph carries a top-level `api_routes` table. Each entry names the method
(`GET`, `POST`, …, or `WS`), path, declaring file, line, handler name, and the
handler's node id. Handler nodes also carry their own `routes` list. A route
whose handler cannot be resolved is attributed to its file node.

## Import resolution

Imports are resolved through a module-name index:

- absolute Python imports (`from backend.engine import decision_model`);
- relative Python imports (`from .db import get_db`);
- TypeScript/JavaScript relative imports and aliases (`@/components/x`);
- Go and Rust imports where the parser can map them.

An unresolved import remains a file-level relationship only if a target can be
identified; otherwise it is omitted and reported as a warning by the builder.

## Call resolution

Call sites become `calls` edges when the target can be resolved statically:

- same-file functions;
- imported symbols;
- methods on a known class;
- qualified names.

Dynamic dispatch, reflection, decorators that replace functions, and generated
code can produce false negatives. The graph is an estimate, not a proof.

## Analysis fields

- **PageRank**: centrality used for ranking and the repo map.
- **In/out degree**: direct dependency counts.
- **Betweenness**: optional bridge score.
- **Cycles**: strongly connected components over the dependency edges.
- **Unreachable symbols**: static reachability from entry points.
- **Hotspots**: centrality combined with git churn.
- **Blast radius**: reverse BFS over the graph's edges.

## Rendering rules

- **Small repository:** draw the full connectivity pyramid (`file` and symbol
  nodes), with rank rows.
- **Large repository:** group top-level modules into cards. The full nodes are
  still in the snapshot; the drawer lists every file in a card.
- **Architecture cluster mode:** group by layer (Client/UI, Backend/API,
  Storage/Data, External/Integrations, Compute/Workers).
- **Flat mode:** every file node is rendered; use it for inspection, not for a
  first read of a large repository.
- **Edges:** parent bottom (`out`) → child top (`in`); grouped views collapse
  endpoints to their module card.
- **No fixed 100-node cap.** The canvas chooses a grouped or flat rendering
  based on size, and renders only visible elements.

## Stable ids and duplicates

The builder deduplicates symbol ids. Duplicate `func:<path>:<name>` entries
(e.g., overloads or nested definitions) are disambiguated so React keys and
graph lookups stay unique. If you change the id scheme, update the golden tests
and the extension's parser together.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) and
[`FEATURES.md`](FEATURES.md).
