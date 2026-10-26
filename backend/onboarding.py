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
from concurrent.futures import ThreadPoolExecutor

from graph_utils import build_adjacency
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


def _node_meta(n: dict) -> dict:
    return {
        "path": n.get("label", ""),
        "language": n.get("language", ""),
        "symbols": "",  # filled by the LLM answer, not the graph
    }


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


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON in model output")
    return json.loads(cleaned[start : end + 1])


def _explain_level(args: tuple) -> dict:
    level, title, files, provider = args
    if not files:
        return {**LEVEL_DEFS[level - 1], "level": level, "files": [], "quiz": []}
    try:
        data = _parse_json(ask_llm(
            "You are a patient senior engineer onboarding a student. "
            "Output only valid JSON.",
            _level_prompt(level, title, files),
            graph_context=json.dumps([_node_meta(n) for n in files])[:2000],
            provider=provider,
        ))
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
        data = _parse_json(ask_llm(
            "You are a maintainer who writes welcoming, well-scoped issues. "
            "Output only valid JSON.",
            _gfi_prompt(candidates),
            graph_context="",
            provider=provider,
        ))
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


def build_onboarding(graph: dict, provider: dict | None = None) -> dict:
    """Full student onboarding payload: 3 levels (why + quiz) + 3 GFIs."""
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

    return {
        "ok": True,
        "levels": levels,
        "good_first_issues": issues,
    }
