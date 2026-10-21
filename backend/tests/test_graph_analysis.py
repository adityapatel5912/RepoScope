"""
test_graph_analysis.py
Tests for backend/graph_analysis.py — PageRank centrality (M7.1), cycle
detection (M7.3), and unreachable-symbol detection (M7.2).
"""
import pytest

from graph_analysis import (
    attach_analysis,
    build_digraph,
    degree_scores,
    entry_points,
    find_cycles,
    cycle_details,
    pagerank_scores,
    top_hubs,
    unreachable_nodes,
)


# ── PageRank ────────────────────────────────────────────────────────────────

def test_pagerank_returns_a_score_for_every_node(built_graph):
    scores = pagerank_scores(built_graph)
    assert len(scores) == len(built_graph["nodes"])
    assert all(isinstance(v, float) for v in scores.values())


def test_pagerank_scores_sum_to_one(built_graph):
    scores = pagerank_scores(built_graph)
    assert sum(scores.values()) == pytest.approx(1.0, abs=1e-6)


def test_pagerank_is_deterministic(built_graph):
    """The same graph must always produce the same scores.

    These scores drive the pyramid layout, the CI risk gate, and the MCP
    tools. Non-determinism would make all three untrustworthy.
    """
    first = pagerank_scores(built_graph)
    second = pagerank_scores(built_graph)
    assert first == second


def test_pagerank_ranks_a_central_hub_above_a_leaf():
    """A hub that everything imports must outrank an isolated leaf."""
    graph = {
        "nodes": [{"id": "file:hub.py"}, {"id": "file:a.py"},
                  {"id": "file:b.py"}, {"id": "file:c.py"}],
        "edges": [
            {"source": "file:a.py", "target": "file:hub.py", "type": "imports"},
            {"source": "file:b.py", "target": "file:hub.py", "type": "imports"},
            {"source": "file:c.py", "target": "file:hub.py", "type": "imports"},
        ],
    }
    scores = pagerank_scores(graph)
    assert scores["file:hub.py"] == max(scores.values())


def test_pagerank_on_empty_graph_returns_empty():
    assert pagerank_scores({"nodes": [], "edges": []}) == {}


def test_degree_scores(built_graph):
    degrees = degree_scores(built_graph)
    assert len(degrees) == len(built_graph["nodes"])
    for in_degree, out_degree in degrees.values():
        assert in_degree >= 0 and out_degree >= 0


def test_top_hubs_is_sorted_and_bounded(built_graph):
    hubs = top_hubs(built_graph, limit=5)
    assert len(hubs) <= 5
    scores = [h["pagerank"] for h in hubs]
    assert scores == sorted(scores, reverse=True)
    assert all("id" in h and "label" in h for h in hubs)


# ── Graph construction ──────────────────────────────────────────────────────

def test_build_digraph_excludes_contains_edges():
    """`contains` is file->symbol membership, not dependency."""
    graph = {
        "nodes": [{"id": "file:a.py"}, {"id": "func:a.py:f"}],
        "edges": [{"source": "file:a.py", "target": "func:a.py:f", "type": "contains"}],
    }
    digraph = build_digraph(graph)
    assert digraph.number_of_edges() == 0


def test_build_digraph_includes_imports_and_calls():
    graph = {
        "nodes": [{"id": "file:a.py"}, {"id": "file:b.py"}, {"id": "func:b.py:g"}],
        "edges": [
            {"source": "file:a.py", "target": "file:b.py", "type": "imports"},
            {"source": "file:a.py", "target": "func:b.py:g", "type": "calls"},
        ],
    }
    digraph = build_digraph(graph)
    assert digraph.number_of_edges() == 2


def test_build_digraph_drops_edges_to_unknown_nodes():
    graph = {
        "nodes": [{"id": "file:a.py"}],
        "edges": [{"source": "file:a.py", "target": "file:ghost.py", "type": "imports"}],
    }
    digraph = build_digraph(graph)
    assert digraph.number_of_edges() == 0


# ── Cycle detection (M7.3) ──────────────────────────────────────────────────

def test_find_cycles_detects_both_fixture_cycles(circular_graph):
    cycles = find_cycles(circular_graph)
    members = {frozenset(c) for c in cycles}
    assert frozenset({"file:alpha.py", "file:beta.py", "file:gamma.py"}) in members
    assert frozenset({"file:a.ts", "file:b.ts", "file:c.ts"}) in members
    assert len(cycles) == 2


def test_isolated_module_is_not_a_cycle(circular_graph):
    for cycle in find_cycles(circular_graph):
        assert "file:isolated.py" not in cycle


def test_find_cycles_on_acyclic_graph_returns_nothing():
    graph = {
        "nodes": [{"id": "file:a.py"}, {"id": "file:b.py"}],
        "edges": [{"source": "file:a.py", "target": "file:b.py", "type": "imports"}],
    }
    assert find_cycles(graph) == []


def test_find_cycles_detects_a_self_loop():
    graph = {
        "nodes": [{"id": "file:a.py"}],
        "edges": [{"source": "file:a.py", "target": "file:a.py", "type": "imports"}],
    }
    cycles = find_cycles(graph)
    assert cycles == [["file:a.py"]]


def test_find_cycles_detects_a_two_node_cycle():
    graph = {
        "nodes": [{"id": "file:a.py"}, {"id": "file:b.py"}],
        "edges": [
            {"source": "file:a.py", "target": "file:b.py", "type": "imports"},
            {"source": "file:b.py", "target": "file:a.py", "type": "imports"},
        ],
    }
    cycles = find_cycles(graph)
    assert cycles == [["file:a.py", "file:b.py"]]


def test_cycle_details_reports_layers(circular_graph):
    details = cycle_details(circular_graph)
    assert len(details) == 2
    for detail in details:
        assert detail["length"] == 3
        assert detail["layers"], "every cycle must report the layers it spans"
        assert detail["severity"] in ("error", "warning")


# ── Entry points and unreachable nodes (M7.2) ───────────────────────────────

def test_entry_points_finds_root_modules(built_graph):
    entries = entry_points(built_graph)
    assert "file:app.py" in entries or "file:greeter.go" in entries


def test_unreachable_nodes_finds_isolated_modules():
    graph = {
        "nodes": [
            {"id": "file:main.py"},
            {"id": "file:used.py"},
            {"id": "file:orphan.py"},
        ],
        "edges": [
            {"source": "file:main.py", "target": "file:used.py", "type": "imports"},
        ],
    }
    unreachable = unreachable_nodes(graph)
    assert unreachable == ["file:orphan.py"]


def test_unreachable_nodes_returns_nothing_when_there_is_no_entry_point():
    """Without an entry point, everything would look unreachable."""
    graph = {
        "nodes": [{"id": "file:a.py"}, {"id": "file:b.py"}],
        "edges": [
            {"source": "file:a.py", "target": "file:b.py", "type": "imports"},
            {"source": "file:b.py", "target": "file:a.py", "type": "imports"},
        ],
    }
    assert unreachable_nodes(graph) == []


def test_unreachable_nodes_on_empty_graph():
    assert unreachable_nodes({"nodes": [], "edges": []}) == []


# ── attach_analysis ─────────────────────────────────────────────────────────

def test_attach_analysis_adds_metrics_to_every_node(built_graph):
    attach_analysis(built_graph)
    for node in built_graph["nodes"]:
        assert "pagerank" in node
        assert "in_degree" in node
        assert "out_degree" in node
        assert "betweenness" in node
        assert isinstance(node["pagerank"], float)
        assert isinstance(node["in_degree"], int)
