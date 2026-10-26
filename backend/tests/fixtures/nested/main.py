"""Fixture: application entry point.

Imports across package boundaries using absolute dotted paths.
"""

from src.core.domain.service import describe
from src.core.models import Entity


def main() -> str:
    """Return a description of the default entity."""
    return describe(Entity("demo"))


if __name__ == "__main__":
    print(main())
