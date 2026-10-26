"""
graph_builder.py
Builds RepoScope's code graph from a directory on disk.

Milestone 1.1 — Tree-sitter polyglot parsing.
Milestone 6.2 — Caching & Incremental Indexing (Sprint 3).

The module has two stages, and the split is the point:

    parse     one file at a time, depending ONLY on that file's bytes
    assemble  the whole repository, resolving imports and call sites

Parsing is expensive; assembly is cheap. Separating them means a
repository can be re-indexed after an edit by re-parsing ONE file and
reusing every other file's parse result. `GraphIndexer` maintains a live
index and patches only the edges an edit can possibly affect.

Files are parsed by the polyglot parser registry (backend/parsers/):
Python, TypeScript, TSX, JavaScript, Go, and Rust. Each parser yields
the same `ParseResult` — symbols, imports, and call sites — so this module
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
import time
from pathlib import Path
from typing import Iterable, Mapping

from parse_cache import FileFacts, ParseCache, hash_bytes
from parsers.registry import get_parser

log = logging.getLogger("reposcope.graph_builder")

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__",
              ".venv", "venv", ".mypy_cache", ".pytest_cache",
              # RepoScope's own index lives here. Without this the graph
              # would index its own cache and the graph store, and every
              # re-index would see a "changed" file.
              ".reposcope"}

_PY_EXTS = {".py"}
_JS_EXTS = {".ts", ".tsx", ".js", ".jsx"}


# ── Stage 1 · parse one file ────────────────────────────────────────────────

def _symbol_to_dict(symbol) -> dict:
    return {
        "name": symbol.name,
        "kind": symbol.kind,
        "line": symbol.line,
        "end_line": symbol.end_line,
        "signature": symbol.signature,
        "exported": symbol.exported,
        "parent": symbol.parent,
        "complexity": symbol.complexity,
    }


def _import_to_dict(imp) -> dict:
    return {
        "module": imp.module,
        "line": imp.line,
        "names": list(imp.names),
        "is_relative": imp.is_relative,
        "level": imp.level,
        "re_export": imp.re_export,
    }


def _call_to_dict(call) -> dict:
    return {
        "callee": call.callee,
        "line": call.line,
        "receiver": call.receiver,
        "enclosing": call.enclosing,
        "enclosing_line": call.enclosing_line,
    }


def parse_bytes(data: bytes, rel: str, suffix: str) -> FileFacts:
    """
    Turn one file's bytes into its facts.

    Depends on nothing but the bytes and the repo-relative path — which
    is exactly what makes the result cacheable by content hash.
    """
    parser = get_parser(suffix)
    if parser is not None:
        try:
            result = parser.extract(data, rel)
        except Exception as exc:  # noqa: BLE001 - a bad file must not stop the graph
            log.warning("Parser failed for %s: %s", rel, exc)
            return FileFacts(
                rel=rel, suffix=suffix, size=len(data), sha256="",
                warnings=[f"parser failed: {exc}"],
            )
        return FileFacts(
            rel=rel,
            suffix=suffix,
            size=len(data),
            sha256="",
            symbols=[_symbol_to_dict(s) for s in result.symbols],
            imports=[_import_to_dict(i) for i in result.imports],
            calls=[_call_to_dict(c) for c in result.calls],
            warnings=list(result.warnings),
        )

    symbols, imports, warnings = _fallback_facts(data, rel, suffix)
    return FileFacts(
        rel=rel, suffix=suffix, size=len(data), sha256="",
        symbols=symbols, imports=imports, calls=[], warnings=warnings,
    )


def parse_file(path: str | Path, rel: str) -> FileFacts:
    """Parse a file on disk. The cache-free path."""
    file_path = Path(path)
    try:
        data = file_path.read_bytes()
    except OSError as exc:
        log.warning("Could not read %s: %s", rel, exc)
        return FileFacts(
            rel=rel, suffix=file_path.suffix, size=0, sha256="",
            warnings=[f"unreadable: {exc}"],
        )
    facts = parse_bytes(data, rel, file_path.suffix)
    facts.sha256 = hash_bytes(data)
    return facts


def _fallback_facts(data: bytes, rel: str, suffix: str) -> tuple[list[dict], list[dict], list[str]]:
    """
    The grammar-free fallback.

    Used only when no tree-sitter grammar is available for an extension.
    It produces the SAME shape as the tree-sitter path — symbols and
    unresolved imports — so the assembly stage cannot tell the difference.
    That matters: the two paths used to diverge (the fallback resolved
    imports eagerly, per alias, while tree-sitter resolved them lazily,
    per statement), which meant the fallback produced a subtly different
    graph for the same repository.
    """
    source = data.decode("utf-8", "replace")
    if suffix in _PY_EXTS:
        return _fallback_python(source, rel)
    if suffix in _JS_EXTS:
        return _fallback_js(source, rel)
    return [], [], []


def _fallback_python(source: str, rel: str) -> tuple[list[dict], list[dict], list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [], [], [f"{rel}: syntax error, skipped ({exc.msg})"]

    funcs: list[tuple[str, int]] = []
    classes: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            classes.append((node.name, node.lineno))

    # Sorted by line so the order matches the tree-sitter path (document
    # order). Call resolution picks the FIRST match for a name, so the
    # order is not cosmetic.
    funcs.sort(key=lambda item: item[1])
    classes.sort(key=lambda item: item[1])

    symbols: list[dict] = []
    for name, lineno in funcs:
        symbols.append(_plain_symbol(name, "function", lineno))
    for name, lineno in classes:
        symbols.append(_plain_symbol(name, "class", lineno))

    imports: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "module": alias.name, "line": node.lineno, "names": [],
                    "is_relative": False, "level": 0, "re_export": False,
                })
        elif isinstance(node, ast.ImportFrom):
            imports.append({
                "module": node.module or "",
                "line": node.lineno,
                "names": [alias.name for alias in node.names],
                "is_relative": bool(node.level),
                "level": node.level or 0,
                "re_export": False,
            })

    return symbols, imports, []


def _plain_symbol(name: str, kind: str, lineno: int) -> dict:
    return {
        "name": name,
        "kind": kind,
        "line": lineno,
        "end_line": lineno,
        "signature": "",
        "exported": not name.startswith("_"),
        "parent": None,
        "complexity": 1,
    }


_JS_FUNCTION_RE = re.compile(
    r"(?:^|\s)(?:export\s+)?(?:async\s+)?function\s+(\w+)|"
    r"(?:^|\s)(?:export\s+)?(?:async\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\("
)
_JS_CLASS_RE = re.compile(r"(?:^|\s)(?:export\s+)?class\s+(\w+)")
_JS_IMPORT_RE = re.compile(r"(?:import|export)\s+.*?\s+from\s+['\"](.+?)['\"]")
_JS_NAMED_RE = re.compile(r"\{([^}]*)\}")


def _fallback_js(source: str, rel: str) -> tuple[list[dict], list[dict], list[str]]:
    symbols: list[dict] = []
    for match in _JS_FUNCTION_RE.finditer(source):
        name = match.group(1) or match.group(2)
        if name:
            symbols.append(_plain_symbol(name, "function", _line_of(source, match.start())))
    for match in _JS_CLASS_RE.finditer(source):
        symbols.append(_plain_symbol(match.group(1), "class", _line_of(source, match.start())))

    imports: list[dict] = []
    for match in _JS_IMPORT_RE.finditer(source):
        module = match.group(1)
        names: list[str] = []
        named = _JS_NAMED_RE.search(match.group(0))
        if named:
            for part in named.group(1).split(","):
                part = part.strip().split(" as ")[0].strip()
                if part:
                    names.append(part)
        imports.append({
            "module": module, "line": _line_of(source, match.start()), "names": names,
            "is_relative": module.startswith("."), "level": 0, "re_export": False,
        })

    return symbols, imports, []


def _line_of(source: str, offset: int) -> int:
    """1-based line number for a character offset in `source`."""
    return source.count("\n", 0, offset) + 1


# ── Stage 2 · assemble the repository ───────────────────────────────────────

class ModuleIndex:
    """
    The module-name lookup used to resolve imports.

    Python modules are indexed by their dotted path AND by their bare
    stem (the fallback for flat layouts). JS/TS files are indexed by path
    and by stem, because an alias import (`@/components/x`) names a
    directory, not a module.
    """

    __slots__ = ("py_index", "py_stems", "js_files", "js_stems")

    def __init__(self) -> None:
        self.py_index: dict[str, str] = {}
        self.py_stems: dict[str, str] = {}
        self.js_files: set[str] = set()
        self.js_stems: dict[str, str] = {}


def build_module_index(facts: Mapping[str, FileFacts]) -> ModuleIndex:
    index = ModuleIndex()
    for rel, file_facts in facts.items():
        suffix = file_facts.suffix
        if suffix in _PY_EXTS:
            parts = rel[:-3].split("/")                      # strip .py
            if parts[-1] == "__init__":
                index.py_index[".".join(parts[:-1])] = f"file:{rel}"
            index.py_index[".".join(parts)] = f"file:{rel}"
            index.py_stems.setdefault(parts[-1], f"file:{rel}")
        elif suffix in _JS_EXTS:
            index.js_files.add(rel)
            index.js_stems.setdefault(Path(rel).stem, f"file:{rel}")
    return index


def _resolve_py(
    index: ModuleIndex,
    module: str | None,
    level: int,
    pkg_parts: list[str],
    imported_name: str | None = None,
) -> str | None:
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
    for variant in variants:
        if variant in index.py_index:
            return index.py_index[variant]
    # bare-stem fallback (flat layouts / src-less repos)
    if imported_name and imported_name in index.py_stems:
        return index.py_stems[imported_name]
    return None


def _resolve_js(index: ModuleIndex, spec: str, importer_rel: str) -> str | None:
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
    for candidate in resolved:
        if candidate in index.js_files:
            return f"file:{candidate}"
    return None


def _resolve_import(
    index: ModuleIndex,
    imp: Mapping,
    rel: str,
    suffix: str,
) -> str | None:
    """
    Resolve one parsed import to the repo-relative path it refers to.

    Returns None for external packages — those must not create dangling
    edges.
    """
    module = imp.get("module") or ""
    names = imp.get("names") or []
    level = int(imp.get("level") or 0)
    is_relative = bool(imp.get("is_relative"))

    if suffix in _PY_EXTS:
        if is_relative:
            # Rebuild the package context the way Python resolves it:
            # level 1 is this package, level 2 the parent, and so on.
            parts = rel[:-3].split("/")[:-1]
            base = parts[: len(parts) - (level - 1)] if level <= len(parts) else []
            module_name = ".".join(base + ([module] if module else []))
            target = _resolve_py(index, module_name or None, 0, parts, names[0] if names else None)
        else:
            target = _resolve_py(index, module or None, 0, rel[:-3].split("/")[:-1],
                                  names[0] if names else None)
    elif suffix in _JS_EXTS:
        target = _resolve_js(index, module, rel)
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

    When a name DOES collide (several `__init__` methods in a class-heavy
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


def _symbol_node(node_id: str, symbol: Mapping, rel: str) -> dict:
    """
    Build a symbol node.

    The C10 keys are always present. The extra keys (signature,
    complexity, exported, parent) are ADDITIVE — they carry information
    the parsers already computed and the repo map (M8.1) needs, and they
    cost nothing to keep.
    """
    node = {
        "id": node_id,
        "type": symbol.get("kind", "function"),
        "label": symbol.get("name", ""),
        "file": rel,
        "line": int(symbol.get("line") or 0),
        "signature": symbol.get("signature", ""),
        "exported": bool(symbol.get("exported", False)),
        "complexity": int(symbol.get("complexity") or 1),
    }
    parent = symbol.get("parent")
    if parent:
        node["parent"] = parent
    return node


def assemble_graph(facts: Mapping[str, FileFacts]) -> dict:
    """
    Assemble a whole repository's graph from its per-file facts.

    This is the C10 contract in one place: node ids, node types, edge
    types. The input is per-file facts, so this stage can run over cached
    results without touching the disk.
    """
    index = build_module_index(facts)

    nodes: list[dict] = []
    edges: list[dict] = []
    symbols_in_file: dict[str, dict[str, list[tuple[int, str]]]] = {}
    file_imports: dict[str, dict[str, set[str]]] = {}
    global_symbols: dict[str, list[tuple[str, str]]] = {}
    pending_calls: list[tuple[str, str, str, int]] = []

    for rel in sorted(facts):
        file_facts = facts[rel]
        fid = f"file:{rel}"
        nodes.append({
            "id": fid,
            "type": "file",
            "label": rel,
            "language": file_facts.suffix.lstrip(".") or "txt",
            "size": file_facts.size,
        })

        name_counts: dict[tuple[str, str], int] = {}
        for symbol in file_facts.symbols:
            key = (symbol.get("kind", "function"), symbol.get("name", ""))
            name_counts[key] = name_counts.get(key, 0) + 1

        per_file: dict[str, list[tuple[int, str]]] = {}
        for symbol in file_facts.symbols:
            kind = symbol.get("kind", "function")
            name = symbol.get("name", "")
            shared = name_counts[(kind, name)] > 1
            node_id = _disambiguate(
                "func" if kind == "function" else "class",
                rel, name, int(symbol.get("line") or 0), shared,
            )
            nodes.append(_symbol_node(node_id, symbol, rel))
            edges.append({"source": fid, "target": node_id, "type": "contains"})
            per_file.setdefault(name, []).append((int(symbol.get("line") or 0), node_id))
            global_symbols.setdefault(name, []).append((rel, node_id))
        symbols_in_file[rel] = per_file

        imported: dict[str, set[str]] = {}
        for imp in file_facts.imports:
            target_rel = _resolve_import(index, imp, rel, file_facts.suffix)
            if not target_rel:
                continue
            edges.append({"source": fid, "target": f"file:{target_rel}", "type": "imports"})
            imported.setdefault(target_rel, set()).update(imp.get("names") or ())
        file_imports[rel] = imported

        for call in file_facts.calls:
            if call.get("receiver"):
                # A method call on an object is a dynamic dispatch we
                # cannot resolve statically. Only an unqualified call is
                # worth resolving.
                continue
            if not call.get("enclosing"):
                # A call at module level is attributed to the file itself.
                pending_calls.append((rel, fid, call.get("callee", ""), 0))
                continue
            # Match the enclosing symbol by name AND line. A file may
            # define several symbols with the same name — four `__init__`
            # methods is the common case — so the line is what
            # disambiguates them. Attributing every call to the first
            # match would silently mis-attribute most of them.
            enclosing = per_file.get(call.get("enclosing"))
            if not enclosing:
                continue
            match = next(
                (node_id for line, node_id in enclosing if line == call.get("enclosing_line", 0)),
                None,
            )
            if match is None:
                match = enclosing[0][1]
            pending_calls.append((rel, match, call.get("callee", ""), call.get("enclosing_line", 0)))

    for src_rel, src_id, callee, _line in pending_calls:
        target_id = _resolve_symbol(
            callee, src_rel, src_id, symbols_in_file, file_imports, global_symbols,
        )
        if target_id and target_id != src_id:
            edges.append({"source": src_id, "target": target_id, "type": "calls"})

    unique_edges = _dedupe_edges(edges)
    graph = {
        "nodes": nodes,
        "edges": unique_edges,
        "summary": f"{len(nodes)} nodes, {len(unique_edges)} edges",
    }

    # Attach centrality (M7.1). PageRank replaces the naive
    # `incoming x 2 + outgoing` heuristic the pyramid used to rank files
    # with, and the same scores drive the hotspot blend and the "top
    # hubs" MCP resource.
    try:
        from graph_analysis import attach_analysis

        attach_analysis(graph)
    except Exception as exc:  # noqa: BLE001 - analysis must never break the graph
        log.warning("Graph analysis failed, continuing without it: %s", exc)

    log.info("Graph assembled: %d nodes, %d edges", len(nodes), len(graph["edges"]))
    return graph


def _dedupe_edges(edges: Iterable[dict]) -> list[dict]:
    seen: set[tuple] = set()
    unique: list[dict] = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge.get("type"))
        if key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique


# ── Public API ──────────────────────────────────────────────────────────────

def collect_facts(
    root: str | Path,
    cache: ParseCache | None = None,
) -> dict[str, FileFacts]:
    """
    Walk a repository and collect the facts for every file.

    With a cache, a file whose content hash is already known is not
    parsed again. Without one, everything is parsed.
    """
    root_path = Path(root)
    facts: dict[str, FileFacts] = {}

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = str(path.relative_to(root_path)).replace("\\", "/")
        except ValueError:
            continue
        # The skip test is on the RELATIVE parts, not the absolute ones.
        # Testing `path.parts` meant a repository that happened to live
        # under a directory called `build` or `dist` indexed NOTHING —
        # the whole tree was skipped before a single file was read.
        if any(part in _SKIP_DIRS for part in rel.split("/")):
            continue

        if cache is not None:
            suffix = path.suffix
            facts[rel] = cache.get_for(
                path, rel, lambda data, r, _suffix=suffix: parse_bytes(data, r, _suffix)
            )
        else:
            facts[rel] = parse_file(path, rel)

    return facts


def build_graph_from_repo(root: str, cache: ParseCache | None = None) -> dict:
    """
    Parse a repository into nodes + edges. Returns the graph dict.

    Correction C10: this signature and the shape it returns are
    load-bearing. `cache` is an optional accelerator — the graph it
    produces is identical with or without one.
    """
    facts = collect_facts(root, cache)
    graph = assemble_graph(facts)
    log.info(
        "Graph built: %d nodes, %d edges from %s",
        len(graph["nodes"]), len(graph["edges"]), root,
    )
    return graph


# ── Stage 3 · the live index ────────────────────────────────────────────────

class GraphIndexer:
    """
    A graph that can be updated when files change.

    Milestone 6.2. The index keeps the parsed facts for every file, so an
    edit re-parses ONE file instead of the whole repository. It also
    keeps the derived tables — node table, edge table, module index,
    symbol table — so an edit patches only the edges it can affect:

      * the edited file's own nodes and edges,
      * the import edges of files that import it (if the file was added,
        removed or renamed),
      * the call edges of files that call a symbol the edit changed.

    Everything else is left alone. That is the difference between an
    index that takes 400 ms to update and one that takes 5 ms.
    """

    def __init__(self, root: str | Path, cache: ParseCache | None = None):
        self.root = Path(root)
        self.cache = cache
        self.facts: dict[str, FileFacts] = {}

        self._index = ModuleIndex()
        self._nodes: dict[str, dict] = {}
        self._edges: dict[tuple[str, str, str], dict] = {}
        self._node_ids_by_file: dict[str, list[str]] = {}
        self._symbols_in_file: dict[str, dict[str, list[tuple[int, str]]]] = {}
        self._file_imports: dict[str, dict[str, set[str]]] = {}
        self._global_symbols: dict[str, list[tuple[str, str]]] = {}
        self._call_sites: dict[str, list[dict]] = {}
        self._import_edge_keys: dict[str, list[tuple[str, str, str]]] = {}
        self._call_edge_keys: dict[str, list[tuple[str, str, str]]] = {}
        self._files_by_symbol_name: dict[str, set[str]] = {}
        self._callers_by_name: dict[str, set[str]] = {}

        self.graph: dict = {"nodes": [], "edges": [], "summary": "0 nodes, 0 edges"}

    # ── Building ────────────────────────────────────────────────────────────

    def index(self) -> dict:
        """Index the whole repository from scratch."""
        self.facts = collect_facts(self.root, self.cache)
        self._index = build_module_index(self.facts)
        self._reset_tables()
        for rel in sorted(self.facts):
            self._add_file(rel, self.facts[rel])
        self._publish()
        return self.graph

    def _reset_tables(self) -> None:
        self._nodes = {}
        self._edges = {}
        self._node_ids_by_file = {}
        self._symbols_in_file = {}
        self._file_imports = {}
        self._global_symbols = {}
        self._call_sites = {}
        self._import_edge_keys = {}
        self._call_edge_keys = {}
        self._files_by_symbol_name = {}
        self._callers_by_name = {}

    def _add_file(self, rel: str, file_facts: FileFacts) -> None:
        """Insert one file's nodes, imports and call sites into the tables."""
        fid = f"file:{rel}"
        self._nodes[fid] = {
            "id": fid,
            "type": "file",
            "label": rel,
            "language": file_facts.suffix.lstrip(".") or "txt",
            "size": file_facts.size,
        }
        node_ids = [fid]

        name_counts: dict[tuple[str, str], int] = {}
        for symbol in file_facts.symbols:
            key = (symbol.get("kind", "function"), symbol.get("name", ""))
            name_counts[key] = name_counts.get(key, 0) + 1

        per_file: dict[str, list[tuple[int, str]]] = {}
        for symbol in file_facts.symbols:
            kind = symbol.get("kind", "function")
            name = symbol.get("name", "")
            shared = name_counts[(kind, name)] > 1
            node_id = _disambiguate(
                "func" if kind == "function" else "class",
                rel, name, int(symbol.get("line") or 0), shared,
            )
            self._nodes[node_id] = _symbol_node(node_id, symbol, rel)
            node_ids.append(node_id)
            self._add_edge(fid, node_id, "contains")
            per_file.setdefault(name, []).append((int(symbol.get("line") or 0), node_id))
            self._global_symbols.setdefault(name, []).append((rel, node_id))
            self._files_by_symbol_name.setdefault(name, set()).add(rel)

        self._symbols_in_file[rel] = per_file
        self._node_ids_by_file[rel] = node_ids
        self._call_sites[rel] = list(file_facts.calls)
        for call in file_facts.calls:
            callee = call.get("callee") or ""
            if callee:
                self._callers_by_name.setdefault(callee, set()).add(rel)

        self._resolve_imports_for(rel, file_facts)
        self._resolve_calls_for(rel)

    def _remove_file(self, rel: str) -> None:
        """Remove one file's nodes and edges from the tables."""
        for key in self._import_edge_keys.pop(rel, []):
            self._edges.pop(key, None)
        for key in self._call_edge_keys.pop(rel, []):
            self._edges.pop(key, None)

        for node_id in self._node_ids_by_file.pop(rel, []):
            self._nodes.pop(node_id, None)
            # Drop edges that leave the removed nodes.
            for key in [k for k in self._edges if k[0] == node_id]:
                self._edges.pop(key, None)
            # Drop edges that pointed AT the removed nodes — an import
            # edge from another file, for instance.
            for key in [k for k in self._edges if k[1] == node_id]:
                self._edges.pop(key, None)

        for name, entries in list(self._global_symbols.items()):
            kept = [entry for entry in entries if entry[0] != rel]
            if kept:
                self._global_symbols[name] = kept
            else:
                self._global_symbols.pop(name, None)
                self._files_by_symbol_name.pop(name, None)

        self._symbols_in_file.pop(rel, None)
        self._file_imports.pop(rel, None)
        self._call_sites.pop(rel, None)

        for name, rels in list(self._callers_by_name.items()):
            rels.discard(rel)
            if not rels:
                self._callers_by_name.pop(name, None)

    def _add_edge(self, source: str, target: str, edge_type: str) -> None:
        self._edges[(source, target, edge_type)] = {
            "source": source, "target": target, "type": edge_type,
        }

    # ── Resolution ──────────────────────────────────────────────────────────

    def _resolve_imports_for(self, rel: str, file_facts: FileFacts) -> None:
        fid = f"file:{rel}"
        imported: dict[str, set[str]] = {}
        keys: list[tuple[str, str, str]] = []
        for imp in file_facts.imports:
            target_rel = _resolve_import(self._index, imp, rel, file_facts.suffix)
            if not target_rel:
                continue
            key = (fid, f"file:{target_rel}", "imports")
            self._add_edge(*key)
            keys.append(key)
            imported.setdefault(target_rel, set()).update(imp.get("names") or ())
        self._file_imports[rel] = imported
        self._import_edge_keys[rel] = keys

    def _resolve_calls_for(self, rel: str) -> None:
        """(Re)resolve the call edges of one file."""
        for key in self._call_edge_keys.pop(rel, []):
            self._edges.pop(key, None)

        keys: list[tuple[str, str, str]] = []
        per_file = self._symbols_in_file.get(rel, {})
        fid = f"file:{rel}"
        for call in self._call_sites.get(rel, []):
            if call.get("receiver"):
                continue
            if not call.get("enclosing"):
                src_id = fid
            else:
                enclosing = per_file.get(call.get("enclosing"))
                if not enclosing:
                    continue
                match = next(
                    (node_id for line, node_id in enclosing
                     if line == call.get("enclosing_line", 0)),
                    None,
                )
                src_id = match if match is not None else enclosing[0][1]

            target_id = _resolve_symbol(
                call.get("callee", ""), rel, src_id,
                self._symbols_in_file, self._file_imports, self._global_symbols,
            )
            if target_id and target_id != src_id:
                key = (src_id, target_id, "calls")
                self._add_edge(*key)
                keys.append(key)
        self._call_edge_keys[rel] = keys

    # ── Updating ────────────────────────────────────────────────────────────

    def apply(
        self,
        changed: Iterable[str] = (),
        removed: Iterable[str] = (),
    ) -> dict:
        """
        Apply a set of file changes and return the updated graph.

        `changed` and `removed` are repo-relative paths.
        """
        started = time.perf_counter()
        changed = {rel for rel in changed if rel}
        removed = {rel for rel in removed if rel}

        # A file that was removed and re-created is a change, not a
        # removal.
        removed -= changed

        file_set_changed = bool(removed)
        reparsed = 0
        reused = 0

        for rel in sorted(removed):
            self._remove_file(rel)
            self.facts.pop(rel, None)

        for rel in sorted(changed):
            path = self.root / rel
            if not path.is_file():
                # The file vanished between the event and the re-index.
                self._remove_file(rel)
                self.facts.pop(rel, None)
                file_set_changed = True
                continue
            if self.cache is not None:
                suffix = path.suffix
                facts = self.cache.get_for(
                    path, rel,
                    lambda data, r, _suffix=suffix: parse_bytes(data, r, _suffix),
                )
            else:
                facts = parse_file(path, rel)
            if facts.sha256 and self.facts.get(rel) is not None \
                    and self.facts[rel].sha256 == facts.sha256:
                reused += 1
            else:
                reparsed += 1
            self._remove_file(rel)
            self.facts[rel] = facts
            file_set_changed = True

        if file_set_changed:
            # The set of files changed, so the module index may have
            # changed, and any file's imports may now resolve elsewhere.
            self._index = build_module_index(self.facts)
            for rel, file_facts in self.facts.items():
                self._resolve_imports_for(rel, file_facts)

        # A file that was edited may have changed which symbols it
        # defines, so the call edges of files that call those symbols
        # must be re-resolved.
        affected_callers: set[str] = set()
        for rel in changed:
            for name in self._files_by_symbol_name.get(rel, set()):
                affected_callers |= self._callers_by_name.get(name, set())
        for rel in sorted(affected_callers | changed):
            if rel in self.facts:
                self._resolve_calls_for(rel)

        self._publish()

        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            "Incremental update: %d reparsed, %d unchanged, %.1f ms",
            reparsed, reused, elapsed_ms,
        )
        self.last_update = {
            "changed": sorted(changed),
            "removed": sorted(removed),
            "reparsed": reparsed,
            "unchanged": reused,
            "duration_ms": round(elapsed_ms, 2),
        }
        return self.graph

    def _publish(self) -> None:
        """Rebuild the public graph dict from the tables."""
        nodes = list(self._nodes.values())
        edges = list(self._edges.values())
        graph = {
            "nodes": nodes,
            "edges": edges,
            "summary": f"{len(nodes)} nodes, {len(edges)} edges",
        }
        try:
            from graph_analysis import attach_analysis

            attach_analysis(graph)
        except Exception as exc:  # noqa: BLE001 - analysis must never break the graph
            log.warning("Graph analysis failed, continuing without it: %s", exc)
        self.graph = graph
