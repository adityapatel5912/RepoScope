"""
architecture_impact.py
The Architecture Impact report.

Milestone 5 + Milestone 10. **This is the repositioning.**

The 2026 market for AI code review is crowded and RepoScope would lose
that fight: CodeRabbit, Greptile, Qodo, Copilot Code Review and Cursor's
BugBot all promise to catch bugs, and they do it better than a
tree-sitter graph can.

So RepoScope does not compete there. It asks a different question:

| RepoScope asks | Every AI reviewer ignores |
|---|---|
| Does this PR violate a declared architecture boundary? | — |
| Did this PR break a contract that has REAL consumers? | — |
| Did this PR introduce a dependency cycle? | — |
| Which consuming files must be regression-tested? | — |
| How much of the repo's context does an agent need to review this? | — |

Those are not "is this code buggy" questions. They are governance
questions, and no AI reviewer competes in them.

**Everything here is deterministic.** No LLM is involved in deciding
whether a PR is risky — that is the point. A governance gate has to be
reproducible, or it is a gate nobody trusts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from arch_rules import RuleSet, check_boundary, load_ruleset
from contract_diff import Finding, attach_consumers
from graph_analysis import find_cycles

log = logging.getLogger("reposcope.architecture_impact")


#: The risk score the API reports, on a 0-10 scale.
RISK_SCALE = 10

#: The risk score a merge gate's threshold is expressed on, 0-100.
#
# Risk R10: the API returns 0-10 while a CI action's
# `max_allowed_risk_score` implies 0-100. Normalising at the ACTION
# BOUNDARY — not inside the API — keeps the API's scale honest and
# documents the conversion in one place.
GATE_SCALE = 100


def normalize_risk_score(score: int | float) -> int:
    """
    Convert the API's 0-10 risk score to the gate's 0-100 scale.

    The conversion is explicit, rounded, and CLAMPED. An un-clamped
    conversion is how a score of 10 becomes 1000 and every gate passes.
    """
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0
    if value < 0:
        return 0
    if value > RISK_SCALE:
        value = RISK_SCALE
    return int(round(value * GATE_SCALE / RISK_SCALE))


@dataclass
class ArchitectureFinding:
    """One governance finding."""

    kind: str            # breaking-contract | boundary-violation | new-cycle | ...
    severity: str        # error | warning | note
    title: str
    detail: str
    file: str = ""
    line: int = 0
    symbol: str = ""
    rule_id: str = ""
    consumers: list[str] = field(default_factory=list)
    guidance: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "file": self.file,
            "line": self.line,
            "symbol": self.symbol,
            "rule_id": self.rule_id,
            "consumers": self.consumers,
            "guidance": self.guidance,
        }


def analyze_architecture_impact(
    graph: dict,
    changed_files: list[dict],
    contract_findings: list[Finding] | None = None,
    ruleset: RuleSet | None = None,
    repo_root: str | None = None,
) -> dict:
    """
    The Architecture Impact report for a pull request.

    `changed_files` is GitHub's shape: `{"filename": ..., "patch": ...}`.
    `contract_findings` are the AST contract changes (from
    `contract_diff`); they are passed in rather than recomputed so the
    caller stays the single owner of the detection.

    Returns the findings, the new cycles, the risk breakdown, and the
    merge-gate inputs.
    """
    if ruleset is None:
        try:
            ruleset = load_ruleset(repo_root)
        except Exception as exc:  # noqa: BLE001 - a broken config must not break the report
            log.warning("Could not load the rule set: %s", exc)
            ruleset = RuleSet()

    findings: list[ArchitectureFinding] = []

    # ── 1. Broken contracts, with their real consumers ──
    contract_findings = contract_findings or []
    attach_consumers(contract_findings, graph)
    for finding in contract_findings:
        if finding.severity != "BREAKING":
            continue
        findings.append(ArchitectureFinding(
            kind="breaking-contract",
            severity="error",
            title=f"Breaking change: {finding.symbol}",
            detail=finding.message,
            file=finding.file,
            line=finding.line,
            symbol=finding.symbol,
            rule_id="reposcope/breaking-contract",
            consumers=finding.consumers,
            guidance=finding.guidance,
        ))

    # ── 2. Boundary violations ──
    for changed in changed_files:
        filename = changed.get("filename") or ""
        if not filename:
            continue
        for target in _import_targets(graph, filename):
            violation = check_boundary(ruleset, filename, target)
            if violation is None:
                continue
            findings.append(ArchitectureFinding(
                kind="boundary-violation",
                severity="error",
                title=f"Boundary violation: {filename} → {target}",
                detail=violation.get("message", "This import crosses a declared boundary."),
                file=filename,
                rule_id="reposcope/boundary-violation",
                guidance=(
                    "The rule is declared by the team. Either the import is "
                    "wrong, or the boundary is wrong — both are worth a "
                    "conversation before the merge."
                ),
            ))

    # ── 3. Dependency cycles ──
    cycles = find_cycles(graph)
    cross_layer_cycles = [c for c in cycles if _crosses_layers(graph, c)]

    # ── 4. The risk breakdown ──
    breaking = sum(1 for f in findings if f.severity == "error")
    boundary = sum(1 for f in findings if f.kind == "boundary-violation")
    contracts = sum(1 for f in findings if f.kind == "breaking-contract")

    return {
        "findings": [f.to_dict() for f in findings],
        "finding_count": len(findings),
        "error_count": breaking,
        "breaking_contracts": contracts,
        "boundary_violations": boundary,
        "cycle_count": len(cycles),
        "cross_layer_cycles": len(cross_layer_cycles),
        "cycles": cycles[:20],
        "consumers": sorted({
            consumer
            for f in findings
            for consumer in f.consumers
        }),
    }


def _import_targets(graph: dict, filename: str) -> list[str]:
    """The files that the given file imports."""
    file_id = f"file:{filename}"
    targets: list[str] = []
    for edge in graph.get("edges", []) or []:
        if edge.get("type") != "imports" or edge.get("source") != file_id:
            continue
        target = str(edge.get("target", ""))
        if target.startswith("file:"):
            targets.append(target[len("file:"):])
    return targets


def _crosses_layers(graph: dict, cycle: list[str]) -> bool:
    """Does a cycle span more than one architectural layer?"""
    from arch_rules import classify

    layers = set()
    for member in cycle:
        node = next(
            (n for n in graph.get("nodes", []) or [] if n.get("id") == member), None,
        )
        if node is None:
            continue
        layers.add(classify(str(node.get("id", "")), str(node.get("label", ""))))
    return len(layers) > 1


# ── The merge gate ──────────────────────────────────────────────────────────

def merge_gate(
    impact: dict,
    risk_score: int,
    max_allowed_risk_score: int = 75,
    require_tests_for_high_risk: bool = False,
    block_on_breaking_contract: bool = True,
    missing_tests: list[str] | None = None,
) -> dict:
    """
    Decide whether a pull request may merge.

    **The threshold is on the 0-100 scale**, because that is what a CI
    action's input implies. The API's score is 0-10, and the conversion
    happens here, at the boundary, where it can be documented.

    The gate is deliberately narrow. It blocks on the things that are
    objectively wrong — a broken contract, a violated boundary — and not
    on "this code feels risky". A gate that blocks on taste gets
    disabled.
    """
    gate_score = normalize_risk_score(risk_score)
    reasons: list[str] = []
    blocking: list[str] = []

    if gate_score > max_allowed_risk_score:
        reasons.append(
            f"Risk score {gate_score}/100 is above the threshold "
            f"{max_allowed_risk_score}/100"
        )
        blocking.append("risk-score")

    if block_on_breaking_contract and impact.get("breaking_contracts", 0) > 0:
        reasons.append(
            f"{impact['breaking_contracts']} breaking contract change(s) "
            f"with real consumers"
        )
        blocking.append("breaking-contract")

    if impact.get("boundary_violations", 0) > 0:
        reasons.append(
            f"{impact['boundary_violations']} architectural boundary violation(s)"
        )
        blocking.append("boundary-violation")

    if require_tests_for_high_risk and missing_tests:
        reasons.append(
            f"{len(missing_tests)} high-risk module(s) have no test file: "
            + ", ".join(missing_tests[:5])
        )
        blocking.append("missing-tests")

    return {
        "passed": not blocking,
        "blocked_by": blocking,
        "reasons": reasons,
        "risk_score": risk_score,
        "risk_score_0_100": gate_score,
        "max_allowed_risk_score": max_allowed_risk_score,
        "threshold_scale": GATE_SCALE,
    }


# ── The comment ─────────────────────────────────────────────────────────────

def render_architecture_section(impact: dict, gate: dict, savings: dict | None = None) -> str:
    """
    The Architecture Impact section of the PR comment.

    Markdown only — GitHub renders it natively, and no service is
    involved.
    """
    lines: list[str] = ["### 🏛️ Architecture impact", ""]

    findings = impact.get("findings", [])
    if not findings:
        lines.append(
            "No boundary violations, no broken contracts, no new cycles. "
            "This change stays inside the architecture."
        )
        return "\n".join(lines)

    lines += [
        "| Finding | Severity | Where | Consumers |",
        "|---|---|---|---|",
    ]
    for finding in findings[:15]:
        where = f"`{finding['file']}`" if finding.get("file") else "—"
        if finding.get("line"):
            where += f":{finding['line']}"
        consumers = ", ".join(f"`{c}`" for c in finding.get("consumers", [])[:4]) or "—"
        lines.append(
            f"| {finding['title']} | {finding['severity']} | {where} | {consumers} |"
        )
    if len(findings) > 15:
        lines.append(f"| _…and {len(findings) - 15} more_ | | | |")

    if impact.get("consumers"):
        lines += [
            "",
            "**Files that consume the changed contracts:**",
            "",
            *[f"- `{c}`" for c in impact["consumers"][:12]],
        ]

    if impact.get("cycle_count"):
        lines += [
            "",
            f"**{impact['cycle_count']} dependency cycle(s)** detected "
            f"({impact.get('cross_layer_cycles', 0)} crossing layers).",
        ]

    if savings and savings.get("reduction_pct") is not None:
        lines += [
            "",
            f"**Context savings:** RepoScope's map of this repository costs "
            f"{savings.get('repo_map_tokens', 0):,} tokens against "
            f"{savings.get('full_context_tokens', 0):,} for the whole codebase — "
            f"a **{savings.get('reduction_pct', 0):.1f}%** reduction.",
        ]

    lines += ["", "#### Merge gate", ""]
    if gate.get("passed"):
        lines.append("✅ **Passed** — no blocking findings.")
    else:
        lines.append(
            f"🛑 **Blocked** by: {', '.join(gate.get('blocked_by', []))}"
        )
        lines.append("")
        lines += [f"- {reason}" for reason in gate.get("reasons", [])]

    return "\n".join(lines)


def render_svg_badges(risk_score: int, risk_level: str, savings_pct: float | None = None) -> str:
    """
    SVG badges for the PR comment.

    GitHub renders inline SVG in a comment — but only as an `<img>` with
    a data URI, and data URIs are stripped from comments by GitHub's
    sanitiser. So the badges are plain markdown image links to a badge
    service, which GitHub DOES render. That is the honest, working
    choice; a badge that GitHub silently drops is worse than no badge.
    """
    colours = {
        "low": "brightgreen",
        "medium": "yellow",
        "high": "orange",
        "critical": "red",
    }
    colour = colours.get(risk_level, "lightgrey")
    badges = [
        f"![Risk](https://img.shields.io/badge/risk-{risk_score}%2F10-{colour})",
        f"![RepoScope](https://img.shields.io/badge/RepoScope-2.0.0-38bdf8)",
    ]
    if savings_pct is not None:
        badges.append(
            f"![Context](https://img.shields.io/badge/context-{savings_pct:.0f}%25%20saved-brightgreen)"
        )
    return " ".join(badges)
