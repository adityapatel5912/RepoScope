"""
test_impact_simulator.py
Phase 12 verification: Three-hop scored explainable blast-radius simulator,
component score breakdown, API boundaries, test gaps, and propagation paths.
"""
import pytest
from fastapi.testclient import TestClient

import main
from impact_analyzer import compute_blast_radius, generate_impact_narrative


@pytest.fixture()
def client():
    return TestClient(main.app)


def test_three_hop_simulation_structure():
    # Chain: target -> hop1 -> hop2 -> hop3
    # Reverse dependencies: hop1 depends on target, hop2 depends on hop1, hop3 depends on hop2
    graph = {
        "nodes": [
            {"id": "file:core.py", "label": "core.py", "file": "core.py", "type": "file"},
            {"id": "file:service.py", "label": "service.py", "file": "service.py", "type": "file"},
            {"id": "file:router.py", "label": "router.py", "file": "router.py", "type": "file", "roles": ["route"]},
            {"id": "file:client.ts", "label": "client.ts", "file": "client.ts", "type": "file"},
            {"id": "file:test_core.py", "label": "test_core.py", "file": "test_core.py", "type": "file"},
        ],
        "edges": [
            {"source": "file:service.py", "target": "file:core.py", "type": "imports"},
            {"source": "file:router.py", "target": "file:service.py", "type": "imports"},
            {"source": "file:client.ts", "target": "file:router.py", "type": "api_calls"},
            {"source": "file:test_core.py", "target": "file:core.py", "type": "calls"},
        ],
    }

    blast = compute_blast_radius(graph, "file:core.py", max_depth=3)
    assert blast["target"]["id"] == "file:core.py"
    assert blast["max_depth"] == 3
    assert len(blast["hops"]) == 3

    # Hop 1: service.py
    hop1 = blast["hops"][0]
    assert hop1["hop"] == 1
    assert any(n["id"] == "file:service.py" for n in hop1["nodes"])

    # Hop 2: router.py
    hop2 = blast["hops"][1]
    assert hop2["hop"] == 2
    assert any(n["id"] == "file:router.py" for n in hop2["nodes"])

    # Hop 3: client.ts
    hop3 = blast["hops"][2]
    assert hop3["hop"] == 3
    assert any(n["id"] == "file:client.ts" for n in hop3["nodes"])

    # API boundaries
    assert len(blast["api_boundaries"]) >= 1
    assert any(b["id"] == "file:router.py" for b in blast["api_boundaries"])

    # Score breakdown
    breakdown = blast["score_breakdown"]
    assert breakdown["direct_callers"] == 2
    assert breakdown["transitive_callers"] == 2
    assert breakdown["api_boundaries"] >= 1
    assert breakdown["raw_score"] > 0
    assert 1 <= breakdown["normalized_score"] <= 10

    # Explanation paths
    paths = blast["explanation_paths"]
    assert len(paths) >= 1
    router_path = next((p for p in paths if "router.py" in p["target"]), None)
    assert router_path is not None
    assert "core.py" in router_path["path"]


def test_deterministic_narrative_generation():
    impact = {
        "target": {"id": "db.py", "label": "db.py", "file": "db.py"},
        "direct_impacts": [{"id": "user.py", "label": "user.py"}],
        "transitive_impacts": [{"id": "auth.py", "label": "auth.py"}, {"id": "app.py", "label": "app.py"}],
        "api_boundaries": [{"id": "app.py", "label": "/api/v1/auth"}],
        "test_gaps": [{"id": "auth.py", "label": "auth.py"}],
        "suggested_tests": ["test_db.py", "test_user.py"],
        "risk_level": "high",
        "risk_score": 7,
    }
    narrative = generate_impact_narrative(impact, provider=None)
    assert "db.py" in narrative
    assert "high risk" in narrative
    assert "1 direct" in narrative
    assert "2 transitive" in narrative
    assert "public API boundaries" in narrative
    assert "test coverage" in narrative


def test_impact_analyze_endpoint_three_hop(client, monkeypatch):
    graph = {
        "nodes": [
            {"id": "file:main.py", "label": "main.py", "file": "main.py", "type": "file"},
            {"id": "file:worker.py", "label": "worker.py", "file": "worker.py", "type": "file"},
        ],
        "edges": [
            {"source": "file:worker.py", "target": "file:main.py", "type": "imports"},
        ],
    }
    monkeypatch.setattr(main, "load_state", lambda: {"repo": "test/repo", "local_path": "."})
    monkeypatch.setattr(main, "build_graph_from_repo", lambda path: graph)

    res = client.post("/api/impact/analyze", json={"target": "main.py", "max_depth": 3})
    assert res.status_code == 200
    data = res.json()
    assert "hops" in data
    assert len(data["hops"]) == 3
    assert "score_breakdown" in data
    assert "narrative" in data
    assert data["total_impacted"] == 1
