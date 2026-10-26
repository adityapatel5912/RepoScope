"""
test_parsers.py
Tests for the polyglot parser package (Milestone 1.1).

These cover the parts that are easy to get subtly wrong and that the
golden-file test would only catch indirectly:

  * every grammar loads and answers with the right root node type
  * symbols carry line numbers, kinds, and complexity
  * imports are classified correctly (absolute, relative, re-export)
  * calls carry the enclosing symbol AND its line, so that two symbols
    with the same name are not confused
  * a malformed file never raises — it produces a partial result and a
    warning, because the parser walks untrusted repositories
"""
import pytest

from parsers.base import Symbol
from parsers.go import GoParser
from parsers.python import PythonParser
from parsers.registry import get_parser, supported_extensions
from parsers.rust import RustParser
from parsers.typescript import (
    JavaScriptParser,
    TsxParser,
    TypeScriptParser,
)


# ── The registry ────────────────────────────────────────────────────────────

def test_registry_knows_every_supported_extension():
    extensions = supported_extensions()
    for expected in (".py", ".ts", ".tsx", ".js", ".go", ".rs"):
        assert expected in extensions, f"{expected} is not registered"


@pytest.mark.parametrize(
    "suffix,expected",
    [
        (".py", "PythonParser"),
        (".ts", "TypeScriptParser"),
        (".tsx", "TsxParser"),
        (".js", "JavaScriptParser"),
        (".go", "GoParser"),
        (".rs", "RustParser"),
        # The suffix may arrive with or without a dot.
        ("py", "PythonParser"),
        ("TS", "TypeScriptParser"),
    ],
)
def test_registry_resolves_extensions(suffix, expected):
    parser = get_parser(suffix)
    assert parser is not None, f"no parser for {suffix!r}"
    assert type(parser).__name__ == expected


def test_registry_returns_none_for_unknown_extensions():
    assert get_parser(".toml") is None
    assert get_parser(".png") is None


# ── Python ──────────────────────────────────────────────────────────────────

PYTHON_SOURCE = b'''
import os
from pathlib import Path as P
from .relative import thing
from ..parent import other


class Widget:
    """A widget."""

    def method(self, value: int) -> str:
        if value > 0:
            return helper(value)
        return helper(0)


def helper(value: int) -> int:
    for index in range(value):
        value += index
    return value
'''


def test_python_extracts_symbols_with_lines():
    result = PythonParser().extract(PYTHON_SOURCE, "sample.py")
    names = {symbol.name for symbol in result.symbols}
    assert {"Widget", "method", "helper"} <= names

    helper = next(s for s in result.symbols if s.name == "helper")
    assert helper.kind == "function"
    assert helper.line > 0
    assert helper.complexity >= 2, "a loop must add a branch"


def test_python_reports_the_enclosing_class():
    result = PythonParser().extract(PYTHON_SOURCE, "sample.py")
    method = next(s for s in result.symbols if s.name == "method")
    assert method.parent == "Widget"
    assert method.kind == "function"


def test_python_classifies_imports():
    result = PythonParser().extract(PYTHON_SOURCE, "sample.py")
    modules = {imp.module for imp in result.imports}

    assert "os" in modules
    assert "pathlib" in modules
    assert "relative" in modules
    assert "parent" in modules

    relative = next(imp for imp in result.imports if imp.module == "relative")
    assert relative.is_relative is True
    assert relative.level == 1
    assert "thing" in relative.names

    parent = next(imp for imp in result.imports if imp.module == "parent")
    assert parent.is_relative is True
    assert parent.level == 2


def test_python_captures_calls_with_their_enclosing_symbol():
    result = PythonParser().extract(PYTHON_SOURCE, "sample.py")
    calls = {(c.callee, c.enclosing) for c in result.calls}
    assert ("helper", "method") in calls


def test_python_call_enclosing_line_disambiguates_same_named_symbols():
    """
    Two functions with the same name must not be confused.

    The enclosing LINE is what tells them apart. Without it, every call
    inside either of them would be attributed to the first one found.
    """
    source = b'''
def build():
    return inner()

def build():
    return inner()

def inner():
    return 1
'''
    result = PythonParser().extract(source, "dupes.py")
    builds = [s for s in result.symbols if s.name == "build"]
    assert len(builds) == 2, "both build functions must be found"
    assert builds[0].line != builds[1].line

    lines = {c.enclosing_line for c in result.calls if c.callee == "inner"}
    assert len(lines) == 2, "each call must be attributed to its own build()"


def test_python_handles_a_malformed_file_without_raising():
    source = b"def broken(:\n    this is not python\n"
    result = PythonParser().extract(source, "broken.py")
    assert result.warnings, "a parse error must produce a warning"
    assert isinstance(result.symbols, list)


# ── TypeScript / JavaScript ─────────────────────────────────────────────────

TS_SOURCE = b'''
import { helper } from "./helper";
import type { Thing } from "./types";
export * from "./reexport";

export interface Shape { name: string }

export function build(input: string): string {
  return helper(input);
}

export const arrow = (value: number) => value + 1;

export class Widget {
  render(): string {
    return helper("x");
  }
}
'''


def test_typescript_extracts_every_symbol_kind():
    result = TypeScriptParser().extract(TS_SOURCE, "sample.ts")
    by_name = {symbol.name: symbol for symbol in result.symbols}

    assert "build" in by_name
    assert by_name["build"].kind == "function"
    assert "Widget" in by_name
    assert by_name["Widget"].kind == "class"
    assert "Shape" in by_name
    assert by_name["Shape"].kind == "class"
    assert "arrow" in by_name
    assert by_name["arrow"].kind == "function"


def test_typescript_records_line_numbers():
    result = TypeScriptParser().extract(TS_SOURCE, "sample.ts")
    for symbol in result.symbols:
        assert symbol.line > 0, f"{symbol.name} has no line number"


def test_typescript_detects_reexports():
    result = TypeScriptParser().extract(TS_SOURCE, "sample.ts")
    reexports = [imp for imp in result.imports if imp.re_export]
    assert any(imp.module == "./reexport" for imp in reexports)


def test_typescript_captures_imported_names():
    result = TypeScriptParser().extract(TS_SOURCE, "sample.ts")
    helper_import = next(
        imp for imp in result.imports if imp.module == "./helper"
    )
    assert "helper" in helper_import.names


def test_typescript_calls_carry_the_enclosing_symbol():
    result = TypeScriptParser().extract(TS_SOURCE, "sample.ts")
    calls = {(c.callee, c.enclosing) for c in result.calls}
    assert ("helper", "build") in calls
    assert ("helper", "render") in calls


def test_tsx_parses_jsx():
    source = b'''
export function Card() {
  return <div className="x">hello</div>;
}
'''
    result = TsxParser().extract(source, "Card.tsx")
    assert any(symbol.name == "Card" for symbol in result.symbols)
    assert not result.warnings


def test_javascript_parser_works_without_types():
    source = b'''
export const slugify = (input) => input.toLowerCase();
export function shout(text) { return text.toUpperCase(); }
'''
    result = JavaScriptParser().extract(source, "sample.js")
    names = {symbol.name for symbol in result.symbols}
    assert {"slugify", "shout"} <= names


# ── Go ──────────────────────────────────────────────────────────────────────

GO_SOURCE = b'''
package main

import (
    "fmt"
    "example.com/pkg"
)

type Greeter struct {
    Prefix string
}

func Greet(name string) string {
    return fmt.Sprintf("hi %s", name)
}

func (g Greeter) Greet(name string) string {
    return g.Prefix + name
}
'''


def test_go_extracts_functions_methods_and_types():
    result = GoParser().extract(GO_SOURCE, "sample.go")
    names = {symbol.name for symbol in result.symbols}
    assert "Greet" in names
    assert "Greeter" in names
    assert any(s.kind == "class" and s.name == "Greeter" for s in result.symbols)


def test_go_method_records_its_receiver_type():
    result = GoParser().extract(GO_SOURCE, "sample.go")
    methods = [s for s in result.symbols if s.name == "Greet"]
    assert len(methods) == 2, "a function and a method are both named Greet"
    assert any(m.parent == "Greeter" for m in methods)


def test_go_imports_are_recorded():
    result = GoParser().extract(GO_SOURCE, "sample.go")
    modules = {imp.module for imp in result.imports}
    assert "fmt" in modules
    assert "example.com/pkg" in modules


# ── Rust ────────────────────────────────────────────────────────────────────

RUST_SOURCE = b'''
use std::fmt;
use crate::thing::Widget;

pub struct Widget {
    pub name: String,
}

pub enum Kind {
    A,
    B,
}

impl Widget {
    pub fn new(name: String) -> Self {
        Self { name }
    }
}

pub fn helper(value: i32) -> i32 {
    value
}
'''


def test_rust_extracts_functions_and_types():
    result = RustParser().extract(RUST_SOURCE, "sample.rs")
    by_name = {symbol.name: symbol for symbol in result.symbols}

    assert by_name["helper"].kind == "function"
    assert by_name["Widget"].kind == "class"
    assert by_name["Kind"].kind == "class"
    assert by_name["new"].parent == "Widget"


def test_rust_records_public_visibility():
    result = RustParser().extract(RUST_SOURCE, "sample.rs")
    helper = next(s for s in result.symbols if s.name == "helper")
    assert helper.exported is True


def test_rust_imports_are_recorded_with_relative_flag():
    result = RustParser().extract(RUST_SOURCE, "sample.rs")
    modules = {imp.module: imp for imp in result.imports}
    assert "std::fmt" in modules
    assert modules["crate::thing::Widget"].is_relative is True


# ── Complexity ──────────────────────────────────────────────────────────────

def test_complexity_grows_with_branches():
    simple = PythonParser().extract(b"def f(x):\n    return x\n", "a.py")
    complex_ = PythonParser().extract(
        b"def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n", "b.py"
    )
    simple_symbol = next(s for s in simple.symbols if s.name == "f")
    complex_symbol = next(s for s in complex_.symbols if s.name == "f")
    assert complex_symbol.complexity > simple_symbol.complexity


def test_symbol_dataclass_defaults_are_safe():
    symbol = Symbol(name="x", kind="function", line=1)
    assert symbol.complexity == 1
    assert symbol.exported is False
    assert symbol.parent is None
