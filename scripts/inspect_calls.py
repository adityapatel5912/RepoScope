"""Inspect the call edges attributed to a specific symbol family."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from graph_builder import build_graph_from_repo  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"

fixture = sys.argv[1] if len(sys.argv) > 1 else "real_small"
prefix = sys.argv[2] if len(sys.argv) > 2 else "func:src/tomli/_parser.py:__init__"

graph = build_graph_from_repo(str(FIXTURES / fixture))
by_id = {n["id"]: n for n in graph["nodes"]}

targets = [n for n in graph["nodes"] if n["id"].startswith(prefix)]
print(f"{len(targets)} symbols matching {prefix!r}")
for node in sorted(targets, key=lambda n: n.get("line", 0)):
    outs = [e["target"] for e in graph["edges"]
            if e["type"] == "calls" and e["source"] == node["id"]]
    names = [by_id[o]["label"] for o in outs][:6]
    print(f'  line {node.get("line", 0):>5}  id={node["id"]}')
    print(f'          {len(outs):>3} calls -> {names}')
