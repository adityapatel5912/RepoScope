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
    Rule(
        id="reposcope/cross-file-taint",
        name="CrossFileTaintFlow",
        short_description="Untrusted user input propagates across files to a critical execution sink.",
        full_description=(
            "Taint flows from an API route or external input through intermediate function calls "
            "and variable assignments across file boundaries into a dangerous sink (CWE-20)."
        ),
        default_level="error",
    ),
    Rule(
        id="reposcope/hardcoded-secret",
        name="HardcodedSecret",
        short_description="Hardcoded credential, token, or high-entropy secret detected.",
        full_description=(
            "Hardcoded API keys, private keys, or high-entropy tokens found in code. "
            "Rotate immediately and move credentials to a secure vault or environment variables (CWE-798)."
        ),
        default_level="error",
    ),
    Rule(
        id="reposcope/vulnerable-dependency",
        name="VulnerableDependency",
        short_description="Manifest pins a dependency version with known critical or high CVE advisories.",
        full_description=(
            "Package manifest pins a version below the security advisory threshold (CWE-1395)."
        ),
        default_level="warning",
    ),
    Rule(
        id="reposcope/injection-sink",
        name="InjectionSink",
        short_description="Unsanitized dynamic parameter in SQL, command execution, or code eval sink.",
        full_description=(
            "Code uses dynamic string concatenation or interpolation in SQL queries, shell commands, "
            "or eval() without proper parameterization or sanitization (CWE-89, CWE-78, CWE-95)."
        ),
        default_level="error",
    ),
    Rule(
        id="reposcope/insecure-configuration",
        name="InsecureConfiguration",
        short_description="Permissive CORS wildcard, disabled TLS verification, or debug mode in production.",
        full_description=(
            "Insecure framework configuration enables credential theft, MITM attacks, or info disclosure (CWE-942, CWE-295)."
        ),
        default_level="warning",
    ),
    Rule(
        id="reposcope/missing-auth-guard",
        name="MissingAuthGuard",
        short_description="State-mutating HTTP endpoint lacks authentication or authorization guards.",
        full_description=(
            "A POST, PUT, DELETE, or PATCH endpoint is exposed without authentication dependencies or guards (CWE-306, CWE-862)."
        ),
        default_level="warning",
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


def flags_to_sarif(flags: Iterable[dict], baseline: Iterable[str] = ()) -> dict:
    """Map security scanner finding dictionaries across all 6 engines into SARIF 2.1.0."""
    rule_map = {
        "cross_file_taint": "reposcope/cross-file-taint",
        "TAINT": "reposcope/cross-file-taint",
        "secrets_entropy": "reposcope/hardcoded-secret",
        "SECRET": "reposcope/hardcoded-secret",
        "dependency_cve": "reposcope/vulnerable-dependency",
        "CVE": "reposcope/vulnerable-dependency",
        "injection_sinks": "reposcope/injection-sink",
        "INJECTION": "reposcope/injection-sink",
        "insecure_config": "reposcope/insecure-configuration",
        "CONFIG": "reposcope/insecure-configuration",
        "auth_bypass": "reposcope/missing-auth-guard",
        "AUTH_BYPASS": "reposcope/missing-auth-guard",
        "BREAKING": "reposcope/breaking-contract",
        "breaking": "reposcope/breaking-contract",
    }
    sev_map = {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
    }
    results: list[SarifResult] = []
    for f in flags:
        engine = f.get("engine") or f.get("type", "")
        rule_id = rule_map.get(engine) or rule_map.get(f.get("type", ""), "reposcope/breaking-contract")
        level = sev_map.get(f.get("severity", "medium"), "warning")
        msg = f.get("detail") or "Security vulnerability detected."
        file_path = f.get("file") or "unknown"
        line = int(f.get("line") or 1)
        props: dict = {}
        if f.get("cwe"):
            props["cwe"] = f["cwe"]
        if f.get("suggestion"):
            props["suggestion"] = f["suggestion"]
        if f.get("trace"):
            props["trace"] = f["trace"]
        results.append(SarifResult(rule_id=rule_id, message=msg, file=file_path, line=line, level=level, properties=props))

    return to_sarif(results, baseline)


def flags_to_sarif_json(flags: Iterable[dict], baseline: Iterable[str] = ()) -> str:
    """Format finding dictionaries as compliant SARIF JSON string."""
    return json.dumps(flags_to_sarif(flags, baseline), indent=2)
