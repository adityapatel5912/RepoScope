"""
Business logic.

This module is in the `domain` layer, and the repository declares that
the domain layer may not depend on the `infra` layer. The import below
is therefore a boundary violation — and it is EXACTLY the kind of
coupling a PR bot should notice, because the database is not the
domain's business.
"""
from infra.store import save_record


def record_order(order_id: str, total: float) -> str:
    """Record an order."""
    save_record({"id": order_id, "total": total})
    return order_id
