"""
orchestrator.py
Combines code-graph context with live GitHub metadata, then hands the
merged context to ask_llm. Falls back to local graph_builder when
codebase-memory-mcp is unavailable.
"""
import logging

from byok_manager import get_user_token
from graph_builder import build_graph_from_repo
from mcp_client import query_codebase_graph, query_github
from repo_tracker import load_state

log = logging.getLogger("reposcope.orchestrator")

# Module-level graph cache so /api/repo/graph can serve it without rebuild
_graph_cache: dict = {"nodes": [], "edges": [], "graph_summary": ""}


def get_cached_graph() -> dict:
    return _graph_cache


async def build_context(
    mode: str,
    message: str,
    repo: str | None,
    session_id: str | None = None,
) -> dict:
    """Build the full context dict passed to ask_llm."""
    global _graph_cache

    state = load_state()

    # 1. Try local graph builder first (fast, no binary dependency)
    graph: dict = {}
    local_path = state.get("local_path")
    if local_path:
        try:
            graph = build_graph_from_repo(local_path)
            log.info("Local graph built: %s", graph.get("summary"))
        except Exception as exc:
            log.warning("Local graph builder failed: %s", exc)

    # 2. Fall back to codebase-memory-mcp if local graph is empty
    if not graph.get("nodes"):
        log.info("Falling back to codebase-memory-mcp")
        graph = await query_codebase_graph(message)
        if graph.get("nodes"):
            log.info("MCP graph returned %d nodes", len(graph["nodes"]))
        else:
            log.warning("codebase-memory-mcp returned empty graph — proceeding without it")

    _graph_cache = graph

    ctx: dict = {
        "graph_summary": graph.get("summary", "No graph available"),
        "nodes": graph.get("nodes", []),
        "edges": graph.get("edges", []),
        "readme": state.get("readme", ""),
        "file_count": state.get("file_count", 0),
        "mode": mode,
    }

    if mode == "tracking" and repo:
        owner, name = repo.split("/", 1)
        user_token = get_user_token(session_id) if session_id else None
        try:
            gh = await query_github(owner, name, state.get("last_check"), user_token)
            ctx["tracking"] = gh
        except Exception as exc:
            log.warning("GitHub tracking fetch failed: %s", exc)

    return ctx
