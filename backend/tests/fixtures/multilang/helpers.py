"""
Fixture helper module.

Imported by app.py via `from helpers import shout` — a bare-stem import,
which exercises the fallback resolution path in graph_builder.
"""


def shout(text: str) -> str:
    """Return the text upper-cased."""
    return text.upper()
