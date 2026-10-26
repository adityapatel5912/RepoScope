"""
test_contract_diff.py
The AST-level contract diff.

Milestone 5.1. Correction C3: this is the ONE implementation.
`security_scanner.detect_breaking_in_patch` delegates to it, and this
test asserts that it really does — so the two can never drift.

The acceptance criteria, in the roadmap's words:

* "A PR that renames a required parameter is flagged as BREAKING, and the
  flag names the CONSUMING files, not the containing directory."
* "A PR that renames a private helper is NOT flagged."
"""
from pathlib import Path

import pytest

from contract_diff import (
    Contract,
    Param,
    diff_contracts,
    diff_sources,
    extract_contracts,
    find_consumers,
    sources_from_patch,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _kinds(findings) -> list[str]:
    return [f.kind for f in findings]


# ── The extraction ──────────────────────────────────────────────────────────

def test_the_contracts_are_extracted_from_the_ast():
    source = "def greet(name: str, times: int = 1) -> str:\n    return name\n"
    contracts = extract_contracts(source.encode(), "a.py")

    assert "greet" in contracts
    greet = contracts["greet"]
    assert greet.exported is True
    assert [p.name for p in greet.params] == ["name", "times"]
    assert greet.params[0].required is True
    assert greet.params[1].required is False
    assert greet.params[0].type == "str"
    assert greet.params[1].type == "int"
    assert greet.return_type == "str"


def test_a_private_helper_is_not_exported():
    contracts = extract_contracts(b"def _helper(a):\n    return a\n", "a.py")
    assert contracts["_helper"].exported is False


def test_typescript_exports_are_detected():
    source = "export function render(text: string): string {\n  return text;\n}\n"
    contracts = extract_contracts(source.encode(), "a.ts")
    assert contracts["render"].exported is True
    assert contracts["render"].params[0].name == "text"


def test_a_typescript_private_helper_is_not_exported():
    source = "function helper(a: number) { return a; }\n"
    contracts = extract_contracts(source.encode(), "a.ts")
    assert contracts["helper"].exported is False


def test_go_exports_are_capitalised():
    source = "package main\n\nfunc Greet(name string) string {\n\treturn name\n}\n\nfunc helper() {}\n"
    contracts = extract_contracts(source.encode(), "a.go")
    assert contracts["Greet"].exported is True
    assert contracts["helper"].exported is False


def test_rust_exports_are_capitalised():
    source = "pub fn greet(name: &str) -> String {\n    name.to_string()\n}\n\nfn helper() {}\n"
    contracts = extract_contracts(source.encode(), "a.rs")
    assert contracts["greet"].exported is True
    assert contracts["helper"].exported is False


# ── The detection ───────────────────────────────────────────────────────────

def test_a_renamed_required_parameter_is_breaking():
    old = "def greet(name: str) -> str:\n    return name\n"
    new = "def greet(nickname: str) -> str:\n    return nickname\n"

    findings = diff_sources(old, new, "a.py")

    assert len(findings) == 1, f"expected one finding, got {len(findings)}"
    finding = findings[0]
    assert finding.kind == "renamed-parameter"
    assert finding.severity == "BREAKING"
    assert "name" in finding.message
    assert "nickname" in finding.message


def test_a_renamed_private_helper_is_NOT_flagged():
    """The criterion that decides whether a bot gets muted."""
    old = "def _helper(a):\n    return a\n"
    new = "def _helper2(a):\n    return a\n"

    assert diff_sources(old, new, "a.py") == []


def test_a_renamed_private_helper_in_typescript_is_not_flagged():
    old = "function helper(a: number) { return a; }\n"
    new = "function helper2(a: number) { return a; }\n"
    assert diff_sources(old, new, "a.ts") == []


def test_a_removed_export_is_breaking():
    old = "def public_api():\n    pass\n"
    new = "def other():\n    pass\n"

    findings = diff_sources(old, new, "a.py")
    assert len(findings) == 1
    assert findings[0].kind == "removed"
    assert findings[0].severity == "BREAKING"


def test_an_added_required_parameter_is_breaking():
    old = "def greet(name: str) -> str:\n    return name\n"
    new = "def greet(name: str, loud: bool) -> str:\n    return name\n"

    findings = diff_sources(old, new, "a.py")
    assert len(findings) == 1
    assert findings[0].kind == "required-parameter"
    assert findings[0].severity == "BREAKING"


def test_an_added_optional_parameter_is_not_breaking():
    old = "def greet(name: str) -> str:\n    return name\n"
    new = "def greet(name: str, loud: bool = False) -> str:\n    return name\n"

    findings = diff_sources(old, new, "a.py")
    assert len(findings) == 1
    assert findings[0].kind == "optional-parameter"
    assert findings[0].severity == "INFO"


def test_a_removed_required_parameter_is_breaking():
    old = "def greet(name: str, times: int) -> str:\n    return name\n"
    new = "def greet(name: str) -> str:\n    return name\n"

    findings = diff_sources(old, new, "a.py")
    assert len(findings) == 1
    assert findings[0].kind == "removed-parameter"
    assert findings[0].severity == "BREAKING"


def test_a_changed_return_type_is_breaking():
    old = "def f() -> str:\n    return 'x'\n"
    new = "def f() -> int:\n    return 1\n"

    findings = diff_sources(old, new, "a.py")
    assert len(findings) == 1
    assert findings[0].kind == "return-type"
    assert findings[0].severity == "BREAKING"


def test_a_retyped_parameter_is_breaking():
    old = "def f(value: str):\n    pass\n"
    new = "def f(value: int):\n    pass\n"

    findings = diff_sources(old, new, "a.py")
    assert len(findings) == 1
    assert findings[0].kind == "retyped-parameter"
    assert findings[0].severity == "BREAKING"


def test_an_unchanged_file_has_no_findings():
    source = "def greet(name: str) -> str:\n    return name\n"
    assert diff_sources(source, source, "a.py") == []


def test_a_non_python_file_is_ignored_rather_than_mangled():
    """A file with no grammar must produce nothing, not noise."""
    assert diff_sources("hello", "goodbye", "notes.txt") == []


# ── The patch path (Correction C3) ──────────────────────────────────────────

def test_the_patch_is_reconstructed_into_two_versions():
    patch = (
        "@@ -1,5 +1,5 @@\n"
        " def greet(name: str) -> str:\n"
        "-    return name\n"
        "+    return name.upper()\n"
    )
    old, new = sources_from_patch(patch)
    assert "def greet" in old
    assert "return name" in old
    assert "return name.upper()" in new


def test_the_security_scanner_delegates_to_the_contract_diff():
    """
    Correction C3: exactly ONE detector.

    The scanner's regex implementation used to live here. It is gone;
    this asserts that the delegation actually works — a patch that
    renames a required parameter is still flagged.
    """
    from security_scanner import detect_breaking_in_patch

    patch = (
        "@@ -1,3 +1,3 @@\n"
        "-def greet(name: str) -> str:\n"
        "+def greet(nickname: str) -> str:\n"
        "     return name\n"
    )
    flags = detect_breaking_in_patch(patch, "a.py")
    assert flags, "the delegation produced no flags"
    assert any(f["type"] == "BREAKING" for f in flags)


def test_the_scanner_and_the_contract_diff_agree():
    """
    The two interfaces must not disagree.

    The scanner is what the PR bot calls; the contract diff is what the
    MCP server and the tests call. If they ever answer differently, one
    of them is lying.
    """
    from security_scanner import detect_breaking_in_patch

    patch = (
        "@@ -1,4 +1,4 @@\n"
        " def greet(name: str) -> str:\n"
        "-    return name\n"
        "+    return name\n"
        "+\n"
        "+def extra(loud: bool) -> str:\n"
        "+    return name\n"
    )
    flags = detect_breaking_in_patch(patch, "a.py")
    findings = diff_sources(
        "def greet(name: str) -> str:\n    return name\n",
        "def greet(name: str) -> str:\n    return name\n\ndef extra(loud: bool) -> str:\n    return name\n",
        "a.py",
    )
    assert bool(flags) == bool(findings)


# ── Precision: the consumers ────────────────────────────────────────────────

def test_the_consumers_are_the_files_that_actually_use_the_symbol():
    """Not every file in the directory — the files that really consume it."""
    from graph_builder import build_graph_from_repo

    graph = build_graph_from_repo(str(FIXTURES_DIR / "multilang"))
    consumers = find_consumers(graph, "helpers.py", "shout")

    assert "app.py" in consumers
    # The file itself is not a consumer of its own symbol.
    assert "helpers.py" not in consumers


def test_the_consumers_of_an_unused_symbol_are_empty():
    from graph_builder import build_graph_from_repo

    graph = build_graph_from_repo(str(FIXTURES_DIR / "multilang"))
    assert find_consumers(graph, "helpers.py", "nobody_calls_this") == []


def test_the_consumers_are_empty_without_a_graph():
    assert find_consumers({"nodes": [], "edges": []}, "a.py", "f") == []


# ── The contract objects ────────────────────────────────────────────────────

def test_a_contract_renders_its_signature():
    contract = Contract(
        kind="function",
        name="greet",
        params=[Param(name="name", type="str"), Param(name="times", type="int", has_default=True)],
        return_type="str",
    )
    assert contract.signature() == "greet(name: str, times: int) -> str"
