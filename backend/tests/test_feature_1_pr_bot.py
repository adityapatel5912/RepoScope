"""
test_feature_1_pr_bot.py
POST /api/impact/pr — blast-radius report for a PR, rendered as GitHub
markdown (risk score, affected files, suggested tests, mermaid).
"""
import pytest
from fastapi.testclient import TestClient

import main
from pr_impact import build_pr_impact


@pytest.fixture()
def client():
    return TestClient(main.app)


@pytest.fixture()
def graph_repo(tmp_path, monkeypatch):
    """mini repo: consumer.py imports lib.py; lib.py imports util.py"""
    (tmp_path / "util.py").write_text("def u():\n    return 1\n")
    (tmp_path / "lib.py").write_text("import util\n\ndef l():\n    return util.u()\n")
    (tmp_path / "consumer.py").write_text("import lib\n\ndef c():\n    return lib.l()\n")
    state = {"repo": "octo/tiny", "local_path": str(tmp_path), "readme": "# x"}
    monkeypatch.setattr(main, "load_state", lambda: state)
    return tmp_path


PR_META = {"number": 7, "title": "Change lib", "state": "open"}
PR_FILES = [
    {"filename": "lib.py", "status": "modified", "additions": 4, "deletions": 2,
     "patch": "+def l(x):\n-    return util.u()\n+    return util.u() + x\n"},
]


def test_build_pr_impact_pure(graph_repo):
    graph = main.build_graph_from_repo(str(graph_repo))
    out = build_pr_impact(graph, PR_META, PR_FILES)
    assert out["pr_number"] == 7
    assert 1 <= out["risk_score"] <= 10
    assert out["risk_level"] in ("low", "medium", "high", "critical")
    assert out["affected_files"][0]["file"] == "lib.py"
    assert out["affected_files"][0]["in_graph"] is True
    # lib.py is imported by consumer.py → at least one direct impact
    assert out["direct_total"] >= 1
    # GitHub-ready markdown contract
    assert "RepoScope PR Impact Report" in out["comment"]
    assert "Risk score" in out["comment"]
    assert "```mermaid" in out["comment"]
    assert "Suggested tests" in out["comment"]


def test_build_pr_impact_unknown_file(graph_repo):
    graph = main.build_graph_from_repo(str(graph_repo))
    out = build_pr_impact(graph, PR_META, [
        {"filename": "does/not/exist.py", "status": "added",
         "additions": 1, "deletions": 0},
    ])
    assert out["affected_files"][0]["in_graph"] is False
    assert out["risk_score"] >= 1  # a change still carries baseline risk


def test_impact_pr_endpoint(client, graph_repo, monkeypatch):
    async def fake_fetch_pr(owner, repo, pr_number, token=None):
        assert (owner, repo, pr_number) == ("octo", "tiny", 7)
        return PR_META, PR_FILES

    monkeypatch.setattr(main, "fetch_pr", fake_fetch_pr)
    res = client.post("/api/impact/pr", json={
        "repo_url": "https://github.com/octo/tiny",
        "pr_number": 7,
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["pr_title"] == "Change lib"
    assert "impact/pr" in repr(data) or "comment" in data
    assert "RepoScope PR Impact Report" in data["comment"]


def test_impact_pr_bad_url(client, monkeypatch):
    monkeypatch.setattr(main, "load_state",
                        lambda: {"repo": None, "local_path": None})
    res = client.post("/api/impact/pr", json={"repo_url": "not-a-url", "pr_number": 1})
    assert res.status_code == 400
