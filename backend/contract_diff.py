"""
contract_diff.py
AST-level interface and breaking-change diffing.

Milestone 5.1. Correction C3 is binding: `security_scanner.detect_breaking_in_patch`
ALREADY exists (regex-based). This module is the tree-sitter implementation, and
`detect_breaking_in_patch` DELEGATES to it — so there is exactly ONE source of truth.
Two divergent detectors would produce two different risk scores and duplicate PR
noise.

**What it detects.**

| Change | Severity |
|---|---|
| A deleted exported function / class / interface | BREAKING |
| A renamed parameter | BREAKING |
| An added REQUIRED parameter (no default) | BREAKING |
| A removed parameter | BREAKING when it was required |
| A changed return type | BREAKING |
| A removed or narrowed exported member | BREAKING |
| A renamed PRIVATE helper | **not flagged** |

That last row is the one that matters. A PR that renames a private helper is not a
breaking change, and a bot that says otherwise gets ignored — and then it gets
uninstalled.

**Precision.** A finding names the files that ACTUALLY CONSUME the changed symbol,
resolved through the call graph and the import edges — not every file in the directory.
A finding that names thirty files when three are affected is noise, and noise is
why bots get muted.

The extraction is genuinely AST-based: the parameter lists come from tree-sitter's
parameter nodes, not from a regular expression over the source text.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

log = logging.getLogger("reposcope.contract_diff")


# ── The contracts ───────────────────────────────────────────────────────────

@dataclass
class Param:
    """One parameter of a definition."""

    name: str
    type: str = ""
    has_default: bool = False
    optional: bool = False   # TypeScript's `?`

    @property
    def required(self) -> bool:
        return not self.has_default and not self.optional


@dataclass
class Contract:
    """One exported (or private) definition's public shape."""

    kind: str                     # function | class | interface | method
    name: str
    exported: bool = True
    params: list[Param] = field(default_factory=list)
    return_type: str = ""
    members: dict[str, "Contract"] = field(default_factory=dict)
    line: int = 0
    language: str = ""

    def signature(self) -> str:
        args = ", ".join(
            p.name + (f": {p.type}" if p.type else "") for p in self.params
        )
        suffix = f" -> {self.return_type}" if self.return_type else ""
        return f"{self.name}({args}){suffix}"


@dataclass
class Finding:
    """One contract change."""

    kind: str                # removed | renamed-parameter | required-parameter | ...
    symbol: str
    file: str
    line: int = 0
    severity: str = "BREAKING"   # BREAKING | WARNING | INFO
    message: str = ""
    guidance: str = ""
    consumers: list[str] = field(default_factory=list)   # repo-relative paths

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "symbol": self.symbol,
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
            "guidance": self.guidance,
            "consumers": self.consumers,
        }


# ── The AST extraction ──────────────────────────────────────────────────────

try:
    from tree_sitter import Language, Parser, Query, QueryCursor

    import tree_sitter_go
    import tree_sitter_javascript
    import tree_sitter_python
    import tree_sitter_rust
    import tree_sitter_typescript

    _LANGUAGES: dict[str, Language] = {
        "python": Language(tree_sitter_python.language()),
        "typescript": Language(tree_sitter_typescript.language_typescript()),
        "tsx": Language(tree_sitter_typescript.language_tsx()),
        "javascript": Language(tree_sitter_javascript.language()),
        "go": Language(tree_sitter_go.language()),
        "rust": Language(tree_sitter_rust.language()),
    }
    _AVAILABLE = True
except ImportError:  # pragma: no cover - the grammars are hard dependencies
    _AVAILABLE = False
    _LANGUAGES = {}

#: The definition queries, per language. A query naming a node type the
#: grammar lacks FAILS TO COMPILE, so each language gets its own.
_QUERIES: dict[str, str] = {
    "python": """
    (function_definition
      name: (identifier) @name
      parameters: (parameters) @params
      return_type: (type)? @ret) @def

    (class_definition
      name: (identifier) @name) @def
    """,
    "typescript": """
    (function_declaration
      name: (identifier) @name
      parameters: (formal_parameters) @params
      return_type: (type_annotation)? @ret) @def

    (class_declaration
      name: (type_identifier) @name) @def

    (method_definition
      name: (property_identifier) @name
      parameters: (formal_parameters) @params) @def
    """,
    "javascript": """
    (function_declaration
      name: (identifier) @name
      parameters: (formal_parameters) @params) @def

    (class_declaration
      name: (identifier) @name) @def

    (method_definition
      name: (property_identifier) @name
      parameters: (formal_parameters) @params) @def
    """,
    "go": """
    (function_declaration
      name: (identifier) @name
      parameters: (parameter_list) @params
      result: (_)? @ret) @def

    (method_declaration
      name: (field_identifier) @name
      parameters: (parameter_list) @params
      result: (_)? @ret) @def

    (type_declaration
      (type_spec
        name: (type_identifier) @name)) @def
    """,
    "rust": """
    (function_item
      name: (identifier) @name
      parameters: (parameters) @params
      return_type: (_)? @ret) @def

    (struct_item
      name: (type_identifier) @name) @def

    (enum_item
      name: (type_identifier) @name) @def

    (trait_item
      name: (type_identifier) @name) @def
    """,
}

#: `tsx` shares TypeScript's query set.
_QUERIES["tsx"] = _QUERIES["typescript"]


def _language_for(rel_path: str) -> str | None:
    suffix = Path(rel_path).suffix.lower()
    return {
        ".py": "python", ".pyi": "python",
        ".ts": "typescript", ".mts": "typescript", ".cts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
    }.get(suffix)


def _text(node, source: bytes) -> str:
    if node is None:
        return ""
    return source[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _is_exported(node, source: bytes, language: str) -> bool:
    """
    Is this definition part of the public surface?

    Each language marks exports differently:

    * Python   — no keyword; the convention is a leading underscore.
    * Go       — an exported name starts with a capital letter.
    * Rust     — the `pub` visibility modifier.
    * TS / JS  — the `export` keyword.
    """
    if language == "python":
        name_node = node.child_by_field_name("name")
        name = _text(name_node, source)
        return not name.startswith("_")
    if language == "rust":
        for child in node.children:
            if child.type == "visibility_modifier":
                return True
        return False
    if language == "go":
        name_node = node.child_by_field_name("name")
        name = _text(name_node, source)
        return bool(name) and name[0].isupper()
    # TypeScript / JavaScript
    current = node.parent
    while current is not None:
        if current.type == "export_statement":
            return True
        current = current.parent
    return False


def _extract_python_params(params_node, source: bytes) -> list[Param]:
    params: list[Param] = []
    if params_node is None:
        return params
    for child in params_node.named_children:
        kind = child.type
        if kind in ("identifier", "splat_pattern", "list_splat_pattern",
                    "dictionary_splat_pattern", "keyword_separator"):
            name = _text(child, source)
            if kind == "identifier":
                params.append(Param(name=name))
            continue
        if kind == "typed_parameter":
            # `typed_parameter` has a `type` field but NO `name` field —
            # the identifier is an unnamed child. (Only
            # `typed_default_parameter` carries a `name` field.)
            name = ""
            for named_child in child.named_children:
                if named_child.type == "identifier":
                    name = _text(named_child, source)
                    break
            type_ = _text(child.child_by_field_name("type"), source)
            params.append(Param(name=name, type=type_))
            continue
        if kind == "default_parameter":
            name = _text(child.child_by_field_name("name"), source)
            params.append(Param(name=name, has_default=True))
            continue
        if kind == "typed_default_parameter":
            name = _text(child.child_by_field_name("name"), source)
            type_ = _text(child.child_by_field_name("type"), source)
            params.append(Param(name=name, type=type_, has_default=True))
            continue
    return params


def _extract_ts_params(params_node, source: bytes) -> list[Param]:
    params: list[Param] = []
    if params_node is None:
        return params
    for child in params_node.named_children:
        if child.type == "required_parameter":
            pattern = child.child_by_field_name("pattern")
            type_ = _text(child.child_by_field_name("type"), source)
            has_default = any(c.type == "assignment_pattern" for c in child.named_children)
            params.append(Param(name=_text(pattern, source), type=type_, has_default=has_default))
        elif child.type == "optional_parameter":
            pattern = child.child_by_field_name("pattern")
            type_ = _text(child.child_by_field_name("type"), source)
            params.append(Param(name=_text(pattern, source), type=type_, optional=True))
    return params


def _extract_go_params(params_node, source: bytes) -> list[Param]:
    params: list[Param] = []
    if params_node is None:
        return params
    for child in params_node.named_children:
        if child.type != "parameter_declaration":
            continue
        name_node = child.child_by_field_name("name")
        type_ = _text(child.child_by_field_name("type"), source)
        name = _text(name_node, source)
        if not name:
            # An unnamed parameter — `func f(int, string)`.
            name = type_
        params.append(Param(name=name, type=type_))
    return params


def _extract_rust_params(params_node, source: bytes) -> list[Param]:
    params: list[Param] = []
    if params_node is None:
        return params
    for child in params_node.named_children:
        if child.type != "parameter":
            continue
        pattern = child.child_by_field_name("pattern")
        type_ = _text(child.child_by_field_name("type"), source)
        params.append(Param(name=_text(pattern, source), type=type_))
    return params


_PARAM_EXTRACTORS = {
    "python": _extract_python_params,
    "typescript": _extract_ts_params,
    "tsx": _extract_ts_params,
    "javascript": _extract_ts_params,
    "go": _extract_go_params,
    "rust": _extract_rust_params,
}


def extract_contracts(source: bytes, rel_path: str) -> dict[str, Contract]:
    """
    Every definition in a file, with its public shape.

    Returns a mapping of `name` to contract. A class's members are nested
    inside it.
    """
    language = _language_for(rel_path)
    if language is None or not _AVAILABLE:
        return {}

    try:
        parser = Parser(_LANGUAGES[language])
        query = Query(_LANGUAGES[language], _QUERIES[language])
    except Exception as exc:  # noqa: BLE001 - a grammar problem must not break the scan
        log.warning("Could not prepare the %s grammar: %s", language, exc)
        return {}

    tree = parser.parse(source)
    captures = QueryCursor(query).captures(tree.root_node)
    names = captures.get("name", [])
    defs = captures.get("def", [])
    params_nodes = captures.get("params", [])
    returns = captures.get("ret", [])

    name_by_def: dict[tuple[int, int], object] = {}
    for name_node in names:
        parent = name_node.parent
        if parent is not None:
            name_by_def[(parent.start_byte, parent.end_byte)] = name_node

    params_by_def: dict[tuple[int, int], object] = {}
    for params_node in params_nodes:
        parent = params_node.parent
        if parent is not None:
            params_by_def[(parent.start_byte, parent.end_byte)] = params_node

    ret_by_def: dict[tuple[int, int], object] = {}
    for ret_node in returns:
        parent = ret_node.parent
        if parent is not None:
            ret_by_def[(parent.start_byte, parent.end_byte)] = ret_node

    contracts: dict[str, Contract] = {}
    for def_node in defs:
        name_node = name_by_def.get((def_node.start_byte, def_node.end_byte))
        if name_node is None:
            continue
        name = _text(name_node, source)
        if not name:
            continue

        key = (def_node.start_byte, def_node.end_byte)
        contract = Contract(
            kind="function" if def_node.type in (
                "function_definition", "function_declaration",
                "function_item", "method_definition",
            ) else "class",
            name=name,
            exported=_is_exported(def_node, source, language),
            line=def_node.start_point[0] + 1,
            language=language,
        )

        params_node = params_by_def.get(key)
        extractor = _PARAM_EXTRACTORS.get(language)
        if extractor is not None:
            contract.params = extractor(params_node, source)

        ret_node = ret_by_def.get(key)
        if ret_node is not None:
            contract.return_type = _text(ret_node, source).lstrip(":").strip()

        contracts[name] = contract

    return contracts


# ── The comparison ──────────────────────────────────────────────────────────

def _param_map(contract: Contract) -> dict[str, Param]:
    return {p.name: p for p in contract.params}


def diff_contracts(
    old: dict[str, Contract],
    new: dict[str, Contract],
    file: str,
) -> list[Finding]:
    """
    Compare two versions of a file's contracts.

    Only EXPORTED symbols are considered. A private helper may change
    freely — that is the whole point of it being private.
    """
    findings: list[Finding] = []

    for name, old_contract in old.items():
        if not old_contract.exported:
            continue

        new_contract = new.get(name)

        # ── Removed ──
        if new_contract is None:
            findings.append(Finding(
                kind="removed",
                symbol=name,
                file=file,
                line=old_contract.line,
                severity="BREAKING",
                message=f"Exported {old_contract.kind} `{name}` was removed",
                guidance=(
                    "If this is part of the public API, deprecate it first "
                    "(warn for one release), then remove it, and note it in a "
                    "BREAKING CHANGES section."
                ),
            ))
            continue

        # ── Parameters ──
        #
        # The comparison is POSITION-AWARE. A renamed parameter is one
        # finding — "renamed-parameter" — not the two findings a
        # name-set comparison would produce ("removed" plus "required
        # added"). Two findings for one rename is how a reviewer learns
        # to ignore the bot.
        old_list = list(old_contract.params)
        new_list = list(new_contract.params)
        old_params = _param_map(old_contract)
        new_params = _param_map(new_contract)

        for index, old_param in enumerate(old_list):
            if index >= len(new_list):
                break
            new_param = new_list[index]
            if old_param.name == new_param.name:
                continue
            if (
                old_param.type and new_param.type
                and old_param.type != new_param.type
            ):
                # A different parameter took the slot — not a rename.
                continue
            findings.append(Finding(
                kind="renamed-parameter",
                symbol=name,
                file=file,
                line=new_contract.line,
                severity="BREAKING",
                message=(
                    f"Parameter `{old_param.name}` of `{name}` was renamed to "
                    f"`{new_param.name}` — every caller using the old name breaks"
                ),
                guidance=(
                    f"Keep `{old_param.name}` as an alias, or update every "
                    f"caller listed below."
                ),
            ))
            old_params.pop(old_param.name, None)
            new_params.pop(new_param.name, None)

        for param_name, old_param in old_params.items():
            new_param = new_params.get(param_name)
            if new_param is None:
                if old_param.required:
                    findings.append(Finding(
                        kind="removed-parameter",
                        symbol=name,
                        file=file,
                        line=old_contract.line,
                        severity="BREAKING",
                        message=(
                            f"Parameter `{param_name}` was removed from `{name}` — "
                            f"every caller that passes it now fails"
                        ),
                        guidance=(
                            "Keep the parameter and ignore it, or give it a "
                            "default so existing callers keep working."
                        ),
                    ))
                else:
                    findings.append(Finding(
                        kind="removed-parameter",
                        symbol=name,
                        file=file,
                        line=old_contract.line,
                        severity="INFO",
                        message=(
                            f"Optional parameter `{param_name}` was removed from "
                            f"`{name}`"
                        ),
                        guidance="Callers that omit it are unaffected.",
                    ))
                continue

            # The same name, but a different type.
            if (
                old_param.type and new_param.type
                and old_param.type != new_param.type
            ):
                findings.append(Finding(
                    kind="retyped-parameter",
                    symbol=name,
                    file=file,
                    line=old_contract.line,
                    severity="BREAKING",
                    message=(
                        f"Parameter `{param_name}` of `{name}` changed type: "
                        f"`{old_param.type}` → `{new_param.type}`"
                    ),
                    guidance="Callers passing the old type will fail.",
                ))

        for param_name, new_param in new_params.items():
            if param_name in old_params:
                continue
            if new_param.required:
                findings.append(Finding(
                    kind="required-parameter",
                    symbol=name,
                    file=file,
                    line=new_contract.line,
                    severity="BREAKING",
                    message=(
                        f"Required parameter `{param_name}` was added to `{name}` — "
                        f"every existing caller now passes too few arguments"
                    ),
                    guidance=(
                        f"Give `{param_name}` a default value, or add an overload "
                        f"that keeps the old signature."
                    ),
                ))
            else:
                findings.append(Finding(
                    kind="optional-parameter",
                    symbol=name,
                    file=file,
                    line=new_contract.line,
                    severity="INFO",
                    message=f"Optional parameter `{param_name}` was added to `{name}`",
                    guidance="Existing callers are unaffected.",
                ))

        # ── Return type ──
        if (
            old_contract.return_type and new_contract.return_type
            and old_contract.return_type != new_contract.return_type
        ):
            findings.append(Finding(
                kind="return-type",
                symbol=name,
                file=file,
                line=new_contract.line,
                severity="BREAKING",
                message=(
                    f"The return type of `{name}` changed: "
                    f"`{old_contract.return_type}` → `{new_contract.return_type}`"
                ),
                guidance=(
                    "Callers that depend on the old shape break at runtime, "
                    "not at compile time — which is worse."
                ),
            ))

        # ── Exported members ──
        for member_name, old_member in old_contract.members.items():
            new_member = new_contract.members.get(member_name)
            if new_member is None:
                findings.append(Finding(
                    kind="removed-member",
                    symbol=f"{name}.{member_name}",
                    file=file,
                    line=old_member.line,
                    severity="BREAKING",
                    message=(
                        f"Exported member `{name}.{member_name}` was removed"
                    ),
                    guidance="Consumers of that member break.",
                ))

    return findings


def diff_routes(old_source: str, new_source: str, file: str) -> list[Finding]:
    """Detect removed, modified, or altered API route endpoints across Python and JS/TS."""
    findings: list[Finding] = []
    suffix = Path(file).suffix.lower()
    try:
        from symbol_resolver import scan_routes
        old_routes = scan_routes(old_source, file, suffix)
        new_routes = scan_routes(new_source, file, suffix)
    except Exception as exc:  # noqa: BLE001
        log.warning("Route diff failed for %s: %s", file, exc)
        return []

    if not old_routes and not new_routes:
        return []

    new_map = {}
    for r in new_routes:
        m = (r.get("methods") or [r.get("method", "GET")])[0].upper()
        p = str(r.get("path") or "")
        new_map[f"{m} {p}"] = r

    for old_r in old_routes:
        m = (old_r.get("methods") or [old_r.get("method", "GET")])[0].upper()
        p = str(old_r.get("path") or "")
        key = f"{m} {p}"
        if key not in new_map:
            # Check if same handler was repurposed with different route
            altered = False
            for new_key, new_r in new_map.items():
                if new_r.get("handler") and new_r.get("handler") == old_r.get("handler"):
                    findings.append(Finding(
                        kind="altered-route",
                        symbol=key,
                        file=file,
                        line=new_r.get("line") or old_r.get("line") or 1,
                        severity="BREAKING",
                        message=(
                            f"API Route `{key}` was altered to `{new_key}` for handler `{old_r.get('handler')}` — "
                            f"external and client callers will break"
                        ),
                        guidance="Keep previous route path as an alias or deprecate via headers before changing.",
                    ))
                    altered = True
                    break
            if not altered:
                findings.append(Finding(
                    kind="removed-route",
                    symbol=key,
                    file=file,
                    line=old_r.get("line") or 1,
                    severity="BREAKING",
                    message=f"API Route `{key}` was removed — frontend and API clients targeting it will fail",
                    guidance="Deprecate route with HTTP headers before removing, or provide backward-compatible redirection.",
                ))

    return findings


def diff_sources(old_source: str, new_source: str, file: str) -> list[Finding]:
    """
    Compare two versions of a file.

    This is the entry point `security_scanner.detect_breaking_in_patch`
    delegates to, so there is exactly one detector.
    """
    old_contracts = extract_contracts(old_source.encode("utf-8"), file)
    new_contracts = extract_contracts(new_source.encode("utf-8"), file)
    findings = diff_contracts(old_contracts, new_contracts, file)
    findings.extend(diff_routes(old_source, new_source, file))
    return findings


def sources_from_patch(patch: str) -> tuple[str, str]:
    """
    Reconstruct the old and new source from a unified diff.

    The context lines are shared; the `-` lines belong to the old
    version and the `+` lines to the new one. The result is a fragment
    rather than a whole file, but tree-sitter parses a fragment happily
    and a signature is a local construct.
    """
    old_lines: list[str] = []
    new_lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            old_lines.append(line[1:])
            continue
        if line.startswith("+"):
            new_lines.append(line[1:])
            continue
        context = line[1:] if line.startswith(" ") else line
        old_lines.append(context)
        new_lines.append(context)
    return "\n".join(old_lines), "\n".join(new_lines)


# ── Precision: who actually consumes the change ─────────────────────────────

def find_consumers(
    graph: dict,
    file: str,
    symbol: str,
) -> list[str]:
    """
    The files that ACTUALLY consume a symbol or route in a file.

    Resolves callers across both backend and frontend:
    - Direct symbol calls (`calls` edges)
    - Cross-stack REST/WS client calls (`api_calls` edges)
    - Module imports (`imports` edges)
    """
    if not graph:
        return []

    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []

    target_ids = {
        node["id"] for node in nodes
        if node.get("file") == file and node.get("label") == symbol
    }

    consumers: set[str] = set()

    # 1. Call edges: something calls this symbol directly
    if target_ids:
        for edge in edges:
            if edge.get("type") == "calls" and edge.get("target") in target_ids:
                source = next(
                    (n for n in nodes if n["id"] == edge.get("source")), None,
                )
                if source is not None and source.get("file"):
                    consumers.add(str(source["file"]))

    # 2. Cross-stack API-call edges (e.g. frontend fetch/axios calling backend routes)
    route_path = symbol.split()[-1] if "/" in symbol else None
    for edge in edges:
        if edge.get("type") == "api_calls":
            ev = edge.get("evidence") or {}
            ev_path = str(ev.get("path") or "")
            target_matches = edge.get("target") in target_ids if target_ids else False
            if target_matches or (route_path and ev_path and (route_path in ev_path or ev_path in route_path)):
                source = next((n for n in nodes if n["id"] == edge.get("source")), None)
                if source is not None and source.get("file"):
                    consumers.add(str(source["file"]))

    # 3. Import edges: something imports the file that defines it
    file_id = f"file:{file}"
    for edge in edges:
        if edge.get("type") == "imports" and (edge.get("target") == file_id or (target_ids and edge.get("target") in target_ids)):
            source = next(
                (n for n in nodes if n["id"] == edge.get("source")), None,
            )
            if source is not None and source.get("file"):
                consumers.add(str(source["file"]))

    consumers.discard(file)
    return sorted(consumers)


def attach_consumers(findings: Iterable[Finding], graph: dict) -> list[Finding]:
    """Resolve each finding's consumers against the graph."""
    resolved: list[Finding] = []
    for finding in findings:
        finding.consumers = find_consumers(graph, finding.file, finding.symbol)
        resolved.append(finding)
    return resolved


def findings_to_dicts(findings: Iterable[Finding]) -> list[dict]:
    """The findings as plain dicts, for the API and the PR comment."""
    return [finding.to_dict() for finding in findings]
