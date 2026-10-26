"""Fixture: third module in a circular import chain."""

from alpha import alpha_value


def gamma_value() -> int:
    """Depends on alpha, closing the cycle."""
    return alpha_value() + 1
