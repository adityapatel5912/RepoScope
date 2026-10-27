"""
backend/tests/test_mcp_v25.py
Tests for Phase 4 MCP tools and resources over in-memory MCP sessions.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _server_for(fixture: str = "v2_contract"):
    from mcp_server.server import build_server

    return build_server(str(FIXTURES_DIR / fixture))


def _run(coro):
    return asyncio.run(coro)


def _call(tool: str, arguments: dict, fixture: str = "v2_contract"):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def check():
        server = _server_for(fixture)
        async with create_connected_server_and_client_session(server) as session:
            await session.initialize()
            return await session.call_tool(tool, arguments)

    return _run(check())


def _read_resource(uri: str, fixture: str = "v2_contract"):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def check():
        server = _server_for(fixture)
        async with create_connected_server_and_client_session(server) as session:
            await session.initialize()
            return await session.read_resource(uri)

    result = _run(check())
    return json.loads(result.contents[0].text)


def _payload(result):
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured.get("result", structured)
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    return {}


def test_mcp_get_mindmap_hierarchy():
    res = _call("get_mindmap_hierarchy", {"include_symbols": True, "max_nodes": 500})
    payload = _payload(res)
    assert payload["available"] is True
    assert payload["schema_version"] == 2
    assert "pillars" in payload
    assert payload["max_nodes"] == 500


def test_mcp_get_ast_skeleton_no_body():
    res = _call("get_ast_skeleton", {"file_path": "base.py"})
    payload = _payload(res)
    assert payload["available"] is True
    assert payload["file"] == "base.py"
    assert len(payload["symbols"]) > 0
    for sym in payload["symbols"]:
        assert "body" not in sym
        assert sym["signature"]


def test_mcp_get_context_pack_defaults_and_since_hash():
    # Default skeleton context pack
    res = _call("get_context_pack", {})
    payload = _payload(res)
    assert payload["available"] is True
    assert payload["detail"] == "skeleton"
    assert payload["budget"] == 8000
    assert payload["format"] == "json"
    pack_hash = payload["hash"]
    assert pack_hash.startswith("sha256:")

    # since_hash matching returns unchanged envelope
    res_unchanged = _call("get_context_pack", {"since_hash": pack_hash})
    payload_unchanged = _payload(res_unchanged)
    assert payload_unchanged.get("unchanged") is True
    assert "files" not in payload_unchanged
    assert payload_unchanged["hash"] == pack_hash


def test_mcp_diff_interface_contracts():
    old_py = "def compute(x: int) -> int:\n    return x * 2\n"
    new_py = "def compute(x: int, y: int) -> int:\n    return x + y\n"

    res = _call(
        "diff_interface_contracts",
        {"file_path": "math.py", "old_source": old_py, "new_source": new_py},
    )
    payload = _payload(res)
    assert payload["available"] is True
    assert payload["file"] == "math.py"
    assert "findings" in payload
    assert "counts" in payload
    assert "note" in payload
    assert "No finding is not proof" in payload["note"]


def test_mcp_get_ranked_reading_path():
    res = _call("get_ranked_reading_path", {"max_files": 10})
    payload = _payload(res)
    assert payload["available"] is True
    assert "levels" in payload
    assert len(payload["levels"]) == 3
    assert "path" in payload
    assert len(payload["path"]) <= 10
    assert "caveat" in payload
    assert "Ranking uses static graph connectivity" in payload["caveat"]


def test_mcp_resource_mindmap():
    data = _read_resource("reposcope://mindmap")
    assert data["available"] is True
    assert "pillars" in data


def test_mcp_resource_api_routes():
    data = _read_resource("reposcope://api-routes")
    assert data["available"] is True
    assert "routes" in data


def test_mcp_resource_context_pack():
    data = _read_resource("reposcope://context-pack")
    assert data["available"] is True
    assert data["detail"] == "skeleton"
    assert data["budget"] == 8000
    assert "files" in data
