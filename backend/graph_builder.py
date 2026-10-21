"""
graph_builder.py
Builds RepoScope's code graph from a directory on disk.

Milestone 1.1 — Tree-sitter polyglot parsing.

Files are parsed by the polyglot parser registry (backend/parsers/):
Python, TypeScript, TSX, JavaScript, Go, and Rust. Each parser yields the
same `ParseResult` — symbols, imports, and call sites — so this module
never needs to know which language it is looking at.

Import edges are RESOLVED against a module index built in a first pass, so
`from backend.engine import decision_model`, relative imports (`from .db
import get_db`), and JS/TS relative or alias imports (`@/components/x`)
all land on real file nodes instead of dangling ids.

Call sites become `calls` edges between symbol nodes. The frontend already
renders that edge type (frontend/src/components/GraphView.tsx:174).

Correction C10 — the node/edge contract is load-bearing and is preserved
exactly:
    file nodes   {id, type, label, language, size}
    symbol nodes {id, type, label, file, line}
    ids          file:{rel}  func:{rel}:{name}  class:{rel}:{name}
    edge types   contains | imports | calls
"""
import ast
import logging
import os
import re
from pathlib import Path

from parsers.registry import get_parser

log = logging.getLogger("reposcope.graph_builder")

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__",
              ".venv", "venv", ".mypy_cache", ".pytest_cache"}

_PY_EXTS = {".py"}
_JS_EXTS = {".ts", ".tsx", ".js", ".jsx"}


def build_graph_from_repo(root: str) -> dict:
    """Parse a cloned repo into nodes + edges. Returns graph dict."""
    nodes: list[dict] = []
    edges: list[dict] = []
    root_path = Path(root)

    # ── Pass 1: collect files + build module indexes ────────────────────────
    py_index: dict[str, str] = {}    # dotted module  -> file:rel
    py_stems: dict[str, str] = {}    # bare stem      -> file:rel (fallback)
    js_files: set[str] = set()       # rel paths of js/ts files
    js_stems: dict[str, str] = {}    # bare stem      -> file:rel (alias '@/', '~/')

    collected: list[tuple[Path, str, str]] = []  # (path, rel, suffix)
    for path in root_path.rglob("*"):
        if any(p in _SKIP_DIRS for p in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            rel = str(path.relative_to(root_path)).replace("\\", "/")
        except ValueError:
            continue
        collected.append((path, rel, path.suffix))

        if path.suffix in _PY_EXTS:
            parts = rel[:-3].split("/")                      # strip .py
            if parts[-1] == "__init__":
                py_index[".".join(parts[:-1])] = f"file:{rel}"
            py_index[".".join(parts)] = f"file:{rel}"
            py_stems.setdefault(parts[-1], f"file:{rel}")
        elif path.suffix in _JS_EXTS:
            js_files.add(rel)
            js_stems.setdefault(Path(rel).stem, f"file:{rel}")

    def resolve_py(module: str | None, level: int, pkg_parts: list[str],
                   imported_name: str | None = None) -> str | None:
        """Resolve a python import to a file id, or None when external."""
        if level:  # relative import: level=1 → this package, 2 → parent, …
            base = pkg_parts[: len(pkg_parts) - (level - 1)] if len(pkg_parts) >= level else []
        else:
            base = module.split(".") if module else []
        if module and not level:
            parts = base
        elif module:
            parts = base + module.split(".")
        else:
            parts = base
        variants = [".".join(parts)]
        if imported_name:
            variants.append(".".join(parts + [imported_name]))
        for v in variants:
            if v in py_index:
                return py_index[v]
        # bare-stem fallback (flat layouts / src-less repos)
        if imported_name and imported_name in py_stems:
            return py_stems[imported_name]
        return None

    def resolve_js(spec: str, importer_rel: str) -> str | None:
        """Resolve a JS/TS import specifier to a file id, or None (external)."""
        if spec.startswith("@/") or spec.startswith("~/"):
            cand_base = [spec[2:], f"src/{spec[2:]}"]
        elif spec.startswith("./") or spec.startswith("../"):
            parts = (Path(importer_rel).parent.joinpath(spec)).as_posix()
            cand_base = [parts]
        else:
            return None  # bare package import — external, skip
        resolved = []
        for base in cand_base:
            norm = os.path.normpath(base).replace("\\", "/")
            resolved.append(norm)
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                resolved.append(f"{norm}{ext}")
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                resolved.append(f"{norm}/index{ext}")
        for cand in resolved:
            if cand in js_files:
                return f"file:{cand}"
        return None

    # ── Pass 2: parse code files ─────────────────────────────────────────────
    #
    # Each file is parsed by the polyglot registry. The parser yields
    # symbols, imports, and call sites; this module mints the node ids and
    # the edges so the C10 contract lives in exactly one place.
    #
    # The bookkeeping below supports call resolution in pass 3:
    #   symbols_in_file  rel -> {name -> [node_id, ...]}
    #   file_imports     rel -> {imported_rel -> set(bound_names)}
    #   global_symbols   name -> [(rel, node_id), ...]
    symbols_in_file: dict[str, dict[str, list[tuple[int, str]]]] = {}
    file_imports: dict[str, dict[str, set[str]]] = {}
    global_symbols: dict[str, list[tuple[str, str]]] = {}
    pending_calls: list[tuple[str, str, str, int]] = []  # (src_rel, src_id, callee, line)

    for path, rel, suffix in collected:
        fid = f"file:{rel}"
        nodes.append({
            "id": fid,
            "type": "file",
            "label": rel,
            "language": suffix.lstrip(".") or "txt",
            "size": path.stat().st_size,
        })

        parser = get_parser(suffix)
        if parser is None:
            # No tree-sitter grammar for this extension — fall back to the
            # original implementation so nothing is lost.
            if suffix in _PY_EXTS:
                pkg_parts = rel[:-3].split("/")[:-1]
                _parse_python(path, rel, fid, nodes, edges, pkg_parts, resolve_py)
            elif suffix in _JS_EXTS:
                _parse_js_ts(path, rel, fid, nodes, edges, resolve_js)
            continue

        try:
            source = path.read_bytes()
        except OSError:
            continue

        try:
            result = parser.extract(source, rel)
        except Exception as exc:  # noqa: BLE001 - a bad file must not stop the graph
            log.warning("Parser failed for %s: %s", rel, exc)
            continue

        # ── Symbols ────────────────────────────────────────────────────────
        name_counts: dict[tuple[str, str], int] = {}
        for symbol in result.symbols:
            key = (symbol.kind, symbol.name)
            name_counts[key] = name_counts.get(key, 0) + 1

        per_file: dict[str, list[tuple[int, str]]] = {}
        for symbol in result.symbols:
            shared = name_counts[(symbol.kind, symbol.name)] > 1
            node_id = _disambiguate(
                "func" if symbol.kind == "function" else "class",
                rel, symbol.name, symbol.line, shared,
            )
            nodes.append({
                "id": node_id,
                "type": symbol.kind,
                "label": symbol.name,
                "file": rel,
                "line": symbol.line,
            })
            edges.append({"source": fid, "target": node_id, "type": "contains"})
            per_file.setdefault(symbol.name, []).append((symbol.line, node_id))
            global_symbols.setdefault(symbol.name, []).append((rel, node_id))
        symbols_in_file[rel] = per_file

        # ── Imports ────────────────────────────────────────────────────────
        imported: dict[str, set[str]] = {}
        for imp in result.imports:
            target_rel = _resolve_import(imp, rel, suffix, resolve_py, resolve_js)
            if not target_rel:
                continue
            edges.append({"source": fid, "target": f"file:{target_rel}", "type": "imports"})
            imported.setdefault(target_rel, set()).update(imp.names)
        file_imports[rel] = imported

        # ── Call sites ─────────────────────────────────────────────────────
        for call in result.calls:
            if call.receiver:
                # A method call on an object is a dynamic dispatch we
                # cannot resolve statically. Only an unqualified call is
                # worth resolving.
                continue
            if not call.enclosing:
                # A call at module level is attributed to the file itself.
                pending_calls.append((rel, fid, call.callee, 0))
                continue
            # Match the enclosing symbol by name AND line. A file may
            # define several symbols with the same name — four `__init__`
            # methods is the common case — so the line is what
            # disambiguates them. Attributing every call to the first
            # match would silently mis-attribute most of them.
            enclosing = per_file.get(call.enclosing)
            if not enclosing:
                continue
            match = next(
                (node_id for line, node_id in enclosing if line == call.enclosing_line),
                None,
            )
            if match is None:
                match = enclosing[0][1]
            pending_calls.append((rel, match, call.callee, call.enclosing_line))

    # ── Pass 3: resolve call sites into `calls` edges ───────────────────────
    for src_rel, src_id, callee, _line in pending_calls:
        target_id = _resolve_symbol(
            callee, src_rel, src_id, symbols_in_file, file_imports, global_symbols,
        )
        if target_id and target_id != src_id:
            edges.append({"source": src_id, "target": target_id, "type": "calls"})

    # Deduplicate edges
    seen: set[tuple] = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"], e.get("type"))
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    log.info("Graph built: %d nodes, %d edges from %s", len(nodes), len(unique_edges), root)
    return {
        "nodes": nodes,
        "edges": unique_edges,
        "summary": f"{len(nodes)} nodes, {len(unique_edges)} edges",
    }


def _line_of(source: str, offset: int) -> int:
    """1-based line number for a character offset in `source`."""
    return source.count("\n", 0, offset) + 1


def _resolve_import(imp, rel: str, suffix: str, resolve_py, resolve_js) -> str | None:
    """
    Resolve one parsed import to the repo-relative path it refers to.

    Returns None for external packages — those must not create dangling
    edges.
    """
    if suffix in _PY_EXTS:
        if imp.is_relative:
            # Rebuild the package context the way Python resolves it:
            # level 1 is this package, level 2 the parent, and so on.
            parts = rel[:-3].split("/")[:-1]
            base = parts[: len(parts) - (imp.level - 1)] if imp.level <= len(parts) else []
            module = ".".join(base + ([imp.module] if imp.module else []))
            target = resolve_py(module or None, 0, parts, imp.names[0] if imp.names else None)
        else:
            target = resolve_py(imp.module or None, 0, rel[:-3].split("/")[:-1],
                                imp.names[0] if imp.names else None)
    elif suffix in _JS_EXTS:
        target = resolve_js(imp.module, rel)
    else:
        # Go and Rust module paths are package names, not repo paths. They
        # are not resolvable to files, so they produce no edge.
        return None

    if not target or not target.startswith("file:"):
        return None
    return target[len("file:"):]


def _resolve_symbol(
    callee: str,
    src_rel: str,
    src_id: str,
    symbols_in_file: dict[str, dict[str, list[tuple[int, str]]]],
    file_imports: dict[str, dict[str, set[str]]],
    global_symbols: dict[str, list[tuple[str, str]]],
) -> str | None:
    """
    Resolve a call to the symbol it invokes.

    The resolution order is deliberately conservative, because a wrong
    edge is worse than a missing one:

      1. A symbol defined in the same file.
      2. A symbol in a module this file imports. When the import binds
         specific names, only those names are considered.
      3. A symbol with this name that exists in exactly ONE file in the
         whole repository — unambiguous, so safe to link.

    Anything more ambiguous is left unlinked rather than guessed.
    """
    if not callee:
        return None

    # 1. Same file.
    local = symbols_in_file.get(src_rel, {}).get(callee)
    if local:
        return local[0][1]

    # 2. An imported module.
    for imported_rel, bound_names in file_imports.get(src_rel, {}).items():
        candidates = symbols_in_file.get(imported_rel, {}).get(callee)
        if not candidates:
            continue
        if bound_names and callee not in bound_names:
            # The import binds specific names and this is not one of them.
            continue
        return candidates[0][1]

    # 3. Unambiguous across the whole repository.
    matches = global_symbols.get(callee)
    if matches and len(matches) == 1:
        return matches[0][1]

    return None


def _disambiguate(kind: str, rel: str, name: str, lineno: int | None, shared: bool) -> str:
    """
    Build a symbol node id, disambiguating names that collide within a file.

    The id scheme is `func:{rel}:{name}` / `class:{rel}:{name}` — Correction
    C10 makes that scheme load-bearing, so it is preserved exactly for the
    overwhelming majority of symbols whose name is unique within their file.

    When a name DOES collide (several `__init__` methods in one class-heavy
    file, two `main` functions, ...), every colliding symbol gets a
    deterministic `@{lineno}` suffix. Emitting the suffix for ALL members of
    a colliding group — rather than for all but the first — keeps the ids
    symmetric: no symbol is privileged by traversal order.

    Before this, `ast.walk` produced one node id per matching name, so four
    `__init__` methods in a single file all mapped to
    `func:src/tomli/_parser.py:__init__`. Duplicate node ids break React
    list keys in the graph renderer and corrupt the graph store.
    """
    base = f"{kind}:{rel}:{name}"
    if not shared:
        return base
    return f"{base}@{lineno}" if lineno else f"{base}@?"


def _parse_python(path: Path, rel: str, fid: str, nodes: list, edges: list,
                  pkg_parts: list[str], resolve) -> None:
    try:
        source = path.read_text(errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return

    # Pass 1 — collect the definitions so name collisions can be counted
    # before any node id is minted.
    funcs: list[tuple[str, int]] = []
    classes: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            classes.append((node.name, node.lineno))

    func_counts: dict[str, int] = {}
    for name, _ in funcs:
        func_counts[name] = func_counts.get(name, 0) + 1
    class_counts: dict[str, int] = {}
    for name, _ in classes:
        class_counts[name] = class_counts.get(name, 0) + 1

    for name, lineno in funcs:
        fn_id = _disambiguate("func", rel, name, lineno, func_counts[name] > 1)
        nodes.append({
            "id": fn_id,
            "type": "function",
            "label": name,
            "file": rel,
            "line": lineno,
        })
        edges.append({"source": fid, "target": fn_id, "type": "contains"})

    for name, lineno in classes:
        cls_id = _disambiguate("class", rel, name, lineno, class_counts[name] > 1)
        nodes.append({
            "id": cls_id,
            "type": "class",
            "label": name,
            "file": rel,
            "line": lineno,
        })
        edges.append({"source": fid, "target": cls_id, "type": "contains"})

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = resolve(alias.name, 0, pkg_parts)
                if target and target != fid:
                    edges.append({"source": fid, "target": target, "type": "imports"})

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                target = resolve(node.module, node.level or 0, pkg_parts, alias.name)
                if target and target != fid:
                    edges.append({"source": fid, "target": target, "type": "imports"})


def _parse_js_ts(path: Path, rel: str, fid: str, nodes: list, edges: list,
                 resolve) -> None:
    try:
        source = path.read_text(errors="ignore")
    except Exception:
        return

    # Pass 1 — collect the definitions so name collisions can be counted
    # before any node id is minted.
    funcs: list[tuple[str, int]] = []
    for m in re.finditer(
        r'(?:^|\s)(?:export\s+)?(?:async\s+)?function\s+(\w+)|'
        r'(?:^|\s)(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(',
        source, re.MULTILINE
    ):
        name = m.group(1) or m.group(2)
        if name:
            funcs.append((name, _line_of(source, m.start())))

    classes: list[tuple[str, int]] = []
    for m in re.finditer(r'(?:^|\s)(?:export\s+)?class\s+(\w+)', source, re.MULTILINE):
        classes.append((m.group(1), _line_of(source, m.start())))

    func_counts: dict[str, int] = {}
    for name, _ in funcs:
        func_counts[name] = func_counts.get(name, 0) + 1
    class_counts: dict[str, int] = {}
    for name, _ in classes:
        class_counts[name] = class_counts.get(name, 0) + 1

    # Pass 2 — emit nodes with deterministic, collision-free ids.
    for name, lineno in funcs:
        fn_id = _disambiguate("func", rel, name, lineno, func_counts[name] > 1)
        nodes.append({
            "id": fn_id,
            "type": "function",
            "label": name,
            "file": rel,
            "line": lineno,
        })
        edges.append({"source": fid, "target": fn_id, "type": "contains"})

    for name, lineno in classes:
        cls_id = _disambiguate("class", rel, name, lineno, class_counts[name] > 1)
        nodes.append({
            "id": cls_id,
            "type": "class",
            "label": name,
            "file": rel,
            "line": lineno,
        })
        edges.append({"source": fid, "target": cls_id, "type": "contains"})

    # Imports — static `import … from` and `export … from`
    for m in re.finditer(r"(?:import|export)\s+.*?\s+from\s+['\"](.+?)['\"]", source):
        target = resolve(m.group(1), rel)
        if target and target != fid:
            edges.append({"source": fid, "target": target, "type": "imports"})
