"""
mcp_client.py
Thin wrappers around:
  - codebase-memory-mcp  (local binary, for code graph queries)
  - GitHub REST API v3   (for repo metadata)

GitHub token is read from GITHUB_PAT (matches .env.example).
The token is never logged and never echoed in error messages.
"""
import json
import logging
import os

from key_rotator import GITHUB_ROTATOR
import subprocess

import httpx

log = logging.getLogger("reposcope.mcp")


async def query_codebase_graph(question: str) -> dict:
    """Call the local codebase-memory-mcp binary and return its JSON output.
    Fails soft (returns {}) if the binary is missing or times out."""
    binary = os.getenv("CODEBASE_MEMORY_PATH", "codebase-memory-mcp")
    try:
        r = subprocess.run(
            [binary, "query", question],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except FileNotFoundError:
        log.info("codebase-memory-mcp binary not found at %r — skipping", binary)
        return {}
    except subprocess.TimeoutExpired:
        log.warning("codebase-memory-mcp timed out after 15s — skipping")
        return {}
    except Exception as exc:
        log.warning("codebase-memory-mcp failed: %s — skipping", exc)
        return {}


async def query_github(
    owner: str,
    repo: str,
    since: str | None = None,
    user_token: str | None = None,
) -> dict:
    """Fetch commits, pulls, issues, and releases from GitHub."""
    # Prefer the user's BYOK token, fall back to env GITHUB_PAT
    token = user_token or GITHUB_ROTATOR.next_key()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    base = f"https://api.github.com/repos/{owner}/{repo}"

    async with httpx.AsyncClient(timeout=15, headers=headers) as c:
        commits_params = {"since": since} if since else {}
        issues_params  = {"since": since} if since else {}

        commits  = (await c.get(f"{base}/commits",  params=commits_params)).json()
        pulls    = (await c.get(f"{base}/pulls",    params={"state": "all", "sort": "updated"})).json()
        issues   = (await c.get(f"{base}/issues",   params=issues_params)).json()
        releases = (await c.get(f"{base}/releases")).json()

    return {
        "commits":  commits,
        "pulls":    pulls,
        "issues":   issues,
        "releases": releases,
    }
