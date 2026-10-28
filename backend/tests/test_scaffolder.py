"""
backend/tests/test_scaffolder.py
Unit tests and L2 contract tests for executable multi-file scaffolder (Phase 7, V2.6).

Covers:
- Determinism (byte-identical file set across calls)
- All modes: preview, zip, command
- Path traversal rejection
- Zip archive roundtrip validation
- Placeholder-only .env.example (zero secret leakage)
- Generic-stack fallback
- Language syntax compilation check (compileall)
- L2 contract: POST /api/scaffold and POST /api/scaffold/download-zip
"""

import compileall
import io
import os
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from scaffolder import Scaffolder, extract_env_keys, sanitize_rel_path


@pytest.fixture()
def client():
    return TestClient(main.app)


@pytest.fixture()
def python_graph():
    """Synthetic Python FastAPI graph."""
    nodes = [
        {"id": "file:main.py", "label": "main.py", "path": "main.py", "type": "file", "pillar": "backend"},
        {"id": "file:app/api.py", "label": "app/api.py", "path": "app/api.py", "type": "file", "pillar": "backend"},
        {"id": "file:app/models.py", "label": "app/models.py", "path": "app/models.py", "type": "file", "pillar": "backend"},
        {"id": "func:app/api.py:get_users", "label": "get_users", "path": "app/api.py", "type": "function", "line": 10},
    ]
    edges = [
        {"source": "file:main.py", "target": "file:app/api.py", "type": "imports"},
    ]
    api_routes = [
        {"method": "GET", "path": "/api/users", "file": "app/api.py", "line": 10, "handler": "get_users", "node_id": "func:app/api.py:get_users"}
    ]
    return {"nodes": nodes, "edges": edges, "api_routes": api_routes}


@pytest.fixture()
def generic_graph():
    """Synthetic graph with no recognized languages/frameworks."""
    nodes = [
        {"id": "file:unknown.xyz", "label": "unknown.xyz", "path": "unknown.xyz", "type": "file"},
    ]
    return {"nodes": nodes, "edges": [], "api_routes": []}


@pytest.fixture()
def loaded_repo(tmp_path, monkeypatch):
    """Loaded repo in main state."""
    (tmp_path / "main.py").write_text("import app\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=sqlite:///app.db\nSECRET_KEY=dev\n", encoding="utf-8")

    state = {
        "repo": "octo/starter",
        "local_path": str(tmp_path),
        "readme": "# Starter Repo\n",
    }
    monkeypatch.setattr(main, "load_state", lambda: state)
    return tmp_path


# ── 1. Determinism Tests ──────────────────────────────────────────────────────

def test_scaffolder_determinism(python_graph, tmp_path):
    scaffolder1 = Scaffolder(python_graph, str(tmp_path), "octo/starter")
    scaffolder2 = Scaffolder(python_graph, str(tmp_path), "octo/starter")

    res1 = scaffolder1.generate()
    res2 = scaffolder2.generate()

    assert res1["project_type"] == res2["project_type"]
    assert res1["file_tree"] == res2["file_tree"]
    assert len(res1["files"]) == len(res2["files"])
    assert res1["token_estimate"] == res2["token_estimate"]

    for f1, f2 in zip(res1["files"], res2["files"]):
        assert f1["path"] == f2["path"]
        assert f1["content"] == f2["content"]
        assert f1["purpose"] == f2["purpose"]


# ── 2. All Modes (preview, zip, command) ──────────────────────────────────────

def test_scaffolder_modes(python_graph, tmp_path):
    scaffolder = Scaffolder(python_graph, str(tmp_path), "octo/starter")

    # Preview mode
    prev = scaffolder.generate(mode="preview")
    assert prev["ok"] is True
    assert len(prev["files"]) >= 12
    assert "main.py" in prev["file_tree"]
    assert "bootstrap_command" in prev

    # Command mode
    cmd = scaffolder.generate(mode="command")
    assert cmd["ok"] is True
    assert "command" in cmd
    assert "npx reposcope-mcp scaffold --from octo/starter --out ./app" == cmd["command"]

    # Zip mode bytes
    zip_bytes = scaffolder.generate_zip_bytes()
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0


# ── 3. Path Traversal Prevention ──────────────────────────────────────────────

def test_sanitize_rel_path_rejects_traversal():
    assert sanitize_rel_path("../../etc/passwd") is None
    assert sanitize_rel_path("../escape.py") is None
    assert sanitize_rel_path("folder/../../escape.py") is None
    assert sanitize_rel_path("C:/Windows/System32/calc.exe") is None
    assert sanitize_rel_path("/root/file.py") is None
    assert sanitize_rel_path("~/file.py") is None
    assert sanitize_rel_path("") is None
    assert sanitize_rel_path(None) is None

    # Valid relative paths
    assert sanitize_rel_path("app/main.py") == "app/main.py"
    assert sanitize_rel_path(".claude/CLAUDE.md") == ".claude/CLAUDE.md"
    assert sanitize_rel_path("tests/test_basic.py") == "tests/test_basic.py"


# ── 4. Zip Roundtrip Validation ───────────────────────────────────────────────

def test_zip_roundtrip_matches_preview(python_graph, tmp_path):
    scaffolder = Scaffolder(python_graph, str(tmp_path), "octo/starter")
    res = scaffolder.generate(mode="preview")
    zip_bytes = scaffolder.generate_zip_bytes()

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        archive_names = set(zf.namelist())
        expected_paths = {f["path"] for f in res["files"]}
        assert archive_names == expected_paths

        for f in res["files"]:
            content = zf.read(f["path"]).decode("utf-8")
            assert content == f["content"], f"Content mismatch for {f['path']}"


# ── 5. Placeholder-Only .env.example ─────────────────────────────────────────

def test_placeholder_only_env_example(python_graph, tmp_path):
    # Write a real .env with a fake secret to test it is NEVER copied
    (tmp_path / ".env").write_text("SUPER_SECRET_TOKEN=ghp_secret1234567890\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=sqlite:///app.db\nPORT=8000\n", encoding="utf-8")

    scaffolder = Scaffolder(python_graph, str(tmp_path), "octo/starter")
    res = scaffolder.generate(mode="preview")

    env_file = next(f for f in res["files"] if f["path"] == ".env.example")
    content = env_file["content"]

    assert "ghp_secret" not in content
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            assert "=" in line
            val = line.split("=", 1)[1].strip()
            assert val == "<placeholder>"


# ── 6. Generic Stack Fallback ─────────────────────────────────────────────────

def test_generic_stack_fallback(generic_graph, tmp_path):
    scaffolder = Scaffolder(generic_graph, str(tmp_path), "generic/app")
    res = scaffolder.generate()

    assert res["ok"] is True
    assert res["project_type"] == "generic-starter"
    assert len(res["files"]) >= 12
    paths = {f["path"] for f in res["files"]}
    assert "README.md" in paths
    assert "SCAFFOLD.md" in paths
    assert ".env.example" in paths


# ── 7. Language Syntax Compilation Check (compileall) ─────────────────────────

def test_python_scaffold_syntax_compiles(python_graph, tmp_path):
    scaffolder = Scaffolder(python_graph, str(tmp_path), "octo/starter")
    res = scaffolder.generate()

    with tempfile.TemporaryDirectory() as td:
        for f in res["files"]:
            dest = Path(td) / f["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f["content"], encoding="utf-8")

        # Compile all python files — raises Exception if invalid syntax
        result = compileall.compile_dir(td, quiet=True)
        assert result is True, "compileall failed on generated python starter kit"


# ── 8. L2 Contract Tests ──────────────────────────────────────────────────────

def test_endpoint_scaffold_preview(client, loaded_repo):
    res = client.post("/api/scaffold", json={"mode": "preview"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["ok"] is True
    assert len(data["files"]) >= 12
    assert "file_tree" in data
    assert "bootstrap_command" in data
    assert data["token_estimate"] > 0


def test_endpoint_scaffold_command(client, loaded_repo):
    res = client.post("/api/scaffold", json={"mode": "command"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["ok"] is True
    assert "command" in data
    assert "npx reposcope-mcp scaffold" in data["command"]


def test_endpoint_scaffold_zip(client, loaded_repo):
    res = client.post("/api/scaffold", json={"mode": "zip"})
    assert res.status_code == 200, res.text
    assert res.headers.get("content-type") == "application/zip"
    assert len(res.content) > 0


def test_endpoint_scaffold_download_zip(client, loaded_repo):
    res = client.post("/api/scaffold/download-zip")
    assert res.status_code == 200, res.text
    assert res.headers.get("content-type") == "application/zip"
    assert "attachment;" in res.headers.get("content-disposition", "")
    assert len(res.content) > 0


def test_endpoint_scaffold_no_repo_loaded(client, monkeypatch):
    monkeypatch.setattr(main, "load_state", lambda: {})
    res = client.post("/api/scaffold")
    assert res.status_code == 400
