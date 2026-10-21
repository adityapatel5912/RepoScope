"""
conftest.py — puts backend/ on sys.path so `import main` resolves when
pytest runs from either the repo root or backend/.

Also provides the shared fixtures used by the golden-file test and the
graph-analysis tests.
"""
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

#: Golden snapshots live outside the fixture directories — see the note in
#: test_graph_golden.py for why.
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def pytest_addoption(parser):
    """
    Register `--regen-golden`.

    Golden snapshots are regenerated ONLY when this flag is passed
    explicitly. It is never automatic, so a snapshot can never be silently
    rewritten to match a broken parser.
    """
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Regenerate the golden graph snapshots for the fixture repositories.",
    )


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """The directory holding every test fixture repository."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def fixture_repo():
    """Factory: build the graph for a named fixture repository."""
    from graph_builder import build_graph_from_repo

    def _build(name: str) -> dict:
        path = FIXTURES_DIR / name
        if not path.is_dir():
            raise AssertionError(f"Unknown fixture repository: {name}")
        return build_graph_from_repo(str(path))

    return _build


@pytest.fixture(scope="session")
def built_graph(fixture_repo):
    """The multi-language fixture graph — the richest of the fixtures."""
    return fixture_repo("multilang")


@pytest.fixture(scope="session")
def circular_graph(fixture_repo):
    """The circular-import fixture graph."""
    return fixture_repo("circular")


@pytest.fixture(scope="session")
def golden_snapshot():
    """Loader for a fixture's committed golden snapshot."""
    def _load(name: str) -> dict:
        path = GOLDEN_DIR / f"{name}.json"
        if not path.exists():
            raise AssertionError(
                f"Missing golden snapshot for '{name}' at {path}. "
                f"Generate it with: python -m pytest tests/test_graph_golden.py --regen-golden"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    return _load
