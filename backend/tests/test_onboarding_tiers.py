"""
test_onboarding_tiers.py
Unit and integration tests for Phase 9: Topological Student Onboarding (V2.7).
Verifies Tarjan SCC condensation, topological tiering, challenge generation,
and graph-graded challenge verification.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from onboarding import (
    tarjan_scc,
    condense_dag,
    compute_topological_layers,
    build_topological_curriculum,
    verify_curriculum_challenge,
)

pytestmark = pytest.mark.usefixtures("fake_ai_provider")


def test_tarjan_scc_and_condense_dag():
    # Graph with cycle: A -> B -> C -> A, and C -> D (leaf)
    nodes = ["A", "B", "C", "D"]
    forward = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A", "D"],
        "D": [],
    }

    sccs = tarjan_scc(nodes, forward)
    assert len(sccs) == 2
    # One SCC has 3 nodes (A, B, C), one has 1 node (D)
    lens = sorted([len(c) for c in sccs])
    assert lens == [1, 3]

    scc_members, dag_forward, node_to_scc = condense_dag(nodes, forward)
    # The condensed graph must have 2 meta-nodes
    assert len(scc_members) == 2
    # Meta-node containing D has out-degree 0
    d_scc = node_to_scc["D"]
    assert dag_forward[d_scc] == []
    # Meta-node containing (A, B, C) has edge to D's SCC
    abc_scc = node_to_scc["A"]
    assert dag_forward[abc_scc] == [d_scc]

    layers = compute_topological_layers(scc_members, dag_forward)
    assert layers[d_scc] == 0  # leaf
    assert layers[abc_scc] == 1  # depends on D


def test_build_topological_curriculum_structure():
    graph = {
        "nodes": [
            {"id": "file:main.py", "label": "main.py", "type": "file"},
            {"id": "file:app/api.py", "label": "app/api.py", "type": "file"},
            {"id": "file:app/models.py", "label": "app/models.py", "type": "file"},
            {"id": "file:app/utils.py", "label": "app/utils.py", "type": "file"},
        ],
        "edges": [
            {"source": "file:main.py", "target": "file:app/api.py"},
            {"source": "file:app/api.py", "target": "file:app/models.py"},
            {"source": "file:app/api.py", "target": "file:app/utils.py"},
            {"source": "file:app/models.py", "target": "file:app/utils.py"},
        ],
    }

    curriculum = build_topological_curriculum(graph)
    assert curriculum["ok"] is True
    assert curriculum["total_tiers"] == 4
    assert len(curriculum["tiers"]) == 4

    t1 = curriculum["tiers"][0]
    assert t1["tier"] == 1
    assert "Foundations" in t1["name"]
    assert len(t1["challenges"]) >= 1

    t4 = curriculum["tiers"][3]
    assert t4["tier"] == 4
    assert "Entrypoints" in t4["name"] or "APIs" in t4["name"]


def test_verify_curriculum_challenge():
    graph = {
        "nodes": [
            {"id": "file:main.py", "label": "main.py", "type": "file"},
            {"id": "file:app/utils.py", "label": "app/utils.py", "type": "file"},
        ],
        "edges": [
            {"source": "file:main.py", "target": "file:app/utils.py"},
        ],
    }
    curriculum = build_topological_curriculum(graph)
    t1 = curriculum["tiers"][0]
    ch1 = t1["challenges"][0]
    correct_idx = ch1["answer_index"]

    # Verify correct numeric index
    res_correct = verify_curriculum_challenge(curriculum, 1, ch1["id"], str(correct_idx))
    assert res_correct["ok"] is True
    assert res_correct["correct"] is True
    assert res_correct["unlocked"] is True

    # Verify incorrect answer
    wrong_idx = (correct_idx + 1) % 4
    res_wrong = verify_curriculum_challenge(curriculum, 1, ch1["id"], str(wrong_idx))
    assert res_wrong["ok"] is True
    assert res_wrong["correct"] is False
    assert res_wrong["unlocked"] is False


def test_api_curriculum_endpoints():
    client = TestClient(app)
    # GET /api/onboard/curriculum returns 200 or 400 if repo loaded
    res = client.get("/api/onboard/curriculum")
    if res.status_code == 200:
        data = res.json()
        assert data["ok"] is True
        assert "tiers" in data
        assert len(data["tiers"]) == 4

        # Test POST /api/onboard/verify-challenge
        t1 = data["tiers"][0]
        if t1.get("challenges"):
            ch = t1["challenges"][0]
            verify_res = client.post(
                "/api/onboard/verify-challenge",
                json={"tier": 1, "challenge_id": ch["id"], "answer": str(ch["answer_index"])},
            )
            assert verify_res.status_code == 200
            assert verify_res.json()["correct"] is True
