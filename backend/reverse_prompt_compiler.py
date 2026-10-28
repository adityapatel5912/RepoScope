"""
backend/reverse_prompt_compiler.py
Deterministic four-mode reverse-prompt compiler for RepoScope (Phase 6, V2.6).

Emits four deterministic modes from the real graph:
- rebuild: stack, topological build order (with cycle detection), routes, models,
           env keys, test commands. 100% graph-derived.
- feature: self-contained prompt for a target node and its 2-hop interface closure.
- spec: CLAUDE.md, AGENTS.md, llms.txt, and .kiro/specs/architecture.md templates.
- context: compact/standard/full context pack with deterministic token estimation.

All modes produce byte-identical output for identical graph inputs.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from token_metrics import estimate_tokens
    from context_compressor import build_context_pack, encode_toon, toon_available
except ImportError:
    from backend.token_metrics import estimate_tokens
    from backend.context_compressor import build_context_pack, encode_toon, toon_available


def find_sccs(nodes: List[str], adj: Dict[str, Set[str]]) -> List[List[str]]:
    """Tarjan's algorithm for strongly connected components (SCCs) to detect cycles.
    
    Returns components in reverse topological order (callees before callers).
    """
    index = 0
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    sccs: List[List[str]] = []

    # Sort nodes deterministically
    sorted_nodes = sorted(nodes)

    def strongconnect(v: str):
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in sorted(adj.get(v, [])):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc: List[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            sccs.append(sorted(scc))

    for node in sorted_nodes:
        if node not in indices:
            strongconnect(node)

    return sccs


def compute_topological_build_order(
    file_nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Tuple[List[str], List[List[str]]]:
    """Compute topological build order of files.
    
    If file A imports or depends on file B, B must be built before A.
    Edge A -> B means A depends on B (B is a dependency of A).
    Returns (build_order_paths, detected_cycles).
    """
    path_set: Set[str] = set()
    id_to_path: Dict[str, str] = {}
    for n in file_nodes:
        p = n.get("path") or n.get("label") or n.get("id", "")
        if p.startswith("file:"):
            p = p[5:]
        p = p.replace("\\", "/").strip()
        if p:
            path_set.add(p)
            id_to_path[n.get("id", "")] = p
            id_to_path[f"file:{p}"] = p

    # Dependencies map: file -> set of files it depends on
    # If A imports B, B is a prereq of A.
    dependencies: Dict[str, Set[str]] = {p: set() for p in path_set}

    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        # Resolve to file paths
        src_path = id_to_path.get(src)
        tgt_path = id_to_path.get(tgt)

        # If edge connects symbols, resolve symbol to file
        if not src_path and ":" in src:
            parts = src.split(":")
            if len(parts) >= 2 and parts[1] in path_set:
                src_path = parts[1]
        if not tgt_path and ":" in tgt:
            parts = tgt.split(":")
            if len(parts) >= 2 and parts[1] in path_set:
                tgt_path = parts[1]

        if src_path and tgt_path and src_path != tgt_path:
            if src_path in dependencies and tgt_path in path_set:
                dependencies[src_path].add(tgt_path)

    # Tarjan's SCC finds components
    sccs = find_sccs(list(path_set), dependencies)

    # Cycles are SCCs with > 1 node or a self-loop
    cycles: List[List[str]] = []
    for scc in sccs:
        if len(scc) > 1:
            cycles.append(scc)
        elif len(scc) == 1 and scc[0] in dependencies.get(scc[0], set()):
            cycles.append(scc)

    # Condensation DAG of SCC components
    scc_of_node: Dict[str, int] = {}
    for i, scc in enumerate(sccs):
        for node in scc:
            scc_of_node[node] = i

    comp_adj: Dict[int, Set[int]] = defaultdict(set)
    in_degree: Dict[int, int] = {i: 0 for i in range(len(sccs))}

    for u, deps in dependencies.items():
        u_comp = scc_of_node[u]
        for v in deps:
            v_comp = scc_of_node[v]
            if u_comp != v_comp:
                # v must be built before u: v_comp -> u_comp
                if u_comp not in comp_adj[v_comp]:
                    comp_adj[v_comp].add(u_comp)
                    in_degree[u_comp] += 1

    # Kahn's algorithm on condensation DAG
    queue = deque(sorted([i for i in in_degree if in_degree[i] == 0]))
    sorted_comps: List[int] = []

    while queue:
        comp = queue.popleft()
        sorted_comps.append(comp)
        for nxt in sorted(comp_adj[comp]):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    # Build final list of file paths
    build_order: List[str] = []
    for comp_idx in sorted_comps:
        for node in sccs[comp_idx]:
            if node not in build_order:
                build_order.append(node)

    # Ensure any remaining files are appended deterministically
    for p in sorted(path_set):
        if p not in build_order:
            build_order.append(p)

    return build_order, cycles


def extract_2hop_closure(
    target_node_id: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any] | None, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract target node and its deterministic 2-hop interface closure.
    
    Returns (target_node, closure_nodes, closure_edges).
    """
    node_map = {n.get("id"): n for n in nodes if n.get("id")}
    
    # Resolve target_node_id
    target_node = node_map.get(target_node_id)
    if not target_node:
        # Try finding by label or path
        clean_target = target_node_id.replace("\\", "/").strip()
        for n in nodes:
            label = n.get("label", "").replace("\\", "/").strip()
            path = n.get("path", "").replace("\\", "/").strip()
            if label == clean_target or path == clean_target or f"file:{clean_target}" == n.get("id"):
                target_node = n
                break

    if not target_node:
        return None, [], []

    tid = target_node["id"]

    # Adjacency
    neighbors: Dict[str, Set[str]] = defaultdict(set)
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src and tgt:
            neighbors[src].add(tgt)
            neighbors[tgt].add(src)

    # Hop 0
    hop0 = {tid}
    # Hop 1
    hop1 = set(neighbors.get(tid, set())) - hop0
    # Hop 2
    hop2: Set[str] = set()
    for h1 in hop1:
        for h2 in neighbors.get(h1, set()):
            if h2 not in hop0 and h2 not in hop1:
                hop2.add(h2)

    closure_ids = sorted(hop0 | hop1 | hop2)
    closure_set = set(closure_ids)

    closure_nodes = [node_map[nid] for nid in closure_ids if nid in node_map]
    closure_edges = [
        e for e in edges
        if e.get("source") in closure_set and e.get("target") in closure_set
    ]

    return target_node, closure_nodes, closure_edges


def detect_stack(graph: Dict[str, Any], root: str | None) -> Dict[str, Any]:
    """Detect technologies, languages, frameworks, and test runners from graph and root."""
    nodes = graph.get("nodes", [])
    languages: Set[str] = set()
    frameworks: Set[str] = set()
    test_runners: Set[str] = set()
    env_keys: Set[str] = set()

    for n in nodes:
        label = n.get("label", "")
        path = n.get("path") or label
        ext = os.path.splitext(path)[1].lower()

        if ext in (".py", ".pyw"):
            languages.add("Python")
        elif ext in (".ts", ".tsx"):
            languages.add("TypeScript")
        elif ext in (".js", ".jsx", ".mjs", ".cjs"):
            languages.add("JavaScript")
        elif ext == ".go":
            languages.add("Go")
        elif ext == ".rs":
            languages.add("Rust")
        elif ext == ".java":
            languages.add("Java")
        elif ext in (".c", ".h", ".cpp", ".hpp"):
            languages.add("C/C++")

        # Framework detection from imports/labels
        low_label = label.lower()
        if "fastapi" in low_label:
            frameworks.add("FastAPI")
        if "react" in low_label:
            frameworks.add("React")
        if "playwright" in low_label:
            test_runners.add("Playwright")
        if "pytest" in low_label or "test_" in low_label:
            test_runners.add("pytest")
        if "tailwind" in low_label:
            frameworks.add("TailwindCSS")
        if "vite" in low_label:
            frameworks.add("Vite")

    # Inspect root directory if available
    if root:
        try:
            root_path = Path(root)
            if (root_path / "package.json").is_file():
                content = (root_path / "package.json").read_text(encoding="utf-8", errors="ignore")
                if "react" in content:
                    frameworks.add("React")
                if "vite" in content:
                    frameworks.add("Vite")
                if "playwright" in content:
                    test_runners.add("Playwright")
                if "tailwindcss" in content:
                    frameworks.add("TailwindCSS")
            if (root_path / "requirements.txt").is_file():
                reqs = (root_path / "requirements.txt").read_text(encoding="utf-8", errors="ignore")
                if "fastapi" in reqs.lower():
                    frameworks.add("FastAPI")
                if "pytest" in reqs.lower():
                    test_runners.add("pytest")
                if "uvicorn" in reqs.lower():
                    frameworks.add("Uvicorn")
            if (root_path / ".env.example").is_file():
                for line in (root_path / ".env.example").read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        env_keys.add(line.split("=", 1)[0].strip())
        except Exception:
            pass

    return {
        "languages": sorted(languages) or ["Generic"],
        "frameworks": sorted(frameworks),
        "test_runners": sorted(test_runners) or ["pytest"],
        "env_keys": sorted(env_keys),
    }


class ReversePromptCompiler:
    """Deterministic compiler that emits rebuild, feature, spec, and context prompts."""

    def __init__(
        self,
        graph: Dict[str, Any],
        local_path: str | None = None,
        repo_name: str | None = None,
    ):
        self.graph = graph or {}
        self.local_path = local_path
        if repo_name:
            clean_name = repo_name.split("/")[-1].strip()
            self.repo_name = clean_name or "Repository"
        elif local_path:
            self.repo_name = os.path.basename(local_path.rstrip("/\\")) or "Repository"
        else:
            self.repo_name = "Repository"

    def compile(
        self,
        mode: str = "context",
        target_node_id: str | None = None,
        budget: int | None = None,
        format_type: str = "json",
    ) -> Dict[str, Any]:
        """Compile reverse prompt in the requested mode."""
        clean_mode = (mode or "context").lower().strip()
        if clean_mode not in ("rebuild", "feature", "spec", "context"):
            clean_mode = "context"

        warnings: List[str] = []
        files: List[Dict[str, str]] = []
        content = ""

        if clean_mode == "rebuild":
            content, files, warnings = self._compile_rebuild()
        elif clean_mode == "feature":
            content, files, warnings = self._compile_feature(target_node_id)
        elif clean_mode == "spec":
            content, files, warnings = self._compile_spec()
        else:
            content, files, warnings = self._compile_context(budget, format_type)

        tokens = estimate_tokens(content)

        return {
            "ok": True,
            "mode": clean_mode,
            "content": content,
            "prompt": content,  # Preserves existing {prompt: "..."} callers
            "files": files,
            "tokens": tokens,
            "format": format_type,
            "source": {
                "nodes": len(self.graph.get("nodes", [])),
                "edges": len(self.graph.get("edges", [])),
                "root": self.local_path or self.repo_name,
            },
            "warnings": warnings,
        }

    def _compile_rebuild(self) -> Tuple[str, List[Dict[str, str]], List[str]]:
        warnings: List[str] = []
        stack = detect_stack(self.graph, self.local_path)
        file_nodes = [n for n in self.graph.get("nodes", []) if n.get("type") == "file"]
        edges = self.graph.get("edges", [])

        # Topological build order and cycle detection
        build_order, cycles = compute_topological_build_order(file_nodes, edges)

        if cycles:
            cycle_desc = "; ".join([" <-> ".join(c) for c in cycles])
            warnings.append(f"Cyclic dependencies detected: {cycle_desc}")

        # Extract API Routes
        api_routes = self.graph.get("api_routes", [])
        if not api_routes:
            # Fallback to nodes with route properties
            for n in self.graph.get("nodes", []):
                if n.get("route"):
                    api_routes.append(n["route"])

        # Extract Models/Classes
        models = [
            n for n in self.graph.get("nodes", [])
            if n.get("type") in ("class", "model") or n.get("role") in ("model", "schema")
        ]

        lines: List[str] = []
        lines.append(f"# System Rebuild Blueprint: {self.repo_name}\n")
        lines.append("## 1. Stack & Architecture")
        lines.append(f"- **Languages**: {', '.join(stack['languages'])}")
        if stack["frameworks"]:
            lines.append(f"- **Frameworks**: {', '.join(stack['frameworks'])}")
        lines.append(f"- **Test Runners**: {', '.join(stack['test_runners'])}")
        lines.append(f"- **Total Files**: {len(file_nodes)}")
        lines.append(f"- **Total Nodes**: {len(self.graph.get('nodes', []))}\n")

        lines.append("## 2. Topological Build Order")
        lines.append("Implement modules in the following order to satisfy dependency contracts:\n")
        if cycles:
            lines.append("> [!WARNING]")
            lines.append(f"> Cyclic dependencies detected across {len(cycles)} cycle group(s):")
            for c in cycles:
                lines.append(f"> - `{' -> '.join(c)}`")
            lines.append("")

        non_source = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".xlsx", ".xls", ".csv", ".zip", ".tar", ".gz", ".lock"}
        source_order = [p for p in build_order if not any(p.lower().endswith(ext) for ext in non_source)]
        asset_files = [p for p in build_order if any(p.lower().endswith(ext) for ext in non_source)]

        for i, path in enumerate(source_order, 1):
            lines.append(f"{i}. `{path}`")
        lines.append("")

        if asset_files:
            lines.append("### Static Assets & Mock Data")
            for a in asset_files[:20]:
                lines.append(f"- `{a}`")
            lines.append("")

        if api_routes:
            lines.append("## 3. API Surface & Routes")
            lines.append("| Method | Path | Handler | Evidence |")
            lines.append("|---|---|---|---|")
            for r in sorted(api_routes, key=lambda x: (x.get("path", ""), x.get("method", ""))):
                m = r.get("method", "GET").upper()
                p = r.get("path", "/")
                h = r.get("handler", r.get("function", "-"))
                file_line = f"{r.get('file', '')}:{r.get('line', '')}" if r.get("file") else "-"
                lines.append(f"| `{m}` | `{p}` | `{h}` | `{file_line}` |")
            lines.append("")

        if models:
            lines.append("## 4. Core Models & Data Contracts")
            for m in sorted(models, key=lambda x: x.get("label", "")):
                lbl = m.get("label", "")
                loc = f"{m.get('path', m.get('file', ''))}:{m.get('line', '')}"
                lines.append(f"- **`{lbl}`** (`{loc}`)")
            lines.append("")

        if stack["env_keys"]:
            lines.append("## 5. Environment & Configuration Keys")
            for k in stack["env_keys"]:
                lines.append(f"- `{k}=<placeholder>`")
            lines.append("")

        lines.append("## 6. Verification Commands")
        for runner in stack["test_runners"]:
            if runner == "pytest":
                lines.append("- `python -m pytest -q`")
            elif runner == "Playwright":
                lines.append("- `npx playwright test`")
            else:
                lines.append(f"- `{runner.lower()} test`")

        content = "\n".join(lines)
        files = [{"path": "BLUEPRINT.md", "content": content}]
        return content, files, warnings

    def _compile_feature(self, target_node_id: str | None) -> Tuple[str, List[Dict[str, str]], List[str]]:
        warnings: List[str] = []
        if not target_node_id:
            # Pick the first non-config, real source code file candidate
            non_feature_exts = (".gitignore", ".env", ".png", ".pdf", ".csv", ".xlsx", ".lock")
            source_exts = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java")
            code_candidates = [
                n.get("id") for n in self.graph.get("nodes", [])
                if n.get("type") in ("file", "function", "class")
                and not any(n.get("label", "").lower().endswith(ext) for ext in non_feature_exts)
                and any(n.get("label", "").lower().endswith(ext) for ext in source_exts)
            ]
            candidates = code_candidates or [
                n.get("id") for n in self.graph.get("nodes", [])
                if n.get("type") in ("file", "function", "class") and n.get("id") != "root"
            ]
            if candidates:
                priority = [c for c in candidates if any(p in c.lower() for p in ("main", "app", "server", "index"))]
                target_node_id = priority[0] if priority else candidates[0]
                warnings.append(f"No target_node_id specified; defaulted to '{target_node_id}'.")
            else:
                return (
                    "# Feature Specification\n\nNo valid target node available in the repository index.",
                    [],
                    ["No valid target node available."],
                )

        target, closure_nodes, closure_edges = extract_2hop_closure(
            target_node_id,
            self.graph.get("nodes", []),
            self.graph.get("edges", []),
        )

        if not target:
            msg = f"Target node '{target_node_id}' not found in graph."
            return (
                f"# Feature Specification\n\n{msg}",
                [],
                [msg],
            )

        target_label = target.get("label", target_node_id)
        target_kind = target.get("type", "node")
        target_file = target.get("path") or target.get("file") or target.get("label", "")
        target_line = target.get("line", "")

        lines: List[str] = []
        lines.append(f"# Feature Slice: `{target_label}`\n")
        lines.append("## 1. Target Details")
        lines.append(f"- **ID**: `{target.get('id')}`")
        lines.append(f"- **Kind**: `{target_kind}`")
        lines.append(f"- **Location**: `{target_file}`{f':{target_line}' if target_line else ''}")
        if target.get("role"):
            lines.append(f"- **Role**: `{target.get('role')}`")
        lines.append("")

        lines.append(f"## 2. 2-Hop Interface Closure ({len(closure_nodes)} nodes, {len(closure_edges)} edges)")
        lines.append("Only dependencies and dependents within 2 hops of the target feature are included:\n")

        # Group closure nodes by type
        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for n in closure_nodes:
            by_type[n.get("type", "node")].append(n)

        for t in sorted(by_type):
            lines.append(f"### {t.capitalize()}s ({len(by_type[t])})")
            for item in sorted(by_type[t], key=lambda x: x.get("label", "")):
                ilabel = item.get("label", "")
                ipath = item.get("path") or item.get("file") or ""
                iline = item.get("line")
                loc_str = f" (`{ipath}:{iline}`)" if ipath and iline else f" (`{ipath}`)" if ipath else ""
                lines.append(f"- `{ilabel}`{loc_str}")
            lines.append("")

        lines.append("## 3. Interface Edges & Contracts")
        lines.append("| Source | Target | Edge Type |")
        lines.append("|---|---|---|")
        for e in sorted(closure_edges, key=lambda x: (x.get("source", ""), x.get("target", ""))):
            s = e.get("source", "")
            t = e.get("target", "")
            etype = e.get("type", "depends_on")
            lines.append(f"| `{s}` | `{t}` | `{etype}` |")
        lines.append("")

        lines.append("## 4. Implementation Guidelines")
        lines.append(f"1. Implement or modify `{target_label}` satisfying all interfaces above.")
        lines.append("2. Maintain deterministic compatibility with direct callers and callees.")
        lines.append("3. Do not modify files outside the 2-hop closure.")

        content = "\n".join(lines)
        files = [{"path": f"FEATURE_{target_label}.md", "content": content}]
        return content, files, warnings

    def _compile_spec(self) -> Tuple[str, List[Dict[str, str]], List[str]]:
        warnings: List[str] = []
        stack = detect_stack(self.graph, self.local_path)
        file_nodes = [n for n in self.graph.get("nodes", []) if n.get("type") == "file"]

        # 1. CLAUDE.md
        claude_md = f"""# CLAUDE.md — {self.repo_name} Guidelines

## Build & Test Commands
- Primary tests: `{stack['test_runners'][0] if stack['test_runners'] else 'pytest'}`
- Syntax & typecheck: `python -m compileall -q backend` (Python), `npm run build` (TypeScript)
- Full gate: verify tests before committing.

## Architecture & Code Style
- Stack: {', '.join(stack['languages'])} ({', '.join(stack['frameworks']) if stack['frameworks'] else 'Core'})
- Hierarchy: root -> pillar -> folder -> file -> symbol
- Strict typing, deterministic functions, zero random timestamps in generated files.
"""

        # 2. AGENTS.md
        agents_md = f"""# AGENTS.md — Autonomous Agent Work Agreement

## Core Rules
1. Work directly against the real codebase and graph; do not invent paths or framework conventions.
2. All AST and graph facts are authoritative; LLM generates prose only.
3. Preserve existing endpoint signatures, node IDs, and resource URIs.
4. Verify every change with self-verification and the author gate before declaring completion.
"""

        # 3. llms.txt
        llms_txt = f"""# {self.repo_name}
> Automated code intelligence and repository visualization engine.

## Overview
- Total indexed files: {len(file_nodes)}
- Primary stack: {', '.join(stack['languages'])}
- Frameworks: {', '.join(stack['frameworks']) if stack['frameworks'] else 'Standard library'}

## Structure
{chr(10).join([f"- `{n.get('path') or n.get('label')}`" for n in file_nodes[:25]])}
"""

        # 4. .kiro/specs/architecture.md
        pillars = sorted({n.get("pillar") for n in self.graph.get("nodes", []) if n.get("pillar")}) or [
            "frontend", "backend", "data", "infrastructure", "tests", "docs"
        ]
        kiro_spec = f"""# Architecture Specification: {self.repo_name}

## Six Pillars
{chr(10).join([f"- **{p.capitalize()}**: structural subsystem" for p in pillars])}

## Contracts
- Graphs maintain schema version 2 with verified evidence edges.
- SSE streams strictly adhere to text/event-stream with double-newline boundaries.
"""

        # 5. .kiro/specs/requirements.md
        api_routes = self.graph.get("api_routes", [])
        kiro_reqs = f"""# Requirements Specification: {self.repo_name}

## 1. Functional Scope
- Codebase intelligence and AST-derived knowledge graph navigation.
- Indexed files: {len(file_nodes)} files across {len(pillars)} architectural pillars.
- Route surface: {len(api_routes)} declared endpoints.

## 2. Non-Functional Requirements
- 100% deterministic output for identical graph inputs.
- Zero secrets or credentials exposed in exported blueprints.
- Strict token budgeting with accurate estimation.
"""

        # 6. .kiro/specs/design.md
        kiro_design = f"""# Design Specification: {self.repo_name}

## 1. Technical Architecture
- Languages: {', '.join(stack['languages'])}
- Frameworks: {', '.join(stack['frameworks']) if stack['frameworks'] else 'Core standard library'}
- Verification: {', '.join(stack['test_runners'])}

## 2. Component Layout
{chr(10).join([f"- `{p}`: Subsystem tier" for p in pillars])}
"""

        # 7. .kiro/specs/tasks.md
        build_order, _ = compute_topological_build_order(file_nodes, self.graph.get("edges", []))
        top_tasks = build_order[:15]
        kiro_tasks = f"""# Implementation Tasks: {self.repo_name}

## Phased Build Checklist (Topological Order)
{chr(10).join([f"- [ ] Step {i+1}: Implement `{f}`" for i, f in enumerate(top_tasks)])}
"""

        files = [
            {"path": "CLAUDE.md", "content": claude_md.strip()},
            {"path": "AGENTS.md", "content": agents_md.strip()},
            {"path": "llms.txt", "content": llms_txt.strip()},
            {"path": ".kiro/specs/architecture.md", "content": kiro_spec.strip()},
            {"path": ".kiro/specs/requirements.md", "content": kiro_reqs.strip()},
            {"path": ".kiro/specs/design.md", "content": kiro_design.strip()},
            {"path": ".kiro/specs/tasks.md", "content": kiro_tasks.strip()},
        ]

        content = "\n\n---\n\n".join([f"### File: `{f['path']}`\n\n```markdown\n{f['content']}\n```" for f in files])
        return content, files, warnings

    def _compile_context(
        self,
        budget: int | None,
        format_type: str,
    ) -> Tuple[str, List[Dict[str, str]], List[str]]:
        warnings: List[str] = []
        actual_budget = budget or 8000
        if actual_budget < 500:
            actual_budget = 500
        if actual_budget > 200000:
            actual_budget = 200000

        try:
            pack = build_context_pack(
                graph=self.graph,
                root=self.local_path,
                detail="skeleton",
                budget=actual_budget,
            )
        except Exception as e:
            warnings.append(f"Context pack build exception: {e}")
            pack = {"available": False, "files": []}

        files_list = pack.get("files", [])
        
        # Build deterministic markdown prompt from context pack
        lines: List[str] = []
        lines.append(f"# Repository Context Pack: {self.repo_name}")
        lines.append(f"Detail: skeleton | Budget: {actual_budget} tokens | Files: {len(files_list)}\n")

        export_files: List[Dict[str, str]] = []
        for f in files_list:
            fpath = f.get("path", "")
            fcontent = f.get("skeleton") or f.get("content") or ""
            if not fcontent and f.get("symbols"):
                sym_lines = []
                for s in f.get("symbols", []):
                    if isinstance(s, dict):
                        kind = s.get("type") or s.get("kind") or "symbol"
                        name = s.get("name") or s.get("label") or ""
                        line = s.get("line")
                        line_info = f" (line {line})" if line else ""
                        sym_lines.append(f"{kind} {name}{line_info}")
                    elif isinstance(s, str):
                        sym_lines.append(s)
                fcontent = "\n".join(sym_lines)

            export_files.append({"path": fpath, "content": fcontent})
            lines.append(f"## File: `{fpath}`")
            if f.get("role"):
                lines.append(f"*Role: {f.get('role')} | Pillar: {f.get('pillar', 'unknown')}*")
            lines.append("```")
            lines.append(fcontent.strip())
            lines.append("```\n")

        if (format_type or "").lower() == "toon":
            if toon_available():
                try:
                    toon_str = encode_toon(pack)
                    return toon_str, export_files, warnings
                except Exception as e:
                    warnings.append(f"TOON encoding failed: {e}")
            else:
                warnings.append("TOON format requested but not available or disabled; using standard format.")

        content = "\n".join(lines)
        return content, export_files, warnings
