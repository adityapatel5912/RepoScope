#!/usr/bin/env python
"""
benchmarks/run.py
The benchmark runner — the thing that produces RepoScope's published
numbers.

Milestone 8.1. The 2026 market for code intelligence sells on one
figure: how many tokens does an agent burn to understand a repository?
`codegraph` claims 62% fewer tokens, Repomix ~70%, GitNexus 88% fewer
tool calls. RepoScope published none, which meant a reviewer had no
reason to believe RepoScope.

**Every number in the README comes from this script.** If it has not been
run, the README says so. That is the only rule that keeps a published
figure from becoming a liability.

What it measures, per repository:

    index_seconds          cold: build the graph with no parse cache
    warm_index_seconds     the same build with a warm cache
    incremental_ms         update the graph after ONE file changes
    full_context_tokens    what an agent pays to read the whole repository
    repo_map_tokens        what an agent pays to read RepoScope's map
    reduction_pct          the difference
    traverse_ms            a transitive blast-radius query

Usage:

    python benchmarks/run.py                       # the local corpus
    python benchmarks/run.py --corpus my.txt       # your own list
    python benchmarks/run.py --output results      # where to write

The corpus file lists one repository per line. A line may be a local
path or a git URL. Blank lines and lines starting with `#` are ignored.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ── Corpus ──────────────────────────────────────────────────────────────────

def _configure_stdio() -> None:
    """
    Make the console able to print the report.

    Windows pipes default to cp1252, and Python raises
    `UnicodeEncodeError` on a character that code page cannot represent.
    Replacing is not as pretty as printing, but a crash would lose the
    whole run.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):  # pragma: no cover - exotic streams
            pass


def read_corpus(path: Path) -> list[str]:
    entries: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def materialise(entry: str, workdir: Path) -> Path:
    """
    Turn a corpus entry into a directory on disk.

    A local path is used as-is. A git URL is cloned shallowly into the
    work directory. A clone that fails is reported, not silently skipped
    — a benchmark that quietly drops the repositories it could not fetch
    would publish a number for a different corpus than it claims.
    """
    candidate = Path(entry).expanduser()
    if candidate.is_dir():
        return candidate.resolve()

    target = workdir / candidate.stem.replace(".git", "")
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", entry, str(target)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"clone failed: {result.stderr.strip()[:300]}")
    return target


# ── Measurements ────────────────────────────────────────────────────────────

def measure_repository(root: Path, scratch: Path) -> dict:
    """Measure one repository. Never raises — a failure is a result."""
    from graph_builder import GraphIndexer, build_graph_from_repo
    from impact_analyzer import compute_blast_radius
    from parse_cache import ParseCache
    from repo_map import build_repo_map_with_metrics

    record: dict = {"repository": str(root), "ok": False}

    try:
        file_count = sum(1 for p in root.rglob("*") if p.is_file())
        record["files"] = file_count

        # The caches live in the scratch directory, NOT inside the
        # repository under test: a benchmark must not leave anything
        # behind in the thing it measured.
        cache_dir = scratch / Path(root).name
        cache_dir.mkdir(parents=True, exist_ok=True)

        # ── Cold index: no cache at all ──
        cold_cache = ParseCache(cache_dir / "cold.json")
        started = time.perf_counter()
        graph = build_graph_from_repo(str(root), cold_cache)
        record["index_seconds"] = round(time.perf_counter() - started, 3)
        record["nodes"] = len(graph.get("nodes", []) or [])
        record["edges"] = len(graph.get("edges", []) or [])

        # ── Warm index: every file's hash is already known ──
        cache = ParseCache(cache_dir / "warm.json")
        cache.load()
        started = time.perf_counter()
        graph = build_graph_from_repo(str(root), cache)
        record["warm_index_seconds"] = round(time.perf_counter() - started, 3)
        cache_stats = cache.stats()
        record["cache_hits"] = cache_stats["hits"]
        record["cache_misses"] = cache_stats["misses"]

        # ── Incremental update: change ONE file ──
        indexer = GraphIndexer(root, cache)
        indexer.index()
        target = _pick_source_file(root)
        if target is not None:
            rel = str(target.relative_to(root)).replace("\\", "/")
            # The file is restored from its ORIGINAL BYTES. Reading and
            # writing it as text would translate "\n" into "\r\n" on
            # Windows, so the restore would leave the repository subtly
            # modified — a benchmark that changes what it measures.
            original = target.read_bytes()
            try:
                target.write_bytes(original + b"\n\ndef __bench_marker__():\n    return 1\n")
                started = time.perf_counter()
                updated = indexer.apply([rel])
                record["incremental_ms"] = round((time.perf_counter() - started) * 1000, 2)
                record["incremental_nodes"] = len(updated.get("nodes", []) or [])
            finally:
                target.write_bytes(original)

        # ── Token economics ──
        metrics = build_repo_map_with_metrics(graph, str(root))
        record["full_context_tokens"] = metrics.get("full_context_tokens", 0)
        record["repo_map_tokens"] = metrics.get("tokens", 0)
        record["reduction_pct"] = metrics.get("reduction_pct", 0.0)
        record["map_files"] = metrics.get("files_included", 0)
        record["map_files_total"] = metrics.get("files_total", 0)
        record["baseline_truncated"] = bool(
            (metrics.get("baseline") or {}).get("truncated", False)
        )

        # ── Traversal latency ──
        file_nodes = [n["id"] for n in graph.get("nodes", []) if n.get("type") == "file"]
        if file_nodes:
            samples = []
            for node_id in file_nodes[:20]:
                started = time.perf_counter()
                compute_blast_radius(graph, node_id, max_depth=3)
                samples.append((time.perf_counter() - started) * 1000)
            record["traverse_ms_median"] = round(statistics.median(samples), 2)
            record["traverse_ms_max"] = round(max(samples), 2)

        record["ok"] = True
    except Exception as exc:  # noqa: BLE001 - a failure is a result, not a crash
        record["error"] = f"{type(exc).__name__}: {exc}"

    return record


def _pick_source_file(root: Path) -> Path | None:
    """A source file to edit for the incremental measurement."""
    for suffix in (".py", ".ts", ".js", ".go", ".rs"):
        for path in sorted(root.rglob(f"*{suffix}")):
            if any(part in {".git", "node_modules", "__pycache__", ".reposcope"}
                   for part in path.parts):
                continue
            return path
    return None


# ── Reporting ───────────────────────────────────────────────────────────────

def render_markdown(records: list[dict], generated: str) -> str:
    lines = [
        "# RepoScope benchmark results",
        "",
        f"Generated by `benchmarks/run.py` on {generated}.",
        "",
        "| Repository | Files | Nodes | Edges | Index (s) | Warm (s) | Incremental (ms) "
        "| Full context (tok) | Repo map (tok) | Reduction |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for record in records:
        if not record.get("ok"):
            lines.append(f"| `{record.get('repository')}` | — | — | — | — | — | — | — | — | *failed* |")
            continue
        lines.append(
            f"| `{Path(record['repository']).name}` "
            f"| {record.get('files', 0)} "
            f"| {record.get('nodes', 0)} "
            f"| {record.get('edges', 0)} "
            f"| {record.get('index_seconds', 0):.3f} "
            f"| {record.get('warm_index_seconds', 0):.3f} "
            f"| {record.get('incremental_ms', 0):.1f} "
            f"| {record.get('full_context_tokens', 0):,} "
            f"| {record.get('repo_map_tokens', 0):,} "
            f"| {record.get('reduction_pct', 0):.1f}% |"
        )
    lines.append("")
    lines.append(
        "Token counts come from the built-in estimator in "
        "`backend/token_metrics.py`, which is model-independent and "
        "deterministic. The reduction is the figure RepoScope is built "
        "around; it is measured, not asserted."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="Run the RepoScope benchmarks.")
    parser.add_argument(
        "--corpus",
        default=str(REPO_ROOT / "benchmarks" / "corpus.txt"),
        help="A file listing one repository per line.",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "benchmarks" / "results"),
        help="Where to write the results.",
    )
    parser.add_argument(
        "--keep-clones",
        action="store_true",
        help="Keep the cloned repositories instead of deleting them.",
    )
    args = parser.parse_args(argv)

    corpus_path = Path(args.corpus)
    if not corpus_path.is_file():
        print(f"No corpus file at {corpus_path}", file=sys.stderr)
        return 2

    entries = read_corpus(corpus_path)
    if not entries:
        print(f"The corpus at {corpus_path} is empty", file=sys.stderr)
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="reposcope-bench-"))
    records: list[dict] = []
    try:
        for entry in entries:
            print(f"-> {entry}", flush=True)
            try:
                root = materialise(entry, workdir)
            except Exception as exc:  # noqa: BLE001
                records.append({"repository": entry, "ok": False, "error": str(exc)})
                print(f"  failed: {exc}", file=sys.stderr)
                continue
            record = measure_repository(root, workdir)
            records.append(record)
            if record.get("ok"):
                print(
                    f"  {record['nodes']} nodes, {record['edges']} edges, "
                    f"{record.get('reduction_pct', 0):.1f}% context reduction, "
                    f"incremental {record.get('incremental_ms', 0):.1f} ms",
                    flush=True,
                )
            else:
                print(f"  failed: {record.get('error')}", file=sys.stderr)
    finally:
        if not args.keep_clones:
            shutil.rmtree(workdir, ignore_errors=True)

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = generated.replace(":", "").replace("-", "")

    json_path = output_dir / f"results-{stamp}.json"
    json_path.write_text(
        json.dumps({"generated": generated, "results": records}, indent=2),
        encoding="utf-8",
    )
    md_path = output_dir / f"results-{stamp}.md"
    md_path.write_text(render_markdown(records, generated), encoding="utf-8")

    print()
    print(render_markdown(records, generated))
    print(f"Written:\n  {json_path}\n  {md_path}")

    failures = [r for r in records if not r.get("ok")]
    if failures:
        print(f"\n{len(failures)} of {len(records)} repositories failed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
