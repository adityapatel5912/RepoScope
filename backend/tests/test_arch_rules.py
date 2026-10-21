"""
test_arch_rules.py
Tests for backend/arch_rules.py — the single source of truth for the
architecture model (Correction C6).

The headline test is `test_python_classifier_matches_typescript` — it runs
the frontend's own rules (scripts/parity_classify.js, a verbatim copy of
layerClassifier.ts) over a shared corpus and asserts byte-identical
classifications. If the frontend rule table changes without the backend
changing, that test fails.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from arch_rules import (
    ALLOWED_IMPORTS,
    DEFAULT_LAYER,
    LAYERS,
    LAYER_RULES,
    RuleSet,
    check_boundary,
    check_import,
    classify,
    is_allowed,
    load_ruleset,
    to_api_payload,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = Path(__file__).resolve().parent / "fixtures" / "layer_corpus.json"
PARITY_SCRIPT = REPO_ROOT / "scripts" / "parity_classify.js"


# ── Parity with the frontend implementation ─────────────────────────────────

def _corpus_cases() -> list[tuple[str, str]]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    return [tuple(case) for case in data["cases"]]


def test_corpus_is_not_empty():
    assert len(_corpus_cases()) >= 50


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_python_classifier_matches_typescript():
    """backend/arch_rules.py must agree with layerClassifier.ts, case for case."""
    result = subprocess.run(
        ["node", str(PARITY_SCRIPT), str(CORPUS)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    ts_layers = json.loads(result.stdout)

    cases = _corpus_cases()
    assert len(ts_layers) == len(cases)

    mismatches = []
    for (node_id, label), ts_layer in zip(cases, ts_layers):
        py_layer = classify(node_id, label)
        if py_layer != ts_layer:
            mismatches.append(
                f"{node_id!r} / {label!r}: typescript={ts_layer} python={py_layer}"
            )
    assert not mismatches, "layer classifier drift:\n" + "\n".join(mismatches)


# ── Canonical layers ────────────────────────────────────────────────────────

def test_five_canonical_layers():
    assert LAYERS == ("client", "backend", "storage", "external", "compute")


def test_rule_order_is_preserved():
    """First match wins — the ordering is load-bearing, so pin it."""
    assert [layer for layer, _ in LAYER_RULES] == [
        "external", "compute", "storage", "backend", "client",
    ]


def test_classify_examples():
    assert classify("file:src/components/Button.tsx", "Button.tsx") == "client"
    assert classify("file:backend/main.py", "main.py") == "backend"
    assert classify("file:src/models/user.py", "user.py") == "storage"
    assert classify("file:webhooks/stripe.py", "stripe.py") == "external"
    assert classify("file:workers/celery.py", "celery.py") == "compute"


def test_classify_falls_back_to_extension_then_default():
    # No ordered rule matches, but the .ts extension does.
    assert classify("file:src/util/helpers.ts", "helpers.ts") == "client"
    # A non-code file is classified by its kind, not by falling through to
    # the default. A README is a document, not backend code.
    assert classify("file:README.md", "README.md") == "storage"
    # Nothing matches at all — a file with no extension and no signal.
    assert classify("file:somefile", "somefile") == DEFAULT_LAYER


# ── Dependency policy ───────────────────────────────────────────────────────

def test_default_policy_matrix():
    assert ALLOWED_IMPORTS["client"] == frozenset(
        {"client", "backend", "storage", "external", "compute"}
    )
    assert ALLOWED_IMPORTS["storage"] == frozenset({"storage", "external"})
    assert ALLOWED_IMPORTS["external"] == frozenset({"external"})


@pytest.mark.parametrize(
    "source,target,allowed",
    [
        ("client", "backend", True),
        ("client", "storage", True),
        ("backend", "storage", True),
        ("compute", "backend", True),
        ("storage", "storage", True),
        ("storage", "external", True),
        ("storage", "client", False),
        ("backend", "client", False),
        ("compute", "client", False),
        ("external", "backend", False),
        ("external", "client", False),
        ("external", "storage", False),
    ],
)
def test_is_allowed(source, target, allowed):
    assert is_allowed(source, target) is allowed


def test_check_import_returns_violation_dict():
    violation = check_import(
        "storage", "client", "src/models/user.py", "src/components/Table.tsx"
    )
    assert violation is not None
    assert violation["severity"] == "error"
    assert violation["source_layer"] == "storage"
    assert violation["target_layer"] == "client"
    assert "src/models/user.py" in violation["message"]


def test_check_import_returns_none_when_allowed():
    assert check_import("client", "backend", "a.tsx", "b.py") is None


# ── .reposcope.yml loading ──────────────────────────────────────────────────

def test_load_ruleset_without_config_returns_defaults(tmp_path):
    ruleset = load_ruleset(tmp_path)
    assert ruleset.source is None
    assert ruleset.domains == ()
    assert ruleset.rules == ()
    assert ruleset.errors == []


def test_load_ruleset_reads_valid_config(tmp_path):
    (tmp_path / ".reposcope.yml").write_text(
        "version: 1\n"
        "layers:\n"
        "  - name: domain\n"
        "    include: ['src/domain/**']\n"
        "  - name: infra\n"
        "    include: ['src/infra/**']\n"
        "rules:\n"
        "  - id: no-domain-to-infra\n"
        "    from: domain\n"
        "    to: infra\n"
        "    severity: error\n"
        "ignore: ['**/generated/**']\n",
        encoding="utf-8",
    )
    ruleset = load_ruleset(tmp_path)
    assert ruleset.errors == []
    assert [d.name for d in ruleset.domains] == ["domain", "infra"]
    assert ruleset.rules[0].id == "no-domain-to-infra"
    assert ruleset.rules[0].severity == "error"
    assert ruleset.ignore == ("**/generated/**",)


def test_malformed_config_never_raises(tmp_path):
    (tmp_path / ".reposcope.yml").write_text(
        "version: 1\nlayers: [ unclosed\n", encoding="utf-8"
    )
    ruleset = load_ruleset(tmp_path)
    assert ruleset.errors, "malformed config must report an error"
    assert ruleset.source is not None


def test_config_with_unknown_domain_is_reported(tmp_path):
    (tmp_path / ".reposcope.yml").write_text(
        "version: 1\n"
        "layers:\n"
        "  - name: domain\n"
        "    include: ['src/**']\n"
        "rules:\n"
        "  - id: bogus\n"
        "    from: domain\n"
        "    to: nowhere\n",
        encoding="utf-8",
    )
    ruleset = load_ruleset(tmp_path)
    assert any("nowhere" in e for e in ruleset.errors)
    assert ruleset.rules == ()


def test_domain_for_matching(tmp_path):
    (tmp_path / ".reposcope.yml").write_text(
        "version: 1\n"
        "layers:\n"
        "  - name: domain\n"
        "    include: ['src/domain/**']\n"
        "  - name: infra\n"
        "    include: ['src/infra/**']\n"
        "ignore: ['**/generated/**']\n",
        encoding="utf-8",
    )
    ruleset = load_ruleset(tmp_path)
    assert ruleset.domain_for("src/domain/user.py") == "domain"
    assert ruleset.domain_for("src/infra/db.py") == "infra"
    assert ruleset.domain_for("src/other/x.py") is None
    assert ruleset.domain_for("src/domain/generated/gen.py") is None


# ── Boundary checks ─────────────────────────────────────────────────────────

def _ruleset_with_rule(tmp_path: Path) -> RuleSet:
    (tmp_path / ".reposcope.yml").write_text(
        "version: 1\n"
        "layers:\n"
        "  - name: domain\n"
        "    include: ['src/domain/**']\n"
        "  - name: infra\n"
        "    include: ['src/infra/**']\n"
        "rules:\n"
        "  - id: no-domain-to-infra\n"
        "    from: domain\n"
        "    to: infra\n"
        "    severity: error\n",
        encoding="utf-8",
    )
    return load_ruleset(tmp_path)


def test_check_boundary_flags_forbidden_edge(tmp_path):
    ruleset = _ruleset_with_rule(tmp_path)
    violation = check_boundary(
        ruleset, "src/domain/user.py", "src/infra/db.py"
    )
    assert violation is not None
    assert violation["id"] == "no-domain-to-infra"
    assert violation["kind"] == "domain-boundary"


def test_check_boundary_allows_same_domain(tmp_path):
    ruleset = _ruleset_with_rule(tmp_path)
    assert check_boundary(ruleset, "src/domain/a.py", "src/domain/b.py") is None


def test_check_boundary_allows_undeclared_side(tmp_path):
    ruleset = _ruleset_with_rule(tmp_path)
    assert check_boundary(ruleset, "src/other/a.py", "src/infra/db.py") is None


def test_check_boundary_without_rules_returns_none():
    assert check_boundary(RuleSet(), "a.py", "b.py") is None


# ── API payload ─────────────────────────────────────────────────────────────

def test_api_payload_shape():
    payload = to_api_payload()
    assert payload["default_layer"] == DEFAULT_LAYER
    assert [layer["id"] for layer in payload["layers"]] == list(LAYERS)
    assert len(payload["layer_rules"]) == len(LAYER_RULES)
    assert set(payload["allowed_imports"]) == set(LAYERS)
    assert payload["domains"] == []
    assert payload["boundary_rules"] == []
    assert payload["config_errors"] == []


def test_api_payload_includes_config_rules(tmp_path):
    payload = to_api_payload(_ruleset_with_rule(tmp_path))
    assert payload["domains"][0]["name"] == "domain"
    assert payload["boundary_rules"][0]["id"] == "no-domain-to-infra"
    assert payload["config_source"] is not None
