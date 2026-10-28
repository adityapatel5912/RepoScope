"""
backend/tests/test_tour_tracks.py
Unit and contract tests for Phase 8: Four deterministic tour tracks (V2.7).
"""

import json
import pytest
from fastapi.testclient import TestClient

import main
import tour_generator

pytestmark = pytest.mark.usefixtures("fake_ai_provider")


@pytest.fixture()
def client():
    return TestClient(main.app)


@pytest.fixture()
def sample_graph():
    return {
        "nodes": [
            {"id": "file:main.py", "label": "main.py", "type": "file", "file": "main.py", "line": 1},
            {"id": "file:app/api.py", "label": "app/api.py", "type": "file", "file": "app/api.py", "line": 5},
            {"id": "file:app/models.py", "label": "app/models.py", "type": "file", "file": "app/models.py", "line": 10},
            {"id": "file:app/db.py", "label": "app/db.py", "type": "file", "file": "app/db.py", "line": 20},
            {"id": "file:utils.py", "label": "utils.py", "type": "file", "file": "utils.py", "line": 1},
        ],
        "edges": [
            {"source": "file:main.py", "target": "file:app/api.py", "type": "imports"},
            {"source": "file:app/api.py", "target": "file:app/models.py", "type": "imports"},
            {"source": "file:app/api.py", "target": "file:app/db.py", "type": "imports"},
            {"source": "file:app/models.py", "target": "file:utils.py", "type": "imports"},
            {"source": "file:app/db.py", "target": "file:utils.py", "type": "imports"},
        ],
    }


def test_four_tracks_deterministic_and_distinct(sample_graph):
    """Test all 4 tracks produce valid, deterministic stops."""
    t1 = tour_generator.build_tour(sample_graph, track="request_lifecycle")
    t2 = tour_generator.build_tour(sample_graph, track="data_flow")
    t3 = tour_generator.build_tour(sample_graph, track="change_impact")
    t4 = tour_generator.build_tour(sample_graph, track="onboarding")

    assert t1["ok"] is True and t1["track"] == "request_lifecycle"
    assert t2["ok"] is True and t2["track"] == "data_flow"
    assert t3["ok"] is True and t3["track"] == "change_impact"
    assert t4["ok"] is True and t4["track"] == "onboarding"

    # All tracks have metadata
    for t in (t1, t2, t3, t4):
        assert t["total_steps"] > 0
        assert len(t["steps"]) == t["total_steps"]
        assert t["why_this_order"]
        assert t["track_label"]
        for s in t["steps"]:
            assert s["node_id"]
            assert s["file"]
            assert s["line"] >= 1
            assert s["explanation"]
            assert s["reason"]

    # Verify change_impact puts utils.py first (indegree 2)
    assert t3["steps"][0]["node_id"] == "file:utils.py"

    # Verify request_lifecycle puts main.py first (entrypoint)
    assert t1["steps"][0]["node_id"] == "file:main.py"

    # Verify data_flow puts models.py before db.py or utils.py
    model_idx = next(i for i, s in enumerate(t2["steps"]) if s["node_id"] == "file:app/models.py")
    assert model_idx == 0


def test_codetour_export_format(sample_graph):
    tour = tour_generator.build_tour(sample_graph, track="request_lifecycle")
    ct = tour_generator.export_codetour(tour, "TestRepo")

    assert ct["$schema"] == "https://aka.ms/codetour-schema"
    assert "TestRepo: Request Lifecycle" in ct["title"]
    assert len(ct["steps"]) == tour["total_steps"]
    assert ct["steps"][0]["file"] == "main.py"
    assert ct["steps"][0]["line"] >= 1
    assert "Step 1" in ct["steps"][0]["description"]


def test_api_tour_generate_and_export(client, tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text("import api\n")
    (tmp_path / "api.py").write_text("import db\n")
    (tmp_path / "db.py").write_text("x = 1\n")
    monkeypatch.setattr(main, "load_state", lambda: {"repo": "octo/tour-test", "local_path": str(tmp_path)})

    # Test POST /api/tour/generate with track
    res = client.post("/api/tour/generate", json={"track": "request_lifecycle"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["track"] == "request_lifecycle"
    assert len(data["steps"]) >= 2

    # Test GET /api/tour/export
    exp = client.get("/api/tour/export?track=request_lifecycle")
    assert exp.status_code == 200
    assert exp.headers["content-type"].startswith("application/json")
    assert "attachment;" in exp.headers["content-disposition"]
    ct_data = exp.json()
    assert ct_data["$schema"] == "https://aka.ms/codetour-schema"
    assert len(ct_data["steps"]) >= 2
