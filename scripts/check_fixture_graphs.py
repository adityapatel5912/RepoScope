"""Sprint 0 verification helper — graph shape across every fixture."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from graph_builder import build_graph_from_repo  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"

for name in ("multilang", "circular", "nested", "real_small"):
    graph = build_graph_from_repo(str(FIXTURES / name))
    ids = [n["id"] for n in graph["nodes"]]
    dupes = {k: v for k, v in Counter(ids).items() if v > 1}
    js_symbols = [
        n for n in graph["nodes"]
        if n["type"] in ("function", "class")
        and str(n.get("file", "")).endswith((".ts", ".tsx", ".js"))
    ]
    with_line = sum(1 for n in js_symbols if "line" in n)
    print(
        f"{name:12} nodes={len(ids):3}  edges={len(graph['edges']):3}  "
        f"dupes={len(dupes)}  js_symbols_with_line={with_line}/{len(js_symbols)}"
    )
    for k, v in list(dupes.items())[:5]:
        print(f"    DUPLICATE {k} x{v}")
