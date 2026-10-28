"""
repo_tracker.py
Manages local state for the currently-loaded repo.
Persists to data/repo_state.json so state survives restarts.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE = Path(__file__).parent.parent / "data" / "repo_state.json"

if os.getenv("REPOSCOPE_QA") == "1":
    # A QA run must not touch the developer's real state.
    #
    # It used to: the QA harness loaded fixture repositories into
    # `data/repo_state.json`, overwriting whatever the developer had
    # loaded — and, worse, the state said `is_local: true` with the
    # developer's own repository, so the QA backend RESUMED that
    # session at start-up and answered questions about a codebase the
    # journeys knew nothing about.
    STATE = Path(tempfile.gettempdir()) / "reposcope-qa" / "repo_state.json"

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


def classify_incident_event(event_type: str, details: dict) -> dict:
    """Classifies an incident event and computes severity and triage suggestion."""
    ev = event_type.lower()
    if "breaking" in ev or "api_break" in ev:
        return {
            "category": "breaking_change",
            "severity": "high",
            "triage": "Verify client consumer contracts and run API integration tests.",
        }
    elif "security" in ev or "vulnerability" in ev or "cve" in ev:
        return {
            "category": "security_vulnerability",
            "severity": "critical",
            "triage": "Isolate affected sink, patch vulnerable dependency, or sanitize input.",
        }
    elif "build" in ev or "syntax" in ev:
        return {
            "category": "build_failure",
            "severity": "high",
            "triage": "Check compileall or TypeScript compilation error output.",
        }
    elif "test" in ev or "regression" in ev:
        return {
            "category": "test_regression",
            "severity": "medium",
            "triage": "Identify failing assertion in recent commit diff.",
        }
    else:
        return {
            "category": "operational",
            "severity": "low",
            "triage": "Review telemetry and commit audit log.",
        }


def record_incident(event_type: str, details: dict) -> dict:
    """Record an incident into the persistent repo state incident triage timeline."""
    s = load_state()
    incidents = s.get("incident_timeline", [])
    classification = classify_incident_event(event_type, details)
    record = {
        "id": f"inc-{len(incidents) + 1}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "category": classification["category"],
        "severity": classification["severity"],
        "triage": classification["triage"],
        "details": details,
    }
    incidents.insert(0, record)
    s["incident_timeline"] = incidents[:100]
    save_state(s)
    return record


def get_incidents(limit: int = 50) -> list[dict]:
    """Retrieve recent incidents from the triage timeline."""
    s = load_state()
    return s.get("incident_timeline", [])[:limit]
