"""Fixture package: the models module."""


class Entity:
    """A trivial entity."""

    def __init__(self, name: str, kind: str = "generic") -> None:
        self.name = name
        self.kind = kind
