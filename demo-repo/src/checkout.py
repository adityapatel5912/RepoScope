from auth import validate_session
from payment import charge


def create_order(cart: list, token: str) -> dict:
    """
    Create an order from a cart after validating the session.

    Args:
        cart:  list of {"name": str, "price": float}
        token: session token from auth.login()

    Returns:
        {"order_id": str, "total": float, "payment": dict}
    """
    if not validate_session(token):
        raise ValueError("Invalid session — please log in again")

    total = sum(item["price"] for item in cart)
    result = charge(total, token)

    return {
        "order_id": "demo-001",
        "total": total,
        "payment": result,
    }
