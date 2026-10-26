"""
mindmap.py
The server-side projection from a schema v2 graph to the mind-map tree.

The tree is a strict hierarchy and the API freezes it:

    root → pillar → folder → file → symbol

No client may classify a file. The `pillar` and `role` fields come from
the graph, and this module only projects them. The projection is
deterministic: the same graph and the same `max_nodes` produce the same
tree, byte for byte, apart from the API's own timestamp.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from mindmap_classifier import (
    PILLARS,
    PILLAR_IDS,
    PILLAR_ROOT_DIRS,
    classify_file,
    pillar_label,
)

DEFAULT_MAX_NODES = 20_000
MAX_NODES_LIMIT = 200_000


def _basename(path: str) -> str:
    return Path(path).name or path


def _folder_chain(path: str, pillar: str) -> list[str]:
    """
    Repo-relative folder paths under a pillar, parent before child.

    The pillar's own root directory is not repeated as a separate level.
    For `backend/api/routers/x.py`, the first folder is `backend/api`
    (labelled `api`), not a `backend` folder followed by an `api` folder.
    The full repository-relative path is preserved in each folder node.
    """
    parts = [part for part in path.split("/")[:-1] if part]
    roots = PILLAR_ROOT_DIRS.get(pillar, frozenset())
    start = 1 if parts and parts[0].lower() in roots else 0
    return ["/".join(parts[:index + 1]) for index in range(start, len(parts))]


def _new_node(
    node_id: str,
    kind: str,
    label: str,
    parent_id: str | None,
    **extra: Any,
) -> dict:
    node = {
        "id": node_id,
        "kind": kind,
        "label": label,
        "parent_id": parent_id,
        "children": [],
    }
    node.update(extra)
    return node


def build_mindmap_payload(
    graph: dict,
    include_symbols: bool = True,
    max_nodes: int = DEFAULT_MAX_NODES,
    root_label: str = "RepoScope",
) -> dict:
    """
    Project a graph into the frozen mind-map payload.

    `max_nodes` caps the returned tree deterministically: root and
    pillars first, then folders (shallow to deep), then files by path,
    then symbols by line. A node is only included when its parent is
    included, so the result is always a valid tree.
    """
    limit = max(1, min(int(max_nodes), MAX_NODES_LIMIT))
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    api_routes = graph.get("api_routes", []) or []

    root = _new_node("root", "root", root_label, None)
    pillars: dict[str, dict] = {}
    for pillar in PILLARS:
        pillar_id = pillar["id"]
        node = _new_node(
            f"pillar:{pillar_id}",
            "pillar",
            pillar["label"],
            "root",
            pillar=pillar_id,
            description=pillar["description"],
            metrics={"files": 0, "symbols": 0, "routes": 0},
        )
        pillars[pillar_id] = node
        root["children"].append(node)

    file_nodes = [node for node in nodes if node.get("type") == "file"]
    file_nodes.sort(key=lambda node: str(node.get("path") or node.get("id") or ""))

    folder_nodes: dict[str, dict] = {}
    folder_parent: dict[str, str] = {}
    file_payload_by_id: dict[str, dict] = {}
    symbols_by_file: dict[str, list[dict]] = {}

    for node in nodes:
        if node.get("type") in ("function", "class") and node.get("file"):
            symbols_by_file.setdefault(str(node["file"]), []).append(node)
    for symbol_list in symbols_by_file.values():
        symbol_list.sort(key=lambda node: (
            int(node.get("line") or 0), str(node.get("id") or ""),
        ))

    for file_node in file_nodes:
        rel = str(file_node.get("path") or str(file_node.get("id", ""))[5:])
        if not rel:
            continue
        info = classify_file(rel)
        pillar = str(file_node.get("pillar") or info["pillar"])
        role = str(file_node.get("role") or info["role"])
        if pillar not in PILLAR_IDS:
            pillar = info["pillar"]

        chain = _folder_chain(rel, pillar)
        parent_id = f"pillar:{pillar}"
        for folder_path in chain:
            folder_id = f"folder:{pillar}:{folder_path}"
            if folder_id not in folder_nodes:
                folder = _new_node(
                    folder_id,
                    "folder",
                    _basename(folder_path),
                    parent_id,
                    path=folder_path,
                )
                folder_nodes[folder_id] = folder
                folder_parent[folder_id] = parent_id
                container = (
                    pillars[pillar] if parent_id == f"pillar:{pillar}"
                    else folder_nodes.get(parent_id)
                )
                if container is not None:
                    container["children"].append(folder)
            parent_id = folder_id

        file_id = str(file_node.get("id") or f"file:{rel}")
        payload = _new_node(
            file_id,
            "file",
            _basename(rel),
            parent_id,
            path=rel,
            line=1,
            role=role,
            pillar=pillar,
            language=str(file_node.get("language") or ""),
        )
        if file_node.get("pagerank") is not None:
            payload["pagerank"] = file_node.get("pagerank")
        route_count = int(file_node.get("route_count") or 0)
        if route_count:
            payload["route_count"] = route_count
        file_payload_by_id[file_id] = payload
        container = (
            pillars[pillar] if parent_id == f"pillar:{pillar}"
            else folder_nodes.get(parent_id)
        )
        if container is not None:
            container["children"].append(payload)

        if include_symbols:
            for symbol in symbols_by_file.get(rel, []):
                symbol_payload = _new_node(
                    str(symbol.get("id") or ""),
                    "symbol",
                    str(symbol.get("label") or ""),
                    file_id,
                    path=rel,
                    line=int(symbol.get("line") or 0),
                    end_line=int(symbol.get("end_line") or 0),
                    role=str(symbol.get("role") or "utility"),
                )
                routes = symbol.get("routes") or []
                if routes:
                    symbol_payload["route_count"] = len(routes)
                payload["children"].append(symbol_payload)

    # Metrics describe the repository, not the pruned tree.
    for rel in {str(node.get("file")) for node in nodes if node.get("file")}:
        info = classify_file(rel)
        pillar = info["pillar"]
        if pillar in pillars:
            pillars[pillar]["metrics"]["symbols"] += len(symbols_by_file.get(rel, []))
    for file_node in file_nodes:
        rel = str(file_node.get("path") or str(file_node.get("id", ""))[5:])
        info = classify_file(rel)
        pillar = str(file_node.get("pillar") or info["pillar"])
        if pillar in pillars:
            pillars[pillar]["metrics"]["files"] += 1
    for route in api_routes:
        rel = str(route.get("file") or "")
        info = classify_file(rel)
        pillar = info["pillar"]
        if pillar in pillars:
            pillars[pillar]["metrics"]["routes"] += 1

    # ── Deterministic pruning ───────────────────────────────────────────
    total_nodes = 1 + len(pillars) + len(folder_nodes)
    total_nodes += sum(1 for _file in file_payload_by_id.values())
    if include_symbols:
        total_nodes += sum(len(symbols) for symbols in symbols_by_file.values())

    order: list[dict] = [root]
    order.extend(pillars[pillar_id] for pillar_id in PILLAR_IDS if pillar_id in pillars)
    folders = sorted(
        folder_nodes.values(),
        key=lambda node: (
            PILLAR_IDS.index(node["id"].split(":", 2)[1]),
            node["path"].count("/"),
            node["path"],
        ),
    )
    order.extend(folders)
    files = sorted(
        file_payload_by_id.values(),
        key=lambda node: (
            PILLAR_IDS.index(_pillar_of(node, pillars)),
            node["path"],
        ),
    )
    order.extend(files)
    if include_symbols:
        symbol_payloads = [
            symbol
            for file_payload in file_payload_by_id.values()
            for symbol in file_payload["children"]
        ]
        symbol_payloads.sort(key=lambda node: (
            PILLAR_IDS.index(_pillar_of_file(node["path"])),
            node["path"],
            node["line"],
            node["id"],
        ))
        order.extend(symbol_payloads)

    allowed: set[str] = set()
    for node in order:
        if len(allowed) >= limit:
            break
        parent_id = node.get("parent_id")
        if parent_id is None or parent_id in allowed:
            allowed.add(node["id"])

    pruned = _prune(root, allowed)
    omitted = max(0, total_nodes - len(allowed))
    return {
        "schema_version": int(graph.get("schema_version") or 2),
        "source": {
            "nodes": len(nodes),
            "edges": len(edges),
            "root": None,
        },
        "stats": {
            "files": len(file_nodes),
            "symbols": sum(len(symbols) for symbols in symbols_by_file.values()),
            "pillars": len(PILLARS),
            "routes": len(api_routes),
            "api_calls": sum(1 for edge in edges if edge.get("type") == "api_calls"),
        },
        "pillars": [
            {
                "id": pillar["id"],
                "label": pillar["label"],
                "description": pillar["description"],
                "file_count": pillars[pillar["id"]]["metrics"]["files"],
            }
            for pillar in PILLARS
        ],
        "root": pruned,
        "truncated": omitted > 0,
        "omitted": omitted,
        "max_nodes": limit,
    }


def _pillar_of(node: dict, pillars: dict[str, dict]) -> str:
    parent_id = str(node.get("parent_id") or "")
    if parent_id.startswith("pillar:"):
        return parent_id[len("pillar:"):]
    for pillar_id in PILLAR_IDS:
        if parent_id.startswith(f"folder:{pillar_id}:"):
            return pillar_id
    return str(node.get("pillar") or "backend")


def _pillar_of_file(path: str) -> str:
    return classify_file(path)["pillar"]


def _prune(node: dict, allowed: set[str]) -> dict:
    kept = dict(node)
    kept["children"] = [
        _prune(child, allowed)
        for child in node.get("children", [])
        if child.get("id") in allowed
    ]
    return kept


def ancestor_ids(payload: dict, node_id: str) -> list[str]:
    """
    The path from the root to `node_id`, inclusive, or `[]` when absent.

    Phase 5's citation UI uses this to open the mind map at a symbol
    without knowing the pillar or folder chain.
    """
    root = payload.get("root") or payload
    path: list[str] = []

    def walk(node: dict) -> bool:
        if node.get("id") == node_id:
            path.append(str(node["id"]))
            return True
        for child in node.get("children", []):
            if walk(child):
                path.append(str(node["id"]))
                return True
        return False

    return list(reversed(path)) if walk(root) else []


def count_tree_nodes(payload: dict) -> int:
    """The number of nodes in a payload tree, including the root."""
    root = payload.get("root") or payload
    return 1 + sum(count_tree_nodes(child) for child in root.get("children", []))
