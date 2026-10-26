"""
test_mcp_server.py
The MCP server's contract.

Milestone 3, with the server itself shipped in Sprint 3 so the CLI's
`reposcope mcp .` command had something real to launch.

What is asserted here:

    * the server completes the MCP initialize handshake;
    * `tools/list` returns exactly the expected tools, each with a valid
      JSON Schema;
    * every tool returns a correct answer against a fixture repository;
    * **no SSE transport anywhere in the codebase** (Correction C1 — SSE
      was deprecated by the spec in revision 2025-03-26).

The tool calls go over a REAL in-memory MCP session, not by calling the
Python functions directly. A test that calls the function skips the
protocol, and the protocol is the thing that breaks when the SDK moves.
"""
import asyncio
import ast
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

#: The tools the server exposes. The roadmap names four; the repo map
#: (M8.1) was added because it is the number the product is built
#: around, and an agent that can ask for the map directly saves a round
#: trip.
EXPECTED_TOOLS = {
    "get_architecture_overview",
    "calculate_blast_radius",
    "get_dependency_lineage",
    "explain_architectural_rule",
    "get_repo_map",
}


def _server_for(fixture: str):
    """A server bound to a fixture repository."""
    from mcp_server.server import build_server

    return build_server(str(FIXTURES_DIR / fixture))


def _run(coro):
    return asyncio.run(coro)


# ── The handshake and the tool list ─────────────────────────────────────────

def test_the_server_completes_the_initialize_handshake():
    """A server that cannot say hello is not an MCP server."""
    from mcp.shared.memory import create_connected_server_and_client_session

    async def check():
        server = _server_for("multilang")
        async with create_connected_server_and_client_session(server) as session:
            result = await session.initialize()
            return result

    result = _run(check())
    assert result is not None
    # The handshake returns the negotiated protocol version and the
    # server's identity. Both must be present for a client to proceed.
    assert getattr(result, "protocolVersion", None), "no protocol version was negotiated"
    assert getattr(result, "serverInfo", None), "the server did not identify itself"
    assert getattr(result, "capabilities", None) is not None


def test_tools_list_returns_exactly_the_expected_tools():
    from mcp.shared.memory import create_connected_server_and_client_session

    async def check():
        server = _server_for("multilang")
        async with create_connected_server_and_client_session(server) as session:
            await session.initialize()
            return await session.list_tools()

    listed = _run(check())
    names = {tool.name for tool in listed.tools}
    assert names == EXPECTED_TOOLS, f"unexpected tool set: {sorted(names)}"


def test_every_tool_has_a_valid_json_schema():
    from mcp.shared.memory import create_connected_server_and_client_session

    async def check():
        server = _server_for("multilang")
        async with create_connected_server_and_client_session(server) as session:
            await session.initialize()
            return await session.list_tools()

    listed = _run(check())
    for tool in listed.tools:
        assert tool.description, f"{tool.name} has no description"
        schema = tool.inputSchema
        assert isinstance(schema, dict), f"{tool.name} has no input schema"
        assert schema.get("type") == "object", f"{tool.name} schema is not an object"
        # A schema that cannot be serialised is a schema a client cannot
        # use.
        json.dumps(schema)


def test_the_tool_description_echoes_the_resolved_root():
    """
    The agent must be able to cite real paths.

    The server's instructions carry the ABSOLUTE repository root, so an
    answer that says `backend/auth.py` can be turned into a path the
    agent's editor can open.
    """
    server = _server_for("multilang")
    instructions = server.instructions
    assert instructions
    assert "multilang" in instructions
    assert str(FIXTURES_DIR.resolve()) in instructions


# ── The tools actually work ─────────────────────────────────────────────────

def _call(tool: str, arguments: dict):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def check():
        server = _server_for("multilang")
        async with create_connected_server_and_client_session(server) as session:
            await session.initialize()
            return await session.call_tool(tool, arguments)

    return _run(check())


def _payload(result):
    """The JSON payload of a tool result."""
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured.get("result", structured)
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    return {}


def test_get_architecture_overview_describes_the_repository():
    payload = _payload(_call("get_architecture_overview", {}))
    assert payload["available"] is True
    assert payload["node_count"] > 0
    assert payload["edge_count"] > 0
    assert payload["layers"], "no layers were reported"
    assert payload["top_hubs"], "no hubs were reported"
    assert payload["entry_points"], "no entry points were reported"


def test_calculate_blast_radius_finds_the_dependents():
    """`app.py` imports `helpers.py`, so helpers has a dependent."""
    payload = _payload(_call("calculate_blast_radius", {"target_file": "helpers.py"}))
    assert payload["available"] is True
    labels = {n["label"] for n in payload["direct_impacts"]}
    assert "app.py" in labels, f"app.py is not listed as a dependent: {labels}"


def test_calculate_blast_radius_names_the_consumers_when_given_a_symbol():
    payload = _payload(_call(
        "calculate_blast_radius",
        {"target_file": "helpers.py", "target_symbol": "shout"},
    ))
    assert payload["available"] is True
    assert payload["target"]["label"] == "shout"


def test_calculate_blast_radius_reports_a_missing_target():
    payload = _payload(_call("calculate_blast_radius", {"target_file": "nope.py"}))
    assert payload["available"] is False
    assert payload["reason"]


def test_get_dependency_lineage_goes_both_ways():
    payload = _payload(_call("get_dependency_lineage", {"file_path": "app.py"}))
    assert payload["available"] is True
    assert payload["target"] == "file:app.py"

    upstream = payload.get("upstream") or []
    downstream = payload.get("downstream") or []
    assert upstream or downstream, "the lineage was empty in both directions"


def test_explain_architectural_rule_reports_the_layers():
    payload = _payload(_call(
        "explain_architectural_rule",
        {"source_file": "app.py", "imported_file": "helpers.py"},
    ))
    assert payload["available"] is True
    assert payload["source_layer"]
    assert payload["imported_layer"]
    # No `.reposcope.yml` in the fixture, so no domain rule applies —
    # but the built-in layer taxonomy is still reported.
    assert payload["violated"] is False


def test_get_repo_map_reports_the_context_saving():
    payload = _payload(_call("get_repo_map", {"token_budget": 8000}))
    assert payload["files_included"] > 0
    assert payload["tokens"] > 0
    assert payload["reduction_pct"] > 0
    assert payload["text"], "the map has no text"
    assert "::" in payload["text"], "the map is not in the documented format"


# ── The transport rule ──────────────────────────────────────────────────────

def test_no_sse_transport_anywhere_in_the_codebase():
    """
    Correction C1: SSE was deprecated by the MCP spec in revision
    2025-03-26, and the 2026-07-28 revision made the transport
    stateless. The server offers stdio and Streamable HTTP. It must not
    offer SSE, and the codebase must not mention it as an option.
    """
    backend = Path(__file__).resolve().parent.parent
    offenders: list[str] = []

    for path in backend.rglob("*.py"):
        if "tests" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue

        # The AST is used rather than a text search, because a DOCSTRING
        # that explains why SSE is not used is exactly the comment this
        # codebase should have — and a text search would flag it. Only a
        # real `transport="sse"` argument is a defect.
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "transport":
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and value.value == "sse":
                    offenders.append(f"{path.name}:{node.lineno}: transport='sse'")

    assert not offenders, (
        "the SSE transport is still wired up somewhere:\n  "
        + "\n  ".join(offenders)
    )


def test_the_server_offers_stdio_and_streamable_http():
    from mcp_server.server import main

    import inspect

    source = inspect.getsource(main)
    assert 'transport="stdio"' in source
    assert 'transport="streamable-http"' in source


# ── The real stdio transport ────────────────────────────────────────────────

def _stdio_exchange(messages: list[dict], root: Path) -> list[dict]:
    """
    Drive the server over a REAL stdio pipe.

    The in-memory session above tests the tools. This tests the
    TRANSPORT — which is the thing that breaks when the SDK changes, and
    the thing a client like Claude Desktop or Cursor actually uses.

    The exchange is deliberately raw JSON-RPC: the server is started as
    a subprocess, the messages are written to its stdin, and its stdout
    is read back. Nothing here shares a process with the server.
    """
    import subprocess
    import sys

    backend = Path(__file__).resolve().parent.parent
    payload = "".join(json.dumps(message) + "\n" for message in messages)

    completed = subprocess.run(
        [sys.executable, "-m", "mcp_server.server", "--root", str(root)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(backend),
    )

    responses: list[dict] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            responses.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return responses


def test_the_stdio_transport_completes_the_handshake():
    """`mcp.run(transport="stdio")` must complete the initialize handshake."""
    root = FIXTURES_DIR / "multilang"
    responses = _stdio_exchange(
        [{
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "reposcope-test", "version": "1"},
            },
        }],
        root,
    )

    assert responses, "the server said nothing over stdio"
    handshake = next((r for r in responses if r.get("id") == 1), None)
    assert handshake is not None, f"no initialize response: {responses}"
    assert "error" not in handshake, handshake["error"]

    result = handshake["result"]
    assert result["serverInfo"]["name"] == "RepoScope"
    assert result["protocolVersion"]
    # The instructions carry the resolved root, so an agent can cite real
    # paths.
    assert str(root.resolve()) in result.get("instructions", "")


def test_the_stdio_transport_lists_the_tools():
    root = FIXTURES_DIR / "multilang"
    responses = _stdio_exchange(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "reposcope-test", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ],
        root,
    )

    listing = next((r for r in responses if r.get("id") == 2), None)
    assert listing is not None, f"no tools/list response: {responses}"
    assert "error" not in listing, listing["error"]

    tools = listing["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == EXPECTED_TOOLS, f"unexpected tool set: {sorted(names)}"

    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["description"].strip()


def test_the_stdio_transport_answers_a_tool_call():
    root = FIXTURES_DIR / "multilang"
    responses = _stdio_exchange(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "reposcope-test", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "calculate_blast_radius",
                    "arguments": {"target_file": "helpers.py"},
                },
            },
        ],
        root,
    )

    call = next((r for r in responses if r.get("id") == 2), None)
    assert call is not None, f"no tool call response: {responses}"
    assert "error" not in call, call["error"]

    # A tool that returns a bare `dict` has no output schema, so the
    # result arrives as a JSON text block rather than as
    # `structuredContent`. Both are valid MCP; the text block is the
    # portable one.
    result = call["result"]
    payload = result.get("structuredContent", {}).get("result")
    if payload is None:
        text = next(
            block["text"] for block in result["content"]
            if block.get("type") == "text"
        )
        payload = json.loads(text)

    assert payload["available"] is True
    labels = {n["label"] for n in payload["direct_impacts"]}
    assert "app.py" in labels
