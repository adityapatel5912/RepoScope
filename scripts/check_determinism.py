"""Determinism check — the same repository must always yield the same graph."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "backend" / "tests" / "fixtures"

SNIPPET = """
import hashlib, json, sys
sys.path.insert(0, {backend!r})
from graph_builder import build_graph_from_repo
graph = build_graph_from_repo({fixture!r})
payload = json.dumps(
    {{"nodes": sorted(graph["nodes"], key=lambda n: n["id"]),
      "edges": sorted(graph["edges"], key=lambda e: (e["source"], e["target"], e.get("type")))}},
    sort_keys=True,
)
print(hashlib.sha256(payload.encode()).hexdigest())
"""

for fixture in ("multilang", "circular", "nested", "real_small"):
    path = str(FIXTURES / fixture)
    code = SNIPPET.format(backend=str(REPO / "backend"), fixture=path)
    hashes = set()
    for _ in range(3):
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=180
        )
        if out.returncode != 0:
            print(f"{fixture:12} ERROR: {out.stderr[-400:]}")
            break
        hashes.add(out.stdout.strip())
    if len(hashes) == 1:
        print(f"{fixture:12} DETERMINISTIC  {hashes.pop()[:16]}")
    else:
        print(f"{fixture:12} NON-DETERMINISTIC — {len(hashes)} distinct graphs")
        for h in sorted(hashes):
            print(f"                {h[:16]}")
