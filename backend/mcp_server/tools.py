"""
mcp_server/tools.py
The deterministic tools the MCP server exposes.

Every tool here is a pure function over ONE indexed repository. No tool
calls an LLM: an agent that asks "what breaks if I change this file?"
should get the graph's answer, not a model's opinion of it. A
deterministic tool is fast, reproducible, and citable — the agent can
quote the `file:line` it was given.

Correction C11: the MCP server is a CLIENT of the same GraphStore the
web app reads. It never re-implements parsing.
"""
from __future__ import annotations

import logging
from pathlib import Path

from arch_rules import check_boundary, classify, load_ruleset
from graph_analysis import (
    cycle_details,
    entry_points,
    top_hubs,
    unreachable_nodes,
)
from graph_utils import build_adjacency, bfs_traverse
from impact_analyzer import compute_blast_radius

log = logging.getLogger("reposcope.mcp.tools")


def architecture_overview(graph: dict, root: str | None = None, max_depth: int = 2) -> dict:
    """
    A summary of the repository's shape: layers, hubs, entry points.

    `max_depth` bounds how far the entry points are expanded.
    """
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    if not nodes:
        return {"available": False, "reason": "the index is empty", "root": root}

    layers: dict[str, int] = {}
    for node in nodes:
        if node.get("type") != "file":
            continue
        layer = classify(str(node.get("id", "")), str(node.get("label", "")))
        layers[layer] = layers.get(layer, 0) + 1

    forward, _reverse = build_adjacency(graph)
    entries = entry_points(graph)
    reach: set[str] = set()
    for entry in entries[:50]:
        depths = bfs_traverse(forward, entry, max_depth=max_depth)
        for bucket in depths.values():
            reach.update(bucket)

    return {
        "available": True,
        "root": root,
        "summary": graph.get("summary", ""),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "layers": layers,
        "top_hubs": top_hubs(graph, limit=10),
        "entry_points": entries[:50],
        "entry_point_count": len(entries),
        "reachable_within_depth": len(reach),
        "max_depth": max_depth,
    }


def blast_radius(
    graph: dict,
    target_file: str,
    target_symbol: str | None = None,
    depth: int = 3,
) -> dict:
    """
    What depends on this file (or symbol), directly and transitively.

    The target is matched by path or by node id, so an agent can pass
    either `backend/auth.py` or `file:backend/auth.py`.
    """
    nodes = {n["id"]: n for n in graph.get("nodes", []) or []}
    target_id: str | None = None

    if target_symbol:
        wanted = f"file:{target_file}"
        for node in nodes.values():
            if node.get("file") == target_file and node.get("label") == target_symbol:
                target_id = node["id"]
                break
        if target_id is None:
            return {
                "available": False,
                "reason": f"symbol {target_symbol!r} not found in {target_file!r}",
            }
    else:
        candidates = [f"file:{target_file}", target_file]
        for candidate in candidates:
            if candidate in nodes:
                target_id = candidate
                break
        if target_id is None:
            # A suffix match — agents often pass a path fragment.
            matches = [
                node_id for node_id, node in nodes.items()
                if node.get("type") == "file"
                and str(node.get("label", "")).endswith(target_file)
            ]
            if len(matches) == 1:
                target_id = matches[0]
            elif len(matches) > 1:
                return {
                    "available": False,
                    "reason": f"{target_file!r} is ambiguous",
                    "candidates": sorted(matches)[:20],
                }
            else:
                return {"available": False, "reason": f"no file matches {target_file!r}"}

    impact = compute_blast_radius(graph, target_id, max_depth=max(1, min(depth, 10)))
    return {"available": True, **impact}


def dependency_lineage(graph: dict, file_path: str, direction: str = "both") -> dict:
    """
    The import/call lineage of a file — what it needs, what needs it.
    """
    nodes = {n["id"]: n for n in graph.get("nodes", []) or []}
    target_id = f"file:{file_path}"
    if target_id not in nodes:
        matches = [
            node_id for node_id, node in nodes.items()
            if node.get("type") == "file"
            and str(node.get("label", "")).endswith(file_path)
        ]
        if len(matches) != 1:
            return {
                "available": False,
                "reason": f"no unique file matches {file_path!r}",
                "candidates": sorted(matches)[:20],
            }
        target_id = matches[0]

    forward, reverse = build_adjacency(graph)

    def _shape(ids: list[str]) -> list[dict]:
        out = []
        for node_id in ids:
            node = nodes.get(node_id)
            if not node:
                continue
            out.append({
                "id": node_id,
                "label": node.get("label", ""),
                "type": node.get("type", ""),
                "file": node.get("file", ""),
                "line": node.get("line", 0),
            })
        return out

    result: dict = {"available": True, "target": target_id, "direction": direction}
    if direction in ("upstream", "both"):
        result["upstream"] = _shape(sorted({
            node_id for bucket in bfs_traverse(forward, target_id, max_depth=5).values()
            for node_id in bucket
        }))
    if direction in ("downstream", "both"):
        result["downstream"] = _shape(sorted({
            node_id for bucket in bfs_traverse(reverse, target_id, max_depth=5).values()
            for node_id in bucket
        }))
    return result


def explain_architectural_rule(
    graph: dict,
    source_file: str,
    imported_file: str,
    repo_root: str | None = None,
) -> dict:
    """
    Does this import cross a declared architectural boundary?

    The rules come from `backend/arch_rules.py` — the same rule set the
    UI serves through `GET /api/arch/rules` and the same one a
    `.reposcope.yml` in the repository can override. The MCP server does
    not keep its own copy.
    """
    ruleset = load_ruleset(repo_root)
    violation = check_boundary(ruleset, source_file, imported_file)
    return {
        "available": True,
        "source_file": source_file,
        "imported_file": imported_file,
        "source_layer": classify(f"file:{source_file}", source_file),
        "imported_layer": classify(f"file:{imported_file}", imported_file),
        "violated": violation is not None,
        "violation": violation,
        "rules_in_effect": len(ruleset.rules),
    }


def hotspots(graph: dict, root: str | None = None, limit: int = 10) -> dict:
    """The files that change often AND are widely depended upon."""
    try:
        from git_history import collect_churn, churn_to_api
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"git history unavailable: {exc}"}

    if not root:
        return {"available": False, "reason": "no repository root was resolved"}
    report = collect_churn(root, 90)
    payload = churn_to_api(report, graph)
    payload["available"] = True
    files = payload.get("files") or []
    payload["files"] = files[: max(1, min(limit, 100))]
    return payload


def find_dependency_cycles(graph: dict) -> dict:
    """
    The dependency cycles — at file level and at symbol level.

    A cycle that crosses layers (storage -> client) is an architecture
    violation. A cycle inside one layer is a code smell. The distinction
    is what makes the report actionable rather than noise.
    """
    if not graph.get("nodes"):
        return {"available": False, "reason": "the index is empty", "cycles": []}

    details = cycle_details(graph)
    file_cycles = [c for c in details if c["members"] and c["members"][0].startswith("file:")]
    symbol_cycles = [c for c in details if not (c["members"] and c["members"][0].startswith("file:"))]

    return {
        "available": True,
        "cycles": details,
        "file_cycles": len(file_cycles),
        "symbol_cycles": len(symbol_cycles),
        "total": len(details),
        "cross_layer_count": sum(1 for c in details if c["crosses_layers"]),
    }


def unreachable_symbols(graph: dict) -> dict:
    """
    The symbols no entry point can reach.

    A STATIC ESTIMATE, not proof of dead code: dynamic dispatch,
    reflection and plugin registration are invisible to static
    analysis. The answer says so, so an agent does not present it as a
    certainty.
    """
    if not graph.get("nodes"):
        return {"available": False, "reason": "the index is empty", "unreachable": []}

    nodes_by_id = {n["id"]: n for n in graph.get("nodes", []) or []}
    orphans = unreachable_nodes(graph)
    roots = entry_points(graph)

    return {
        "available": True,
        "estimate": True,
        "caveat": (
            "A static estimate - dynamic dispatch, reflection and plugin "
            "registration are invisible to it. Not proof of dead code."
        ),
        "entry_points": roots[:50],
        "entry_point_count": len(roots),
        "unreachable": [
            {
                "id": node_id,
                "label": nodes_by_id.get(node_id, {}).get("label", node_id),
                "file": nodes_by_id.get(node_id, {}).get("file", ""),
                "type": nodes_by_id.get(node_id, {}).get("type", ""),
            }
            for node_id in orphans[:200]
        ],
        "total": len(orphans),
    }


def graph_summary_resource(graph: dict, root: str | None = None) -> dict:
    """The payload behind `reposcope://graph/summary`."""
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    symbol_count = sum(1 for n in nodes if n.get("type") in ("function", "class"))
    edge_types: dict[str, int] = {}
    for edge in edges:
        edge_type = str(edge.get("type", "unknown"))
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

    return {
        "root": root,
        "summary": graph.get("summary", ""),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "file_count": sum(1 for n in nodes if n.get("type") == "file"),
        "symbol_count": symbol_count,
        "edge_types": edge_types,
        "top_hubs": top_hubs(graph, limit=10),
    }
