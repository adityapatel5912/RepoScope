"""
Persistence.

The `infra` layer. The domain layer is not allowed to import this — and
`domain/orders.py` does, which is the violation the boundary fixture
exists to demonstrate.
"""
from pathlib import Path

RECORDS: list[dict] = []


def save_record(record: dict) -> None:
    """Save a record."""
    RECORDS.append(record)


def load_records() -> list[dict]:
    """Every saved record."""
    return list(RECORDS)
