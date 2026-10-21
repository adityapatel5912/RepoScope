"""
test_graph_store.py
Tests for backend/graph_store.py — the GraphStore abstraction (Correction C11).

The store is the seam that lets the web app, the CLI daemon, and the MCP
server read ONE index instead of each parsing the repository themselves.
"""
import json

import pytest

from graph_store import (
    JsonGraphStore,
    empty_graph,
    graph_summary,
    validate_graph,
)


def _sample_graph() -> dict:
    return {
        "nodes": [
            {"id": "file:a.py", "type": "file", "label": "a.py",
             "language": "py", "size": 120},
            {"id": "func:a.py:f", "type": "function", "label": "f",
             "file": "a.py", "line": 3},
            {"id": "file:b.ts", "type": "file", "label": "b.ts",
             "language": "ts", "size": 80},
        ],
        "edges": [
            {"source": "file:a.py", "target": "func:a.py:f", "type": "contains"},
            {"source": "file:a.py", "target": "file:b.ts", "type": "imports"},
        ],
        "summary": "3 nodes, 2 edges",
    }


# ── validate_graph ──────────────────────────────────────────────────────────

def test_valid_graph_has_no_problems():
    assert validate_graph(_sample_graph()) == []


def test_duplicate_node_ids_are_reported():
    graph = _sample_graph()
    graph["nodes"].append(dict(graph["nodes"][0]))
    problems = validate_graph(graph)
    assert any("duplicate node id" in p for p in problems)


def test_unknown_edge_type_is_reported():
    graph = _sample_graph()
    graph["edges"][0]["type"] = "teleports"
    problems = validate_graph(graph)
    assert any("unknown edge type" in p for p in problems)


def test_edge_to_unknown_node_is_reported():
    graph = _sample_graph()
    graph["edges"][0]["target"] = "file:ghost.py"
    problems = validate_graph(graph)
    assert any("unknown target" in p for p in problems)


def test_calls_edge_type_is_allowed():
    """The frontend already renders `calls` edges — they must validate."""
    graph = _sample_graph()
    graph["edges"].append(
        {"source": "func:a.py:f", "target": "file:b.ts", "type": "calls"}
    )
    assert validate_graph(graph) == []


def test_node_without_label_is_reported():
    graph = _sample_graph()
    del graph["nodes"][0]["label"]
    problems = validate_graph(graph)
    assert any("no 'label'" in p for p in problems)


def test_non_dict_graph_is_rejected():
    assert validate_graph([]) == ["graph is not a dictionary"]


# ── Round trip ──────────────────────────────────────────────────────────────

def test_save_then_load_round_trips(tmp_path):
    store = JsonGraphStore(tmp_path / ".reposcope" / "graph.json")
    graph = _sample_graph()
    store.save(graph)

    loaded = store.load()
    assert loaded["nodes"] == graph["nodes"]
    assert loaded["edges"] == graph["edges"]
    assert loaded["summary"] == graph["summary"]


def test_load_on_missing_store_returns_empty_graph(tmp_path):
    store = JsonGraphStore(tmp_path / "absent.json")
    assert store.load() == empty_graph()
    assert store.exists() is False


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "deep" / "nested" / "graph.json"
    store = JsonGraphStore(path)
    store.save(_sample_graph())
    assert path.is_file()


def test_save_refuses_a_graph_that_violates_the_contract(tmp_path):
    store = JsonGraphStore(tmp_path / "graph.json")
    broken = _sample_graph()
    broken["nodes"].append(dict(broken["nodes"][0]))  # duplicate id
    with pytest.raises(ValueError) as exc:
        store.save(broken)
    assert "contract" in str(exc.value)


def test_save_is_atomic(tmp_path):
    """No temp file may be left behind."""
    store = JsonGraphStore(tmp_path / "graph.json")
    store.save(_sample_graph())
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"temp files left behind: {leftovers}"


def test_load_recovers_from_corrupt_file(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = JsonGraphStore(path)
    assert store.load() == empty_graph()


def test_load_accepts_a_bare_graph_without_the_wrapper(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(_sample_graph()), encoding="utf-8")
    store = JsonGraphStore(path)
    loaded = store.load()
    assert len(loaded["nodes"]) == 3


# ── stats ───────────────────────────────────────────────────────────────────

def test_stats_reports_counts_and_types(tmp_path):
    store = JsonGraphStore(tmp_path / "graph.json")
    store.save(_sample_graph())
    stats = store.stats()

    assert stats["node_count"] == 3
    assert stats["edge_count"] == 2
    assert stats["node_types"]["file"] == 2
    assert stats["node_types"]["function"] == 1
    assert stats["edge_types"]["contains"] == 1
    assert stats["edge_types"]["imports"] == 1
    assert stats["exists"] is True


def test_stats_on_missing_store(tmp_path):
    store = JsonGraphStore(tmp_path / "absent.json")
    stats = store.stats()
    assert stats["node_count"] == 0
    assert stats["edge_count"] == 0
    assert stats["exists"] is False


# ── Helpers ─────────────────────────────────────────────────────────────────

def test_graph_summary_format():
    assert graph_summary({"nodes": [1, 2], "edges": [1]}) == "2 nodes, 1 edges"


def test_empty_graph_shape():
    empty = empty_graph()
    assert empty["nodes"] == []
    assert empty["edges"] == []
    assert "nodes" in empty["summary"]
