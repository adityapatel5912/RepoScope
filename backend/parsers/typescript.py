"""
parsers/typescript.py
Tree-sitter parsers for TypeScript, TSX, and JavaScript.

Milestone 1.1.

Node types confirmed against tree-sitter-typescript 0.23 and
tree-sitter-javascript 0.25:

    function_declaration        name: identifier
    class_declaration           name: type_identifier   (TS) / identifier (JS)
    method_definition           name: property_identifier
    interface_declaration       name: type_identifier   (TS only)
    type_alias_declaration      name: type_identifier   (TS only)
    lexical_declaration         -> variable_declarator -> arrow_function
    import_statement            source: string
    export_statement            source: string   (when it has a `from`)
    call_expression             function: identifier | member_expression

TypeScript and JavaScript need separate query sets: a tree-sitter query
that names a node type the grammar does not have fails to compile.
"""
from __future__ import annotations

from tree_sitter import Language, Parser, Query, QueryCursor

from parsers.base import (
    CallSite,
    Import,
    ParseResult,
    Symbol,
    compute_complexity,
    first_child_of_type,
    text_of,
)

try:
    import tree_sitter_javascript
    import tree_sitter_typescript
except ImportError:  # pragma: no cover - the grammars are hard dependencies
    tree_sitter_javascript = None
    tree_sitter_typescript = None


# ── Query sets ──────────────────────────────────────────────────────────────

TS_SYMBOL_QUERY = """
(function_declaration
  name: (identifier) @sym.name) @sym.function

(class_declaration
  name: (type_identifier) @sym.name) @sym.class

(method_definition
  name: (property_identifier) @sym.name) @sym.function

(interface_declaration
  name: (type_identifier) @sym.name) @sym.class

(type_alias_declaration
  name: (type_identifier) @sym.name) @sym.class

(variable_declarator
  name: (identifier) @sym.name
  value: (arrow_function)) @sym.function
"""

JS_SYMBOL_QUERY = """
(function_declaration
  name: (identifier) @sym.name) @sym.function

(class_declaration
  name: (identifier) @sym.name) @sym.class

(method_definition
  name: (property_identifier) @sym.name) @sym.function

(variable_declarator
  name: (identifier) @sym.name
  value: (arrow_function)) @sym.function
"""

TS_IMPORT_QUERY = """
(import_statement
  source: (string) @import.source)

(export_statement
  source: (string) @import.source)
"""

JS_IMPORT_QUERY = """
(import_statement
  source: (string) @import.source)

(export_statement
  source: (string) @import.source)
"""

TS_CALL_QUERY = """
(call_expression
  function: (identifier) @call.name)

(call_expression
  function: (member_expression) @call.member)
"""

JS_CALL_QUERY = TS_CALL_QUERY


def _string_value(node) -> str:
    """The contents of a `string` node, without the quotes."""
    raw = node.text.decode("utf-8", "replace")
    if len(raw) >= 2 and raw[0] in "\"'`" and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


class _ECMAScriptParser:
    """Shared implementation for the TypeScript and JavaScript families."""

    language_name = "typescript"
    symbol_query_text = TS_SYMBOL_QUERY
    import_query_text = TS_IMPORT_QUERY
    call_query_text = TS_CALL_QUERY

    def __init__(self, language: Language) -> None:
        self._language = language
        self._parser = Parser(language)
        self._symbol_query = Query(language, self.symbol_query_text)
        self._import_query = Query(language, self.import_query_text)
        self._call_query = Query(language, self.call_query_text)

    def extract(self, source: bytes, rel_path: str) -> ParseResult:
        result = ParseResult()
        tree = self._parser.parse(source)
        root = tree.root_node

        if root.has_error:
            result.warnings.append(f"{rel_path}: parse error, partial result")

        self._extract_symbols(root, source, result)
        self._extract_imports(root, source, result)
        self._extract_calls(root, source, result)
        return result

    # ── Symbols ────────────────────────────────────────────────────────────

    def _extract_symbols(self, root, source: bytes, result: ParseResult) -> None:
        captures = QueryCursor(self._symbol_query).captures(root)
        names = captures.get("sym.name", [])
        defs = (
            captures.get("sym.function", [])
            + captures.get("sym.class", [])
        )

        name_by_def: dict[tuple[int, int], object] = {}
        for name_node in names:
            parent = name_node.parent
            if parent is not None:
                name_by_def[(parent.start_byte, parent.end_byte)] = name_node

        for def_node in defs:
            name_node = name_by_def.get((def_node.start_byte, def_node.end_byte))
            if name_node is None:
                continue
            is_class = def_node.type in (
                "class_declaration", "interface_declaration", "type_alias_declaration",
            )
            body = first_child_of_type(def_node, ("statement_block", "interface_body", "class_body"))
            name = name_node.text.decode("utf-8", "replace")
            result.symbols.append(
                Symbol(
                    name=name,
                    kind="class" if is_class else "function",
                    line=def_node.start_point[0] + 1,
                    end_line=def_node.end_point[0] + 1,
                    signature=text_of(def_node, source, 160),
                    exported=self._is_exported(def_node),
                    parent=self._enclosing_class(def_node),
                    complexity=compute_complexity(body or def_node, source, self.language_name),
                )
            )

    def _is_exported(self, node) -> bool:
        """True when the definition sits inside an `export` statement."""
        current = node.parent
        while current is not None and current.type != "program":
            if current.type == "export_statement":
                return True
            current = current.parent
        return False

    def _enclosing_class(self, node) -> str | None:
        current = node.parent
        while current is not None:
            if current.type in ("class_declaration", "class_body"):
                class_node = current
                while class_node is not None and class_node.type != "class_declaration":
                    class_node = class_node.parent
                if class_node is not None:
                    name = first_child_of_type(
                        class_node, ("type_identifier", "identifier")
                    )
                    if name is not None:
                        return name.text.decode("utf-8", "replace")
                return None
            current = current.parent
        return None

    # ── Imports ────────────────────────────────────────────────────────────

    def _extract_imports(self, root, source: bytes, result: ParseResult) -> None:
        captures = QueryCursor(self._import_query).captures(root)
        for source_node in captures.get("import.source", []):
            statement = source_node.parent
            if statement is None:
                continue
            module = _string_value(source_node)
            result.imports.append(
                Import(
                    module=module,
                    line=statement.start_point[0] + 1,
                    names=self._imported_names(statement),
                    is_relative=module.startswith("."),
                    re_export=statement.type == "export_statement",
                )
            )

    @staticmethod
    def _imported_names(statement) -> tuple[str, ...]:
        """
        The names an import statement binds.

        `import { a, b as c } from "./m"` binds `a` and `c`. Knowing the
        bound names makes call resolution precise: a call to `a` can only
        resolve to a module that actually exports `a`, rather than to any
        imported module that happens to define a symbol with that name.
        """
        names: list[str] = []
        stack = [statement]
        while stack:
            node = stack.pop()
            if node.type == "import_specifier":
                alias = node.child_by_field_name("alias")
                if alias is not None:
                    names.append(alias.text.decode("utf-8", "replace"))
                    continue
                identifier = first_child_of_type(node, ("identifier",))
                if identifier is not None:
                    names.append(identifier.text.decode("utf-8", "replace"))
            elif node.type == "namespace_import":
                identifier = first_child_of_type(node, ("identifier",))
                if identifier is not None:
                    names.append(identifier.text.decode("utf-8", "replace"))
            elif node.type == "import_clause":
                identifier = first_child_of_type(node, ("identifier",))
                if identifier is not None:
                    names.append(identifier.text.decode("utf-8", "replace"))
            stack.extend(node.children)
        return tuple(names)

    # ── Calls ──────────────────────────────────────────────────────────────

    def _extract_calls(self, root, source: bytes, result: ParseResult) -> None:
        captures = QueryCursor(self._call_query).captures(root)

        for name_node in captures.get("call.name", []):
            call_node = name_node.parent
            if call_node is None:
                continue
            enclosing, enclosing_line = self._enclosing_symbol(call_node)
            result.calls.append(
                CallSite(
                    callee=name_node.text.decode("utf-8", "replace"),
                    line=call_node.start_point[0] + 1,
                    enclosing=enclosing,
                    enclosing_line=enclosing_line,
                )
            )

        # `obj.method()` — `member_expression` has no object:/property:
        # fields in this grammar, so the receiver and the method name are
        # taken from its children: the object first, the property last.
        for member_node in captures.get("call.member", []):
            call_node = member_node.parent
            if call_node is None:
                continue
            receiver = None
            callee = None
            for child in member_node.children:
                if child.type == "identifier":
                    receiver = child.text.decode("utf-8", "replace")
                elif child.type == "property_identifier":
                    callee = child.text.decode("utf-8", "replace")
            if not callee:
                continue
            enclosing, enclosing_line = self._enclosing_symbol(call_node)
            result.calls.append(
                CallSite(
                    callee=callee,
                    line=call_node.start_point[0] + 1,
                    receiver=receiver,
                    enclosing=enclosing,
                    enclosing_line=enclosing_line,
                )
            )

    def _enclosing_symbol(self, node) -> tuple[str | None, int]:
        """The name and line of the symbol a call sits inside."""
        current = node.parent
        while current is not None:
            if current.type in (
                "function_declaration", "method_definition", "class_declaration",
                "variable_declarator",
            ):
                name = first_child_of_type(current, ("identifier", "property_identifier"))
                if name is not None:
                    return (
                        name.text.decode("utf-8", "replace"),
                        current.start_point[0] + 1,
                    )
            current = current.parent
        return None, 0


class TypeScriptParser(_ECMAScriptParser):
    """Parses .ts and .mts."""

    name = "typescript"
    extensions = (".ts", ".mts", ".cts")
    language_name = "typescript"

    def __init__(self) -> None:
        if tree_sitter_typescript is None:
            raise RuntimeError("tree-sitter-typescript is not installed")
        super().__init__(Language(tree_sitter_typescript.language_typescript()))


class TsxParser(_ECMAScriptParser):
    """Parses .tsx — the same grammar, with JSX enabled."""

    name = "tsx"
    extensions = (".tsx",)
    language_name = "typescript"

    def __init__(self) -> None:
        if tree_sitter_typescript is None:
            raise RuntimeError("tree-sitter-typescript is not installed")
        super().__init__(Language(tree_sitter_typescript.language_tsx()))


class JavaScriptParser(_ECMAScriptParser):
    """Parses .js and .jsx."""

    name = "javascript"
    extensions = (".js", ".mjs", ".cjs", ".jsx")
    language_name = "javascript"

    symbol_query_text = JS_SYMBOL_QUERY
    import_query_text = JS_IMPORT_QUERY
    call_query_text = JS_CALL_QUERY

    def __init__(self) -> None:
        if tree_sitter_javascript is None:
            raise RuntimeError("tree-sitter-javascript is not installed")
        super().__init__(Language(tree_sitter_javascript.language()))
