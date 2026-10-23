# Knowledge graph schema

RepoScope stores one graph in `.reposcope/graph.json`. The canvas, MCP server,
and extension read that snapshot. There is no separate “MCP index” or
“extension index”.

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

## Edge types

| Type | Source → target | Meaning |
|---|---|---|
| `contains` | file → function/class | The file defines the symbol |
| `imports` | file → file | A resolved import |
| `calls` | function/method → function/method | A resolved static call |

No `extends`, `part_of`, or GitHub metadata edges are stored in the code graph.
Tracking data lives in `data/repo_state.json`, not in `.reposcope/graph.json`.

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
- **Cycles**: strongly connected components over `imports`.
- **Unreachable symbols**: static reachability from entry points.
- **Hotspots**: centrality combined with git churn.
- **Blast radius**: reverse BFS over `imports`/`calls`.

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
