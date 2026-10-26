"""
test_graph_golden.py
The golden-file test — the point of Sprint 0.

Correction C10: the node ids and edge types produced by graph_builder are
load-bearing. `pr_impact.py` looks nodes up by label,
`graph_utils.find_node_by_label` resolves targets by substring, the
pyramid ranking in the frontend depends on the node set, and
`frontend/src/components/GraphView.tsx:174` filters edges on
`type === "imports" || type === "calls"`.

Sprint 1 replaces the JS/TS regex parser with Tree-sitter. If that rewrite
changes a single node id, the pyramid silently re-ranks and blast radii
quietly shift — with no failing test and no visible symptom until someone
asks "why is this file in row 1?".

This test pins the contract:

    sorted [(node.id, node.type)]   == snapshot
    sorted [(source, target, type)] == snapshot
    summary                         == snapshot

Regeneration is EXPLICIT ONLY:

    cd backend && python -m pytest tests/test_graph_golden.py --regen-golden

It is never automatic, so a snapshot can never be silently rewritten to
match a broken parser.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from graph_builder import build_graph_from_repo

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

#: Golden snapshots live OUTSIDE the fixture directories.
#:
#: They must. The parser indexes every file it finds, so a snapshot stored
#: inside `fixtures/multilang/` would itself become a graph node
#: (`file:golden.json`) — the snapshot would then change the graph it is
#: supposed to describe, and the test could never be stable.
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

#: Every fixture that has a golden snapshot.
FIXTURE_NAMES = ("multilang", "circular", "nested", "real_small", "qualified")

#: Contract constants from Correction C10.
VALID_EDGE_TYPES = {"contains", "imports", "calls"}


def _regen_enabled() -> bool:
    return bool(pytestconfig.getoption("--regen-golden"))


def _snapshot_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def _snapshot_for(name: str) -> dict:
    path = _snapshot_path(name)
    if not path.exists():
        pytest.fail(
            f"Missing golden snapshot for fixture '{name}' at {path}. "
            f"Generate it with: python -m pytest tests/test_graph_golden.py --regen-golden"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _observed(graph: dict) -> dict:
    return {
        "nodes": sorted(
            [str(n.get("id", "")), str(n.get("type", ""))]
            for n in graph.get("nodes", [])
        ),
        "edges": sorted(
            [str(e.get("source", "")), str(e.get("target", "")), str(e.get("type", ""))]
            for e in graph.get("edges", [])
        ),
        "summary": graph.get("summary", ""),
    }


# ── The contract ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_graph_matches_golden_snapshot(name, pytestconfig):
    """The parsed graph must be byte-identical to the committed snapshot."""
    fixture_dir = FIXTURES_DIR / name
    graph = build_graph_from_repo(str(fixture_dir))
    observed = _observed(graph)

    # Regeneration happens BEFORE the snapshot is loaded — a first run has
    # no snapshot to compare against yet.
    if pytestconfig.getoption("--regen-golden"):
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        _snapshot_path(name).write_text(
            json.dumps(observed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        pytest.skip(f"regenerated golden snapshot for '{name}'")

    expected = _snapshot_for(name)

    if observed["nodes"] != expected["nodes"]:
        only_new = sorted(set(map(tuple, observed["nodes"])) - set(map(tuple, expected["nodes"])))
        only_old = sorted(set(map(tuple, expected["nodes"])) - set(map(tuple, observed["nodes"])))
        msg = [f"node ids drifted for fixture '{name}'"]
        if only_new:
            msg.append("  added:   " + ", ".join(f"{i}:{t}" for i, t in only_new))
        if only_old:
            msg.append("  removed: " + ", ".join(f"{i}:{t}" for i, t in only_old))
        pytest.fail("\n".join(msg))

    if observed["edges"] != expected["edges"]:
        only_new = sorted(set(map(tuple, observed["edges"])) - set(map(tuple, expected["edges"])))
        only_old = sorted(set(map(tuple, expected["edges"])) - set(map(tuple, observed["edges"])))
        msg = [f"edges drifted for fixture '{name}'"]
        if only_new:
            msg.append("  added:   " + ", ".join(f"{s}->{t} [{ty}]" for s, t, ty in only_new))
        if only_old:
            msg.append("  removed: " + ", ".join(f"{s}->{t} [{ty}]" for s, t, ty in only_old))
        pytest.fail("\n".join(msg))

    assert observed["summary"] == expected["summary"], (
        f"summary drifted for fixture '{name}': "
        f"{observed['summary']!r} != {expected['summary']!r}"
    )


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_graph_satisfies_the_node_edge_contract(name):
    """Structural invariants that must hold regardless of snapshot content."""
    graph = build_graph_from_repo(str(FIXTURES_DIR / name))

    node_ids = [n["id"] for n in graph["nodes"]]
    assert len(node_ids) == len(set(node_ids)), "duplicate node ids"

    known = set(node_ids)
    for edge in graph["edges"]:
        assert edge["type"] in VALID_EDGE_TYPES, f"unknown edge type {edge['type']!r}"
        assert edge["source"] in known, f"edge references unknown source {edge['source']!r}"
        assert edge["target"] in known, f"edge references unknown target {edge['target']!r}"

    for node in graph["nodes"]:
        assert node.get("id"), "node without id"
        assert node.get("label") is not None, f"node {node['id']} has no label"
        if node["type"] in ("function", "class"):
            assert "file" in node, f"symbol node {node['id']} has no file"


# ── Fixture-specific behaviour ──────────────────────────────────────────────

def test_multilang_resolves_every_language():
    """Python, TS, TSX, JS and Go must all produce file nodes."""
    graph = build_graph_from_repo(str(FIXTURES_DIR / "multilang"))
    ids = {n["id"] for n in graph["nodes"]}

    for rel in ("app.py", "helpers.py", "user.ts", "format.ts",
                "Card.tsx", "Button.tsx", "slug.js", "greeter.go"):
        assert f"file:{rel}" in ids, f"missing file node for {rel}"

    languages = {n.get("language") for n in graph["nodes"] if n["type"] == "file"}
    assert {"py", "ts", "tsx", "js", "go"} <= languages, f"missing languages: {languages}"


def test_multilang_resolves_relative_imports():
    """The import edges must land on real files, not dangle."""
    graph = build_graph_from_repo(str(FIXTURES_DIR / "multilang"))
    edges = {(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "imports"}

    assert ("file:user.ts", "file:format.ts") in edges
    assert ("file:Card.tsx", "file:format.ts") in edges
    assert ("file:Card.tsx", "file:Button.tsx") in edges
    assert ("file:slug.js", "file:format.ts") in edges
    assert ("file:app.py", "file:helpers.py") in edges


def test_multilang_ignores_external_imports():
    """`import "fmt"` must NOT create an edge to a file that does not exist."""
    graph = build_graph_from_repo(str(FIXTURES_DIR / "multilang"))
    node_ids = {n["id"] for n in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["target"] in node_ids


def test_circular_fixture_produces_file_and_symbol_cycles():
    """The circular fixture must contain exactly the cycles it was built for.

    Since Milestone 1.1 the graph carries `calls` edges as well as
    `imports` edges, so the cycle detector finds TWO levels of cycle:

      * file level   — alpha.py -> beta.py -> gamma.py -> alpha.py
      * symbol level — alpha_value -> beta_value -> gamma_value -> alpha_value

    The symbol-level cycles are the interesting ones: they were invisible
    to the import-only graph, and they name the exact functions that form
    the loop.
    """
    from graph_analysis import find_cycles

    graph = build_graph_from_repo(str(FIXTURES_DIR / "circular"))
    cycles = find_cycles(graph)
    members = {frozenset(c) for c in cycles}

    # File-level cycles.
    assert frozenset({"file:alpha.py", "file:beta.py", "file:gamma.py"}) in members
    assert frozenset({"file:a.ts", "file:b.ts", "file:c.ts"}) in members

    # Symbol-level cycles — the same loops, one level down.
    assert frozenset({
        "func:alpha.py:alpha_value",
        "func:beta.py:beta_value",
        "func:gamma.py:gamma_value",
    }) in members
    assert frozenset({
        "func:a.ts:aValue",
        "func:b.ts:bValue",
        "func:c.ts:cValue",
    }) in members

    assert len(cycles) == 4, f"expected exactly 4 cycles, got {cycles}"


def test_isolated_module_is_not_in_any_cycle():
    """`isolated.py` reaches into the cycle but nothing reaches back."""
    from graph_analysis import find_cycles

    graph = build_graph_from_repo(str(FIXTURES_DIR / "circular"))
    for cycle in find_cycles(graph):
        assert "file:isolated.py" not in cycle
        assert not any("isolated" in member for member in cycle)


def test_nested_fixture_resolves_relative_imports():
    """`from ..models import Entity` must resolve to src/core/models.py."""
    graph = build_graph_from_repo(str(FIXTURES_DIR / "nested"))
    edges = {(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "imports"}

    assert (
        "file:src/core/domain/service.py",
        "file:src/core/models.py",
    ) in edges, "level-2 relative import did not resolve"

    assert ("file:main.py", "file:src/core/domain/service.py") in edges
    assert ("file:main.py", "file:src/core/models.py") in edges


def test_real_small_fixture_parses_real_world_python():
    """The vendored real project must produce a non-trivial graph."""
    graph = build_graph_from_repo(str(FIXTURES_DIR / "real_small"))

    assert len(graph["nodes"]) > 10, "vendored project produced too few nodes"
    ids = {n["id"] for n in graph["nodes"]}
    assert "file:src/tomli/__init__.py" in ids
    assert "file:src/tomli/_parser.py" in ids
    assert "file:pyproject.toml" in ids, "non-source files must still become nodes"

    # The real package uses level-1 relative imports.
    edges = {(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "imports"}
    assert ("file:src/tomli/__init__.py", "file:src/tomli/_parser.py") in edges
    assert ("file:src/tomli/_parser.py", "file:src/tomli/_types.py") in edges


# ── The red/green proof ─────────────────────────────────────────────────────

def test_golden_test_detects_a_perturbed_node_id(tmp_path):
    """
    Prove the golden gate actually bites.

    A golden test that has never been observed failing proves nothing. This
    test rebuilds a fixture graph, perturbs one node id, and asserts the
    comparison reports the drift — the same comparison the real test uses.
    """
    graph = build_graph_from_repo(str(FIXTURES_DIR / "multilang"))
    expected = _snapshot_for("multilang")

    observed = _observed(graph)
    assert observed["nodes"] == expected["nodes"], "baseline must match first"

    # Perturb exactly one node id.
    victim = graph["nodes"][0]["id"]
    graph["nodes"][0]["id"] = victim + "__perturbed"
    perturbed = _observed(graph)

    assert perturbed["nodes"] != expected["nodes"], "perturbation was not detected"
    assert (
        victim + "__perturbed",
        graph["nodes"][0]["type"],
    ) in [tuple(n) for n in perturbed["nodes"]]


def test_snapshot_file_is_valid_json_and_complete():
    """Every fixture snapshot must exist and carry all three sections."""
    for name in FIXTURE_NAMES:
        snapshot = _snapshot_for(name)
        assert set(snapshot) == {"nodes", "edges", "summary"}, (
            f"snapshot for '{name}' is missing sections"
        )
        assert isinstance(snapshot["nodes"], list)
        assert isinstance(snapshot["edges"], list)
        assert isinstance(snapshot["summary"], str)
        assert snapshot["nodes"], f"snapshot for '{name}' has no nodes"
