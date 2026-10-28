"""
test_pr_impact_symbols.py
Phase 11 verification: Symbol-level AST diffing, route contract breaks,
cross-stack consumer resolution, test gaps, SARIF 2.1.0 emission, and PR endpoints.
"""
import json
import pytest
from fastapi.testclient import TestClient

import main
from contract_diff import diff_routes, diff_sources, find_consumers, Finding
from pr_impact import build_pr_impact, detect_test_gaps
from chat_actions import detect_chat_actions


@pytest.fixture()
def client():
    return TestClient(main.app)


def test_diff_routes_detection():
    old_source = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/v1/users")
def get_users():
    return []

@app.delete("/api/v1/users/{id}")
def delete_user(id: str):
    pass
"""
    new_source = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/v2/users")
def get_users():
    return []
"""
    findings = diff_routes(old_source, new_source, "main.py")
    assert len(findings) >= 2

    # Check altered route for get_users
    altered = [f for f in findings if f.kind == "altered-route"]
    assert len(altered) == 1
    assert "GET /api/v1/users" in altered[0].symbol
    assert altered[0].severity == "BREAKING"

    # Check removed route for delete_user
    removed = [f for f in findings if f.kind == "removed-route"]
    assert len(removed) == 1
    assert "DELETE /api/v1/users/{id}" in removed[0].symbol
    assert removed[0].severity == "BREAKING"


def test_find_consumers_with_api_calls():
    graph = {
        "nodes": [
            {"id": "file:backend/main.py", "label": "backend/main.py", "file": "backend/main.py", "type": "file"},
            {"id": "fn:get_users", "label": "get_users", "file": "backend/main.py", "type": "function"},
            {"id": "file:frontend/client.ts", "label": "frontend/client.ts", "file": "frontend/client.ts", "type": "file"},
            {"id": "file:backend/services.py", "label": "backend/services.py", "file": "backend/services.py", "type": "file"},
        ],
        "edges": [
            {
                "source": "file:frontend/client.ts",
                "target": "file:backend/main.py",
                "type": "api_calls",
                "evidence": {"path": "/api/users", "method": "GET"},
            },
            {
                "source": "file:backend/services.py",
                "target": "fn:get_users",
                "type": "calls",
            },
        ],
    }

    # Direct call consumer
    consumers = find_consumers(graph, "backend/main.py", "get_users")
    assert "backend/services.py" in consumers

    # Cross-stack API-call consumer
    route_consumers = find_consumers(graph, "backend/main.py", "GET /api/users")
    assert "frontend/client.ts" in route_consumers


def test_detect_test_gaps():
    graph = {
        "nodes": [
            {"id": "file:lib.py", "label": "lib.py", "file": "lib.py", "type": "file"},
            {"id": "fn:foo", "label": "foo", "file": "lib.py", "type": "function"},
            {"id": "file:tests/test_lib.py", "label": "tests/test_lib.py", "file": "tests/test_lib.py", "type": "file"},
        ],
        "edges": [
            {"source": "file:tests/test_lib.py", "target": "fn:foo", "type": "calls"},
        ],
    }
    findings = [
        Finding(kind="removed", symbol="bar", file="lib.py", line=10, severity="BREAKING"),
        Finding(kind="renamed-parameter", symbol="foo", file="lib.py", line=5, severity="BREAKING"),
    ]
    per_file = [{"file": "lib.py", "in_graph": True}]

    gaps = detect_test_gaps(graph, findings, per_file)
    gap_symbols = [g["symbol"] for g in gaps]
    # bar has no test call edge, so it must be flagged
    assert "bar" in gap_symbols
    # foo has incoming test edge from tests/test_lib.py, so it shouldn't be a test gap
    assert "foo" not in gap_symbols


def test_build_pr_impact_sarif_and_symbols():
    graph = {
        "nodes": [
            {"id": "file:lib.py", "label": "lib.py", "file": "lib.py", "type": "file"},
            {"id": "fn:calc", "label": "calc", "file": "lib.py", "type": "function"},
            {"id": "file:app.py", "label": "app.py", "file": "app.py", "type": "file"},
        ],
        "edges": [
            {"source": "file:app.py", "target": "fn:calc", "type": "calls"},
        ],
    }
    meta = {"number": 42, "title": "Refactor calc", "state": "open"}
    files = [
        {
            "filename": "lib.py",
            "status": "modified",
            "additions": 3,
            "deletions": 1,
            "patch": "-def calc(a):\n+def calc(a, required_b):\n     return a\n",
        }
    ]
    report = build_pr_impact(graph, meta, files)
    assert report["pr_number"] == 42
    assert "symbol_findings" in report
    assert len(report["symbol_findings"]) >= 1
    assert "sarif_doc" in report
    sarif = report["sarif_doc"]
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1
    results = sarif["runs"][0]["results"]
    assert any(r["ruleId"] == "reposcope/breaking-contract" for r in results)


def test_pr_impact_format_sarif(client, monkeypatch):
    meta = {"number": 88, "title": "API update", "state": "open"}
    files = [
        {
            "filename": "api.py",
            "status": "modified",
            "additions": 2,
            "deletions": 1,
            "patch": "-def fetch(): pass\n+def fetch(limit): pass\n",
        }
    ]

    async def fake_fetch_pr(owner, repo, pr_number, token=None):
        return meta, files

    monkeypatch.setattr(main, "fetch_pr", fake_fetch_pr)
    monkeypatch.setattr(main, "load_state", lambda: {"repo": "org/repo", "local_path": "."})

    res = client.post("/api/impact/pr", json={
        "repo_url": "https://github.com/org/repo",
        "pr_number": 88,
        "format": "sarif",
    })
    assert res.status_code == 200
    assert "application/sarif+json" in res.headers.get("content-type", "")
    data = res.json()
    assert data["version"] == "2.1.0"
    assert "runs" in data


def test_chat_actions_pr_intent():
    actions = detect_chat_actions("Can you analyze the impact of PR #42?")
    pr_actions = [a for a in actions if a["kind"] == "pr_impact"]
    assert len(pr_actions) == 1
    assert pr_actions[0]["pr_number"] == 42
