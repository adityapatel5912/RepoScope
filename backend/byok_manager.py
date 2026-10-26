"""
byok_manager.py
Bring Your Own Key — stores a user's GitHub PAT in memory for
the duration of the session. Never persisted to disk.
"""
from typing import Dict

_user_tokens: Dict[str, str] = {}


def set_user_token(session_id: str, token: str) -> None:
    """Store the user's GitHub PAT keyed by session ID."""
    _user_tokens[session_id] = token


def get_user_token(session_id: str) -> str | None:
    """Retrieve the stored token for a session, or None."""
    return _user_tokens.get(session_id)


def clear_user_token(session_id: str) -> None:
    """Remove a stored token (e.g. on logout)."""
    _user_tokens.pop(session_id, None)
