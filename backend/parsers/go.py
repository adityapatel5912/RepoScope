"""
parsers/go.py
Tree-sitter parser for Go.

Milestone 1.1.

Node types confirmed against tree-sitter-go 0.25:

    function_declaration   name: identifier
    method_declaration     name: field_identifier
    type_declaration       -> type_spec -> type_identifier
    import_declaration     -> import_spec -> interpreted_string_literal
    call_expression        function: identifier | selector_expression
"""
from __future__ import annotations

from tree_sitter import Language, Parser, Query, QueryCursor

from parsers.base import (
    CallSite,
    Import,
    ParseResult,
    Symbol,
    compute_complexity,
    find_descendant_of_type,
    first_child_of_type,
    text_of,
)

try:
    import tree_sitter_go
except ImportError:  # pragma: no cover - the grammar is a hard dependency
    tree_sitter_go = None


LANGUAGE_NAME = "go"

SYMBOL_QUERY = """
(function_declaration
  name: (identifier) @sym.name) @sym.function

(method_declaration
  name: (field_identifier) @sym.name) @sym.function

(type_declaration
  (type_spec
    name: (type_identifier) @sym.name) @sym.class)
"""

IMPORT_QUERY = """
(import_spec
  path: (interpreted_string_literal) @import.path)
"""

CALL_QUERY = """
(call_expression
  function: (identifier) @call.name)

(call_expression
  function: (selector_expression) @call.selector)
"""


class GoParser:
    """Parses Go source into symbols, imports, and call sites."""

    name = LANGUAGE_NAME
    extensions = (".go",)

    def __init__(self) -> None:
        if tree_sitter_go is None:
            raise RuntimeError("tree-sitter-go is not installed")
        self._language = Language(tree_sitter_go.language())
        self._parser = Parser(self._language)
        self._symbol_query = Query(self._language, SYMBOL_QUERY)
        self._import_query = Query(self._language, IMPORT_QUERY)
        self._call_query = Query(self._language, CALL_QUERY)

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
        defs = captures.get("sym.function", []) + captures.get("sym.class", [])

        name_by_def: dict[tuple[int, int], object] = {}
        for name_node in names:
            parent = name_node.parent
            if parent is not None:
                name_by_def[(parent.start_byte, parent.end_byte)] = name_node

        for def_node in defs:
            name_node = name_by_def.get((def_node.start_byte, def_node.end_byte))
            if name_node is None:
                continue
            # The captured node for a type is the `type_spec` inside the
            # `type_declaration`, so both spellings mean "a type".
            is_class = def_node.type in ("type_declaration", "type_spec")
            body = first_child_of_type(def_node, ("block",))
            result.symbols.append(
                Symbol(
                    name=name_node.text.decode("utf-8", "replace"),
                    kind="class" if is_class else "function",
                    line=def_node.start_point[0] + 1,
                    end_line=def_node.end_point[0] + 1,
                    signature=text_of(def_node, source, 160),
                    exported=name_node.text.decode("utf-8", "replace")[:1].isupper(),
                    parent=self._enclosing_type(def_node),
                    complexity=compute_complexity(body or def_node, source, LANGUAGE_NAME),
                )
            )

    def _enclosing_type(self, node) -> str | None:
        """The receiver type of a Go method, when it has one."""
        # The node itself may be the method — check it before walking up.
        current = node
        while current is not None:
            if current.type == "method_declaration":
                receiver = first_child_of_type(current, ("parameter_list",))
                if receiver is not None:
                    # The receiver type lives inside
                    # parameter_list > parameter_declaration > type_identifier.
                    type_id = find_descendant_of_type(receiver, ("type_identifier",))
                    if type_id is not None:
                        return type_id.text.decode("utf-8", "replace")
                return None
            current = current.parent
        return None

    # ── Imports ────────────────────────────────────────────────────────────

    def _extract_imports(self, root, source: bytes, result: ParseResult) -> None:
        captures = QueryCursor(self._import_query).captures(root)
        for path_node in captures.get("import.path", []):
            statement = path_node.parent
            if statement is None:
                continue
            raw = path_node.text.decode("utf-8", "replace")
            module = raw.strip('"')
            result.imports.append(
                Import(
                    module=module,
                    line=statement.start_point[0] + 1,
                    # A Go import path with a dot in the first segment is a
                    # third-party module; a bare path is standard library.
                    is_relative=False,
                )
            )

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

        # `pkg.Func()` — `selector_expression` has no operand:/field:
        # fields in this grammar, so the receiver and the name are taken
        # from its children.
        for selector_node in captures.get("call.selector", []):
            call_node = selector_node.parent
            if call_node is None:
                continue
            receiver = None
            callee = None
            for child in selector_node.children:
                if child.type == "identifier":
                    receiver = child.text.decode("utf-8", "replace")
                elif child.type == "field_identifier":
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
                "function_declaration", "method_declaration", "func_literal",
            ):
                name = first_child_of_type(current, ("identifier", "field_identifier"))
                if name is not None:
                    return (
                        name.text.decode("utf-8", "replace"),
                        current.start_point[0] + 1,
                    )
            current = current.parent
        return None, 0
