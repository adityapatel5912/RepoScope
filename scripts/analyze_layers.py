"""
Measure how the layer classifier treats a real repository.

    python scripts/analyze_layers.py <repo-root>

Prints the extension -> layer distribution, and every file that lands in a
layer its extension does not belong to. This is how the classifier's real
mistakes get found — by looking at real code, not by reading the regexes.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(REPO_ROOT))

from arch_rules import classify  # noqa: E402

SKIP = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}

#: Extensions that are code, and therefore legitimately land in a code layer.
CODE_EXT = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp", ".swift", ".kt",
    ".scala", ".sh", ".bash", ".zsh", ".sql", ".html", ".css", ".scss", ".vue",
    ".svelte", ".ipynb", ".gradle", ".tf", ".dockerfile", ".makefile",
}

#: The layer each non-code extension SHOULD land in, when the path gives
#: no better signal.
EXPECTED_NON_CODE = {
    ".md": "storage", ".markdown": "storage", ".txt": "storage", ".rst": "storage",
    ".pdf": "storage", ".doc": "storage", ".docx": "storage", ".ppt": "storage",
    ".pptx": "storage", ".xls": "storage", ".xlsx": "storage", ".csv": "storage",
    ".tsv": "storage", ".json": "storage", ".jsonl": "storage", ".yaml": "storage",
    ".yml": "storage", ".toml": "storage", ".xml": "storage", ".ini": "storage",
    ".cfg": "storage", ".conf": "storage", ".env": "storage",
    ".png": "client", ".jpg": "client", ".jpeg": "client", ".gif": "client",
    ".svg": "client", ".webp": "client", ".ico": "client", ".bmp": "client",
    ".mp4": "client", ".webm": "client", ".mov": "client", ".mp3": "client",
    ".wav": "client", ".ttf": "client", ".woff": "client", ".woff2": "client",
    ".zip": "storage", ".tar": "storage", ".gz": "storage", ".bin": "storage",
    ".lock": "storage", ".log": "storage", ".pyc": "storage",
    ".gitignore": "storage", ".gitattributes": "storage", ".editorconfig": "storage",
    ".dockerignore": "storage", ".npmrc": "storage", ".nvmrc": "storage",
    ".prettierrc": "storage", ".eslintrc": "storage", ".babelrc": "storage",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/analyze_layers.py <repo-root>")
        return 2

    root = Path(sys.argv[1]).resolve()
    rows = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP for part in path.parts):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        suffix = path.suffix.lower()
        rows.append((rel, suffix, classify(f"file:{rel}", rel)))

    total = len(rows)
    print(f"repository: {root}")
    print(f"files: {total}\n")

    by_ext = defaultdict(Counter)
    for _rel, ext, layer in rows:
        by_ext[ext][layer] += 1

    print("--- extension -> layer ---")
    for ext in sorted(by_ext, key=lambda e: (-sum(by_ext[e].values()), e)):
        counts = by_ext[ext]
        dominant = counts.most_common(1)[0]
        flag = ""
        if ext not in CODE_EXT and ext in EXPECTED_NON_CODE:
            if dominant[0] != EXPECTED_NON_CODE[ext]:
                flag = f"   <-- expected {EXPECTED_NON_CODE[ext]}"
        print(f"  {(ext or '(none)'):12} {sum(counts.values()):4}  {dict(counts)}{flag}")

    print("\n--- misclassified non-code files ---")
    bad = [
        (rel, ext, layer)
        for rel, ext, layer in rows
        if ext in EXPECTED_NON_CODE and layer != EXPECTED_NON_CODE[ext]
    ]
    if not bad:
        print("  (none)")
    for rel, ext, layer in bad[:40]:
        print(f"  {layer:9} {ext:10} {rel}")
    if len(bad) > 40:
        print(f"  ... and {len(bad) - 40} more")
    print(f"\n  total misclassified: {len(bad)} of {total}")

    layer_totals = Counter(layer for _r, _e, layer in rows)
    print(f"\n--- layer totals ---\n  {dict(layer_totals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
