"""
backend/tests/test_context_compressor.py
Tests for context_compressor module.
"""

import json
import os
from pathlib import Path
import pytest

from context_compressor import (
    CONTEXT_SCHEMA_VERSION,
    DEFAULT_BUDGET_TOKENS,
    MAX_BODY_CHARS,
    MAX_BODY_LINES,
    MIN_BUDGET_TOKENS,
    ContextError,
    build_ast_skeleton,
    build_context_pack,
    context_hash,
    decode_toon,
    encode_json,
    encode_toon,
    normalize_signature,
    resolve_context_path,
    toon_available,
)


@pytest.fixture
def sample_graph(tmp_path: Path):
    """Fixture providing a sample repository and corresponding graph."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_a = repo_dir / "mod_a.py"
    file_a.write_text(
        "class Alpha:\n"
        "    def run(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    file_b = repo_dir / "mod_b.py"
    file_b.write_text(
        "def beta():\n"
        "    return 42\n",
        encoding="utf-8",
    )

    graph = {
        "nodes": [
            {
                "id": "file:mod_a.py",
                "type": "file",
                "label": "mod_a.py",
                "path": "mod_a.py",
                "role": "core",
                "pillar": "backend",
                "route_count": 0,
            },
            {
                "id": "class:mod_a.py:Alpha",
                "type": "class",
                "label": "Alpha",
                "file": "mod_a.py",
                "line": 1,
                "end_line": 3,
                "signature": "class Alpha:",
                "exported": True,
                "complexity": 1,
                "role": "core",
            },
            {
                "id": "file:mod_b.py",
                "type": "file",
                "label": "mod_b.py",
                "path": "mod_b.py",
                "role": "utility",
                "pillar": "backend",
                "route_count": 0,
            },
            {
                "id": "func:mod_b.py:beta",
                "type": "function",
                "label": "beta",
                "file": "mod_b.py",
                "line": 1,
                "end_line": 2,
                "signature": "def beta() -> int:",
                "exported": True,
                "complexity": 1,
                "role": "utility",
            },
        ],
        "edges": [
            {"source": "file:mod_a.py", "target": "file:mod_b.py"},
        ],
    }
    return repo_dir, graph


def test_normalize_signature():
    raw = "def   foo(\n    a: int,\n    b: str\n) -> bool:"
    norm = normalize_signature(raw)
    assert norm == "def foo( a: int, b: str ) -> bool:"
    assert len(normalize_signature("a" * 600)) == 500
    assert normalize_signature("") == ""


def test_resolve_context_path(tmp_path: Path):
    root = tmp_path / "my_root"
    root.mkdir()
    (root / "safe.py").write_text("ok", encoding="utf-8")

    assert resolve_context_path(root, "safe.py") == (root / "safe.py").resolve()
    assert resolve_context_path(root, "../escaped.py") is None
    assert resolve_context_path(root, "/abs/path.py") is None
    assert resolve_context_path(root, "C:\\windows\\file.py") is None
    assert resolve_context_path(root, "subdir/../escaped.py") is None
    assert resolve_context_path(None, "safe.py") is None


def test_ast_skeleton_basics(sample_graph):
    repo_dir, graph = sample_graph
    skel = build_ast_skeleton(graph, str(repo_dir), "mod_a.py")
    assert skel["available"] is True
    assert skel["file"] == "mod_a.py"
    assert skel["role"] == "core"
    assert len(skel["symbols"]) == 1
    sym = skel["symbols"][0]
    assert sym["name"] == "Alpha"
    assert sym["kind"] == "class"
    assert sym["line"] == 1
    assert sym["end_line"] == 3
    assert sym["signature"] == "class Alpha:"
    assert "body" not in sym
    assert skel["truncated"] is False
    assert skel["counts"]["symbols"] == 1
    assert skel["counts"]["returned"] == 1


def test_ast_skeleton_empty_or_missing(sample_graph):
    repo_dir, graph = sample_graph
    empty = build_ast_skeleton({}, str(repo_dir), "mod_a.py")
    assert empty["available"] is False
    assert empty["reason"] == "the index is empty"

    not_found = build_ast_skeleton(graph, str(repo_dir), "nonexistent.py")
    assert not_found["available"] is False
    assert "not indexed" in not_found["reason"]

    outside = build_ast_skeleton(graph, str(repo_dir), "../outside.py")
    assert outside["available"] is False
    assert outside["reason"] == "path outside root"


def test_context_pack_skeleton_default(sample_graph):
    repo_dir, graph = sample_graph
    pack = build_context_pack(graph, str(repo_dir), paths=["mod_a.py"])
    assert pack["available"] is True
    assert pack["detail"] == "skeleton"
    assert pack["budget"] == DEFAULT_BUDGET_TOKENS
    assert len(pack["files"]) == 1
    f = pack["files"][0]
    assert f["path"] == "mod_a.py"
    assert "body" not in f["symbols"][0]
    assert pack["hash"].startswith("sha256:")
    assert pack["format"] == "json"
    assert pack["tokens"]["budget"] == DEFAULT_BUDGET_TOKENS
    assert pack["tokens"]["pack"] > 0


def test_context_pack_full_detail_and_caps(tmp_path: Path):
    repo_dir = tmp_path / "repo_full"
    repo_dir.mkdir()
    # Create large file with > 120 lines and long line
    lines = [f"    x_{i} = {i}\n" for i in range(150)]
    long_content = "def big_func():\n" + "".join(lines)
    (repo_dir / "big.py").write_text(long_content, encoding="utf-8")

    graph = {
        "nodes": [
            {
                "id": "file:big.py",
                "type": "file",
                "label": "big.py",
                "path": "big.py",
                "role": "service",
                "pillar": "backend",
            },
            {
                "id": "func:big.py:big_func",
                "type": "function",
                "label": "big_func",
                "file": "big.py",
                "line": 1,
                "end_line": 151,
                "signature": "def big_func():",
                "role": "service",
            },
        ],
        "edges": [],
    }

    pack = build_context_pack(graph, str(repo_dir), paths=["big.py"], detail="full")
    assert pack["available"] is True
    assert pack["detail"] == "full"
    sym = pack["files"][0]["symbols"][0]
    assert "body" in sym
    assert sym["body_truncated"] is True
    assert sym["body_lines"] <= MAX_BODY_LINES
    assert len(pack["caps"]) >= 1
    assert any(c["reason"] == "max-lines" for c in pack["caps"])


def test_context_pack_budget_omissions(sample_graph):
    repo_dir, graph = sample_graph
    # Budget too small to fit any file (minimum budget is 500)
    pack = build_context_pack(graph, str(repo_dir), budget=500)
    assert pack["available"] is True
    assert pack["budget"] == 500
    assert pack["tokens"]["pack"] <= 500
    if len(pack["files"]) < 2:
        assert len(pack["omitted"]) > 0
        assert any(o["reason"] == "budget" for o in pack["omitted"])


def test_context_pack_invalid_budget_and_detail(sample_graph):
    repo_dir, graph = sample_graph
    with pytest.raises(ContextError) as exc_detail:
        build_context_pack(graph, str(repo_dir), detail="invalid_detail")
    assert exc_detail.value.status_code == 400

    with pytest.raises(ContextError) as exc_budget:
        build_context_pack(graph, str(repo_dir), budget=100)
    assert exc_budget.value.status_code == 400

    with pytest.raises(ContextError) as exc_budget2:
        build_context_pack(graph, str(repo_dir), budget=300000)
    assert exc_budget2.value.status_code == 400


def test_context_pack_unreadable_file(tmp_path: Path):
    repo_dir = tmp_path / "repo_unreadable"
    repo_dir.mkdir()
    # File exists in graph but missing on disk
    graph = {
        "nodes": [
            {
                "id": "file:ghost.py",
                "type": "file",
                "label": "ghost.py",
                "path": "ghost.py",
                "role": "core",
            },
            {
                "id": "func:ghost.py:spooky",
                "type": "function",
                "label": "spooky",
                "file": "ghost.py",
                "line": 1,
                "end_line": 2,
                "signature": "def spooky(): pass",
            },
        ],
        "edges": [],
    }
    pack = build_context_pack(graph, str(repo_dir), paths=["ghost.py"], detail="full")
    assert pack["available"] is True
    assert len(pack["files"]) == 1
    assert "body" not in pack["files"][0]["symbols"][0]
    assert any(o["reason"] == "unreadable" for o in pack["omitted"])


def test_context_pack_outside_root(sample_graph):
    repo_dir, graph = sample_graph
    pack = build_context_pack(graph, str(repo_dir), paths=["../outside.py"])
    assert pack["available"] is True
    assert len(pack["files"]) == 0
    assert any(o["reason"] == "outside-root" for o in pack["omitted"])


def test_context_pack_hash_determinism_and_delta(sample_graph):
    repo_dir, graph = sample_graph
    pack1 = build_context_pack(graph, str(repo_dir), paths=["mod_a.py"])
    pack2 = build_context_pack(graph, str(repo_dir), paths=["mod_a.py"])
    assert pack1["hash"] == pack2["hash"]

    # Altering metadata excluded from hash does not change hash
    mutated = dict(pack1)
    mutated["tokens"] = {"pack": 99999, "budget": 8000}
    mutated["root"] = "/completely/different/root"
    mutated["format"] = "toon"
    assert context_hash(mutated) == pack1["hash"]

    # Altering detail changes hash
    pack_full = build_context_pack(graph, str(repo_dir), paths=["mod_a.py"], detail="full")
    assert pack_full["hash"] != pack1["hash"]

    # since_hash matching returns unchanged envelope
    pack_unchanged = build_context_pack(graph, str(repo_dir), paths=["mod_a.py"], since_hash=pack1["hash"])
    assert pack_unchanged.get("unchanged") is True
    assert "files" not in pack_unchanged
    assert pack_unchanged["hash"] == pack1["hash"]

    # since_hash not matching echoes since_hash
    pack_changed = build_context_pack(graph, str(repo_dir), paths=["mod_a.py"], since_hash="sha256:000000000000")
    assert "unchanged" not in pack_changed
    assert pack_changed.get("since_hash") == "sha256:000000000000"
    assert pack_changed["hash"] == pack1["hash"]


def test_toon_roundtrip_and_killswitch(sample_graph, monkeypatch):
    repo_dir, graph = sample_graph
    pack = build_context_pack(graph, str(repo_dir), paths=["mod_a.py"])

    if toon_available():
        toon_text = encode_toon(pack)
        assert isinstance(toon_text, str)
        decoded = decode_toon(toon_text)
        expected = json.loads(json.dumps(pack))
        assert decoded == expected
        assert context_hash(pack) == context_hash(decoded)

    # Kill switch REPOSCOPE_TOON=0
    monkeypatch.setenv("REPOSCOPE_TOON", "0")
    assert toon_available() is False
    with pytest.raises(ContextError) as exc:
        encode_toon(pack)
    assert exc.value.status_code == 400
    assert "disabled" in exc.value.detail

    with pytest.raises(ContextError):
        decode_toon("dummy: toon")
