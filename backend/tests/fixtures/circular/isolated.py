"""Fixture: an isolated module that participates in no cycle."""

from alpha import alpha_value


def isolated() -> int:
    """Reaches into the cycle but nothing reaches back, so it is acyclic."""
    return alpha_value() + 100
