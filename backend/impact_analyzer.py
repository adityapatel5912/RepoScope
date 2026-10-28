"""
impact_analyzer.py
Agentic "What-If" Impact Analysis — reverse-BFS over the dependency graph
to compute the blast radius of changing a node, with an LLM narrative.
"""
import json
import logging

from runtime_config import ask_llm
from graph_utils import build_adjacency_cached

log = logging.getLogger("reposcope.impact")


def compute_blast_radius(graph: dict, target_id: str,
                         max_depth: int = 3) -> dict:
    """
    Reverse-BFS from target to compute 1-hop, 2-hop, and 3-hop downstream dependency graphs,
    mathematical risk score breakdown, API boundaries, and test gaps.
    """
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges", []) or []
    _, reverse = build_adjacency_cached(graph)

    visited = {target_id}
    queue: list[tuple[str, int, list[str]]] = [(target_id, 0, [target_id])]

    hop_nodes_map: dict[int, list[str]] = {1: [], 2: [], 3: []}
    path_map: dict[str, list[str]] = {target_id: [target_id]}

    while queue:
        nid, depth, current_path = queue.pop(0)
        if depth >= max_depth:
            continue
        for parent in reverse.get(nid, []):
            if parent in visited:
                continue
            visited.add(parent)
            next_depth = depth + 1
            new_path = current_path + [parent]
            path_map[parent] = new_path

            if next_depth in hop_nodes_map:
                hop_nodes_map[next_depth].append(parent)
            queue.append((parent, next_depth, new_path))

    def shape(ids: list[str]) -> list[dict]:
        out = []
        for i in ids:
            n = nodes.get(i)
            if not n:
                continue
            out.append({
                "id": n["id"],
                "label": n.get("label", ""),
                "type": n.get("type", "file"),
                "file": n.get("file", ""),
            })
        return out

    direct_nodes = shape(hop_nodes_map[1])
    transitive_ids = hop_nodes_map[2] + hop_nodes_map[3]
    transitive_nodes = shape(transitive_ids)

    # 3-hop structured data
    hops_data = []
    hop_labels = {
        1: "Direct Impacts (Hop 1)",
        2: "Secondary Dependents (Hop 2)",
        3: "Deep Transitive (Hop 3)",
    }
    for h in (1, 2, 3):
        h_node_ids = set(hop_nodes_map[h])
        h_nodes = shape(hop_nodes_map[h])
        prev_ids = {target_id} if h == 1 else set(hop_nodes_map[h - 1])
        h_edges = [
            {"source": e.get("source"), "target": e.get("target"), "type": e.get("type", "imports")}
            for e in edges
            if (e.get("source") in h_node_ids and e.get("target") in prev_ids)
            or (e.get("target") in h_node_ids and e.get("source") in prev_ids)
        ]
        hops_data.append({
            "hop": h,
            "label": hop_labels[h],
            "nodes": h_nodes,
            "edges": h_edges,
        })

    # API boundaries
    api_boundary_nodes = []
    for nid in visited:
        n = nodes.get(nid)
        if not n:
            continue
        is_route = (
            n.get("type") in ("route", "endpoint")
            or "route" in str(n.get("roles", [])).lower()
            or str(n.get("label", "")).startswith("/api")
            or str(n.get("file", "")).startswith("api/")
            or "routes" in str(n.get("file", ""))
        )
        if is_route:
            api_boundary_nodes.append({
                "id": n["id"],
                "label": n.get("label", ""),
                "file": n.get("file", ""),
                "type": "api_boundary",
            })

    # Test gaps
    test_node_ids = {
        n["id"] for n in nodes.values()
        if "test" in n.get("id", "").lower()
        or "test" in str(n.get("label", "")).lower()
        or "spec" in str(n.get("label", "")).lower()
    }
    tested_targets = {
        e.get("target") for e in edges if e.get("source") in test_node_ids
    }
    test_gaps = []
    for nid in visited - {target_id}:
        n = nodes.get(nid)
        if not n:
            continue
        if nid not in tested_targets and n.get("file") not in tested_targets:
            if not ("test" in str(n.get("file", "")).lower() or "spec" in str(n.get("file", "")).lower()):
                test_gaps.append({
                    "id": n["id"],
                    "label": n.get("label", ""),
                    "file": n.get("file", ""),
                    "detail": f"Downstream dependency `{n.get('label')}` lacks direct test coverage.",
                })

    # Invariant formula
    raw_score = (
        (len(direct_nodes) * 3.0)
        + (len(transitive_nodes) * 1.5)
        + (len(api_boundary_nodes) * 4.0)
        + (len(test_gaps) * 2.0)
    )
    risk_score = max(1, min(10, round(raw_score / 4.0))) if (direct_nodes or transitive_nodes) else 1
    if risk_score >= 8:
        risk_level = "critical"
    elif risk_score >= 5:
        risk_level = "high"
    elif risk_score >= 3:
        risk_level = "medium"
    else:
        risk_level = "low"

    score_breakdown = {
        "direct_callers": len(direct_nodes),
        "transitive_callers": len(transitive_nodes),
        "api_boundaries": len(api_boundary_nodes),
        "test_gaps": len(test_gaps),
        "raw_score": round(raw_score, 1),
        "normalized_score": risk_score,
    }

    # Propagation paths
    explanation_paths = []
    for nid in list(visited - {target_id})[:10]:
        n = nodes.get(nid)
        if not n:
            continue
        p = path_map.get(nid, [target_id, nid])
        explanation_paths.append({
            "target": n.get("label", nid),
            "hop": len(p) - 1,
            "path": [nodes.get(x, {}).get("label", x) for x in p],
            "reason": f"Transitively imported via {' -> '.join(nodes.get(x, {}).get('label', x) for x in p[-2:])}",
        })

    suggested_tests = [
        n.get("label", n["id"]) for n in nodes.values()
        if "test" in n.get("id", "").lower()
        or "test" in n.get("label", "").lower()
    ][:6]

    target = nodes.get(target_id, {"id": target_id})
    return {
        "target": {
            "id": target.get("id", target_id),
            "label": target.get("label", target_id),
            "file": target.get("file", ""),
            "type": target.get("type", ""),
        },
        "max_depth": max_depth,
        "direct_impacts": direct_nodes,
        "transitive_impacts": transitive_nodes,
        "hops": hops_data,
        "score_breakdown": score_breakdown,
        "api_boundaries": api_boundary_nodes,
        "test_gaps": test_gaps,
        "explanation_paths": explanation_paths,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "suggested_tests": suggested_tests,
        "total_impacted": len(direct_nodes) + len(transitive_nodes),
    }


def generate_impact_narrative(impact: dict, provider: dict | None = None) -> str:
    """LLM-written or deterministic heuristic 3-4 sentence explanation of what could break."""
    target_label = impact['target'].get('label', '')
    direct_cnt = len(impact.get('direct_impacts', []))
    trans_cnt = len(impact.get('transitive_impacts', []))
    boundaries_cnt = len(impact.get('api_boundaries', []))
    test_gaps_cnt = len(impact.get('test_gaps', []))
    risk_lvl = impact.get('risk_level', 'low')
    risk_sc = impact.get('risk_score', 1)

    prompt = (
        f"A developer wants to change: {target_label} "
        f"({impact['target'].get('file', '')}).\n\n"
        f"Impact analysis:\n"
        f"- Risk level: {risk_lvl} ({risk_sc}/10)\n"
        f"- Directly impacted (Hop 1): {direct_cnt}\n"
        f"- Transitively impacted (Hops 2 & 3): {trans_cnt}\n"
        f"- API boundaries exposed: {boundaries_cnt}\n"
        f"- Downstream test gaps: {test_gaps_cnt}\n"
        f"- Suggested tests: {impact.get('suggested_tests', [])}\n\n"
        f"Write 3-4 sentences explaining what could break and what the "
        f"developer should check before making this change. "
        f"Be specific and actionable. No code blocks."
    )
    if provider:
        try:
            return ask_llm(
                "You are a code impact analyst. Be concise and practical.",
                prompt,
                graph_context=json.dumps(impact)[:3000],
                provider=provider,
            )
        except Exception as exc:
            log.warning("Impact narrative LLM call failed: %s", exc)

    # Deterministic fallback narrative
    boundary_msg = f" It exposes {boundaries_cnt} public API boundaries." if boundaries_cnt else ""
    gap_msg = f" Note {test_gaps_cnt} downstream components lack direct test coverage." if test_gaps_cnt else ""
    tests_msg = f" Verify tests for: {', '.join(impact.get('suggested_tests', [])[:3])}." if impact.get('suggested_tests') else ""
    return (
        f"Modifying `{target_label}` produces a {risk_lvl} risk ({risk_sc}/10) with "
        f"{direct_cnt} direct caller(s) and {trans_cnt} transitive dependent(s) across 3 hops.{boundary_msg}"
        f"{gap_msg} {tests_msg}".strip()
    )
