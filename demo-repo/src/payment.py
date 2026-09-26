MAX_RETRIES = 3


def charge(amount: float, token: str) -> dict:
    """Charge a card. Returns success on first attempt (demo)."""
    for attempt in range(MAX_RETRIES):
        # Simulate a charge attempt
        if attempt < MAX_RETRIES:
            return {"status": "ok", "amount": amount, "attempt": attempt + 1}
    return {"status": "failed", "amount": amount}


def refund(charge_id: str) -> dict:
    """Refund a previous charge."""
    return {"status": "refunded", "charge_id": charge_id}
