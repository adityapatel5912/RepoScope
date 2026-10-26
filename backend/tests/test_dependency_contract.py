"""
test_dependency_contract.py
The deployment install and the package metadata must agree.

CI installs `backend/requirements.txt`; Render does the same. If a runtime
import is declared only in `pyproject.toml`, CI can pass while production
fails — which is exactly how the missing `mcp`, `typer`, and `watchdog`
dependencies survived until the Phase 0 audit.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Packages the application imports at runtime, not just in tests.
RUNTIME_PACKAGES = {
    "fastapi",
    "uvicorn",
    "sse-starlette",
    "openai",
    "python-dotenv",
    "httpx",
    "pydantic",
    "gitpython",
    "psutil",
    "networkx",
    "numpy",
    "scipy",
    "pyyaml",
    "tree-sitter",
    "tree-sitter-python",
    "tree-sitter-javascript",
    "tree-sitter-typescript",
    "tree-sitter-go",
    "tree-sitter-rust",
    "typer",
    "watchdog",
    "mcp",
}


def _requirement_name(line: str) -> str:
    """The distribution name from a PEP 508 requirement line."""
    stripped = line.split("#", 1)[0].strip()
    if not stripped:
        return ""
    # A name ends at an extras marker, a version operator, a marker, or
    # whitespace. `uvicorn[standard]>=0.32` -> `uvicorn`.
    match = re.match(r"^([A-Za-z0-9_.-]+)", stripped)
    return match.group(1).lower() if match else ""


def _requirement_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _requirements() -> dict[str, str]:
    return {
        _requirement_name(line): line
        for line in _requirement_lines(ROOT / "backend" / "requirements.txt")
        if _requirement_name(line)
    }


def _pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _pyproject_dependencies() -> dict[str, str]:
    raw = _pyproject()["project"]["dependencies"]
    return {
        _requirement_name(item): item
        for item in raw
        if _requirement_name(item)
    }


def test_requirements_declare_every_runtime_package():
    declared = set(_requirements())
    missing = sorted(RUNTIME_PACKAGES - declared)
    assert not missing, f"backend/requirements.txt is missing: {missing}"


def test_pyproject_declares_every_runtime_package():
    declared = set(_pyproject_dependencies())
    missing = sorted(RUNTIME_PACKAGES - declared)
    assert not missing, f"pyproject.toml is missing: {missing}"


def test_the_two_runtime_dependency_sets_agree():
    requirements = set(_requirements())
    pyproject = set(_pyproject_dependencies())
    # `pytest` is a dev extra in pyproject but stays in requirements for the
    # CI install; it is the only intentional difference.
    assert requirements - pyproject == {"pytest"}
    assert pyproject - requirements == set()


def test_mcp_is_pinned_below_two_in_both_files():
    """MCP 2.x removed `mcp.server.fastmcp.FastMCP`; the server needs 1.x."""
    for label, line in (
        ("requirements", _requirements()["mcp"]),
        ("pyproject", _pyproject_dependencies()["mcp"]),
    ):
        assert "<2" in line, f"{label} must cap mcp below 2.x: {line!r}"
        assert ">=1.29" in line, f"{label} must require mcp 1.29+: {line!r}"


def test_numerical_stack_is_declared_for_pagerank():
    """PageRank needs numpy/scipy. The CI baseline failed without them."""
    declared = set(_requirements())
    assert {"numpy", "scipy"} <= declared


def test_installed_mcp_still_exposes_the_fastmcp_import():
    """The decorator surface the server imports must exist in the env."""
    from importlib.metadata import version

    from mcp.server.fastmcp import FastMCP  # noqa: F401

    major = int(version("mcp").split(".", 1)[0])
    assert major < 2, f"installed mcp is {version('mcp')}; the server needs 1.x"
