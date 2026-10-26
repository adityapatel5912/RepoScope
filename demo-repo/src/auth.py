def login(username: str, password: str) -> dict:
    """Validate credentials and return a session token."""
    # Demo only — real auth would hash passwords and query a DB
    return {"token": "demo-token", "user": username}


def validate_session(token: str) -> bool:
    """Return True if the token is valid."""
    return token == "demo-token"


def logout(token: str) -> dict:
    """Invalidate a session token."""
    return {"ok": True, "token": token}
