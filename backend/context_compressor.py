"""
backend/context_compressor.py
Deterministic context compression and AST skeleton generation for RepoScope.

V2.5 Phase 4.

Provides:
- AST skeleton generation omitting symbol bodies.
- Deterministic context packing with strict token budget accounting.
- SHA-256 delta hashing excluding volatile and format metadata.
- Lazy TOON (Token-Oriented Object Notation) adapter with kill-switch support.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Sequence

try:
    from token_metrics import estimate_tokens
    from onboarding import rank_rows
except ImportError:
    from backend.token_metrics import estimate_tokens
    from backend.onboarding import rank_rows

CONTEXT_SCHEMA_VERSION = 1
DEFAULT_BUDGET_TOKENS = 8000
MIN_BUDGET_TOKENS = 500
MAX_BUDGET_TOKENS = 200000
MAX_BODY_LINES = 120
MAX_BODY_CHARS = 12000

DROP_HASH_KEYS = {
    "format",
    "since_hash",
    "hash",
    "root",
    "tokens",
    "token_count",
    "estimated_tokens",
    "full_context_tokens",
    "reduction_pct",
    "saving_pct",
    "generated_at",
}


class ContextError(ValueError):
    """Raised when context pack generation or encoding encounters an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def normalize_signature(signature: str) -> str:
    """Normalize signature by collapsing all whitespace to single spaces and capping at 500 chars."""
    if not signature:
        return ""
    collapsed = " ".join(signature.split())
    return collapsed[:500]


def resolve_context_path(root: str | Path, relpath: str) -> Path | None:
    """Safely resolve relpath inside root.

    Rejects absolute paths, drive-qualified paths, and any component equal to '..'
    as outside-root. Never reads outside the repository root.
    """
    if not root or not relpath:
        return None

    # Reject Windows drive letters, UNC, or leading separators
    norm = relpath.replace("\\", "/").strip()
    if ":" in relpath or norm.startswith("/") or norm.startswith("\\"):
        return None

    p = Path(relpath)
    if p.is_absolute():
        return None

    for part in p.parts:
        if part == "..":
            return None

    try:
        root_resolved = Path(root).resolve()
        target_resolved = (root_resolved / p).resolve()
        target_resolved.relative_to(root_resolved)
        return target_resolved
    except (ValueError, RuntimeError):
        return None


def _find_file_node(graph: dict, requested_path: str) -> tuple[dict | None, str | None, list[dict]]:
    """Resolve an explicit path by exact file:<path>, then exact label/path, then unique suffix.

    Returns (matched_node, error_code, candidates).
    error_code is None, 'ambiguous', or 'not-indexed'.
    """
    clean_p = requested_path.replace("\\", "/").strip().lstrip("/")
    file_nodes = [n for n in graph.get("nodes", []) if n.get("type") == "file"]

    # 1. Exact node id match
    id_target = f"file:{clean_p}"
    for n in file_nodes:
        if n.get("id") == id_target:
            return n, None, [n]

    # 2. Exact label or path match
    exact_matches = [
        n for n in file_nodes
        if (n.get("path") and n.get("path").replace("\\", "/").strip() == clean_p) or
           (n.get("label") and n.get("label").replace("\\", "/").strip() == clean_p)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0], None, exact_matches
    if len(exact_matches) > 1:
        return None, "ambiguous", exact_matches

    # 3. Unique file-label suffix
    suffix_matches = [
        n for n in file_nodes
        if (n.get("path") and (
            n.get("path").replace("\\", "/").endswith("/" + clean_p) or
            n.get("path").replace("\\", "/").strip() == clean_p
        )) or
        (n.get("label") and (
            n.get("label").replace("\\", "/").endswith("/" + clean_p) or
            n.get("label").replace("\\", "/").strip() == clean_p
        ))
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0], None, suffix_matches
    if len(suffix_matches) > 1:
        return None, "ambiguous", suffix_matches

    return None, "not-indexed", []


def _read_signature_from_file(root: str | Path | None, relpath: str, line_no: int) -> str:
    """Read the first non-empty line at line_no from the source file."""
    if not root or line_no <= 0:
        return ""
    target = resolve_context_path(root, relpath)
    if not target or not target.is_file():
        return ""
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        if 1 <= line_no <= len(lines):
            line_text = lines[line_no - 1].strip()
            if line_text:
                return normalize_signature(line_text)
    except Exception:
        pass
    return ""


def build_ast_skeleton(
    graph: dict,
    root: str | None,
    file_path: str,
    max_symbols: int = 200,
) -> dict:
    """Build an AST skeleton for a single file. Never returns bodies."""
    if not graph or not graph.get("nodes"):
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "available": False,
            "reason": "the index is empty",
        }

    # Validate path safety
    norm = file_path.replace("\\", "/").strip()
    if ":" in file_path or norm.startswith("/") or any(part == ".." for part in Path(file_path).parts):
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "available": False,
            "reason": "path outside root",
            "file": file_path,
        }

    matched, err, candidates = _find_file_node(graph, file_path)
    if err == "ambiguous":
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "available": False,
            "reason": f"path '{file_path}' is ambiguous",
            "candidates": [c.get("path") or c.get("label") for c in candidates],
        }
    if err == "not-indexed" or matched is None:
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "available": False,
            "reason": f"file '{file_path}' is not indexed",
            "file": file_path,
        }

    canonical_path = matched.get("path") or matched.get("label") or file_path
    role = matched.get("role", "utility")
    pillar = matched.get("pillar", "backend")
    route_count = int(matched.get("route_count", 0))

    # Collect symbols
    raw_symbols = [
        n for n in graph.get("nodes", [])
        if n.get("type") != "file" and (
            n.get("file") == canonical_path or n.get("path") == canonical_path
        )
    ]
    raw_symbols.sort(
        key=lambda s: (
            int(s.get("line") or 0),
            s.get("label") or s.get("name") or "",
            s.get("type") or s.get("kind") or "",
        )
    )

    clamped_max = max(1, min(1000, max_symbols))
    total_symbols = len(raw_symbols)
    if total_symbols > clamped_max:
        symbols_slice = raw_symbols[:clamped_max]
        truncated = True
    else:
        symbols_slice = raw_symbols
        truncated = False

    formatted_symbols = []
    for s in symbols_slice:
        sig = normalize_signature(s.get("signature") or "")
        if not sig:
            sig = _read_signature_from_file(root, canonical_path, int(s.get("line") or 0))
        formatted_symbols.append({
            "name": s.get("label") or s.get("name") or "",
            "kind": s.get("type") or s.get("kind") or "",
            "line": int(s.get("line") or 0),
            "end_line": int(s.get("end_line") or s.get("line") or 0),
            "exported": bool(s.get("exported", False)),
            "complexity": int(s.get("complexity") or 1),
            "role": s.get("role") or role,
            "signature": sig,
        })

    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "available": True,
        "root": str(Path(root).resolve()) if root else "",
        "file": canonical_path,
        "role": role,
        "pillar": pillar,
        "route_count": route_count,
        "symbols": formatted_symbols,
        "truncated": truncated,
        "counts": {
            "symbols": total_symbols,
            "returned": len(formatted_symbols),
        },
    }


def _strip_hash_keys(obj: Any) -> Any:
    """Recursively strip keys excluded from the hash."""
    if isinstance(obj, dict):
        return {k: _strip_hash_keys(v) for k, v in obj.items() if k not in DROP_HASH_KEYS}
    if isinstance(obj, list):
        return [_strip_hash_keys(item) for item in obj]
    return obj


def context_hash(payload: dict) -> str:
    """Compute deterministic SHA-256 hash of payload excluding metadata/token fields."""
    cleaned = _strip_hash_keys(copy.deepcopy(payload))
    serialized = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def encode_json(payload: dict) -> str:
    """Encode payload to compact JSON without extra whitespace."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _load_toon() -> Any:
    """Lazily load toon_format or raise ContextError."""
    if os.environ.get("REPOSCOPE_TOON") == "0":
        raise ContextError(400, "TOON output is disabled (REPOSCOPE_TOON=0). Use format=json.")
    try:
        import toon_format
        return toon_format
    except ImportError:
        raise ContextError(
            400,
            "TOON output requires the optional dependency. Install with: pip install reposcope[toon]",
        )


def encode_toon(payload: dict) -> str:
    """Encode payload to TOON format."""
    tf = _load_toon()
    normalized = json.loads(json.dumps(payload))
    return tf.encode(normalized, sort_keys=True)


def decode_toon(text: str) -> dict:
    """Decode text from TOON format."""
    tf = _load_toon()
    return tf.decode(text)


def toon_available() -> bool:
    """Return True if TOON format is available and enabled."""
    if os.environ.get("REPOSCOPE_TOON") == "0":
        return False
    try:
        import toon_format  # noqa: F401
        return True
    except ImportError:
        return False


def _make_neutralized(
    detail: str,
    budget: int,
    files: list[dict],
    omitted: list[dict],
    caps: list[dict],
    truncated: bool,
    files_requested: int,
) -> dict:
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "available": True,
        "detail": detail,
        "budget": budget,
        "files": files,
        "omitted": omitted,
        "caps": caps,
        "truncated": truncated,
        "counts": {
            "files_included": len(files),
            "files_requested": files_requested,
            "symbols_included": sum(len(f.get("symbols", [])) for f in files),
        },
    }


def build_context_pack(
    graph: dict,
    root: str | None,
    paths: str | Sequence[str] | None = None,
    detail: str = "skeleton",
    budget: int = DEFAULT_BUDGET_TOKENS,
    since_hash: str | None = None,
) -> dict:
    """Build a deterministic context pack fitting within budget tokens."""
    if detail not in ("skeleton", "full"):
        raise ContextError(400, f"Invalid detail: '{detail}'. Must be 'skeleton' or 'full'.")

    if not isinstance(budget, int) or budget < MIN_BUDGET_TOKENS or budget > MAX_BUDGET_TOKENS:
        raise ContextError(
            400,
            f"Invalid budget: {budget}. Must be between {MIN_BUDGET_TOKENS} and {MAX_BUDGET_TOKENS} tokens.",
        )

    if not graph or not graph.get("nodes"):
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "available": False,
            "reason": "the index is empty",
        }

    # Resolve requested candidates
    candidates: list[str] = []
    if paths is None or (isinstance(paths, str) and not paths.strip()) or (isinstance(paths, (list, tuple)) and not paths):
        rows = rank_rows(graph)
        for r in (1, 2, 3, 4, 5):
            for node in rows.get(r, []):
                p = node.get("path") or node.get("label")
                if p and p not in candidates:
                    candidates.append(p)
        files_requested = len(candidates)
    else:
        if isinstance(paths, str):
            raw_parts = [p.strip() for p in paths.split(",")]
        else:
            raw_parts = [str(p).strip() for p in paths]
        for p in raw_parts:
            if p and p not in candidates:
                candidates.append(p)
        files_requested = len(candidates)

    included_files: list[dict] = []
    omitted: list[dict] = []
    caps: list[dict] = []

    for cand_path in candidates:
        norm = cand_path.replace("\\", "/").strip()
        if ":" in cand_path or norm.startswith("/") or any(part == ".." for part in Path(cand_path).parts):
            omitted.append({"path": cand_path, "reason": "outside-root"})
            continue

        matched, err, match_candidates = _find_file_node(graph, cand_path)
        if err == "ambiguous":
            omitted.append({"path": cand_path, "reason": "ambiguous"})
            continue
        if err == "not-indexed" or matched is None:
            omitted.append({"path": cand_path, "reason": "not-indexed"})
            continue

        canonical_path = matched.get("path") or matched.get("label") or cand_path
        file_role = matched.get("role", "utility")
        file_pillar = matched.get("pillar", "backend")
        file_route_count = int(matched.get("route_count", 0))

        raw_symbols = [
            n for n in graph.get("nodes", [])
            if n.get("type") != "file" and (
                n.get("file") == canonical_path or n.get("path") == canonical_path
            )
        ]
        raw_symbols.sort(
            key=lambda s: (
                int(s.get("line") or 0),
                s.get("label") or s.get("name") or "",
                s.get("type") or s.get("kind") or "",
            )
        )

        file_lines: list[str] | None = None
        file_unreadable = False
        if detail == "full":
            resolved = resolve_context_path(root, canonical_path) if root else None
            if resolved and resolved.is_file():
                try:
                    file_lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                except Exception:
                    file_lines = None
                    file_unreadable = True
            else:
                file_unreadable = True

        candidate_caps: list[dict] = []
        file_symbols: list[dict] = []
        for s in raw_symbols:
            sig = normalize_signature(s.get("signature") or "")
            if not sig:
                sig = _read_signature_from_file(root, canonical_path, int(s.get("line") or 0))
            sym_dict = {
                "name": s.get("label") or s.get("name") or "",
                "kind": s.get("type") or s.get("kind") or "",
                "line": int(s.get("line") or 0),
                "end_line": int(s.get("end_line") or s.get("line") or 0),
                "exported": bool(s.get("exported", False)),
                "complexity": int(s.get("complexity") or 1),
                "role": s.get("role") or file_role,
                "signature": sig,
            }

            if detail == "full" and not file_unreadable and file_lines is not None:
                l_start = max(1, sym_dict["line"])
                l_end = max(l_start, sym_dict["end_line"])
                sym_lines = file_lines[l_start - 1 : l_end]
                capped_lines = False
                capped_chars = False
                if len(sym_lines) > MAX_BODY_LINES:
                    sym_lines = sym_lines[:MAX_BODY_LINES]
                    candidate_caps.append({
                        "path": canonical_path,
                        "symbol": sym_dict["name"],
                        "reason": "max-lines",
                        "limit": MAX_BODY_LINES,
                    })
                    capped_lines = True
                body_str = "".join(sym_lines)
                if len(body_str) > MAX_BODY_CHARS:
                    body_str = body_str[:MAX_BODY_CHARS]
                    candidate_caps.append({
                        "path": canonical_path,
                        "symbol": sym_dict["name"],
                        "reason": "max-chars",
                        "limit": MAX_BODY_CHARS,
                    })
                    capped_chars = True
                sym_dict["body"] = body_str
                sym_dict["body_truncated"] = (capped_lines or capped_chars)
                sym_dict["body_lines"] = len(body_str.splitlines())
                sym_dict["body_chars"] = len(body_str)

            file_symbols.append(sym_dict)

        file_entry = {
            "path": canonical_path,
            "role": file_role,
            "pillar": file_pillar,
            "route_count": file_route_count,
            "symbols": file_symbols,
        }

        if detail == "full" and file_unreadable:
            omitted.append({"path": canonical_path, "reason": "unreadable"})

        # Test if adding this file fits into budget
        test_files = included_files + [file_entry]
        test_caps = caps + candidate_caps
        test_truncated = bool(
            omitted
            or test_caps
            or len(test_files) < files_requested
        )
        test_neutralized = _make_neutralized(
            detail=detail,
            budget=budget,
            files=test_files,
            omitted=omitted,
            caps=test_caps,
            truncated=test_truncated,
            files_requested=files_requested,
        )
        test_tokens = estimate_tokens(encode_json(test_neutralized))
        if test_tokens <= budget:
            included_files.append(file_entry)
            caps.extend(candidate_caps)
        else:
            omitted.append({"path": canonical_path, "reason": "budget"})

    # Post-finalization back-off if measured pack still exceeds budget
    while included_files:
        truncated = bool(
            omitted
            or caps
            or len(included_files) < files_requested
        )
        neutralized = _make_neutralized(
            detail=detail,
            budget=budget,
            files=included_files,
            omitted=omitted,
            caps=caps,
            truncated=truncated,
            files_requested=files_requested,
        )
        tokens_pack = estimate_tokens(encode_json(neutralized))
        if tokens_pack <= budget:
            break
        dropped = included_files.pop()
        caps = [c for c in caps if c.get("path") != dropped["path"]]
        omitted.append({"path": dropped["path"], "reason": "budget"})

    if not included_files:
        truncated = bool(omitted or caps or 0 < files_requested)
        neutralized = _make_neutralized(
            detail=detail,
            budget=budget,
            files=[],
            omitted=omitted,
            caps=caps,
            truncated=truncated,
            files_requested=files_requested,
        )
        tokens_pack = estimate_tokens(encode_json(neutralized))

    hash_val = context_hash(neutralized)

    # If since_hash matches computed hash, return unchanged envelope
    if since_hash is not None and since_hash == hash_val:
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "available": True,
            "unchanged": True,
            "detail": detail,
            "budget": budget,
            "hash": hash_val,
            "format": "json",
        }

    payload = {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "available": True,
        "detail": detail,
        "budget": budget,
        "files": included_files,
        "omitted": omitted,
        "caps": caps,
        "truncated": truncated,
        "counts": {
            "files_included": len(included_files),
            "files_requested": files_requested,
            "symbols_included": sum(len(f.get("symbols", [])) for f in included_files),
        },
        "hash": hash_val,
        "tokens": {
            "pack": tokens_pack,
            "budget": budget,
        },
        "format": "json",
        "root": str(Path(root).resolve()) if root else "",
    }
    if since_hash is not None:
        payload["since_hash"] = since_hash

    return payload
