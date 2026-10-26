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

from parse_cache import SKIP_DIRS, FileFacts, ParseCache, hash_bytes
from parsers.base import type_name as _base_type_name
from parsers.registry import get_parser
from symbol_resolver import (
    class_owner_candidates,
    load_path_aliases,
    normalize_api_path,
    path_matches,
    resolve_alias_spec,
    scan_contract_facts,
)

log = logging.getLogger("reposcope.graph_builder")

_SKIP_DIRS = set(SKIP_DIRS)

_PY_EXTS = {".py"}
_JS_EXTS = {".ts", ".tsx", ".js", ".jsx"}

#: Files that are never source, even though they live inside the tree.
#: `newest_source_mtime` uses this to decide whether an index is stale.
#: Without it, a running server's own log (`backend/logs/app.log`) is
#: newer than the index on every start, so the MCP server rebuilds a
#: 347-file graph every time it launches.
_NON_SOURCE_SUFFIXES = {
    ".log", ".tmp", ".temp", ".pyc", ".pyo", ".map", ".wasm",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp",
    ".pdf", ".pptx", ".docx", ".zip", ".tar", ".gz", ".7z",
    ".vsix",
}


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
    source = data.decode("utf-8", "replace")
    if parser is not None:
        try:
            result = parser.extract(data, rel)
        except Exception as exc:  # noqa: BLE001 - a bad file must not stop the graph
            log.warning("Parser failed for %s: %s", rel, exc)
            return FileFacts(
                rel=rel, suffix=suffix, size=len(data), sha256="",
                warnings=[f"parser failed: {exc}"],
            )
        symbols = [_symbol_to_dict(s) for s in result.symbols]
        routes, api_calls, heritage = scan_contract_facts(
            source, rel, suffix, symbols,
        )
        return FileFacts(
            rel=rel,
            suffix=suffix,
            size=len(data),
            sha256="",
            symbols=symbols,
            imports=[_import_to_dict(i) for i in result.imports],
            calls=[_call_to_dict(c) for c in result.calls],
            receivers=[
                {
                    "name": r.name, "type": r.type, "line": r.line,
                    "scope": r.scope, "scope_line": r.scope_line,
                }
                for r in result.receivers
            ],
            routes=routes,
            api_calls=api_calls,
            heritage=heritage,
            warnings=list(result.warnings),
        )

    symbols, imports, warnings = _fallback_facts(data, rel, suffix)
    routes, api_calls, heritage = scan_contract_facts(
        source, rel, suffix, symbols,
    )
    return FileFacts(
        rel=rel, suffix=suffix, size=len(data), sha256="",
        symbols=symbols, imports=imports, calls=[], warnings=warnings,
        routes=routes, api_calls=api_calls, heritage=heritage,
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

    __slots__ = (
        "py_index", "py_stems", "py_dotted", "py_tail", "js_files", "js_stems",
        "aliases",
    )

    def __init__(self) -> None:
        self.py_index: dict[str, str] = {}
        self.py_stems: dict[str, str] = {}
        # The dotted path of every python file ("backend.api.routers.analysis")
        # and a lookup from the LAST segment of that path to the paths that
        # end with it. Together they answer "which file does `from
        # api.routers import analysis` mean?" when the repository never
        # names `backend/` as a source root.
        self.py_dotted: dict[str, str] = {}
        self.py_tail: dict[str, list[str]] = {}
        self.js_files: set[str] = set()
        self.js_stems: dict[str, str] = {}
        #: tsconfig/jsconfig path aliases, repo-relative. Empty when the
        #: repository has no config; `@/` and `~/` still work as before.
        self.aliases: dict[str, list[str]] = {}


def build_module_index(
    facts: Mapping[str, FileFacts],
    root: str | Path | None = None,
) -> ModuleIndex:
    index = ModuleIndex()
    if root is not None:
        index.aliases = load_path_aliases(root)
    for rel, file_facts in facts.items():
        suffix = file_facts.suffix
        if suffix in _PY_EXTS:
            parts = rel[:-3].split("/")                      # strip .py
            if parts[-1] == "__init__":
                index.py_index[".".join(parts[:-1])] = f"file:{rel}"
            index.py_index[".".join(parts)] = f"file:{rel}"
            index.py_stems.setdefault(parts[-1], f"file:{rel}")
            # The dotted path of the module this file provides. A package
            # is named by its directory, a module by its own name.
            dotted = (
                ".".join(parts[:-1]) if parts[-1] == "__init__" else ".".join(parts)
            )
            if dotted:
                index.py_dotted[dotted] = f"file:{rel}"
                index.py_tail.setdefault(dotted.rsplit(".", 1)[-1], []).append(dotted)
        elif suffix in _JS_EXTS:
            index.js_files.add(rel)
            index.js_stems.setdefault(Path(rel).stem, f"file:{rel}")
    return index


def _suffix_lookup(index: ModuleIndex, dotted: str) -> str | None:
    """
    Resolve a dotted module path against the repository's files, allowing
    the path to start at a source root the repository never names.

    A repository is not always imported from its own root. `backend/` is a
    source root in this project, so `backend/main.py` says
    `from graph_builder import build_graph_from_repo` — and "graph_builder"
    is not the file's dotted path ("backend.graph_builder"). Without this
    lookup the import never resolves, the edge is never drawn, and every
    blast radius downstream of it reads "no dependents".

    The match is a SUFFIX match: "api.routers.analysis" matches
    "backend.api.routers.analysis". It is tried only after the exact
    dotted-path lookup fails, so a full path always wins.
    """
    if not dotted:
        return None
    tail = dotted.rsplit(".", 1)[-1]
    for candidate in index.py_tail.get(tail, ()):
        if candidate == dotted or candidate.endswith("." + dotted):
            return index.py_dotted[candidate]
    return None


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
    # Most specific first. `from api.routers import analysis` names a
    # MODULE, not the package that contains it — so `api.routers.analysis`
    # is tried before `api.routers`, and the edge points at the file the
    # developer actually imported from.
    for variant in reversed(variants):
        if variant in index.py_index:
            return index.py_index[variant]
    # The module may be named from a source root the repository does not
    # declare. `from graph_builder import x` in `backend/main.py` means
    # `backend/graph_builder.py`.
    for variant in reversed(variants):
        hit = _suffix_lookup(index, variant)
        if hit:
            return hit
    # bare-stem fallback (flat layouts / src-less repos)
    if imported_name and imported_name in index.py_stems:
        return index.py_stems[imported_name]
    return None


def _js_candidates(base: str) -> list[str]:
    """Every file a module base could resolve to, most specific first."""
    norm = os.path.normpath(base).replace("\\", "/")
    candidates = [norm]
    candidates.extend(f"{norm}{ext}" for ext in (".ts", ".tsx", ".js", ".jsx"))
    candidates.extend(
        f"{norm}/index{ext}" for ext in (".ts", ".tsx", ".js", ".jsx")
    )
    return candidates


def _resolve_js(index: ModuleIndex, spec: str, importer_rel: str) -> str | None:
    """Resolve a JS/TS import specifier to a file id, or None (external)."""
    bases: list[str] = []
    if spec.startswith("./") or spec.startswith("../"):
        bases.append(
            (Path(importer_rel).parent / spec).as_posix()
        )
    else:
        # tsconfig/jsconfig aliases win over the historical `@/` shorthand.
        bases.extend(resolve_alias_spec(spec, index.aliases))
        if spec.startswith("@/") or spec.startswith("~/"):
            bases.extend([spec[2:], f"src/{spec[2:]}"])
        if not bases:
            return None  # bare package import — external, skip

    for base in dict.fromkeys(bases):
        for candidate in _js_candidates(base):
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


def _resolve_qualified(
    call: Mapping,
    src_rel: str,
    receiver_decls: dict[str, list[dict]],
    symbol_parents: dict[tuple[str, str, int], str | None],
    classes_by_file: dict[str, set[str]],
    methods_by_class: dict[tuple[str, str], dict[str, str]],
    class_rels: dict[str, set[str]],
    file_imports: dict[str, dict[str, set[str]]],
    attributes_by_class: dict[tuple[str, str], dict[str, set[str]]],
) -> str | None:
    """
    Resolve `repo.save()` when the receiver's type is known locally.

    Tier-4 resolution, M9.2. The source of truth is a parser-emitted
    `receivers` fact: a parameter annotation, a typed variable, or a
    `new Type()` assignment. `self`/`this` resolve through the enclosing
    class. A chained receiver (`self.repo.save()`) is followed one
    attribute at a time when the class declares that attribute's type.
    If any link is unknown or ambiguous, the call is left unlinked — the
    same conservative contract as unqualified resolution.
    """
    callee = call.get("callee") or ""
    receiver = call.get("receiver") or ""
    if not callee or not receiver:
        return None

    scope = call.get("enclosing") or ""
    scope_line = int(call.get("enclosing_line") or 0)
    parts = receiver.split(".")
    base = parts[0]
    base_type = ""

    if base in ("self", "this") and scope:
        base_type = symbol_parents.get((src_rel, scope, scope_line)) or ""

    if not base_type:
        best_line = -1
        call_line = int(call.get("line") or 0)
        for decl in receiver_decls.get(src_rel, []):
            if decl.get("name") != base:
                continue
            if (decl.get("scope") or "") != scope:
                continue
            if (
                scope_line and decl.get("scope_line")
                and int(decl.get("scope_line") or 0) != scope_line
            ):
                continue
            decl_line = int(decl.get("line") or 0)
            # Pick the declaration in effect AT the call, not a later
            # reassignment of the same name.
            if call_line and decl_line > call_line:
                continue
            if decl_line >= best_line:
                best_line = decl_line
                base_type = decl.get("type") or ""

    if not base_type:
        return None
    current_type = _base_type_name(base_type)
    current_rels = _class_rels_for_type(
        current_type, src_rel, classes_by_file, class_rels, file_imports
    )

    # Follow `a.b.c` through declared class attributes.
    for member in parts[1:]:
        attribute_types: set[str] = set()
        for rel in current_rels:
            attribute_types.update(
                attributes_by_class.get((rel, current_type), {}).get(member, set())
            )
        if len(attribute_types) != 1:
            return None
        current_type = _base_type_name(next(iter(attribute_types)))
        current_rels = _class_rels_for_type(
            current_type, src_rel, classes_by_file, class_rels, file_imports
        )
        if not current_rels:
            return None

    targets: list[str] = []
    for rel in current_rels:
        node_id = methods_by_class.get((rel, current_type), {}).get(callee)
        if node_id:
            targets.append(node_id)
    if len(targets) == 1:
        return targets[0]
    return None


def _class_rels_for_type(
    type_name_value: str,
    src_rel: str,
    classes_by_file: dict[str, set[str]],
    class_rels: dict[str, set[str]],
    file_imports: dict[str, dict[str, set[str]]],
) -> list[str]:
    """The files that could declare `type_name_value`, nearest first."""
    rels: list[str] = []
    if type_name_value in classes_by_file.get(src_rel, set()):
        rels.append(src_rel)
    for imported_rel in file_imports.get(src_rel, {}):
        if type_name_value in classes_by_file.get(imported_rel, set()):
            rels.append(imported_rel)
    if not rels:
        # The class is not imported with a binding this resolver can see
        # (a bare module import, for example). Only a globally unique
        # class name is safe.
        globally = class_rels.get(type_name_value, set())
        if len(globally) == 1:
            rels = list(globally)
    return rels


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


def assemble_graph(
    facts: Mapping[str, FileFacts],
    root: str | Path | None = None,
) -> dict:
    """
    Assemble a whole repository's graph from its per-file facts.

    This is the C10 contract in one place: node ids, node types, edge
    types. The input is per-file facts, so this stage can run over cached
    results without touching the disk.

    `root` is optional and used only to read tsconfig/jsconfig aliases.
    When it is absent, resolution falls back to the v1 behaviour, so an
    in-memory caller still gets a valid v1-compatible graph.
    """
    index = build_module_index(facts, root=root)

    nodes: list[dict] = []
    edges: list[dict] = []
    symbols_in_file: dict[str, dict[str, list[tuple[int, str]]]] = {}
    file_imports: dict[str, dict[str, set[str]]] = {}
    global_symbols: dict[str, list[tuple[str, str]]] = {}
    pending_calls: list[tuple[str, str, dict]] = []
    # Tier-4 resolution tables (M9.2).
    receiver_decls: dict[str, list[dict]] = {}
    symbol_parents: dict[tuple[str, str, int], str | None] = {}
    classes_by_file: dict[str, set[str]] = {}
    methods_by_class: dict[tuple[str, str], dict[str, str]] = {}
    class_rels: dict[str, set[str]] = {}
    attributes_by_class: dict[tuple[str, str], dict[str, set[str]]] = {}

    for rel in sorted(facts):
        file_facts = facts[rel]
        fid = f"file:{rel}"
        nodes.append({
            "id": fid,
            "type": "file",
            "label": rel,
            "language": file_facts.suffix.lstrip(".") or "txt",
            "size": file_facts.size,
            # The content hash. It is what makes the incremental index
            # possible — and Milestone 6.2 asks for it to be stored per
            # file, which the SQLite store does.
            "sha256": file_facts.sha256,
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
            symbol_parents[(rel, name, int(symbol.get("line") or 0))] = symbol.get("parent")
            if kind == "class":
                classes_by_file.setdefault(rel, set()).add(name)
                class_rels.setdefault(name, set()).add(rel)
            elif symbol.get("parent"):
                methods_by_class.setdefault((rel, str(symbol["parent"])), {}).setdefault(name, node_id)
        symbols_in_file[rel] = per_file
        receiver_decls[rel] = list(file_facts.receivers)
        for declaration in file_facts.receivers:
            declared_name = declaration.get("name") or ""
            declared_scope = declaration.get("scope") or ""
            if declared_scope and "." in declared_name:
                attribute = declared_name.split(".", 1)[1]
                attributes_by_class.setdefault(
                    (rel, declared_scope), {}
                ).setdefault(attribute, set()).add(declaration.get("type") or "")

        imported: dict[str, set[str]] = {}
        for imp in file_facts.imports:
            target_rel = _resolve_import(index, imp, rel, file_facts.suffix)
            if not target_rel:
                continue
            edges.append({"source": fid, "target": f"file:{target_rel}", "type": "imports"})
            imported.setdefault(target_rel, set()).update(imp.get("names") or ())
        file_imports[rel] = imported

        for call in file_facts.calls:
            if not call.get("enclosing"):
                # A call at module level is attributed to the file itself.
                pending_calls.append((rel, fid, call))
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
            pending_calls.append((rel, match, call))

    for src_rel, src_id, call in pending_calls:
        if call.get("receiver"):
            target_id = _resolve_qualified(
                call, src_rel, receiver_decls, symbol_parents,
                classes_by_file, methods_by_class, class_rels, file_imports,
                attributes_by_class,
            )
        else:
            target_id = _resolve_symbol(
                call.get("callee", ""), src_rel, src_id,
                symbols_in_file, file_imports, global_symbols,
            )
        if target_id and target_id != src_id:
            edges.append({"source": src_id, "target": target_id, "type": "calls"})

    unique_edges = _dedupe_edges(edges)
    graph = {
        "nodes": nodes,
        "edges": unique_edges,
        "summary": f"{len(nodes)} nodes, {len(unique_edges)} edges",
    }

    finalize_graph(graph, facts, root=root)

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


# ── Schema v2 finalization ──────────────────────────────────────────────────

#: Edges derived from the graph's own facts during finalization. They are
#: stripped before recomputation so finalize is idempotent.
DERIVED_EDGE_TYPES = frozenset({"inherits", "exports", "api_calls"})

#: What a schema v2 graph can answer that a v1 graph cannot.
GRAPH_CAPABILITIES = (
    "roles", "pillars", "routes", "api_calls", "inherits", "exports",
)


def finalize_graph(
    graph: dict,
    facts: Mapping[str, FileFacts],
    root: str | Path | None = None,
) -> dict:
    """
    Enrich a v1 graph with schema v2 evidence, in place, and return it.

    The v1 graph is never rewritten: ids, labels, edge directions and
    the three v1 edge types are exactly what `assemble_graph` produced.
    Everything here is additive.

    The function is idempotent. Full builds and the incremental indexer
    both call it, and the incremental graph must equal a fresh rebuild
    including the v2 edges — so derived edges and node fields are
    removed before they are recomputed, never appended twice.
    """
    from graph_store import SCHEMA_VERSION
    from mindmap_classifier import classify_file, classify_symbol

    nodes: list[dict] = graph.setdefault("nodes", [])
    edges: list[dict] = [
        edge for edge in graph.get("edges", []) or []
        if edge.get("type") not in DERIVED_EDGE_TYPES
    ]

    for node in nodes:
        for derived in (
            "path", "pillar", "role", "route_count", "routes", "end_line",
        ):
            node.pop(derived, None)

    index = build_module_index(facts, root=root)

    file_nodes: dict[str, dict] = {}
    symbol_by_key: dict[tuple[str, str, int], str] = {}
    symbols_by_file_name: dict[tuple[str, str], list[tuple[int, str]]] = {}
    class_node_by_file_name: dict[tuple[str, str], str] = {}
    classes_by_file: dict[str, set[str]] = {}
    class_rels: dict[str, set[str]] = {}

    for node in nodes:
        node_id = str(node.get("id") or "")
        node_type = node.get("type")
        if node_type == "file" and node_id.startswith("file:"):
            file_nodes[node_id[len("file:"):]] = node
        elif node_type in ("function", "class"):
            rel = str(node.get("file") or "")
            label = str(node.get("label") or "")
            line = int(node.get("line") or 0)
            if not rel or not label:
                continue
            symbol_by_key[(rel, label, line)] = node_id
            symbols_by_file_name.setdefault((rel, label), []).append((line, node_id))
            if node_type == "class":
                class_node_by_file_name.setdefault((rel, label), node_id)
                classes_by_file.setdefault(rel, set()).add(label)
                class_rels.setdefault(label, set()).add(rel)

    for entries in symbols_by_file_name.values():
        entries.sort(key=lambda item: item[0])

    file_imports: dict[str, dict[str, set[str]]] = {}
    for rel, file_facts in facts.items():
        resolved: dict[str, set[str]] = {}
        for imp in file_facts.imports:
            target_rel = _resolve_import(index, imp, rel, file_facts.suffix)
            if target_rel and target_rel != rel:
                resolved.setdefault(target_rel, set()).update(
                    imp.get("names") or ()
                )
        file_imports[rel] = resolved

    def symbol_node(
        rel: str, name: str | None, line: int | None,
    ) -> str | None:
        if not name:
            return None
        if line:
            exact = symbol_by_key.get((rel, name, int(line)))
            if exact:
                return exact
        candidates = symbols_by_file_name.get((rel, name))
        return candidates[0][1] if candidates else None

    # ── Route table ──────────────────────────────────────────────────────
    api_routes: list[dict] = []
    routes_by_node: dict[str, list[dict]] = {}
    route_count_by_file: dict[str, int] = {}
    seen_routes: set[tuple] = set()
    for rel in sorted(facts):
        file_facts = facts[rel]
        for route in file_facts.routes:
            method = str(route.get("method") or "GET").upper()
            path = str(route.get("path") or "")
            if not path.startswith("/"):
                continue
            handler = route.get("handler") or ""
            handler_line = route.get("handler_line") or route.get("line")
            handler_id = symbol_node(rel, handler, handler_line)
            if handler_id is None:
                handler_node = file_nodes.get(rel)
                handler_id = handler_node.get("id") if handler_node else None
            if not handler_id:
                continue
            declaration_line = int(route.get("line") or 0)
            key = (method, path, rel, str(handler), declaration_line)
            if key in seen_routes:
                continue
            seen_routes.add(key)
            line = declaration_line
            handler_node = next(
                (node for node in nodes if node.get("id") == handler_id), None,
            )
            if handler_node and handler_node.get("type") in ("function", "class"):
                line = int(handler_node.get("line") or declaration_line)
            record = {
                "method": method,
                "path": path,
                "file": rel,
                "line": line,
                "handler": str(handler),
                "node_id": handler_id,
            }
            api_routes.append(record)
            routes_by_node.setdefault(handler_id, []).append({
                "method": method,
                "path": path,
                "line": declaration_line,
            })
            route_count_by_file[rel] = route_count_by_file.get(rel, 0) + 1

    api_routes.sort(key=lambda item: (
        item["file"], item["line"], item["method"], item["path"],
    ))
    for route_list in routes_by_node.values():
        route_list.sort(key=lambda item: (item["line"], item["method"], item["path"]))

    # ── Node enrichment ─────────────────────────────────────────────────
    file_classification: dict[str, dict] = {}
    for rel, node in file_nodes.items():
        info = classify_file(rel, route_count=route_count_by_file.get(rel, 0))
        file_classification[rel] = info
        node["path"] = rel
        node["pillar"] = info["pillar"]
        node["role"] = info["role"]
        node["route_count"] = route_count_by_file.get(rel, 0)

    symbol_end_lines: dict[tuple[str, str, int], int] = {}
    for rel, file_facts in facts.items():
        for symbol in file_facts.symbols:
            symbol_end_lines[(
                rel,
                str(symbol.get("name") or ""),
                int(symbol.get("line") or 0),
            )] = int(symbol.get("end_line") or symbol.get("line") or 0)

    for node in nodes:
        if node.get("type") not in ("function", "class"):
            continue
        rel = str(node.get("file") or "")
        label = str(node.get("label") or "")
        line = int(node.get("line") or 0)
        info = file_classification.get(rel) or classify_file(rel)
        node["path"] = rel
        node["pillar"] = info["pillar"]
        end_line = symbol_end_lines.get((rel, label, line))
        if end_line:
            node["end_line"] = end_line
        node_id = str(node.get("id") or "")
        route_list = routes_by_node.get(node_id)
        if route_list:
            node["role"] = "api_controller"
            node["routes"] = [dict(route) for route in route_list]
        else:
            node["role"] = classify_symbol(node, info["role"])

    # ── Inheritance edges ───────────────────────────────────────────────
    for rel in sorted(facts):
        file_facts = facts[rel]
        for entry in file_facts.heritage:
            class_name = str(entry.get("class") or "")
            class_line = int(entry.get("line") or 0)
            source_id = symbol_node(rel, class_name, class_line)
            if not source_id:
                continue
            for base_name in entry.get("bases") or []:
                owners = class_owner_candidates(
                    str(base_name), rel, classes_by_file, file_imports, class_rels,
                )
                targets = [
                    class_node_by_file_name[(owner, str(base_name))]
                    for owner in owners
                    if (owner, str(base_name)) in class_node_by_file_name
                ]
                unique_targets = sorted(set(targets))
                if len(unique_targets) != 1 or unique_targets[0] == source_id:
                    continue
                target_id = unique_targets[0]
                owner_rel = next(
                    (owner for owner in owners
                     if class_node_by_file_name.get((owner, str(base_name))) == target_id),
                    rel,
                )
                if owner_rel == rel:
                    confidence = 1.0
                elif owner_rel in file_imports.get(rel, {}):
                    confidence = 0.9
                else:
                    confidence = 0.7
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "type": "inherits",
                    "evidence": {
                        "kind": "inheritance",
                        "file": rel,
                        "line": class_line,
                        "base": str(base_name),
                        "confidence": confidence,
                    },
                })

    # ── Re-export edges ─────────────────────────────────────────────────
    for rel in sorted(facts):
        file_facts = facts[rel]
        basename = Path(rel).name
        is_python_barrel = basename == "__init__.py"
        is_js_barrel = basename in {"index.ts", "index.js", "index.tsx", "index.jsx"}
        seen_targets: set[str] = set()
        for imp in file_facts.imports:
            exports_this = (
                is_python_barrel or is_js_barrel or bool(imp.get("re_export"))
            )
            if not exports_this:
                continue
            target_rel = _resolve_import(index, imp, rel, file_facts.suffix)
            if not target_rel or target_rel == rel or target_rel in seen_targets:
                continue
            seen_targets.add(target_rel)
            edges.append({
                "source": f"file:{rel}",
                "target": f"file:{target_rel}",
                "type": "exports",
                "evidence": {
                    "kind": "re_export",
                    "file": rel,
                    "line": int(imp.get("line") or 0),
                    "module": str(imp.get("module") or ""),
                    "confidence": 1.0,
                },
            })

    # ── Cross-stack API-call edges ──────────────────────────────────────
    for rel in sorted(facts):
        file_facts = facts[rel]
        for call in file_facts.api_calls:
            method = str(call.get("method") or "GET").upper()
            call_path = str(call.get("path") or "")
            if not call_path:
                continue
            matches: list[tuple[float, dict]] = []
            for record in api_routes:
                if record["method"] not in ("ALL", method):
                    continue
                matched, confidence = path_matches(record["path"], call_path)
                if matched:
                    matches.append((confidence, record))
            if not matches:
                continue
            best = max(confidence for confidence, _record in matches)
            top = [record for confidence, record in matches if confidence == best]
            targets = {record["node_id"] for record in top}
            if len(targets) != 1:
                # Two handlers match equally well. A guessed cross-stack
                # edge is worse than no edge.
                continue
            target_id = next(iter(targets))
            source_id = symbol_node(
                rel,
                call.get("enclosing"),
                call.get("enclosing_line"),
            )
            if source_id is None:
                file_node = file_nodes.get(rel)
                source_id = file_node.get("id") if file_node else None
            if not source_id or source_id == target_id:
                continue
            record = top[0]
            edges.append({
                "source": source_id,
                "target": target_id,
                "type": "api_calls",
                "evidence": {
                    "kind": "http_call",
                    "file": rel,
                    "line": int(call.get("line") or 0),
                    "method": method,
                    "path": normalize_api_path(call_path),
                    "route": normalize_api_path(record["path"]),
                    "confidence": best,
                },
            })

    graph["schema_version"] = SCHEMA_VERSION
    graph["metadata"] = {
        "builder": "graph_builder",
        "capabilities": list(GRAPH_CAPABILITIES),
    }
    graph["api_routes"] = api_routes
    graph["edges"] = _dedupe_edges(edges)
    graph["nodes"] = nodes
    graph["summary"] = f"{len(nodes)} nodes, {len(graph['edges'])} edges"
    return graph


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

    # Prune the skip list DURING the walk. `rglob("*")` still descended
    # into .git, node_modules and .venv and discarded them afterwards;
    # on this repository that was 15+ seconds of traversal per build.
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
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


def newest_source_mtime(root: str | Path) -> float:
    """
    The newest modification time among the repository's source files.

    This is how a reader knows whether a persisted index is still true.
    An index built at 10:00 and a source file edited at 10:05 cannot both
    be right, and the index is the one that is wrong.

    The skip list is the same one the builder uses, so a generated
    directory never makes an index look stale.
    """
    root_path = Path(root)
    newest = 0.0
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            try:
                rel = str(path.relative_to(root_path)).replace("\\", "/")
            except ValueError:
                continue
            if any(part in _SKIP_DIRS for part in rel.split("/")):
                continue
            if path.suffix.lower() in _NON_SOURCE_SUFFIXES:
                continue
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                continue
    return newest


def build_graph_from_repo(root: str, cache: ParseCache | None = None) -> dict:
    """
    Parse a repository into nodes + edges. Returns the graph dict.

    Correction C10: this signature and the shape it returns are
    load-bearing. `cache` is an optional accelerator — the graph it
    produces is identical with or without one.
    """
    facts = collect_facts(root, cache)
    graph = assemble_graph(facts, root=root)
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
        # Tier-4 resolution tables (M9.2).
        self._receiver_decls: dict[str, list[dict]] = {}
        self._symbol_parents: dict[tuple[str, str, int], str | None] = {}
        self._classes_by_file: dict[str, set[str]] = {}
        self._methods_by_class: dict[tuple[str, str], dict[str, str]] = {}
        self._class_rels: dict[str, set[str]] = {}
        self._attributes_by_class: dict[tuple[str, str], dict[str, set[str]]] = {}
        self._call_sites: dict[str, list[dict]] = {}
        self._import_edge_keys: dict[str, list[tuple[str, str, str]]] = {}
        self._call_edge_keys: dict[str, list[tuple[str, str, str]]] = {}
        self._files_by_symbol_name: dict[str, set[str]] = {}
        self._symbol_names_by_file: dict[str, set[str]] = {}
        self._callers_by_name: dict[str, set[str]] = {}

        self.graph: dict = {"nodes": [], "edges": [], "summary": "0 nodes, 0 edges"}

    # ── Building ────────────────────────────────────────────────────────────

    def index(self) -> dict:
        """
        Index the whole repository from scratch.

        Two passes, and the second one matters. A call is resolved by
        NAME, so `Card.tsx` calling `formatName` can only resolve once
        `format.ts` has been added. Resolving calls as each file is
        added — in alphabetical order — silently dropped every call to a
        file that sorts later. The full rebuild does the same two passes,
        which is why the two graphs have to be compared.
        """
        self.facts = collect_facts(self.root, self.cache)
        self._index = build_module_index(self.facts, root=self.root)
        self._reset_tables()
        for rel in sorted(self.facts):
            self._add_file(rel, self.facts[rel], resolve_calls=False)
        for rel in sorted(self.facts):
            self._resolve_calls_for(rel)
        self._publish()
        return self.graph

    def _reset_tables(self) -> None:
        self._nodes = {}
        self._edges = {}
        self._node_ids_by_file = {}
        self._symbols_in_file = {}
        self._file_imports = {}
        self._global_symbols = {}
        self._receiver_decls = {}
        self._symbol_parents = {}
        self._classes_by_file = {}
        self._methods_by_class = {}
        self._class_rels = {}
        self._attributes_by_class = {}
        self._call_sites = {}
        self._import_edge_keys = {}
        self._call_edge_keys = {}
        self._files_by_symbol_name = {}
        self._symbol_names_by_file = {}
        self._callers_by_name = {}

    def _add_file(self, rel: str, file_facts: FileFacts, resolve_calls: bool = True) -> None:
        """Insert one file's nodes, imports and call sites into the tables."""
        fid = f"file:{rel}"
        self._nodes[fid] = {
            "id": fid,
            "type": "file",
            "label": rel,
            "language": file_facts.suffix.lstrip(".") or "txt",
            "size": file_facts.size,
            "sha256": file_facts.sha256,
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
            self._symbol_parents[(rel, name, int(symbol.get("line") or 0))] = symbol.get("parent")
            if kind == "class":
                self._classes_by_file.setdefault(rel, set()).add(name)
                self._class_rels.setdefault(name, set()).add(rel)
            elif symbol.get("parent"):
                self._methods_by_class.setdefault(
                    (rel, str(symbol["parent"])), {}
                ).setdefault(name, node_id)

        self._symbols_in_file[rel] = per_file
        self._receiver_decls[rel] = list(file_facts.receivers)
        for declaration in file_facts.receivers:
            declared_name = declaration.get("name") or ""
            declared_scope = declaration.get("scope") or ""
            if declared_scope and "." in declared_name:
                attribute = declared_name.split(".", 1)[1]
                self._attributes_by_class.setdefault(
                    (rel, declared_scope), {}
                ).setdefault(attribute, set()).add(declaration.get("type") or "")
        self._node_ids_by_file[rel] = node_ids
        self._symbol_names_by_file[rel] = set(per_file)
        self._call_sites[rel] = list(file_facts.calls)
        for call in file_facts.calls:
            callee = call.get("callee") or ""
            if callee:
                self._callers_by_name.setdefault(callee, set()).add(rel)

        self._resolve_imports_for(rel, file_facts)
        if resolve_calls:
            self._resolve_calls_for(rel)

    def _remove_file(self, rel: str, drop_incoming: bool = True) -> None:
        """
        Remove one file's nodes and edges from the tables.

        `drop_incoming` controls the edges that point AT this file's
        nodes. They belong to OTHER files — an `imports` edge from a
        caller, or a `calls` edge to a symbol here.

        When the file is being DELETED, those edges must go: their target
        no longer exists, and a dangling edge is worse than a missing
        one.

        When the file is being RE-ADDED — the content changed, the path
        did not — they must STAY. The node ids are derived from the
        path, so the incoming edges are still perfectly valid, and
        dropping them would break every importer of the edited file. The
        edges into the file's SYMBOLS are re-resolved separately, because
        a rename genuinely changes them.
        """
        for key in self._import_edge_keys.pop(rel, []):
            self._edges.pop(key, None)
        for key in self._call_edge_keys.pop(rel, []):
            self._edges.pop(key, None)

        for node_id in self._node_ids_by_file.pop(rel, []):
            self._nodes.pop(node_id, None)
            # Drop the edges that LEAVE the removed nodes.
            for key in [k for k in self._edges if k[0] == node_id]:
                self._edges.pop(key, None)
            if drop_incoming:
                # Drop the edges that pointed AT the removed nodes.
                for key in [k for k in self._edges if k[1] == node_id]:
                    self._edges.pop(key, None)

        for name, entries in list(self._global_symbols.items()):
            kept = [entry for entry in entries if entry[0] != rel]
            if kept:
                self._global_symbols[name] = kept
            else:
                self._global_symbols.pop(name, None)
            # The owner set has to lose this file even when ANOTHER file
            # still defines the same name — otherwise the file would
            # still be listed as an owner of a symbol it no longer has,
            # and the call re-resolution would chase a phantom.
            owners = self._files_by_symbol_name.get(name)
            if owners is not None:
                owners.discard(rel)
                if not owners:
                    self._files_by_symbol_name.pop(name, None)

        self._symbols_in_file.pop(rel, None)
        self._file_imports.pop(rel, None)
        self._call_sites.pop(rel, None)
        self._symbol_names_by_file.pop(rel, None)
        self._receiver_decls.pop(rel, None)
        self._classes_by_file.pop(rel, None)
        for key in [k for k in self._symbol_parents if k[0] == rel]:
            self._symbol_parents.pop(key, None)
        for key in [k for k in self._methods_by_class if k[0] == rel]:
            self._methods_by_class.pop(key, None)
        for key in [k for k in self._attributes_by_class if k[0] == rel]:
            self._attributes_by_class.pop(key, None)
        for name, rels in list(self._class_rels.items()):
            rels.discard(rel)
            if not rels:
                self._class_rels.pop(name, None)

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

            if call.get("receiver"):
                target_id = _resolve_qualified(
                    call, rel, self._receiver_decls, self._symbol_parents,
                    self._classes_by_file, self._methods_by_class,
                    self._class_rels, self._file_imports,
                    self._attributes_by_class,
                )
            else:
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

        reparsed = 0
        reused = 0
        file_set_changed = False

        # ── 1. Parse the changed files ──────────────────────────────────────
        # The facts table has to be final before the module index is
        # rebuilt, so this happens first.
        new_facts: dict[str, FileFacts] = {}
        for rel in sorted(changed):
            path = self.root / rel
            if not path.is_file():
                # The file vanished between the event and the re-index.
                removed.add(rel)
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

            previous = self.facts.get(rel)
            if previous is not None and facts.sha256 and previous.sha256 == facts.sha256:
                # The content did not actually change — a touch, a
                # re-save of the same bytes. Nothing to re-index.
                reused += 1
                continue

            reparsed += 1
            if previous is None:
                file_set_changed = True
            new_facts[rel] = facts

        # ── 2. Apply the file-set change ────────────────────────────────────
        for rel in sorted(removed):
            self.facts.pop(rel, None)
        self.facts.update(new_facts)

        # ── 3. Rebuild the module index when the file SET changed ───────────
        # A content change cannot alter which module a path resolves to;
        # an added or removed file can.
        if file_set_changed:
            self._index = build_module_index(self.facts, root=self.root)

        # ── 4. Drop the old nodes and edges of every changed file ──────────
        #
        # The symbol names the changed files define, captured BEFORE the
        # removal — a caller of a symbol that the edit DELETED must have
        # its call edge re-resolved too, and after the removal that
        # symbol is no longer in the table.
        affected_names: set[str] = set()
        for rel in set(new_facts) | removed:
            affected_names |= self._symbol_names_by_file.get(rel, set())
        for rel in new_facts:
            affected_names |= {
                str(symbol.get("name", ""))
                for symbol in new_facts[rel].symbols
                if symbol.get("name")
            }

        for rel in sorted(set(new_facts) | removed):
            # A file that is being re-added keeps its incoming edges —
            # the path, and therefore every node id that depends on it,
            # has not changed. A file that is genuinely gone loses them.
            self._remove_file(rel, drop_incoming=rel not in new_facts)

        # ── 5. Re-add the changed files ─────────────────────────────────────
        for rel in sorted(new_facts):
            self._add_file(rel, new_facts[rel])

        # ── 6. Re-resolve every import when the module index moved ─────────
        # A file that was added or removed can change where somebody
        # ELSE's import resolves to, so every file's import edges are
        # recomputed. This is cheap — it is arithmetic over cached facts,
        # not a re-parse.
        if file_set_changed:
            for rel, file_facts in self.facts.items():
                self._resolve_imports_for(rel, file_facts)

        # ── 7. Re-resolve the calls that the edit could have changed ───────
        #
        # A call resolves to a symbol by name. If the edit changed which
        # symbols a file defines, every caller of those names has to be
        # re-resolved — including a caller whose call used to resolve
        # and now does not.
        affected_callers: set[str] = set()
        for name in affected_names:
            affected_callers |= self._callers_by_name.get(name, set())
        # A qualified call's target is named by the RECEIVER's type, not
        # just by the method name. If a class gains/loses a method, the
        # files that import that class must re-resolve even when the
        # method name itself did not change.
        touched = set(new_facts) | removed
        for src_rel, imported_map in self._file_imports.items():
            if touched.intersection(imported_map):
                affected_callers.add(src_rel)
        for rel in sorted(affected_callers | set(new_facts)):
            if rel in self.facts:
                self._resolve_calls_for(rel)

        self._publish()

        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            "Incremental update: %d reparsed, %d unchanged, %.1f ms",
            reparsed, reused, elapsed_ms,
        )
        self.last_update = {
            "changed": sorted(new_facts),
            "removed": sorted(removed),
            "reparsed": reparsed,
            "unchanged": reused,
            "duration_ms": round(elapsed_ms, 2),
        }
        return self.graph

    def _publish(self) -> None:
        """Rebuild the public graph dict from the tables."""
        # Copies matter: finalize adds derived fields and edges. If it
        # mutated the live tables directly, the next publish would start
        # from already-enriched nodes and the incremental graph could
        # drift from a full rebuild.
        nodes = [dict(node) for node in self._nodes.values()]
        edges = [dict(edge) for edge in self._edges.values()]
        graph = {
            "nodes": nodes,
            "edges": edges,
            "summary": f"{len(nodes)} nodes, {len(edges)} edges",
        }
        finalize_graph(graph, self.facts, root=self.root)
        try:
            from graph_analysis import attach_analysis

            attach_analysis(graph)
        except Exception as exc:  # noqa: BLE001 - analysis must never break the graph
            log.warning("Graph analysis failed, continuing without it: %s", exc)
        self.graph = graph
