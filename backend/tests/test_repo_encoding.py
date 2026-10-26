"""
test_repo_encoding.py
Guards the repository against encoding corruption.

This test exists because of a real regression: a PowerShell
`Get-Content -Raw` / `Set-Content -Encoding utf8` round-trip reads a file
as Windows-1252 and writes it back as UTF-8, which double-encodes every
non-ASCII character. The UI showed "multilang <mojibake> Architecture"
instead of "multilang - Architecture", and the console gate did not catch
it - only a human reading the screenshot did.

Mojibake is invisible to unit tests, invisible to the console-error gate,
and obvious in a screenshot. This test closes the first gap, and journey
screenshots close the second.

The check is deliberately narrow: it looks for the signature byte
sequences of a double-encoded UTF-8 string, not for "non-ASCII", because
this repository legitimately uses box-drawing characters and em-dashes.

The patterns are written with \\u escapes so that this file does not
contain the sequences it is looking for.
"""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Directories that must never be scanned (generated, vendored, or huge).
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", "dist", "build",
    ".venv", "venv", "qa-report", "test-results", "playwright-report",
    ".playwright-mcp", "apps",
}

#: File types worth checking.
SCAN_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".json",
                 ".md", ".css", ".html", ".yml", ".yaml"}

#: The signature of a double-encoded (mojibake) UTF-8 string.
#:
#:   U+00B7 in UTF-8 is C2 B7, decoded as cp1252 it becomes two characters
#:   U+2014 in UTF-8 is E2 80 94, decoded as cp1252 it becomes three
#:   U+FFFD in UTF-8 is EF BF BD, decoded as cp1252 it becomes three
#:
#: Each pattern is the leading character(s) of that mis-decode. They are
#: built from integer code points so that this file contains no literal
#: instance of what it is looking for.
MOJIBAKE_PATTERNS = (
    re.compile(chr(0x00C2)),                      # lead byte 0xC2
    re.compile(chr(0x00E2) + chr(0x20AC)),        # lead bytes 0xE2 0x80
    re.compile(chr(0x00EF) + chr(0x00BF) + chr(0x00BD)),  # replacement char
)


def _scannable_files():
    """
    Yield every file worth checking.

    Uses os.walk with in-place directory pruning. Path.rglob would still
    walk node_modules and .git even though their contents are skipped -
    that made this test take 44 seconds instead of well under one.
    """
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and d != "real_small"
        ]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            yield path


def test_repo_has_no_mojibake():
    """No source file may contain double-encoded UTF-8."""
    offenders = []
    for path in _scannable_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            # A file that is not valid UTF-8 at all is also a problem, but
            # it is reported separately so the message stays actionable.
            offenders.append(f"{path.relative_to(REPO_ROOT)}: not valid UTF-8")
            continue
        for pattern in MOJIBAKE_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: mojibake")
                break

    assert not offenders, (
        "mojibake found - a file was likely re-encoded through Windows-1252. "
        "Restore it with `git checkout -- <file>` and re-apply the edit with a "
        "UTF-8-safe editor:\n  " + "\n  ".join(offenders)
    )


def test_the_scan_actually_covers_source_files():
    """Guard against the scanner silently scanning nothing."""
    scanned = list(_scannable_files())
    assert len(scanned) > 20, f"the scanner only found {len(scanned)} files"

    names = {p.name for p in scanned}
    assert "App.tsx" in names, "the frontend entry point was not scanned"
    assert "main.py" in names, "the backend entry point was not scanned"


def test_every_python_file_is_valid_utf8():
    """Python source must decode as UTF-8 - it is the repo's source of truth."""
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and d != "real_small"
        ]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            (Path(dirpath) / filename).read_text(encoding="utf-8")  # raises on invalid UTF-8
