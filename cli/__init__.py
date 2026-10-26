"""
cli/
The `reposcope` command-line interface.

Milestone 2.2 (Sprint 3).

    reposcope run .      serve the app for a local repository
    reposcope index .    write the index without starting a server
    reposcope mcp .      serve the graph over the Model Context Protocol
"""
from __future__ import annotations

__all__ = ["app"]


def __getattr__(name: str):
    # Lazy so that `import cli` does not require Typer — the package is
    # imported by the packaging metadata, and by tests that only want
    # the helper functions.
    if name == "app":
        from cli.main import app

        return app
    raise AttributeError(name)
