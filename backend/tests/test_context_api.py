"""
backend/tests/test_context_api.py
L2 contract tests for GET /api/context/pack.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import main
import orchestrator
from graph_builder import build_graph_from_repo
from context_compressor import decode_toon, toon_available

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v2_contract"


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def loaded_client(client, monkeypatch):
    graph = build_graph_from_repo(str(FIXTURE))
    monkeypatch.setattr(
        orchestrator, "current_graph", lambda: (graph, str(FIXTURE))
    )
    return client


def test_context_pack_503_when_no_repo_loaded(client, monkeypatch):
    monkeypatch.setattr(orchestrator, "current_graph", lambda: ({}, None))
    # Also patch repo_tracker so it doesn't find saved state
    import repo_tracker
    monkeypatch.setattr(repo_tracker, "load_state", lambda: {})

    resp = client.get("/api/context/pack")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "No repository is loaded"


def test_context_pack_defaults(loaded_client):
    resp = loaded_client.get("/api/context/pack")
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/json"
    assert "X-RepoScope-Context-Hash" in resp.headers
    pack_hash = resp.headers["X-RepoScope-Context-Hash"]
    assert pack_hash.startswith("sha256:")

    data = resp.json()
    assert data["schema_version"] == 1
    assert data["available"] is True
    assert data["detail"] == "skeleton"
    assert data["budget"] == 8000
    assert data["format"] == "json"
    assert data["hash"] == pack_hash
    assert len(data["files"]) > 0
    # Skeleton omits body
    for f in data["files"]:
        for s in f["symbols"]:
            assert "body" not in s


def test_context_pack_explicit_paths_and_full_detail(loaded_client):
    resp = loaded_client.get("/api/context/pack?paths=base.py&detail=full")
    assert resp.status_code == 200
    data = resp.json()
    assert data["detail"] == "full"
    assert len(data["files"]) == 1
    assert data["files"][0]["path"] == "base.py"
    sym = data["files"][0]["symbols"][0]
    assert "body" in sym
    assert "class Base" in sym["body"]


def test_context_pack_since_hash_unchanged(loaded_client):
    resp1 = loaded_client.get("/api/context/pack")
    assert resp1.status_code == 200
    pack_hash = resp1.headers["X-RepoScope-Context-Hash"]

    # Request with matching since_hash
    resp2 = loaded_client.get(f"/api/context/pack?since_hash={pack_hash}")
    assert resp2.status_code == 200
    assert resp2.headers.get("X-RepoScope-Context-Unchanged") == "1"
    assert resp2.headers.get("X-RepoScope-Context-Hash") == pack_hash

    data2 = resp2.json()
    assert data2["available"] is True
    assert data2["unchanged"] is True
    assert "files" not in data2
    assert data2["hash"] == pack_hash


def test_context_pack_since_hash_mismatch(loaded_client):
    resp = loaded_client.get("/api/context/pack?since_hash=sha256:1111111111111111111111111111111111111111111111111111111111111111")
    assert resp.status_code == 200
    assert "X-RepoScope-Context-Unchanged" not in resp.headers
    data = resp.json()
    assert "unchanged" not in data
    assert data.get("since_hash") == "sha256:1111111111111111111111111111111111111111111111111111111111111111"


def test_context_pack_toon_format_and_kill_switch(loaded_client, monkeypatch):
    if toon_available():
        resp = loaded_client.get("/api/context/pack?format=toon")
        assert resp.status_code == 200
        assert "text/toon" in resp.headers.get("content-type", "")
        # Round-trip verify
        decoded = decode_toon(resp.text)
        assert decoded["available"] is True
        assert decoded["detail"] == "skeleton"

    # Disable TOON via kill switch
    monkeypatch.setenv("REPOSCOPE_TOON", "0")
    resp_disabled = loaded_client.get("/api/context/pack?format=toon")
    assert resp_disabled.status_code == 400
    assert "disabled" in resp_disabled.json()["detail"]


def test_context_pack_invalid_parameters(loaded_client):
    # Invalid budget
    resp1 = loaded_client.get("/api/context/pack?budget=10")
    assert resp1.status_code == 422 or resp1.status_code == 400

    # Invalid detail
    resp2 = loaded_client.get("/api/context/pack?detail=summary")
    assert resp2.status_code == 422 or resp2.status_code == 400
