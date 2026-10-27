"""
mcp_server/server.py
The RepoScope MCP server.

Milestone 3 (Sprint 4) — but the CLI's `reposcope mcp .` command needs
something real to launch, so the server ships in Sprint 3 with the
deterministic tool set and grows in Sprint 4.

Correction C1 — transports. `stdio` (the default, for Claude Desktop,
Cursor, Claude Code) and `streamable-http` (for containers and hosted
setups). **No SSE.** SSE was deprecated by the MCP spec in revision
2025-03-26, and the 2026-07-28 revision made the transport stateless.
`FastMCP.run()` still accepts `transport="sse"`, but it is legacy and
this server does not offer it.

Correction C11 — one index, three front-ends. The server is a CLIENT of
the GraphStore: it reads `.reposcope/graph.json` (or builds it), and it
never parses source code itself. That is what makes the answer it gives
an agent identical to the map a human sees.

Every tool is deterministic. An agent that asks "what breaks if I change
this file?" gets the graph's answer — with `file:line` citations it can
quote — not a model's opinion.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("reposcope.mcp")

#: Where the backend package lives, so the server can be launched as a
#: script (`python -m mcp_server.server`) from anywhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def resolve_root(explicit: str | None = None) -> Path:
    """
    Resolve the repository root.

    In order: the `--root` argument, the `REPOSCOPE_ROOT` environment
    variable, then the current directory. The resolved ABSOLUTE path is
    echoed in the tool descriptions, so the agent can cite real paths
    rather than relative ones.
    """
    candidate = explicit or os.getenv("REPOSCOPE_ROOT") or os.getcwd()
    return Path(candidate).expanduser().resolve()


def load_index(root: Path) -> dict:
    """
    Load the graph for a repository, building it if necessary.

    Reads the persisted index when there is one — but only when that
    index is still TRUE. An index is dated when it is written, and a
    source file newer than that date means the index describes a
    codebase that no longer exists. Answering an agent from a stale
    index is worse than rebuilding it: the agent cites it.

    Otherwise the graph is built and persisted, so the next call is
    instant.
    """
    from graph_store import JsonGraphStore

    store = JsonGraphStore(root / ".reposcope" / "graph.json")
    if store.exists():
        graph = store.load()
        if graph.get("nodes") and _index_is_current(store, root):
            log.info("Loaded the index from %s", store.path)
            return graph
        log.info(
            "The index at %s no longer describes the source — rebuilding it",
            store.path,
        )

    from graph_builder import build_graph_from_repo
    from parse_cache import ParseCache, default_cache_path

    cache = ParseCache(default_cache_path(root))
    cache.load()
    graph = build_graph_from_repo(str(root), cache)
    cache.save()
    try:
        store.save(graph)
    except ValueError as exc:
        log.warning("Could not persist the index: %s", exc)
    return graph


def _index_is_current(store, root: Path) -> bool:
    """True when the persisted index is newer than every source file."""
    from graph_builder import newest_source_mtime

    built_at = store.built_at()
    if built_at is None:
        return False
    return newest_source_mtime(root) <= built_at


def build_server(root: str | None = None):
    """
    Create the FastMCP application with every tool registered.

    The root is resolved once, at start-up, and every tool answers about
    THAT repository. Re-resolving it per call would let a tool drift
    away from the index it was started with.
    """
    from mcp.server.fastmcp import FastMCP

    from mcp_server import tools as T

    resolved = resolve_root(root)
    graph = load_index(resolved)
    root_text = str(resolved)

    mcp = FastMCP(
        "RepoScope",
        instructions=(
            "RepoScope indexes a repository with Tree-sitter and serves the "
            f"resulting code graph. The repository root is {root_text}. "
            "Paths in every answer are relative to that root; cite them as "
            "`path/to/file.py:LINE`."
        ),
    )

    @mcp.tool()
    def get_architecture_overview(max_depth: int = 2) -> dict:
        """
        A summary of the repository's architecture: the layers, the most
        central files (by PageRank), the entry points, and how much of the
        graph is reachable within `max_depth` hops of an entry point.

        Start here. It is the cheapest way to learn the shape of a codebase
        you have never seen.
        """
        return T.architecture_overview(graph, root_text, max_depth=max_depth)

    @mcp.tool()
    def calculate_blast_radius(
        target_file: str,
        target_symbol: str | None = None,
        depth: int = 3,
    ) -> dict:
        """
        What breaks if this file (or symbol) changes.

        Returns the direct dependents, the transitive dependents, and a
        risk score from 0 to 10. Every impacted node carries its path and
        line, so the answer can be cited directly.
        """
        return T.blast_radius(graph, target_file, target_symbol, depth)

    @mcp.tool()
    def get_dependency_lineage(
        file_path: str,
        direction: str = "both",
    ) -> dict:
        """
        The lineage of a file: what it imports and calls (`upstream`), and
        what imports and calls it (`downstream`).

        Use `direction="upstream"` to find what a file needs, and
        `direction="downstream"` to find what needs it.
        """
        return T.dependency_lineage(graph, file_path, direction)

    @mcp.tool()
    def explain_architectural_rule(source_file: str, imported_file: str) -> dict:
        """
        Does this import cross a declared architectural boundary?

        The rules are the team's own, from `.reposcope.yml` when the
        repository has one, and RepoScope's built-in five-layer taxonomy
        otherwise. This is the same rule set the UI uses.
        """
        return T.explain_architectural_rule(graph, source_file, imported_file, root_text)

    @mcp.tool()
    def get_repo_map(token_budget: int = 8000) -> dict:
        """
        A compact map of the repository, ranked by centrality, that fits in
        `token_budget` tokens.

        The point of the map is the number: it states what the whole
        repository would cost an agent to read, and what this map costs
        instead.
        """
        from repo_map import build_repo_map_with_metrics

        return build_repo_map_with_metrics(graph, root_text, token_budget)

    @mcp.tool()
    def find_dependency_cycles() -> dict:
        """
        The dependency cycles, at file level and at symbol level.

        A cycle that crosses architectural layers is a violation; a cycle
        inside one layer is a code smell. The report says which is which.
        """
        return T.find_dependency_cycles(graph)

    @mcp.tool()
    def get_hotspots(limit: int = 10) -> dict:
        """
        The files that change often AND are widely depended upon.

        That combination is where regressions actually happen: churn
        alone is noise, centrality alone is a fact, the product of the
        two is a risk.
        """
        return T.hotspots(graph, root_text, limit)

    @mcp.tool()
    def find_unreachable_symbols() -> dict:
        """
        The symbols that no entry point can reach.

        This is a STATIC ESTIMATE. Dynamic dispatch, reflection and
        plugin registration are invisible to it, so it is not proof of
        dead code — and the answer says so.
        """
        return T.unreachable_symbols(graph)

    # ── Phase 4 Tools ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_mindmap_hierarchy(
        include_symbols: bool = True,
        max_nodes: int = 2000,
    ) -> dict:
        """
        Return the hierarchical mind-map tree of the repository: root -> pillars ->
        folders -> files -> symbols. Deterministic projection bounded by `max_nodes`.
        """
        return T.mindmap_hierarchy(graph, root_text, include_symbols, max_nodes)

    @mcp.tool()
    def get_ast_skeleton(file_path: str, max_symbols: int = 200) -> dict:
        """
        Return the AST skeleton of a file: symbols, signatures, lines, roles, and
        complexity. Deterministic output that omits bodies to conserve tokens.
        """
        return T.ast_skeleton(graph, root_text, file_path, max_symbols)

    @mcp.tool()
    def get_context_pack(
        paths: str = "",
        detail: str = "skeleton",
        budget: int = 8000,
        since_hash: str | None = None,
    ) -> dict:
        """
        Build a deterministic, token-budget-bounded context pack.
        JSON only over MCP (TOON format is an HTTP export). Detail can be 'skeleton'
        or 'full'. If since_hash matches, returns an unchanged envelope.
        """
        return T.context_pack(graph, root_text, paths, detail, budget, since_hash)

    @mcp.tool()
    def diff_interface_contracts(
        file_path: str,
        patch: str | None = None,
        old_source: str | None = None,
        new_source: str | None = None,
        include_consumers: bool = True,
    ) -> dict:
        """
        Diff interface contracts and boundary crossings between a patch or source pair.
        Deterministic check. Caveat: No finding is not proof that no consumer breaks;
        dynamic dispatch, reflection, and unsupported languages are invisible to this check.
        """
        return T.diff_interface_contracts(
            graph, file_path, patch, old_source, new_source, include_consumers
        )

    @mcp.tool()
    def get_ranked_reading_path(max_files: int = 12) -> dict:
        """
        Return a ranked, three-level reading path: Entry Points -> Core Modules -> Utils & Leaves.
        Caveat: Ranking uses static graph connectivity; it is a starting path, not a measure of code quality.
        """
        return T.ranked_reading_path(graph, root_text, max_files)

    # ── Resources ─────────────────────────────────────────────────────────
    #
    # Resources are the READ side: an agent can pull a summary without
    # spending a tool call. The URIs are stable, so a client can bookmark
    # them.

    @mcp.resource("reposcope://graph/summary")
    def graph_summary() -> str:
        """
        The graph's shape: node and edge counts, the layer split, and the
        most central files by PageRank.
        """
        return json.dumps(
            T.graph_summary_resource(graph, root_text), indent=2, sort_keys=True,
        )

    @mcp.resource("reposcope://hotspots")
    def hotspots_resource() -> str:
        """The churn x centrality hotspots — the files most likely to regress."""
        return json.dumps(T.hotspots(graph, root_text, 10), indent=2, sort_keys=True)

    @mcp.resource("reposcope://repo-map")
    def repo_map_resource() -> str:
        """The budgeted repo map, with the context-saving figure."""
        from repo_map import build_repo_map_with_metrics

        return json.dumps(
            build_repo_map_with_metrics(graph, root_text, 8000),
            indent=2, sort_keys=True,
        )

    @mcp.resource("reposcope://dead-code")
    def dead_code_resource() -> str:
        """The unreachable symbols — labelled as an estimate, never as a certainty."""
        return json.dumps(T.unreachable_symbols(graph), indent=2, sort_keys=True)

    @mcp.resource("reposcope://cycles")
    def cycles_resource() -> str:
        """The dependency cycles, with the layers they span."""
        return json.dumps(T.find_dependency_cycles(graph), indent=2, sort_keys=True)

    # ── Phase 4 Resources ─────────────────────────────────────────────────

    @mcp.resource("reposcope://mindmap")
    def mindmap_resource() -> str:
        """The hierarchical mindmap projection of the repository."""
        return json.dumps(
            T.mindmap_hierarchy(graph, root_text, include_symbols=True, max_nodes=2000),
            indent=2,
            sort_keys=True,
        )

    @mcp.resource("reposcope://api-routes")
    def api_routes_resource() -> str:
        """The detected API routes in the repository."""
        return json.dumps(
            T.api_routes_resource(graph, root_text),
            indent=2,
            sort_keys=True,
        )

    @mcp.resource("reposcope://context-pack")
    def context_pack_resource() -> str:
        """The default skeleton context pack for the repository within 8000 tokens."""
        return json.dumps(
            T.context_pack(graph, root_text, detail="skeleton", budget=8000),
            indent=2,
            sort_keys=True,
        )

    return mcp


def main(argv: list[str] | None = None) -> int:
    """The `reposcope-mcp` entry point."""
    parser = argparse.ArgumentParser(
        prog="reposcope-mcp",
        description="Serve a repository's code graph over the Model Context Protocol.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="The repository to index. Defaults to $REPOSCOPE_ROOT, then the cwd.",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve over Streamable HTTP instead of stdio.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="The host to bind when serving over HTTP.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="The port to bind when serving over HTTP.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    mcp = build_server(args.root)

    if args.http:
        # Correction C1: Streamable HTTP, not the deprecated SSE transport.
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")

    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
