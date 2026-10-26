"""
mcp_server/
The RepoScope Model Context Protocol server.

Milestone 3. Correction C1 — the transports are stdio and Streamable
HTTP. SSE is deprecated and is not offered.

    from mcp_server.server import build_server, main
"""
from __future__ import annotations

__all__ = ["build_server", "main"]


def __getattr__(name: str):
    # Lazy so that importing the package does not import the MCP SDK —
    # the SDK is only needed when a server is actually created.
    if name in ("build_server", "main"):
        from mcp_server import server

        return getattr(server, name)
    raise AttributeError(name)
