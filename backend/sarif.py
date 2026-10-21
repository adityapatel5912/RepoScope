"""
sarif.py
SARIF 2.1.0 output.

Milestone 8.2. SARIF is the GitHub code-scanning standard, and emitting
it means RepoScope's findings appear INLINE on the PR diff — where
reviewers already look, instead of in a comment they have to scroll to.

It is the single highest-leverage CI detail, and it was completely
absent.

**The schema matters.** GitHub silently rejects a malformed SARIF file,
so "we emit SARIF" is not the same as "our findings render". The shape
here follows 2.1.0 exactly, and `backend/tests/test_sarif.py` validates
it against the published schema's requirements: the `$schema`, the
`version`, the `runs` array, the tool driver, and every result's
`ruleId`, `level` and `message`.

**Baseline mode.** A gate that flags pre-existing debt gets disabled by
every team within a week. So the findings can be filtered against a
baseline: only NEW issues are reported, and only new ones can block.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemata/sarif-schema-2.1.0.json"
)
TOOL_NAME = "RepoScope"
TOOL_VERSION = "2.0.0"
TOOL_URL = "https://github.com/adityapatel5912/RepoScope"


@dataclass
class Rule:
    """One rule in the tool's catalogue."""

    id: str
    name: str
    short_description: str
    full_description: str = ""
    default_level: str = "warning"   # error | warning | note | none
    help_uri: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "shortDescription": {"text": self.short_description},
            "fullDescription": {"text": self.full_description or self.short_description},
            "defaultConfiguration": {"level": self.default_level},
            "helpUri": self.help_uri or f"{TOOL_URL}/docs/{self.id.replace('/', '-')}",
        }


#: The rule catalogue. Every result's ruleId must appear here — GitHub
#: renders a result whose rule is unknown as an unhelpful generic
#: annotation.
RULES: list[Rule] = [
    Rule(
        id="reposcope/breaking-contract",
        name="BreakingContract",
        short_description="A public contract changed in a way that breaks its consumers.",
        full_description=(
            "An exported function, class or interface changed shape: a parameter "
            "was renamed, a required parameter was added, a return type changed, "
            "or the symbol was removed. Every consumer listed needs updating."
        ),
        default_level="error",
    ),
    Rule(
        id="reposcope/boundary-violation",
        name="BoundaryViolation",
        short_description="An import crosses a declared architectural boundary.",
        full_description=(
            "The import violates a rule declared in the repository's "
            ".reposcope.yml, or RepoScope's built-in layer taxonomy."
        ),
        default_level="error",
    ),
    Rule(
        id="reposcope/new-dependency-cycle",
        name="NewDependencyCycle",
        short_description="The change introduced a dependency cycle.",
        full_description=(
            "A dependency loop that did not exist before the change. A cycle "
            "that crosses architectural layers is a violation; a cycle inside "
            "one layer is a code smell."
        ),
        default_level="warning",
    ),
    Rule(
        id="reposcope/high-blast-radius",
        name="HighBlastRadius",
        short_description="The change affects a large part of the dependency graph.",
        full_description=(
            "The changed file is depended upon by many other files, so the "
            "change has a wide blast radius."
        ),
        default_level="warning",
    ),
    Rule(
        id="reposcope/missing-test",
        name="MissingTest",
        short_description="A high-risk changed module has no test file.",
        full_description=(
            "The module is in the blast radius and no test file covers it, so "
            "a regression would not be caught."
        ),
        default_level="note",
    ),
]

_RULES_BY_ID = {rule.id: rule for rule in RULES}


@dataclass
class SarifResult:
    """One finding, ready for SARIF."""

    rule_id: str
    message: str
    file: str
    line: int = 0
    level: str = ""
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        rule = _RULES_BY_ID.get(self.rule_id)
        level = self.level or (rule.default_level if rule else "warning")
        result: dict = {
            "ruleId": self.rule_id,
            "level": level,
            "message": {"text": self.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": self.file.replace("\\", "/")},
                        **({"region": {"startLine": max(1, self.line)}} if self.line else {}),
                    }
                }
            ],
        }
        if self.properties:
            result["properties"] = self.properties
        return result


def to_sarif(results: Iterable[SarifResult], baseline: Iterable[str] = ()) -> dict:
    """
    Build a SARIF 2.1.0 document.

    `baseline` is the set of finding keys that already existed. A
    baseline finding is dropped — a gate that reports pre-existing debt
    is a gate that gets turned off.
    """
    known = set(baseline)
    kept: list[dict] = []
    for result in results:
        key = f"{result.rule_id}:{result.file}:{result.line}:{result.message}"
        if key in known:
            continue
        kept.append(result.to_dict())

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                        "informationUri": TOOL_URL,
                        "rules": [rule.to_dict() for rule in RULES],
                    }
                },
                "results": kept,
            }
        ],
    }


def to_sarif_json(results: Iterable[SarifResult], baseline: Iterable[str] = ()) -> str:
    """The SARIF document as JSON — what GitHub wants."""
    return json.dumps(to_sarif(results, baseline), indent=2)


def finding_key(rule_id: str, file: str, line: int, message: str) -> str:
    """The stable identity of a finding, for the baseline."""
    return f"{rule_id}:{file}:{line}:{message}"
