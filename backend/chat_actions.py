"""
backend/chat_actions.py
Deterministic intent detector and action dispatcher for natural language chat.

Extracts structured action suggestions from chat user prompts and conversation context,
enabling the frontend ChatPanel to render interactive, one-click Action Cards
that launch tours, simulations, onboarding lessons, security scans, metrics, and scaffolds.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def detect_chat_actions(
    message: str,
    graph: Optional[Dict[str, Any]] = None,
    current_mode: str = "understanding",
) -> List[Dict[str, Any]]:
    """Analyze the user's message and current graph context to emit actionable chips."""
    if not message or not isinstance(message, str):
        return []

    msg = message.lower().strip()
    actions: List[Dict[str, Any]] = []
    nodes = (graph or {}).get("nodes", [])

    # 1. Tour intent detection
    if any(k in msg for k in ("tour", "walk through", "guide me through", "reading order", "lifecycle", "flow")):
        track = "request_lifecycle"
        track_title = "Request Lifecycle Tour"
        desc = "Trace requests from entrypoints through routers to domain services."

        if "data" in msg or "database" in msg or "store" in msg or "persist" in msg:
            track = "data_flow"
            track_title = "Data Flow Tour"
            desc = "Follow models and data transformations from ingestion to storage."
        elif "impact" in msg or "depend" in msg or "hub" in msg:
            track = "change_impact"
            track_title = "Change Impact Tour"
            desc = "Explore high-indegree hubs and critical shared dependencies."
        elif "onboard" in msg or "start" in msg or "begin" in msg or "overview" in msg:
            track = "onboarding"
            track_title = "Architectural Onboarding Tour"
            desc = "Read the codebase topographically from foundation to entrypoints."

        actions.append({
            "kind": "tour",
            "track": track,
            "title": track_title,
            "description": desc,
            "icon": "map",
        })

    # 2. Student Onboarding intent
    if any(k in msg for k in ("onboard", "learn", "lesson", "teach me", "student mode", "quiz", "curriculum")):
        actions.append({
            "kind": "onboarding",
            "level": 1,
            "title": "Start Onboarding Curriculum",
            "description": "Progress through topological tiers with graph-verified challenges.",
            "icon": "graduation-cap",
        })

    # 3. Metrics, Churn, Hotspots & Time Machine intent
    if any(k in msg for k in ("hotspot", "churn", "bus factor", "history", "time machine", "who changed", "frequent")):
        actions.append({
            "kind": "metrics",
            "view": "hotspots",
            "title": "Open Churn & Hotspots Matrix",
            "description": "Inspect churn velocity vs AST complexity and author bus factor.",
            "icon": "radio",
        })

    # 4. Impact Simulation intent
    if any(k in msg for k in ("what breaks", "blast radius", "simulate", "impact of", "if i change")):
        # Look for a mentioned node or file in the query
        target_node = None
        for n in nodes:
            label = n.get("label", "")
            nid = n.get("id", "")
            if label and label.lower() in msg:
                target_node = label
                break
            elif nid and nid.lower() in msg:
                target_node = label or nid
                break

        actions.append({
            "kind": "impact",
            "target": target_node or "main.py",
            "title": f"Simulate Impact{' for ' + target_node if target_node else ''}",
            "description": "Analyze 3-hop downstream blast radius and broken contract paths.",
            "icon": "git-branch",
        })

    # 5. Security & Taint Scan intent
    if any(k in msg for k in ("security", "vulnerability", "cve", "taint", "injection", "secret", "audit", "cwe")):
        actions.append({
            "kind": "security",
            "title": "Run 6-Engine Security Suite",
            "description": "Scan for cross-file taint, hardcoded secrets, injection sinks & offline CVEs.",
            "icon": "shield-alert",
        })

    # 6. Scaffold & Starter Kit intent
    if any(k in msg for k in ("scaffold", "starter kit", "bootstrap", "boilerplate", "generate project", "skeleton")):
        actions.append({
            "kind": "scaffold",
            "title": "Generate Starter Kit Scaffold",
            "description": "CodeCrafters-style runnable multi-file project skeleton.",
            "icon": "zap",
        })

    # 7. Reverse Prompt & Blueprint intent
    if any(k in msg for k in ("reverse prompt", "blueprint", "spec bundle", "prompt compiler", "rebuild prompt")):
        actions.append({
            "kind": "reverse_prompt",
            "title": "Open Reverse-Prompt Compiler",
            "description": "Generate rebuild blueprints, feature slices, and agent spec bundles.",
            "icon": "wand",
        })

    # 8. PR Impact intent
    pr_match = re.search(r"\bpr\s*#?(\d+)\b|\bpull\s*request\s*#?(\d+)\b", msg)
    if pr_match or "pr impact" in msg or "pull request impact" in msg:
        pr_num = int(pr_match.group(1) or pr_match.group(2)) if pr_match else None
        actions.append({
            "kind": "pr_impact",
            "pr_number": pr_num,
            "title": f"Inspect Symbol Diffs{' for PR #' + str(pr_num) if pr_num else ''}",
            "description": "Analyze symbol-level contract breaks, API route changes, and test gaps.",
            "icon": "git-pull-request",
        })

    return actions
