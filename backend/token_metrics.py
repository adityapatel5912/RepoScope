"""
token_metrics.py
Measuring how many tokens a codebase costs an agent.

Milestone 8.1 — "Context savings" is the 2026 buying trigger. Every
competitor publishes a number: `codegraph` claims 62% fewer tokens,
Repomix ~70%, GitNexus 88% fewer tool calls. RepoScope published none,
which means a reviewer had no reason to believe RepoScope.

Two numbers matter:

    full_context_tokens   what an agent pays to read the whole repository
    repo_map_tokens       what an agent pays to read RepoScope's map

and the reduction between them.

**The tokenizer is an estimate, and it is labelled as one.** A real BPE
tokenizer would need the model's vocabulary — and the answer changes with
the model. This estimator is model-independent and deterministic, so the
number is reproducible: the same repository always produces the same
figure. It is also pluggable, so a real tokenizer can be dropped in
without touching anything else.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable

#: A token is roughly four characters of English prose or code. The
#: estimator below is finer than a flat divide-by-four: it charges long
#: identifiers more (they really do split into several sub-word tokens)
#: and charges punctuation one token each.
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\sA-Za-z0-9_]")

#: Files that are never worth putting in an agent's context.
BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff",
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".flac", ".ogg", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".so", ".dll", ".dylib", ".exe", ".bin", ".dat", ".db", ".sqlite",
    ".pyc", ".pyo", ".class", ".o", ".a", ".obj",
})

#: How many bytes of repository content the baseline measurement reads.
#: Beyond this the number would take longer to compute than it is worth,
#: and the response says so rather than quietly extrapolating.
MAX_MEASURE_BYTES = 120 * 1024 * 1024

#: How many files the baseline measurement reads.
MAX_MEASURE_FILES = 20_000


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a piece of text.

    Words and identifiers cost roughly one token per four characters (with
    a floor of one); punctuation and symbols cost one each. This is an
    approximation of a BPE tokenizer, not one — see the module docstring.
    """
    if not text:
        return 0
    total = 0
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if token[0].isdigit():
            # Numbers split on digit boundaries; a long literal is
            # several tokens.
            total += max(1, (len(token) + 2) // 3)
        else:
            total += max(1, (len(token) + 3) // 4)
    return total


#: The default tokenizer. Pluggable: pass any `str -> int` callable.
Tokenizer = Callable[[str], int]


def get_tokenizer(name: str | None = None) -> Tokenizer:
    """
    Return a tokenizer by name.

    Only the built-in estimator ships today. The indirection exists so a
    real model tokenizer can be added without changing every caller — and
    so the choice is visible in the API rather than hidden.
    """
    if name in (None, "estimate", "builtin"):
        return estimate_tokens
    raise ValueError(f"Unknown tokenizer: {name!r}")


def _iter_source_files(root: Path):
    """Yield the text files under a repository root.

    The skip list is applied to DIRECTORIES during the walk. Filtering
    only the yielded paths meant every measurement descended into .git
    and node_modules first; on a normal checkout that is tens of
    thousands of files and several seconds of wasted I/O.
    """
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".reposcope",
        "dist", "build", ".venv", "venv", ".mypy_cache",
        ".pytest_cache", ".playwright-mcp", ".turbo", "out", "logs",
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() in BINARY_SUFFIXES:
                continue
            try:
                rel = str(path.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            if any(part in skip_dirs for part in rel.split("/")):
                continue
            yield path, rel


def full_context_tokens(root: str | Path, tokenizer: Tokenizer | None = None) -> dict:
    """
    Measure what it costs an agent to read the whole repository.

    Returns the token count, how many files were measured, and whether the
    measurement hit its ceiling. The ceiling is reported rather than
    hidden: a truncated baseline that looks complete is a lie about a
    number the whole product is built around.
    """
    tokenizer = tokenizer or estimate_tokens
    root_path = Path(root)
    if not root_path.is_dir():
        return {
            "tokens": 0,
            "files_measured": 0,
            "files_total": 0,
            "truncated": False,
            "bytes_measured": 0,
        }

    total = 0
    measured = 0
    bytes_measured = 0
    truncated = False
    file_total = 0

    for path, _rel in _iter_source_files(root_path):
        file_total += 1
        if measured >= MAX_MEASURE_FILES or bytes_measured >= MAX_MEASURE_BYTES:
            truncated = True
            break
        try:
            size = path.stat().st_size
            if size > 4 * 1024 * 1024:
                # A single enormous file would dominate the baseline and
                # is not something an agent reads anyway.
                truncated = True
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += tokenizer(text)
        measured += 1
        bytes_measured += size

    return {
        "tokens": total,
        "files_measured": measured,
        "files_total": file_total,
        "truncated": truncated,
        "bytes_measured": bytes_measured,
    }


def reduction_pct(repo_map_tokens: int, full_tokens: int) -> float:
    """
    The percentage of context saved by using the map instead of the code.

    Returns 0.0 when there is nothing to compare against — a 100%
    reduction would be a lie.
    """
    if full_tokens <= 0:
        return 0.0
    saved = full_tokens - repo_map_tokens
    if saved <= 0:
        return 0.0
    return round(saved * 100.0 / full_tokens, 2)
