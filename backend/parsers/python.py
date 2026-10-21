"""
parsers/python.py
Tree-sitter parser for Python.

Milestone 1.1. The stock `ast` module already parses Python well, but
Tree-sitter gives one uniform pipeline for every language, produces line
numbers for every symbol, and handles syntax errors without raising —
which matters because the parser walks untrusted repositories.

Node types confirmed against tree-sitter-python 0.25:
    function_definition   name: identifier
    class_definition      name: identifier
    import_statement      module: dotted_name
    import_from_statement module: dotted_name | relative_import
    call                  function: identifier | attribute
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
    import tree_sitter_python
except ImportError:  # pragma: no cover - the grammar is a hard dependency
    tree_sitter_python = None


LANGUAGE_NAME = "python"

#: Captures the definition name and the definition node itself.
SYMBOL_QUERY = """
(function_definition
  name: (identifier) @sym.name) @sym.function

(class_definition
  name: (identifier) @sym.name) @sym.class
"""

#: `import a.b.c` — the module is a dotted_name. Only used for the plain
#: `import x` form; `import_from_statement` is walked in code because this
#: grammar has no `module:` field on it.
IMPORT_QUERY = """
(import_statement
  name: (dotted_name) @import.module)
"""

#: A call — `f()` or `obj.f()`.
#:
#: NOTE: the `attribute` node has no `object:`/`attribute:` fields in this
#: grammar, so the receiver and the method name are split in code from the
#: node's children.
CALL_QUERY = """
(call
  function: (identifier) @call.name)

(call
  function: (attribute) @call.attr)
"""


class PythonParser:
    """Parses Python source into symbols, imports, and call sites."""

    name = LANGUAGE_NAME
    extensions = (".py", ".pyi")

    def __init__(self) -> None:
        if tree_sitter_python is None:
            raise RuntimeError("tree-sitter-python is not installed")
        self._language = Language(tree_sitter_python.language())
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

        # Map each definition node to its name node by position.
        name_by_def: dict[tuple[int, int], object] = {}
        for name_node in names:
            parent = name_node.parent
            if parent is not None:
                name_by_def[(parent.start_byte, parent.end_byte)] = name_node

        for def_node in defs:
            name_node = name_by_def.get((def_node.start_byte, def_node.end_byte))
            if name_node is None:
                continue
            kind = "function" if def_node.type == "function_definition" else "class"
            body = first_child_of_type(def_node, ("block",))
            symbol = Symbol(
                name=name_node.text.decode("utf-8", "replace"),
                kind=kind,
                line=def_node.start_point[0] + 1,
                end_line=def_node.end_point[0] + 1,
                signature=text_of(def_node, source, 160),
                exported=not name_node.text.decode("utf-8", "replace").startswith("_"),
                parent=self._enclosing_class(def_node),
                complexity=compute_complexity(body or def_node, source, LANGUAGE_NAME),
            )
            result.symbols.append(symbol)

    def _enclosing_class(self, node) -> str | None:
        """The name of the class a definition sits inside, if any."""
        current = node.parent
        while current is not None:
            if current.type == "class_definition":
                name = first_child_of_type(current, ("identifier",))
                if name is not None:
                    return name.text.decode("utf-8", "replace")
                return None
            current = current.parent
        return None

    # ── Imports ────────────────────────────────────────────────────────────

    def _extract_imports(self, root, source: bytes, result: ParseResult) -> None:
        """
        Extract every import.

        This walks the import statements directly rather than using a
        query, because this grammar has no `module:` field on
        `import_from_statement` — the module is simply the child before the
        `import` keyword, and the imported names are the dotted_names
        after it. Walking the children is both simpler and correct for
        relative imports, which a query cannot separate from the module.
        """
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        result.imports.append(
                            Import(
                                module=child.text.decode("utf-8", "replace"),
                                line=node.start_point[0] + 1,
                            )
                        )
                    elif child.type == "aliased_import":
                        inner = first_child_of_type(child, ("dotted_name",))
                        if inner is not None:
                            result.imports.append(
                                Import(
                                    module=inner.text.decode("utf-8", "replace"),
                                    line=node.start_point[0] + 1,
                                    names=(child.text.decode("utf-8", "replace"),),
                                )
                            )
            elif node.type == "import_from_statement":
                keyword_index = None
                for index, child in enumerate(node.children):
                    if child.type == "import":
                        keyword_index = index
                        break

                module_text = ""
                level = 0
                is_relative = False
                names: list[str] = []

                for index, child in enumerate(node.children):
                    after_keyword = keyword_index is not None and index > keyword_index
                    if child.type == "dotted_name":
                        if after_keyword:
                            names.append(child.text.decode("utf-8", "replace"))
                        elif not module_text:
                            module_text = child.text.decode("utf-8", "replace")
                    elif child.type == "aliased_import":
                        inner = first_child_of_type(child, ("dotted_name",))
                        label = inner.text.decode("utf-8", "replace") if inner else ""
                        if after_keyword:
                            names.append(label)
                        elif not module_text:
                            module_text = label
                    elif child.type == "relative_import":
                        raw = child.text.decode("utf-8", "replace")
                        level = len(raw) - len(raw.lstrip("."))
                        module_text = raw.lstrip(".")
                        is_relative = True

                if module_text or names:
                    result.imports.append(
                        Import(
                            module=module_text,
                            line=node.start_point[0] + 1,
                            names=tuple(names),
                            is_relative=is_relative,
                            level=level,
                        )
                    )

            stack.extend(node.children)

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

        # `obj.method()` — the attribute node's children are the receiver
        # first and the method name last.
        for attribute_node in captures.get("call.attr", []):
            call_node = attribute_node.parent
            if call_node is None:
                continue
            parts = [
                child.text.decode("utf-8", "replace")
                for child in attribute_node.children
                if child.type == "identifier"
            ]
            if not parts:
                continue
            enclosing, enclosing_line = self._enclosing_symbol(call_node)
            result.calls.append(
                CallSite(
                    callee=parts[-1],
                    line=call_node.start_point[0] + 1,
                    receiver=parts[0] if len(parts) > 1 else None,
                    enclosing=enclosing,
                    enclosing_line=enclosing_line,
                )
            )

    def _enclosing_symbol(self, node) -> tuple[str | None, int]:
        """The name and line of the function or class a call sits inside."""
        current = node.parent
        while current is not None:
            if current.type in ("function_definition", "class_definition"):
                name = first_child_of_type(current, ("identifier",))
                if name is not None:
                    return (
                        name.text.decode("utf-8", "replace"),
                        current.start_point[0] + 1,
                    )
            current = current.parent
        return None, 0
