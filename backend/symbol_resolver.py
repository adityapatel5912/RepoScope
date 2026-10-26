"""
symbol_resolver.py
Deterministic, conservative fact scanners and cross-file resolvers.

Schema v2 adds three questions the v1 builder never asked:

    routes      which HTTP routes does this file declare?
    api_calls   which client call targets one of those routes?
    heritage    which class does this class extend or implement?

Every answer here is derived from source bytes, never from an LLM. The
rule for every resolver is the same as the v1 call resolver: **a missing
edge is better than a guessed one**. When the target is ambiguous, the
edge is not emitted.

The scanners are per-file and cacheable (they feed `parse_cache.FileFacts`).
The resolvers are cross-file and run during graph finalization, because
they need the whole repository to decide what a name means.
"""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Iterable, Mapping

PY_EXTS = frozenset({".py", ".pyi"})
JS_EXTS = frozenset({".ts", ".tsx", ".js", ".jsx"})
WEB_EXTS = PY_EXTS | JS_EXTS

#: Decorator names that declare an HTTP (or WebSocket) route.
PY_ROUTE_METHODS = frozenset({
    "get", "post", "put", "patch", "delete", "route", "api_route", "websocket",
})

#: Express-style route declarations: `app.get("/api/x", handler)`.
_JS_ROUTE_RE = re.compile(
    r"\b(?:app|router|server|api)\s*\.\s*"
    r"(get|post|put|patch|delete|all)\s*\(\s*"
    r"(['\"])(?P<path>/[^'\"]*)\2"
    r"(?P<tail>[^\n)]*)",
    re.IGNORECASE,
)

#: `class Child(Base)` / `class Child extends Base implements A, B`.
_JS_HERITAGE_RE = re.compile(
    r"\bclass\s+(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"(?:extends\s+(?P<base>[A-Za-z_$][\w$.<>]*))?\s*"
    r"(?:implements\s+(?P<impl>[^{]+))?",
)

#: Client calls whose URL is the first argument.
_JS_FETCH_RE = re.compile(r"\bfetch\s*\(\s*(?P<quote>['\"`])(?P<url>[^'\"`]*)\1")
_JS_AXIOS_RE = re.compile(
    r"\baxios\s*\.\s*(get|post|put|patch|delete)\s*"
    r"\(\s*(?P<quote>['\"`])(?P<url>[^'\"`]*)\2",
    re.IGNORECASE,
)
_JS_EVENT_SOURCE_RE = re.compile(
    r"\bnew\s+EventSource\s*\(\s*(?P<quote>['\"`])(?P<url>[^'\"`]*)\1"
)
_JS_METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"]([A-Za-z]+)['\"]", re.IGNORECASE)


# ── Generic helpers ─────────────────────────────────────────────────────────

def _line_of(source: str, offset: int) -> int:
    """1-based line number for a character offset in `source`."""
    return source.count("\n", 0, offset) + 1


def _strip_js_comments(source: str) -> str:
    """
    Replace JS/TS comments with spaces, preserving every newline.

    Line numbers must stay true, so the replacement keeps the line
    structure. A regex that simply removed comments would shift every
    subsequent route and call by a line.
    """
    def blank(match: re.Match) -> str:
        return "\n" * match.group(0).count("\n")

    source = re.sub(r"/\*.*?\*/", blank, source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _normalize_ws(value: str) -> str:
    return " ".join(value.split())


def enclosing_symbol(
    symbols: Iterable[Mapping],
    line: int,
) -> tuple[str | None, int | None]:
    """
    The innermost symbol whose range contains `line`.

    A method's range always starts after its class's, so preferring the
    LATEST start line picks the method over the class that contains it.
    Module-level facts return `(None, None)` and are attributed to the
    file node by the caller.
    """
    if not line:
        return None, None
    best: tuple[int, str, int] | None = None
    for symbol in symbols:
        start = int(symbol.get("line") or 0)
        end = int(symbol.get("end_line") or start)
        if start <= line <= end and start:
            candidate = (start, str(symbol.get("name") or ""), start)
            if best is None or candidate[0] >= best[0]:
                best = candidate
    if best is None:
        return None, None
    return best[1], best[2]


def normalize_api_path(raw: str) -> str:
    """
    Turn a URL or template literal into a comparable route path.

    Full URLs keep only their path. `${id}` / `{id}` / `:id` / `<int:id>`
    become `*`, because a client that interpolates an id and a server
    that declares a parameter are describing the same endpoint.
    """
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" in value:
        from urllib.parse import urlsplit

        value = urlsplit(value).path or "/"
    value = value.split("?", 1)[0].split("#", 1)[0]
    value = re.sub(r"\$\{[^}]*\}", "*", value)
    value = re.sub(r"\{[^}]*\}", "*", value)
    value = re.sub(r"<[^>]*>", "*", value)
    value = re.sub(r"(?<=/):[A-Za-z_$][\w$]*", "*", value)
    value = re.sub(r"/+", "/", value)
    if not value.startswith("/"):
        value = "/" + value
    if len(value) > 1:
        value = value.rstrip("/")
    return value


def path_matches(route_path: str, call_path: str) -> tuple[bool, float]:
    """
    Does a client path select a declared route?

    Returns `(matched, confidence)`. A static match is exact; a match
    that leans on a parameter or an interpolated segment is weaker.
    Segment counts must agree, so `/api/x` never matches
    `/api/x/sub`.
    """
    route = normalize_api_path(route_path)
    call = normalize_api_path(call_path)
    if not route or not call:
        return False, 0.0
    route_has_wildcard = "*" in route
    call_has_wildcard = "*" in call
    if route == call:
        return True, 0.6 if (route_has_wildcard or call_has_wildcard) else 1.0

    route_parts = [part for part in route.split("/") if part]
    call_parts = [part for part in call.split("/") if part]
    if len(route_parts) != len(call_parts):
        return False, 0.0

    wildcard = False
    for declared, observed in zip(route_parts, call_parts):
        if declared == observed:
            continue
        if declared == "*" or observed == "*":
            wildcard = True
            continue
        return False, 0.0
    return True, 0.6 if wildcard else 0.8


# ── Python scanners ─────────────────────────────────────────────────────────

def _python_tree(source: str) -> ast.AST | None:
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError):
        return None


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _python_routes(tree: ast.AST) -> list[dict]:
    routes: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            attribute = func.attr if isinstance(func, ast.Attribute) else None
            if not attribute or attribute.lower() not in PY_ROUTE_METHODS:
                continue
            path = _literal_string(decorator.args[0]) if decorator.args else None
            if not path or not path.startswith("/"):
                continue

            method = attribute.lower()
            methods: list[str]
            if method == "websocket":
                methods = ["WS"]
            elif method in ("route", "api_route"):
                declared = None
                for keyword in decorator.keywords:
                    if keyword.arg == "methods":
                        try:
                            value = ast.literal_eval(keyword.value)
                        except (ValueError, SyntaxError):
                            value = None
                        if isinstance(value, (list, tuple)) and value:
                            declared = [str(item).upper() for item in value]
                methods = declared or ["GET"]
            else:
                methods = [method.upper()]

            for declared_method in methods:
                routes.append({
                    "method": declared_method,
                    "path": path,
                    "line": decorator.lineno,
                    "handler": node.name,
                    "handler_line": node.lineno,
                    "kind": "websocket" if method == "websocket" else "http",
                })
    routes.sort(key=lambda item: (item["line"], item["method"], item["path"]))
    return routes


def _python_api_calls(tree: ast.AST, symbols: list[dict]) -> list[dict]:
    """`requests.get`, `httpx.post`, and `client.get` calls with a path."""
    receivers = {"requests", "httpx", "client", "session", "http", "axios"}
    calls: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        method = ""
        receiver = ""
        if isinstance(func, ast.Attribute):
            method = func.attr.lower()
            if isinstance(func.value, ast.Name):
                receiver = func.value.id.lower()
            elif isinstance(func.value, ast.Attribute):
                receiver = func.value.attr.lower()
        else:
            continue
        if receiver not in receivers or method not in {
            "get", "post", "put", "patch", "delete", "request",
        }:
            continue
        if method == "request":
            if len(node.args) < 2:
                continue
            method = (_literal_string(node.args[0]) or "").upper()
            url_node = node.args[1]
        else:
            if not node.args:
                continue
            method = method.upper()
            url_node = node.args[0]
        url = _literal_string(url_node)
        if not url or not (url.startswith("/") or url.startswith("http")):
            continue
        enclosing, enclosing_line = enclosing_symbol(symbols, node.lineno)
        calls.append({
            "method": method,
            "path": url,
            "line": node.lineno,
            "enclosing": enclosing,
            "enclosing_line": enclosing_line,
            "origin": "python",
        })
    calls.sort(key=lambda item: (item["line"], item["method"], item["path"]))
    return calls


def _python_heritage(tree: ast.AST) -> list[dict]:
    heritage: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases: list[str] = []
        for base in node.bases:
            name = None
            if isinstance(base, ast.Name):
                name = base.id
            elif isinstance(base, ast.Attribute):
                name = base.attr
            elif isinstance(base, ast.Subscript):
                inner = base.value
                if isinstance(inner, ast.Name):
                    name = inner.id
                elif isinstance(inner, ast.Attribute):
                    name = inner.attr
            if name and name not in {"object", "ABC", "Protocol"}:
                bases.append(name)
        if bases:
            heritage.append({
                "class": node.name,
                "line": node.lineno,
                "bases": bases,
                "kind": "python",
            })
    heritage.sort(key=lambda item: (item["line"], item["class"]))
    return heritage


# ── JS/TS scanners ─────────────────────────────────────────────────────────

def _js_routes(source: str) -> list[dict]:
    routes: list[dict] = []
    for match in _JS_ROUTE_RE.finditer(source):
        tail = match.group("tail") or ""
        handler_match = re.match(
            r"\s*,\s*(?:async\s+)?([A-Za-z_$][\w$]*)", tail,
        )
        handler = handler_match.group(1) if handler_match else None
        routes.append({
            "method": match.group(1).upper(),
            "path": match.group("path"),
            "line": _line_of(source, match.start()),
            "handler": handler,
            "handler_line": None,
            "kind": "http",
        })
    routes.sort(key=lambda item: (item["line"], item["method"], item["path"]))
    return routes


def _js_api_calls(source: str, symbols: list[dict]) -> list[dict]:
    calls: list[dict] = []

    def add(method: str, url: str, offset: int, origin: str) -> None:
        line = _line_of(source, offset)
        enclosing, enclosing_line = enclosing_symbol(symbols, line)
        calls.append({
            "method": method,
            "path": url,
            "line": line,
            "enclosing": enclosing,
            "enclosing_line": enclosing_line,
            "origin": origin,
        })

    for match in _JS_FETCH_RE.finditer(source):
        line_end = source.find("\n", match.end())
        tail = source[match.end(): line_end if line_end != -1 else len(source)]
        method_match = _JS_METHOD_RE.search(tail)
        method = method_match.group(1).upper() if method_match else "GET"
        add(method, match.group("url"), match.start(), "fetch")

    for match in _JS_AXIOS_RE.finditer(source):
        add(match.group(1).upper(), match.group("url"), match.start(), "axios")

    for match in _JS_EVENT_SOURCE_RE.finditer(source):
        add("GET", match.group("url"), match.start(), "eventsource")

    calls.sort(key=lambda item: (item["line"], item["method"], item["path"]))
    return calls


def _js_heritage(source: str) -> list[dict]:
    heritage: list[dict] = []
    for match in _JS_HERITAGE_RE.finditer(source):
        bases: list[str] = []
        extends = (match.group("base") or "").strip()
        if extends:
            bases.append(_clean_type_name(extends))
        implements = match.group("impl") or ""
        for part in implements.split(","):
            cleaned = _clean_type_name(part)
            if cleaned:
                bases.append(cleaned)
        bases = [base for base in bases if base]
        if bases:
            heritage.append({
                "class": match.group("name"),
                "line": _line_of(source, match.start()),
                "bases": bases,
                "kind": "js",
            })
    heritage.sort(key=lambda item: (item["line"], item["class"]))
    return heritage


def _clean_type_name(raw: str) -> str:
    """`Base<T>` -> `Base`; `ns.Base` -> `Base`; `implements A` -> `A`."""
    value = _normalize_ws(raw)
    value = re.sub(r"<.*$", "", value).strip()
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    if not re.match(r"^[A-Za-z_$][\w$]*$", value):
        return ""
    return value


# ── Public scanners ────────────────────────────────────────────────────────

def scan_routes(source: str, rel: str, suffix: str) -> list[dict]:
    """Declared HTTP/WebSocket routes for one file."""
    del rel  # the caller owns path attribution; kept for a uniform signature
    if suffix in PY_EXTS:
        tree = _python_tree(source)
        return _python_routes(tree) if tree is not None else []
    if suffix in JS_EXTS:
        return _js_routes(_strip_js_comments(source))
    return []


def scan_api_calls(
    source: str,
    rel: str,
    suffix: str,
    symbols: list[dict] | None = None,
) -> list[dict]:
    """Client calls that may target one of the declared routes."""
    del rel
    symbols = symbols or []
    if suffix in PY_EXTS:
        tree = _python_tree(source)
        return _python_api_calls(tree, symbols) if tree is not None else []
    if suffix in JS_EXTS:
        return _js_api_calls(_strip_js_comments(source), symbols)
    return []


def scan_heritage(source: str, rel: str, suffix: str) -> list[dict]:
    """Class bases for one file. External bases are kept and resolved later."""
    del rel
    if suffix in PY_EXTS:
        tree = _python_tree(source)
        return _python_heritage(tree) if tree is not None else []
    if suffix in JS_EXTS:
        return _js_heritage(_strip_js_comments(source))
    return []


def scan_contract_facts(
    source: str,
    rel: str,
    suffix: str,
    symbols: list[dict] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """The three v2 fact families, scanned once per file."""
    return (
        scan_routes(source, rel, suffix),
        scan_api_calls(source, rel, suffix, symbols),
        scan_heritage(source, rel, suffix),
    )


# ── tsconfig / jsconfig aliases ────────────────────────────────────────────

def _strip_json_comments(text: str) -> str:
    """JSONC -> JSON, without touching newlines inside strings."""
    def blank(match: re.Match) -> str:
        return "\n" * match.group(0).count("\n")

    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.DOTALL)
    text = re.sub(r"(?m)//.*$", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def _load_config(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(_strip_json_comments(raw))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def load_path_aliases(root: str | Path) -> dict[str, list[str]]:
    """
    Repo-relative alias prefixes from every tsconfig/jsconfig in the tree.

    `{"@/*": ["src/*"]}` with `baseUrl: "."` becomes
    `{"@/*": ["src/*"]}`. The result is merged root-first, and a
    `frontend/` config is included because RepoScope itself keeps its
    TypeScript app there.

    The paths are normalized to the repository root, so the resolver
    never needs to know which config a hit came from.
    """
    root_path = Path(root)
    aliases: dict[str, list[str]] = {}
    configs = [
        root_path / "tsconfig.json",
        root_path / "jsconfig.json",
        root_path / "frontend" / "tsconfig.json",
        root_path / "frontend" / "jsconfig.json",
    ]
    for config_path in configs:
        data = _load_config(config_path)
        options = data.get("compilerOptions") or {}
        if not isinstance(options, dict):
            continue
        base_url = str(options.get("baseUrl") or ".")
        config_dir = config_path.parent.relative_to(root_path).as_posix()
        if config_dir == ".":
            prefix = ""
        else:
            prefix = config_dir + "/"
        base_parts = os.path.normpath(prefix + base_url).replace("\\", "/")
        if base_parts == ".":
            base_parts = ""
        paths = options.get("paths") or {}
        if not isinstance(paths, dict):
            continue
        for alias, targets in paths.items():
            if not isinstance(targets, list):
                continue
            resolved: list[str] = []
            for target in targets:
                if not isinstance(target, str):
                    continue
                joined = os.path.normpath(
                    "/".join(part for part in (base_parts, target) if part)
                ).replace("\\", "/")
                if joined.startswith(".."):
                    continue
                resolved.append(joined)
            if resolved:
                aliases.setdefault(str(alias), []).extend(resolved)
    return aliases


def resolve_alias_spec(spec: str, aliases: Mapping[str, list[str]]) -> list[str]:
    """Every repo-relative candidate path a specifier could mean."""
    candidates: list[str] = []
    for alias, targets in aliases.items():
        if alias.endswith("*"):
            prefix = alias[:-1]
            if not spec.startswith(prefix):
                continue
            suffix = spec[len(prefix):]
            for target in targets:
                if target.endswith("*"):
                    candidates.append(target[:-1] + suffix)
                else:
                    candidates.append(Path(target).joinpath(suffix).as_posix())
        elif spec == alias:
            candidates.extend(targets)
    # A stable order makes the chosen target deterministic.
    return sorted(dict.fromkeys(candidates))


# ── Cross-file resolution helpers ──────────────────────────────────────────

def barrel_reexports(
    facts: Mapping[str, Any],
    rel: str,
) -> list[str]:
    """
    The import targets a barrel file re-exports from.

    A JS/TS `export ... from` is marked by the parser's `re_export`
    flag. A Python package's `__init__.py` has no such syntax, so every
    import in it is treated as a re-export — which is what an
    `__init__.py` is for in practice.
    """
    file_facts = facts.get(rel)
    if file_facts is None:
        return []
    basename = Path(rel).name
    is_python_barrel = basename == "__init__.py"
    is_js_barrel = basename in {"index.ts", "index.js", "index.tsx", "index.jsx"}
    targets: list[str] = []
    for imp in getattr(file_facts, "imports", []) or []:
        if not (is_python_barrel or is_js_barrel or imp.get("re_export")):
            continue
        module = str(imp.get("module") or "")
        if module:
            targets.append(module)
    return sorted(dict.fromkeys(targets))


def class_owner_candidates(
    base_name: str,
    src_rel: str,
    classes_by_file: Mapping[str, set[str]],
    imports_by_file: Mapping[str, Mapping[str, set[str]]],
    class_rels: Mapping[str, set[str]],
) -> list[str]:
    """
    Files that could declare `base_name`, nearest first.

    Same order as the v1 call resolver: this file, then imported files,
    then the whole repository only when the name is globally unique.
    """
    rels: list[str] = []
    if base_name in classes_by_file.get(src_rel, set()):
        rels.append(src_rel)
    for imported_rel in imports_by_file.get(src_rel, {}):
        if base_name in classes_by_file.get(imported_rel, set()):
            rels.append(imported_rel)
    if not rels:
        globally = class_rels.get(base_name, set())
        if len(globally) == 1:
            rels = list(globally)
    return list(dict.fromkeys(rels))
