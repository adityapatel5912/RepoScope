"""
test_health.py — health endpoints must keep passing (deliverable #5).
"""
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

import main


def test_health_full():
    client = TestClient(main.app)
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "reposcope-api"
    assert "openrouter_keys" in data["checks"]


def test_health_version_matches_package_metadata():
    """The API must not advertise a stale release version.

    Render's health check is used to confirm a deploy, so a hard-coded
    version that drifts from pyproject.toml is a release bug, not a cosmetic
    one. Read the package metadata and compare it to the live response.
    """
    root = Path(__file__).resolve().parents[2]
    with (root / "pyproject.toml").open("rb") as handle:
        expected = tomllib.load(handle)["project"]["version"]

    client = TestClient(main.app)
    assert client.get("/api/health").json()["version"] == expected


def test_health_simple_and_root():
    client = TestClient(main.app)
    assert client.get("/health").json() == {"status": "ok"}
    # Root redirects to /api/health for browsers
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (302, 307)


def test_csp_allows_webassembly_without_javascript_eval():
    """The optional browser parser compiles Tree-sitter WebAssembly.

    Chrome refuses WebAssembly.instantiate under `script-src 'self'`; the
    CSP must include `wasm-unsafe-eval`. It must not fall back to the much
    broader `'unsafe-eval'`.
    """
    client = TestClient(main.app)
    csp = client.get("/api/health").headers["content-security-policy"]
    assert "script-src 'self' 'wasm-unsafe-eval'" in csp
    assert "'unsafe-eval'" not in csp
