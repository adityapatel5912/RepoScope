"""Index freshness: what counts as a source change, and what does not.

The MCP server rebuilds a persisted index when a source file is newer
than the index. Before this test existed, `newest_source_mtime` walked
EVERY file, so the local server's own `backend/logs/app.log` was always
newer than the last build. The MCP server therefore rebuilt a 347-file
graph on every launch, and a cold start could outlast the client's
startup timeout.
"""
import os
import time

from graph_builder import build_graph_from_repo, newest_source_mtime
from graph_store import JsonGraphStore
from mcp_server.server import _index_is_current


def _write(path, text, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_newest_source_mtime_ignores_logs_and_artifacts(tmp_path):
    now = time.time()
    _write(tmp_path / "main.py", "x = 1\n", now - 100)
    _write(tmp_path / "app.log", "a line was written\n", now)
    _write(tmp_path / "shot.png", "not really a png\n", now)
    assert newest_source_mtime(tmp_path) == now - 100


def test_an_index_stays_current_when_only_an_artifact_changes(tmp_path):
    now = time.time()
    _write(tmp_path / "main.py", "x = 1\n", now - 100)
    store = JsonGraphStore(tmp_path / ".reposcope" / "graph.json")
    store.save(build_graph_from_repo(str(tmp_path)))

    _write(tmp_path / "app.log", "the server kept writing\n", now + 100)
    assert _index_is_current(store, tmp_path), (
        "a log file must not make the index look stale"
    )


def test_a_source_edit_makes_the_index_stale(tmp_path):
    now = time.time()
    _write(tmp_path / "main.py", "x = 1\n", now - 100)
    store = JsonGraphStore(tmp_path / ".reposcope" / "graph.json")
    store.save(build_graph_from_repo(str(tmp_path)))

    _write(tmp_path / "main.py", "x = 2\n", now + 100)
    assert not _index_is_current(store, tmp_path), (
        "a source edit must force a rebuild"
    )
