"""
test_pr_bot.py
PR Bot 2.0 — the architecture governance layer.

Milestones 5 and 8.2, plus the M10 repositioning.

The acceptance criteria, in the roadmap's words:

* "A PR that renames a required parameter is flagged as BREAKING, and
  the flag names the CONSUMING files, not the containing directory."
* "A PR that renames a private helper is NOT flagged."
* "SARIF 2.1.0 valid; findings render inline on a PR."
* "Baseline mode reports only new findings."
* "The merge gate blocks a PR exceeding the threshold — and passes a
  clean one."
"""
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def graph():
    from graph_builder import build_graph_from_repo

    return build_graph_from_repo(str(FIXTURES_DIR / "multilang"))


# ── The architecture impact report ──────────────────────────────────────────

def test_a_renamed_required_parameter_is_flagged_with_its_consumers(graph):
    """The CONSUMING files, not the containing directory."""
    from architecture_impact import analyze_architecture_impact
    from contract_diff import diff_sources

    old = "def shout(text: str) -> str:\n    return text.upper()\n"
    new = "def yell(text: str) -> str:\n    return text.upper()\n"

    findings = diff_sources(old, new, "helpers.py")
    impact = analyze_architecture_impact(
        graph,
        [{"filename": "helpers.py", "patch": ""}],
        findings,
    )

    assert impact["breaking_contracts"] >= 1

    # The consuming file is named.
    consumers = impact["consumers"]
    assert "app.py" in consumers, f"the consumer was not named: {consumers}"

    # And it is the CONSUMER, not every file in the directory.
    assert "helpers.py" not in consumers


def test_a_renamed_private_helper_is_not_flagged(graph):
    """The criterion that decides whether a bot gets muted."""
    from architecture_impact import analyze_architecture_impact
    from contract_diff import diff_sources

    old = "def _helper(text: str) -> str:\n    return text\n"
    new = "def _helper2(text: str) -> str:\n    return text\n"

    findings = diff_sources(old, new, "helpers.py")
    impact = analyze_architecture_impact(
        graph,
        [{"filename": "helpers.py", "patch": ""}],
        findings,
    )

    assert impact["breaking_contracts"] == 0
    assert impact["finding_count"] == 0


def test_the_report_counts_the_cycles(graph):
    from architecture_impact import analyze_architecture_impact

    impact = analyze_architecture_impact(graph, [{"filename": "app.py"}])
    assert "cycle_count" in impact
    assert impact["cycle_count"] == 0  # the multilang fixture has none


def test_the_circular_fixture_reports_its_cycles():
    from architecture_impact import analyze_architecture_impact
    from graph_builder import build_graph_from_repo

    circular = build_graph_from_repo(str(FIXTURES_DIR / "circular"))
    impact = analyze_architecture_impact(circular, [{"filename": "alpha.py"}])
    assert impact["cycle_count"] >= 4


# ── The merge gate ──────────────────────────────────────────────────────────

def test_the_risk_score_is_normalised_to_the_gate_scale():
    """Risk R10: the API says 0-10, the gate says 0-100."""
    from architecture_impact import normalize_risk_score

    assert normalize_risk_score(0) == 0
    assert normalize_risk_score(5) == 50
    assert normalize_risk_score(10) == 100
    assert normalize_risk_score(7) == 70


def test_the_normalisation_is_clamped():
    """An unclamped conversion turns a score of 10 into 1000."""
    from architecture_impact import normalize_risk_score

    assert normalize_risk_score(100) == 100
    assert normalize_risk_score(-5) == 0
    assert normalize_risk_score("nonsense") == 0


def test_the_gate_blocks_on_a_broken_contract():
    from architecture_impact import merge_gate

    impact = {"breaking_contracts": 1, "boundary_violations": 0}
    gate = merge_gate(impact, risk_score=3)

    assert gate["passed"] is False
    assert "breaking-contract" in gate["blocked_by"]
    assert gate["risk_score_0_100"] == 30


def test_the_gate_passes_a_clean_pull_request():
    from architecture_impact import merge_gate

    impact = {"breaking_contracts": 0, "boundary_violations": 0}
    gate = merge_gate(impact, risk_score=2)

    assert gate["passed"] is True
    assert gate["blocked_by"] == []
    assert gate["reasons"] == []


def test_the_gate_blocks_on_an_over_threshold_risk_score():
    from architecture_impact import merge_gate

    impact = {"breaking_contracts": 0, "boundary_violations": 0}
    gate = merge_gate(impact, risk_score=9, max_allowed_risk_score=75)

    assert gate["passed"] is False
    assert "risk-score" in gate["blocked_by"]
    assert gate["risk_score_0_100"] == 90


def test_the_gate_blocks_on_a_boundary_violation():
    from architecture_impact import merge_gate

    impact = {"breaking_contracts": 0, "boundary_violations": 2}
    gate = merge_gate(impact, risk_score=1)

    assert gate["passed"] is False
    assert "boundary-violation" in gate["blocked_by"]


def test_the_gate_can_require_tests():
    from architecture_impact import merge_gate

    impact = {"breaking_contracts": 0, "boundary_violations": 0}
    gate = merge_gate(
        impact, risk_score=1,
        require_tests_for_high_risk=True,
        missing_tests=["backend/auth.py"],
    )
    assert gate["passed"] is False
    assert "missing-tests" in gate["blocked_by"]


# ── The SARIF output ────────────────────────────────────────────────────────

def test_the_sarif_document_is_valid():
    """GitHub SILENTLY rejects a malformed SARIF file, so this matters."""
    from sarif import SarifResult, to_sarif

    document = to_sarif([
        SarifResult(
            rule_id="reposcope/breaking-contract",
            message="Parameter `name` of `greet` was renamed to `nickname`",
            file="backend/auth.py",
            line=42,
        ),
    ])

    assert document["version"] == "2.1.0"
    assert document["$schema"].endswith("sarif-schema-2.1.0.json")
    assert len(document["runs"]) == 1

    run = document["runs"][0]
    assert run["tool"]["driver"]["name"] == "RepoScope"
    assert run["tool"]["driver"]["version"]
    assert run["tool"]["driver"]["rules"], "the tool has no rule catalogue"

    assert len(run["results"]) == 1
    result = run["results"][0]
    assert result["ruleId"] == "reposcope/breaking-contract"
    assert result["level"] in ("error", "warning", "note", "none")
    assert result["message"]["text"]

    location = result["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "backend/auth.py"
    assert location["region"]["startLine"] == 42


def test_every_sarif_rule_is_in_the_catalogue():
    """A result whose rule is unknown renders as a useless annotation."""
    from sarif import RULES, SarifResult, to_sarif

    document = to_sarif([
        SarifResult(rule_id="reposcope/breaking-contract", message="x", file="a.py"),
    ])
    known = {rule["id"] for rule in document["runs"][0]["tool"]["driver"]["rules"]}
    assert known == {rule.id for rule in RULES}
    for result in document["runs"][0]["results"]:
        assert result["ruleId"] in known


def test_the_sarif_baseline_drops_pre_existing_findings():
    """A gate that reports pre-existing debt gets turned off."""
    from sarif import SarifResult, finding_key, to_sarif

    result = SarifResult(
        rule_id="reposcope/breaking-contract",
        message="something old",
        file="a.py",
        line=3,
    )
    key = finding_key(result.rule_id, result.file, result.line, result.message)

    with_baseline = to_sarif([result], baseline=[key])
    assert with_baseline["runs"][0]["results"] == []

    without_baseline = to_sarif([result])
    assert len(without_baseline["runs"][0]["results"]) == 1


def test_the_sarif_document_is_json_serialisable():
    from sarif import SarifResult, to_sarif_json

    text = to_sarif_json([SarifResult(
        rule_id="reposcope/boundary-violation",
        message="a violation",
        file="a.py",
    )])
    assert json.loads(text)["version"] == "2.1.0"


# ── The PR comment ──────────────────────────────────────────────────────────

def test_the_comment_carries_the_architecture_section(graph):
    from pr_impact import build_pr_impact

    meta = {"number": 7, "title": "A change", "state": "open"}
    files = [{
        "filename": "helpers.py",
        "status": "modified",
        "additions": 2,
        "deletions": 1,
        "patch": "-def shout(text: str) -> str:\n+def yell(text: str) -> str:\n",
    }]

    report = build_pr_impact(graph, meta, files)
    comment = report["comment"]

    assert "Architecture impact" in comment
    assert "Merge gate" in comment
    # The Mermaid fallback is still there — GitHub renders it natively
    # and it needs no external service.
    assert "```mermaid" in comment
    # The badges.
    assert "img.shields.io" in comment


def test_the_report_exposes_the_gate_and_the_sarif(graph):
    from pr_impact import build_pr_impact

    report = build_pr_impact(
        graph,
        {"number": 1, "title": "x", "state": "open"},
        [{"filename": "app.py", "status": "modified", "additions": 1, "deletions": 0}],
    )

    assert "merge_gate" in report
    assert "risk_score_0_100" in report["merge_gate"]
    assert "sarif" in report
    assert isinstance(report["sarif"], list)


# ── The conversational bot ──────────────────────────────────────────────────

def test_the_bot_understands_the_question(graph):
    from pr_chat import parse_command

    assert parse_command("@reposcope-bot explain risk for helpers.py")["intent"] == "risk"
    assert parse_command("@reposcope-bot suggest test cases")["intent"] == "tests"
    assert parse_command("@reposcope-bot verify architectural boundaries")["intent"] == "boundaries"
    assert parse_command("@reposcope-bot what breaks if I change helpers.py")["intent"] == "blast"
    assert parse_command("@reposcope-bot hello there")["intent"] == "help"


def test_the_bot_answers_with_citations(graph):
    from pr_chat import ChatRequest, answer

    request = ChatRequest(
        comment="@reposcope-bot explain risk for helpers.py",
        changed_files=[{"filename": "helpers.py"}],
        graph=graph,
    )
    result = answer(request)

    assert result["intent"] == "risk"
    assert "helpers.py" in result["answer"]
    assert result["citations"], "the answer cited nothing"
    assert any("app.py" in c["file"] for c in result["citations"])


def test_the_bot_names_the_untested_modules(graph):
    from pr_chat import ChatRequest, answer

    request = ChatRequest(
        comment="@reposcope-bot suggest test cases",
        changed_files=[{"filename": "helpers.py"}, {"filename": "greeter.go"}],
        graph=graph,
    )
    result = answer(request)

    assert result["intent"] == "tests"
    assert result["untested"]
    assert "helpers.py" in result["untested"]


def test_the_bot_reports_no_boundary_violations(graph):
    from pr_chat import ChatRequest, answer

    request = ChatRequest(
        comment="@reposcope-bot verify architectural boundaries",
        changed_files=[{"filename": "app.py"}],
        graph=graph,
    )
    result = answer(request)

    assert result["intent"] == "boundaries"
    assert "No boundary violations" in result["answer"]


def test_the_bot_survives_an_empty_graph():
    from pr_chat import ChatRequest, answer

    request = ChatRequest(
        comment="@reposcope-bot explain risk for anything.py",
        changed_files=[],
        graph={"nodes": [], "edges": []},
    )
    result = answer(request)
    assert result["intent"] == "risk"
    assert result["answer"]


# ── The test-stub generator ─────────────────────────────────────────────────

def test_the_stub_generator_marks_its_output():
    """A generated test must never be mistaken for a reviewed one."""
    from test_stubs import GENERATED_MARKER, _mark_generated

    marked = _mark_generated("def test_x():\n    pass\n")
    assert GENERATED_MARKER in marked
    assert marked.startswith("#")


def test_the_stub_generator_finds_the_untested_modules(graph):
    from test_stubs import find_untested_modules

    # A test file for something ELSE — so helpers.py is genuinely
    # uncovered. (A file called test_helpers.py WOULD cover it, and the
    # generator says so.)
    untested = find_untested_modules(
        graph,
        ["helpers.py", "tests/test_other.py"],
        ["tests/test_other.py"],
    )
    assert "helpers.py" in untested
    assert "tests/test_other.py" not in untested


def test_the_stub_generator_knows_a_covered_module(graph):
    from test_stubs import find_untested_modules

    untested = find_untested_modules(
        graph,
        ["helpers.py"],
        ["tests/test_helpers.py"],
    )
    assert "helpers.py" not in untested


# ── The boundary fixture ───────────────────────────────────────────────────

def test_the_boundary_fixture_declares_its_own_rules():
    """A built-in taxonomy is a guess; a declared rule is a decision."""
    from arch_rules import load_ruleset

    ruleset = load_ruleset(FIXTURES_DIR / "boundary")
    assert len(ruleset.rules) == 1
    rule = ruleset.rules[0]
    assert rule.id == "no-domain-to-infra"
    assert rule.from_domain == "domain"
    assert rule.to_domain == "infra"
    assert rule.severity == "error"


def test_the_boundary_fixture_has_one_clean_file_and_one_violation():
    from architecture_impact import analyze_architecture_impact
    from arch_rules import load_ruleset
    from graph_builder import build_graph_from_repo

    root = FIXTURES_DIR / "boundary"
    graph = build_graph_from_repo(str(root))
    ruleset = load_ruleset(root)

    # `main.py` imports the domain — that is allowed.
    clean = analyze_architecture_impact(
        graph, [{"filename": "main.py"}], ruleset=ruleset, repo_root=str(root),
    )
    assert clean["boundary_violations"] == 0

    # `domain/orders.py` imports the infra — that is not.
    violating = analyze_architecture_impact(
        graph, [{"filename": "domain/orders.py"}], ruleset=ruleset, repo_root=str(root),
    )
    assert violating["boundary_violations"] == 1

    finding = violating["findings"][0]
    assert finding["kind"] == "boundary-violation"
    assert "domain/orders.py" in finding["title"]
    assert "infra/store.py" in finding["title"]


def test_the_boundary_violation_blocks_the_merge_gate():
    from architecture_impact import analyze_architecture_impact, merge_gate
    from arch_rules import load_ruleset
    from graph_builder import build_graph_from_repo

    root = FIXTURES_DIR / "boundary"
    graph = build_graph_from_repo(str(root))
    impact = analyze_architecture_impact(
        graph,
        [{"filename": "domain/orders.py"}],
        ruleset=load_ruleset(root),
        repo_root=str(root),
    )

    gate = merge_gate(impact, risk_score=2)
    assert gate["passed"] is False
    assert "boundary-violation" in gate["blocked_by"]
