"""
orchestrator.py
Combines code-graph context with live GitHub metadata, then hands the
merged context to ask_llm. Falls back to local graph_builder when
codebase-memory-mcp is unavailable.
"""
import json
import logging
import re
from pathlib import Path

from byok_manager import get_user_token
from graph_builder import build_graph_from_repo
from mcp_client import query_codebase_graph, query_github
from repo_tracker import load_state

log = logging.getLogger("reposcope.orchestrator")

# Module-level graph cache so /api/repo/graph can serve it without rebuild
_graph_cache: dict = {"nodes": [], "edges": [], "graph_summary": ""}

# Setup-intent detection: when a question mentions any of these words, extra
# setup files (build.sh, render.yaml, …) are added to the LLM context.
_SETUP_TRIGGER_RE = re.compile(
    r"\b(setup|install|installation|run|running|start|starting|quickstart|"
    r"getting\s+started|requirements|prerequisites|local|environment|"
    r"dependencies)\b",
    re.I,
)

# Setup hint files: label → candidate paths under the repo root. Missing
# files are skipped silently.
_SETUP_FILES: list[tuple[str, list[str]]] = [
    ("build.sh", ["build.sh"]),
    ("render.yaml", ["render.yaml"]),
    ("vercel.json", ["frontend/vercel.json", "vercel.json"]),
]
_MAX_BLOCK = 4000  # per-file cap so one huge file can't blow the prompt


def _is_setup_query(message: str) -> bool:
    return bool(message) and bool(_SETUP_TRIGGER_RE.search(message))


def _read_capped(path: Path, cap: int = _MAX_BLOCK) -> str:
    try:
        return path.read_text(errors="ignore")[:cap].strip()
    except OSError:
        return ""


def _collect_setup_files(local_path: str | None) -> dict[str, str]:
    """Read setup-hint files from the cloned repo. Missing → skipped."""
    if not local_path:
        return {}
    root = Path(local_path)
    blocks: dict[str, str] = {}

    for label, candidates in _SETUP_FILES:
        for cand in candidates:
            content = _read_capped(root / cand)
            if content:
                blocks[label] = content
                break

    # package.json — scripts + dependencies objects only (skip the lockfile
    # noise; parsed JSON, so a malformed file is skipped silently)
    pkg = root / "frontend" / "package.json"
    if not pkg.exists():
        pkg = root / "package.json"
    try:
        data = json.loads(pkg.read_text(errors="ignore"))
        if data.get("scripts"):
            blocks["package.json scripts"] = json.dumps(data["scripts"], indent=2)
        if data.get("dependencies"):
            blocks["package.json dependencies"] = json.dumps(
                data["dependencies"], indent=2
            )
    except Exception:
        pass

    # requirements.txt — first 20 lines
    reqs = root / "backend" / "requirements.txt"
    if not reqs.exists():
        reqs = root / "requirements.txt"
    try:
        lines = reqs.read_text(errors="ignore").splitlines()[:20]
        if lines:
            blocks["requirements.txt"] = "\n".join(lines).strip()
    except OSError:
        pass

    return blocks


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

    # Setup-intent questions get extra ground truth: build.sh, render.yaml,
    # vercel.json, package.json scripts/deps, requirements.txt.
    if _is_setup_query(message):
        ctx["setup_files"] = _collect_setup_files(local_path)
        log.info("Setup query detected — %d setup files attached",
                 len(ctx["setup_files"]))

    if mode == "tracking" and repo:
        owner, name = repo.split("/", 1)
        user_token = get_user_token(session_id) if session_id else None
        try:
            gh = await query_github(owner, name, state.get("last_check"), user_token)
            ctx["tracking"] = gh
        except Exception as exc:
            log.warning("GitHub tracking fetch failed: %s", exc)

    return ctx
