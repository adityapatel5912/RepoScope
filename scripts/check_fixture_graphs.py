"""Sprint 1 verification helper — graph shape across every fixture."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from graph_builder import build_graph_from_repo  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"

for name in ("multilang", "circular", "nested", "real_small"):
    graph = build_graph_from_repo(str(FIXTURES / name))
    node_types = Counter(n["type"] for n in graph["nodes"])
    edge_types = Counter(e["type"] for e in graph["edges"])
    ids = [n["id"] for n in graph["nodes"]]
    dupes = {k: v for k, v in Counter(ids).items() if v > 1}
    known = set(ids)
    dangling = [e for e in graph["edges"] if e["source"] not in known or e["target"] not in known]

    print(f"{name:12} nodes={len(ids):3} {dict(node_types)}")
    print(f"{'':12} edges={len(graph['edges']):3} {dict(edge_types)}  dupes={len(dupes)} dangling={len(dangling)}")
    for k, v in list(dupes.items())[:5]:
        print(f"    DUPLICATE {k} x{v}")
    for e in dangling[:5]:
        print(f"    DANGLING {e}")
