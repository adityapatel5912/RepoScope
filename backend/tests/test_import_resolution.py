"""
test_import_resolution.py
The import edges — the thing that makes the architecture map an
architecture map rather than a list of files.

Every other intelligence in RepoScope hangs off these edges. The blast
radius a developer reads in the status bar, the "what breaks if I change
this" an agent asks for, the dependency cycles, the unreachable symbols —
all of it walks import edges.

The bug this file pins down: a repository is not always imported from
its own root. `backend/` is a source root in this project, so
`backend/main.py` writes `from graph_builder import build_graph_from_repo`
— and "graph_builder" is NOT the file's dotted path ("backend.graph_builder").
Before the suffix resolution, that import produced no edge at all, so the
blast radius of the repository's most central module read "no dependents".
"""
from pathlib import Path

from graph_builder import build_graph_from_repo


def _edges(graph: dict, kind: str = "imports") -> list[tuple[str, str]]:
    return [
        (e["source"], e["target"])
        for e in graph["edges"]
        if e.get("type") == kind
    ]


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_bare_module_import_resolves_from_a_source_root(tmp_path):
    """
    `backend/main.py` says `from graph_builder import build`. The module
    lives at `backend/graph_builder.py`.
    """
    _write(tmp_path, "backend/main.py", "from graph_builder import build\n")
    _write(tmp_path, "backend/graph_builder.py", "def build():\n    return 1\n")

    graph = build_graph_from_repo(str(tmp_path))

    assert ("file:backend/main.py", "file:backend/graph_builder.py") in _edges(graph)


def test_a_package_import_resolves_to_the_module_inside_it(tmp_path):
    """`from api.routers import analysis` means `backend/api/routers/analysis.py`."""
    _write(
        tmp_path,
        "backend/app.py",
        "from api.routers import analysis\n",
    )
    _write(tmp_path, "backend/api/__init__.py", "")
    _write(tmp_path, "backend/api/routers/__init__.py", "")
    _write(tmp_path, "backend/api/routers/analysis.py", "def run():\n    return 2\n")

    graph = build_graph_from_repo(str(tmp_path))

    targets = {t for _, t in _edges(graph)}
    assert "file:backend/api/routers/analysis.py" in targets


def test_an_external_import_produces_no_edge(tmp_path):
    """A third-party package must not become a dangling edge."""
    _write(tmp_path, "app.py", "import os\nimport requests\n")

    graph = build_graph_from_repo(str(tmp_path))

    assert _edges(graph) == []


def test_a_relative_import_still_wins(tmp_path):
    """Relative imports resolve exactly as before — the suffix rule is a fallback."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/helper.py", "def h():\n    return 1\n")
    _write(tmp_path, "pkg/consumer.py", "from .helper import h\n")

    graph = build_graph_from_repo(str(tmp_path))

    assert ("file:pkg/consumer.py", "file:pkg/helper.py") in _edges(graph)


def test_the_exact_dotted_path_wins_over_a_suffix_match(tmp_path):
    """
    Two files could both end with "utils". The one the dotted path names
    exactly is the one that must be resolved.
    """
    _write(tmp_path, "pkg/utils.py", "def u():\n    return 1\n")
    _write(tmp_path, "other/utils.py", "def u():\n    return 2\n")
    _write(tmp_path, "pkg/consumer.py", "from pkg.utils import u\n")

    graph = build_graph_from_repo(str(tmp_path))

    pairs = _edges(graph)
    assert ("file:pkg/consumer.py", "file:pkg/utils.py") in pairs
    assert ("file:pkg/consumer.py", "file:other/utils.py") not in pairs


def test_the_import_edge_gives_the_module_a_blast_radius(tmp_path):
    """
    The reason the edges matter: with the import resolved, the file that
    imports it has a dependent. Before, it had none.
    """
    _write(tmp_path, "backend/main.py", "from graph_builder import build\n")
    _write(tmp_path, "backend/graph_builder.py", "def build():\n    return 1\n")

    graph = build_graph_from_repo(str(tmp_path))

    from impact_analyzer import compute_blast_radius

    impact = compute_blast_radius(graph, "file:backend/graph_builder.py", max_depth=3)
    assert impact["total_impacted"] >= 1
