"""
test_graph_source.py
One repository, one graph, one answer.

A P1 that the browser-QA harness caught: the analysis endpoints and the
web UI could describe **different codebases at the same time**.

The repo-map panel showed a map built from the LIVE SESSION's graph
(7.9k tokens — the RepoScope repository) next to a "full repository"
figure measured against the STATE FILE's root (1.3k tokens — a nine-file
test fixture). Both numbers were true. The claim they supported was
nonsense.

There were two sources for "the current graph": the live session and
the orchestrator's cache. A request could read one from each. The fix
is a single function — `orchestrator.current_graph()` — that returns the
graph AND the root it describes, so no caller can pair a graph with the
wrong baseline.

These tests pin that invariant.
"""
import shutil
import tempfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """
    Point the state file at a temporary location.

    `load_local_repo` writes the state, and the state is what says which
    repository is active. A test must not write the developer's real
    `data/repo_state.json`.
    """
    import repo_tracker

    state_path = tmp_path / "repo_state.json"
    monkeypatch.setattr(repo_tracker, "STATE", state_path)
    return state_path


def test_the_graph_and_its_root_describe_the_same_repository(isolated_state):
    """`current_graph()` must return a graph and the root it belongs to."""
    from orchestrator import clear_graph_cache, current_graph
    from repo_loader import load_local_repo

    root = FIXTURES_DIR / "multilang"
    load_local_repo(str(root))
    clear_graph_cache()

    graph, described_root = current_graph()

    assert graph.get("nodes"), "no graph was produced"
    assert described_root == str(root.resolve())

    # And the graph really is THAT repository's.
    labels = {n.get("label") for n in graph["nodes"] if n.get("type") == "file"}
    assert "app.py" in labels
    assert "helpers.py" in labels


def test_loading_a_second_repository_switches_both(isolated_state):
    """The graph AND the root must change together."""
    from orchestrator import clear_graph_cache, current_graph
    from repo_loader import load_local_repo

    load_local_repo(str(FIXTURES_DIR / "multilang"))
    clear_graph_cache()
    first_graph, first_root = current_graph()

    load_local_repo(str(FIXTURES_DIR / "circular"))
    clear_graph_cache()
    second_graph, second_root = current_graph()

    assert first_root != second_root
    assert first_root.endswith("multilang")
    assert second_root.endswith("circular")

    first_labels = {n.get("label") for n in first_graph["nodes"] if n.get("type") == "file"}
    second_labels = {n.get("label") for n in second_graph["nodes"] if n.get("type") == "file"}
    assert "app.py" in first_labels
    assert "alpha.py" in second_labels
    assert "app.py" not in second_labels


def test_the_repo_map_measures_its_baseline_against_its_own_graph(isolated_state):
    """
    The map and the baseline must describe the SAME repository.

    This is the assertion that would have caught the P1. The reduction
    percentage is only meaningful when both numbers come from the same
    codebase.
    """
    from orchestrator import clear_graph_cache, current_graph
    from repo_loader import load_local_repo
    from repo_map import build_repo_map_with_metrics

    root = FIXTURES_DIR / "multilang"
    load_local_repo(str(root))
    clear_graph_cache()

    graph, described_root = current_graph()
    assert described_root == str(root.resolve())

    metrics = build_repo_map_with_metrics(graph, described_root)

    # The baseline was measured against a real directory, so it is
    # non-zero.
    assert metrics["full_context_tokens"] > 0
    # The map is smaller than the code it replaces — otherwise the
    # "saving" is negative and the panel would show 0%.
    assert metrics["tokens"] < metrics["full_context_tokens"]
    assert metrics["reduction_pct"] > 0

    # And the map really describes this repository.
    paths = {entry["path"] for entry in metrics["entries"]}
    assert any(path.endswith(".py") for path in paths)
    assert all(
        (Path(described_root) / path).exists()
        for path in paths
    ), "the map names a file that does not exist in the described root"


def test_the_repo_map_of_a_tiny_repository_is_still_honest(tmp_path, isolated_state):
    """
    A repository smaller than the map must not produce a fake saving.

    If the code is smaller than the map that describes it, there is
    nothing to save — and claiming a reduction would be a lie.
    """
    from orchestrator import clear_graph_cache, current_graph
    from repo_loader import load_local_repo
    from repo_map import build_repo_map_with_metrics

    tiny = tmp_path / "tiny"
    tiny.mkdir()
    (tiny / "one.py").write_text("def only():\n    return 1\n", encoding="utf-8")

    load_local_repo(str(tiny))
    clear_graph_cache()

    graph, described_root = current_graph()
    metrics = build_repo_map_with_metrics(graph, described_root)

    # The reduction is clamped at zero rather than going negative — a
    # negative "saving" is not a saving.
    assert metrics["reduction_pct"] >= 0
    assert metrics["full_context_tokens"] > 0
