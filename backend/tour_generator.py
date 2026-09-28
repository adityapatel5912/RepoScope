"""
tour_generator.py
Conversational onboarding "Code Tours" — given a topic, walk the dependency
graph forward from matching entry points and explain each stop with the LLM.
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from runtime_config import ask_llm
from graph_utils import build_adjacency

log = logging.getLogger("reposcope.tour")

TOUR_SYSTEM = "You are a code tour guide. Be concise, practical, and clear."


def _explain_step(topic: str, node: dict, idx: int, total: int, provider: dict | None = None) -> str:
    """Generate the 2-3 sentence explanation for a single tour stop."""
    prompt = (
        f"You are giving a code tour. Step {idx + 1} of {total}.\n"
        f"Topic: {topic}\n"
        f"Node: {node.get('label')} (type: {node.get('type', 'file')})\n"
        f"File: {node.get('file', node.get('id', ''))}\n"
        f"Explain in 2-3 sentences why this matters for understanding "
        f"'{topic}' and what to look for. No code blocks. Be concise."
    )
    try:
        return ask_llm(
            TOUR_SYSTEM,
            prompt,
            graph_context=json.dumps(node)[:2000],
            provider=provider,
        ).strip()
    except Exception as exc:
        log.warning("Step explanation failed for %s: %s", node.get("id"), exc)
        return f"Read {node.get('label')} to understand part of {topic}."


def build_tour(graph: dict, topic: str, max_steps: int = 12, provider: dict | None = None) -> dict:
    """
    Produce an ordered list of steps (files/functions) that form a
    logical reading tour for the given topic.
    """
    nodes = graph.get("nodes", [])
    if not nodes:
        return {"error": "No graph loaded. Load a repo first."}

    # 1. Find entry points matching the topic
    topic_lower = topic.lower().strip()
    entry_points = [
        n for n in nodes
        if topic_lower in n.get("label", "").lower()
        or topic_lower in n.get("id", "").lower()
    ]

    if not entry_points:
        return {"error": f"No nodes match topic: {topic}"}

    # 2. Build forward adjacency (dependencies)
    forward, _ = build_adjacency(graph)

    # 3. BFS from top 3 entry points to build a reading order
    visited: set = set()
    order: list = []
    queue = [n["id"] for n in entry_points[:3]]

    while queue and len(order) < max_steps:
        nid = queue.pop(0)
        if nid in visited:
            continue
        visited.add(nid)
        order.append(nid)
        for nxt in forward.get(nid, []):
            if nxt not in visited:
                queue.append(nxt)

    # Edges may reference phantom targets (e.g. stdlib imports like
    # file:json.py that have no node in the graph) — drop them.
    node_map: Dict[str, dict] = {n["id"]: n for n in nodes}
    order = [nid for nid in order if nid in node_map]

    # 4. Build steps — explanations generated in parallel for speed
    steps_in_order = [node_map[nid] for nid in order]
    total = len(steps_in_order)

    with ThreadPoolExecutor(max_workers=6) as pool:
        explanations = list(pool.map(
            lambda args: _explain_step(*args),
            [(topic, node, i, total, provider) for i, node in enumerate(steps_in_order)],
        ))

    steps = []
    for i, (nid, explanation) in enumerate(zip(order, explanations)):
        node = node_map[nid]
        steps.append({
            "step": i + 1,
            "node_id": nid,
            "label": node.get("label", ""),
            "type": node.get("type", "file"),
            "file": node.get("file", ""),
            "line": node.get("line", 0),
            "explanation": explanation,
        })

    return {
        "topic": topic,
        "total_steps": len(steps),
        "steps": steps,
    }
