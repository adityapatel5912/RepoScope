"""
parsers/registry.py
Maps a file extension to its parser.

Milestone 1.1. A grammar that fails to load MUST NOT take the app down —
the parser registry degrades to "no parser for this extension" and
`graph_builder` falls back to the previous regex/ast implementation.
"""
from __future__ import annotations

import logging
from typing import Optional

from parsers.base import LanguageParser

log = logging.getLogger("reposcope.parsers")

_PARSER_CLASSES: dict[str, type] = {}
_PARSER_CACHE: dict[str, Optional[LanguageParser]] = {}


def _load_parser_classes() -> dict[str, type]:
    """Instantiate the parser classes, tolerating a missing grammar."""
    global _PARSER_CLASSES
    if _PARSER_CLASSES:
        return _PARSER_CLASSES

    classes: dict[str, type] = {}

    try:
        from parsers.python import PythonParser
        classes["python"] = PythonParser
    except Exception as exc:  # noqa: BLE001 - a missing grammar is not fatal
        log.warning("Python parser unavailable: %s", exc)

    try:
        from parsers.typescript import (
            JavaScriptParser,
            TsxParser,
            TypeScriptParser,
        )
        classes["typescript"] = TypeScriptParser
        classes["tsx"] = TsxParser
        classes["javascript"] = JavaScriptParser
    except Exception as exc:  # noqa: BLE001
        log.warning("ECMAScript parsers unavailable: %s", exc)

    try:
        from parsers.go import GoParser
        classes["go"] = GoParser
    except Exception as exc:  # noqa: BLE001
        log.warning("Go parser unavailable: %s", exc)

    try:
        from parsers.rust import RustParser
        classes["rust"] = RustParser
    except Exception as exc:  # noqa: BLE001
        log.warning("Rust parser unavailable: %s", exc)

    _PARSER_CLASSES = classes
    return classes


def get_parser(suffix: str) -> Optional[LanguageParser]:
    """
    Return the parser for a file extension, or None when there is none.

    The suffix is matched case-insensitively and may include the dot
    (".ts") or not ("ts").
    """
    key = suffix.lower().lstrip(".")
    if key in _PARSER_CACHE:
        return _PARSER_CACHE[key]

    # The registry key has no dot; a parser declares its extensions WITH
    # one. Normalise both sides before comparing.
    wanted = f".{key}"

    parser: Optional[LanguageParser] = None
    for cls in _load_parser_classes().values():
        instance = _instantiate(cls)
        if instance is None:
            continue
        if wanted in instance.extensions:
            parser = instance
            break

    _PARSER_CACHE[key] = parser
    return parser


_INSTANCES: dict[str, Optional[LanguageParser]] = {}


def _instantiate(cls: type) -> Optional[LanguageParser]:
    """Create one parser instance per class, tolerating failures."""
    name = cls.__name__
    if name not in _INSTANCES:
        try:
            _INSTANCES[name] = cls()
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not create parser %s: %s", name, exc)
            _INSTANCES[name] = None
    return _INSTANCES[name]


def supported_extensions() -> list[str]:
    """Every extension the registry can currently parse."""
    extensions: list[str] = []
    for cls in _load_parser_classes().values():
        instance = _instantiate(cls)
        if instance is None:
            continue
        extensions.extend(instance.extensions)
    return sorted(set(extensions))
