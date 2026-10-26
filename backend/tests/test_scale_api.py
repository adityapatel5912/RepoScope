"""
test_scale_api.py
The endpoints Sprint 7 added to the analysis router.

Sprint 7 shipped three graph questions that are not drawn on the canvas:

    GET /api/analysis/critical-path  — betweenness, computed on demand
    GET /api/analysis/workspaces     — monorepo detection (M9.1)
    GET /api/analysis/ownership      — who owns each file (M9.4)

The modules have their own unit tests in `test_scale.py`. These tests go
through the ROUTER, because the bugs that matter here are wiring bugs:
a missing state field, a sync call in an async endpoint, a shape the
client cannot read.
"""
import asyncio
import subprocess
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Never write the developer's real `data/repo_state.json`."""
    import repo_tracker

    state_path = tmp_path / "repo_state.json"
    monkeypatch.setattr(repo_tracker, "STATE", state_path)
    return state_path


def test_the_critical_path_endpoint_returns_ranked_nodes(isolated_state):
    """
    Betweenness is computed on demand — the endpoint is the "on demand".
    """
    from api.routers import analysis
    from repo_loader import load_local_repo

    load_local_repo(str(FIXTURES_DIR / "circular"))

    result = asyncio.run(analysis.critical_path(limit=5))

    assert result["available"] is True
    assert result["nodes"]
    assert len(result["nodes"]) <= 5
    scores = [node["betweenness"] for node in result["nodes"]]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > 0
    for node in result["nodes"]:
        assert node["id"]
        assert node["label"]


def test_the_workspaces_endpoint_reports_an_ordinary_repository(isolated_state):
    """An empty list is the right answer for a normal repository."""
    from api.routers import analysis
    from repo_loader import load_local_repo

    load_local_repo(str(FIXTURES_DIR / "multilang"))

    result = asyncio.run(analysis.workspaces())

    assert result["available"] is True
    assert result["workspaces"] == []
    assert result["count"] == 0
    assert result["is_monorepo"] is False


def test_the_ownership_endpoint_reads_a_real_git_history(
    isolated_state, tmp_path,
):
    """
    The endpoint must combine the git history with the churn, and must
    name the file's owner — not just return a count.
    """
    from api.routers import analysis
    from repo_loader import load_local_repo

    root = tmp_path / "owned"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")

    def git(*args):
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)

    git("init", "-q")
    git("config", "user.email", "dev@example.com")
    git("config", "user.name", "Ada Lovelace")
    git("add", ".")
    git("commit", "-q", "-m", "first")

    load_local_repo(str(root))

    result = asyncio.run(analysis.ownership())

    assert result["available"] is True
    paths = {entry["path"]: entry for entry in result["files"]}
    assert paths["a.py"]["owner"] == "Ada Lovelace"
    assert result["author_count"] == 1
    assert result["top_authors"][0]["author"] == "Ada Lovelace"


def test_the_ownership_endpoint_says_why_it_cannot_answer(
    isolated_state, tmp_path,
):
    """No git is a normal state, not a 500."""
    from api.routers import analysis
    from repo_loader import load_local_repo

    root = tmp_path / "plain"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    load_local_repo(str(root))

    result = asyncio.run(analysis.ownership())

    assert result["available"] is False
    assert result["files"] == []
    assert result["reason"]
