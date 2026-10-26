"""
mindmap_classifier.py
The deterministic six-pillar / role taxonomy behind the mind-map.

The classifier is server-side on purpose: two clients must not be able
to disagree about whether `backend/main.py` is backend or infrastructure.
It is also rule-based and total — every path gets a pillar and a role,
with no LLM and no confidence score.

Precedence is fixed and documented in `classify_file`. The order is the
contract: tests win over docs, infrastructure wins over docs, and the
default for code is the backend pillar.
"""
from __future__ import annotations

from pathlib import Path

#: The six pillars, in render order. The order is part of the API: a
#: client may render them without sorting.
PILLARS: tuple[dict, ...] = (
    {
        "id": "frontend",
        "label": "Frontend & UI",
        "description": "Browser and editor clients, components, hooks, and styles.",
    },
    {
        "id": "backend",
        "label": "Backend & Core",
        "description": "Servers, ingestion, graph analysis, and domain logic.",
    },
    {
        "id": "data",
        "label": "Data & Models",
        "description": "Schemas, migrations, persistence, and the domain model.",
    },
    {
        "id": "infrastructure",
        "label": "Infrastructure & Delivery",
        "description": "Build, deploy, CI, packaging, and agent configuration.",
    },
    {
        "id": "tests",
        "label": "Tests & Fixtures",
        "description": "Unit, contract, browser, and fixture repositories.",
    },
    {
        "id": "docs",
        "label": "Docs & Knowledge",
        "description": "READMEs, guides, design notes, and static content.",
    },
)

PILLAR_IDS = tuple(pillar["id"] for pillar in PILLARS)
PILLAR_BY_ID = {pillar["id"]: pillar for pillar in PILLARS}

#: The first path segment a pillar owns. The tree strips it so the pillar
#: itself is the top level: `backend/api/x.py` renders as pillar →
#: folder `backend/api`, not pillar → folder `backend` → folder `api`.
PILLAR_ROOT_DIRS: dict[str, frozenset[str]] = {
    "frontend": frozenset({"frontend", "web", "ui", "client", "app"}),
    "backend": frozenset({"backend", "server", "api"}),
    "data": frozenset({"data", "db", "database"}),
    "infrastructure": frozenset({".github", "infra", "deploy", "ops", ".devcontainer"}),
    "tests": frozenset({"tests", "test", "__tests__", "spec", "specs"}),
    "docs": frozenset({"docs", "doc"}),
}

_TEST_PARTS = frozenset({"tests", "test", "__tests__", "spec", "specs"})
_TEST_SUFFIXES = (".test.ts", ".test.tsx", ".test.js", ".test.jsx",
                  ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")
_DOC_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".adoc", ".txt"})
_DOC_NAMES = frozenset({
    "readme", "license", "licence", "changelog", "contributing", "authors",
    "code_of_conduct", "security", "notice",
})
_INFRA_PARTS = frozenset({
    ".github", ".gitlab", ".circleci", ".devcontainer", ".vscode",
    ".agents", ".kiro", ".cursor", ".codex", ".windsurf", ".roo", ".cline",
    "infra", "deploy", "deployment", "ops", "docker", "k8s", "helm",
})
_INFRA_NAMES = frozenset({
    "dockerfile", "containerfile", "procfile", "makefile", "justfile",
    "render.yaml", "render.yml", "vercel.json", "netlify.toml",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "requirements.txt", "pyproject.toml", "poetry.lock", "pipfile",
    "tsconfig.json", "jsconfig.json", "vite.config.ts", "vite.config.js",
    ".gitignore", ".gitattributes", ".dockerignore", ".env.example",
    "build.sh", "docker-compose.yml", "docker-compose.yaml",
})
_DATA_PARTS = frozenset({
    "data", "models", "model", "schema", "schemas", "migrations",
    "migration", "db", "database", "persistence", "storage",
})
_DATA_SUFFIXES = frozenset({".sql", ".prisma", ".graphql", ".gql"})
_REPOSITORY_PARTS = frozenset({"repositories", "repository", "repos", "repo", "dao", "store", "stores"})
_FRONTEND_PARTS = frozenset({
    "frontend", "web", "ui", "client", "components", "pages", "views",
    "hooks", "styles", "public", "assets", "extensions",
})
_FRONTEND_SUFFIXES = frozenset({".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"})
_ENTRY_NAMES = frozenset({
    "main.py", "app.py", "server.py", "__main__.py", "manage.py", "cli.py",
    "main.ts", "main.tsx", "index.ts", "index.tsx", "app.ts", "app.tsx",
})
_SERVICE_WORDS = frozenset({"service", "services", "usecase", "usecases", "handler", "handlers"})
_MODEL_WORDS = frozenset({"model", "models", "domain", "entities", "entity"})


def _parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in Path(path).as_posix().split("/") if part)


def _stem(path: str) -> str:
    name = Path(path).name.lower()
    for suffix in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def classify_file(path: str, route_count: int = 0) -> dict:
    """
    Classify one repository-relative path.

    Returns `{"pillar", "role"}`. Both are always present; the caller
    never has to invent a fallback. `route_count` lets a route-bearing
    file become an `api_controller` without re-parsing it.
    """
    parts = _parts(path)
    name = Path(path).name.lower()
    stem = _stem(path)
    suffix = Path(path).suffix.lower()
    lowered = "/".join(parts)

    # 1. Tests. A test named `docs_test.py` is still a test.
    if (
        any(part in _TEST_PARTS for part in parts)
        or name.startswith("test_")
        or name.startswith("test.")
        or stem.endswith("_test")
        or name.endswith(_TEST_SUFFIXES)
    ):
        return {"pillar": "tests", "role": "test"}

    # 2. Infrastructure. A workflow file is delivery, not documentation,
    #    even when it lives under a dot-directory.
    if (
        any(part in _INFRA_PARTS for part in parts)
        or name in _INFRA_NAMES
        or name.startswith("docker-compose.")
        or name.startswith("vite.config.")
        or name.startswith("eslint")
        or name.startswith(".env")
        or name.startswith(".prettier")
    ):
        return {"pillar": "infrastructure", "role": "config"}

    # 3. Documentation.
    if (
        suffix in _DOC_SUFFIXES
        or stem in _DOC_NAMES
        or "docs" in parts
        or "doc" in parts
    ):
        return {"pillar": "docs", "role": "docs"}

    # 4. Data and persistence.
    if suffix in _DATA_SUFFIXES or any(part in _DATA_PARTS for part in parts):
        role = "repository" if any(part in _REPOSITORY_PARTS for part in parts) else "model"
        return {"pillar": "data", "role": role}

    # 5. Frontend.
    if (
        any(part in _FRONTEND_PARTS for part in parts)
        or suffix in _FRONTEND_SUFFIXES
    ):
        if "hooks" in parts or stem.startswith("use"):
            role = "hook"
        elif suffix in _FRONTEND_SUFFIXES or any(
            part in {"components", "pages", "views"} for part in parts
        ):
            role = "ui_component"
        else:
            role = "utility"
        return {"pillar": "frontend", "role": role}

    # 6. Backend and core. This is the default for code, so it goes last.
    if name in _ENTRY_NAMES:
        role = "entry_point"
    elif route_count > 0 or any(
        part in {"api", "routers", "routes", "controllers", "endpoints"}
        for part in parts
    ):
        role = "api_controller"
    elif any(part in _SERVICE_WORDS for part in parts) or "service" in stem:
        role = "service"
    elif any(part in _REPOSITORY_PARTS for part in parts) or "repository" in stem:
        role = "repository"
    elif any(part in _MODEL_WORDS for part in parts):
        role = "model"
    else:
        role = "utility"
    return {"pillar": "backend", "role": role}


def classify_symbol(node: dict, file_role: str) -> str:
    """
    The role of a symbol node.

    A symbol usually inherits its file's role. The exceptions are a class
    in a model file (a model), and a symbol whose file is the entry point
    or an API controller — both stay at that role so a reader can jump
    from the symbol to the same mental bucket as the file.
    """
    if node.get("routes"):
        return "api_controller"
    if file_role in {
        "entry_point", "api_controller", "service", "repository", "model",
        "ui_component", "hook", "test", "docs", "config",
    }:
        return file_role
    if node.get("type") == "class":
        return "model" if file_role == "model" else "utility"
    return "utility"


def pillar_label(pillar_id: str) -> str:
    """The display label for a pillar id, or the id itself if unknown."""
    return PILLAR_BY_ID.get(pillar_id, {}).get("label", pillar_id)


def pillar_descriptions() -> list[dict]:
    """A copy of the public pillar list, safe for a response payload."""
    return [dict(pillar) for pillar in PILLARS]
