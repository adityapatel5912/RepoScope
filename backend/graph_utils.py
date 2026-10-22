"""
graph_utils.py
Shared graph-traversal helpers for Code Tours and What-If Impact Analysis.
Both features read the same node/edge shapes produced by graph_builder.py.

It also holds the **LRU cache over the adjacency structures** (Milestone
6.2). Building the forward and reverse adjacency is O(edges) and every
traversal needs it, so it is cached.

The cache is keyed by the graph's CONTENT, not by its identity. That is
what makes invalidation per-subgraph automatic: when an edit changes an
edge, the content signature changes, and the stale entry is simply never
looked up again. A cache keyed by object identity would need explicit
invalidation, and explicit invalidation is what gets forgotten.
"""
from collections import OrderedDict, deque
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


class LruCache:
    """
    A small LRU cache with explicit eviction.

    Standard library only — `functools.lru_cache` cannot be used because
    the key is a content signature that has to be COMPUTED, not a
    hashable argument.
    """

    def __init__(self, maxsize: int = 8):
        self.maxsize = max(1, maxsize)
        self._entries: "OrderedDict[object, object]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        value = self._entries.get(key)
        if value is None:
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return value

    def put(self, key, value) -> None:
        self._entries[key] = value
        self._entries.move_to_end(key)
        while len(self._entries) > self.maxsize:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "entries": len(self._entries),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }


#: The adjacency cache. Small on purpose: the graph changes on every
#: edit, and a large cache would hold big graphs alive.
_ADJACENCY_CACHE = LruCache(maxsize=6)


def graph_signature(graph: dict) -> tuple:
    """
    A cheap content signature for a graph's edges.

    Two graphs with the same nodes and edges have the same signature,
    and any edit that changes an edge changes it. That is the
    invalidation rule.
    """
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    edge_key = hash(tuple(
        (e.get("source"), e.get("target"), e.get("type"))
        for e in edges
    ))
    return (len(nodes), len(edges), edge_key)


def build_adjacency_cached(graph: dict) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    The forward and reverse adjacency, from the cache when possible.

    The traversal-heavy endpoints — the blast radius, the lineage, the
    dependency check — all need this, and they all ask for it more than
    once per request.
    """
    signature = graph_signature(graph)
    cached = _ADJACENCY_CACHE.get(signature)
    if cached is not None:
        return cached

    adjacency = build_adjacency(graph)
    _ADJACENCY_CACHE.put(signature, adjacency)
    return adjacency


def adjacency_cache_stats() -> dict:
    """The cache's counters, for the diagnostics endpoint."""
    return _ADJACENCY_CACHE.stats()


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
