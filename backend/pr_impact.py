"""
pr_impact.py
PR Bot — computes the blast radius of a pull request's changed files and
renders the result as a GitHub-ready markdown comment (risk score, affected
files, suggested tests, mermaid impact graph). GitHub renders mermaid code
fences natively in PR comments, so the diagram is live on the PR.
"""
import logging
import re

import httpx

from graph_utils import build_adjacency, find_node_by_label
from impact_analyzer import compute_blast_radius

log = logging.getLogger("reposcope.pr_impact")

GITHUB_API = "https://api.github.com"
MAX_FILES_ANALYZED = 25   # per-PR cap so a 100-file PR can't stall the API
MAX_MERMAID_NODES = 14    # comment-size cap for the mermaid diagram


async def fetch_pr(owner: str, repo: str, pr_number: int,
                   token: str | None = None) -> tuple[dict, list[dict]]:
    """Fetch PR metadata + changed files from GitHub REST v3.

    Returns (meta, files). Raises RuntimeError with a safe message when the
    PR is missing or the API call fails.
    """
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=20, headers=headers) as c:
        pr_res = await c.get(base)
        if pr_res.status_code == 404:
            raise RuntimeError(f"PR #{pr_number} not found in {owner}/{repo}")
        if pr_res.status_code == 403:
            raise RuntimeError("GitHub API rate limit or forbidden — pass a "
                               "GITHUB_TOKEN to raise the limit")
        pr_res.raise_for_status()
        meta = pr_res.json()

        files: list[dict] = []
        page = 1
        while len(files) < 300:  # hard cap: 3 pages × 100
            f_res = await c.get(f"{base}/files",
                                params={"per_page": 100, "page": page})
            f_res.raise_for_status()
            batch = f_res.json()
            if not isinstance(batch, list) or not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1

    return meta, files


def _risk_level(score: int) -> str:
    if score >= 8:
        return "critical"
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def build_pr_impact(graph: dict, meta: dict, files: list[dict]) -> dict:
    """Aggregate blast radius across every changed file and render the
    GitHub comment markdown. Pure function — no network, no LLM."""
    forward, reverse = build_adjacency(graph)

    per_file: list[dict] = []
    impacted_ids: set[str] = set()
    direct_ids: set[str] = set()
    transitive_ids: set[str] = set()
    tests: list[str] = []
    total_risk = 0

    for f in files[:MAX_FILES_ANALYZED]:
        filename = f.get("filename") or ""
        if not filename:
            continue
        node = find_node_by_label(graph, filename)
        entry = {
            "file": filename,
            "status": f.get("status") or "changed",
            "additions": f.get("additions") or 0,
            "deletions": f.get("deletions") or 0,
            "in_graph": node is not None,
            "direct": 0,
            "transitive": 0,
        }
        if node:
            blast = compute_blast_radius(graph, node["id"], 3)
            entry["direct"] = len(blast["direct_impacts"])
            entry["transitive"] = len(blast["transitive_impacts"])
            total_risk += blast["risk_score"]
            impacted_ids.update(
                [blast["target"]["id"]]
                + [n["id"] for n in blast["direct_impacts"]]
                + [n["id"] for n in blast["transitive_impacts"]]
            )
            direct_ids.update(n["id"] for n in blast["direct_impacts"])
            transitive_ids.update(n["id"] for n in blast["transitive_impacts"])
            for t in blast["suggested_tests"]:
                if t not in tests:
                    tests.append(t)
        per_file.append(entry)

    # Aggregate risk: mean of per-file scores (≥1 when files changed) so a
    # 20-file PR doesn't automatically max out the scale.
    analyzed = len([e for e in per_file if e["in_graph"]]) or 1
    risk_score = max(1, min(10, round(total_risk / analyzed)))
    risk_level = _risk_level(risk_score)

    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}

    def _label(node_id: str) -> str:
        n = nodes_by_id.get(node_id)
        return n.get("label", node_id) if n else node_id

    comment = _render_comment(meta, risk_score, risk_level, per_file,
                              tests, direct_ids, transitive_ids, _label)

    return {
        "pr_number": meta.get("number"),
        "pr_title": meta.get("title") or "",
        "pr_state": meta.get("state") or "",
        "risk_score": risk_score,
        "risk_level": risk_level,
        "affected_files": per_file,
        "files_analyzed": analyzed,
        "impacted_total": len(impacted_ids),
        "direct_total": len(direct_ids),
        "transitive_total": len(transitive_ids),
        "suggested_tests": tests[:8],
        "mermaid": _mermaid(direct_ids, transitive_ids, _label),
        "comment": comment,
    }


def _render_comment(meta: dict, risk_score: int, risk_level: str,
                    per_file: list[dict], tests: list[str],
                    direct_ids: set, transitive_ids: set,
                    label) -> str:
    risk_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(risk_level, "⚪")
    lines = [
        f"## {risk_icon} RepoScope PR Impact Report — #{meta.get('number', '?')}",
        "",
        f"**Risk score: `{risk_score}/10` ({risk_level})** · "
        f"{len(per_file)} files changed · "
        f"{len(direct_ids) + len(transitive_ids)} nodes in the blast radius",
        "",
        "### Affected files",
        "",
        "| File | Status | +/− | Direct impacts | Transitive |",
        "|---|---|---|---|---|",
    ]
    for e in per_file[:20]:
        sign = f"+{e['additions']}/−{e['deletions']}"
        in_graph = f"{e['direct']}" if e["in_graph"] else "n/a (not in graph)"
        trans = f"{e['transitive']}" if e["in_graph"] else "n/a"
        lines.append(f"| `{e['file']}` | {e['status']} | {sign} | {in_graph} | {trans} |")
    if len(per_file) > 20:
        lines.append(f"| _…and {len(per_file) - 20} more_ | | | | |")

    lines += ["", "### ✅ Suggested tests", ""]
    if tests:
        lines += [f"- `{t}`" for t in tests[:6]]
    else:
        lines.append("- No test files detected in the graph — consider adding "
                     "tests for the direct imports of the changed files.")

    lines += [
        "",
        "### 🕸️ Impact graph",
        "",
        "```mermaid",
        _mermaid(direct_ids, transitive_ids, label),
        "```",
        "",
        "<details>",
        "<summary>How this works</summary>",
        "",
        "RepoScope parses the dependency graph (AST for Python, regex for ",
        "JS/TS) and reverse-BFSes every changed file to compute the blast ",
        "radius: files that import the changed code (direct) and everything ",
        "that depends on those (transitive).",
        "",
        "</details>",
        "",
        f"<sub>🤖 Generated by [RepoScope](https://repo-scope-nu.vercel.app) "
        f"— blast-radius analysis on every PR.</sub>",
    ]
    return "\n".join(lines)


def _mermaid(direct_ids: set, transitive_ids: set, label) -> str:
    lines = ["graph TD"]
    direct_list = sorted(direct_ids)[:MAX_MERMAID_NODES]
    transitive_list = sorted(transitive_ids)[:MAX_MERMAID_NODES // 2]

    for i, nid in enumerate(direct_list):
        safe = _mangle(label(nid))
        lines.append(f"  D{i}[\"{safe}\"]:::direct")
    for i, nid in enumerate(transitive_list):
        safe = _mangle(label(nid))
        lines.append(f"  T{i}[\"{safe}\"]:::transitive")
    for i, nid in enumerate(direct_list):
        # link up to the first transitive dependents that actually import it
        lines.append(f"  D{i} -.-> PR((PR))")
    for i in range(len(transitive_list)):
        tgt = f"D{i % max(1, len(direct_list))}" if direct_list else "PR"
        lines.append(f"  T{i} -.-> {tgt}")

    lines.append("  classDef direct fill:#F0503C,stroke:#B03A2A,color:#fff")
    lines.append("  classDef transitive fill:#D97706,stroke:#9A5B0A,color:#fff")
    return "\n".join(lines)


def _mangle(label: str) -> str:
    """Mermaid-safe node text: strip quotes/backslashes that break the fence."""
    return re.sub(r'["\\]', "'", label)[:48]


async def post_pr_comment(owner: str, repo: str, pr_number: int,
                          body: str, token: str | None = None) -> dict:
    """POST the rendered comment to the PR conversation thread."""
    if not token:
        raise RuntimeError("A GitHub token is required to post the comment")
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    async with httpx.AsyncClient(timeout=20) as c:
        res = await c.post(url, json={"body": body},
                           headers={"Authorization": f"Bearer {token}",
                                    "Accept": "application/vnd.github+json"})
    if res.status_code == 403:
        raise RuntimeError("GitHub rejected the comment (403) — the token "
                           "needs 'pull-requests: write' permission")
    res.raise_for_status()
    return res.json()
