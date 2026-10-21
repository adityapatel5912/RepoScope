"""
test_incremental.py
The invariant that makes the incremental index trustworthy.

Milestone 6.2. An incremental index is only worth having if it produces
the SAME graph a full rebuild would. If it does not, the graph quietly
diverges from the code — and the symptom is not "the index is stale", it
is "the blast radius is wrong" or "the file disappeared from the map",
which is far worse.

This test therefore asserts the strongest possible property:

    incremental_graph == full_rebuild

after every kind of change: an edit, an addition, a deletion, and a
rename.

It is here because a real bug was found by exactly this comparison. The
first implementation of `GraphIndexer.apply()` removed the changed file's
nodes and never re-added them, so the graph SHRANK on every edit — from
24 nodes to 22, with a dangling `imports` edge pointing at a node that
no longer existed. Nothing else caught it: the watcher published the
update, the SSE stream delivered it, the frontend rendered it, and every
unit test passed. The graph was simply wrong.

The graph store's `validate_graph` would also have caught the dangling
edge — so this test asserts that too.
"""
import shutil
import tempfile
from pathlib import Path

import pytest

from graph_builder import GraphIndexer, build_graph_from_repo
from graph_store import validate_graph
from parse_cache import FileFacts, ParseCache, hash_bytes

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A writable copy of the multi-language fixture."""
    target = tmp_path / "repo"
    shutil.copytree(FIXTURES_DIR / "multilang", target)
    return target


def _shape(graph: dict) -> tuple[set, set]:
    """The comparable identity of a graph: its node ids and its edges."""
    nodes = {(n["id"], n.get("type")) for n in graph.get("nodes", [])}
    edges = {
        (e["source"], e["target"], e["type"])
        for e in graph.get("edges", [])
    }
    return nodes, edges


def _indexer(repo: Path) -> GraphIndexer:
    indexer = GraphIndexer(repo, ParseCache(repo / ".reposcope" / "cache.json"))
    indexer.index()
    return indexer


# ── The core invariant ──────────────────────────────────────────────────────

def test_edit_produces_the_same_graph_as_a_full_rebuild(repo: Path):
    """Editing a file must not change the graph's identity."""
    indexer = _indexer(repo)
    before = _shape(indexer.graph)

    target = repo / "helpers.py"
    target.write_text(
        target.read_text(encoding="utf-8")
        + '\n\ndef added_symbol():\n    return "new"\n',
        encoding="utf-8",
    )

    indexer.apply(["helpers.py"])
    incremental = _shape(indexer.graph)
    full = _shape(build_graph_from_repo(str(repo)))

    assert incremental[0] == full[0], "the node sets diverged"
    assert incremental[1] == full[1], "the edge sets diverged"
    assert incremental[0] != before[0], "the edit was not picked up at all"


def test_added_file_produces_the_same_graph_as_a_full_rebuild(repo: Path):
    """A new file must appear, with its symbols and its edges."""
    indexer = _indexer(repo)

    (repo / "extra.py").write_text(
        "from helpers import shout\n\n\ndef extra():\n    return shout('x')\n",
        encoding="utf-8",
    )
    indexer.apply(["extra.py"])
    incremental = _shape(indexer.graph)
    full = _shape(build_graph_from_repo(str(repo)))

    assert incremental == full
    assert any(node_id == "file:extra.py" for node_id, _kind in incremental[0])


def test_deleted_file_produces_the_same_graph_as_a_full_rebuild(repo: Path):
    """A deleted file must disappear — with its edges."""
    indexer = _indexer(repo)

    (repo / "extra.py").write_text("def extra():\n    return 1\n", encoding="utf-8")
    indexer.apply(["extra.py"])
    assert any(node_id == "file:extra.py" for node_id, _ in _shape(indexer.graph)[0])

    (repo / "extra.py").unlink()
    indexer.apply(removed=["extra.py"])
    incremental = _shape(indexer.graph)
    full = _shape(build_graph_from_repo(str(repo)))

    assert incremental == full
    assert not any(node_id == "file:extra.py" for node_id, _ in incremental[0])


def test_renamed_file_produces_the_same_graph_as_a_full_rebuild(repo: Path):
    """A rename changes the module index — every import must be re-resolved."""
    indexer = _indexer(repo)

    (repo / "helpers.py").rename(repo / "helpers2.py")
    indexer.apply(changed=["helpers2.py"], removed=["helpers.py"])
    incremental = _shape(indexer.graph)
    full = _shape(build_graph_from_repo(str(repo)))

    assert incremental == full


def test_a_symbol_rename_updates_the_callers(repo: Path):
    """
    Renaming a function must break the call edge to it.

    This is the case a naive incremental index gets wrong: the caller
    did not change, so a naive patcher leaves the old edge in place.
    """
    indexer = _indexer(repo)

    helpers = repo / "helpers.py"
    source = helpers.read_text(encoding="utf-8")
    assert "def shout" in source

    helpers.write_text(source.replace("def shout", "def yell"), encoding="utf-8")
    indexer.apply(["helpers.py"])

    node_ids = {node["id"] for node in indexer.graph["nodes"]}
    call_edges = {
        (e["source"], e["target"])
        for e in indexer.graph["edges"]
        if e["type"] == "calls"
    }

    # The exact ids — "shout_loud" in app.py also contains "shout", so a
    # substring test would pass for the wrong reason.
    assert "func:helpers.py:shout" not in node_ids
    assert "func:helpers.py:yell" in node_ids
    assert not any(target == "func:helpers.py:shout" for _source, target in call_edges)


def test_an_unchanged_file_is_not_reparsed(repo: Path):
    """Re-saving the same bytes must not re-parse anything."""
    indexer = _indexer(repo)
    target = repo / "helpers.py"

    # Bytes, not text: writing text on Windows translates "\n" into
    # "\r\n", which genuinely changes the file — and the cache is
    # content-addressed, so it would (correctly) re-parse.
    target.write_bytes(target.read_bytes())
    indexer.apply(["helpers.py"])

    assert indexer.last_update["reparsed"] == 0
    assert indexer.last_update["unchanged"] == 1


def test_the_incremental_graph_has_no_dangling_edges(repo: Path):
    """The graph must always satisfy the C10 contract."""
    indexer = _indexer(repo)

    target = repo / "helpers.py"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n\ndef more():\n    return 1\n",
        encoding="utf-8",
    )
    indexer.apply(["helpers.py"])

    problems = validate_graph(indexer.graph)
    assert problems == [], f"the incremental graph broke the contract: {problems}"


# ── The parse cache ─────────────────────────────────────────────────────────

def test_the_cache_is_content_addressed(tmp_path: Path):
    """The key must be the content hash, so a stale entry is impossible."""
    first = tmp_path / "a.py"
    first.write_text("def one():\n    return 1\n", encoding="utf-8")
    digest = hash_bytes(first.read_bytes())

    cache = ParseCache(tmp_path / "cache.json")
    facts = FileFacts(rel="a.py", suffix=".py", size=10, sha256=digest)
    cache.put(facts)

    assert cache.get(digest) is facts
    # A different content, a different key — the old entry is never
    # reachable.
    assert cache.get("0" * 64) is None


def test_the_cache_round_trips_through_disk(tmp_path: Path):
    cache = ParseCache(tmp_path / "cache.json")
    cache.put(FileFacts(rel="a.py", suffix=".py", size=10, sha256="a" * 64,
                        symbols=[{"name": "one", "kind": "function", "line": 1}]))
    cache.save()

    reloaded = ParseCache(tmp_path / "cache.json")
    assert reloaded.load() == 1
    assert reloaded.get("a" * 64).symbols[0]["name"] == "one"


def test_a_corrupt_cache_is_ignored_not_fatal(tmp_path: Path):
    """A cache must never be able to break the index."""
    path = tmp_path / "cache.json"
    path.write_text("{not json at all", encoding="utf-8")

    cache = ParseCache(path)
    assert cache.load() == 0
    assert cache.get("a" * 64) is None


def test_the_cache_evicts_the_least_recently_used_entry(tmp_path: Path):
    cache = ParseCache(tmp_path / "cache.json", max_entries=2)
    cache.put(FileFacts(rel="a", suffix=".py", size=1, sha256="a" * 64))
    cache.put(FileFacts(rel="b", suffix=".py", size=1, sha256="b" * 64))

    # Touch "a" so "b" becomes the least recently used.
    assert cache.get("a" * 64) is not None
    cache.put(FileFacts(rel="c", suffix=".py", size=1, sha256="c" * 64))

    assert cache.get("b" * 64) is None
    assert cache.get("a" * 64) is not None


def test_a_cached_file_is_not_parsed_again(repo: Path, monkeypatch):
    """The cache must actually short-circuit the parse."""
    import graph_builder

    calls: list[str] = []
    original = graph_builder.parse_bytes

    def counting(data, rel, suffix):
        calls.append(rel)
        return original(data, rel, suffix)

    monkeypatch.setattr(graph_builder, "parse_bytes", counting)

    cache = ParseCache(repo / ".reposcope" / "cache.json")
    build_graph_from_repo(str(repo), cache)
    first_pass = len(calls)
    assert first_pass > 0

    calls.clear()
    build_graph_from_repo(str(repo), cache)
    assert len(calls) == 0, "the cache did not prevent a re-parse"


def test_the_cache_directory_is_never_indexed(repo: Path):
    """RepoScope's own index must not become part of the graph."""
    indexer = _indexer(repo)
    node_ids = {node["id"] for node in indexer.graph["nodes"]}
    assert not any(".reposcope" in node_id for node_id in node_ids)
