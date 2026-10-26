"""
test_feature_2_onboard.py
POST /api/onboard — Student Mode learning path: Row-ranked levels, quizzes,
and Good First Issues from the low-traffic bottom rows.
"""
import json

import pytest
from fastapi.testclient import TestClient

import main
import onboarding
from onboarding import rank_rows


@pytest.fixture()
def client():
    return TestClient(main.app)


@pytest.fixture()
def graph_repo(tmp_path, monkeypatch):
    """util is most-imported; orphan.py has no edges (bottom rows)."""
    (tmp_path / "util.py").write_text("def u():\n    return 1\n")
    (tmp_path / "a.py").write_text("import util\n\ndef a():\n    return util.u()\n")
    (tmp_path / "b.py").write_text("import util\n\ndef b():\n    return util.u()\n")
    (tmp_path / "orphan.py").write_text("def o():\n    return 2\n")
    state = {"repo": "octo/tiny", "local_path": str(tmp_path), "readme": "# x"}
    monkeypatch.setattr(main, "load_state", lambda: state)
    return tmp_path


LEVEL_JSON = json.dumps({
    "files": [{"path": "util.py", "why": "Most imported file."}],
    "quiz": [{
        "question": "What does util.py do?",
        "options": ["helpers", "routes", "models", "configs"],
        "answer_index": 0,
        "explanation": "It holds shared helpers.",
    }],
})

GFI_JSON = json.dumps({
    "issues": [{
        "title": "Document orphan.py",
        "file": "orphan.py",
        "description": "No dependents — safe to document.",
        "hint": "Add a module docstring.",
    }]
})


def test_rank_rows_orders_by_connectivity(graph_repo):
    graph = main.build_graph_from_repo(str(graph_repo))
    rows = rank_rows(graph)
    assert rows[1], "row 1 (backbone) should be non-empty"
    assert rows[1][0]["label"] == "util.py"  # 2 incoming → highest score
    all_rows = [n["label"] for r in rows.values() for n in r]
    assert "orphan.py" in all_rows  # edge-less file still lands somewhere
    # orphan has no incoming edges → must NOT be in row 1
    assert "orphan.py" not in [n["label"] for n in rows[1]]


def test_build_onboarding_shapes(graph_repo, monkeypatch):
    monkeypatch.setattr(onboarding, "ask_llm", lambda *a, **k: LEVEL_JSON)
    # GFI call gets its own JSON — route by prompt content
    def fake_ask(system, prompt, graph_context="", provider=None):
        return GFI_JSON if "Good First Issues" in prompt else LEVEL_JSON
    monkeypatch.setattr(onboarding, "ask_llm", fake_ask)

    graph = main.build_graph_from_repo(str(graph_repo))
    out = onboarding.build_onboarding(graph, provider={"source": "byok"})
    assert len(out["levels"]) == 3
    l1, l2, l3 = out["levels"]
    assert (l1["level"], l2["level"], l3["level"]) == (1, 2, 3)
    assert l1["files"], "level 1 must list entry files"
    assert all("why" in f for lv in out["levels"] for f in lv["files"])
    assert len(out["good_first_issues"]) >= 1
    gfi = out["good_first_issues"][0]
    assert {"title", "file", "description", "hint"} <= set(gfi.keys())


def test_build_onboarding_llm_failure_falls_back(graph_repo, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(onboarding, "ask_llm", boom)
    graph = main.build_graph_from_repo(str(graph_repo))
    out = onboarding.build_onboarding(graph, provider=None)
    assert len(out["levels"]) == 3                     # still usable
    assert out["levels"][0]["files"]
    assert out["good_first_issues"]                    # heuristic GFIs


def test_onboard_endpoint(client, graph_repo, monkeypatch):
    def fake_ask(system, prompt, graph_context="", provider=None):
        return GFI_JSON if "Good First Issues" in prompt else LEVEL_JSON
    monkeypatch.setattr(onboarding, "ask_llm", fake_ask)
    res = client.post("/api/onboard", json={})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["repo"] == "octo/tiny"
    assert len(data["levels"]) == 3
