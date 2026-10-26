"""
test_mindmap_classifier.py
The six-pillar taxonomy and the deterministic tree projection.

The classifier is a contract, not a heuristic: every rule has a fixed
precedence, and every path resolves to exactly one pillar and one role.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from graph_builder import build_graph_from_repo
from mindmap import ancestor_ids, build_mindmap_payload, count_tree_nodes
from mindmap_classifier import (
    PILLARS,
    PILLAR_IDS,
    classify_file,
    classify_symbol,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v2_contract"


def _walk(node: dict):
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


# ── Pillar and role rules ───────────────────────────────────────────────────

def test_there_are_exactly_six_stable_pillars():
    assert len(PILLARS) == 6
    assert len(set(PILLAR_IDS)) == 6
    assert PILLAR_IDS == (
        "frontend", "backend", "data", "infrastructure", "tests", "docs",
    )


def test_tests_win_over_docs_and_backend():
    assert classify_file("tests/test_api.py") == {"pillar": "tests", "role": "test"}
    assert classify_file("docs/test_examples.md")["pillar"] == "tests"


def test_infrastructure_wins_over_documentation():
    assert classify_file(".github/workflows/qa.yml") == {
        "pillar": "infrastructure", "role": "config",
    }
    assert classify_file("frontend/package.json") == {
        "pillar": "infrastructure", "role": "config",
    }


def test_docs_are_docs_even_when_the_suffix_is_plain_text():
    assert classify_file("docs/architecture/overview.md") == {
        "pillar": "docs", "role": "docs",
    }
    assert classify_file("README") == {"pillar": "docs", "role": "docs"}


def test_data_and_repository_roles():
    assert classify_file("backend/models/user.py")["pillar"] == "data"
    assert classify_file("backend/models/user.py")["role"] == "model"
    assert classify_file("backend/migrations/0001_init.sql")["pillar"] == "data"
    assert classify_file("backend/repositories/user_repo.py")["role"] == "repository"


def test_frontend_components_and_hooks():
    assert classify_file("frontend/src/components/Card.tsx") == {
        "pillar": "frontend", "role": "ui_component",
    }
    assert classify_file("frontend/src/hooks/useRepo.ts") == {
        "pillar": "frontend", "role": "hook",
    }


def test_backend_entry_points_and_controllers():
    assert classify_file("backend/main.py") == {
        "pillar": "backend", "role": "entry_point",
    }
    assert classify_file("backend/api/routers/analysis.py")["role"] == "api_controller"
    assert classify_file("backend/anything.py", route_count=2)["role"] == "api_controller"


def test_unknown_code_falls_back_to_backend_utility():
    assert classify_file("scripts/random_tool.py") == {
        "pillar": "backend", "role": "utility",
    }


def test_symbol_role_inherits_the_file_unless_it_has_routes():
    node = {"type": "function", "label": "health"}
    assert classify_symbol(node, "entry_point") == "entry_point"
    assert classify_symbol({**node, "routes": [{"method": "GET"}]}, "utility") == "api_controller"


def test_classification_is_deterministic():
    paths = [
        "frontend/src/App.tsx",
        "backend/main.py",
        "tests/test_x.py",
        "docs/README.md",
        "infra/render.yaml",
        "data/schema.sql",
    ]
    first = [classify_file(path) for path in paths]
    second = [classify_file(path) for path in paths]
    assert first == second


# ── Tree projection ─────────────────────────────────────────────────────────

def _payload(**kwargs) -> dict:
    graph = build_graph_from_repo(str(FIXTURE))
    return build_mindmap_payload(graph, **kwargs)


def test_first_paint_has_root_and_six_pillars():
    payload = _payload()
    assert payload["root"]["id"] == "root"
    assert [child["id"] for child in payload["root"]["children"]] == [
        f"pillar:{pillar_id}" for pillar_id in PILLAR_IDS
    ]
    assert payload["stats"]["pillars"] == 6


def test_folders_are_nested_under_the_pillar_without_a_redundant_root_folder():
    graph = build_graph_from_repo(str(Path(__file__).resolve().parent / "fixtures" / "nested"))
    payload = build_mindmap_payload(graph)
    ids = {node["id"] for node in _walk(payload["root"])}
    assert "pillar:backend" in ids
    assert "folder:backend:src" in ids
    assert "folder:backend:src/core" in ids
    assert "folder:backend:src/core/domain" in ids
    assert "file:src/core/domain/service.py" in ids


def test_pillar_root_is_not_a_second_folder_level():
    """
    `backend/api/routers/x.py` belongs to a folder whose id and path keep
    the repository-relative `backend/api/routers` prefix, but there is no
    extra `backend` folder between the pillar and `api`.
    """
    graph = {
        "nodes": [{
            "id": "file:backend/api/routers/x.py",
            "type": "file",
            "label": "x.py",
            "path": "backend/api/routers/x.py",
            "language": "py",
            "size": 12,
        }],
        "edges": [],
        "schema_version": 2,
    }
    payload = build_mindmap_payload(graph)
    by_id = {node["id"]: node for node in _walk(payload["root"])}

    assert "folder:backend:backend/api" in by_id
    assert "folder:backend:backend/api/routers" in by_id
    assert by_id["folder:backend:backend/api"]["label"] == "api"
    assert by_id["folder:backend:backend/api"]["path"] == "backend/api"
    assert by_id["folder:backend:backend/api/routers"]["label"] == "routers"
    assert by_id["folder:backend:backend/api/routers"]["path"] == "backend/api/routers"
    assert "folder:backend:backend" not in by_id
    assert by_id["file:backend/api/routers/x.py"]["parent_id"] == (
        "folder:backend:backend/api/routers"
    )


def test_file_then_symbol_hierarchy():
    payload = _payload()
    by_id = {node["id"]: node for node in _walk(payload["root"])}
    file_node = by_id["file:server.py"]
    assert file_node["kind"] == "file"
    assert file_node["role"] == "entry_point"
    assert file_node["route_count"] == 3
    symbol = by_id["func:server.py:health"]
    assert symbol["kind"] == "symbol"
    assert symbol["parent_id"] == "file:server.py"
    assert symbol["role"] == "api_controller"


def test_include_symbols_false_truncates_at_file_level():
    payload = _payload(include_symbols=False)
    kinds = Counter(node["kind"] for node in _walk(payload["root"]))
    assert kinds["symbol"] == 0
    assert kinds["file"] >= 1


def test_max_nodes_keeps_root_and_pillars_first():
    payload = _payload(max_nodes=7)
    assert count_tree_nodes(payload) == 7
    assert payload["truncated"] is True
    assert payload["omitted"] > 0
    assert [child["id"] for child in payload["root"]["children"]] == [
        f"pillar:{pillar_id}" for pillar_id in PILLAR_IDS
    ]


def test_max_nodes_is_deterministic_and_parent_before_child():
    first = _payload(max_nodes=12)
    second = _payload(max_nodes=12)
    assert first == second
    assert count_tree_nodes(first) <= 12

    ids = {node["id"] for node in _walk(first["root"])}
    for node in _walk(first["root"]):
        if node["parent_id"] is not None:
            assert node["parent_id"] in ids


def test_payload_has_no_duplicate_node_ids():
    payload = _payload()
    ids = [node["id"] for node in _walk(payload["root"])]
    assert len(ids) == len(set(ids))


def test_ancestor_ids_returns_the_path_to_a_symbol():
    payload = _payload()
    path = ancestor_ids(payload, "func:server.py:health")
    assert path == ["root", "pillar:backend", "file:server.py", "func:server.py:health"]
    assert ancestor_ids(payload, "file:does-not-exist.py") == []


def test_empty_graph_still_produces_a_valid_tree():
    payload = build_mindmap_payload({"nodes": [], "edges": []})
    assert payload["root"]["id"] == "root"
    assert len(payload["root"]["children"]) == 6
    assert all(child["children"] == [] for child in payload["root"]["children"])
    assert payload["stats"]["files"] == 0
