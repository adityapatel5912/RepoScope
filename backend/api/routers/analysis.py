"""
api/routers/analysis.py
Serves the graph-intelligence endpoints (Milestones 7.1, 7.2, 7.3, 1.3).

Four things the UI could not previously see:

  GET /api/analysis/hotspots   git churn and the churn x centrality blend
  GET /api/analysis/cycles     dependency cycles, at file and symbol level
  GET /api/analysis/unreachable symbols that no entry point can reach
  GET /api/analysis/hubs       the most central nodes, by PageRank

Every endpoint degrades gracefully: no git repository, an empty graph, or
a failure inside the analysis all produce a well-formed "not available"
payload rather than an error.
"""
import asyncio

from fastapi import APIRouter, HTTPException

from git_history import collect_churn, churn_to_api
from graph_analysis import (
    cycle_details,
    entry_points,
    pagerank_scores,
    top_hubs,
    unreachable_nodes,
)
from repo_tracker import load_state

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _current_graph() -> dict:
    """
    The graph for the loaded repository.

    It reads the SAME source as `/api/repo/graph` — the live session
    when there is one, the orchestrator's cache otherwise. Two paths
    meant an endpoint could answer about a different codebase than the
    one on screen.
    """
    from orchestrator import current_graph

    graph, _root = current_graph()
    return graph


def _file_of(node: dict) -> str:
    """
    The file a node belongs to, always.

    A file node has no `file` of its own — it IS the file. But the
    extension jumps to `caller.file`, so a file-level caller that
    answered with an empty path would send the developer to the
    workspace root instead of the file that calls.
    """
    file_path = str(node.get("file") or "")
    if file_path:
        return file_path
    node_id = str(node.get("id") or "")
    if node_id.startswith("file:"):
        return node_id[len("file:"):]
    return ""


@router.get("/hotspots")
async def hotspots(window_days: int = 90):
    """
    Git churn for the loaded repository, with a hotspot score per file.

    The hotspot score blends churn with the file's centrality: a file
    that changes often AND is widely depended upon is where regressions
    actually happen.
    """
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        return {
            "available": False,
            "reason": "no repository loaded",
            "window_days": window_days,
            "files": [],
            "total_files": 0,
        }

    graph = await asyncio.to_thread(_current_graph)
    report = await asyncio.to_thread(collect_churn, local_path, window_days)
    return churn_to_api(report, graph)


@router.get("/cycles")
async def cycles():
    """Dependency cycles — at file level and at symbol level."""
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "cycles": [], "total": 0}

    details = cycle_details(graph)
    file_cycles = [c for c in details if c["members"][0].startswith("file:")]
    symbol_cycles = [c for c in details if not c["members"][0].startswith("file:")]

    return {
        "available": True,
        "cycles": details,
        "file_cycles": len(file_cycles),
        "symbol_cycles": len(symbol_cycles),
        "total": len(details),
        "cross_layer_count": sum(1 for c in details if c["crosses_layers"]),
    }


@router.get("/unreachable")
async def unreachable():
    """
    Symbols that no entry point can reach.

    This is a STATIC ESTIMATE. Dynamic dispatch, reflection and plugin
    registration are invisible to static analysis, so the UI must label
    it as an estimate rather than as proof of dead code.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {
            "available": False,
            "reason": "no graph",
            "entry_points": [],
            "unreachable": [],
            "total": 0,
        }

    roots = entry_points(graph)
    orphans = unreachable_nodes(graph)

    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    return {
        "available": True,
        "estimate": True,
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


@router.get("/hubs")
async def hubs(limit: int = 15):
    """
    The most central nodes in the graph, by PageRank.

    Unlike the old `incoming x 2 + outgoing` heuristic, PageRank
    distinguishes a widely-imported leaf from a genuine hub.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "hubs": []}

    scores = pagerank_scores(graph)
    return {
        "available": True,
        "hubs": top_hubs(graph, limit=max(1, min(limit, 100))),
        "total_nodes": len(scores),
    }


@router.get("/workspaces")
async def workspaces():
    """
    The packages in a monorepo (Milestone 9.1).

    An empty list means an ordinary repository — which is the common
    case, and the right answer.
    """
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        return {"available": False, "reason": "no repository loaded", "workspaces": []}

    from monorepo import detect_workspaces

    found = await asyncio.to_thread(detect_workspaces, local_path)
    return {
        "available": True,
        "workspaces": found,
        "count": len(found),
        "is_monorepo": len(found) > 1,
    }


@router.get("/ownership")
async def ownership():
    """
    The ownership overlay (Milestone 9.4).

    Who last changed each file, combined with the churn. A file that
    changes often and has ONE owner is a knowledge silo; a file that
    changes often and has MANY is a coordination problem. Both are worth
    knowing before you change something.
    """
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        return {"available": False, "reason": "no repository loaded", "files": []}

    from ownership import ownership_report

    churn: dict[str, float] = {}
    try:
        from git_history import collect_churn

        report = await asyncio.to_thread(collect_churn, local_path, 90)
        for path, entry in (getattr(report, "files", {}) or {}).items():
            churn[path] = float(getattr(entry, "churn_score", 0) or 0)
    except Exception:  # noqa: BLE001 - churn is optional here
        pass

    result = await asyncio.to_thread(ownership_report, local_path, churn)
    return result


@router.get("/critical-path")
async def critical_path(limit: int = 15):
    """
    The nodes on the critical path — the codebase's choke points.

    Betweenness centrality is O(n·m), and it used to be computed on
    every graph build — 2.5 seconds on a 3,753-node repository, for a
    number the canvas never rendered. It is computed HERE, on demand, and
    cached.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "nodes": []}

    from graph_analysis import critical_path as compute_critical_path

    nodes = await asyncio.to_thread(compute_critical_path, graph, max(1, min(limit, 200)))
    return {
        "available": True,
        "nodes": nodes,
        "total": len(nodes),
    }


@router.get("/callers")
async def callers(file: str = "", symbol: str = ""):
    """
    Who calls this symbol?

    The VS Code extension's CodeLens shows this count, and it MUST match
    the MCP tool's answer — an extension that says "View Callers (8)"
    when the graph says 3 is worse than no extension at all.

    The resolution order is the graph's own: same file, then an imported
    module, then an unambiguous global match. The SAME rule, so the same
    answer.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "callers": [], "count": 0}

    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []

    symbol_nodes = [
        n for n in nodes
        if n.get("type") in ("function", "class")
        and (not file or n.get("file") == file)
        and (not symbol or n.get("label") == symbol)
    ]
    if not symbol_nodes:
        return {
            "available": True,
            "found": False,
            "count": 0,
            "callers": [],
            "reason": f"no symbol matching {file}:{symbol}",
        }

    target_ids = {n["id"] for n in symbol_nodes}
    caller_ids = {
        e["source"] for e in edges
        if e.get("type") == "calls" and e.get("target") in target_ids
    }

    nodes_by_id = {n["id"]: n for n in nodes}
    caller_nodes = [nodes_by_id[i] for i in caller_ids if i in nodes_by_id]
    caller_nodes.sort(key=lambda n: (str(n.get("file", "")), int(n.get("line") or 0)))

    return {
        "available": True,
        "found": True,
        "count": len(caller_nodes),
        "callers": [
            {
                "id": n["id"],
                "label": n.get("label", ""),
                "file": _file_of(n),
                "line": int(n.get("line") or 0),
            }
            for n in caller_nodes
        ],
    }


@router.get("/callers-batch")
async def callers_batch(file: str = "", symbols: str = ""):
    """
    The callers of EVERY symbol in a file, in ONE request.

    The extension's CodeLens needs a count above each definition line.
    Asking once per line meant a file with fifty definitions fired fifty
    HTTP requests — the lens took seconds to appear, and the backend did
    fifty times the work for one answer.

    The counts are the SAME counts `/callers` returns: one implementation,
    one answer, whichever way it is asked for.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "results": {}}

    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    nodes_by_id = {n["id"]: n for n in nodes}

    wanted = [name for name in symbols.split(",") if name]
    results: dict[str, dict] = {}
    for name in wanted:
        symbol_nodes = [
            n for n in nodes
            if n.get("type") in ("function", "class")
            and (not file or n.get("file") == file)
            and n.get("label") == name
        ]
        if not symbol_nodes:
            results[name] = {"found": False, "count": 0, "callers": []}
            continue

        target_ids = {n["id"] for n in symbol_nodes}
        caller_ids = {
            e["source"] for e in edges
            if e.get("type") == "calls" and e.get("target") in target_ids
        }
        caller_nodes = [nodes_by_id[i] for i in caller_ids if i in nodes_by_id]
        caller_nodes.sort(key=lambda n: (str(n.get("file", "")), int(n.get("line") or 0)))
        results[name] = {
            "found": True,
            "count": len(caller_nodes),
            "callers": [
                {
                    "id": n["id"],
                    "label": n.get("label", ""),
                    "file": _file_of(n),
                    "line": int(n.get("line") or 0),
                }
                for n in caller_nodes
            ],
        }

    return {"available": True, "file": file, "results": results}


@router.get("/dependents")
async def dependents(file: str = ""):
    """
    What depends on this file, and how risky a change would be.

    The status bar in the VS Code extension shows this: the number of
    dependents and the risk level, so a developer sees the blast radius
    before they type.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "dependents": 0, "risk": "unknown"}

    nodes_by_id = {n["id"]: n for n in graph.get("nodes", []) or []}
    target_id = f"file:{file}"
    if target_id not in nodes_by_id:
        return {
            "available": True,
            "found": False,
            "dependents": 0,
            "risk": "unknown",
            "reason": f"no file matching {file!r}",
        }

    from impact_analyzer import compute_blast_radius

    impact = compute_blast_radius(graph, target_id, max_depth=3)
    return {
        "available": True,
        "found": True,
        "file": file,
        "dependents": impact["total_impacted"],
        "direct": len(impact["direct_impacts"]),
        "transitive": len(impact["transitive_impacts"]),
        "risk": impact["risk_level"],
        "risk_score": impact["risk_score"],
        "top": [
            {
                "id": n["id"],
                "label": n.get("label", ""),
                "file": _file_of(n),
                "line": int(n.get("line") or 0),
            }
            for n in impact["direct_impacts"][:10]
        ],
    }


@router.get("/repo-map")
async def repo_map(budget: int = 8000):
    """
    The repo map, and what it saves.

    Milestone 8.1. The map is the graph rendered for a reader that is
    not looking at a canvas: the files that matter, the symbols they
    define, and the architectural layer each belongs to.

    The number that matters is the reduction. `full_context_tokens` is
    what an agent pays to read the whole repository; `tokens` is what it
    pays to read this map instead.

    The baseline is measured against the SAME repository the map was
    built from. Measuring one against the other produces a figure that
    is worse than useless — a map for one codebase compared against a
    "full repository" count for another.
    """
    from orchestrator import current_graph

    graph, root = await asyncio.to_thread(current_graph)
    if not graph:
        return {
            "available": False,
            "reason": "no repository loaded",
            "text": "",
            "entries": [],
            "tokens": 0,
            "full_context_tokens": 0,
            "reduction_pct": 0.0,
        }

    from repo_map import build_repo_map_with_metrics

    result = await asyncio.to_thread(
        build_repo_map_with_metrics, graph, root, max(500, min(budget, 100_000))
    )
    return {"available": True, **result}
