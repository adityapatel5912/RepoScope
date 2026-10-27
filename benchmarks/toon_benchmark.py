"""
benchmarks/toon_benchmark.py
Comparative token and byte compaction benchmark for RepoScope context packs:
Compact JSON vs TOON (Token-Oriented Object Notation).

Milestone V2.5 Phase 4.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from graph_builder import build_graph_from_repo
from context_compressor import (
    build_context_pack,
    decode_toon,
    encode_json,
    encode_toon,
    estimate_tokens,
    toon_available,
)


def get_git_info(repo_path: Path) -> tuple[str, str]:
    """Retrieve HEAD commit hash and ISO commit timestamp without exposing secrets."""
    cmd_hash = ["git", "-C", str(repo_path), "rev-parse", "HEAD"]
    cmd_date = ["git", "-C", str(repo_path), "log", "-1", "--format=%cI"]

    res_hash = subprocess.run(cmd_hash, capture_output=True, text=True, check=True)
    res_date = subprocess.run(cmd_date, capture_output=True, text=True, check=True)

    return res_hash.stdout.strip(), res_date.stdout.strip()


def run_benchmark(
    repos: list[tuple[str, Path]],
    budget: int = 8000,
    detail: str = "skeleton",
    out_path: str | None = None,
) -> dict[str, Any]:
    if not toon_available():
        print("ERROR: TOON format is not available in the current environment.", file=sys.stderr)
        sys.exit(1)

    import toon_format

    system_info = {
        "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python_version": sys.version.split()[0],
        "toon_format_version": getattr(toon_format, "__version__", "unknown"),
        "budget": budget,
        "detail": detail,
    }

    results: list[dict[str, Any]] = []

    for name, path in repos:
        resolved_path = Path(path).resolve()
        if not resolved_path.exists():
            print(f"ERROR: Repository path does not exist: {resolved_path}", file=sys.stderr)
            sys.exit(1)

        commit_sha, commit_date = get_git_info(resolved_path)

        # 1. Build graph
        graph = build_graph_from_repo(str(resolved_path))
        node_count = len(graph.get("nodes", []))
        edge_count = len(graph.get("edges", []))

        # 2. Build context pack
        pack = build_context_pack(
            graph=graph,
            root=str(resolved_path),
            detail=detail,
            budget=budget,
        )

        files_inc = pack.get("counts", {}).get("files_included", 0)
        symbols_inc = pack.get("counts", {}).get("symbols_included", 0)

        # 3. Compact JSON serialization
        compact_json = json.dumps(pack, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        json_bytes = len(compact_json.encode("utf-8"))
        json_tokens = estimate_tokens(compact_json)

        # 4. TOON serialization
        toon_text = encode_toon(pack)
        toon_bytes = len(toon_text.encode("utf-8"))
        toon_tokens = estimate_tokens(toon_text)

        # 5. Roundtrip validation
        decoded = decode_toon(toon_text)
        expected = json.loads(compact_json)
        roundtrip_ok = (decoded == expected)

        if not roundtrip_ok:
            print(f"ERROR: Roundtrip mismatch for repository '{name}'!", file=sys.stderr)
            sys.exit(1)

        token_saving_pct = round((1 - toon_tokens / json_tokens) * 100, 2) if json_tokens else 0.0
        byte_saving_pct = round((1 - toon_bytes / json_bytes) * 100, 2) if json_bytes else 0.0

        results.append({
            "name": name,
            "path": str(resolved_path),
            "commit": commit_sha,
            "commit_date": commit_date,
            "node_count": node_count,
            "edge_count": edge_count,
            "files_included": files_inc,
            "symbols_included": symbols_inc,
            "json_bytes": json_bytes,
            "json_tokens": json_tokens,
            "toon_bytes": toon_bytes,
            "toon_tokens": toon_tokens,
            "token_saving_pct": token_saving_pct,
            "byte_saving_pct": byte_saving_pct,
            "roundtrip_ok": roundtrip_ok,
        })

    token_savings = [r["token_saving_pct"] for r in results]
    byte_savings = [r["byte_saving_pct"] for r in results]

    median_token_saving = round(statistics.median(token_savings), 2) if token_savings else 0.0
    median_byte_saving = round(statistics.median(byte_savings), 2) if byte_savings else 0.0

    summary = {
        "metadata": system_info,
        "results": results,
        "summary": {
            "median_token_saving_pct": median_token_saving,
            "median_byte_saving_pct": median_byte_saving,
            "total_repositories": len(results),
            "all_roundtrips_passed": all(r["roundtrip_ok"] for r in results),
        },
    }

    # Print Markdown table
    print("\n## TOON Benchmark Results\n")
    print(f"- **Date**: {system_info['date']}")
    print(f"- **OS**: {system_info['os']}")
    print(f"- **Python**: {system_info['python_version']}")
    print(f"- **toon-format**: {system_info['toon_format_version']}")
    print(f"- **Budget**: {budget} tokens | **Detail**: {detail}")
    print()
    print("| Repository | Commit | Date | Nodes/Edges | Files/Symbols | JSON (bytes/tok) | TOON (bytes/tok) | Token Saving | Roundtrip |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        short_commit = r["commit"][:7]
        c_date = r["commit_date"][:10]
        ne = f"{r['node_count']}/{r['edge_count']}"
        fs = f"{r['files_included']}/{r['symbols_included']}"
        jb = f"{r['json_bytes']} B / {r['json_tokens']}"
        tb = f"{r['toon_bytes']} B / {r['toon_tokens']}"
        tsave = f"{r['token_saving_pct']:+.1f}%"
        rt = "PASS" if r["roundtrip_ok"] else "FAIL"
        print(f"| `{r['name']}` | `{short_commit}` | {c_date} | {ne} | {fs} | {jb} | {tb} | **{tsave}** | {rt} |")
    print()
    print(f"**Median Token Saving:** {median_token_saving:+.1f}%")
    print(f"**Median Byte Saving:** {median_byte_saving:+.1f}%")
    print()

    if out_path:
        out_p = Path(out_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Wrote benchmark results to {out_p}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Run RepoScope TOON benchmark against real repositories.")
    parser.add_argument(
        "--repo",
        action="append",
        dest="repos",
        metavar="NAME=PATH",
        required=True,
        help="Repository in format 'name=path'. Can be specified multiple times.",
    )
    parser.add_argument("--budget", type=int, default=8000, help="Token budget (default: 8000)")
    parser.add_argument(
        "--detail", choices=["skeleton", "full"], default="skeleton", help="Detail level (default: skeleton)"
    )
    parser.add_argument("--out", type=str, default=None, help="Output JSON path")

    args = parser.parse_args()

    parsed_repos = []
    for item in args.repos:
        if "=" not in item:
            parser.error(f"Invalid --repo format: {item!r}. Expected 'name=path'.")
        name, path = item.split("=", 1)
        parsed_repos.append((name.strip(), Path(path.strip())))

    run_benchmark(
        repos=parsed_repos,
        budget=args.budget,
        detail=args.detail,
        out_path=args.out,
    )


if __name__ == "__main__":
    main()
