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

log = logging.getLogger("reposcope.repo_loader")

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
    save_state(s)

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
