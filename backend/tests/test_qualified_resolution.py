"""
test_qualified_resolution.py
Tier-4 symbol resolution (M9.2): `repo.save()` resolves when — and only
when — the parser can say what `repo` is.

The negative assertions matter as much as the positive ones. A resolver
that guesses produces a plausible graph with wrong blast radii, which is
worse than one that leaves a call unresolved.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from graph_builder import (
    GraphIndexer,
    build_graph_from_repo,
    collect_facts,
    parse_bytes,
)
from parse_cache import ParseCache

FIXTURES = Path(__file__).resolve().parent / "fixtures"
QUALIFIED = FIXTURES / "qualified"


def _calls(graph: dict) -> set[tuple[str, str]]:
    return {
        (edge["source"], edge["target"])
        for edge in graph.get("edges", [])
        if edge.get("type") == "calls"
    }


def _graph() -> dict:
    return build_graph_from_repo(str(QUALIFIED))


# ── Positive: the receiver type is locally knowable ────────────────────────

def test_annotated_variable_resolves_to_the_method():
    calls = _calls(_graph())
    assert ("func:app.py:run", "func:services.py:save@4") in calls


def test_constructor_inference_resolves_without_an_annotation():
    calls = _calls(_graph())
    assert ("func:app.py:inferred", "func:services.py:load") in calls


def test_parameter_annotation_resolves():
    calls = _calls(_graph())
    assert ("func:app.py:annotated_parameter", "func:services.py:save@4") in calls


def test_typescript_annotation_and_constructor_resolve():
    calls = _calls(_graph())
    assert ("func:client.ts:work", "func:user.ts:save@2") in calls
    assert ("func:client.ts:work", "func:user.ts:load") in calls
    assert ("func:client.ts:parameterWork", "func:user.ts:load") in calls
    assert ("func:client.ts:adminWork", "func:user.ts:save@12") in calls


def test_module_level_receiver_is_attributed_to_the_file():
    calls = _calls(_graph())
    assert ("file:client.ts", "func:user.ts:save@2") in calls


def test_self_and_this_resolve_to_the_enclosing_class():
    calls = _calls(_graph())
    assert ("func:client.ts:local", "func:client.ts:help") in calls


def test_reassignment_changes_the_inferred_type():
    calls = _calls(_graph())
    # `repo = Cache()` shadows the annotated Repo; the call after it
    # belongs to Cache.save, not Repo.save.
    assert ("func:app.py:shadowed", "func:services.py:save@15") in calls
    assert ("func:app.py:after_shadow", "func:services.py:save@4") in calls


# ── Negative: an unknown or chained receiver is not guessed ───────────────

def test_chained_receiver_is_resolved_through_declared_attributes():
    calls = _calls(_graph())
    # `self.repo = Repo()` declares the attribute type, so the chained
    # call resolves to Repo.save — and must never become Controller.save.
    assert ("func:app.py:persist", "func:services.py:save@4") in calls
    assert ("func:app.py:persist", "func:app.py:save") not in calls
    assert ("func:client.ts:persist", "func:user.ts:save@2") in calls
    assert ("func:client.ts:persist", "func:client.ts:save") not in calls


def test_unknown_receiver_adds_no_call_edge():
    graph = _graph()
    assert not any(
        edge["type"] == "calls"
        and edge["source"] == "func:app.py:__init__"
        and edge["target"].endswith(":save")
        for edge in graph["edges"]
    )


# ── Receiver facts are parser-owned and cached ────────────────────────────

def test_receivers_are_extracted_per_file():
    facts = collect_facts(str(QUALIFIED))
    python = facts["app.py"].receivers
    typescript = facts["client.ts"].receivers

    assert any(r["name"] == "repo" and r["type"] == "Repo" for r in python)
    assert any(r["name"] == "typed" and r["type"] == "User" for r in typescript)
    # The shadowing assignment is recorded with its own line.
    assert {"Repo", "Cache"} <= {r["type"] for r in python if r["name"] == "repo"}


def test_receiver_facts_survive_a_cache_round_trip(tmp_path: Path):
    path = tmp_path / "cache.json"
    cache = ParseCache(path)
    facts = cache.get_for(
        QUALIFIED / "app.py",
        "app.py",
        lambda data, rel: parse_bytes(data, rel, ".py"),
    )
    cache.save()

    reloaded = ParseCache(path)
    assert reloaded.load() == 1
    restored = reloaded.get(facts.sha256)
    assert restored is not None
    assert any(r["type"] == "Repo" for r in restored.receivers)


# ── The incremental index must agree with the full rebuild ────────────────

def test_incremental_index_matches_full_rebuild_after_class_edit(tmp_path: Path):
    repo = tmp_path / "repo"
    shutil.copytree(QUALIFIED, repo)
    indexer = GraphIndexer(repo, ParseCache(repo / ".reposcope" / "cache.json"))
    indexer.index()

    services = repo / "services.py"
    services.write_text(
        services.read_text(encoding="utf-8")
        + "\n    def remove(self) -> str:\n        return 'removed'\n",
        encoding="utf-8",
    )
    indexer.apply(["services.py"])

    def shape(graph: dict):
        return (
            {(n["id"], n.get("type")) for n in graph["nodes"]},
            {(e["source"], e["target"], e["type"]) for e in graph["edges"]},
        )

    assert shape(indexer.graph) == shape(build_graph_from_repo(str(repo)))
