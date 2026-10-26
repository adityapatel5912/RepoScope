"""Probe: dump the tree-sitter AST node types for each supported language.

Not part of the committed suite — a development aid for authoring the
queries in backend/parsers/. Run it after upgrading a grammar:

    python scripts/probe_asts.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from tree_sitter import Language, Parser  # noqa: E402

import tree_sitter_go as tsgo  # noqa: E402
import tree_sitter_javascript as tsjs  # noqa: E402
import tree_sitter_python as tspy  # noqa: E402
import tree_sitter_rust as tsrs  # noqa: E402
import tree_sitter_typescript as tsts  # noqa: E402

SAMPLES = {
    "python": (
        tspy.language(),
        b'''
import os
from pathlib import Path as P
from .rel import thing

class Widget(Base):
    """doc"""
    def method(self, a: int = 1) -> str:
        return helper(a)

def helper(x):
    return x
''',
    ),
    "typescript": (
        tsts.language_typescript(),
        b'''
import { a } from "./mod";
import type { T } from "./types";
export * from "./re";

export interface Shape { n: number }
export type Alias = string;
export const fn = (x: number): string => `${x}`;
export function decl(y: string) { return y; }
export class Cls extends Base {
  m(a: number) { return a; }
  static s() {}
}
''',
    ),
    "tsx": (
        tsts.language_tsx(),
        b'''
import { a } from "./mod";
export function C() { return <div/>; }
''',
    ),
    "javascript": (
        tsjs.language(),
        b'''
import { a } from "./mod";
export const fn = (x) => x;
export function decl(y) { return y; }
export class Cls { m(a) { return a; } }
''',
    ),
    "go": (
        tsgo.language(),
        b'''
package main

import (
    "fmt"
    "example.com/pkg"
)

type Greeter struct { Prefix string }

func Greet(name string) string { return fmt.Sprintf("hi %s", name) }

func (g Greeter) Greet(name string) string { return g.Prefix + name }
''',
    ),
    "rust": (
        tsrs.language(),
        b'''
use std::fmt;
use crate::thing::Widget;

pub struct Widget { pub name: String }

pub enum Kind { A, B }

impl Widget {
    pub fn new(name: String) -> Self { Self { name } }
}

pub fn helper(x: i32) -> i32 { x }

pub trait Doer { fn do_it(&self); }
''',
    ),
}


def dump(node, source, depth=0, out=None):
    if out is None:
        out = []
    if depth > 6:
        return out
    text = source[node.start_byte:node.end_byte][:40].decode("utf-8", "replace")
    out.append(f"{'  ' * depth}{node.type}  {text!r}")
    for child in node.children:
        dump(child, source, depth + 1, out)
    return out


for name, (lang, source) in SAMPLES.items():
    parser = Parser(Language(lang))
    tree = parser.parse(source)
    print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
    for line in dump(tree.root_node, source):
        print(line)
