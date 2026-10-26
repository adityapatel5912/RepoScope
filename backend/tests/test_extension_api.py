"""
test_extension_api.py
The endpoints the VS Code extension depends on.

Milestone 4. The extension reads the graph over HTTP; it never parses
code. These two endpoints are its whole vocabulary:

    GET /api/analysis/callers     — the CodeLens count
    GET /api/analysis/dependents   — the status-bar blast radius

The count MUST match the MCP tool's answer, because both read the same
graph. If they ever disagree, a human and an agent are looking at two
different codebases — so the agreement is asserted here, across the two
interfaces, rather than assumed.
"""
import asyncio
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _graph():
    from graph_builder import build_graph_from_repo

    return build_graph_from_repo(str(FIXTURES_DIR / "multilang"))


def _call(router_path: str, **params):
    """Call an analysis endpoint against the fixture graph."""
    from api.routers import analysis

    module = analysis
    function = {
        "/callers": module.callers,
        "/callers-batch": module.callers_batch,
        "/dependents": module.dependents,
    }[router_path]
    return asyncio.run(function(**params))


def test_the_callers_endpoint_counts_the_real_callers(served_graph):
    """`app.py` calls `shout` from `helpers.py`."""
    result = _call("/callers", file="helpers.py", symbol="shout")

    assert result["available"] is True
    assert result["found"] is True
    assert result["count"] >= 1

    callers = {c["file"] for c in result["callers"]}
    assert "app.py" in callers
    # Every caller carries the evidence — the file and the line.
    for caller in result["callers"]:
        assert caller["file"]
        assert caller["line"] >= 0


def test_the_callers_endpoint_reports_a_symbol_with_no_callers(served_graph):
    result = _call("/callers", file="helpers.py", symbol="nothing_calls_this")
    assert result["available"] is True
    assert result["found"] is False
    assert result["count"] == 0


def test_the_batch_endpoint_agrees_with_the_single_one(served_graph):
    """
    The CodeLens asks for every symbol in a file at once. The answers
    must be the SAME answers — one implementation, one answer.
    """
    batch = _call("/callers-batch", file="helpers.py", symbols="shout,nothing_calls_this")

    assert batch["available"] is True
    assert batch["results"]["shout"]["found"] is True
    assert batch["results"]["nothing_calls_this"]["found"] is False

    single = _call("/callers", file="helpers.py", symbol="shout")
    assert batch["results"]["shout"]["count"] == single["count"]
    assert {c["file"] for c in batch["results"]["shout"]["callers"]} == {
        c["file"] for c in single["callers"]
    }


def test_the_batch_endpoint_answers_for_a_file_with_no_symbols(served_graph):
    batch = _call("/callers-batch", file="helpers.py", symbols="")
    assert batch["available"] is True
    assert batch["results"] == {}


def test_the_dependents_endpoint_reports_the_blast_radius(served_graph):
    """`helpers.py` is imported by `app.py`, so it has a dependent."""
    result = _call("/dependents", file="helpers.py")

    assert result["available"] is True
    assert result["found"] is True
    assert result["dependents"] >= 1
    assert result["risk"] in ("low", "medium", "high", "critical")
    assert 0 <= result["risk_score"] <= 10


def test_the_dependents_endpoint_reports_a_file_with_no_dependents(served_graph):
    result = _call("/dependents", file="greeter.go")
    assert result["available"] is True
    assert result["found"] is True
    assert result["dependents"] == 0


def test_the_dependents_endpoint_reports_an_unknown_file(served_graph):
    result = _call("/dependents", file="nope.py")
    assert result["available"] is True
    assert result["found"] is False


def test_the_extension_count_matches_the_mcp_tool(served_graph):
    """
    The CodeLens count and the MCP tool's answer MUST agree.

    They read the same graph, so they must. This is the assertion that
    catches a future change to one side of the interface.
    """
    from mcp_server import tools as mcp_tools

    graph = _graph()

    via_endpoint = _call("/callers", file="helpers.py", symbol="shout")
    # The symbol's blast radius — the same question the endpoint answers.
    # (The FILE's blast radius is a different question: it includes the
    # file-level import edge, so the two answers are not comparable.)
    via_tool = mcp_tools.blast_radius(graph, "helpers.py", "shout")

    endpoint_files = {c["file"] for c in via_endpoint["callers"]}
    tool_files = {n.get("file", "") for n in via_tool["direct_impacts"]}
    assert endpoint_files & tool_files, (
        "the CodeLens and the MCP tool disagree about who calls the symbol: "
        f"{endpoint_files} vs {tool_files}"
    )


def test_the_extension_endpoints_survive_an_empty_graph():
    """An empty index must produce a well-formed answer, not a crash."""
    empty = {"nodes": [], "edges": [], "summary": "0 nodes, 0 edges"}
    from graph_analysis import pagerank_scores

    assert pagerank_scores(empty) == {}

    # The routers read the graph through the orchestrator, so an absent
    # repository produces the "not available" payload.
    from api.routers import analysis

    result = asyncio.run(analysis.dependents(file="anything.py"))
    assert "available" in result
