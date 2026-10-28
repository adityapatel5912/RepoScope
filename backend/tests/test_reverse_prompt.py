"""
backend/tests/test_reverse_prompt.py
Unit tests and L2 contract tests for the four-mode reverse-prompt compiler (Phase 6, V2.6).

Covers:
- Determinism (byte-identical output across calls)
- Rebuild mode: topological build order, cycle detection, stack, routes, models
- Feature mode: 2-hop interface closure, isolated slices, missing target node
- Spec mode: CLAUDE.md, AGENTS.md, llms.txt, .kiro/specs/* templates
- Context mode: budget clamping, deterministic token counting, TOON handling
- L2 contract: POST /api/repo/reverse-prompt and POST /api/reverse-prompt
- Backward compatibility: prompt field matches content
"""

import pytest
from fastapi.testclient import TestClient

import main
from reverse_prompt_compiler import (
    ReversePromptCompiler,
    compute_topological_build_order,
    detect_stack,
    extract_2hop_closure,
    find_sccs,
)
from token_metrics import estimate_tokens


@pytest.fixture()
def client():
    return TestClient(main.app)


@pytest.fixture()
def sample_graph():
    """Deterministic synthetic graph with files, routes, models, and cyclic dependencies."""
    nodes = [
        {"id": "file:app/main.py", "label": "app/main.py", "path": "app/main.py", "type": "file", "pillar": "backend"},
        {"id": "file:app/api.py", "label": "app/api.py", "path": "app/api.py", "type": "file", "pillar": "backend"},
        {"id": "file:app/models.py", "label": "app/models.py", "path": "app/models.py", "type": "file", "pillar": "backend"},
        {"id": "file:app/utils.py", "label": "app/utils.py", "path": "app/utils.py", "type": "file", "pillar": "backend"},
        {"id": "file:frontend/App.tsx", "label": "frontend/App.tsx", "path": "frontend/App.tsx", "type": "file", "pillar": "frontend"},
        {"id": "file:unrelated/far_away.py", "label": "unrelated/far_away.py", "path": "unrelated/far_away.py", "type": "file", "pillar": "data"},
        # Symbols & Routes & Models
        {"id": "func:app/api.py:get_health", "label": "get_health", "path": "app/api.py", "type": "function", "line": 15},
        {"id": "class:app/models.py:UserRecord", "label": "UserRecord", "path": "app/models.py", "type": "class", "role": "model", "line": 8},
    ]

    edges = [
        # main depends on api
        {"source": "file:app/main.py", "target": "file:app/api.py", "type": "imports"},
        # api depends on models
        {"source": "file:app/api.py", "target": "file:app/models.py", "type": "imports"},
        # models depends on utils
        {"source": "file:app/models.py", "target": "file:app/utils.py", "type": "imports"},
        # Mutual cycle: utils depends on api
        {"source": "file:app/utils.py", "target": "file:app/api.py", "type": "imports"},
        # frontend calls api
        {"source": "file:frontend/App.tsx", "target": "file:app/api.py", "type": "calls"},
    ]

    api_routes = [
        {"method": "GET", "path": "/api/health", "file": "app/api.py", "line": 15, "handler": "get_health", "node_id": "func:app/api.py:get_health"}
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "api_routes": api_routes,
    }


@pytest.fixture()
def loaded_repo(tmp_path, monkeypatch):
    """Sets up a loaded repository in main state."""
    (tmp_path / "main.py").write_text("import helper\ndef run(): return helper.help()\n", encoding="utf-8")
    (tmp_path / "helper.py").write_text("def help(): return 42\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0\npytest>=7.0.0\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=sqlite:///test.db\nPORT=8000\n", encoding="utf-8")

    state = {
        "repo": "test/repo",
        "local_path": str(tmp_path),
        "readme": "# Test Repo\nDocumentation for test repository.\n",
    }
    monkeypatch.setattr(main, "load_state", lambda: state)
    return tmp_path


# ── 1. Determinism Tests ──────────────────────────────────────────────────────

def test_compiler_determinism(sample_graph, tmp_path):
    compiler1 = ReversePromptCompiler(sample_graph, str(tmp_path))
    compiler2 = ReversePromptCompiler(sample_graph, str(tmp_path))

    for mode in ("rebuild", "feature", "spec", "context"):
        res1 = compiler1.compile(mode=mode)
        res2 = compiler2.compile(mode=mode)

        assert res1["content"] == res2["content"], f"Mode {mode} output is not deterministic"
        assert res1["prompt"] == res2["prompt"]
        assert res1["tokens"] == res2["tokens"]
        assert len(res1["files"]) == len(res2["files"])
        for f1, f2 in zip(res1["files"], res2["files"]):
            assert f1["path"] == f2["path"]
            assert f1["content"] == f2["content"]


# ── 2. Rebuild Mode Tests (Topological Build Order & Cycles) ──────────────────

def test_topological_sort_with_cycle():
    file_nodes = [
        {"id": "file:a.py", "path": "a.py"},
        {"id": "file:b.py", "path": "b.py"},
        {"id": "file:c.py", "path": "c.py"},
        {"id": "file:d.py", "path": "d.py"},
    ]
    edges = [
        {"source": "file:d.py", "target": "file:c.py"},
        {"source": "file:c.py", "target": "file:b.py"},
        # Cycle between a and b
        {"source": "file:b.py", "target": "file:a.py"},
        {"source": "file:a.py", "target": "file:b.py"},
    ]

    order, cycles = compute_topological_build_order(file_nodes, edges)

    # Cycle detected
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a.py", "b.py"}

    # d depends on c, c depends on b: so a/b before c, and c before d
    assert order.index("c.py") < order.index("d.py")
    assert order.index("a.py") < order.index("c.py") or order.index("b.py") < order.index("c.py")


def test_rebuild_mode_compilation(sample_graph, tmp_path):
    compiler = ReversePromptCompiler(sample_graph, str(tmp_path))
    res = compiler.compile(mode="rebuild")

    assert res["ok"] is True
    assert res["mode"] == "rebuild"
    content = res["content"]

    # Verify Stack section
    assert "## 1. Stack & Architecture" in content
    assert "Python" in content
    assert "TypeScript" in content

    # Verify Topological Build Order & Cycle Warning
    assert "## 2. Topological Build Order" in content
    assert "Cyclic dependencies detected" in content
    assert len(res["warnings"]) > 0

    # Verify Routes section
    assert "## 3. API Surface & Routes" in content
    assert "/api/health" in content
    assert "GET" in content

    # Verify Models section
    assert "## 4. Core Models & Data Contracts" in content
    assert "UserRecord" in content

    # Verify Files bundle
    assert len(res["files"]) == 1
    assert res["files"][0]["path"] == "BLUEPRINT.md"


# ── 3. Feature Mode Tests (2-Hop Interface Closure) ───────────────────────────

def test_feature_mode_2hop_closure(sample_graph, tmp_path):
    compiler = ReversePromptCompiler(sample_graph, str(tmp_path))
    
    # Target node: file:app/models.py
    # Hop 0: models.py
    # Hop 1: api.py (calls models), utils.py (models calls utils)
    # Hop 2: main.py (calls api), frontend/App.tsx (calls api)
    # 3+ hops away: unrelated/far_away.py (MUST NOT be in closure)
    res = compiler.compile(mode="feature", target_node_id="file:app/models.py")

    assert res["ok"] is True
    assert res["mode"] == "feature"
    content = res["content"]

    assert "# Feature Slice: `app/models.py`" in content
    assert "app/api.py" in content
    assert "app/utils.py" in content
    assert "unrelated/far_away.py" not in content


def test_feature_mode_invalid_target(sample_graph, tmp_path):
    compiler = ReversePromptCompiler(sample_graph, str(tmp_path))
    res = compiler.compile(mode="feature", target_node_id="non_existent_node_id")

    assert res["ok"] is True
    assert res["mode"] == "feature"
    assert "Target node 'non_existent_node_id' not found in graph" in res["content"]
    assert len(res["warnings"]) > 0


# ── 4. Spec Mode Tests (Templates) ────────────────────────────────────────────

def test_spec_mode_templates(sample_graph, tmp_path):
    compiler = ReversePromptCompiler(sample_graph, str(tmp_path))
    res = compiler.compile(mode="spec")

    assert res["ok"] is True
    assert res["mode"] == "spec"
    
    paths = {f["path"] for f in res["files"]}
    assert "CLAUDE.md" in paths
    assert "AGENTS.md" in paths
    assert "llms.txt" in paths
    assert ".kiro/specs/architecture.md" in paths
    assert ".kiro/specs/requirements.md" in paths
    assert ".kiro/specs/design.md" in paths
    assert ".kiro/specs/tasks.md" in paths

    # Check content of CLAUDE.md
    claude_md = next(f["content"] for f in res["files"] if f["path"] == "CLAUDE.md")
    assert "CLAUDE.md" in claude_md
    assert "Build & Test Commands" in claude_md

    # Check content of AGENTS.md
    agents_md = next(f["content"] for f in res["files"] if f["path"] == "AGENTS.md")
    assert "AGENTS.md" in agents_md
    assert "Autonomous Agent Work Agreement" in agents_md


# ── 5. Context Mode Tests (Budget & Tokens) ───────────────────────────────────

def test_context_mode_budget_and_tokens(sample_graph, tmp_path):
    compiler = ReversePromptCompiler(sample_graph, str(tmp_path))
    
    # Standard budget
    res = compiler.compile(mode="context", budget=5000)
    assert res["ok"] is True
    assert res["mode"] == "context"
    assert res["tokens"] > 0
    assert "Budget: 5000 tokens" in res["content"]

    # Budget clamp test: under 500 clamped to 500
    res_clamped = compiler.compile(mode="context", budget=100)
    assert "Budget: 500 tokens" in res_clamped["content"]


# ── 6. L2 Contract & Backward Compatibility Tests ─────────────────────────────

def test_endpoint_backward_compatibility_empty_body(client, loaded_repo):
    """Call POST /api/repo/reverse-prompt with empty JSON body.
    Existing {prompt: '...'} callers MUST receive valid non-empty string.
    """
    res = client.post("/api/repo/reverse-prompt", json={})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["ok"] is True
    assert data["mode"] == "context"
    assert isinstance(data["prompt"], str)
    assert len(data["prompt"]) > 0
    assert data["prompt"] == data["content"]
    assert isinstance(data["tokens"], int)
    assert data["tokens"] > 0
    assert isinstance(data["files"], list)


def test_endpoint_rebuild_mode(client, loaded_repo):
    res = client.post("/api/repo/reverse-prompt", json={"mode": "rebuild"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["ok"] is True
    assert data["mode"] == "rebuild"
    assert "Topological Build Order" in data["content"]
    assert data["prompt"] == data["content"]


def test_endpoint_feature_mode(client, loaded_repo):
    res = client.post("/api/repo/reverse-prompt", json={"mode": "feature"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["ok"] is True
    assert data["mode"] == "feature"
    assert "Feature Slice" in data["content"]


def test_endpoint_spec_mode(client, loaded_repo):
    res = client.post("/api/repo/reverse-prompt", json={"mode": "spec"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["ok"] is True
    assert data["mode"] == "spec"
    assert len(data["files"]) >= 4
    paths = [f["path"] for f in data["files"]]
    assert "CLAUDE.md" in paths
    assert "AGENTS.md" in paths


def test_endpoint_additive_alias(client, loaded_repo):
    """POST /api/reverse-prompt is an additive alias for /api/repo/reverse-prompt."""
    res = client.post("/api/reverse-prompt", json={"mode": "rebuild"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["ok"] is True
    assert data["mode"] == "rebuild"
    assert "BLUEPRINT.md" in [f["path"] for f in data["files"]]


def test_endpoint_no_repo_loaded(client, monkeypatch):
    monkeypatch.setattr(main, "load_state", lambda: {})
    res = client.post("/api/repo/reverse-prompt", json={})
    assert res.status_code == 400
    assert "No repo loaded" in res.json()["detail"]
