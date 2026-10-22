"""
ownership.py
The ownership overlay.

Milestone 9.4. "Who owns this file?" is a question every team asks and
no code graph answers — because the answer lives in the git history, not
in the source.

It pairs with the churn data: a file that changes often AND has one
owner is a knowledge silo, and a file that changes often and has MANY
owners is a coordination problem. Both are worth knowing before you
change something.

The data comes from `git log --format='%an'`, which is a single command
over the whole repository — not one call per file, which would be
hopeless on a large repository.
"""
from __future__ import annotations

import logging
import subprocess
from collections import Counter
from pathlib import Path

log = logging.getLogger("reposcope.ownership")

GIT_TIMEOUT_SECONDS = 60


def _run_git(repo_root: Path, args: list[str]) -> str:
    """Run a git command, returning its output or an empty string."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - git may not exist at all
        log.debug("git %s failed: %s", " ".join(args), exc)
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def is_git_repository(repo_root: str | Path) -> bool:
    """True when the directory is inside a git work tree."""
    root = Path(repo_root)
    if not root.is_dir():
        return False
    if (root / ".git").exists():
        return True
    output = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return output.strip() == "true"


def primary_owners(repo_root: str | Path) -> dict[str, str]:
    """
    The file that changed a file most often.

    Returns `{path: author}`. An empty dict when the directory is not a
    git repository — never an exception, because "no git" is a normal
    state, not an error.
    """
    root = Path(repo_root)
    if not is_git_repository(root):
        return {}

    # ONE git call for the whole repository. A per-file call would be
    # hopeless on a large repository.
    output = _run_git(root, [
        "log", "--no-merges", "--pretty=format:%H%x00%an", "--name-only",
    ])
    if not output:
        return {}

    # Each commit contributes one author line followed by its files.
    commits: list[tuple[str, list[str]]] = []
    current_author: str | None = None
    current_files: list[str] = []

    for line in output.splitlines():
        if "\x00" in line:
            if current_author is not None:
                commits.append((current_author, current_files))
            _, current_author = line.split("\x00", 1)
            current_files = []
        elif line.strip():
            current_files.append(line.strip())
    if current_author is not None:
        commits.append((current_author, current_files))

    counts: dict[str, Counter] = {}
    for author, files in commits:
        for path in files:
            counts.setdefault(path, Counter())[author] += 1

    owners: dict[str, str] = {}
    for path, counter in counts.items():
        if not counter:
            continue
        # The most frequent author; ties break alphabetically so the
        # answer is deterministic.
        owners[path] = sorted(
            counter.items(), key=lambda item: (-item[1], item[0]),
        )[0][0]
    return owners


def ownership_report(
    repo_root: str | Path,
    churn: dict[str, float] | None = None,
) -> dict:
    """
    The ownership overlay, combined with the churn.

    A file with many owners AND high churn is a coordination problem; a
    file with one owner AND high churn is a knowledge silo. Both are
    worth surfacing.
    """
    owners = primary_owners(repo_root)
    if not owners:
        return {"available": False, "reason": "not a git repository", "files": []}

    by_author: Counter = Counter(owners.values())
    files: list[dict] = []
    silos: list[str] = []
    coordination: list[str] = []

    for path, owner in sorted(owners.items()):
        churn_score = float((churn or {}).get(path, 0.0))
        entry = {
            "path": path,
            "owner": owner,
            "churn": round(churn_score, 4),
        }
        if churn_score > 0.5 and by_author[owner] == 1:
            entry["flag"] = "knowledge-silo"
            silos.append(path)
        elif churn_score > 0.5 and by_author[owner] > 3:
            entry["flag"] = "coordination"
            coordination.append(path)
        files.append(entry)

    return {
        "available": True,
        "files": files,
        "author_count": len(by_author),
        "top_authors": [{"author": a, "files": c} for a, c in by_author.most_common(10)],
        "knowledge_silos": silos,
        "coordination_risks": coordination,
    }
