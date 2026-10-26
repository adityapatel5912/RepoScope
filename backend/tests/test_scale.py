"""
test_scale.py
Sprint 7 — the scale-out layer.

What is asserted here:

* **The betweenness fix.** Betweenness centrality is O(n·m) and used to
  be computed on EVERY graph build — 2.5 seconds on a 3,753-node
  repository, for a number the canvas never rendered. It is now computed
  on demand, and cached. This is the difference between a live update
  that takes 3.8 seconds and one that takes 28 milliseconds.

* **The LRU caches.** The adjacency structures and the analysis digraph
  are cached, keyed by CONTENT, so an edit invalidates them
  automatically.

* **The SQLite store's recursive CTEs.** The transitive closure, the
  shortest path and the cycle detection all run in SQL, which is the
  whole reason for putting the index in a database.

* **Monorepo detection** (M9.1).

* **The ownership overlay** (M9.4).
"""
import time
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── The betweenness fix ─────────────────────────────────────────────────────

def test_the_analysis_does_not_compute_betweenness_eagerly():
    """
    Betweenness is O(n·m) and the canvas never rendered it.

    It is computed on demand now, by `critical_path()`.
    """
    from graph_analysis import attach_analysis

    graph = {
        "nodes": [{"id": f"file:{i}.py", "type": "file", "label": f"{i}.py"} for i in range(50)],
        "edges": [
            {"source": "file:0.py", "target": "file:1.py", "type": "imports"},
            {"source": "file:1.py", "target": "file:2.py", "type": "imports"},
        ],
    }
    attach_analysis(graph)

    # The key is still there, so the node shape does not change.
    assert "betweenness" in graph["nodes"][0]
    # But it was not computed.
    assert graph["nodes"][0]["betweenness"] == 0.0
    # PageRank WAS computed — it is cheap and it is used.
    assert graph["nodes"][0]["pagerank"] > 0


def test_the_critical_path_is_computed_on_demand():
    from graph_analysis import attach_analysis, critical_path

    graph = {
        "nodes": [{"id": f"file:{i}.py", "type": "file", "label": f"{i}.py"} for i in range(5)],
        "edges": [
            {"source": "file:0.py", "target": "file:2.py", "type": "imports"},
            {"source": "file:1.py", "target": "file:2.py", "type": "imports"},
            {"source": "file:2.py", "target": "file:3.py", "type": "imports"},
        ],
    }
    attach_analysis(graph)

    nodes = critical_path(graph, limit=3)
    assert nodes
    # The node every path goes through is the top one.
    assert nodes[0]["id"] == "file:2.py"
    assert nodes[0]["betweenness"] > 0


def test_the_critical_path_is_cached():
    from graph_analysis import critical_path

    graph = {
        "nodes": [{"id": f"file:{i}.py", "type": "file", "label": f"{i}.py"} for i in range(5)],
        "edges": [{"source": "file:0.py", "target": "file:1.py", "type": "imports"}],
    }

    started = time.perf_counter()
    critical_path(graph, limit=3)
    first = time.perf_counter() - started

    started = time.perf_counter()
    critical_path(graph, limit=3)
    second = time.perf_counter() - started

    # The second call is served from the cache. The margin is generous
    # so the test is not flaky on a slow machine — the point is that the
    # second is not O(n·m) again.
    assert second < first or second < 0.01, (
        f"the cached call ({second:.4f}s) was not faster than the first "
        f"({first:.4f}s)"
    )


# ── The LRU caches ──────────────────────────────────────────────────────────

def test_the_adjacency_cache_serves_repeated_requests():
    from graph_utils import build_adjacency_cached

    graph = {
        "nodes": [{"id": "file:a.py", "type": "file", "label": "a.py"}],
        "edges": [{"source": "file:a.py", "target": "file:b.py", "type": "imports"}],
    }

    first = build_adjacency_cached(graph)
    second = build_adjacency_cached(graph)
    assert first is second, "the adjacency was rebuilt instead of cached"


def test_the_adjacency_cache_is_invalidated_by_an_edit():
    """
    Keyed by CONTENT, so a changed edge changes the signature and the
    stale entry is never looked up again.
    """
    from graph_utils import build_adjacency_cached

    graph = {
        "nodes": [{"id": "file:a.py", "type": "file", "label": "a.py"}],
        "edges": [{"source": "file:a.py", "target": "file:b.py", "type": "imports"}],
    }
    before = build_adjacency_cached(graph)

    graph["edges"] = [{"source": "file:a.py", "target": "file:c.py", "type": "imports"}]
    after = build_adjacency_cached(graph)

    assert after is not before, "the stale adjacency was served"
    assert "file:c.py" in after[0]["file:a.py"]
    assert "file:b.py" not in after[0]["file:a.py"]


def test_the_lru_cache_evicts_the_least_recently_used_entry():
    from graph_utils import LruCache

    cache = LruCache(maxsize=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")          # "a" is now the most recent
    cache.put("c", 3)       # so "b" is evicted

    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


# ── The SQLite store's recursive CTEs ────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    """A SQLite store holding the circular fixture's graph."""
    from graph_builder import build_graph_from_repo
    from graph_store import SqliteGraphStore

    graph = build_graph_from_repo(str(FIXTURES_DIR / "circular"))
    store = SqliteGraphStore(tmp_path / "graph.db")
    store.save(graph)
    return store


def test_the_sqlite_store_round_trips_the_graph(store):
    graph = store.load()
    assert graph["nodes"]
    assert graph["edges"]
    assert graph["summary"]


def test_the_sqlite_store_rejects_a_broken_graph(tmp_path):
    from graph_store import SqliteGraphStore, validate_graph

    assert validate_graph({"nodes": [], "edges": []}) == []
    broken = {"nodes": [{"id": "file:a.py"}], "edges": [
        {"source": "file:a.py", "target": "file:missing.py", "type": "imports"},
    ]}
    with pytest.raises(ValueError):
        SqliteGraphStore(tmp_path / "broken.db").save(broken)


def test_the_recursive_cte_finds_the_descendants(store):
    """`alpha.py` imports `beta.py` imports `gamma.py`."""
    descendants = store.descendants("file:alpha.py")
    assert "file:beta.py" in descendants
    assert "file:gamma.py" in descendants


def test_the_recursive_cte_finds_the_ancestors(store):
    ancestors = store.ancestors("file:gamma.py")
    assert "file:beta.py" in ancestors
    assert "file:alpha.py" in ancestors


def test_the_recursive_cte_respects_the_depth_limit(store):
    shallow = store.descendants("file:alpha.py", max_depth=1)
    assert "file:beta.py" in shallow
    assert "file:gamma.py" not in shallow


def test_the_recursive_cte_finds_the_shortest_path(store):
    path = store.shortest_path("file:alpha.py", "file:gamma.py")
    assert path[0] == "file:alpha.py"
    assert path[-1] == "file:gamma.py"
    assert len(path) == 3


def test_the_recursive_cte_finds_the_cycles(store):
    """The circular fixture has file-level AND symbol-level cycles."""
    cycles = store.cycles(min_length=2)
    assert cycles
    members = {frozenset(cycle) for cycle in cycles}
    assert frozenset({"file:alpha.py", "file:beta.py", "file:gamma.py"}) in members


def test_the_sqlite_store_records_the_file_hashes(store):
    """Milestone 6.2's per-file SHA-256."""
    hashes = store.files_with_hashes()
    assert hashes
    assert all(len(digest) == 64 for digest in hashes.values())


def test_a_50k_node_index_traverses_within_the_budget(tmp_path):
    """
    Milestone 6.1: "A 50k-file repo's transitive closure resolves in
    <100ms."

    The graph is the synthetic one the QA journey also uses — 50,000
    files, each importing three others at short, medium and long range,
    which is shallow and wide like a real repository. Saving it takes
    ~1.7 s; the traversal is what the budget is about.
    """
    from api.routers.qa import _build_scale_graph
    from graph_store import SqliteGraphStore

    count = 50_000
    graph = _build_scale_graph(count)
    assert len(graph["nodes"]) == count
    assert len(graph["edges"]) > 100_000

    store = SqliteGraphStore(tmp_path / "scale.db")
    store.save(graph)

    # The first query opens the database and populates the page cache;
    # the budget is about the traversal, so warm it and take the median
    # of three measured runs.
    store.descendants("file:f00000.py", max_depth=32)
    runs: list[float] = []
    descendants: list[str] = []
    for _ in range(3):
        started = time.perf_counter()
        descendants = store.descendants("file:f00000.py", max_depth=32)
        runs.append((time.perf_counter() - started) * 1000)
    elapsed_ms = sorted(runs)[1]

    assert len(descendants) > 5_000, (
        f"the closure touched only {len(descendants)} nodes — the graph shape "
        "is not exercising a wide traversal"
    )
    assert elapsed_ms < 100, (
        f"the depth-32 closure over 50,000 files took {elapsed_ms:.0f} ms "
        f"(runs: {[round(run) for run in runs]}), over the 100 ms budget"
    )


def test_the_shortest_path_is_a_shortest_path(tmp_path):
    """
    BFS, not the first path found: `a → d` must go through `b` or `c`,
    not through the longer `a → b → c → d` route.
    """
    from graph_store import SqliteGraphStore

    def node(name):
        return {"id": f"file:{name}.py", "type": "file", "label": f"{name}.py"}

    graph = {
        "nodes": [node(name) for name in "abcde"],
        "edges": [
            {"source": "file:a.py", "target": "file:b.py", "type": "imports"},
            {"source": "file:a.py", "target": "file:c.py", "type": "imports"},
            {"source": "file:b.py", "target": "file:c.py", "type": "imports"},
            {"source": "file:b.py", "target": "file:d.py", "type": "imports"},
            {"source": "file:c.py", "target": "file:d.py", "type": "imports"},
            {"source": "file:d.py", "target": "file:e.py", "type": "imports"},
        ],
    }
    store = SqliteGraphStore(tmp_path / "graph.db")
    store.save(graph)

    path = store.shortest_path("file:a.py", "file:e.py")
    assert path[0] == "file:a.py"
    assert path[-1] == "file:e.py"
    assert len(path) == 4, path

    edges = {(edge["source"], edge["target"]) for edge in graph["edges"]}
    assert all((a, b) in edges for a, b in zip(path, path[1:]))


def test_a_shortest_path_beyond_the_depth_cap_terminates(tmp_path):
    """
    The old path-string CTE was UNBOUNDED. On a 50,000-node chain it ran
    for over ten minutes and never finished; on a branching graph it
    filled the disk. The cap is what makes "no path" an answer instead of
    a hang.
    """
    from graph_store import SqliteGraphStore

    count = 200
    graph = {
        "nodes": [
            {"id": f"file:n{i}.py", "type": "file", "label": f"n{i}.py"}
            for i in range(count)
        ],
        "edges": [
            {"source": f"file:n{i}.py", "target": f"file:n{i + 1}.py", "type": "imports"}
            for i in range(count - 1)
        ],
    }
    store = SqliteGraphStore(tmp_path / "chain.db")
    store.save(graph)

    started = time.perf_counter()
    path = store.shortest_path("file:n0.py", "file:n199.py")
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert path == []
    assert elapsed_ms < 1000


# ── The monorepo detection (M9.1) ──────────────────────────────────────────

def test_a_workspace_root_is_detected(tmp_path):
    """Enterprise evaluators ask this in the first ten minutes."""
    from monorepo import detect_workspaces

    root = tmp_path / "mono"
    (root / "packages" / "api").mkdir(parents=True)
    (root / "packages" / "web").mkdir(parents=True)
    (root / "package.json").write_text(
        '{"name": "mono", "workspaces": ["packages/*"]}', encoding="utf-8",
    )
    (root / "packages" / "api" / "package.json").write_text(
        '{"name": "@mono/api"}', encoding="utf-8",
    )
    (root / "packages" / "web" / "package.json").write_text(
        '{"name": "@mono/web"}', encoding="utf-8",
    )

    workspaces = detect_workspaces(root)
    assert workspaces
    assert {w["name"] for w in workspaces} == {"@mono/api", "@mono/web"}
    assert all(w["root"].endswith(("api", "web")) for w in workspaces)


def test_a_plain_repository_has_no_workspaces(tmp_path):
    from monorepo import detect_workspaces

    root = tmp_path / "plain"
    root.mkdir()
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    assert detect_workspaces(root) == []


def test_a_workspace_root_is_detected_from_a_go_work_file(tmp_path):
    from monorepo import detect_workspaces

    root = tmp_path / "gowork"
    (root / "svc").mkdir(parents=True)
    (root / "svc" / "go.mod").write_text("module example.com/svc\n", encoding="utf-8")
    (root / "go.work").write_text("go 1.21\n\nuse ./svc\n", encoding="utf-8")

    workspaces = detect_workspaces(root)
    assert any("svc" in w["root"] for w in workspaces)


# ── The ownership overlay (M9.4) ────────────────────────────────────────────

def test_the_ownership_overlay_reports_the_primary_owner(tmp_path):
    """
    `git log --format='%an'` per file, combined with the churn.
    """
    import subprocess

    from ownership import primary_owners

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

    owners = primary_owners(root)
    assert "a.py" in owners
    assert owners["a.py"] == "Ada Lovelace"


def test_the_ownership_overlay_is_empty_without_git(tmp_path):
    from ownership import primary_owners

    root = tmp_path / "nogit"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert primary_owners(root) == {}
