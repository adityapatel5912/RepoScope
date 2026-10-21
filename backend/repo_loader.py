"""
repo_loader.py
Shallow-clones a GitHub repo into a temp directory, reads the README,
counts files, and persists state for the rest of the session.
"""
import hashlib
import logging
import os

from key_rotator import GITHUB_ROTATOR
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from repo_tracker import load_state, save_state
from parse_cache import SKIP_DIRS

log = logging.getLogger("reposcope.repo_loader")


def clear_graph_cache() -> None:
    """
    Forget the cached graph.

    Imported lazily to avoid a circular import: orchestrator imports
    repo_loader, and repo_loader would otherwise import orchestrator.
    """
    try:
        from orchestrator import clear_graph_cache as _clear

        _clear()
    except Exception:  # noqa: BLE001 - the cache is an optimisation
        pass

# Use system temp dir for Windows compatibility
REPO_CACHE = Path(tempfile.gettempdir()) / "reposcope"


def _force_remove(path: Path) -> bool:
    """
    Recursive delete that survives Windows quirks:
    - git object files are read-only → chmod +w before unlinking
    - returns True only if the path is really gone
    """
    if not path.exists():
        return True

    def _onerror(func, target, exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except Exception:
            pass

    try:
        shutil.rmtree(path, onerror=_onerror)
    except Exception as exc:
        log.warning("rmtree failed for %s: %s", path, exc)
    return not path.exists()


def load_repo(url: str, user_token: str | None = None) -> dict:
    """Clone the repo, read README, count files, persist state."""
    # Normalize protocol-less input ("github.com/owner/repo")
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    REPO_CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(url.encode()).hexdigest()[:12]
    dest = REPO_CACHE / h

    # Remove any previous clone at this path. If the directory is locked
    # (open handles, antivirus scan), fall back to a fresh unique dir so
    # a stale clone never blocks loading.
    if not _force_remove(dest):
        log.warning("Old clone at %s is locked — using a fresh directory", dest)
        i = 2
        while dest.exists() and i < 50:
            dest = REPO_CACHE / f"{h}-{i}"
            i += 1

    # Inject PAT for private repos — never log the token
    clone_url = url
    token = user_token or GITHUB_ROTATOR.next_key()
    if token and "github.com" in url:
        clone_url = url.replace("https://", f"https://{token}@")

    log.info("Cloning %s into %s", url, dest)
    result = subprocess.run(
        ["git", "clone", "--depth=50", clone_url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Strip any token from error message before raising
        safe_err = result.stderr.replace(token or "", "***") if token else result.stderr
        raise RuntimeError(f"git clone failed: {safe_err}")

    # Read README
    readme = ""
    for name in ("README.md", "README.rst", "README.txt", "readme.md"):
        p = dest / name
        if p.exists():
            readme = p.read_text(errors="ignore")
            log.info("README found: %s (%d chars)", name, len(readme))
            break

    # Count files (skip .git)
    file_count = sum(
        1 for f in dest.rglob("*")
        if f.is_file() and ".git" not in f.parts
    )

    # Best-effort MCP index
    try:
        subprocess.run(
            [os.getenv("CODEBASE_MEMORY_PATH", "codebase-memory-mcp"), "index", str(dest)],
            capture_output=True,
            timeout=60,
        )
    except Exception:
        pass

    owner, name = _parse_github_url(url)

    # Persist state
    s = load_state()
    s["repo"] = f"{owner}/{name}"
    s["local_path"] = str(dest)
    s["readme"] = readme
    s["file_count"] = file_count
    # A repository cloned from GitHub is NOT local mode. The flag has to be
    # cleared explicitly: the state file persists between loads, so
    # without this a local repository loaded earlier would leave the UI
    # showing the LOCAL MODE badge over a GitHub clone — and the
    # live-update stream would stay open over a snapshot that never
    # changes.
    s["is_local"] = False
    save_state(s)

    # The active repository changed — the cached graph now describes a
    # different codebase.
    clear_graph_cache()
    _detach_stale_session(str(dest))

    log.info("Repo loaded: %s/%s  files=%d", owner, name, file_count)
    return {
        "local_path": str(dest),
        "owner": owner,
        "repo": name,
        "file_count": file_count,
        "readme_length": len(readme),
    }


def _parse_github_url(url: str) -> tuple[str, str]:
    parts = url.rstrip("/").replace(".git", "").split("/")
    return parts[-2], parts[-1]


def load_local_repo(path: str) -> dict:
    """
    Load a repository that is already on disk — no clone, no GitHub, no PAT.

    This is what makes local mode possible (Milestone 2.2, the `reposcope`
    CLI) and what makes the browser-QA harness hermetic: a QA run must not
    depend on the network, because a network failure looks like a product
    failure.

    Every downstream feature (graph, chat, impact analysis, onboarding, the
    PR bot) already reads `state["local_path"]`, so all of them light up
    without further change.

    Returns the same shape as `load_repo`.
    """
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"Not a directory: {root}")

    readme = ""
    for name in ("README.md", "README.rst", "README.txt", "readme.md"):
        candidate = root / name
        if candidate.exists():
            readme = candidate.read_text(errors="ignore")
            log.info("README found: %s (%d chars)", name, len(readme))
            break

    file_count = sum(
        1
        for f in root.rglob("*")
        if f.is_file() and not (SKIP_DIRS & set(f.relative_to(root).parts))
    )

    name = root.name or "local"
    state = load_state()
    state["repo"] = name
    state["owner"] = ""
    state["local_path"] = str(root)
    state["readme"] = readme
    state["file_count"] = file_count
    state["is_local"] = True
    save_state(state)

    # The active repository changed — the cached graph now describes a
    # different codebase.
    clear_graph_cache()
    _detach_stale_session(str(root))

    log.info("Local repo loaded: %s  files=%d", root, file_count)
    return {
        "local_path": str(root),
        "owner": "",
        "repo": name,
        "file_count": file_count,
        "readme_length": len(readme),
        "is_local": True,
    }


def _detach_stale_session(root: str) -> None:
    """
    Release a live session that points at a DIFFERENT repository.

    The live session owns the graph the app serves. If a second
    repository is loaded while a session is attached to the first, the
    app would keep serving the FIRST repository's graph — the same class
    of bug as the stale graph cache, but with the live index on top of
    it.
    """
    try:
        from watcher import session

        if session.root and session.root != root:
            session.detach()
    except Exception:  # noqa: BLE001 - the watcher is an optimisation
        pass
