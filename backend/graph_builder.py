"""
graph_builder.py
Local AST-based code graph builder — fallback when codebase-memory-mcp
is unavailable. Parses Python files with ast, other files with regex.

Import edges are RESOLVED against a module index built in a first pass, so
`from backend.engine import decision_model`, relative imports (`from .db
import get_db`), and JS/TS relative or alias imports (`@/components/x`)
all land on real file nodes instead of dangling ids.
"""
import ast
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("reposcope.graph_builder")

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__",
              ".venv", "venv", ".mypy_cache", ".pytest_cache"}

_PY_EXTS = {".py"}
_JS_EXTS = {".ts", ".tsx", ".js", ".jsx"}


def build_graph_from_repo(root: str) -> dict:
    """Parse a cloned repo into nodes + edges. Returns graph dict."""
    nodes: list[dict] = []
    edges: list[dict] = []
    root_path = Path(root)

    # ── Pass 1: collect files + build module indexes ────────────────────────
    py_index: dict[str, str] = {}    # dotted module  -> file:rel
    py_stems: dict[str, str] = {}    # bare stem      -> file:rel (fallback)
    js_files: set[str] = set()       # rel paths of js/ts files
    js_stems: dict[str, str] = {}    # bare stem      -> file:rel (alias '@/', '~/')

    collected: list[tuple[Path, str, str]] = []  # (path, rel, suffix)
    for path in root_path.rglob("*"):
        if any(p in _SKIP_DIRS for p in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            rel = str(path.relative_to(root_path)).replace("\\", "/")
        except ValueError:
            continue
        collected.append((path, rel, path.suffix))

        if path.suffix in _PY_EXTS:
            parts = rel[:-3].split("/")                      # strip .py
            if parts[-1] == "__init__":
                py_index[".".join(parts[:-1])] = f"file:{rel}"
            py_index[".".join(parts)] = f"file:{rel}"
            py_stems.setdefault(parts[-1], f"file:{rel}")
        elif path.suffix in _JS_EXTS:
            js_files.add(rel)
            js_stems.setdefault(Path(rel).stem, f"file:{rel}")

    def resolve_py(module: str | None, level: int, pkg_parts: list[str],
                   imported_name: str | None = None) -> str | None:
        """Resolve a python import to a file id, or None when external."""
        if level:  # relative import: level=1 → this package, 2 → parent, …
            base = pkg_parts[: len(pkg_parts) - (level - 1)] if len(pkg_parts) >= level else []
        else:
            base = module.split(".") if module else []
        if module and not level:
            parts = base
        elif module:
            parts = base + module.split(".")
        else:
            parts = base
        variants = [".".join(parts)]
        if imported_name:
            variants.append(".".join(parts + [imported_name]))
        for v in variants:
            if v in py_index:
                return py_index[v]
        # bare-stem fallback (flat layouts / src-less repos)
        if imported_name and imported_name in py_stems:
            return py_stems[imported_name]
        return None

    def resolve_js(spec: str, importer_rel: str) -> str | None:
        """Resolve a JS/TS import specifier to a file id, or None (external)."""
        if spec.startswith("@/") or spec.startswith("~/"):
            cand_base = [spec[2:], f"src/{spec[2:]}"]
        elif spec.startswith("./") or spec.startswith("../"):
            parts = (Path(importer_rel).parent.joinpath(spec)).as_posix()
            cand_base = [parts]
        else:
            return None  # bare package import — external, skip
        resolved = []
        for base in cand_base:
            norm = os.path.normpath(base).replace("\\", "/")
            resolved.append(norm)
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                resolved.append(f"{norm}{ext}")
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                resolved.append(f"{norm}/index{ext}")
        for cand in resolved:
            if cand in js_files:
                return f"file:{cand}"
        return None

    # ── Pass 2: parse code files ─────────────────────────────────────────────
    for path, rel, suffix in collected:
        fid = f"file:{rel}"
        nodes.append({
            "id": fid,
            "type": "file",
            "label": rel,
            "language": suffix.lstrip(".") or "txt",
            "size": path.stat().st_size,
        })
        if suffix in _PY_EXTS:
            pkg_parts = rel[:-3].split("/")[:-1]   # file's package = parent dirs
            _parse_python(path, rel, fid, nodes, edges,
                          pkg_parts, resolve_py)
        elif suffix in _JS_EXTS:
            _parse_js_ts(path, rel, fid, nodes, edges, resolve_js)

    # Deduplicate edges
    seen: set[tuple] = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"], e.get("type"))
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    log.info("Graph built: %d nodes, %d edges from %s", len(nodes), len(unique_edges), root)
    return {
        "nodes": nodes,
        "edges": unique_edges,
        "summary": f"{len(nodes)} nodes, {len(unique_edges)} edges",
    }


def _parse_python(path: Path, rel: str, fid: str, nodes: list, edges: list,
                  pkg_parts: list[str], resolve) -> None:
    try:
        source = path.read_text(errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_id = f"func:{rel}:{node.name}"
            nodes.append({
                "id": fn_id,
                "type": "function",
                "label": node.name,
                "file": rel,
                "line": node.lineno,
            })
            edges.append({"source": fid, "target": fn_id, "type": "contains"})

        elif isinstance(node, ast.ClassDef):
            cls_id = f"class:{rel}:{node.name}"
            nodes.append({
                "id": cls_id,
                "type": "class",
                "label": node.name,
                "file": rel,
                "line": node.lineno,
            })
            edges.append({"source": fid, "target": cls_id, "type": "contains"})

        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = resolve(alias.name, 0, pkg_parts)
                if target and target != fid:
                    edges.append({"source": fid, "target": target, "type": "imports"})

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                target = resolve(node.module, node.level or 0, pkg_parts, alias.name)
                if target and target != fid:
                    edges.append({"source": fid, "target": target, "type": "imports"})


def _parse_js_ts(path: Path, rel: str, fid: str, nodes: list, edges: list,
                 resolve) -> None:
    try:
        source = path.read_text(errors="ignore")
    except Exception:
        return

    # Functions: function foo / const foo = / foo = () =>
    for m in re.finditer(
        r'(?:^|\s)(?:export\s+)?(?:async\s+)?function\s+(\w+)|'
        r'(?:^|\s)(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(',
        source, re.MULTILINE
    ):
        name = m.group(1) or m.group(2)
        if not name:
            continue
        fn_id = f"func:{rel}:{name}"
        nodes.append({"id": fn_id, "type": "function", "label": name, "file": rel})
        edges.append({"source": fid, "target": fn_id, "type": "contains"})

    # Classes
    for m in re.finditer(r'(?:^|\s)(?:export\s+)?class\s+(\w+)', source, re.MULTILINE):
        cls_id = f"class:{rel}:{m.group(1)}"
        nodes.append({"id": cls_id, "type": "class", "label": m.group(1), "file": rel})
        edges.append({"source": fid, "target": cls_id, "type": "contains"})

    # Imports — static `import … from` and `export … from`
    for m in re.finditer(r"(?:import|export)\s+.*?\s+from\s+['\"](.+?)['\"]", source):
        target = resolve(m.group(1), rel)
        if target and target != fid:
            edges.append({"source": fid, "target": target, "type": "imports"})
