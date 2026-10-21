"""Fixture: first module in a circular import chain."""

from beta import beta_value


def alpha_value() -> int:
    """Depends on beta, which depends on gamma, which depends on alpha."""
    return beta_value() + 1
