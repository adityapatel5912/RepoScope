"""
backend/citation_verifier.py
Phase 5: Verified chat citations (V2.6).

Pure deterministic AST citation verifier.
Checks every citation against the repository index and disk.
Snaps near misses (within 5 lines) to real symbol ranges.
Marks ranges spanning multiple symbols as partial.
Visibly marks hallucinations and missing paths as unverified.
Enforces path-traversal safety: previews never read outside repo root.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional


# Pattern for citations in markdown:
# 1) [path/file.py:10-20] or [path/file.py:10] or [path/file.py]
BRACKET_CITATION_RE = re.compile(
    r"\[([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+)(?::(\d+)(?:-(\d+))?)?\]"
)

# 2) `path/file.py:10-20` or `path/file.py:10` or `path/file.py`
BACKTICK_CITATION_RE = re.compile(
    r"`([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+)(?::(\d+)(?:-(\d+))?)?`"
)

# 3) Plain table/line citation: path/file.py:10-20 or path/file.py:10
PLAIN_CITATION_RE = re.compile(
    r"(?:^|[\s|(])([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_]+):(\d+)(?:-(\d+))?(?=[\s|),;]|$)"
)


def normalize_rel_path(raw_path: str) -> str:
    """Normalize file path to POSIX relative form."""
    cleaned = raw_path.strip().replace("\\", "/")
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return os.path.normpath(cleaned).replace("\\", "/")


def is_safe_repo_path(rel_path: str, repo_root: Path) -> bool:
    """Check that the path does not escape the repository root."""
    if os.path.isabs(rel_path):
        return False
    if rel_path.startswith("../") or rel_path == "..":
        return False
    try:
        root_resolved = repo_root.resolve()
        target_resolved = (root_resolved / rel_path).resolve()
        return (
            target_resolved == root_resolved
            or root_resolved in target_resolved.parents
        )
    except Exception:
        return False


def get_preview(file_path: Path, start_line: int, end_line: int, max_lines: int = 15) -> str:
    """Read a narrow snippet (up to max_lines) from file safely."""
    try:
        if not file_path.is_file():
            return ""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        if start_line < 1 or start_line > total:
            return ""
        s_idx = max(0, start_line - 1)
        e_idx = min(total, max(s_idx + 1, end_line if end_line else s_idx + 1))
        if e_idx - s_idx > max_lines:
            e_idx = s_idx + max_lines
        return "".join(lines[s_idx:e_idx]).rstrip()
    except Exception:
        return ""


def get_file_line_count(file_path: Path) -> int:
    """Return line count of file, or 0 if unreadable."""
    try:
        if not file_path.is_file():
            return 0
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def extract_symbols_for_file(
    rel_path: str,
    graph: Optional[Mapping[str, Any]],
    file_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """
    Extract symbol list for a file from the graph or parse on the fly.
    Returns list of dicts: {name, line, end_line, kind, node_id}.
    """
    symbols: list[dict[str, Any]] = []

    # 1. Look in provided graph nodes
    if graph and isinstance(graph.get("nodes"), list):
        norm_rel = normalize_rel_path(rel_path)
        for node in graph["nodes"]:
            n_file = normalize_rel_path(str(node.get("file") or ""))
            n_type = str(node.get("type") or "")
            n_id = str(node.get("id") or "")
            if n_file == norm_rel or n_id.startswith(f"func:{norm_rel}:") or n_id.startswith(f"class:{norm_rel}:"):
                if n_type in ("function", "class", "method"):
                    s_line = int(node.get("line") or 0)
                    s_end = int(node.get("end_line") or s_line)
                    symbols.append({
                        "name": str(node.get("label") or ""),
                        "line": s_line,
                        "end_line": max(s_line, s_end),
                        "kind": n_type,
                        "node_id": n_id,
                    })

    if symbols:
        symbols.sort(key=lambda s: (s["line"], s["end_line"]))
        return symbols

    # 2. Fallback: parse file on the fly
    if file_path and file_path.is_file():
        try:
            from graph_builder import parse_bytes
            suffix = file_path.suffix.lower()
            with open(file_path, "rb") as f:
                content = f.read()
            facts = parse_bytes(content, rel_path, suffix)
            for s in facts.symbols:
                s_name = s.name
                s_line = s.line
                s_end = s.end_line or s_line
                s_kind = s.kind
                prefix = "func" if s_kind == "function" else "class"
                symbols.append({
                    "name": s_name,
                    "line": s_line,
                    "end_line": max(s_line, s_end),
                    "kind": s_kind,
                    "node_id": f"{prefix}:{rel_path}:{s_name}",
                })
            symbols.sort(key=lambda s: (s["line"], s["end_line"]))
        except Exception:
            pass

    return symbols


def verify_citation(
    path: str,
    line: Optional[int] = None,
    end_line: Optional[int] = None,
    raw: Optional[str] = None,
    repo_root: Optional[Path | str] = None,
    graph: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """
    Verify a single citation against AST symbols and disk.
    Pure deterministic; never calls an LLM.
    """
    root = Path(repo_root or ".").resolve()
    norm_path = normalize_rel_path(path)
    raw_str = raw or f"[{norm_path}{f':{line}' if line else ''}{f'-{end_line}' if end_line and end_line != line else ''}]"

    result: dict[str, Any] = {
        "raw": raw_str,
        "path": norm_path,
        "start_line": line,
        "end_line": end_line,
        "symbol": None,
        "node_id": None,
        "verified": False,
        "confidence": 0.0,
        "reason": "unverified",
        "preview": "",
    }

    # 1. Path safety check
    if not is_safe_repo_path(norm_path, root):
        result["reason"] = "path escape"
        return result

    file_path = root / norm_path
    file_exists = file_path.is_file()

    graph_has_file = False
    if graph and isinstance(graph.get("nodes"), list):
        for n in graph["nodes"]:
            if n.get("type") == "file" and normalize_rel_path(str(n.get("label") or n.get("id", "").replace("file:", ""))) == norm_path:
                graph_has_file = True
                break

    if not file_exists and not graph_has_file:
        result["reason"] = "file not found"
        return result

    total_lines = get_file_line_count(file_path) if file_exists else 0

    # 2. File-only citation (no line specified)
    if line is None:
        result["verified"] = True
        result["confidence"] = 1.0
        result["node_id"] = f"file:{norm_path}"
        result["reason"] = "file only"
        result["start_line"] = 1
        result["end_line"] = min(15, total_lines) if total_lines else 15
        if file_exists:
            result["preview"] = get_preview(file_path, 1, result["end_line"])
        return result

    start_line = int(line)
    req_end = int(end_line) if end_line is not None else start_line
    result["start_line"] = start_line
    result["end_line"] = req_end

    # Check bounds if file exists
    if file_exists and total_lines > 0 and (start_line < 1 or start_line > total_lines):
        result["reason"] = "line out of range"
        return result

    # 3. Symbol matching & snapping
    symbols = extract_symbols_for_file(norm_path, graph, file_path if file_exists else None)

    # Check for overlapping symbols
    overlapping: list[dict[str, Any]] = []
    for s in symbols:
        if not (req_end < s["line"] or start_line > s["end_line"]):
            overlapping.append(s)

    # Multi-symbol span -> marked partial
    if len(overlapping) >= 2:
        names = [s["name"] for s in overlapping]
        result["verified"] = True
        result["confidence"] = 0.5
        result["reason"] = "partial"
        result["symbol"] = ", ".join(names)
        result["node_id"] = overlapping[0]["node_id"]
        if file_exists:
            result["preview"] = get_preview(file_path, start_line, req_end)
        return result

    # Single overlapping symbol
    if len(overlapping) == 1:
        sym = overlapping[0]
        if start_line == sym["line"] and req_end == sym["end_line"]:
            result["verified"] = True
            result["confidence"] = 1.0
            result["reason"] = "exact symbol range"
            result["symbol"] = sym["name"]
            result["node_id"] = sym["node_id"]
            if file_exists:
                result["preview"] = get_preview(file_path, sym["line"], sym["end_line"])
            return result

        # Near-miss start within 5 lines of symbol start
        diff = abs(start_line - sym["line"])
        if diff <= 5:
            result["verified"] = True
            result["confidence"] = 0.9
            result["reason"] = "snapped"
            result["start_line"] = sym["line"]
            result["end_line"] = sym["end_line"]
            result["symbol"] = sym["name"]
            result["node_id"] = sym["node_id"]
            if file_exists:
                result["preview"] = get_preview(file_path, sym["line"], sym["end_line"])
            return result

        # Interior of symbol
        result["verified"] = True
        result["confidence"] = 0.8
        result["reason"] = "exact symbol range"
        result["symbol"] = sym["name"]
        result["node_id"] = sym["node_id"]
        if file_exists:
            result["preview"] = get_preview(file_path, start_line, req_end)
        return result

    # No overlapping symbol, check near-miss within 5 lines of any symbol start
    # but only if not line 1 when symbol starts deeper
    near_symbol: Optional[dict[str, Any]] = None
    min_dist = 6
    for s in symbols:
        dist = abs(start_line - s["line"])
        if dist <= 5 and dist < min_dist:
            min_dist = dist
            near_symbol = s

    if near_symbol is not None:
        result["verified"] = True
        result["confidence"] = 0.9
        result["reason"] = "snapped"
        result["start_line"] = near_symbol["line"]
        result["end_line"] = near_symbol["end_line"]
        result["symbol"] = near_symbol["name"]
        result["node_id"] = near_symbol["node_id"]
        if file_exists:
            result["preview"] = get_preview(file_path, near_symbol["line"], near_symbol["end_line"])
        return result

    # 4. Valid file line with no symbol
    result["verified"] = True
    result["confidence"] = 1.0
    result["reason"] = "file line"
    result["node_id"] = f"file:{norm_path}"
    if file_exists:
        result["preview"] = get_preview(file_path, start_line, req_end)

    return result


def extract_raw_citations(text: str) -> list[tuple[str, str, Optional[int], Optional[int]]]:
    """
    Extract citation tuples (raw, path, start_line, end_line) from text in document order.
    """
    matches: list[tuple[int, str, str, Optional[int], Optional[int]]] = []
    seen_spans: list[tuple[int, int]] = []

    def span_overlaps(s_start: int, s_end: int) -> bool:
        return any(not (s_end <= s[0] or s_start >= s[1]) for s in seen_spans)

    # 1. Bracketed: [path/file.ext:10-20]
    for m in BRACKET_CITATION_RE.finditer(text):
        span = m.span()
        seen_spans.append(span)
        raw = m.group(0)
        path = m.group(1)
        start_line = int(m.group(2)) if m.group(2) else None
        end_line = int(m.group(3)) if m.group(3) else (start_line if start_line else None)
        matches.append((m.start(), raw, path, start_line, end_line))

    # 2. Backticked: `path/file.ext:10-20`
    for m in BACKTICK_CITATION_RE.finditer(text):
        span = m.span()
        if span_overlaps(span[0], span[1]):
            continue
        seen_spans.append(span)
        raw = m.group(0)
        path = m.group(1)
        start_line = int(m.group(2)) if m.group(2) else None
        end_line = int(m.group(3)) if m.group(3) else (start_line if start_line else None)
        matches.append((m.start(), raw, path, start_line, end_line))

    # 3. Plain table/line: path/file.ext:10
    for m in PLAIN_CITATION_RE.finditer(text):
        span = m.span()
        if span_overlaps(span[0], span[1]):
            continue
        raw = m.group(0).strip()
        path = m.group(1)
        if "://" in path or path.startswith("http") or path.endswith((".com", ".org", ".net")):
            continue
        seen_spans.append(span)
        start_line = int(m.group(2)) if m.group(2) else None
        end_line = int(m.group(3)) if m.group(3) else (start_line if start_line else None)
        matches.append((m.start(), raw, path, start_line, end_line))

    # Sort in order of appearance in text
    matches.sort(key=lambda x: x[0])

    # Deduplicate while preserving first appearance
    seen_raw: set[str] = set()
    result = []
    for _, raw, path, s_l, e_l in matches:
        if raw not in seen_raw:
            seen_raw.add(raw)
            result.append((raw, path, s_l, e_l))
    return result


def verify_citations_in_text(
    text: str,
    repo_root: Optional[Path | str] = None,
    graph: Optional[Mapping[str, Any]] = None,
) -> list[dict[str, Any]]:
    """
    Extract and verify all citations from LLM answer text.
    """
    citations: list[dict[str, Any]] = []
    extracted = extract_raw_citations(text)
    for raw, path, s_line, e_line in extracted:
        verified = verify_citation(
            path=path,
            line=s_line,
            end_line=e_line,
            raw=raw,
            repo_root=repo_root,
            graph=graph,
        )
        citations.append(verified)

    return citations
