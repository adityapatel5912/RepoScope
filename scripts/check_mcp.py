#!/usr/bin/env python
"""
check_mcp.py
Health-check the MCP servers RepoScope's tooling depends on.

    python scripts/check_mcp.py

Each server is launched exactly as the client config launches it, then sent
a real MCP `initialize` handshake over stdio. A server that starts but does
not answer the handshake is NOT working — and that is the failure mode
that shows up as "Error" in an MCP client.

Why this exists: a broad `Stop-Process` sweep over every `node.exe` kills
the MCP server processes the client spawned, and the client then shows them
as Error without respawning them. This script proves whether a server is
actually healthy, and prints the exact command to re-register it.

Exit code 0 when every configured server answers the handshake.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Mirrors the `mcp.servers` block of opencode.json.
SERVERS: dict[str, dict] = {
    "chrome-devtools": {
        "command": ["npx", "-y", "chrome-devtools-mcp@latest"],
        "env": {},
    },
    "playwright": {
        "command": ["npx", "-y", "@playwright/mcp@latest"],
        "env": {},
    },
    "tavily": {
        "command": ["npx", "-y", "tavily-mcp@latest"],
        "env": {"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
    },
}

HANDSHAKE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "reposcope-mcp-check", "version": "1.0.0"},
    },
}

TIMEOUT_SECONDS = 75


def resolve(command: list[str]) -> list[str] | None:
    """
    Resolve the executable, including the Windows batch-file case.

    On Windows `npx` is `npx.cmd`, and `subprocess.Popen` cannot launch a
    `.cmd` by its bare name — it must be resolved explicitly.
    """
    executable = command[0]
    found = shutil.which(executable)
    if not found and os.name == "nt":
        found = shutil.which(f"{executable}.cmd") or shutil.which(f"{executable}.bat")
    if not found:
        return None
    return [found, *command[1:]]


def check(name: str, spec: dict) -> tuple[bool, str]:
    """Start a server and wait for it to answer the initialize handshake."""
    env = dict(os.environ)
    env.update({k: v for k, v in spec.get("env", {}).items() if v})

    for key, value in spec.get("env", {}).items():
        if not value:
            return False, f"missing environment variable {key}"

    resolved = resolve(spec["command"])
    if resolved is None:
        return False, f"command not found: {spec['command'][0]}"

    try:
        process = subprocess.Popen(
            resolved,
            cwd=str(REPO_ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        return False, f"command not found: {resolved[0]}"

    result: dict[str, str] = {}

    def read_answer() -> None:
        try:
            for line in process.stdout:  # type: ignore[union-attr]
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get("id") == 1 and "result" in message:
                    info = message["result"].get("serverInfo", {})
                    result["server"] = (
                        f"{info.get('name', '?')} {info.get('version', '')}".strip()
                    )
                    return
        except Exception:  # noqa: BLE001
            return

    reader = threading.Thread(target=read_answer, daemon=True)
    reader.start()

    try:
        process.stdin.write(json.dumps(HANDSHAKE) + "\n")  # type: ignore[union-attr]
        process.stdin.flush()  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001
        return False, f"could not write the handshake: {exc}"

    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        if "server" in result:
            return True, result["server"]
        if process.poll() is not None and not result:
            return False, f"the process exited with code {process.returncode}"
        time.sleep(0.25)

    return False, f"no handshake within {TIMEOUT_SECONDS}s"


def main() -> int:
    print("RepoScope MCP health check")
    print(f"repository: {REPO_ROOT}\n")

    failures = 0
    for name, spec in SERVERS.items():
        print(f"  {name:<16} ", end="", flush=True)
        started = time.time()
        ok, detail = check(name, spec)
        elapsed = time.time() - started
        if ok:
            print(f"OK    {detail}  ({elapsed:.1f}s)")
        else:
            failures += 1
            print(f"FAIL  {detail}  ({elapsed:.1f}s)")

    if failures:
        print(f"\n{failures} of {len(SERVERS)} servers are not answering.")
        print("\nIf a client shows these as Error after a restart, the server")
        print("processes were killed. Restart the MCP client, or re-register")
        print("them by hand:")
        print()
        print('  claude mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest')
        print('  claude mcp add playwright -- npx -y @playwright/mcp@latest')
        print('  claude mcp add tavily --env TAVILY_API_KEY=$TAVILY_API_KEY '
              '-- npx -y tavily-mcp@latest')
        return 1

    print(f"\nAll {len(SERVERS)} MCP servers answer the initialize handshake.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
