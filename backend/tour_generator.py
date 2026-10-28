"""
backend/tour_generator.py
Four deterministic guided tour tracks and CodeTour exporter (Phase 8, V2.7).

Supported Tracks:
- `request_lifecycle`: Entrypoint route -> middleware -> router -> handler -> domain service -> persistence
- `data_flow`: Input ingestion -> schema validation -> domain model -> persistence sink
- `change_impact`: High-indegree hubs -> shared utilities -> cross-cutting boundaries
- `onboarding`: Low-level foundations -> domain core -> top-level application controllers
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from runtime_config import ask_llm
    from graph_utils import build_adjacency
except ImportError:
    from backend.runtime_config import ask_llm
    from backend.graph_utils import build_adjacency

log = logging.getLogger("reposcope.tour")

TOUR_SYSTEM = "You are an expert code tour guide. Be concise, practical, and clear."

TRACK_METADATA: Dict[str, Dict[str, str]] = {
    "request_lifecycle": {
        "label": "Request Lifecycle",
        "why_this_order": "Topological order from HTTP entrypoint route to domain handlers and persistence sinks.",
        "default_desc": "Traces ingress HTTP/CLI requests through routing to domain logic.",
    },
    "data_flow": {
        "label": "Data Flow",
        "why_this_order": "Traces data structures from validation schemas through transformation logic to storage.",
        "default_desc": "Follows models and state mutations through the core architecture.",
    },
    "change_impact": {
        "label": "Change Impact",
        "why_this_order": "Ranks nodes by dependency degree to highlight architectural hubs whose changes carry high blast radius.",
        "default_desc": "Highlights high-indegree hubs and shared foundational contracts.",
    },
    "onboarding": {
        "label": "Architectural Onboarding",
        "why_this_order": "Progressive curriculum starting with zero-dependency foundations, building up to domain controllers.",
        "default_desc": "First-day reading order for engineers onboarding to the codebase.",
    },
}


def _explain_step(
    topic: str,
    track: str,
    node: dict,
    idx: int,
    total: int,
    reason: str,
    provider: dict | None = None,
) -> str:
    """Generate concise 2-3 sentence explanation for a single tour stop."""
    label = node.get("label", node.get("id", ""))
    ntype = node.get("type", "file")
    nfile = node.get("file", node.get("id", ""))
    line = node.get("line") or 1

    prompt = (
        f"You are giving a code tour for track '{track}'. Step {idx + 1} of {total}.\n"
        f"Topic: {topic}\n"
        f"Node: {label} (type: {ntype})\n"
        f"File: {nfile}:{line}\n"
        f"Architectural role: {reason}\n"
        f"Explain in 2 concise sentences what this stop does in the {track} flow. No markdown code blocks."
    )
    if provider:
        try:
            res = ask_llm(
                TOUR_SYSTEM,
                prompt,
                graph_context=json.dumps(node)[:1500],
                provider=provider,
            ).strip()
            if res:
                return res
        except Exception as exc:
            log.warning("Step explanation failed for %s: %s", node.get("id"), exc)

    # Deterministic fallback explanation
    return (
        f"`{label}` acts as {reason} in the {track.replace('_', ' ')} pipeline. "
        f"Inspect line {line} to see interface contracts and downstream callers."
    )


def _find_request_lifecycle_nodes(nodes: List[dict], forward: Dict[str, List[str]], max_stops: int) -> List[Tuple[dict, str]]:
    """Select nodes in request lifecycle order: Routes/Entrypoints -> Router/Handler -> Services -> Data."""
    stops: List[Tuple[dict, str]] = []
    seen: Set[str] = set()

    # 1. Entrypoints / Main
    entrypoints = [
        n for n in nodes
        if any(k in n.get("id", "").lower() for k in ("main.py", "app.py", "server.ts", "index.ts", "api.py", "routes"))
        or n.get("type") in ("route", "entrypoint")
    ]
    if not entrypoints:
        entrypoints = nodes[:1]

    for ep in entrypoints[:2]:
        if ep["id"] not in seen:
            seen.add(ep["id"])
            stops.append((ep, "HTTP / server request entrypoint"))

    # 2. Trace forward downstream
    for ep, _ in list(stops):
        for nxt_id in forward.get(ep["id"], []):
            if nxt_id not in seen and len(stops) < max_stops:
                nxt_node = next((n for n in nodes if n["id"] == nxt_id), None)
                if nxt_node:
                    seen.add(nxt_id)
                    stops.append((nxt_node, "Router handler or controller logic"))

    # 3. Add any remaining nodes up to max_stops
    for n in nodes:
        if n["id"] not in seen and len(stops) < max_stops:
            seen.add(n["id"])
            stops.append((n, "Downstream service or storage dependency"))

    return stops


def _find_data_flow_nodes(nodes: List[dict], forward: Dict[str, List[str]], max_stops: int) -> List[Tuple[dict, str]]:
    """Select nodes in data flow order: Models/Schemas -> Transformers -> Storage/API."""
    stops: List[Tuple[dict, str]] = []
    seen: Set[str] = set()

    # Priority to schemas, models, types
    model_nodes = [
        n for n in nodes
        if any(k in n.get("id", "").lower() for k in ("model", "schema", "type", "entity", "dto"))
    ]
    other_nodes = [n for n in nodes if n not in model_nodes]
    ordered_candidates = model_nodes + other_nodes

    for n in ordered_candidates[:max_stops]:
        if n["id"] not in seen:
            seen.add(n["id"])
            role = "Data model or schema definition" if n in model_nodes else "Data transformation / state consumer"
            stops.append((n, role))

    return stops


def _find_change_impact_nodes(nodes: List[dict], backward: Dict[str, List[str]], max_stops: int) -> List[Tuple[dict, str]]:
    """Select nodes in change impact order: Highest in-degree (most depended upon) hubs."""
    # Compute in-degree
    scored = []
    for n in nodes:
        indegree = len(backward.get(n["id"], []))
        scored.append((indegree, n))
    scored.sort(key=lambda x: x[0], reverse=True)

    stops: List[Tuple[dict, str]] = []
    for indegree, n in scored[:max_stops]:
        stops.append((n, f"High-impact hub depended on by {indegree} downstream modules"))

    return stops


def _find_onboarding_nodes(nodes: List[dict], forward: Dict[str, List[str]], backward: Dict[str, List[str]], max_stops: int) -> List[Tuple[dict, str]]:
    """Select nodes in onboarding order: Foundation utilities -> Domain -> Entrypoints."""
    # Lowest in-degree first (foundational)
    foundations = [n for n in nodes if len(backward.get(n["id"], [])) == 0]
    hubs = [n for n in nodes if n not in foundations]

    stops: List[Tuple[dict, str]] = []
    for n in foundations[: max_stops // 2]:
        stops.append((n, "Foundational utility or standalone module"))
    for n in hubs[: max_stops - len(stops)]:
        stops.append((n, "Core domain or architectural orchestrator"))

    return stops


def build_tour(
    graph: dict,
    topic: str = "",
    max_steps: int = 12,
    provider: dict | None = None,
    track: Optional[str] = None,
    target_node_id: Optional[str] = None,
) -> dict:
    """
    Produce an ordered tour across 4 deterministic tracks:
    `request_lifecycle`, `data_flow`, `change_impact`, or `onboarding`.
    """
    nodes = graph.get("nodes", [])
    if not nodes:
        return {"error": "No graph loaded. Load a repo first.", "available": False}

    forward, backward = build_adjacency(graph)
    node_map = {n["id"]: n for n in nodes}

    # Normalize track selection
    clean_track = (track or "").lower().strip()
    clean_topic = (topic or "").lower().strip()

    if not clean_track:
        if clean_topic in TRACK_METADATA:
            clean_track = clean_topic
        elif any(k in clean_topic for k in ("request", "lifecycle", "route", "api", "http")):
            clean_track = "request_lifecycle"
        elif any(k in clean_topic for k in ("data", "flow", "model", "schema", "db")):
            clean_track = "data_flow"
        elif any(k in clean_topic for k in ("impact", "hub", "change", "blast")):
            clean_track = "change_impact"
        elif any(k in clean_topic for k in ("onboard", "start", "curriculum", "learn")):
            clean_track = "onboarding"
        else:
            clean_track = "request_lifecycle"

    meta = TRACK_METADATA.get(clean_track, TRACK_METADATA["request_lifecycle"])
    track_label = meta["label"]
    why_this_order = meta["why_this_order"]

    # Select ordered stops according to the track
    if target_node_id and target_node_id in node_map:
        target_node = node_map[target_node_id]
        stops_with_reasons = [(target_node, f"Specified target start node: {target_node.get('label')}")]
        for nxt in forward.get(target_node_id, []):
            if nxt in node_map and len(stops_with_reasons) < max_steps:
                stops_with_reasons.append((node_map[nxt], "Direct downstream dependency"))
    elif clean_track == "request_lifecycle":
        stops_with_reasons = _find_request_lifecycle_nodes(nodes, forward, max_steps)
    elif clean_track == "data_flow":
        stops_with_reasons = _find_data_flow_nodes(nodes, forward, max_steps)
    elif clean_track == "change_impact":
        stops_with_reasons = _find_change_impact_nodes(nodes, backward, max_steps)
    elif clean_track == "onboarding":
        stops_with_reasons = _find_onboarding_nodes(nodes, forward, backward, max_steps)
    else:
        stops_with_reasons = _find_request_lifecycle_nodes(nodes, forward, max_steps)

    if not stops_with_reasons:
        return {
            "available": False,
            "track": clean_track,
            "track_label": track_label,
            "error": f"No matching nodes found for track '{clean_track}'",
            "total_steps": 0,
            "steps": [],
        }

    total = len(stops_with_reasons)
    with ThreadPoolExecutor(max_workers=6) as pool:
        explanations = list(pool.map(
            lambda args: _explain_step(*args),
            [
                (topic or clean_track, clean_track, n, i, total, r, provider)
                for i, (n, r) in enumerate(stops_with_reasons)
            ],
        ))

    steps: List[dict] = []
    for i, ((node, reason), explanation) in enumerate(zip(stops_with_reasons, explanations)):
        fpath = node.get("file") or node.get("id", "").replace("file:", "")
        line_num = node.get("line") or 1
        steps.append({
            "step": i + 1,
            "node_id": node["id"],
            "label": node.get("label", node["id"]),
            "type": node.get("type", "file"),
            "file": fpath,
            "line": line_num,
            "explanation": explanation,
            "reason": reason,
        })

    return {
        "ok": True,
        "topic": topic or clean_track,
        "track": clean_track,
        "track_label": track_label,
        "why_this_order": why_this_order,
        "available": True,
        "total_steps": len(steps),
        "steps": steps,
        "source": {
            "nodes": len(nodes),
            "edges": len(graph.get("edges", [])),
        },
    }


def export_codetour(tour: dict, repo_name: str = "RepoScope") -> dict:
    """Export a tour dictionary into official VS Code CodeTour JSON schema."""
    track_label = tour.get("track_label", "Guided Tour")
    steps = tour.get("steps", [])

    codetour_steps = []
    for s in steps:
        codetour_steps.append({
            "file": s.get("file", ""),
            "line": s.get("line", 1),
            "description": f"### Step {s.get('step')}: {s.get('label')}\n\n{s.get('explanation')}\n\n*Role:* {s.get('reason')}",
        })

    return {
        "$schema": "https://aka.ms/codetour-schema",
        "title": f"{repo_name}: {track_label}",
        "steps": codetour_steps,
        "ref": "main",
    }
