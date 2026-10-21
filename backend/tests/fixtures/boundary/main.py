"""
A fixture repository with a DECLARED architecture boundary.

The `.reposcope.yml` in the root declares two layers — `domain` and
`infra` — and one rule: the domain may not depend on the infra.

Two halves, deliberately:

    main.py               imports the domain  -> CLEAN
    domain/orders.py      imports the infra   -> VIOLATION

The PR bot must flag the second and name both files and the rule.

This is the difference between RepoScope and an AI code reviewer: an AI
reviewer asks "is this code correct?". This asks "does this change
respect the architecture the team declared?".
"""
from domain.orders import order_total


def checkout(items: list[dict]) -> float:
    """The entry point. It depends on the domain, which is allowed."""
    return order_total(items)
