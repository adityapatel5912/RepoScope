"""
graph_utils.py
Shared graph-traversal helpers for Code Tours and What-If Impact Analysis.
Both features read the same node/edge shapes produced by graph_builder.py.
"""
from collections import deque
from typing import Dict, List, Tuple, Optional


def build_adjacency(graph: dict) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Return (forward_adj, reverse_adj) from graph edges.
    forward_adj[src] = [dsts...]
    reverse_adj[dst] = [srcs...]
    """
    forward: Dict[str, List[str]] = {}
    reverse: Dict[str, List[str]] = {}
    for e in graph.get("edges", []):
        src, dst = e.get("source"), e.get("target")
        if not src or not dst:
            continue
        forward.setdefault(src, []).append(dst)
        reverse.setdefault(dst, []).append(src)
    return forward, reverse


def find_node_by_label(graph: dict, label: str) -> Optional[dict]:
    """Fuzzy-find a node by label or id substring (case-insensitive)."""
    if not label:
        return None
    needle = label.lower().strip()
    nodes = graph.get("nodes", [])
    # Exact label match first
    for n in nodes:
        if n.get("label", "").lower() == needle:
            return n
    # Substring match on label
    for n in nodes:
        if needle in n.get("label", "").lower():
            return n
    # Substring match on id
    for n in nodes:
        if needle in n.get("id", "").lower():
            return n
    return None


def bfs_traverse(adj: Dict[str, List[str]], start: str,
                 max_depth: int = 3) -> Dict[int, List[str]]:
    """BFS returning {depth: [node_ids]} excluding the start node."""
    visited = {start}
    result: Dict[int, List[str]] = {}
    queue = deque([(start, 0)])
    while queue:
        nid, depth = queue.popleft()
        if depth > max_depth:
            continue
        if depth > 0:
            result.setdefault(depth, []).append(nid)
        for nxt in adj.get(nid, []):
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, depth + 1))
    return result
