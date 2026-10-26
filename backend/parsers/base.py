"""
parsers/base.py
The shared contract for RepoScope's polyglot parsers.

Milestone 1.1. Every language parser turns source bytes into the same
`ParseResult`, so `graph_builder` never needs to know which language it is
looking at.

The design keeps Correction C10 intact: a parser produces SYMBOLS and
IMPORTS, and `graph_builder` decides the node ids, the node types, and the
edge shapes. The parser must never mint a node id itself — the id scheme
is load-bearing and lives in one place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Symbol:
    """A named definition: a function, a method, a class, a type."""

    name: str
    kind: str                      # function | class
    line: int                      # 1-based
    end_line: int = 0
    signature: str = ""            # a one-line, human-readable signature
    exported: bool = False
    parent: str | None = None      # enclosing class/type name, if any
    complexity: int = 1            # cyclomatic complexity


@dataclass
class Import:
    """A module import, resolved later against the module index."""

    module: str                    # the module specifier, verbatim
    line: int = 0
    names: tuple[str, ...] = ()    # imported symbol names, when known
    is_relative: bool = False
    level: int = 0                 # for Python: 1 = ".", 2 = ".."
    re_export: bool = False        # `export … from` / `from … import *`


@dataclass
class CallSite:
    """A call expression, attributed to the symbol that contains it."""

    callee: str                    # the name called
    line: int = 0
    receiver: str | None = None    # `obj` in `obj.method()`
    enclosing: str | None = None   # the symbol containing the call
    enclosing_line: int = 0        # the line of that symbol

    # NOTE: `enclosing` alone is not enough to identify the enclosing
    # symbol. A file may define several symbols with the same name — four
    # `__init__` methods is the common case — and attributing every call
    # inside them to the first one is wrong. The line disambiguates.


@dataclass
class ParseResult:
    """Everything a parser extracted from one file."""

    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    #: Non-fatal problems (an unsupported construct, a truncated file).
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class LanguageParser(Protocol):
    """The interface every language parser implements."""

    #: File extensions this parser handles, e.g. (".ts", ".tsx").
    extensions: tuple[str, ...]

    #: A human-readable name, used in warnings and diagnostics.
    name: str

    def extract(self, source: bytes, rel_path: str) -> ParseResult:
        """Parse one file's contents."""
        ...


# ── Shared helpers ──────────────────────────────────────────────────────────

#: Node types that each add one branch to the cyclomatic complexity.
COMPLEXITY_NODES: dict[str, frozenset[str]] = {
    "python": frozenset({
        "if_statement", "elif_clause", "for_statement", "while_statement",
        "except_clause", "with_statement", "assert_statement",
        "conditional_expression", "boolean_operator", "case_clause",
    }),
    "typescript": frozenset({
        "if_statement", "else_clause", "for_statement", "for_in_statement",
        "while_statement", "do_statement", "catch_clause", "switch_case",
        "ternary_expression", "binary_expression",
    }),
    "javascript": frozenset({
        "if_statement", "else_clause", "for_statement", "for_in_statement",
        "while_statement", "do_statement", "catch_clause", "switch_case",
        "ternary_expression", "binary_expression",
    }),
    "go": frozenset({
        "if_statement", "for_statement", "expression_case", "type_switch_statement",
        "communication_case", "select_statement",
    }),
    "rust": frozenset({
        "if_expression", "while_expression", "loop_expression",
        "for_expression", "match_arm", "match_expression",
    }),
}

#: Binary operators that genuinely branch. Most binary expressions are
#: arithmetic, so counting every one of them would inflate complexity.
_COMPLEXITY_BINARY_OPERATORS = frozenset({
    "&&", "||", "and", "or", "?",
})


def compute_complexity(node, source: bytes, language: str, base: int = 1) -> int:
    """
    Cyclomatic complexity of a definition body.

    Counts decision points: branches, loops, exception handlers, boolean
    operators and ternaries. It is an approximation — it does not model
    short-circuit depth — but it is consistent and monotonic, which is what
    the node-sizing heuristic needs.
    """
    interesting = COMPLEXITY_NODES.get(language, frozenset())
    if not interesting:
        return base

    score = base
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in interesting:
            score += 1
        elif current.type == "binary_expression":
            operator = current.child_by_field_name("operator")
            if operator is not None:
                text = source[operator.start_byte:operator.end_byte].decode(
                    "utf-8", "replace"
                )
                if text in _COMPLEXITY_BINARY_OPERATORS:
                    score += 1
        stack.extend(current.children)
    return score


def first_child_of_type(node, types: tuple[str, ...]):
    """Return the first child whose type is in `types`, or None."""
    for child in node.children:
        if child.type in types:
            return child
    return None


def find_descendant_of_type(node, types: tuple[str, ...], limit: int = 200):
    """
    Return the first DESCENDANT whose type is in `types`, or None.

    Some grammars nest the interesting node deeper than one level — a Go
    method's receiver type sits inside `parameter_list > parameter_declaration >
    type_identifier` — so a direct-child search misses it.
    """
    if node is None:
        return None
    stack = [node]
    seen = 0
    while stack and seen < limit:
        seen += 1
        current = stack.pop(0)
        if current is not node and current.type in types:
            return current
        stack.extend(current.children)
    return None


def text_of(node, source: bytes, limit: int = 200) -> str:
    """The node's source text, truncated and whitespace-collapsed."""
    if node is None:
        return ""
    raw = source[node.start_byte:node.end_byte].decode("utf-8", "replace")
    collapsed = " ".join(raw.split())
    return collapsed[:limit]
