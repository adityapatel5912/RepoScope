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



# ── Phase 4 Tools & Resources ──────────────────────────────────────────


def mindmap_hierarchy(
    graph: dict,
    root: str | None = None,
    include_symbols: bool = True,
    max_nodes: int = 2000,
) -> dict:
    """Return the hierarchical root -> pillar -> folder -> file -> symbol mindmap."""
    if not graph or not graph.get("nodes"):
        return {"available": False, "reason": "the index is empty", "root": root}

    from mindmap import build_mindmap_payload

    clamped_max = max(1, min(max_nodes, 200000))
    payload = build_mindmap_payload(
        graph,
        include_symbols=include_symbols,
        max_nodes=clamped_max,
    )
    payload["available"] = True
    payload["root"] = str(Path(root).resolve()) if root else ""
    payload["include_symbols"] = include_symbols
    payload["max_nodes"] = clamped_max
    if "source" in payload and isinstance(payload["source"], dict):
        payload["source"]["root"] = payload["root"]
    return payload


def ast_skeleton(
    graph: dict,
    root: str | None,
    file_path: str,
    max_symbols: int = 200,
) -> dict:
    """Return the AST skeleton of a file omitting symbol bodies."""
    from context_compressor import build_ast_skeleton

    return build_ast_skeleton(graph, root, file_path, max_symbols=max_symbols)


def context_pack(
    graph: dict,
    root: str | None,
    paths: str = "",
    detail: str = "skeleton",
    budget: int = 8000,
    since_hash: str | None = None,
) -> dict:
    """Return a deterministic budget-bounded context pack. JSON only over MCP."""
    from context_compressor import build_context_pack

    return build_context_pack(
        graph=graph,
        root=root,
        paths=paths,
        detail=detail,
        budget=budget,
        since_hash=since_hash,
    )


def diff_interface_contracts(
    graph: dict,
    file_path: str,
    patch: str | None = None,
    old_source: str | None = None,
    new_source: str | None = None,
    include_consumers: bool = True,
) -> dict:
    """Diff interface contracts and boundary crossings between patch or source pair."""
    if not file_path:
        return {"available": False, "reason": "file_path is required"}

    has_patch = patch is not None
    has_sources = old_source is not None or new_source is not None

    if not has_patch and not has_sources:
        return {
            "available": False,
            "reason": "Either 'patch' or both 'old_source' and 'new_source' must be supplied",
        }
    if has_patch and has_sources:
        return {
            "available": False,
            "reason": "Cannot supply both 'patch' and ('old_source'/'new_source')",
        }
    if not has_patch and (old_source is None or new_source is None):
        return {
            "available": False,
            "reason": "Both 'old_source' and 'new_source' must be supplied when not using 'patch'",
        }

    import contract_diff

    if has_patch:
        old_src, new_src = contract_diff.sources_from_patch(patch)
    else:
        old_src, new_src = old_source, new_source

    findings = contract_diff.diff_sources(old_src, new_src, file_path)
    consumers_attached = False
    if include_consumers and graph and graph.get("nodes"):
        contract_diff.attach_consumers(findings, graph)
        consumers_attached = True

    findings_dicts = contract_diff.findings_to_dicts(findings)
    counts = {"breaking": 0, "warning": 0, "info": 0, "total": len(findings_dicts)}
    for fd in findings_dicts:
        sev = str(fd.get("severity", "")).lower()
        if sev in counts:
            counts[sev] += 1

    return {
        "available": True,
        "file": file_path,
        "findings": findings_dicts,
        "counts": counts,
        "consumers_attached": consumers_attached,
        "note": "No finding is not proof that no consumer breaks; dynamic dispatch, reflection, and unsupported languages are invisible to this check.",
    }


def ranked_reading_path(
    graph: dict,
    root: str | None = None,
    max_files: int = 12,
) -> dict:
    """Return a ranked, level-tiered reading path based on static connectivity."""
    if not graph or not graph.get("nodes"):
        return {"available": False, "reason": "the index is empty"}

    from onboarding import rank_rows
    from graph_utils import build_adjacency

    forward, reverse = build_adjacency(graph)
    rows = rank_rows(graph)

    level_defs = [
        (1, "Entry Points", "Start here - these files are where execution begins.", rows.get(1, []), "Backbone file with the highest reverse-dependency score."),
        (2, "Core Modules", "The central domain logic and data flows.", rows.get(2, []) + rows.get(3, []), "Core module in the middle of the dependency path."),
        (3, "Utils & Leaves", "Leaf or low-traffic helper; safe to read after the core.", rows.get(4, []) + rows.get(5, []), "Leaf or low-traffic helper; safe to read after the core."),
    ]

    clamped_max = max(1, min(max_files, 50))
    all_file_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "file"]
    total_files = len(all_file_nodes)

    seen_paths: set[str] = set()
    levels_out: list[dict] = []
    flat_path: list[dict] = []

    for lvl_num, title, desc, raw_nodes, why_text in level_defs:
        lvl_files = []
        for n in raw_nodes:
            p = n.get("path") or n.get("label") or ""
            if not p or p in seen_paths:
                continue
            seen_paths.add(p)
            incoming = len(reverse.get(n.get("id", ""), []))
            outgoing = len(forward.get(n.get("id", ""), []))
            score = incoming * 2 + outgoing
            file_entry = {
                "path": p,
                "role": n.get("role", "utility"),
                "pillar": n.get("pillar", "backend"),
                "line": int(n.get("line") or 1),
                "incoming": incoming,
                "outgoing": outgoing,
                "score": score,
                "why": why_text,
            }
            lvl_files.append(file_entry)
            if len(lvl_files) >= 6:
                break
        levels_out.append({
            "level": lvl_num,
            "title": title,
            "description": desc,
            "files": lvl_files,
        })

    for lvl in levels_out:
        for f in lvl["files"]:
            if len(flat_path) >= clamped_max:
                break
            flat_path.append({
                "rank": len(flat_path) + 1,
                "level": lvl["level"],
                **f,
            })
        if len(flat_path) >= clamped_max:
            break

    path_paths = {p["path"] for p in flat_path}
    for lvl in levels_out:
        lvl["files"] = [f for f in lvl["files"] if f["path"] in path_paths]

    return {
        "available": True,
        "root": str(Path(root).resolve()) if root else "",
        "levels": levels_out,
        "path": flat_path,
        "total_files": total_files,
        "returned": len(flat_path),
        "truncated": len(flat_path) < total_files,
        "caveat": "Ranking uses static graph connectivity; it is a starting path, not a measure of code quality.",
    }


def api_routes_resource(
    graph: dict,
    root: str | None = None,
    limit: int = 500,
) -> dict:
    """The payload behind reposcope://api-routes."""
    if not graph or not graph.get("nodes"):
        return {"available": False, "reason": "the index is empty"}

    routes = list(graph.get("api_routes", []))
    total = len(routes)
    clamped_limit = max(1, min(limit, 2000))
    truncated = total > clamped_limit
    return {
        "available": True,
        "root": str(Path(root).resolve()) if root else "",
        "routes": routes[:clamped_limit],
        "total": total,
        "truncated": truncated,
    }
