"""
api/routers/pr_chat.py
The conversational PR bot, and the SARIF endpoint.

Milestone 5.3 and 8.2.

    POST /api/pr/chat     answer a question about a pull request
    GET  /api/pr/sarif    the findings as SARIF 2.1.0

Both are PURE functions of their input. The GitHub Action reads a
comment, calls `/api/pr/chat`, and posts the reply — no webhook server,
no state, and the bot is testable without a network.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pr_chat import ChatRequest, answer, is_addressed_to_the_bot
from sarif import to_sarif_json

log = logging.getLogger("reposcope.api.pr_chat")

router = APIRouter(prefix="/api/pr", tags=["pr"])


class ChatBody(BaseModel):
    """A question about the loaded pull request."""

    comment: str
    changed_files: list[dict] | None = None


class SarifBody(BaseModel):
    """The findings to render as SARIF."""

    findings: list[dict] = []
    baseline: list[str] = []


class ReportBody(BaseModel):
    """The pull request to report on."""

    changed_files: list[dict] = []
    meta: dict = {}
    baseline: list[str] = []


def _current_graph() -> dict:
    """The graph for the loaded repository."""
    from orchestrator import current_graph

    graph, _root = current_graph()
    return graph


def _repo_root() -> str | None:
    from repo_tracker import load_state

    return load_state().get("local_path")


@router.post("/report")
async def pr_report(body: ReportBody):
    """
    The Architecture Impact report for a pull request.

    The GitHub Action calls this with the pull request's file list, and
    posts the returned comment. The report is built from the loaded
    repository's graph, so the numbers are the same ones the canvas
    shows.
    """
    from arch_rules import load_ruleset
    from pr_impact import build_pr_impact
    from sarif import to_sarif_json

    graph = await asyncio.to_thread(_current_graph)
    root = _repo_root()

    try:
        ruleset = load_ruleset(root) if root else None
    except Exception as exc:  # noqa: BLE001 - a broken config must not break the report
        log.warning("Could not load the rule set: %s", exc)
        ruleset = None

    report = await asyncio.to_thread(
        build_pr_impact, graph, body.meta or {}, body.changed_files,
        ruleset, root,
    )

    return {
        "ok": True,
        "comment": report["comment"],
        "risk_score": report["risk_score"],
        "risk_level": report["risk_level"],
        "architecture_impact": report["architecture_impact"],
        "merge_gate": report["merge_gate"],
        "badges": report["badges"],
        "sarif": json.loads(to_sarif_json(report["sarif"], body.baseline)),
    }


@router.post("/chat")
async def pr_chat(body: ChatBody):
    """
    Answer a question about the pull request.

    The answers are GROUNDED: every number comes from the graph, and
    every claim carries the file and line it came from. A reviewer who
    cannot check a claim ignores the bot — so the citations are not
    decoration.
    """
    comment = (body.comment or "").strip()
    if not comment:
        raise HTTPException(status_code=400, detail="The comment is empty")

    graph = await asyncio.to_thread(_current_graph)
    changed = body.changed_files or []

    if not changed:
        # Fall back to the repository's own state, so a bot asked about
        # a loaded repository still has something to say.
        from repo_tracker import load_state

        state = load_state()
        changed = [{"filename": state.get("repo", "")}] if state.get("repo") else []

    request = ChatRequest(
        comment=comment,
        changed_files=changed,
        graph=graph,
    )
    result = await asyncio.to_thread(answer, request)

    return {
        "ok": True,
        "addressed_to_bot": is_addressed_to_the_bot(comment),
        **result,
    }


@router.get("/sarif")
async def pr_sarif():
    """
    The pull request's findings as SARIF 2.1.0.

    SARIF is the GitHub code-scanning standard, and it means RepoScope's
    findings appear INLINE on the PR diff — where reviewers already look
    — instead of in a comment they have to scroll to.
    """
    from sarif import SarifResult

    graph = await asyncio.to_thread(_current_graph)
    results: list[SarifResult] = []

    # The cycles and the unreachable symbols, as findings.
    from architecture_impact import analyze_architecture_impact
    from repo_tracker import load_state

    state = load_state()
    changed = [{"filename": state.get("repo", "")}] if state.get("repo") else []

    try:
        impact = analyze_architecture_impact(graph, changed)
        for finding in impact.get("findings", []):
            results.append(SarifResult(
                rule_id=finding.get("rule_id") or "reposcope/breaking-contract",
                message=finding.get("detail") or finding.get("title", ""),
                file=finding.get("file", ""),
                line=finding.get("line", 0),
                level="error" if finding.get("severity") == "error" else "warning",
            ))
    except Exception as exc:  # noqa: BLE001 - never fail the endpoint
        log.warning("Could not build the SARIF findings: %s", exc)

    return {"sarif": json.loads(to_sarif_json(results))}
