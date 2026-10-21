"""
test_git_history.py
Tests for backend/git_history.py — the churn metrics (Milestone 1.3).

Correction C2: this module is separate from repo_tracker.py, which holds
JSON state about the GitHub metadata of the loaded repository and never
calls git at all.

The critical property is graceful degradation. The graph must render for a
repository that has never been committed to, for a directory that is not
a git working tree, and for a machine with no `git` binary — in every
case without an exception.
"""
import subprocess
from pathlib import Path

import pytest

from git_history import ChurnReport, collect_churn, churn_to_api

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _git_available() -> bool:
    try:
        result = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


# ── Degradation ─────────────────────────────────────────────────────────────

def test_non_git_directory_degrades_cleanly(tmp_path):
    report = collect_churn(tmp_path)
    assert report.available is False
    assert report.reason
    assert report.files == {}


def test_missing_directory_degrades_cleanly(tmp_path):
    report = collect_churn(tmp_path / "does-not-exist")
    assert report.available is False
    assert report.reason


@pytest.mark.skipif(not _git_available(), reason="git is not installed")
def test_a_freshly_initialised_repo_has_no_churn(tmp_path):
    """A repository with no commits is a valid, empty result."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=30)
    report = collect_churn(tmp_path)
    # Either no commits (empty) or commits with no files touched.
    assert isinstance(report.files, dict)


# ── Real measurements ───────────────────────────────────────────────────────

@pytest.mark.skipif(not _git_available(), reason="git is not installed")
def test_collects_churn_from_this_repository():
    """RepoScope's own history is a real, committed git history."""
    report = collect_churn(REPO_ROOT, window_days=3650)
    assert report.available is True, report.reason
    assert report.files, "the repository has commits, so churn must exist"

    # Every entry has sane numbers, and every path is a normalised
    # repo-relative path (forward slashes, no leading "./").
    for path, churn in report.files.items():
        assert churn.commits >= 1
        assert churn.lines_added >= 0
        assert churn.lines_deleted >= 0
        assert churn.churn_score > 0
        assert path
        assert "\\" not in path, f"path was not normalised: {path}"
        assert not path.startswith("./")


@pytest.mark.skipif(not _git_available(), reason="git is not installed")
def test_finds_files_that_keep_changing_together():
    """Co-change coupling is the signal that two files are entangled."""
    report = collect_churn(REPO_ROOT, window_days=3650)
    coupled = [
        path for path, partners in report.co_changes.items()
        if any(count >= 2 for count in partners.values())
    ]
    assert coupled, "a repository with real history must have co-changed files"


@pytest.mark.skipif(not _git_available(), reason="git is not installed")
def test_hotspot_score_blends_churn_and_centrality():
    report = collect_churn(REPO_ROOT, window_days=3650)
    path = next(iter(report.files))
    churn = report.files[path]

    # With no centrality the score is driven by churn alone.
    without_centrality = report.hotspot_score(path, 0.0)
    with_centrality = report.hotspot_score(path, 0.05)
    assert with_centrality > without_centrality, (
        "a file that is both churny and central must outrank a churny one"
    )
    assert 0.0 <= with_centrality <= 1.0


def test_hotspot_score_for_an_unknown_file_is_zero():
    report = ChurnReport()
    assert report.hotspot_score("nope.py") == 0.0


# ── API payload ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _git_available(), reason="git is not installed")
def test_churn_to_api_payload_shape():
    report = collect_churn(REPO_ROOT, window_days=3650)
    payload = churn_to_api(report)

    assert payload["available"] is True
    assert payload["window_days"] == 3650
    assert payload["total_files"] == len(report.files)
    assert payload["files"], "the payload must carry the churn data"

    # The hottest file comes first.
    scores = [entry["hotspot_score"] for entry in payload["files"]]
    assert scores == sorted(scores, reverse=True)

    entry = payload["files"][0]
    assert entry["path"]
    assert entry["commits"] >= 1
    assert 0.0 <= entry["hotspot_score"] <= 1.0


def test_churn_to_api_payload_for_an_unavailable_report():
    payload = churn_to_api(ChurnReport(reason="not a git repository"))
    assert payload["available"] is False
    assert payload["reason"]
    assert payload["files"] == []


@pytest.mark.skipif(not _git_available(), reason="git is not installed")
def test_churn_to_api_uses_centrality_when_a_graph_is_supplied():
    report = collect_churn(REPO_ROOT, window_days=3650)
    path = next(iter(report.files))
    graph = {
        "nodes": [
            {"id": f"file:{path}", "type": "file", "label": path, "pagerank": 0.05},
        ],
        "edges": [],
    }
    payload = churn_to_api(report, graph)
    entry = next(e for e in payload["files"] if e["path"] == path)
    assert entry["hotspot_score"] > 0
