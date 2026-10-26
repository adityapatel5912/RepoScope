"""Fixture: second module in a circular import chain."""

from gamma import gamma_value


def beta_value() -> int:
    """Depends on gamma, closing the alpha -> beta -> gamma -> alpha loop."""
    return gamma_value() + 1
