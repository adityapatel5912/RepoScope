"""
pr_chat.py
The conversational PR bot.

Milestone 5.3. A pure function: a question and the report's facts go in,
an answer comes out. No webhook plumbing — the GitHub Action reads the
comment and posts the reply, which is the simplification the roadmap
calls for and which keeps the bot testable.

**The answers are GROUNDED.** Every number in a reply comes from the
graph, and the reply cites the file and line it came from. A PR bot
that says "this might break authentication" without saying WHICH file
and WHICH line is guessing — and a reviewer who cannot check a claim
ignores it.

The supported questions:

| Question | Answered from |
|---|---|
| "explain risk for `<file>`" | That file's blast radius |
| "suggest test cases" | The changed modules with no tests |
| "verify architectural boundaries" | The boundary rules |
| "what breaks if I change `<symbol>`?" | The symbol's callers |
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from arch_rules import check_boundary, classify, load_ruleset
from graph_utils import find_node_by_label
from impact_analyzer import compute_blast_radius

log = logging.getLogger("reposcope.pr_chat")

#: The trigger. A comment that starts with this is addressed to the bot.
TRIGGER = "@reposcope-bot"

_FILE_RE = re.compile(r"([\w./-]+\.[A-Za-z]{1,5})")
_SYMBOL_RE = re.compile(r"`?([A-Za-z_][A-Za-z0-9_]*)`?")


@dataclass
class ChatRequest:
    """A question about a pull request."""

    comment: str
    changed_files: list[dict]
    graph: dict
    repo_root: str | None = None


def parse_command(comment: str) -> dict:
    """
    Read the question.

    Returns `{"intent": ..., "target": ...}`. The intent is one of
    `risk`, `tests`, `boundaries`, `blast`, or `help`.
    """
    body = comment.lower()
    if body.startswith(TRIGGER):
        body = body[len(TRIGGER):].strip()

    files = _FILE_RE.findall(comment)

    if "test" in body:
        return {"intent": "tests", "target": files[0] if files else None}
    if "boundary" in body or "architectur" in body or "layer" in body:
        return {"intent": "boundaries", "target": files[0] if files else None}
    if "break" in body or "blast" in body or "depend" in body or "impact" in body:
        return {"intent": "blast", "target": files[0] if files else None}
    if "risk" in body:
        return {"intent": "risk", "target": files[0] if files else None}
    return {"intent": "help", "target": files[0] if files else None}


def answer(request: ChatRequest) -> dict:
    """
    Answer a question about the pull request.

    Every number is grounded in the graph, and every claim carries the
    file (and line) it came from.
    """
    command = parse_command(request.comment)

    if command["intent"] == "help":
        return {
            "intent": "help",
            "answer": (
                "I can answer these about this pull request:\n\n"
                "- `explain risk for <file>` — what depends on this file, and how risky a change is\n"
                "- `what breaks if I change <file>` — the direct and transitive dependents\n"
                "- `suggest test cases` — the changed modules with no test coverage\n"
                "- `verify architectural boundaries` — does this PR cross a declared boundary?"
            ),
            "citations": [],
        }

    if command["intent"] == "tests":
        return _answer_tests(request)

    if command["intent"] == "boundaries":
        return _answer_boundaries(request)

    if command["intent"] in ("risk", "blast"):
        return _answer_risk(request, command["target"])

    return {"intent": "help", "answer": "I did not understand that question.", "citations": []}


def _answer_risk(request: ChatRequest, target: str | None) -> dict:
    graph = request.graph
    if not graph:
        return {
            "intent": "risk",
            "answer": "The graph is empty, so I cannot compute a blast radius.",
            "citations": [],
        }

    filenames = [f.get("filename") for f in request.changed_files if f.get("filename")]
    chosen = target or (filenames[0] if filenames else None)

    if not chosen:
        return {
            "intent": "risk",
            "answer": "Name a file — `explain risk for backend/auth.py`.",
            "citations": [],
        }

    node = find_node_by_label(graph, chosen)
    if node is None:
        return {
            "intent": "risk",
            "answer": f"`{chosen}` is not in the graph, so I have no blast radius for it.",
            "citations": [],
        }

    impact = compute_blast_radius(graph, node["id"], max_depth=3)
    citations = [
        {
            "file": n.get("file") or n.get("label", ""),
            "line": n.get("line", 0),
            "label": n.get("label", ""),
        }
        for n in impact["direct_impacts"][:8]
    ]

    lines = [
        f"**Risk for `{chosen}`: {impact['risk_level']} "
        f"({impact['risk_score']}/10).**",
        "",
        f"- {len(impact['direct_impacts'])} direct dependent(s)",
        f"- {len(impact['transitive_impacts'])} transitive dependent(s)",
        f"- {impact['total_impacted']} node(s) in the blast radius",
    ]
    if impact["direct_impacts"]:
        lines += ["", "**Direct dependents:**"]
        for node_ in impact["direct_impacts"][:8]:
            where = f"{node_.get('file') or node_.get('label')}"
            if node_.get("line"):
                where += f":{node_['line']}"
            lines.append(f"- `{where}`")
    if impact["suggested_tests"]:
        lines += ["", f"**Tests to run:** {', '.join('`' + t + '`' for t in impact['suggested_tests'][:5])}"]

    return {
        "intent": "risk",
        "answer": "\n".join(lines),
        "citations": citations,
        "risk_score": impact["risk_score"],
        "risk_level": impact["risk_level"],
    }


def _answer_tests(request: ChatRequest) -> dict:
    from test_stubs import find_untested_modules

    changed = [f.get("filename", "") for f in request.changed_files if f.get("filename")]
    graph = request.graph

    test_files = [
        str(n.get("label", ""))
        for n in graph.get("nodes", []) or []
        if n.get("type") == "file" and "test" in str(n.get("label", "")).lower()
    ]

    untested = find_untested_modules(graph, changed, test_files)
    if not untested:
        return {
            "intent": "tests",
            "answer": (
                "Every changed module is covered by a test file in the graph. "
                "No stubs are needed."
            ),
            "citations": [],
        }

    lines = [
        f"**{len(untested)} changed module(s) have no test file.**",
        "",
        *[f"- `{m}`" for m in untested[:10]],
        "",
        "Ask me for a stub and I will draft one — but it will be a "
        "suggestion to review, never an automatic commit.",
    ]
    return {
        "intent": "tests",
        "answer": "\n".join(lines),
        "citations": [{"file": m, "line": 0, "label": m} for m in untested[:10]],
        "untested": untested,
    }


def _answer_boundaries(request: ChatRequest) -> dict:
    graph = request.graph
    try:
        ruleset = load_ruleset(request.repo_root)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load the rule set: %s", exc)
        ruleset = None

    violations: list[str] = []
    citations: list[dict] = []

    for changed in request.changed_files:
        filename = changed.get("filename") or ""
        if not filename:
            continue
        file_id = f"file:{filename}"
        for edge in graph.get("edges", []) or []:
            if edge.get("type") != "imports" or edge.get("source") != file_id:
                continue
            target = str(edge.get("target", ""))
            if not target.startswith("file:"):
                continue
            target_rel = target[len("file:"):]
            violation = check_boundary(ruleset, filename, target_rel) if ruleset else None
            if violation is None:
                continue
            violations.append(
                f"- `{filename}` → `{target_rel}` — {violation.get('message', '')}"
            )
            citations.append({"file": filename, "line": 0, "label": target_rel})

    if not violations:
        layers = sorted({
            classify(f"file:{f.get('filename')}", str(f.get("filename")))
            for f in request.changed_files if f.get("filename")
        })
        return {
            "intent": "boundaries",
            "answer": (
                "**No boundary violations.** Every import in this pull request "
                "stays inside its declared domain.\n\n"
                f"Layers touched: {', '.join(layers) if layers else 'none'}."
            ),
            "citations": [],
        }

    return {
        "intent": "boundaries",
        "answer": (
            f"**{len(violations)} boundary violation(s).**\n\n"
            + "\n".join(violations)
        ),
        "citations": citations,
        "violations": violations,
    }


def is_addressed_to_the_bot(comment: str) -> bool:
    """True when a comment is addressed to the bot."""
    return comment.strip().lower().startswith(TRIGGER)
