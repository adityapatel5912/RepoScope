"""
test_harness_api.py
L2 contract for the Phase 3 harness endpoints.

Pins the four routes, the preview/apply distinction, the server-side
apply flag, the force rule for existing files, and the no-writes
guarantee on every read-only path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
import orchestrator

EXPECTED_IDS = {
    "claude",
    "cursor",
    "vscode",
    "codex",
    "kiro",
    "antigravity",
    "windsurf",
    "cline",
    "opencode",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("REPOSCOPE_HARNESS_APPLY", raising=False)
    monkeypatch.delenv("REPOSCOPE_MCP_HTTP_URL", raising=False)


def _json(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json()


def _config(client: TestClient, repo: Path, **params) -> dict:
    query = {"agent": "claude", "transport": "stdio", "root": str(repo), **params}
    return _json(client.get("/api/harness/config", params=query))


def _apply(client: TestClient, repo: Path, **body) -> dict:
    payload = {"agent": "claude", "transport": "stdio", "root": str(repo), **body}
    return _json(client.post("/api/harness/apply", json=payload))


# ── Registry and skills ─────────────────────────────────────────────────────


def test_agents_endpoint_returns_the_nine_targets(client):
    payload = _json(client.get("/api/harness/agents"))
    assert payload["apply_enabled"] is False
    assert {agent["id"] for agent in payload["agents"]} == EXPECTED_IDS
    assert len(payload["agents"]) == 9
    assert all(set(agent) >= {
        "id", "label", "config_paths", "transport", "default_transport",
        "global_preview_paths", "docs_url", "verified_at", "notes",
    } for agent in payload["agents"])


def test_agents_endpoint_reflects_the_server_apply_flag(client, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    assert _json(client.get("/api/harness/agents"))["apply_enabled"] is True


def test_skills_endpoint_returns_canonical_bodies(client):
    payload = _json(client.get("/api/harness/skills"))
    assert payload["content_available"] is True
    assert len(payload["skills"]) == 5
    assert all(skill["content_available"] is True for skill in payload["skills"])
    assert all(len(skill.get("content", "")) > 100 for skill in payload["skills"])


def test_harness_config_includes_skills_for_claude_and_antigravity(client, tmp_path):
    repo_dir = str(tmp_path)
    res_claude = _json(client.get(f"/api/harness/config?agent=claude&root={repo_dir}"))
    assert len(res_claude["files"]) == 7
    assert any(".claude/skills/" in f["path"] for f in res_claude["files"])

    res_anti = _json(client.get(f"/api/harness/config?agent=antigravity&root={repo_dir}"))
    assert len(res_anti["files"]) == 7
    assert any(".agents/skills/" in f["path"] for f in res_anti["files"])


def test_harness_routes_are_registered(client):
    paths = set(main.app.openapi()["paths"])
    assert {
        "/api/harness/agents",
        "/api/harness/config",
        "/api/harness/apply",
        "/api/harness/skills",
    } <= paths


# ── Preview ─────────────────────────────────────────────────────────────────


def test_config_previews_the_contract_shape_without_writing(client, repo):
    payload = _config(client, repo)
    assert payload["ok"] is True
    assert payload["agent"] == "claude"
    assert payload["label"] == "Claude Code"
    assert payload["transport"] == "stdio"
    assert payload["root"] == str(repo.resolve())
    assert payload["apply_enabled"] is False
    assert payload["requires_force"] is False
    assert payload["command"].startswith("claude mcp add --scope project")
    assert layer_names(payload)[:2] == [".mcp.json", "CLAUDE.md"]
    assert len(layer_names(payload)) == 7
    assert all(item["exists"] is False for item in payload["files"])
    assert all(item["will_write"] is True for item in payload["files"])
    assert payload["warnings"] == []
    assert list(repo.iterdir()) == []


def layer_names(payload: dict) -> list[str]:
    return [item["path"] for item in payload["files"]]


def test_config_does_not_write_even_when_apply_is_enabled(client, repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    payload = _config(client, repo)
    assert payload["apply_enabled"] is True
    assert list(repo.iterdir()) == []


def test_config_uses_the_active_local_repository(client, repo, monkeypatch):
    monkeypatch.setattr(orchestrator, "current_graph", lambda: ({}, str(repo)))
    payload = _json(
        client.get("/api/harness/config", params={"agent": "opencode"})
    )
    assert payload["root"] == str(repo.resolve())
    assert layer_names(payload) == ["opencode.json"]


def test_config_requires_a_root_when_no_repository_is_active(client, monkeypatch):
    monkeypatch.setattr(orchestrator, "current_graph", lambda: ({}, None))
    response = client.get("/api/harness/config", params={"agent": "claude"})
    assert response.status_code == 400
    assert "root is required" in response.json()["detail"].lower()


def test_config_rejects_a_relative_root(client):
    response = client.get(
        "/api/harness/config", params={"agent": "claude", "root": "repo"}
    )
    assert response.status_code == 400
    assert "absolute" in response.json()["detail"].lower()


def test_config_rejects_an_unknown_agent(client, repo):
    response = client.get(
        "/api/harness/config", params={"agent": "unknown", "root": str(repo)}
    )
    assert response.status_code == 400
    assert "Unknown agent" in response.json()["detail"]


def test_config_rejects_an_unsupported_transport(client, repo):
    response = client.get(
        "/api/harness/config",
        params={"agent": "claude", "transport": "sse", "root": str(repo)},
    )
    assert response.status_code == 400
    assert "Unsupported transport" in response.json()["detail"]


def test_config_http_preview_uses_the_http_command(client, repo):
    payload = _json(
        client.get(
            "/api/harness/config",
            params={"agent": "vscode", "transport": "http", "root": str(repo)},
        )
    )
    assert payload["command"].startswith("code --add-mcp '")
    entry = json.loads(payload["files"][0]["content"])["servers"]["reposcope"]
    assert entry["type"] == "http"


# ── Apply ───────────────────────────────────────────────────────────────────


def test_apply_defaults_to_a_dry_run(client, repo):
    payload = _apply(client, repo)
    assert payload["apply"] is False
    assert payload["applied"] == []
    assert payload["unchanged"] == []
    assert list(repo.iterdir()) == []


def test_apply_is_refused_when_the_flag_is_off(client, repo):
    response = client.post(
        "/api/harness/apply",
        json={
            "agent": "claude",
            "transport": "stdio",
            "root": str(repo),
            "apply": True,
            "force": False,
        },
    )
    assert response.status_code == 403
    assert "REPOSCOPE_HARNESS_APPLY=1" in response.json()["detail"]
    assert list(repo.iterdir()) == []


def test_apply_writes_only_after_the_flag_and_force_allow_it(client, repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    payload = _apply(client, repo, apply=True)
    assert payload["apply"] is True
    assert len(payload["applied"]) == 7
    assert {".mcp.json", "CLAUDE.md"} <= set(payload["applied"])
    assert {".mcp.json", "CLAUDE.md", ".claude"} <= {path.name for path in repo.iterdir()}

    again = _apply(client, repo, apply=True)
    assert again["applied"] == []
    assert len(again["unchanged"]) == 7
    assert {".mcp.json", "CLAUDE.md"} <= set(again["unchanged"])


def test_apply_409s_for_a_changed_existing_file_without_force(client, repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    (repo / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "x"}}}, indent=2) + "\n",
        encoding="utf-8",
    )

    response = client.post(
        "/api/harness/apply",
        json={
            "agent": "claude",
            "transport": "stdio",
            "root": str(repo),
            "apply": True,
            "force": False,
        },
    )
    assert response.status_code == 409
    assert ".mcp.json" in response.json()["detail"]
    assert "force" in response.json()["detail"].lower()

    forced = _apply(client, repo, apply=True, force=True)
    assert ".mcp.json" in forced["applied"]
    data = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))
    assert data["mcpServers"]["other"]["command"] == "x"
    assert data["mcpServers"]["reposcope"]["command"] == "reposcope-mcp"


def test_apply_rejects_an_unknown_agent(client, repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    response = client.post(
        "/api/harness/apply",
        json={"agent": "unknown", "root": str(repo), "apply": True},
    )
    assert response.status_code == 400
    assert "Unknown agent" in response.json()["detail"]


def test_apply_rejects_a_missing_agent(client):
    response = client.post("/api/harness/apply", json={"apply": True})
    assert response.status_code == 422


def test_apply_http_transport_writes_a_url_entry(client, repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    _apply(client, repo, agent="opencode", transport="http", apply=True)
    data = json.loads((repo / "opencode.json").read_text(encoding="utf-8"))
    assert data["mcp"]["reposcope"]["type"] == "remote"
    assert data["mcp"]["reposcope"]["url"] == "http://127.0.0.1:8765/mcp"


def test_apply_preserves_unrelated_toml_tables(client, repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    (repo / ".codex").mkdir()
    (repo / ".codex" / "config.toml").write_text(
        'model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "other"\n',
        encoding="utf-8",
    )
    payload = _apply(client, repo, agent="codex", apply=True, force=True)
    assert ".codex/config.toml" in payload["applied"]

    import tomllib

    data = tomllib.loads((repo / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert data["model"] == "gpt-5"
    assert data["mcp_servers"]["other"]["command"] == "other"
    assert data["mcp_servers"]["reposcope"]["command"] == "reposcope-mcp"
