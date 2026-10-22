"""
monorepo.py
Monorepo and workspace detection.

Milestone 9.1. "Enterprise evaluators ask this in the first ten
minutes." A 900-file repository that is really forty packages is a
different problem from a 900-file repository, and a tool that treats
them the same gives a confusing answer.

The detection looks for the markers each ecosystem uses:

| Ecosystem | Marker |
|---|---|
| npm / yarn / pnpm | `package.json` with `workspaces`, or `pnpm-workspace.yaml` |
| Go | `go.work` |
| Rust | a `Cargo.toml` with `workspace.members` |
| Python | `pyproject.toml` with `tool.uv.workspace`, or `poetry` workspaces |
| JavaScript build tools | `nx.json`, `turbo.json` |

Each package is reported with its root directory and its name, so the
graph can be built per package and the packages linked together.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger("reposcope.monorepo")

#: The directories never descended into when looking for packages.
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv",
    ".reposcope", "target", ".next", ".nuxt", "vendor", "Pods",
}

#: The package manifests, by ecosystem.
MANIFESTS = {
    "package.json": "npm",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pyproject.toml": "python",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 - a malformed manifest is skipped
        return {}


def _glob_to_paths(root: Path, pattern: str) -> list[Path]:
    """Expand the `packages/*` style patterns the manifests use."""
    pattern = pattern.strip().rstrip("/")
    if not pattern:
        return []
    if "*" not in pattern:
        candidate = root / pattern
        return [candidate] if candidate.is_dir() else []

    # Only the trailing `*` form is used in practice.
    if pattern.endswith("/*"):
        parent = root / pattern[:-2]
        if not parent.is_dir():
            return []
        return sorted(p for p in parent.iterdir() if p.is_dir())
    if pattern == "*":
        return sorted(p for p in root.iterdir() if p.is_dir())
    return []


def _npm_workspaces(root: Path) -> list[Path]:
    """The package roots declared by npm, yarn or pnpm."""
    candidates: list[Path] = []

    package_json = root / "package.json"
    if package_json.is_file():
        data = _read_json(package_json)
        workspaces = data.get("workspaces")
        patterns: list[str] = []
        if isinstance(workspaces, list):
            patterns = [str(p) for p in workspaces]
        elif isinstance(workspaces, dict):
            patterns = [str(p) for p in (workspaces.get("packages") or [])]
        for pattern in patterns:
            candidates.extend(_glob_to_paths(root, pattern))

    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file():
        try:
            text = pnpm.read_text(encoding="utf-8", errors="replace")
            in_block = False
            for line in text.splitlines():
                if line.strip().startswith("packages:"):
                    in_block = True
                    continue
                if in_block:
                    stripped = line.strip()
                    if stripped.startswith("-"):
                        candidates.extend(_glob_to_paths(root, stripped.lstrip("- ")))
                    elif stripped and not stripped.startswith("#"):
                        in_block = False
        except OSError:
            pass

    return [c for c in candidates if c.is_dir()]


def _go_workspaces(root: Path) -> list[Path]:
    work_file = root / "go.work"
    if not work_file.is_file():
        return []
    try:
        text = work_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[Path] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("use "):
            target = (root / stripped[4:].strip().strip('"')).resolve()
            if target.is_dir():
                out.append(target)
    return out


def _rust_workspaces(root: Path) -> list[Path]:
    manifest = root / "Cargo.toml"
    if not manifest.is_file():
        return []
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    members: list[str] = []
    in_members = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("members"):
            in_members = "[" not in stripped
            if "[" in stripped:
                members.extend(
                    m.strip().strip('"').strip("'")
                    for m in stripped.split("[", 1)[1].split("]", 1)[0].split(",")
                    if m.strip()
                )
            continue
        if in_members:
            if stripped.startswith("]"):
                in_members = False
                continue
            members.append(stripped.strip('"').strip("'").rstrip(","))
    return [p for p in (_glob_to_paths(root, m) for m in members) if p]


def _python_workspaces(root: Path) -> list[Path]:
    manifest = root / "pyproject.toml"
    if not manifest.is_file():
        return []
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[Path] = []
    # `[tool.uv.workspace] members = ["packages/*"]`
    for match in re.finditer(r"members\s*=\s*\[([^\]]*)\]", text):
        for member in match.group(1).split(","):
            pattern = member.strip().strip('"').strip("'")
            if pattern:
                out.extend(_glob_to_paths(root, pattern))
    return [p for p in out if p.is_dir()]


def _package_name(package_root: Path, ecosystem: str) -> str:
    """The package's own name, from its manifest."""
    if ecosystem == "npm":
        data = _read_json(package_root / "package.json")
        return str(data.get("name") or package_root.name)
    if ecosystem == "go":
        go_mod = package_root / "go.mod"
        try:
            for line in go_mod.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("module "):
                    return line.split(" ", 1)[1].strip()
        except OSError:
            pass
        return package_root.name
    if ecosystem == "rust":
        cargo = package_root / "Cargo.toml"
        try:
            for line in cargo.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("name"):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return package_root.name
    return package_root.name


def detect_workspaces(root: str | Path) -> list[dict]:
    """
    The packages in a monorepo.

    Returns a list of `{"name", "root", "ecosystem", "relative_root"}`.
    An empty list means this is an ordinary repository — which is the
    common case, and the right answer.
    """
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        return []

    found: list[dict] = []
    seen: set[str] = set()

    def add(package_root: Path, ecosystem: str) -> None:
        key = str(package_root)
        if key in seen:
            return
        seen.add(key)
        found.append({
            "name": _package_name(package_root, ecosystem),
            "root": key,
            "relative_root": str(package_root.relative_to(root_path)).replace("\\", "/"),
            "ecosystem": ecosystem,
        })

    for package_root in _npm_workspaces(root_path):
        add(package_root, "npm")
    for package_root in _go_workspaces(root_path):
        add(package_root, "go")
    for package_root in _rust_workspaces(root_path):
        add(package_root, "rust")
    for package_root in _python_workspaces(root_path):
        add(package_root, "python")

    # `nx.json` and `turbo.json` do not declare the packages themselves —
    # they declare the build system. The packages are still the npm
    # workspaces, so they are already covered.

    return sorted(found, key=lambda w: w["relative_root"])


def is_monorepo(root: str | Path) -> bool:
    """True when the repository holds more than one package."""
    return len(detect_workspaces(root)) > 1
