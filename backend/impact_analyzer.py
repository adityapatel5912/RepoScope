"""
impact_analyzer.py
Agentic "What-If" Impact Analysis — reverse-BFS over the dependency graph
to compute the blast radius of changing a node, with an LLM narrative.
"""
import json
import logging

from runtime_config import ask_llm
from graph_utils import build_adjacency

log = logging.getLogger("reposcope.impact")


def compute_blast_radius(graph: dict, target_id: str,
                         max_depth: int = 3) -> dict:
    """
    Reverse-BFS from target to find everything that depends on it.
    Depth-0 neighbours = direct impacts; deeper = transitive.
    """
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    _, reverse = build_adjacency(graph)

    visited = {target_id}
    queue: list[tuple] = [(target_id, 0)]
    direct: list[str] = []
    transitive: list[str] = []

    while queue:
        nid, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for parent in reverse.get(nid, []):
            if parent in visited:
                continue
            visited.add(parent)
            if depth == 0:
                direct.append(parent)
            else:
                transitive.append(parent)
            queue.append((parent, depth + 1))

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

    direct_nodes = shape(direct)
    transitive_nodes = shape(transitive)

    risk_score = min(10, len(direct_nodes) * 2 + len(transitive_nodes))
    if risk_score >= 8:
        risk_level = "critical"
    elif risk_score >= 5:
        risk_level = "high"
    elif risk_score >= 3:
        risk_level = "medium"
    else:
        risk_level = "low"

    impacted_ids = {n["id"] for n in direct_nodes + transitive_nodes}
    suggested_tests = [
        n["id"] for n in nodes.values()
        if "test" in n.get("id", "").lower()
        or "test" in n.get("label", "").lower()
    ][:5]

    target = nodes.get(target_id, {"id": target_id})
    return {
        "target": {
            "id": target.get("id", target_id),
            "label": target.get("label", target_id),
            "file": target.get("file", ""),
            "type": target.get("type", ""),
        },
        "direct_impacts": direct_nodes,
        "transitive_impacts": transitive_nodes,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "suggested_tests": suggested_tests,
        "total_impacted": len(impacted_ids),
    }


def generate_impact_narrative(impact: dict) -> str:
    """LLM-written 3-4 sentence explanation of what could break."""
    prompt = (
        f"A developer wants to change: {impact['target'].get('label')} "
        f"({impact['target'].get('file', '')}).\n\n"
        f"Impact analysis:\n"
        f"- Risk level: {impact['risk_level']} ({impact['risk_score']}/10)\n"
        f"- Directly impacted: {len(impact['direct_impacts'])}\n"
        f"- Transitively impacted: {len(impact['transitive_impacts'])}\n"
        f"- Suggested tests: {impact['suggested_tests']}\n\n"
        f"Write 3-4 sentences explaining what could break and what the "
        f"developer should check before making this change. "
        f"Be specific and actionable. No code blocks."
    )
    try:
        return ask_llm(
            "You are a code impact analyst. Be concise and practical.",
            prompt,
            graph_context=json.dumps(impact)[:3000],
        )
    except Exception as exc:
        log.warning("Impact narrative failed: %s", exc)
        return (
            f"Changing {impact['target'].get('label')} affects "
            f"{impact['total_impacted']} downstream nodes. "
            f"Risk level: {impact['risk_level']}."
        )
