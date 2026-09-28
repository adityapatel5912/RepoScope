"""
test_feature_5_scaffold.py
POST /api/scaffold — CodeCrafters-style starter scaffold from the loaded repo.
"""
import json

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client():
    return TestClient(main.app)


@pytest.fixture()
def tiny_repo(tmp_path, monkeypatch):
    """A real 3-file mini repo so build_graph_from_repo runs for real."""
    (tmp_path / "main.py").write_text(
        "import helper\n\n\ndef run():\n    return helper.help()\n"
    )
    (tmp_path / "helper.py").write_text(
        "def help():\n    \"\"\"Help the runner.\"\"\"\n    return 1\n"
    )
    (tmp_path / "README.md").write_text("# Tiny repo\n\nA test repo.\n")
    state = {
        "repo": "octo/tiny",
        "local_path": str(tmp_path),
        "readme": "# Tiny repo\n\nA test repo.\n",
    }
    monkeypatch.setattr(main, "load_state", lambda: state)
    return tmp_path


SCAFFOLD_JSON = json.dumps({
    "project_type": "python-cli",
    "file_tree": ["README.md", "main.py", "helper.py"],
    "files": [
        {"path": "README.md", "content": "# Stage 1\nTODO", "purpose": "Build guide"},
        {"path": "main.py", "content": "def main():\n    TODO = 1\n", "purpose": "Entry"},
        {"path": "helper.py", "content": "def help():\n    return None\n", "purpose": "Helper"},
    ],
})


def test_scaffold_returns_valid_scaffold(client, tiny_repo, monkeypatch):
    monkeypatch.setattr(main, "ask_llm", lambda *a, **k: f"```json\n{SCAFFOLD_JSON}\n```")
    res = client.post("/api/scaffold")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["project_type"] == "python-cli"
    assert len(data["files"]) == 3
    assert {"path", "content", "purpose"} <= set(data["files"][0].keys())
    assert isinstance(data["file_tree"], list)
    assert isinstance(data["top_nodes"], list)


def test_scaffold_rejects_garbage_llm_output(client, tiny_repo, monkeypatch):
    monkeypatch.setattr(main, "ask_llm", lambda *a, **k: "I cannot do that")
    res = client.post("/api/scaffold")
    assert res.status_code == 502
    assert "invalid scaffold" in res.json()["detail"].lower()


def test_scaffold_sanitizes_paths(client, tiny_repo, monkeypatch):
    evil = json.dumps({
        "project_type": "evil",
        "file_tree": ["../etc/passwd"],
        "files": [
            {"path": "../../etc/passwd", "content": "root", "purpose": "escape"},
            {"path": "ok.py", "content": "x = 1\n", "purpose": "fine"},
        ],
    })
    monkeypatch.setattr(main, "ask_llm", lambda *a, **k: evil)
    res = client.post("/api/scaffold")
    assert res.status_code == 200
    paths = [f["path"] for f in res.json()["files"]]
    assert paths == ["ok.py"]


def test_scaffold_requires_loaded_repo(client, monkeypatch):
    monkeypatch.setattr(main, "load_state", lambda: {"repo": None, "local_path": None})
    res = client.post("/api/scaffold")
    assert res.status_code == 400


def test_salvage_recovers_truncated_scaffold():
    """Reasoning models truncate mid-JSON — salvage must recover the files
    emitted before the cut."""
    from json_utils import salvage_truncated_json
    truncated = (
        '{"project_type": "react-spa", "file_tree": ["main.tsx", "App.tsx"], "files": ['
        '{"path": "main.tsx", "content": "import { createRoot } from \'react-dom\'\n'
    )
    data = salvage_truncated_json(truncated)
    assert data is not None
    assert data["project_type"] == "react-spa"
    assert data["files"][0]["path"] == "main.tsx"
    assert "createRoot" in data["files"][0]["content"]


def test_salvage_returns_none_on_garbage():
    from json_utils import salvage_truncated_json
    assert salvage_truncated_json("no json here at all") is None
