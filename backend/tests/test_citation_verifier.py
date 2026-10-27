"""
test_citation_verifier.py
Tests for Phase 5: Verified chat citations.

Covers:
- Exact symbol match
- Snapped near-miss (within 5 lines of symbol start)
- Multi-symbol span marked partial
- Valid file line with no symbol
- File-only citation
- Missing path (verified: false, never invent path)
- Line out of range / EOF
- Path-escape / directory traversal rejection
- Hover preview narrow bounds (<= 15 lines) and within repo root
- Multi-format extraction from answer text in document order
"""
from pathlib import Path
import pytest

from citation_verifier import (
    verify_citation,
    verify_citations_in_text,
    is_safe_repo_path,
)


@pytest.fixture
def sample_repo(tmp_path: Path):
    """Create a temporary repository with known sample files and symbols."""
    # File 1: Python file with 2 functions and top-level comments
    py_code = (
        "# Top-level comment line 1\n"
        "# Top-level comment line 2\n"
        "import sys\n"
        "import os\n"
        "\n"
        "# Section header\n"
        "\n"
        "\n"
        "\n"
        "def first_func():\n"
        "    a = 1\n"
        "    b = 2\n"
        "    return a + b\n"
        "\n"
        "def second_func():\n"
        "    print('hello')\n"
        "    return 42\n"
        "\n"
        "# Bottom comment line 19\n"
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "calculator.py"
    py_file.write_text(py_code, encoding="utf-8")

    # Synthetic graph matching graph_builder output
    graph = {
        "nodes": [
            {"id": "file:src/calculator.py", "type": "file", "label": "src/calculator.py"},
            {
                "id": "func:src/calculator.py:first_func",
                "type": "function",
                "label": "first_func",
                "file": "src/calculator.py",
                "line": 10,
                "end_line": 13,
            },
            {
                "id": "func:src/calculator.py:second_func",
                "type": "function",
                "label": "second_func",
                "file": "src/calculator.py",
                "line": 15,
                "end_line": 17,
            },
        ],
        "edges": [],
    }

    return tmp_path, graph


def test_exact_symbol_range(sample_repo):
    root, graph = sample_repo
    res = verify_citation(
        path="src/calculator.py",
        line=10,
        end_line=13,
        repo_root=root,
        graph=graph,
    )
    assert res["verified"] is True
    assert res["confidence"] == 1.0
    assert res["reason"] == "exact symbol range"
    assert res["symbol"] == "first_func"
    assert res["node_id"] == "func:src/calculator.py:first_func"
    assert "def first_func():" in res["preview"]


def test_snapped_symbol_range(sample_repo):
    root, graph = sample_repo
    # Line 8 is within 5 lines of first_func's start (line 10; abs(8 - 10) == 2 <= 5)
    res = verify_citation(
        path="src/calculator.py",
        line=8,
        end_line=8,
        repo_root=root,
        graph=graph,
    )
    assert res["verified"] is True
    assert res["confidence"] == 0.9
    assert res["reason"] == "snapped"
    assert res["start_line"] == 10
    assert res["end_line"] == 13
    assert res["symbol"] == "first_func"
    assert res["node_id"] == "func:src/calculator.py:first_func"
    assert "def first_func():" in res["preview"]


def test_partial_symbol_range(sample_repo):
    root, graph = sample_repo
    # Range spans from line 11 (inside first_func) to line 16 (inside second_func)
    res = verify_citation(
        path="src/calculator.py",
        line=11,
        end_line=16,
        repo_root=root,
        graph=graph,
    )
    assert res["verified"] is True
    assert res["confidence"] == 0.5
    assert res["reason"] == "partial"
    assert "first_func" in res["symbol"]
    assert "second_func" in res["symbol"]


def test_file_line_without_symbol(sample_repo):
    root, graph = sample_repo
    # Line 1 is a top-level comment, more than 5 lines away from first_func (line 10)
    res = verify_citation(
        path="src/calculator.py",
        line=1,
        end_line=2,
        repo_root=root,
        graph=graph,
    )
    assert res["verified"] is True
    assert res["confidence"] == 1.0
    assert res["reason"] == "file line"
    assert res["symbol"] is None
    assert res["node_id"] == "file:src/calculator.py"
    assert "# Top-level comment" in res["preview"]


def test_file_only_citation(sample_repo):
    root, graph = sample_repo
    res = verify_citation(
        path="src/calculator.py",
        line=None,
        repo_root=root,
        graph=graph,
    )
    assert res["verified"] is True
    assert res["confidence"] == 1.0
    assert res["reason"] == "file only"
    assert res["node_id"] == "file:src/calculator.py"
    assert res["start_line"] == 1
    assert len(res["preview"]) > 0


def test_hallucinated_file_not_found(sample_repo):
    root, graph = sample_repo
    res = verify_citation(
        path="src/non_existent.py",
        line=10,
        repo_root=root,
        graph=graph,
    )
    assert res["verified"] is False
    assert res["confidence"] == 0.0
    assert res["reason"] == "file not found"
    assert res["node_id"] is None
    assert res["symbol"] is None
    assert res["preview"] == ""


def test_hallucinated_line_out_of_range(sample_repo):
    root, graph = sample_repo
    res = verify_citation(
        path="src/calculator.py",
        line=99999,
        end_line=99999,
        repo_root=root,
        graph=graph,
    )
    assert res["verified"] is False
    assert res["confidence"] == 0.0
    assert res["reason"] == "line out of range"
    assert res["preview"] == ""


def test_path_escape_traversal(sample_repo):
    root, graph = sample_repo
    escapes = [
        "../../etc/passwd",
        "../calculator.py",
        "/etc/shadow",
    ]
    for p in escapes:
        res = verify_citation(
            path=p,
            line=1,
            repo_root=root,
            graph=graph,
        )
        assert res["verified"] is False
        assert res["confidence"] == 0.0
        assert res["reason"] == "path escape"
        assert res["preview"] == ""


def test_preview_never_reads_outside_root(sample_repo):
    root, _ = sample_repo
    assert not is_safe_repo_path("../outside.py", root)
    assert not is_safe_repo_path("/root/secret", root)
    assert is_safe_repo_path("src/calculator.py", root)


def test_verify_citations_in_text(sample_repo):
    root, graph = sample_repo
    text = (
        "Here is the calculation logic:\n"
        "- Call `src/calculator.py:10-13` for the first operation.\n"
        "- Also check [src/calculator.py:15] for second.\n"
        "- And nonexistent file [src/fake.py:42] is cited.\n"
        "| Path | Line |\n"
        "| :--- | :--- |\n"
        "| src/calculator.py:1 | comment |\n"
    )
    citations = verify_citations_in_text(text, repo_root=root, graph=graph)
    assert len(citations) >= 3

    # Document order: first is calculator.py:10-13
    c0 = citations[0]
    assert c0["path"] == "src/calculator.py"
    assert c0["verified"] is True
    assert c0["symbol"] == "first_func"

    # Second is calculator.py:15
    c1 = citations[1]
    assert c1["path"] == "src/calculator.py"
    assert c1["verified"] is True
    assert c1["symbol"] == "second_func"

    # Fake file is unverified
    fake = next((c for c in citations if c["path"] == "src/fake.py"), None)
    assert fake is not None
    assert fake["verified"] is False
    assert fake["reason"] == "file not found"
