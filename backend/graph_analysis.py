"""
graph_analysis.py
Graph algorithms over RepoScope's dependency graph.

Milestone 7.1 — PageRank centrality.
  RepoScope ranks files with `incoming x 2 + outgoing`, a naive degree
  heuristic. `aider` established PageRank on the symbol graph as the right
  primitive for "which files matter", and `codegraph` uses centrality to
  build its repo map. PageRank is therefore the engine behind:
    - the pyramid's row assignment
    - the hotspot score
    - the student onboarding curriculum
    - the repo map (M8.1) and its token-reduction number
    - the "top central hubs" MCP resource

Milestone 7.3 — Cycle detection.
  The v2.0 architecture diagram promised "Cyclic Dep Detection" but no
  milestone implemented it. Madge and dependency-cruiser exist solely for
  this. Cycles are computed with Tarjan's SCC via networkx.

networkx 3.6.1 is installed. Two verified constraints:
  - `nx.strongly_connected_components` raises NetworkXNotImplemented on an
    undirected Graph. Everything here uses nx.DiGraph.
  - `nx.community.leiden_communities` raises NotImplementedError without
    the optional `leidenalg` backend, so Louvain is used instead.
"""
from __future__ import annotations

import logging
from typing import Iterable

import networkx as nx

log = logging.getLogger("reposcope.graph_analysis")

#: Edge types that represent a real dependency for traversal purposes.
DEPENDENCY_EDGE_TYPES = frozenset({"imports", "calls"})


def build_digraph(
    graph: dict,
    edge_types: Iterable[str] | None = None,
    include_isolated: bool = True,
) -> nx.DiGraph:
    """
    Build a directed graph from RepoScope's graph dict.

    Only dependency edges (imports / calls) are included by default — the
    `contains` edges are file-to-symbol membership, not dependency, and
    including them would make every symbol look like a hub.
    """
    allowed = set(edge_types) if edge_types is not None else set(DEPENDENCY_EDGE_TYPES)

    digraph = nx.DiGraph()
    for node in graph.get("nodes", []) or []:
        node_id = node.get("id")
        if node_id:
            digraph.add_node(node_id, **{k: v for k, v in node.items() if k != "id"})

    for edge in graph.get("edges", []) or []:
        edge_type = edge.get("type")
        if edge_type not in allowed:
            continue
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        if source not in digraph or target not in digraph:
            continue
        digraph.add_edge(source, target, type=edge_type)

    if not include_isolated:
        digraph.remove_nodes_from(list(nx.isolates(digraph)))

    return digraph


def pagerank_scores(
    graph: dict,
    damping: float = 0.85,
    max_iter: int = 200,
    tolerance: float = 1.0e-6,
) -> dict[str, float]:
    """
    PageRank centrality for every node in the graph.

    Returns a mapping of node id -> score. Scores sum to 1.0.

    Deterministic: networkx's PageRank uses a fixed starting vector, so
    the same graph always produces the same scores. That matters because
    these scores drive the pyramid layout, the CI risk gate, and the MCP
    tools — non-determinism would make them untrustworthy.
    """
    digraph = build_digraph(graph)
    if digraph.number_of_nodes() == 0:
        return {}
    try:
        scores = nx.pagerank(
            digraph,
            alpha=damping,
            max_iter=max_iter,
            tol=tolerance,
            weight=None,
        )
    except nx.PowerIterationFailedConvergence:
        log.warning("PageRank did not converge — falling back to degree heuristic")
        return _degree_fallback(digraph)
    return {node_id: float(score) for node_id, score in scores.items()}


def _degree_fallback(digraph: nx.DiGraph) -> dict[str, float]:
    """
    Degree-based fallback used only when PageRank fails to converge.

    Deliberately close to the old heuristic so the pyramid does not jump
    around when the fallback engages.
    """
    total = digraph.number_of_nodes()
    if total == 0:
        return {}
    scores: dict[str, float] = {}
    for node_id in digraph.nodes:
        in_degree = digraph.in_degree(node_id)
        out_degree = digraph.out_degree(node_id)
        scores[node_id] = ((in_degree * 2) + out_degree) / (total * 4)
    return scores


def betweenness_centrality(graph: dict) -> dict[str, float]:
    """
    Betweenness centrality — nodes that sit on the critical path between
    other nodes. Useful for identifying "choke points" in a codebase.
    """
    digraph = build_digraph(graph)
    if digraph.number_of_nodes() == 0:
        return {}
    return {
        node_id: float(score)
        for node_id, score in nx.betweenness_centrality(digraph).items()
    }


def degree_scores(graph: dict) -> dict[str, tuple[int, int]]:
    """(in_degree, out_degree) for every node."""
    digraph = build_digraph(graph)
    return {
        node_id: (int(digraph.in_degree(node_id)), int(digraph.out_degree(node_id)))
        for node_id in digraph.nodes
    }


def find_cycles(graph: dict, min_length: int = 2) -> list[list[str]]:
    """
    Find dependency cycles using Tarjan's strongly-connected components.

    A cycle is a strongly connected component with more than one node, or a
    single node with a self-loop. Components are returned in a stable order
    so the output is reproducible.

    `min_length` applies to multi-node cycles only. Self-loops are always
    reported — a file that imports itself is a genuine defect, and it is
    length 1 by definition.
    """
    digraph = build_digraph(graph)
    cycles: list[list[str]] = []
    self_loops: list[list[str]] = []
    for component in nx.strongly_connected_components(digraph):
        if len(component) > 1:
            cycles.append(sorted(component))
        else:
            only = next(iter(component))
            if digraph.has_edge(only, only):
                self_loops.append([only])

    cycles = [c for c in cycles if len(c) >= min_length]
    cycles.sort(key=lambda c: (len(c), c))
    self_loops.sort()
    return cycles + self_loops


def cycle_details(graph: dict) -> list[dict]:
    """
    Cycles enriched with the layers they span.

    A cycle that crosses layers (e.g. storage -> client) is an
    architecture violation; a cycle inside a single layer is a code smell.
    The distinction is what makes a cycle actionable rather than noise.
    """
    from arch_rules import classify

    nodes_by_id = {n["id"]: n for n in graph.get("nodes", []) or []}
    details: list[dict] = []
    for cycle in find_cycles(graph):
        members = [nodes_by_id[n] for n in cycle if n in nodes_by_id]
        layers = sorted({
            classify(str(m.get("id", "")), str(m.get("label", ""))) for m in members
        })
        details.append({
            "length": len(cycle),
            "members": cycle,
            "layers": layers,
            "crosses_layers": len(layers) > 1,
            "severity": "error" if len(layers) > 1 else "warning",
        })
    return details


def entry_points(graph: dict) -> list[str]:
    """
    Entry points — the roots for reachability analysis.

    A node qualifies when it has NO incoming dependency edges but DOES
    lead somewhere (out-degree > 0), or when it uses a conventional entry
    filename.

    The out-degree condition matters. Treating every in-degree-0 node as an
    entry point makes every isolated module an entry point, which would
    make the unreachable set permanently empty and the dead-code detection
    worthless. An isolated module is a leaf that nothing reaches — that is
    precisely the thing worth reporting.
    """
    digraph = build_digraph(graph)
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", []) or []}

    conventional = {
        "main.py", "__main__.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
        "index.ts", "index.tsx", "index.js", "index.jsx", "main.ts", "main.tsx",
        "main.go", "main.rs", "server.ts", "server.js", "app.ts", "app.tsx",
    }

    entries: list[str] = []
    for node_id in digraph.nodes:
        if digraph.in_degree(node_id) == 0 and digraph.out_degree(node_id) > 0:
            entries.append(node_id)
            continue
        node = nodes_by_id.get(node_id, {})
        label = str(node.get("label", ""))
        basename = label.rsplit("/", 1)[-1]
        if basename in conventional:
            entries.append(node_id)
    return sorted(set(entries))


def unreachable_nodes(graph: dict) -> list[str]:
    """
    Nodes that cannot be reached from any entry point.

    This is a STATIC ESTIMATE, not proof of dead code — dynamic dispatch,
    reflection, and plugin registration are invisible to static analysis.
    The UI must label it as an estimate (see M7.2 in the roadmap).
    """
    digraph = build_digraph(graph)
    if digraph.number_of_nodes() == 0:
        return []

    roots = [n for n in entry_points(graph) if n in digraph]
    if not roots:
        # No entry point detected — everything would look unreachable, which
        # is a worse answer than none. Report nothing.
        return []

    reachable = set()
    for root in roots:
        reachable.add(root)
        reachable.update(nx.descendants(digraph, root))

    unreachable = sorted(set(digraph.nodes) - reachable)
    return unreachable


def attach_analysis(graph: dict) -> dict:
    """
    Attach PageRank, degrees, and betweenness to every node in place.

    Returns the same graph object for convenience. Nodes gain:
        pagerank    float  centrality score (sums to 1.0)
        in_degree   int
        out_degree  int
        betweenness float
    """
    scores = pagerank_scores(graph)
    degrees = degree_scores(graph)
    betweenness = betweenness_centrality(graph)

    for node in graph.get("nodes", []) or []:
        node_id = node.get("id")
        if not node_id:
            continue
        node["pagerank"] = round(scores.get(node_id, 0.0), 8)
        in_degree, out_degree = degrees.get(node_id, (0, 0))
        node["in_degree"] = in_degree
        node["out_degree"] = out_degree
        node["betweenness"] = round(betweenness.get(node_id, 0.0), 8)

    return graph


def top_hubs(graph: dict, limit: int = 10) -> list[dict]:
    """
    The most central nodes in the graph — the "top hubs" reported by the
    `reposcope://graph/summary` MCP resource and
    `get_architecture_overview`.
    """
    scores = pagerank_scores(graph)
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", []) or []}

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    hubs: list[dict] = []
    for node_id, score in ranked[:limit]:
        node = nodes_by_id.get(node_id, {})
        hubs.append({
            "id": node_id,
            "label": node.get("label", node_id),
            "type": node.get("type", ""),
            "file": node.get("file", ""),
            "pagerank": round(score, 6),
        })
    return hubs
