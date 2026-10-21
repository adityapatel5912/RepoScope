"""
Repair double-encoded (mojibake) UTF-8 in a file.

A PowerShell `Get-Content -Raw` / `Set-Content -Encoding utf8` round-trip
reads a file as Windows-1252 and writes it back as UTF-8, which
double-encodes every non-ASCII character. This reverses that mis-decode.

    python scripts/repair_mojibake.py <file> [--dry-run]

Only the characters that were mis-decoded are touched; ordinary UTF-8 is
left alone. Run with --dry-run first to see what would change.
"""
import sys
from pathlib import Path


def repair(text: str) -> tuple[str, int]:
    """Undo the Windows-1252 mis-decode. Returns (text, lines_changed)."""
    lines = text.split("\n")
    changed = 0
    out = []
    for line in lines:
        try:
            candidate = line.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Not a mis-decode — leave the line exactly as it is.
            out.append(line)
            continue
        if candidate != line:
            changed += 1
            out.append(candidate)
        else:
            out.append(line)
    return "\n".join(out), changed


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    if not args:
        print("usage: python scripts/repair_mojibake.py <file> [--dry-run]")
        return 2

    path = Path(args[0])
    original = path.read_text(encoding="utf-8")
    repaired, changed = repair(original)

    if changed == 0:
        print(f"{path}: nothing to repair")
        return 0

    print(f"{path}: {changed} line(s) would be repaired")
    if dry_run:
        for before, after in zip(original.split("\n"), repaired.split("\n")):
            if before != after:
                # The console may not be able to render the characters, so
                # show them as escaped ASCII rather than raw text.
                print(f"  - {before.strip()[:100]!r}")
                print(f"  + {after.strip()[:100]!r}")
        return 0

    path.write_text(repaired, encoding="utf-8")
    print(f"{path}: repaired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
