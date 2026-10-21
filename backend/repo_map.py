"""
repo_map.py
A compact, LLM-ready map of a repository.

Milestone 8.1.

The idea comes from `aider`: before an agent edits a file, it needs to
know WHICH files matter and WHAT is in them. Reading the whole repository
to find that out is expensive — and the cost is paid on every request.

RepoScope already knows the answer. It has parsed every file, resolved
every symbol, and computed a PageRank over the dependency graph. So the
map is not a summary of the code; it is the graph, rendered for a reader
that is not looking at a canvas:

    backend/graph_builder.py :: build_graph_from_repo(root, cache), assemble_graph(facts) :: backend
    frontend/src/App.tsx :: App() :: client

Files are ranked by PageRank — the same score the pyramid uses — and
added to the map until the token budget is spent. The lowest-ranked files
are dropped first, because a file nobody imports and that imports nobody
is the least useful thing to put in an agent's context.

The format is deliberately plain text. It is meant to be pasted into a
prompt, so it must survive a copy-and-paste without escaping.
"""
from __future__ import annotations

import logging
from typing import Callable, Iterable

from arch_rules import classify
from token_metrics import Tokenizer, estimate_tokens, reduction_pct

log = logging.getLogger("reposcope.repo_map")

#: The default budget. 8k tokens is roughly one context window's worth of
#: orientation, which is enough to find the right file and then read it.
DEFAULT_BUDGET_TOKENS = 8_000

#: How many symbols are listed per file. A file with forty exports does
#: not need all forty in the map — the top few are what an agent looks
#: for, and the rest is noise that costs tokens.
DEFAULT_MAX_SYMBOLS = 6

#: The header line of the plain-text map.
MAP_HEADER = "# RepoScope repo map"


def _compact_signature(signature: str, name: str) -> str:
    """
    Reduce a raw definition to `name(params)`.

    The parsers store the definition's source text, which for Python is
    `def foo(a, b) -> dict:` and for Go is `func Foo(a int) error {`. The
    map wants the name and the parameters, without the return type or the
    body.
    """
    if not signature:
        return name
    open_paren = signature.find("(")
    if open_paren == -1:
        return name
    depth = 0
    end = -1
    for index in range(open_paren, len(signature)):
        char = signature[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end == -1:
        return name
    params = " ".join(signature[open_paren + 1:end].split())
    return f"{name}({params})"


def _symbol_lines(graph: dict, max_symbols: int) -> dict[str, list[tuple[dict, str]]]:
    """Map each file to the list of symbol descriptions it contributes."""
    per_file: dict[str, list[tuple[dict, str]]] = {}
    for node in graph.get("nodes", []) or []:
        if node.get("type") not in ("function", "class"):
            continue
        file_path = node.get("file")
        if not file_path:
            continue
        name = str(node.get("label", ""))
        description = _compact_signature(str(node.get("signature", "")), name)
        per_file.setdefault(file_path, []).append((node, description))
    return per_file


def _rank_files(graph: dict) -> list[dict]:
    """
    The file nodes, ranked by PageRank.

    A file's score is its own PageRank, plus a share of the score of the
    symbols it defines — a file whose central function is a hub is more
    important than a file that merely contains many trivial helpers.
    """
    file_nodes: list[dict] = []
    symbol_scores: dict[str, float] = {}
    for node in graph.get("nodes", []) or []:
        if node.get("type") in ("function", "class") and node.get("file"):
            path = str(node["file"])
            symbol_scores[path] = symbol_scores.get(path, 0.0) + float(node.get("pagerank") or 0.0)

    for node in graph.get("nodes", []) or []:
        if node.get("type") != "file":
            continue
        path = str(node.get("label") or node.get("id", "").removeprefix("file:"))
        score = float(node.get("pagerank") or 0.0) + symbol_scores.get(path, 0.0)
        file_nodes.append({"path": path, "score": score, "node": node})

    # Deterministic: score descending, then path ascending.
    file_nodes.sort(key=lambda item: (-item["score"], item["path"]))
    return file_nodes


def build_repo_map(
    graph: dict,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    root: str | None = None,
    tokenizer: Tokenizer | None = None,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
) -> dict:
    """
    Build the repo map.

    Returns a dict with the plain-text map, a JSON variant, the token
    counts, and the files that were included.
    """
    tokenizer = tokenizer or estimate_tokens
    budget = max(500, int(budget_tokens))

    symbols_by_file = _symbol_lines(graph, max_symbols)
    ranked = _rank_files(graph)

    lines: list[str] = []
    entries: list[dict] = []
    used = 0
    budget_exhausted = False

    for item in ranked:
        path = item["path"]
        node = item["node"]
        layer = classify(str(node.get("id", "")), str(node.get("label", path)))

        raw_symbols = symbols_by_file.get(path, [])
        # Exported symbols first, then the most complex — those are the
        # ones a reader is looking for.
        ordered = sorted(
            raw_symbols,
            key=lambda pair: (
                0 if pair[0].get("exported") else 1,
                -int(pair[0].get("complexity") or 1),
                str(pair[0].get("label", "")),
            ),
        )
        descriptions = [description for _n, description in ordered[:max_symbols]]
        line = f"{path} :: {', '.join(descriptions)} :: {layer}" if descriptions else f"{path} :: :: {layer}"

        cost = tokenizer(line) + 1  # +1 for the newline
        if used + cost > budget and entries:
            budget_exhausted = True
            continue

        lines.append(line)
        entries.append({
            "path": path,
            "layer": layer,
            "score": round(item["score"], 8),
            "symbols": descriptions,
            "tokens": cost,
        })
        used += cost

    header = f"{MAP_HEADER} — {len(entries)} of {len(ranked)} files, ~{used} tokens"
    text = "\n".join([header, *lines])

    return {
        "text": text,
        "header": header,
        "entries": entries,
        "tokens": used,
        "budget_tokens": budget,
        "files_included": len(entries),
        "files_total": len(ranked),
        "budget_exhausted": budget_exhausted,
    }


def build_repo_map_with_metrics(
    graph: dict,
    root: str | None = None,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    tokenizer: Tokenizer | None = None,
) -> dict:
    """
    The repo map, plus the context-savings comparison.

    The baseline is what an agent would pay to read the whole repository.
    The map is what it pays to read RepoScope's map instead. The
    difference is the number the product is built around, so it is
    measured, not asserted.
    """
    tokenizer = tokenizer or estimate_tokens
    repo_map = build_repo_map(graph, budget_tokens=budget_tokens, root=root, tokenizer=tokenizer)

    baseline = {"tokens": 0, "files_measured": 0, "files_total": 0, "truncated": False}
    if root:
        from token_metrics import full_context_tokens

        baseline = full_context_tokens(root, tokenizer=tokenizer)

    map_tokens = tokenizer(repo_map["text"])
    full_tokens = int(baseline.get("tokens") or 0)

    return {
        **repo_map,
        "tokens": map_tokens,
        "full_context_tokens": full_tokens,
        "reduction_pct": reduction_pct(map_tokens, full_tokens),
        "baseline": baseline,
        "root": root,
    }


def format_map_for_prompt(repo_map: dict, max_chars: int = 20_000) -> str:
    """The map, truncated to a character budget, for a prompt."""
    text = repo_map.get("text", "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit("\n", 1)[0] + "\n… (map truncated)"
