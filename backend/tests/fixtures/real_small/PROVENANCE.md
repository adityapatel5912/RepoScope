# Fixture: `real_small` — a vendored real repository

This directory is a **verbatim copy of the source package** of a small,
permissively-licensed open-source project, vendored so that the parser is
exercised against genuine third-party code rather than only against
hand-written fixtures.

| | |
|---|---|
| **Upstream** | `hukkin/tomli` — https://github.com/hukkin/tomli |
| **Version** | 2.5.0 |
| **Licence** | MIT — see `LICENSE` in this directory |
| **Copyright** | Copyright (c) 2021 Taneli Hukkinen |
| **Vendored** | `src/tomli/` only, plus `LICENSE`, `pyproject.toml`, `setup.py` |

The upstream repository's `tests/`, `benchmark/`, `fuzzer/`, `profiler/`,
and `scripts/` directories are **not** vendored — they carry a large
tree of TOML test data that would dominate the fixture without
exercising the parser any further.

## Why this fixture exists

Hand-authored fixtures (`multilang/`, `circular/`, `nested/`) are
deterministic and readable, but they are written by us, so they can only
prove the parser handles code we already thought of. This one proves the
parser handles code somebody else wrote:

- **Real type hints** — `def loads(s: str, *, parse_float: ParseFloat = ...) -> dict[str, Any]:`
- **Real dataclasses** — `_types.py` uses `@dataclass(frozen=True)`
- **Real relative imports** — `from ._parser import ...`, `from ._re import ...`, `from ._types import ...`
  (level-1 relative resolution)
- **Real packaging metadata** — `pyproject.toml` and `setup.py` are parsed as
  file nodes alongside the source
- **A `src/` layout** — the package is not at the repository root
- **Real-world volume** — `_parser.py` is ~700 lines, far larger than
  anything in the hand-authored fixtures

## Licence

MIT. The full licence text is retained at `LICENSE` in this directory and
also in each vendored source file's SPDX header. Vendoring is for testing
only; the code is not distributed as part of RepoScope at runtime.
