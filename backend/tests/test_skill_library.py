"""
backend/tests/test_skill_library.py
Tests for skill_library module and checked-in skill copies.
"""

from pathlib import Path
import pytest

from skill_library import (
    ALLOWED_RESOURCES,
    ALLOWED_TOOLS,
    FIRST_TOOL_CALL,
    FORBIDDEN_TOOLS,
    REQUIRED_SECTIONS,
    SKILL_BODIES,
    SKILL_IDS,
    skill_body,
    validate_skill_bodies,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_validate_skill_bodies_passes():
    problems = validate_skill_bodies()
    assert problems == [], f"Validation failed with problems: {problems}"


def test_five_skill_ids_and_order():
    expected = (
        "blast-radius-guard",
        "zero-grep-architect",
        "pr-contract-shield",
        "onboarding-navigator",
        "dead-code-surgeon",
    )
    assert SKILL_IDS == expected
    assert set(SKILL_BODIES.keys()) == set(expected)


def test_first_tool_calls_frozen():
    assert FIRST_TOOL_CALL["blast-radius-guard"] == "get_ast_skeleton"
    assert FIRST_TOOL_CALL["zero-grep-architect"] == "get_architecture_overview"
    assert FIRST_TOOL_CALL["pr-contract-shield"] == "diff_interface_contracts"
    assert FIRST_TOOL_CALL["onboarding-navigator"] == "get_ranked_reading_path"
    assert FIRST_TOOL_CALL["dead-code-surgeon"] == "find_unreachable_symbols"


def test_dead_code_surgeon_caveat():
    body = skill_body("dead-code-surgeon")
    assert "Static reachability is an estimate, not proof of dead code." in body
    assert "dynamic dispatch" in body
    assert "reflection" in body
    assert "plugin registration" in body
    assert "external consumers" in body


def test_no_forbidden_stale_names_in_bodies():
    for skill_id in SKILL_IDS:
        body = skill_body(skill_id)
        for fb in FORBIDDEN_TOOLS:
            assert fb not in body, f"{skill_id} contains forbidden tool {fb}"


def test_checked_in_copies_match_canonical():
    for skill_id in SKILL_IDS:
        canonical = skill_body(skill_id).replace("\r\n", "\n").rstrip("\n") + "\n"

        claude_file = REPO_ROOT / ".claude" / "skills" / skill_id / "SKILL.md"
        assert claude_file.is_file(), f"Missing {claude_file}"
        claude_content = claude_file.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n") + "\n"
        assert claude_content == canonical, f"Drift in {claude_file}"

        agents_file = REPO_ROOT / ".agents" / "skills" / skill_id / "SKILL.md"
        assert agents_file.is_file(), f"Missing {agents_file}"
        agents_content = agents_file.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n") + "\n"
        assert agents_content == canonical, f"Drift in {agents_file}"


def test_unknown_skill_body_raises():
    with pytest.raises(KeyError):
        skill_body("nonexistent-skill")
