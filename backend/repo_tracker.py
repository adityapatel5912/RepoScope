"""
repo_tracker.py
Manages local state for the currently-loaded repo.
Persists to data/repo_state.json so state survives restarts.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

STATE = Path(__file__).parent.parent / "data" / "repo_state.json"

_EMPTY_STATE: dict = {
    "repo": None,
    "loaded_at": None,
    "last_check": None,
    "known_commits": [],
    "known_prs": [],
    "known_issues": [],
    "known_releases": [],
}


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return dict(_EMPTY_STATE)


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def mark_checked(repo: str) -> dict:
    s = load_state()
    s["repo"] = repo
    s["last_check"] = datetime.now(timezone.utc).isoformat()
    save_state(s)
    return s


def classify(commit: dict) -> str:
    """Classify a commit by its message prefix."""
    msg = commit.get("commit", {}).get("message", "").lower()
    if "breaking" in msg or "!:" in msg:
        return "breaking"
    for t in ("feat", "fix", "chore", "docs", "refactor"):
        if msg.startswith(f"{t}:") or msg.startswith(f"{t}("):
            return t
    if "bump" in msg:
        return "deps"
    return "other"


def diff_changes(gh: dict, state: dict) -> dict:
    """Return only the commits/items not already in local state."""
    known = set(state.get("known_commits", []))
    new_commits = [c for c in gh.get("commits", []) if c["sha"] not in known]
    for c in new_commits:
        c["_type"] = classify(c)
    return {
        "new_commits": new_commits,
        "pulls":       gh.get("pulls", []),
        "issues":      gh.get("issues", []),
        "releases":    gh.get("releases", []),
    }
