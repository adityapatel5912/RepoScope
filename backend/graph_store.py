"""
graph_store.py
The GraphStore abstraction — one index, three front-ends.

Correction C11 (pulled forward from Milestone 6): the original v2.0
architecture drew the MCP server as a separate box pointing at the core
engine, which would have produced three independent implementations of
"parse the repo". The stronger design is a single persisted index that the
web app, the local CLI daemon, and the MCP server all read from.

    GraphStore
       ├── Web App      (REST / SSE)
       ├── CLI Daemon   (localhost)
       └── MCP Server   (stdio / Streamable HTTP)

The graph shape is byte-compatible with `graph_builder.build_graph_from_repo()`:
    file nodes  {id, type, label, language, size}
    symbol nodes{id, type, label, file, line}
    ids         file:{rel}  func:{rel}:{name}  class:{rel}:{name}
    edges       {source, target, type}  type in {contains, imports, calls}

Correction C10: those shapes are load-bearing. `pr_impact.py`,
`graph_utils.find_node_by_label`, the pyramid ranking, and the frontend's
`calls` filter all depend on them, so the golden test in
backend/tests/test_graph_golden.py enforces them.

This module ships the JSON implementation. The SQLite implementation lands
in Milestone 6 (`SqliteGraphStore`) behind the same interface.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

log = logging.getLogger("reposcope.graph_store")

#: Where a store writes by default, relative to the repository root.
DEFAULT_DIRNAME = ".reposcope"
DEFAULT_FILENAME = "graph.json"

#: The schema version written into the store's metadata block.
SCHEMA_VERSION = 1

#: Edge types the graph may contain. `calls` is already accepted by the
#: frontend renderer (frontend/src/components/GraphView.tsx:174).
VALID_EDGE_TYPES = frozenset({"contains", "imports", "calls"})

#: Node types the graph may contain.
VALID_NODE_TYPES = frozenset({
    "file", "function", "class", "folder", "cluster",
    "root", "repo", "import", "commit",
})


@runtime_checkable
class GraphStore(Protocol):
    """
    The interface every front-end reads the indexed graph through.
    """

    def load(self) -> dict:
        """Return the persisted graph, or an empty graph if none exists."""
        ...

    def save(self, graph: dict) -> None:
        """Persist a graph."""
        ...

    def stats(self) -> dict:
        """Return summary counters for the stored graph."""
        ...

    def exists(self) -> bool:
        """True when a graph has been persisted."""
        ...


def empty_graph() -> dict:
    """The canonical empty graph."""
    return {"nodes": [], "edges": [], "summary": "0 nodes, 0 edges"}


def graph_summary(graph: dict) -> str:
    """Build the same summary string graph_builder produces."""
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    return f"{len(nodes)} nodes, {len(edges)} edges"


def validate_graph(graph: dict) -> list[str]:
    """
    Return a list of structural problems with a graph.

    An empty list means the graph satisfies the C10 contract. This is
    deliberately permissive about extra keys — the graph is allowed to grow
    new attributes — but strict about the load-bearing ones.
    """
    problems: list[str] = []

    if not isinstance(graph, dict):
        return ["graph is not a dictionary"]

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list):
        problems.append("'nodes' must be a list")
    if not isinstance(edges, list):
        problems.append("'edges' must be a list")
    if problems:
        return problems

    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            problems.append(f"nodes[{index}] is not a dictionary")
            continue
        node_id = node.get("id")
        if not node_id:
            problems.append(f"nodes[{index}] has no 'id'")
            continue
        if not isinstance(node_id, str):
            problems.append(f"nodes[{index}].id is not a string")
            continue
        if node_id in node_ids:
            problems.append(f"duplicate node id: {node_id}")
        node_ids.add(node_id)
        node_type = node.get("type")
        if node_type and node_type not in VALID_NODE_TYPES:
            problems.append(f"unknown node type '{node_type}' on {node_id}")
        if not node.get("label"):
            problems.append(f"node {node_id} has no 'label'")

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            problems.append(f"edges[{index}] is not a dictionary")
            continue
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type")
        if not source or not target:
            problems.append(f"edges[{index}] is missing source or target")
            continue
        if edge_type and edge_type not in VALID_EDGE_TYPES:
            problems.append(f"unknown edge type '{edge_type}' on edge {index}")
        if source not in node_ids:
            problems.append(f"edges[{index}] references unknown source '{source}'")
        if target not in node_ids:
            problems.append(f"edges[{index}] references unknown target '{target}'")

    return problems


def default_store_path(repo_root: str | Path | None = None) -> Path:
    """Where the graph index lives for a given repository root."""
    if repo_root:
        return Path(repo_root) / DEFAULT_DIRNAME / DEFAULT_FILENAME
    return Path(tempfile.gettempdir()) / "reposcope" / DEFAULT_FILENAME


class JsonGraphStore:
    """
    The default GraphStore: a single JSON file on disk.

    Chosen over an embedded graph database for Sprint 0 because it is
    zero-risk, human-inspectable, and git-ignorable. `SqliteGraphStore`
    lands in Milestone 6 behind the same interface.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_store_path()

    # ── GraphStore interface ───────────────────────────────────────────────

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict:
        if not self.exists():
            return empty_graph()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not read graph store %s: %s", self.path, exc)
            return empty_graph()
        return self._unwrap(raw)

    def save(self, graph: dict) -> None:
        problems = validate_graph(graph)
        if problems:
            raise ValueError(
                "graph does not satisfy the node/edge contract:\n  "
                + "\n  ".join(problems)
            )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "summary": graph.get("summary") or graph_summary(graph),
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def stats(self) -> dict:
        graph = self.load()
        nodes = graph.get("nodes", []) or []
        edges = graph.get("edges", []) or []

        node_types: dict[str, int] = {}
        for node in nodes:
            node_type = str(node.get("type", "unknown"))
            node_types[node_type] = node_types.get(node_type, 0) + 1

        edge_types: dict[str, int] = {}
        for edge in edges:
            edge_type = str(edge.get("type", "unknown"))
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

        return {
            "path": str(self.path),
            "exists": self.exists(),
            "schema_version": SCHEMA_VERSION,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_types": node_types,
            "edge_types": edge_types,
            "summary": graph.get("summary") or graph_summary(graph),
        }

    # ── Internals ──────────────────────────────────────────────────────────

    @staticmethod
    def _unwrap(raw: Any) -> dict:
        """Accept both the wrapped payload and a bare graph."""
        if not isinstance(raw, dict):
            return empty_graph()
        if "nodes" in raw or "edges" in raw:
            return {
                "nodes": raw.get("nodes", []) or [],
                "edges": raw.get("edges", []) or [],
                "summary": raw.get("summary") or graph_summary(raw),
            }
        return empty_graph()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"JsonGraphStore(path={str(self.path)!r})"
