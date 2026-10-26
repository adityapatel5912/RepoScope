"""
test_graph_v2.py
The schema v2 contract: additive edges, evidence, and incremental parity.

The golden test still pins the v1 node/edge subset. These tests prove the
new surface is real, validated, persisted, and never guessed.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from graph_builder import (
    DERIVED_EDGE_TYPES,
    assemble_graph,
    build_graph_from_repo,
    finalize_graph,
    GraphIndexer,
)
from graph_store import JsonGraphStore, SCHEMA_VERSION, validate_graph
from parse_cache import FileFacts

FIXTURES = Path(__file__).resolve().parent / "fixtures"
V2_FIXTURE = FIXTURES / "v2_contract"


def _edge_set(graph: dict, edge_type: str) -> set[tuple[str, str]]:
    return {
        (edge["source"], edge["target"])
        for edge in graph["edges"]
        if edge["type"] == edge_type
    }


def _build_v2() -> dict:
    return build_graph_from_repo(str(V2_FIXTURE))


# ── Schema and evidence ─────────────────────────────────────────────────────

def test_builder_writes_schema_v2_and_capabilities():
    graph = _build_v2()
    assert graph["schema_version"] == SCHEMA_VERSION == 2
    assert graph["metadata"]["builder"] == "graph_builder"
    assert set(graph["metadata"]["capabilities"]) >= {
        "roles", "pillars", "routes", "api_calls", "inherits", "exports",
    }


def test_every_v2_edge_has_evidence_and_resolves_to_real_nodes():
    graph = _build_v2()
    node_ids = {node["id"] for node in graph["nodes"]}
    for edge in graph["edges"]:
        if edge["type"] not in DERIVED_EDGE_TYPES:
            continue
        assert edge["evidence"]["file"]
        assert edge["evidence"]["line"] >= 1
        assert 0.0 <= edge["evidence"]["confidence"] <= 1.0
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
    assert validate_graph(graph) == []


def test_v1_graph_still_validates():
    graph = {
        "nodes": [
            {"id": "file:a.py", "type": "file", "label": "a.py"},
            {"id": "func:a.py:f", "type": "function", "label": "f", "file": "a.py", "line": 1},
        ],
        "edges": [
            {"source": "file:a.py", "target": "func:a.py:f", "type": "contains"},
        ],
        "summary": "2 nodes, 1 edges",
    }
    assert validate_graph(graph) == []


def test_unknown_v2_edge_type_is_rejected():
    graph = _build_v2()
    graph["edges"].append({
        "source": "file:server.py",
        "target": "file:client.ts",
        "type": "teleports",
        "evidence": {"file": "server.py", "line": 1, "confidence": 1.0},
    })
    problems = validate_graph(graph)
    assert any("unknown edge type" in problem for problem in problems)


def test_v2_edge_without_evidence_is_rejected():
    graph = {
        "nodes": [
            {"id": "file:a.py", "type": "file", "label": "a.py"},
            {"id": "file:b.py", "type": "file", "label": "b.py"},
        ],
        "edges": [
            {"source": "file:a.py", "target": "file:b.py", "type": "exports"},
        ],
        "schema_version": 2,
    }
    problems = validate_graph(graph)
    assert any("without an evidence object" in problem for problem in problems)


@pytest.mark.parametrize(
    "evidence, needle",
    [
        ({"file": "/etc/passwd", "line": 1, "confidence": 1.0}, "absolute"),
        ({"file": "../outside.py", "line": 1, "confidence": 1.0}, "escapes"),
        ({"file": "a.py", "line": 0, "confidence": 1.0}, "positive integer"),
        ({"file": "a.py", "line": 1, "confidence": 1.7}, "within [0, 1]"),
    ],
)
def test_malformed_evidence_is_rejected(evidence, needle):
    graph = {
        "nodes": [
            {"id": "file:a.py", "type": "file", "label": "a.py"},
            {"id": "file:b.py", "type": "file", "label": "b.py"},
        ],
        "edges": [{
            "source": "file:a.py",
            "target": "file:b.py",
            "type": "exports",
            "evidence": evidence,
        }],
        "schema_version": 2,
    }
    problems = validate_graph(graph)
    assert any(needle in problem for problem in problems), problems


# ── The three new edge families ─────────────────────────────────────────────

def test_inherits_resolves_a_two_file_fixture():
    graph = _build_v2()
    assert (
        "class:derived.py:Child",
        "class:base.py:Base",
    ) in _edge_set(graph, "inherits")
    edge = next(
        edge for edge in graph["edges"]
        if edge["type"] == "inherits"
    )
    assert edge["evidence"]["kind"] == "inheritance"
    assert edge["evidence"]["file"] == "derived.py"


def test_exports_follows_a_barrel():
    graph = _build_v2()
    assert (
        "file:components/index.ts",
        "file:components/Button.tsx",
    ) in _edge_set(graph, "exports")


def test_api_calls_links_fetch_to_the_backend_handler():
    graph = _build_v2()
    edges = _edge_set(graph, "api_calls")
    assert (
        "func:client.ts:fetchHealth",
        "func:server.py:health",
    ) in edges
    assert (
        "func:client.ts:createItem",
        "func:server.py:create_item",
    ) in edges

    parameterized = next(
        edge for edge in graph["edges"]
        if edge["type"] == "api_calls"
        and edge["target"] == "func:server.py:create_item"
    )
    assert parameterized["evidence"]["method"] == "POST"
    assert parameterized["evidence"]["path"] == "/api/items/*"
    assert parameterized["evidence"]["confidence"] < 1.0


def test_api_routes_name_real_handler_nodes():
    graph = _build_v2()
    node_ids = {node["id"] for node in graph["nodes"]}
    assert {route["path"] for route in graph["api_routes"]} == {
        "/api/health", "/api/items/{item_id}", "/ws/live",
    }
    for route in graph["api_routes"]:
        assert route["node_id"] in node_ids
        assert route["file"] == "server.py"


def test_ambiguous_api_target_is_not_guessed():
    """
    Two files declare the same method and path. A client call cannot
    choose between them, so no edge is emitted. A guessed cross-stack
    edge is worse than a missing one.
    """
    def server(rel: str, handler: str) -> FileFacts:
        return FileFacts(
            rel=rel, suffix=".py", size=1, sha256=rel,
            symbols=[{
                "name": handler, "kind": "function", "line": 1, "end_line": 2,
                "signature": "", "exported": True, "parent": None, "complexity": 1,
            }],
            imports=[],
            calls=[],
            routes=[{
                "method": "GET", "path": "/api/ambiguous", "line": 1,
                "handler": handler, "handler_line": 1, "kind": "http",
            }],
        )

    client = FileFacts(
        rel="client.ts", suffix=".ts", size=1, sha256="client",
        symbols=[{
            "name": "callAmbiguous", "kind": "function", "line": 1, "end_line": 2,
            "signature": "", "exported": True, "parent": None, "complexity": 1,
        }],
        imports=[],
        calls=[],
        api_calls=[{
            "method": "GET", "path": "/api/ambiguous", "line": 1,
            "enclosing": "callAmbiguous", "enclosing_line": 1, "origin": "fetch",
        }],
    )
    graph = assemble_graph({
        "server_a.py": server("server_a.py", "first"),
        "server_b.py": server("server_b.py", "second"),
        "client.ts": client,
    })
    assert _edge_set(graph, "api_calls") == set()


# ── Persistence and idempotence ────────────────────────────────────────────

def test_store_round_trip_preserves_v2_metadata_and_routes(tmp_path):
    graph = _build_v2()
    store = JsonGraphStore(tmp_path / ".reposcope" / "graph.json")
    store.save(graph)
    loaded = store.load()

    assert loaded["schema_version"] == 2
    assert loaded["metadata"] == graph["metadata"]
    assert loaded["api_routes"] == graph["api_routes"]
    assert loaded["edges"] == graph["edges"]
    assert store.stats()["schema_version"] == 2


def test_finalize_is_idempotent():
    graph = _build_v2()
    before_edges = sorted(
        (edge["source"], edge["target"], edge["type"])
        for edge in graph["edges"]
    )
    before_routes = list(graph["api_routes"])

    # Re-finalizing the same graph with the same facts must not append.
    from graph_builder import collect_facts

    facts = collect_facts(str(V2_FIXTURE))
    finalize_graph(graph, facts, root=str(V2_FIXTURE))
    after_edges = sorted(
        (edge["source"], edge["target"], edge["type"])
        for edge in graph["edges"]
    )
    assert after_edges == before_edges
    assert graph["api_routes"] == before_routes


def test_incremental_graph_equals_a_full_rebuild(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(V2_FIXTURE, root)
    indexer = GraphIndexer(root)
    incremental = indexer.index()

    full = build_graph_from_repo(str(root))
    _assert_graphs_equal(incremental, full)

    # An edit that changes a client target must be reflected in both.
    client = root / "client.ts"
    client.write_text(
        client.read_text(encoding="utf-8").replace(
            'fetch("/api/health")', 'fetch("/api/items/42", { method: "POST" })',
        ),
        encoding="utf-8",
    )
    incremental = indexer.apply(changed=["client.ts"])
    full = build_graph_from_repo(str(root))
    _assert_graphs_equal(incremental, full)


def _assert_graphs_equal(left: dict, right: dict) -> None:
    assert left["schema_version"] == right["schema_version"]
    assert left["metadata"] == right["metadata"]
    assert left["api_routes"] == right["api_routes"]
    assert left["summary"] == right["summary"]

    left_nodes = {
        node["id"]: {key: value for key, value in node.items() if key != "pagerank"}
        for node in left["nodes"]
    }
    right_nodes = {
        node["id"]: {key: value for key, value in node.items() if key != "pagerank"}
        for node in right["nodes"]
    }
    assert left_nodes == right_nodes

    left_edges = sorted(
        (edge["source"], edge["target"], edge["type"], edge.get("evidence"))
        for edge in left["edges"]
    )
    right_edges = sorted(
        (edge["source"], edge["target"], edge["type"], edge.get("evidence"))
        for edge in right["edges"]
    )
    assert left_edges == right_edges
