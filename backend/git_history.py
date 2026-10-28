"""
git_history.py
Git churn metrics for the hotspot overlay (Milestone 1.3).

Correction C2: this is a NEW module. `backend/repo_tracker.py` is JSON
state describing the GitHub metadata of the currently-loaded repository —
it contains no git calls at all. Mixing the two would conflate "what we
know about the remote repo" with "how the local working tree has changed".

Three metrics are produced:

  churn score   How often the file has changed in the window. A file
                touched every week is a hotspot; a file untouched for a
                year is stable.

  co-change     Which files keep changing together. Two files that
                always change together are coupled, and a change to one
                probably requires a change to the other — the blast
                radius should say so.

  ownership     Who touches the file most. Combined with churn it answers
                "who do I talk to about this?".

Everything degrades gracefully: no `.git` directory, no `git` binary, a
non-zero exit, or a timeout all produce an empty result rather than an
exception. A repository that has never been committed to still renders.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("reposcope.git_history")

DEFAULT_WINDOW_DAYS = 90
GIT_TIMEOUT_SECONDS = 30


@dataclass
class FileChurn:
    """How much a single file has changed inside the window."""

    path: str
    commits: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    authors: dict[str, int] = field(default_factory=dict)
    last_modified: str = ""

    @property
    def churn_score(self) -> int:
        """Commits plus lines touched. Simple, and stable across runs."""
        return self.commits + (self.lines_added + self.lines_deleted) // 10

    @property
    def primary_author(self) -> str:
        """The author who touched the file most often."""
        if not self.authors:
            return ""
        return max(self.authors.items(), key=lambda kv: (kv[1], kv[0]))[0]


@dataclass
class ChurnReport:
    """The churn metrics for a whole repository."""

    files: dict[str, FileChurn] = field(default_factory=dict)
    #: Files that keep changing together: file -> {other file: co-changes}
    co_changes: dict[str, dict[str, int]] = field(default_factory=dict)
    window_days: int = DEFAULT_WINDOW_DAYS
    available: bool = False
    reason: str = ""

    def churn_for(self, path: str) -> FileChurn | None:
        return self.files.get(path.replace("\\", "/"))

    def hotspot_score(self, path: str, centrality: float = 0.0) -> float:
        """
        The hotspot score for a file.

        Churn alone finds churny files; centrality alone finds important
        files. A file that is both — frequently changed AND widely
        depended upon — is where regressions actually happen. That is the
        one worth flagging.
        """
        churn = self.churn_for(path)
        if churn is None:
            return 0.0
        # Normalise both inputs to 0..1 so neither dominates.
        churn_norm = min(1.0, churn.churn_score / 50.0)
        centrality_norm = max(0.0, min(1.0, centrality * 20.0))
        return round(0.6 * churn_norm + 0.4 * centrality_norm, 4)


def _run_git(repo_root: Path, args: list[str], timeout: int = GIT_TIMEOUT_SECONDS):
    """Run a git command, returning stdout or None on any failure."""
    try:
        # Stdout/stderr go to TEMPORARY FILES, not pipes. On Windows, a
        # git process killed after `timeout` can leave a child holding
        # the write end of a capture pipe open; subprocess.run then waits
        # forever for EOF while joining its reader threads. That wedged
        # the MCP server: `git rev-parse` timed out, the timeout handler
        # hung, and every later call waited on the same blocked worker.
        # Files cannot deadlock that way.
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            creationflags = (
                subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            result = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=timeout,
                creationflags=creationflags,
            )
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read().decode("utf-8", "replace")
            stderr = stderr_file.read().decode("utf-8", "replace")
    except FileNotFoundError:
        log.info("git is not installed — churn metrics unavailable")
        return None
    except subprocess.TimeoutExpired:
        log.warning("git %s timed out after %ss", args[0], timeout)
        return None
    except Exception as exc:  # noqa: BLE001 - never break the graph
        log.warning("git %s failed: %s", args[0], exc)
        return None

    if result.returncode != 0:
        log.info("git %s exited %s: %s", args[0], result.returncode, stderr.strip())
        return None
    return stdout


def _is_git_repo(repo_root: Path) -> bool:
    """True when the directory is inside a git working tree."""
    result = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"], timeout=10)
    return bool(result and result.strip() == "true")


def collect_churn(
    repo_root: str | Path,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> ChurnReport:
    """
    Collect churn metrics for a repository.

    Returns an empty report (with `available` False and a reason) when
    the metrics cannot be produced — the caller renders the graph either
    way.
    """
    root = Path(repo_root)
    if not root.is_dir():
        return ChurnReport(window_days=window_days, reason="not a directory")
    if not _is_git_repo(root):
        return ChurnReport(window_days=window_days, reason="not a git repository")

    # One pass: numstat plus the author and date per commit.
    output = _run_git(
        root,
        [
            "log",
            f"--since={window_days}.days",
            "--numstat",
            "--format=__COMMIT__%H%x09%an%x09%aI",
            "--no-merges",
        ],
    )
    if output is None:
        return ChurnReport(window_days=window_days, reason="git log failed")

    files: dict[str, FileChurn] = {}
    co_changes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    author = ""
    timestamp = ""
    touched_in_commit: list[str] = []

    def flush_commit() -> None:
        """Record the co-change relationships for the commit just parsed."""
        if len(touched_in_commit) < 2:
            return
        for left in touched_in_commit:
            for right in touched_in_commit:
                if left == right:
                    continue
                co_changes[left][right] += 1

    for line in output.splitlines():
        if line.startswith("__COMMIT__"):
            flush_commit()
            touched_in_commit = []
            parts = line[len("__COMMIT__"):].split("\t")
            if len(parts) >= 3:
                _, author, timestamp = parts[0], parts[1], parts[2]
            else:
                author, timestamp = "", ""
            continue

        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, deleted, path = parts[0], parts[1], parts[2]
        path = path.replace("\\", "/")
        # A rename shows as "old => new" or "old => new (similarity)".
        if " => " in path:
            path = path.split(" => ")[-1].split(" (")[0]

        entry = files.get(path)
        if entry is None:
            entry = FileChurn(path=path)
            files[path] = entry

        entry.commits += 1
        if added.isdigit():
            entry.lines_added += int(added)
        if deleted.isdigit():
            entry.lines_deleted += int(deleted)
        if author:
            entry.authors[author] = entry.authors.get(author, 0) + 1
        if timestamp:
            entry.last_modified = timestamp

        if path not in touched_in_commit:
            touched_in_commit.append(path)

    flush_commit()

    plain_co_changes = {
        left: dict(rights) for left, rights in co_changes.items()
    }

    log.info(
        "Churn collected: %d files changed in %d days (%d co-change groups)",
        len(files), window_days, len(plain_co_changes),
    )

    return ChurnReport(
        files=files,
        co_changes=plain_co_changes,
        window_days=window_days,
        available=True,
    )


def churn_to_api(report: ChurnReport, graph: dict | None = None) -> dict:
    """
    The churn payload served to the UI.

    When a graph is supplied, each file node also carries its hotspot
    score, which blends churn with the node's centrality — that is the
    number the heatmap colours by.
    """
    centrality: dict[str, float] = {}
    if graph:
        for node in graph.get("nodes", []) or []:
            if node.get("type") == "file":
                centrality[str(node.get("file") or node.get("label") or "")] = float(
                    node.get("pagerank", 0.0)
                )

    entries = []
    for path, churn in sorted(
        report.files.items(), key=lambda kv: kv[1].churn_score, reverse=True
    ):
        entries.append({
            "path": path,
            "commits": churn.commits,
            "lines_added": churn.lines_added,
            "lines_deleted": churn.lines_deleted,
            "churn_score": churn.churn_score,
            "primary_author": churn.primary_author,
            "last_modified": churn.last_modified,
            "hotspot_score": report.hotspot_score(path, centrality.get(path, 0.0)),
            "co_changes": sorted(
                report.co_changes.get(path, {}).items(),
                key=lambda kv: kv[1],
                reverse=True,
            )[:5],
        })

    return {
        "available": report.available,
        "reason": report.reason,
        "window_days": report.window_days,
        "files": entries,
        "total_files": len(entries),
    }


def compute_ast_complexity(file_path: Path) -> int:
    """Computes cyclomatic complexity proxy by counting branching nodes/tokens."""
    if not file_path.is_file():
        return 1
    ext = file_path.suffix.lower()
    try:
        if ext == ".py":
            import ast
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
            count = 1
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler, ast.With, ast.Match)):
                    count += 1
                elif isinstance(node, ast.BoolOp):
                    count += max(0, len(node.values) - 1)
            return count
        elif ext in {".js", ".jsx", ".ts", ".tsx"}:
            import re
            content = file_path.read_text(encoding="utf-8", errors="replace")
            branches = len(re.findall(r"\b(if|else\s+if|for|while|switch|case|catch)\b", content))
            logics = len(re.findall(r"(&&|\|\||\?)", content))
            return max(1, branches + logics // 2)
        else:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return max(1, len([l for l in lines if l.strip()]) // 20)
    except Exception:
        return 1


def compute_hotspots(repo_root: str | Path, limit: int = 100) -> dict:
    """Computes bounded churn, AST complexity, hotspot quadrant scores, and bus factor risks."""
    root = Path(repo_root)
    churn_report = collect_churn(root)
    if not churn_report.available:
        return {
            "ok": False,
            "reason": churn_report.reason or "Git history unavailable",
            "files": [],
            "high_risk_hotspots": [],
            "bus_factor_warnings": [],
            "quadrant_summary": {"critical": 0, "debt": 0, "active": 0, "stable": 0},
        }

    import math
    file_results = []
    author_totals: dict[str, int] = defaultdict(int)

    for path, churn in churn_report.files.items():
        full_path = root / path
        complexity = compute_ast_complexity(full_path)
        churn_score = churn.churn_score
        hotspot_score = round(math.log10(churn_score + 1) * complexity, 2)

        top_author = churn.primary_author or "Unknown"
        top_count = churn.authors.get(top_author, 0)
        total_commits = max(1, churn.commits)
        author_share = round(top_count / total_commits, 2)
        bus_factor_risk = bool(author_share >= 0.8 and total_commits >= 2)

        for a, cnt in churn.authors.items():
            author_totals[a] += cnt

        is_high_churn = churn_score >= 10
        is_high_comp = complexity >= 10

        if is_high_churn and is_high_comp:
            quadrant = "critical"
            risk_level = "critical" if hotspot_score >= 15 else "high"
        elif not is_high_churn and is_high_comp:
            quadrant = "debt"
            risk_level = "medium"
        elif is_high_churn and not is_high_comp:
            quadrant = "active"
            risk_level = "medium"
        else:
            quadrant = "stable"
            risk_level = "low"

        file_results.append({
            "path": path,
            "commits": churn.commits,
            "lines_added": churn.lines_added,
            "lines_deleted": churn.lines_deleted,
            "churn_score": churn_score,
            "complexity": complexity,
            "hotspot_score": hotspot_score,
            "primary_author": top_author,
            "author_share": author_share,
            "bus_factor_risk": bus_factor_risk,
            "risk_level": risk_level,
            "quadrant": quadrant,
        })

    file_results.sort(key=lambda x: x["hotspot_score"], reverse=True)

    high_risk = [f for f in file_results if f["risk_level"] in ("critical", "high")][:10]
    bus_warnings = [f for f in file_results if f["bus_factor_risk"]][:10]

    quadrant_counts = {
        "critical": len([f for f in file_results if f["quadrant"] == "critical"]),
        "debt": len([f for f in file_results if f["quadrant"] == "debt"]),
        "active": len([f for f in file_results if f["quadrant"] == "active"]),
        "stable": len([f for f in file_results if f["quadrant"] == "stable"]),
    }

    return {
        "ok": True,
        "total_files": len(file_results),
        "high_risk_hotspots": high_risk,
        "bus_factor_warnings": bus_warnings,
        "quadrant_summary": quadrant_counts,
        "files": file_results[:50],
    }


def compare_refs(repo_root: str | Path, ref_a: str = "HEAD~10", ref_b: str = "HEAD") -> dict:
    """Historical Time Machine: compare two commits/refs and summarize changes & architectural drift."""
    root = Path(repo_root)
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789~^_-./")
    if not all(c in safe_chars for c in ref_a) or not all(c in safe_chars for c in ref_b):
        return {"ok": False, "error": "Invalid ref format"}

    diff_out = _run_git(root, ["diff", "--name-status", ref_a, ref_b])
    if diff_out is None and ref_a != "HEAD~1":
        ref_a = "HEAD~1"
        diff_out = _run_git(root, ["diff", "--name-status", ref_a, ref_b])

    if diff_out is None:
        return {
            "ok": True,
            "ref_a": ref_a,
            "ref_b": ref_b,
            "added_files": [],
            "removed_files": [],
            "modified_files": [],
            "summary": "No git diff available.",
            "architectural_drift": [],
        }

    added = []
    removed = []
    modified = []
    for line in diff_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        fpath = parts[-1]
        if status.startswith("A"):
            added.append(fpath)
        elif status.startswith("D"):
            removed.append(fpath)
        else:
            modified.append(fpath)

    shortstat = _run_git(root, ["diff", "--shortstat", ref_a, ref_b]) or "0 files changed"

    drift = []
    if added:
        drift.append(f"{len(added)} new file(s) introduced (e.g. {added[0]})")
    if removed:
        drift.append(f"{len(removed)} file(s) removed")
    if len(modified) > 10:
        drift.append(f"Cross-cutting refactor spanning {len(modified)} files")

    return {
        "ok": True,
        "ref_a": ref_a,
        "ref_b": ref_b,
        "added_files": added,
        "removed_files": removed,
        "modified_files": modified,
        "summary": shortstat.strip(),
        "architectural_drift": drift,
    }
