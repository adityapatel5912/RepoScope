"""
parsers/rust.py
Tree-sitter parser for Rust.

Milestone 1.1.

Node types confirmed against tree-sitter-rust 0.24:

    function_item      name: identifier
    struct_item       name: type_identifier
    enum_item         name: type_identifier
    trait_item        name: type_identifier
    impl_item         (contains function_item)
    use_declaration   -> scoped_identifier
    call_expression   function: identifier | scoped_identifier | field_expression
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
    import tree_sitter_rust
except ImportError:  # pragma: no cover - the grammar is a hard dependency
    tree_sitter_rust = None


LANGUAGE_NAME = "rust"

SYMBOL_QUERY = """
(function_item
  name: (identifier) @sym.name) @sym.function

(struct_item
  name: (type_identifier) @sym.name) @sym.class

(enum_item
  name: (type_identifier) @sym.name) @sym.class

(trait_item
  name: (type_identifier) @sym.name) @sym.class
"""

IMPORT_QUERY = """
(use_declaration
  argument: (scoped_identifier) @import.path)

(use_declaration
  argument: (identifier) @import.path)

(use_declaration
  argument: (use_as_clause
    path: (scoped_identifier) @import.path))
"""

CALL_QUERY = """
(call_expression
  function: (identifier) @call.name)

(call_expression
  function: (scoped_identifier) @call.scoped)

(call_expression
  function: (field_expression) @call.field)
"""


class RustParser:
    """Parses Rust source into symbols, imports, and call sites."""

    name = LANGUAGE_NAME
    extensions = (".rs",)

    def __init__(self) -> None:
        if tree_sitter_rust is None:
            raise RuntimeError("tree-sitter-rust is not installed")
        self._language = Language(tree_sitter_rust.language())
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
            is_class = def_node.type != "function_item"
            body = first_child_of_type(def_node, ("block", "declaration_list"))
            result.symbols.append(
                Symbol(
                    name=name_node.text.decode("utf-8", "replace"),
                    kind="class" if is_class else "function",
                    line=def_node.start_point[0] + 1,
                    end_line=def_node.end_point[0] + 1,
                    signature=text_of(def_node, source, 160),
                    exported=self._is_public(def_node),
                    parent=self._enclosing_impl(def_node),
                    complexity=compute_complexity(body or def_node, source, LANGUAGE_NAME),
                )
            )

    def _is_public(self, node) -> bool:
        """True when the item carries a `pub` visibility modifier."""
        for child in node.children:
            if child.type == "visibility_modifier":
                return True
        return False

    def _enclosing_impl(self, node) -> str | None:
        """The type an `impl` block provides methods for."""
        current = node.parent
        while current is not None:
            if current.type == "impl_item":
                name = first_child_of_type(current, ("type_identifier",))
                if name is not None:
                    return name.text.decode("utf-8", "replace")
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
            module = path_node.text.decode("utf-8", "replace")
            result.imports.append(
                Import(
                    module=module,
                    line=statement.start_point[0] + 1,
                    is_relative=module.startswith(("crate::", "super::", "self::")),
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

        # `Type::method()` — the scoped identifier's last segment is the
        # name being called.
        for scoped_node in captures.get("call.scoped", []):
            call_node = scoped_node.parent
            if call_node is None:
                continue
            path = scoped_node.text.decode("utf-8", "replace")
            enclosing, enclosing_line = self._enclosing_symbol(call_node)
            result.calls.append(
                CallSite(
                    callee=path.rsplit("::", 1)[-1],
                    line=call_node.start_point[0] + 1,
                    receiver=path.rsplit("::", 1)[0] if "::" in path else None,
                    enclosing=enclosing,
                    enclosing_line=enclosing_line,
                )
            )

        # `value.field()` — `field_expression` has no value:/field: fields
        # in this grammar, so the receiver and the name come from children.
        for field_node in captures.get("call.field", []):
            call_node = field_node.parent
            if call_node is None:
                continue
            receiver = None
            callee = None
            for child in field_node.children:
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
            if current.type == "function_item":
                name = first_child_of_type(current, ("identifier",))
                if name is not None:
                    return (
                        name.text.decode("utf-8", "replace"),
                        current.start_point[0] + 1,
                    )
            current = current.parent
        return None, 0
