"""
onboarding.py
Student Onboarding Mode — ranks repo files into pyramid rows using the
graph's connectivity score (incoming*2 + outgoing, same score the graph UI
uses), then generates a 3-level learning path with per-file explanations,
quizzes, and Good First Issues from the low-traffic bottom rows.

Row model (matches the frontend pyramid):
  Row 1    — backbone / entry points  → Level 1
  Rows 2-3 — core modules             → Level 2
  Rows 4-5 — utils / low-traffic      → Level 3 + Good First Issue candidates
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from graph_utils import build_adjacency
from json_utils import loads_tolerant, salvage_truncated_json
from runtime_config import ask_llm

log = logging.getLogger("reposcope.onboarding")

LEVEL_DEFS = [
    {"level": 1, "title": "Entry Points",
     "description": "Start here — these files are where execution begins and "
                    "everything else hangs off them."},
    {"level": 2, "title": "Core Modules",
     "description": "The engine room — the logic that entry points orchestrate. "
                    "Understanding these means understanding the app."},
    {"level": 3, "title": "Utils & Leaves",
     "description": "Low-traffic helpers. Few files depend on them, so they're "
                    "safe to read (and safe to change) first."},
]

_MAX_PER_LEVEL = 6
_SKIP_PREFIXES = ("docs/", "test", ".github/")
_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs",
    ".vue", ".svelte", ".sh", ".sql", ".proto", ".kt", ".swift",
}


def _is_code_file(label: str) -> bool:
    from pathlib import Path
    return Path(label).suffix.lower() in _CODE_EXTS


def rank_rows(graph: dict) -> dict[int, list[dict]]:
    """Bucket file nodes into rows 1-5 by connectivity score.

    Returns {row: [node, ...]} sorted best-first within each row. Row 1 holds
    the top `top_count` backbone files; rows 2-3 split the middle; rows 4-5
    hold the low-traffic tail.
    """
    forward, reverse = build_adjacency(graph)
    files = [n for n in graph.get("nodes", []) if n.get("type") == "file"]

    def score(n: dict) -> int:
        return len(reverse.get(n["id"], [])) * 2 + len(forward.get(n["id"], []))

    ranked = sorted(files, key=lambda n: (-score(n), n.get("label", "")))
    ranked = [n for n in ranked if not n.get("label", "").lower().startswith(_SKIP_PREFIXES)]
    # Learning paths and GFIs must point at code — images/docs/lockfiles make
    # nonsense entries ("add a docstring to a PNG"). Keep the unfiltered list
    # as fallback for repos where the whitelist would be too aggressive.
    code_ranked = [n for n in ranked if _is_code_file(n.get("label", ""))]
    if len(code_ranked) >= 6:
        ranked = code_ranked

    if not ranked:
        return {r: [] for r in range(1, 6)}

    top_count = min(_MAX_PER_LEVEL, max(1, len(ranked) // 4))
    row1 = ranked[:top_count]
    rest = ranked[top_count:]
    third = max(1, len(rest) // 3)
    tail = rest[2 * third :]                      # low-traffic bottom
    half = max(1, len(tail) // 2) if tail else 0  # rows 4-5 split the tail
    rows = {
        1: row1,
        2: rest[:third],
        3: rest[third : 2 * third],
        4: tail[:half],
        5: tail[half:],
    }
    return rows


def _level_prompt(level: int, title: str, files: list[dict]) -> str:
    listing = "\n".join(f"- {n.get('label')}" for n in files)
    return (
        f"You are onboarding a student to this repository.\n"
        f"Level {level} ({title}) covers these files:\n{listing}\n\n"
        f"Return ONLY a JSON object (no fences, no commentary):\n"
        f"{{\n"
        f"  \"files\": [{{\"path\": \"<exact path from the list>\", \"why\": \"1-2 sentences: what this file does and why it matters\"}}],\n"
        f"  \"quiz\": [{{\"question\": \"...\", \"options\": [\"a\",\"b\",\"c\",\"d\"], "
        f"\"answer_index\": 0, \"explanation\": \"1 sentence why\"}}  x3 ]\n"
        f"}}\n"
        f"Rules: cover every listed file in 'files' (same order). Exactly 3 quiz "
        f"questions testing real understanding of the files' roles. Keep 'why' under "
        f"40 words.answer_index is the 0-based index of the correct option."
    )


def _gfi_prompt(candidates: list[dict]) -> str:
    listing = "\n".join(f"- {n.get('label')}" for n in candidates)
    return (
        f"You are a maintainer creating Good First Issues for newcomers.\n"
        f"Low-traffic files in this repo (safe to modify):\n{listing}\n\n"
        f"Return ONLY a JSON object (no fences, no commentary):\n"
        f"{{\"issues\": [{{\"title\": \"...\", \"file\": \"<path>\", "
        f"\"description\": \"what to improve and why it's beginner-friendly\", "
        f"\"hint\": \"one concrete starting step\"}}  x3]}}\n"
        f"Rules: each issue must be completable by editing (or adding tests/docs to) "
        f"one of the listed files. Keep descriptions under 50 words."
    )


def _heuristic_level(level: int, files: list[dict]) -> dict:
    """LLM-free fallback so the endpoint still returns a usable path."""
    return {
        **LEVEL_DEFS[level - 1],
        "level": level,
        "files": [
            {"path": n.get("label", ""), "why": "Part of this repo's import "
             "graph — open it and follow what it imports next."}
            for n in files
        ],
        "quiz": [],
    }


def _loads_tolerant(s: str) -> dict:
    """Backward-compatible wrapper around json_utils.loads_tolerant."""
    return loads_tolerant(s)


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON in model output")
    return _loads_tolerant(cleaned[start : end + 1])


def _ask_json(system: str, prompt: str, provider: dict | None = None) -> dict:
    """ask_llm + parse; on malformed JSON, one repair round-trip with the
    model's own output (small models emit stray commas / unescaped quotes).
    max_tokens=4096: reasoning models (e.g. NVIDIA muse-glimmer) spend the
    budget on reasoning_content first — 1024 leaves the answer empty."""
    text = ask_llm(system, prompt, provider=provider, max_tokens=8192)
    try:
        return _parse_json(text)
    except (ValueError, json.JSONDecodeError) as exc:
        log.warning("JSON parse failed (%s) — attempting one repair round", exc)
        repair = (
            "The following was supposed to be a single valid JSON object but "
            "is malformed. Fix it and output ONLY the corrected JSON — no "
            "fences, no commentary, no trailing commas.\n\n" + text[:3000]
        )
        fixed = ask_llm(
            "You output only strictly valid JSON. No fences, no commentary.",
            repair,
            provider=provider,
            max_tokens=8192,
        )
        try:
            return _parse_json(fixed)
        except (ValueError, json.JSONDecodeError):
            # Deterministic salvage for token-truncated output
            salvaged = salvage_truncated_json(text)
            if salvaged is not None:
                log.warning("Using salvaged truncated JSON (%d keys)", len(salvaged))
                return salvaged
            raise


def _explain_level(args: tuple) -> dict:
    level, title, files, provider = args
    if not files:
        return {**LEVEL_DEFS[level - 1], "level": level, "files": [], "quiz": []}
    try:
        data = _ask_json(
            "You are a patient senior engineer onboarding a student. "
            "Output only valid JSON.",
            _level_prompt(level, title, files),
            provider=provider,
        )
        whys = {f.get("path"): f.get("why", "") for f in data.get("files", [])
                if isinstance(f, dict)}
        quiz = []
        for q in data.get("quiz", [])[:3]:
            if not isinstance(q, dict) or not isinstance(q.get("options"), list):
                continue
            idx = q.get("answer_index", 0)
            quiz.append({
                "question": str(q.get("question", "")),
                "options": [str(o) for o in q["options"][:4]],
                "answer_index": idx if isinstance(idx, int) and 0 <= idx < len(q["options"][:4]) else 0,
                "explanation": str(q.get("explanation", "")),
            })
        return {
            **LEVEL_DEFS[level - 1],
            "level": level,
            "files": [
                {"path": n.get("label", ""), "why": whys.get(n.get("label", "")) or "Read this file next."}
                for n in files
            ],
            "quiz": quiz,
        }
    except Exception as exc:
        log.warning("Level %d explanation failed: %s", level, exc)
        return _heuristic_level(level, files)


def _good_first_issues(args: tuple) -> list[dict]:
    candidates, provider = args
    if not candidates:
        return []
    try:
        data = _ask_json(
            "You are a maintainer who writes welcoming, well-scoped issues. "
            "Output only valid JSON.",
            _gfi_prompt(candidates),
            provider=provider,
        )
        issues = []
        for i in data.get("issues", [])[:3]:
            if not isinstance(i, dict):
                continue
            issues.append({
                "title": str(i.get("title", "Improve a low-traffic file")),
                "file": str(i.get("file", "")),
                "description": str(i.get("description", "")),
                "hint": str(i.get("hint", "")),
            })
        return issues
    except Exception as exc:
        log.warning("Good First Issue generation failed: %s", exc)
        return [
            {
                "title": f"Add documentation to {n.get('label', 'a low-traffic file')}",
                "file": n.get("label", ""),
                "description": "This file has few dependents, so improving its "
                               "docstring/comments is a safe first contribution.",
                "hint": "Open the file, add a module docstring explaining its role.",
            }
            for n in candidates[:3]
        ]


def tarjan_scc(nodes: list[str], forward: dict[str, list[str]]) -> list[list[str]]:
    """Tarjan's algorithm for Strongly Connected Components (SCC).
    Partitions nodes into maximal strongly connected subgraphs.
    """
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    sccs: list[list[str]] = []

    def strongconnect(v: str):
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in forward.get(v, []):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            sccs.append(scc)

    for n in sorted(nodes):
        if n not in indices:
            strongconnect(n)

    return sccs


def condense_dag(
    nodes: list[str], forward: dict[str, list[str]]
) -> tuple[dict[int, list[str]], dict[int, list[int]], dict[str, int]]:
    """Condenses strongly connected components into a strictly acyclic DAG.
    Returns:
      (scc_members, dag_forward, node_to_scc)
    """
    sccs = tarjan_scc(nodes, forward)
    node_to_scc: dict[str, int] = {}
    scc_members: dict[int, list[str]] = {}

    for idx, scc in enumerate(sccs):
        scc_members[idx] = scc
        for node in scc:
            node_to_scc[node] = idx

    dag_forward: dict[int, list[int]] = {idx: [] for idx in range(len(sccs))}
    for u in nodes:
        u_scc = node_to_scc[u]
        for v in forward.get(u, []):
            if v in node_to_scc:
                v_scc = node_to_scc[v]
                if u_scc != v_scc and v_scc not in dag_forward[u_scc]:
                    dag_forward[u_scc].append(v_scc)

    return scc_members, dag_forward, node_to_scc


def compute_topological_layers(
    scc_members: dict[int, list[str]], dag_forward: dict[int, list[int]]
) -> dict[int, int]:
    """Compute bottom-up topological layer for each SCC in the condensation DAG.
    Leaves (out-degree 0 in dependency graph) are layer 0 (foundations/leaf utilities).
    Modules importing layer 0 are layer 1, and so on.
    """
    memo: dict[int, int] = {}

    def get_layer(scc_id: int, visited: set[int]) -> int:
        if scc_id in memo:
            return memo[scc_id]
        deps = dag_forward.get(scc_id, [])
        if not deps:
            memo[scc_id] = 0
            return 0
        visited.add(scc_id)
        max_dep = 0
        for dep in deps:
            if dep not in visited:
                max_dep = max(max_dep, 1 + get_layer(dep, visited))
        visited.remove(scc_id)
        memo[scc_id] = max_dep
        return max_dep

    for scc_id in scc_members:
        get_layer(scc_id, set())

    return memo


TIER_METADATA = [
    {
        "tier": 1,
        "name": "Foundations & Leaf Utilities",
        "badge": "L1",
        "description": "Base helper libraries, configurations, and leaf utilities with minimal internal repository dependencies.",
        "prerequisites": [],
    },
    {
        "tier": 2,
        "name": "Core Domain Models & Schemas",
        "badge": "L2",
        "description": "Domain entities, type definitions, and schema models consumed across services.",
        "prerequisites": [1],
    },
    {
        "tier": 3,
        "name": "Application Services & Handlers",
        "badge": "L3",
        "description": "Business logic orchestrators, pipelines, and internal services that integrate domain models.",
        "prerequisites": [1, 2],
    },
    {
        "tier": 4,
        "name": "Public APIs & System Entrypoints",
        "badge": "L4",
        "description": "HTTP routers, CLI entrypoints, and public interfaces that drive the application.",
        "prerequisites": [1, 2, 3],
    },
]


def _build_tier_challenges(tier_num: int, tier_files: list[dict]) -> list[dict]:
    if not tier_files:
        return []

    target = tier_files[0]
    target_path = target.get("path") or target.get("label", "module")

    challenges = []

    # Challenge 1: Architectural Role Check
    role_options = [
        "Foundation leaf utility with zero or minimal internal repo imports",
        "Core domain model or data schema consumed across services",
        "Application service orchestrating business workflows",
        "Public API route handler or CLI entrypoint",
    ]
    correct_idx = min(tier_num - 1, 3)

    challenges.append({
        "id": f"tier_{tier_num}_role",
        "title": f"Architectural Role: {target.get('label') or target_path}",
        "prompt": f"Based on the repository's topological dependency graph, what is the primary role of `{target_path}`?",
        "options": role_options,
        "answer_index": correct_idx,
        "explanation": f"`{target_path}` belongs to Tier {tier_num} ({TIER_METADATA[tier_num - 1]['name']}) based on its position in the import DAG.",
        "kind": "multiple_choice",
    })

    # Challenge 2: Prerequisite knowledge
    if tier_num == 1:
        c2_prompt = f"Why is `{target_path}` studied in Tier 1 before other application components?"
        c2_options = [
            f"`{target_path}` is a foundation module that higher tiers depend on, so mastering it first prevents confusion.",
            f"`{target_path}` is an HTTP router that starts user requests.",
            f"`{target_path}` is an obsolete legacy file.",
            f"`{target_path}` has circular dependencies with all other files.",
        ]
        c2_ans = 0
        c2_exp = "Tier 1 contains foundation and leaf modules with no internal repository dependencies."
    else:
        prev_tier = tier_num - 1
        c2_prompt = f"Before modifying or extending `{target_path}`, which tier's concepts should you master first?"
        c2_options = [
            f"Tier {prev_tier}: {TIER_METADATA[prev_tier - 1]['name']}",
            "None — this module has no architectural dependencies.",
            "Tier 4: Public APIs only.",
            "External package documentation only.",
        ]
        c2_ans = 0
        c2_exp = f"Topological learning requires mastering prerequisite layers (Tier {prev_tier}) before advancing to Tier {tier_num}."

    challenges.append({
        "id": f"tier_{tier_num}_prereq",
        "title": f"Dependency Prerequisites: Tier {tier_num}",
        "prompt": c2_prompt,
        "options": c2_options,
        "answer_index": c2_ans,
        "explanation": c2_exp,
        "kind": "multiple_choice",
    })

    return challenges


def build_topological_curriculum(graph: dict) -> dict:
    """Build a verified 4-tier student curriculum using Tarjan SCC condensation and topological layering."""
    forward_adj, reverse_adj = build_adjacency(graph)
    node_map = {n["id"]: n for n in graph.get("nodes", [])}
    file_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "file"]

    # Filter out docs, tests, and non-code files where possible
    code_files = [n for n in file_nodes if not n.get("label", "").lower().startswith(_SKIP_PREFIXES)]
    strict_code = [n for n in code_files if _is_code_file(n.get("label", ""))]
    candidates = strict_code if len(strict_code) >= 4 else (code_files or file_nodes)

    if not candidates:
        return {
            "ok": True,
            "total_tiers": 4,
            "scc_count": 0,
            "dag_edges": 0,
            "tiers": [
                {**meta, "files": [], "challenges": []}
                for meta in TIER_METADATA
            ],
        }

    candidate_ids = [n["id"] for n in candidates]
    cand_id_set = set(candidate_ids)

    # Subgraph forward adjacency
    cand_forward = {
        nid: [dst for dst in forward_adj.get(nid, []) if dst in cand_id_set]
        for nid in candidate_ids
    }

    # Tarjan SCC condensation
    scc_members, dag_forward, node_to_scc = condense_dag(candidate_ids, cand_forward)
    scc_count = len(scc_members)
    dag_edges_count = sum(len(deps) for deps in dag_forward.values())

    # Bottom-up topological layers
    scc_layers = compute_topological_layers(scc_members, dag_forward)

    max_layer = max(scc_layers.values()) if scc_layers else 0
    tier_buckets: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}

    def node_score(nid: str) -> int:
        return len(reverse_adj.get(nid, [])) * 2 + len(forward_adj.get(nid, []))

    sorted_nodes = sorted(
        candidates,
        key=lambda n: (scc_layers.get(node_to_scc.get(n["id"], 0), 0), node_score(n["id"])),
    )

    if max_layer >= 3:
        for n in candidates:
            layer = scc_layers.get(node_to_scc.get(n["id"], 0), 0)
            target_tier = min(4, max(1, layer + 1))
            tier_buckets[target_tier].append(n)
        for t in range(1, 5):
            if not tier_buckets[t] and sorted_nodes:
                tier_buckets[t].append(sorted_nodes[min(t - 1, len(sorted_nodes) - 1)])
    else:
        n_count = len(sorted_nodes)
        for idx, n in enumerate(sorted_nodes):
            t = min(4, max(1, int((idx / max(1, n_count)) * 4) + 1))
            tier_buckets[t].append(n)

    tiers = []
    for meta in TIER_METADATA:
        t_num = meta["tier"]
        bucket_nodes = tier_buckets.get(t_num, [])[:5]

        tier_files = []
        for n in bucket_nodes:
            lbl = n.get("label", n["id"])
            scc_id = node_to_scc.get(n["id"])
            scc_group = [node_map[m].get("label", m) for m in scc_members.get(scc_id, []) if m in node_map]
            tier_files.append({
                "path": lbl,
                "label": lbl.split("/")[-1],
                "role": meta["name"],
                "in_degree": len(reverse_adj.get(n["id"], [])),
                "out_degree": len(forward_adj.get(n["id"], [])),
                "scc_group": scc_group if len(scc_group) > 1 else [],
                "why": f"Part of {meta['name']} (layer {scc_layers.get(scc_id, 0)}).",
            })

        challenges = _build_tier_challenges(t_num, tier_files)

        tiers.append({
            **meta,
            "files": tier_files,
            "challenges": challenges,
        })

    return {
        "ok": True,
        "total_tiers": 4,
        "scc_count": scc_count,
        "dag_edges": dag_edges_count,
        "tiers": tiers,
    }


def verify_curriculum_challenge(
    curriculum: dict, tier: int, challenge_id: str, answer: str
) -> dict:
    """Graph-graded challenge verification."""
    target_tier = None
    for t in curriculum.get("tiers", []):
        if t.get("tier") == tier:
            target_tier = t
            break

    if not target_tier:
        return {
            "ok": False,
            "correct": False,
            "feedback": f"Tier {tier} not found in curriculum.",
            "next_tier": tier,
            "unlocked": False,
        }

    target_challenge = None
    for ch in target_tier.get("challenges", []):
        if ch.get("id") == challenge_id:
            target_challenge = ch
            break

    if not target_challenge:
        return {
            "ok": True,
            "correct": True,
            "feedback": "Challenge verified successfully.",
            "next_tier": min(4, tier + 1),
            "unlocked": True,
        }

    ans_str = str(answer).strip().lower()
    correct_idx = target_challenge.get("answer_index", 0)
    options = target_challenge.get("options", [])
    correct_option = options[correct_idx].strip().lower() if 0 <= correct_idx < len(options) else ""

    letter_map = {"a": 0, "b": 1, "c": 2, "d": 3}
    is_correct = False

    if ans_str == str(correct_idx):
        is_correct = True
    elif ans_str in letter_map and letter_map[ans_str] == correct_idx:
        is_correct = True
    elif correct_option and (ans_str == correct_option or ans_str in correct_option or correct_option in ans_str):
        is_correct = True

    if is_correct:
        next_t = min(4, tier + 1)
        return {
            "ok": True,
            "correct": True,
            "feedback": f"Correct! {target_challenge.get('explanation', '')}",
            "next_tier": next_t,
            "unlocked": True,
        }
    else:
        return {
            "ok": True,
            "correct": False,
            "feedback": f"Not quite. Review the dependency structure of Tier {tier} and try again.",
            "next_tier": tier,
            "unlocked": False,
        }


def build_onboarding(graph: dict, provider: dict | None = None) -> dict:
    """Full student onboarding payload: 3 levels (why + quiz) + 3 GFIs + topological curriculum."""
    rows = rank_rows(graph)

    # Level buckets per the spec: L1 = Row 1, L2 = Rows 2-3, L3 = Rows 4-5
    level_files = {
        1: rows.get(1, []),
        2: (rows.get(2, []) + rows.get(3, []))[:_MAX_PER_LEVEL],
        3: (rows.get(4, []) + rows.get(5, []))[:_MAX_PER_LEVEL],
    }
    gfi_candidates = (rows.get(4, []) + rows.get(5, []))[-_MAX_PER_LEVEL:] or level_files[3]

    with ThreadPoolExecutor(max_workers=4) as pool:
        level_futures = [
            pool.submit(_explain_level,
                        (lv, LEVEL_DEFS[lv - 1]["title"], level_files[lv], provider))
            for lv in (1, 2, 3)
        ]
        gfi_future = pool.submit(_good_first_issues, (gfi_candidates, provider))
        levels = [f.result() for f in level_futures]
        issues = gfi_future.result()

    curriculum = build_topological_curriculum(graph)

    return {
        "ok": True,
        "levels": levels,
        "good_first_issues": issues,
        "curriculum": curriculum,
        "tiers": curriculum.get("tiers", []),
    }
