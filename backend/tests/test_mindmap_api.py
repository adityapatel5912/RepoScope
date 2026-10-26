"""
test_mindmap_api.py
L2 contract for `GET /api/mindmap`.

The endpoint is frozen for Phase 2. These tests pin the payload shape,
the empty/absent states, and the deterministic cap.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
import orchestrator
from graph_builder import build_graph_from_repo
from mindmap import count_tree_nodes

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v2_contract"


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def served(client, monkeypatch):
    graph = build_graph_from_repo(str(FIXTURE))
    monkeypatch.setattr(
        orchestrator, "current_graph", lambda: (graph, str(FIXTURE)),
    )
    return client


def _walk(node: dict):
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def test_mindmap_returns_the_frozen_payload(served):
    response = served.get("/api/mindmap")
    assert response.status_code == 200
    payload = response.json()

    assert payload["schema_version"] == 2
    assert payload["generated_at"].endswith("Z")
    assert payload["source"]["root"] == str(FIXTURE)
    assert payload["source"]["nodes"] > 0
    assert payload["stats"]["pillars"] == 6
    assert payload["stats"]["routes"] == 3
    assert payload["stats"]["api_calls"] == 2
    assert [pillar["id"] for pillar in payload["pillars"]] == [
        "frontend", "backend", "data", "infrastructure", "tests", "docs",
    ]
    assert payload["root"]["id"] == "root"
    assert len(payload["root"]["children"]) == 6
    assert payload["truncated"] is False


def test_mindmap_include_symbols_false_truncates_at_file_level(served):
    payload = served.get("/api/mindmap?include_symbols=false").json()
    assert payload["stats"]["symbols"] > 0
    assert all(node["kind"] != "symbol" for node in _walk(payload["root"]))


def test_mindmap_max_nodes_is_deterministic(served):
    first = served.get("/api/mindmap?max_nodes=9").json()
    second = served.get("/api/mindmap?max_nodes=9").json()
    assert count_tree_nodes(first) <= 9
    assert first["truncated"] is True
    assert first["omitted"] > 0
    assert first["max_nodes"] == 9
    # `generated_at` is the only field allowed to differ.
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_mindmap_has_no_duplicate_ids(served):
    payload = served.get("/api/mindmap").json()
    ids = [node["id"] for node in _walk(payload["root"])]
    assert len(ids) == len(set(ids))


def test_mindmap_returns_an_empty_tree_for_an_empty_active_repository(client, monkeypatch):
    monkeypatch.setattr(
        orchestrator, "current_graph", lambda: ({"nodes": [], "edges": []}, "/tmp/empty"),
    )
    response = client.get("/api/mindmap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["root"]["id"] == "root"
    assert all(child["children"] == [] for child in payload["root"]["children"])
    assert payload["stats"]["files"] == 0


def test_mindmap_503_when_no_repository_is_active(client, monkeypatch):
    monkeypatch.setattr(orchestrator, "current_graph", lambda: ({}, None))
    response = client.get("/api/mindmap")
    assert response.status_code == 503
    assert "No repository" in response.json()["detail"]


def test_mindmap_rejects_an_out_of_range_cap(served):
    assert served.get("/api/mindmap?max_nodes=0").status_code == 422
    assert served.get("/api/mindmap?max_nodes=200001").status_code == 422


def test_health_reports_the_v2_schema(client):
    payload = client.get("/api/health").json()
    assert payload["schema_version"] == 2
    assert payload["status"] == "healthy"
