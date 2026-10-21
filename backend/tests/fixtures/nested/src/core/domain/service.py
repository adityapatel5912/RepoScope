"""Fixture package: the domain layer.

Uses a package-relative import (`from ..models import Entity`) to exercise
relative resolution in graph_builder.
"""

from ..models import Entity


def describe(entity: Entity) -> str:
    """Return a human-readable description of an entity."""
    return f"{entity.name} ({entity.kind})"
