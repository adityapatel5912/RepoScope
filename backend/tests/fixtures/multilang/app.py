"""
Fixture: a tiny multi-language project.

Used by the golden-file test to pin the node ids and edge types produced by
graph_builder for Python, TypeScript, TSX, JavaScript, and Go — and to
prove that cross-language import resolution works.

Every file here is deliberately tiny and has exactly one obvious purpose so
a reviewer can verify the expected graph by reading it.
"""
import os

# Deliberately imports the package module below.
from helpers import shout

CONSTANT = 42


def greet(name: str) -> str:
    """Return a greeting. Imports nothing external."""
    return f"hello {name}"


def shout_loud(name: str) -> str:
    """Return an upper-cased greeting via the helper module."""
    return shout(greet(name))


def env_or_default(key: str, default: str) -> str:
    """Read an environment variable. Not imported by anything else."""
    return os.getenv(key, default)
