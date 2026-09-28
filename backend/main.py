"""
main.py
FastAPI application — all HTTP and SSE endpoints for RepoScope.
SSE events use StreamingResponse so every chunk is a single-line
JSON payload; no sse-starlette dependency needed on the streaming path.
"""
import asyncio
import json
import logging
import logging.handlers
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from ai_byok import PROVIDERS, resolve_provider
from byok_manager import get_user_token, set_user_token
from graph_builder import build_graph_from_repo
from graph_utils import build_adjacency, find_node_by_label
from impact_analyzer import compute_blast_radius, generate_impact_narrative
from key_rotator import OPENROUTER_ROTATOR, GROQ_ROTATOR, NVIDIA_ROTATOR, GITHUB_ROTATOR
from mcp_client import query_github
from orchestrator import build_context
from onboarding import build_onboarding
from pr_impact import build_pr_impact, fetch_pr, post_pr_comment
from repo_loader import load_repo
from repo_tracker import diff_changes, load_state, mark_checked
from runtime_config import ask_llm
from security_scanner import (
    check_dependency_cves, detect_breaking_commit, scan_pr_patch, scan_repo_files,
)
from tour_generator import build_tour
from tts_service import synthesize

START_TIME = time.time()

# ── Logging setup ──────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=5_000_000, backupCount=3
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[_handler, logging.StreamHandler()],
)
log = logging.getLogger("reposcope")

app = FastAPI(title="RepoScope API")

# Allowed origins: localhost for dev, plus any Vercel deployment (preview + prod).
# Set ALLOWED_ORIGINS env var on Render to override (comma-separated list).
_default_origins = [
    "http://localhost:5173",
    "http://localhost:4173",
]
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
if _env_origins:
    _default_origins += [o.strip() for o in _env_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


# ── Security headers, request IDs, and access logging on every response ─────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    t0 = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-Id"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    # Access log: method, path, status, duration
    log.info("%s %s -> %s (%.1fms) [%s]",
             request.method, request.url.path, response.status_code, duration_ms, req_id)
    return response


# ── Global exception handler: JSON errors, never stack traces ───────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception(
        "Unhandled error on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check backend logs."},
    )


SYSTEM_PROMPT = (
    "You are RepoScope. You answer questions about the loaded repository "
    "using the code graph and the file context provided.\n\n"
    "When the user asks about setup, installation, running, or getting "
    "started:\n\n"
    "1. First check for an explicit Setup, Install, Quickstart, Getting "
    "Started, or Usage section in the README context. If one exists, use "
    "it. Cite the section name.\n"
    "2. If no explicit section exists, look at build.sh, render.yaml, "
    "vercel.json, package.json scripts, and requirements.txt. Extract "
    "commands from those files.\n"
    "3. If neither exists, synthesize the setup steps from the detected "
    "stack. For example, if you see backend/requirements.txt and "
    "frontend/package.json, produce:\n"
    "     Backend:\n"
    "       cd backend\n"
    "       pip install -r requirements.txt\n"
    "       uvicorn main:app --reload --port 8000\n"
    "     Frontend (new terminal):\n"
    "       cd frontend\n"
    "       npm install\n"
    "       npm run dev\n"
    "4. Never say \"not in the provided excerpt.\" Never give up when the "
    "answer can be inferred from the repo structure.\n"
    "5. Always cite the file or section that supports each step — e.g. "
    "`[README Quick Start]`, `[build.sh]`, `[render.yaml startCommand]`, "
    "`[package.json scripts.dev]` — or, for a synthesized step, the source "
    "of the inference: `[inferred from backend/requirements.txt + "
    "frontend/package.json]`.\n"
    "6. For setup/install questions, answer with the steps only — no "
    "markdown tables, no key-files listing.\n\n"
    "For every other question, follow the existing rules: cite files, "
    "functions, and commits. Do not hallucinate. If the answer is not in "
    "the context, say so clearly. Never fabricate paths, SHAs, or PR "
    "numbers.\n\n"
    "RESPONSE FORMAT (strict):\n"
    "1. Open with ONE bold one-line summary of the answer.\n"
    "2. Organize the body with '##' section headings (2-4 sections max).\n"
    "3. Present files/functions in a markdown table with columns: "
    "`Path | Role | Key symbols`.\n"
    "4. Cite code locations as `path/to/file.py:LINE` in backticks.\n"
    "5. Close with a '### Next steps' section listing 2-3 actionable "
    "bullets for the developer.\n"
    "6. No greetings, no filler phrases, no self-references "
    "(never start with 'Sure' or 'Great question').\n"
    "7. Keep the whole answer under 350 words.\n\n"
    "In TRACKING mode, report changes grouped by type in a table and flag "
    "breaking changes with a warning line first. "
    "In INCIDENT mode, report blast radius first, then ranked hypotheses "
    "ordered by likelihood with evidence for each."
)


# ── Request / Response models ──────────────────────────────────────────────

class LoadReq(BaseModel):
    url: str

class Query(BaseModel):
    mode: str
    message: str
    repo: str | None = None

class BYOKReq(BaseModel):
    token: str

class CommitReq(BaseModel):
    message: str
    files: list[str] = []

class TourReq(BaseModel):
    topic: str

class ImpactReq(BaseModel):
    target: str
    max_depth: int = 3

class PRImpactReq(BaseModel):
    repo_url: str
    pr_number: int
    github_token: str | None = None
    post_comment: bool = False

class OnboardReq(BaseModel):
    repo_url: str | None = None

class TTSReq(BaseModel):
    text: str

class ScanReq(BaseModel):
    repo_url: str | None = None
    pr_number: int | None = None


# ── SSE helpers ────────────────────────────────────────────────────────────

def _sse(event: str, data: object) -> str:
    """Format a single SSE frame as a plain string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Setup-relevant README sections are preferred over raw truncation; fall
# back to the first 20000 chars when nothing matches.
_README_LIMIT = 20000
_SETUP_SECTION_RE = re.compile(
    r"setup|install|quick\s?start|getting\s+started|run|requirements|usage|"
    r"prerequisites?|local(development|ly)?|environment|configuration",
    re.I,
)


def _extract_readme_sections(readme: str) -> str:
    """Prefer markdown sections about setup/running; else first 20000 chars."""
    if len(readme) <= _README_LIMIT:
        return readme
    # Split on ATX headings of levels 1-3, keeping the body under each.
    sections = re.split(r"\n#{1,3}\s", readme)
    hits = [s for s in sections if _SETUP_SECTION_RE.search(s)]
    if hits:
        # Re-attach a heading marker so the model can cite section names.
        joined = "\n\n".join(f"## {s.strip()}" for s in hits if s.strip())
        if joined:
            return joined[:_README_LIMIT]
    return readme[:_README_LIMIT]


def _build_user_prompt(message: str, ctx: dict) -> str:
    parts = [f"USER QUESTION: {message}"]
    if ctx.get("readme"):
        readme_text = _extract_readme_sections(ctx["readme"])
        parts.append(f"\n--- README (setup-relevant sections) ---\n{readme_text}")
    nodes = ctx.get("nodes", [])
    if nodes:
        files = [n for n in nodes if n.get("type") == "file"]
        symbols = [n for n in nodes if n.get("type") != "file"]
        # Full file tree (compact) so the LLM can reference any file,
        # plus a JSON sample of functions/classes with line numbers
        file_lines = [f"- {n.get('label', n.get('id', '?'))}" for n in files[:250]]
        parts.append(
            f"\n--- FILE TREE ({len(files)} files) ---\n" + "\n".join(file_lines)
        )
        parts.append(
            f"\n--- CODE SYMBOLS SAMPLE ({len(symbols)} total functions/classes) ---\n"
            + json.dumps(symbols[:60], indent=2)[:3500]
        )
    # Setup-intent questions: raw setup files as labeled blocks
    for label, content in (ctx.get("setup_files") or {}).items():
        parts.append(f"\n[{label}]\n{content}")
    # Tracking mode: recent GitHub activity so the LLM can summarize changes
    tracking = ctx.get("tracking") or {}
    if any(tracking.get(k) for k in ("commits", "pulls", "issues", "releases")):
        def _brief(items, keys):
            out = []
            for it in (items or [])[:10]:
                if not isinstance(it, dict):
                    continue
                out.append({k: it.get(k) for k in keys if it.get(k) is not None})
            return out
        payload = {
            "commits": _brief(tracking.get("commits"),
                              ["sha", "message", "date", "author"]),
            "pulls": _brief(tracking.get("pulls"),
                            ["number", "title", "state", "user", "merged_at"]),
            "issues": _brief(tracking.get("issues"),
                             ["number", "title", "state", "user"]),
            "releases": _brief(tracking.get("releases"),
                               ["tag_name", "name", "published_at"]),
        }
        parts.append(
            "\n--- GITHUB TRACKING (latest activity) ---\n"
            + json.dumps(payload, indent=1)[:6000]
        )
    return "\n".join(parts)


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Root redirect — sends browsers straight to the health page."""
    return RedirectResponse(url="/api/health")


@app.get("/health")
async def health_simple():
    """Minimal liveness probe for platform health checks."""
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    """Full health snapshot: uptime, memory, configured key counts."""
    uptime = int(time.time() - START_TIME)
    try:
        import psutil
        memory_mb = round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        memory_mb = 0.0
    return {
        "status": "healthy",
        "service": "reposcope-api",
        "version": "1.0.0",
        "uptime_seconds": uptime,
        "uptime_human": f"{uptime // 3600}h {(uptime % 3600) // 60}m",
        "memory_mb": memory_mb,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "checks": {
            "openrouter_keys": OPENROUTER_ROTATOR.count(),
            "groq_keys": GROQ_ROTATOR.count(),
            "nvidia_keys": NVIDIA_ROTATOR.count(),
            "github_keys": GITHUB_ROTATOR.count(),
        },
    }


@app.post("/api/repo/load")
async def repo_load(req: LoadReq, x_session_id: str = Header(None)):
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] repo/load url=%s", req_id, req.url)
    try:
        user_token = get_user_token(x_session_id) if x_session_id else None
        info = load_repo(req.url, user_token)
        mark_checked(f"{info['owner']}/{info['repo']}")
        log.info("[%s] repo/load OK files=%s nodes=%s", req_id,
                 info.get("file_count"), info.get("node_count"))
        return {"ok": True, **info}
    except Exception as e:
        log.error("[%s] repo/load FAILED: %s", req_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/repo/status")
async def repo_status():
    return load_state()


@app.get("/api/repo/check")
async def repo_check(x_session_id: str = Header(None)):
    s = load_state()
    if not s.get("repo"):
        raise HTTPException(status_code=400, detail="No repo loaded")
    owner, name = s["repo"].split("/", 1)
    user_token = get_user_token(x_session_id) if x_session_id else None
    gh = await query_github(owner, name, s.get("last_check"), user_token)
    diff = diff_changes(gh, s)
    mark_checked(s["repo"])
    return diff


@app.get("/api/repo/graph")
async def repo_graph():
    from orchestrator import get_cached_graph
    graph = get_cached_graph()
    # If cache is empty (e.g. first load before any chat), build it now
    if not graph.get("nodes"):
        state = load_state()
        local_path = state.get("local_path")
        if local_path:
            built = await asyncio.to_thread(build_graph_from_repo, local_path)
            from orchestrator import _graph_cache
            _graph_cache.update(built)
            return built
    return graph


# ── Demo repositories (one-click examples) ───────────────────────────────────
DEMO_REPOS = {
    "verdict": {
        "name": "Verdict",
        "url": "https://github.com/adityapatel5912/Verdict",
        "description": "Decision stress-test lab — full-stack Python + React",
    },
    "studyrot": {
        "name": "StudyRot",
        "url": "https://github.com/adityapatel5912/StudyRot",
        "description": "Study rotation scheduler",
    },
}


@app.get("/api/repo/demos")
async def list_demos():
    return DEMO_REPOS


@app.post("/api/repo/load-demo/{demo_id}")
async def load_demo(demo_id: str, x_session_id: str = Header(None)):
    if demo_id not in DEMO_REPOS:
        raise HTTPException(404, "Demo not found")
    demo = DEMO_REPOS[demo_id]
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] repo/load-demo id=%s url=%s", req_id, demo_id, demo["url"])
    try:
        user_token = get_user_token(x_session_id) if x_session_id else None
        info = load_repo(demo["url"], user_token)
        mark_checked(f"{info['owner']}/{info['repo']}")
        return {"ok": True, **info}
    except Exception as e:
        log.error("[%s] repo/load-demo FAILED: %s", req_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to load demo repo: {e}")


@app.post("/api/byok/set")
async def byok_set(req: BYOKReq, x_session_id: str = Header(None)):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")
    set_user_token(x_session_id, req.token)
    return {"ok": True}


@app.post("/api/repo/commit")
async def repo_commit(req: CommitReq, x_session_id: str = Header(None)):
    token = get_user_token(x_session_id) if x_session_id else None
    if not token:
        raise HTTPException(
            status_code=401,
            detail="BYOK GitHub PAT required to commit. Set it in the BYOK panel.",
        )
    return {
        "ok": True,
        "message": "Commit simulated (BYOK active)",
        "commit_message": req.message,
        "files": req.files,
    }


@app.get("/api/repo/file")
async def repo_file(path: str):
    """Serve a single file from the loaded repo (FileTree downloads).

    Rejects absolute paths and any path that escapes the repo root.
    """
    rel = (path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("~") or ":" in rel.split("/")[0]:
        raise HTTPException(400, "Invalid file path")
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        raise HTTPException(400, "No repo loaded. Load a repo first.")

    repo_root = Path(local_path).resolve()
    target = (repo_root / rel).resolve()
    if not target.is_relative_to(repo_root):
        log.warning("Blocked path traversal attempt: %s", path)
        raise HTTPException(403, "Path escapes the repository root")
    if not target.is_file():
        raise HTTPException(404, f"File not found: {rel}")

    return FileResponse(target, filename=target.name)


REVERSE_SYSTEM_PROMPT = (
    "You reverse-engineer an agent-ready build prompt from a repository.\n"
    "Rules (strict):\n"
    "1. Write in plain English, second person, starting with 'Build me a...'.\n"
    "2. Include: purpose, stack, architecture, key features, data flow, UI feel.\n"
    "3. EXCLUDE implementation trivia, exact file names, and any code.\n"
    "4. Keep it under 400 words.\n"
    "5. End with the exact sentence: Make it feel fast and polished.\n"
    "6. Output ONLY the prompt text — no preamble, no markdown fences."
)


@app.get("/api/ai/providers")
async def list_ai_providers():
    """List available AI providers and server-configured key status."""
    return {
        "providers": PROVIDERS,
        "server_keys": {
            "groq": bool(os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEYS")),
            "nvidia": bool(os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_API_KEYS")),
        },
    }


SCAFFOLD_SYSTEM_PROMPT = (
    "You generate a minimal starter scaffold for a repository, CodeCrafters "
    "style — guide the reader to build it themselves, do NOT clone the app.\n"
    "Rules (strict):\n"
    "1. Output ONLY one JSON object — no markdown fences, no commentary.\n"
    "2. Shape: {\"project_type\": string, \"file_tree\": [\"path\", ...], "
    "\"files\": [{\"path\": string, \"content\": string, \"purpose\": string}]}\n"
    "3. 6-12 files max. Each file is runnable boilerplate with TODO comments, "
    "under 50 lines. Never reproduce the original codebase's code.\n"
    "4. file_tree lists every scaffold path (same strings as files[].path).\n"
    "5. Include a README.md stub with 'Stage 1 / Stage 2 / Stage 3' build "
    "steps so a developer can rebuild the project incrementally.\n"
    "6. purpose is one sentence explaining why the file exists."
)


def _extract_json_object(text: str) -> dict:
    """Pull the first JSON object out of an LLM reply (fence-tolerant)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    return json.loads(cleaned[start : end + 1])


def _validate_scaffold(data: dict) -> dict:
    """Validate + sanitize the scaffold JSON. Raises ValueError when unusable."""
    if not isinstance(data, dict):
        raise ValueError("scaffold is not an object")
    project_type = str(data.get("project_type") or "unknown")
    raw_tree = data.get("file_tree") or []
    raw_files = data.get("files") or []
    if not isinstance(raw_tree, list) or not isinstance(raw_files, list) or not raw_files:
        raise ValueError("scaffold missing file_tree or files")

    files: list[dict] = []
    seen: set[str] = set()
    for f in raw_files[:15]:
        if not isinstance(f, dict):
            continue
        path = str(f.get("path") or "").strip().replace("\\", "/").lstrip("/")
        if (
            not path
            or path.startswith("~")
            or ".." in path.split("/")
            or ":" in path.split("/")[0]
            or path in seen
        ):
            continue
        seen.add(path)
        # Safety cap: a runaway model answer never bloats the payload
        content_lines = str(f.get("content") or "").splitlines()
        files.append({
            "path": path,
            "content": "\n".join(content_lines[:80]),
            "purpose": str(f.get("purpose") or "").strip(),
        })
    if not files:
        raise ValueError("scaffold has no usable files")
    tree = [str(p).strip() for p in raw_tree if str(p).strip()]
    return {"project_type": project_type, "file_tree": tree, "files": files}


_ENTRY_FILE_RE = re.compile(
    r"(^|/)(main|app|server|wsgi|asgi|manage|index|__main__)\.(py|tsx?|jsx?)$"
)


def _shallow_tree(local_path: str, depth: int = 1) -> list[str]:
    """Depth-limited listing of the repo root (dirs + files)."""
    root = Path(local_path)
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    entries: list[str] = []
    try:
        for p in sorted(root.iterdir(), key=lambda x: x.name):
            if p.name in skip:
                continue
            entries.append(f"{p.name}/" if p.is_dir() else p.name)
            if len(entries) >= 60:
                break
    except OSError:
        pass
    return entries


def _entry_file_blocks(graph: dict, local_path: str, max_files: int = 2) -> tuple[list[str], list[dict]]:
    """First 100 lines of up to `max_files` entry files (never the whole repo)."""
    root = Path(local_path)
    candidates = [
        n.get("label") for n in graph.get("nodes", [])
        if n.get("type") == "file" and _ENTRY_FILE_RE.search(n.get("label", ""))
    ]
    # Order by connectivity so the most-imported entry file comes first
    if candidates:
        _, reverse = build_adjacency(graph)
        candidates = sorted(set(candidates),
                            key=lambda c: -len(reverse.get(f"file:{c}", [])))
    blocks: list[dict] = []
    used: list[str] = []
    for rel in candidates[:max_files]:
        try:
            lines = (root / rel).read_text(errors="ignore").splitlines()[:100]
        except OSError:
            continue
        if lines:
            blocks.append({"path": rel, "preview": "\n".join(lines)})
            used.append(rel)
    return used, blocks


@app.post("/api/repo/reverse-prompt")
async def reverse_prompt(
    x_ai_provider: Optional[str] = Header(None),
    x_ai_key: Optional[str] = Header(None),
    x_ai_model: Optional[str] = Header(None),
    x_ai_base_url: Optional[str] = Header(None),
):
    """Generate a single agent-ready prompt that would rebuild this repo."""
    req_id = str(uuid.uuid4())[:8]
    provider = resolve_provider(x_ai_provider, x_ai_key, x_ai_model, x_ai_base_url)
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        raise HTTPException(400, "No repo loaded. Load a repo first.")
    try:
        graph = await asyncio.to_thread(build_graph_from_repo, local_path)
        files = sorted({
            n.get("label", "")
            for n in graph.get("nodes", [])
            if n.get("type") == "file" and n.get("label")
        })
        readme = state.get("readme", "")[:2500]
        user_prompt = (
            "Repository to reverse-engineer:\n\n"
            f"SUMMARY: {graph.get('summary', 'no summary')}\n\n"
            f"FILES ({len(files)}):\n" + "\n".join(files[:200]) + "\n\n"
            f"README (excerpt):\n{readme}"
        )
        text = await asyncio.to_thread(ask_llm, REVERSE_SYSTEM_PROMPT, user_prompt, "", provider)
        # Strip any markdown fences the model may have added
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()
        if not cleaned:
            raise HTTPException(502, "Model returned an empty build prompt")
        log.info("[%s] reverse-prompt OK %d chars from %d files", req_id, len(cleaned), len(files))
        return {"prompt": cleaned}
    except HTTPException:
        raise
    except Exception as e:
        log.error("[%s] reverse-prompt FAILED: %s", req_id, e)
        raise HTTPException(500, "Failed to generate build prompt. Is an LLM key configured?")


@app.post("/api/scaffold")
async def scaffold(
    x_ai_provider: Optional[str] = Header(None),
    x_ai_key: Optional[str] = Header(None),
    x_ai_model: Optional[str] = Header(None),
    x_ai_base_url: Optional[str] = Header(None),
):
    """Generate a CodeCrafters-style starter scaffold from the loaded repo.

    Context sent to the LLM is deliberately shallow: README excerpt (4000
    chars) + depth-1 file tree + graph layers/top nodes + first 100 lines of
    at most 2 entry files. The full codebase is never sent.
    """
    req_id = str(uuid.uuid4())[:8]
    provider = resolve_provider(x_ai_provider, x_ai_key, x_ai_model, x_ai_base_url)
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        raise HTTPException(400, "No repo loaded. Load a repo first.")
    try:
        graph = await asyncio.to_thread(build_graph_from_repo, local_path)

        # Connectivity ranking — same score the graph pyramid uses
        # (incoming*2 + outgoing) — Row 1 "most-imported" nodes.
        forward, reverse = build_adjacency(graph)
        file_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "file"]

        def _score(n: dict) -> int:
            return len(reverse.get(n["id"], [])) * 2 + len(forward.get(n["id"], []))

        ranked = sorted(file_nodes, key=_score, reverse=True)
        top_nodes = [n.get("label", "") for n in ranked[:8] if n.get("label")]
        layers = {
            f"rank_{i + 1}": [n.get("label", "") for n in ranked[i::6][:6]]
            for i in range(2)
        }

        readme = (state.get("readme") or "")[:4000]
        depth1 = _shallow_tree(local_path)
        entry_files, entry_blocks = await asyncio.to_thread(
            _entry_file_blocks, graph, local_path
        )

        parts = [
            f"PROJECT TYPE HINT (from summary): {graph.get('summary', 'unknown')}",
            f"\n--- README (first 4000 chars) ---\n{readme or '(no README)'}",
            f"\n--- FILE TREE (depth 1) ---\n" + "\n".join(depth1),
            f"\n--- TOP NODES (most-imported, Row 1) ---\n" + "\n".join(top_nodes),
            f"\n--- GRAPH LAYERS (sample) ---\n" + json.dumps(layers, indent=1),
        ]
        for blk in entry_blocks:
            parts.append(
                f"\n--- ENTRY FILE {blk['path']} (first 100 lines) ---\n{blk['preview']}"
            )
        user_prompt = "\n".join(parts)

        raw = await asyncio.to_thread(
            ask_llm, SCAFFOLD_SYSTEM_PROMPT, user_prompt, "", provider, 4096
        )
        scaffold = _validate_scaffold(_extract_json_object(raw))
        scaffold["entry_files"] = entry_files
        scaffold["top_nodes"] = top_nodes
        scaffold["ok"] = True
        log.info("[%s] scaffold OK type=%s files=%d", req_id,
                 scaffold["project_type"], len(scaffold["files"]))
        return scaffold
    except HTTPException:
        raise
    except ValueError as e:
        log.error("[%s] scaffold INVALID: %s", req_id, e)
        raise HTTPException(502, f"Model returned an invalid scaffold ({e}). Try again.")
    except Exception as e:
        log.error("[%s] scaffold FAILED: %s", req_id, e)
        raise HTTPException(500, "Failed to generate scaffold. Is an LLM key configured?")


@app.post("/api/tour/generate")
async def tour_generate(
    req: TourReq,
    x_ai_provider: Optional[str] = Header(None),
    x_ai_key: Optional[str] = Header(None),
    x_ai_model: Optional[str] = Header(None),
    x_ai_base_url: Optional[str] = Header(None),
):
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] tour/generate topic=%s", req_id, req.topic)
    provider = resolve_provider(x_ai_provider, x_ai_key, x_ai_model, x_ai_base_url)
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        raise HTTPException(400, "No repo loaded. Load a repo first.")
    try:
        # Offload the (sync) graph build + LLM calls so the event loop stays free
        graph = await asyncio.to_thread(build_graph_from_repo, local_path)
        tour = await asyncio.to_thread(build_tour, graph, req.topic, 12, provider)
    except HTTPException:
        raise
    except Exception as e:
        log.error("[%s] tour/generate FAILED: %s", req_id, e)
        raise HTTPException(500, str(e))
    if "error" in tour:
        raise HTTPException(404, tour["error"])
    log.info("[%s] tour/generate OK steps=%s", req_id, tour.get("total_steps"))
    return tour


@app.post("/api/tts")
async def tts(
    req: TTSReq,
    x_ai_provider: Optional[str] = Header(None),
    x_ai_key: Optional[str] = Header(None),
    x_ai_model: Optional[str] = Header(None),
    x_ai_base_url: Optional[str] = Header(None),
):
    """Voice Code Tours — synthesize narration audio for a tour step.

    Tries OpenRouter audio models (fish-audio/s2.1-pro-free:free →
    deepgram/flux-tts:free) with the standard key rotation; the client falls
    back to browser speechSynthesis when this fails.
    """
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] tts chars=%d", req_id, len(req.text))
    provider = resolve_provider(x_ai_provider, x_ai_key, x_ai_model, x_ai_base_url)
    try:
        result = await synthesize(req.text, provider)
        result["ok"] = True
        return result
    except ValueError:
        raise HTTPException(400, "text is required")
    except Exception as e:
        log.warning("[%s] tts FAILED: %s", req_id, e)
        raise HTTPException(502, "TTS unavailable — the client will use browser speech")


@app.post("/api/impact/analyze")
async def impact_analyze(
    req: ImpactReq,
    x_ai_provider: Optional[str] = Header(None),
    x_ai_key: Optional[str] = Header(None),
    x_ai_model: Optional[str] = Header(None),
    x_ai_base_url: Optional[str] = Header(None),
):
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] impact/analyze target=%s depth=%s", req_id, req.target, req.max_depth)
    provider = resolve_provider(x_ai_provider, x_ai_key, x_ai_model, x_ai_base_url)
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        raise HTTPException(400, "No repo loaded. Load a repo first.")
    try:
        graph = await asyncio.to_thread(build_graph_from_repo, local_path)

        target = find_node_by_label(graph, req.target)
        if not target:
            raise HTTPException(404, f"No node found matching: {req.target}")

        impact = await asyncio.to_thread(
            compute_blast_radius, graph, target["id"], req.max_depth
        )
        impact["narrative"] = await asyncio.to_thread(generate_impact_narrative, impact, provider)
    except HTTPException:
        raise
    except Exception as e:
        log.error("[%s] impact/analyze FAILED: %s", req_id, e)
        raise HTTPException(500, str(e))
    log.info("[%s] impact/analyze OK risk=%s (%s/%s)", req_id,
             impact.get("risk_level"), impact.get("risk_score"),
             impact.get("total_impacted"))
    return impact


@app.post("/api/impact/pr")
async def impact_pr(
    req: PRImpactReq,
    x_session_id: str = Header(None),
):
    """PR Bot — blast-radius report for a pull request, rendered as a
    GitHub-ready markdown comment (risk score, affected files, suggested
    tests, mermaid impact graph).

    Token precedence: request body → session BYOK PAT → server GITHUB_TOKENS.
    """
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] impact/pr url=%s pr=%s", req_id, req.repo_url, req.pr_number)

    # Normalize the repo URL into owner/repo
    url = req.repo_url.strip().rstrip("/")
    url = re.sub(r"^https?://(www\.)?github\.com/", "", url)
    url = re.sub(r"\.git$", "", url)
    parts = [p for p in url.split("/") if p]
    if len(parts) < 2:
        raise HTTPException(400, "repo_url must be a GitHub URL or owner/repo")
    owner, repo = parts[-2], parts[-1]

    token = (req.github_token
             or (get_user_token(x_session_id) if x_session_id else None)
             or GITHUB_ROTATOR.next_key()
             or None)

    try:
        # Reuse the loaded clone when it matches; otherwise clone fresh.
        state = load_state()
        local_path = state.get("local_path")
        if not local_path or state.get("repo") != f"{owner}/{repo}":
            log.info("[%s] impact/pr cloning %s/%s", req_id, owner, repo)
            info = await asyncio.to_thread(
                load_repo, f"https://github.com/{owner}/{repo}", token
            )
            local_path = info["local_path"]

        graph = await asyncio.to_thread(build_graph_from_repo, local_path)
        meta, files = await fetch_pr(owner, repo, req.pr_number, token)
        result = build_pr_impact(graph, meta, files)

        if req.post_comment:
            await post_pr_comment(owner, repo, req.pr_number,
                                  result["comment"], token)
            result["comment_posted"] = True
            log.info("[%s] impact/pr comment posted to PR #%s", req_id, req.pr_number)

        result["ok"] = True
        log.info("[%s] impact/pr OK risk=%s files=%s", req_id,
                 result["risk_level"], result["files_analyzed"])
        return result
    except HTTPException:
        raise
    except RuntimeError as e:
        log.error("[%s] impact/pr FAILED: %s", req_id, e)
        raise HTTPException(404 if "not found" in str(e) else 502, str(e))
    except Exception as e:
        log.error("[%s] impact/pr FAILED: %s", req_id, e)
        raise HTTPException(500, "Failed to analyze PR impact. Check backend logs.")


@app.post("/api/onboard")
async def onboard(
    req: OnboardReq,
    x_ai_provider: Optional[str] = Header(None),
    x_ai_key: Optional[str] = Header(None),
    x_ai_model: Optional[str] = Header(None),
    x_ai_base_url: Optional[str] = Header(None),
):
    """Student Onboarding Mode — 3-level learning path (entry points → core →
    utils) ranked by the graph's connectivity score, with per-file
    explanations, 3 quizzes per level, and 3 Good First Issues mined from the
    low-traffic bottom rows (Rows 4-5)."""
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] onboard url=%s", req_id, req.repo_url)
    provider = resolve_provider(x_ai_provider, x_ai_key, x_ai_model, x_ai_base_url)
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        raise HTTPException(400, "No repo loaded. Load a repo first.")
    try:
        graph = await asyncio.to_thread(build_graph_from_repo, local_path)
        if not graph.get("nodes"):
            raise HTTPException(400, "Graph is empty — reload the repository.")
        payload = await asyncio.to_thread(build_onboarding, graph, provider)
        payload["repo"] = state.get("repo")
        log.info("[%s] onboard OK levels=%d gfis=%d", req_id,
                 len(payload["levels"]), len(payload["good_first_issues"]))
        return payload
    except HTTPException:
        raise
    except Exception as e:
        log.error("[%s] onboard FAILED: %s", req_id, e)
        raise HTTPException(500, "Failed to build the onboarding path. Check backend logs.")


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@app.post("/api/security/scan")
async def security_scan(
    req: ScanReq,
    x_session_id: str = Header(None),
):
    """Breaking Change + Secret Scan (Nord Security angle).

    Sources: the loaded clone (committed secrets, .env leaks, vulnerable
    dependency pins), optionally a PR's patches (breaking signature changes,
    major bumps, added secrets), and recent commit messages (BREAKING
    markers). Pure heuristics — no LLM, so scans are fast and deterministic.
    """
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] security/scan url=%s pr=%s", req_id, req.repo_url, req.pr_number)

    state = load_state()
    local_path = state.get("local_path")

    owner = repo = None
    if req.repo_url:
        url = req.repo_url.strip().rstrip("/")
        url = re.sub(r"^https?://(www\.)?github\.com/", "", url)
        url = re.sub(r"\.git$", "", url)
        parts = [p for p in url.split("/") if p]
        if len(parts) >= 2:
            owner, repo = parts[-2], parts[-1]
            if not local_path or state.get("repo") != f"{owner}/{repo}":
                token = get_user_token(x_session_id) if x_session_id else None
                info = await asyncio.to_thread(
                    load_repo, f"https://github.com/{owner}/{repo}",
                    token or GITHUB_ROTATOR.next_key() or None,
                )
                local_path = info["local_path"]
    elif state.get("repo"):
        owner, repo = state["repo"].split("/", 1)

    if not local_path:
        raise HTTPException(400, "No repo loaded. Load a repo first.")

    flags: list[dict] = []

    # 1. Clone scan: committed secrets, .env leaks, vulnerable pins
    flags.extend(await asyncio.to_thread(scan_repo_files, local_path))

    # 2. PR patch scan (optional): breaking sig changes, bumps, added secrets
    pr_scanned: int | None = None
    if req.pr_number and owner and repo:
        token = (get_user_token(x_session_id) if x_session_id else None) \
            or GITHUB_ROTATOR.next_key() or None
        try:
            _meta, pr_files = await fetch_pr(owner, repo, req.pr_number, token)
            flags.extend(scan_pr_patch(pr_files))
            pr_scanned = req.pr_number
        except Exception as e:
            log.warning("[%s] security/scan PR fetch failed: %s", req_id, e)

    # 3. Recent commit messages: conventional BREAKING markers
    commits_scanned = 0
    if owner and repo:
        token = (get_user_token(x_session_id) if x_session_id else None) \
            or GITHUB_ROTATOR.next_key() or None
        try:
            gh = await query_github(owner, repo, None, token)
            for c in (gh.get("commits") or [])[:20]:
                commits_scanned += 1
                flags.extend(detect_breaking_commit(
                    c.get("commit", {}).get("message", ""), c.get("sha", ""),
                ))
        except Exception as e:
            log.warning("[%s] security/scan commits fetch failed: %s", req_id, e)

    # Dedupe + sort by severity, then type
    seen: set[tuple] = set()
    unique: list[dict] = []
    for f in flags:
        key = (f["type"], f["severity"], f["file"], f["line"], f["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    unique.sort(key=lambda f: (_SEVERITY_ORDER.get(f["severity"], 9), f["type"], f["file"]))

    summary = {
        "SECRET": sum(1 for f in unique if f["type"] == "SECRET"),
        "BREAKING": sum(1 for f in unique if f["type"] == "BREAKING"),
        "CVE": sum(1 for f in unique if f["type"] == "CVE"),
        "critical": sum(1 for f in unique if f["severity"] == "critical"),
        "high": sum(1 for f in unique if f["severity"] == "high"),
    }

    log.info("[%s] security/scan OK flags=%d", req_id, len(unique))
    return {
        "ok": True,
        "repo": f"{owner}/{repo}" if owner and repo else state.get("repo"),
        "scanned": {"repo_files": True, "pr": pr_scanned, "commits": commits_scanned},
        "flags": unique[:100],
        "total_flags": len(unique),
        "summary": summary,
    }


@app.post("/api/chat/stream")
async def chat_stream(
    q: Query,
    request: Request,
    x_session_id: str = Header(None),
    x_ai_provider: Optional[str] = Header(None),
    x_ai_key: Optional[str] = Header(None),
    x_ai_model: Optional[str] = Header(None),
    x_ai_base_url: Optional[str] = Header(None),
):
    req_id = str(uuid.uuid4())[:8]
    log.info("[%s] chat/stream mode=%s repo=%s provider=%s", req_id, q.mode, q.repo, x_ai_provider or "default")
    provider = resolve_provider(x_ai_provider, x_ai_key, x_ai_model, x_ai_base_url)

    async def event_generator():
        try:
            # Build graph + README context
            ctx = await build_context(q.mode, q.message, q.repo, x_session_id)
            log.info("[%s] context built: %s nodes, %s edges",
                     req_id, len(ctx.get("nodes", [])), len(ctx.get("edges", [])))
            yield _sse("context", {
                "nodes": ctx.get("nodes", []),
                "edges": ctx.get("edges", []),
                "graph_summary": ctx.get("graph_summary", ""),
                "file_count": ctx.get("file_count", 0),
                "node_count": len(ctx.get("nodes", [])),
                "edge_count": len(ctx.get("edges", [])),
                "readme_length": len(ctx.get("readme", "")),
            })

            user_prompt = _build_user_prompt(q.message, ctx)
            answer = ask_llm(SYSTEM_PROMPT, user_prompt, provider=provider)
            log.info("[%s] LLM answered %d chars", req_id, len(answer))

            # Stream in small chunks (~4 words) for smooth UX, but preserve
            # line structure — markdown headings/tables/lists need newlines
            # to render, so never flatten the answer into one line.
            for line in answer.split("\n"):
                if await request.is_disconnected():
                    log.info("[%s] client disconnected", req_id)
                    break
                words = line.split(" ")
                for i in range(0, len(words), 4):
                    yield _sse("token", {"t": " ".join(words[i : i + 4]) + " "})
                    await asyncio.sleep(0.015)
                yield _sse("token", {"t": "\n"})

            if "tracking" in ctx:
                yield _sse("tracking", ctx["tracking"])

            yield _sse("done", {"ok": True, "req_id": req_id})
            log.info("[%s] stream complete", req_id)

        except Exception as exc:
            log.error("[%s] stream error: %s", req_id, exc, exc_info=True)
            yield _sse("error", {"message": str(exc)})
            yield _sse("done", {"ok": False})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Request-Id": req_id,
            "Content-Security-Policy": "default-src 'none'",
        },
    )
