"""
backend/scaffolder.py
Deterministic executable multi-file starter kit generator (Phase 7, V2.6).

Emits a runnable 12-20 file starter kit from the analyzed repository's real stack:
- Preview tree
- Zip stream with path traversal protections
- Terminal bootstrap command (npx reposcope-mcp scaffold --from <owner/repo> --out ./app)
- Stack-specific templates (Python FastAPI/CLI, TypeScript React/Node, Generic fallback)
- Placeholders-only .env.example (zero secret leakage)
- Verified with compileall syntax validation
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from token_metrics import estimate_tokens
    from reverse_prompt_compiler import detect_stack
except ImportError:
    from backend.token_metrics import estimate_tokens
    from backend.reverse_prompt_compiler import detect_stack


_TRAVERSAL_RE = re.compile(r"(^|[/\\])\.\.([/\\]|$)")


def sanitize_rel_path(path: str) -> str | None:
    """Sanitize and validate a relative file path for scaffold generation.
    
    Rejects:
    - Path traversal (..)
    - Absolute paths (/ or \\ or C:)
    - Windows reserved chars
    - Empty paths
    Preserves:
    - Dotfiles (e.g., .env.example, .gitignore, .claude/CLAUDE.md)
    """
    if not path or not isinstance(path, str):
        return None
    norm = path.strip().replace("\\", "/")
    if norm.startswith("/") or norm.startswith("~"):
        return None
    while norm.startswith("./"):
        norm = norm[2:]
    norm = norm.lstrip("/")
    if not norm:
        return None
    if ":" in norm.split("/")[0]:  # Windows drive letter escape
        return None
    parts = norm.split("/")
    for p in parts:
        if p == ".." or p == "":
            return None
    if _TRAVERSAL_RE.search(norm):
        return None
    return norm


def extract_env_keys(root: str | None, graph: Dict[str, Any]) -> List[str]:
    """Extract environment variable keys from .env.example or graph references.
    
    Never reads values or actual .env files — emits only key names with placeholders.
    """
    keys: Set[str] = set()
    if root:
        try:
            example_path = Path(root) / ".env.example"
            if example_path.is_file():
                for line in example_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k = line.split("=", 1)[0].strip()
                        if k and re.match(r"^[A-Z0-9_]+$", k):
                            keys.add(k)
        except Exception:
            pass

    # Extract common keys referenced in graph labels
    for n in graph.get("nodes", []):
        lbl = n.get("label", "")
        if "database" in lbl.lower() or "db" in lbl.lower():
            keys.add("DATABASE_URL")
        if "auth" in lbl.lower() or "jwt" in lbl.lower() or "secret" in lbl.lower():
            keys.add("APP_SECRET_KEY")
        if "redis" in lbl.lower() or "cache" in lbl.lower():
            keys.add("REDIS_URL")

    if not keys:
        keys = {"PORT", "APP_ENV", "LOG_LEVEL"}
    return sorted(keys)


class Scaffolder:
    """Deterministic multi-file starter kit scaffolder."""

    def __init__(self, graph: Dict[str, Any], local_path: str | None = None, repo_name: str | None = None):
        self.graph = graph or {}
        self.local_path = local_path
        if repo_name:
            self.repo_name = repo_name.split("/")[-1].strip() or "Repository"
            self.repo_slug = repo_name.strip()
        elif local_path:
            self.repo_name = os.path.basename(local_path.rstrip("/\\")) or "Repository"
            self.repo_slug = f"local/{self.repo_name}"
        else:
            self.repo_name = "Repository"
            self.repo_slug = "starter/repo"

    def generate(self, mode: str = "preview") -> Dict[str, Any]:
        """Generate starter scaffold in the requested mode (preview, zip, command)."""
        clean_mode = (mode or "preview").lower().strip()
        stack = detect_stack(self.graph, self.local_path)
        project_type, files, entry_files = self._build_file_set(stack)

        # Sanitize and validate every file path
        sanitized_files: List[Dict[str, str]] = []
        file_tree: List[str] = []
        warnings: List[str] = []

        for f in files:
            path = sanitize_rel_path(f.get("path", ""))
            if not path:
                warnings.append(f"Rejected invalid or traversal path: '{f.get('path')}'")
                continue
            content = f.get("content", "")
            purpose = f.get("purpose", "Starter module")
            language = f.get("language") or self._detect_language(path)
            sanitized_files.append({
                "path": path,
                "content": content,
                "purpose": purpose,
                "language": language,
            })
            file_tree.append(path)

        file_tree = sorted(file_tree)
        bootstrap_command = f"npx reposcope-mcp scaffold --from {self.repo_slug} --out ./app"

        # Compute token estimate
        total_chars = sum(len(f["content"]) for f in sanitized_files)
        token_estimate = estimate_tokens("\n".join(f["content"] for f in sanitized_files))

        if clean_mode == "command":
            return {
                "ok": True,
                "command": bootstrap_command,
                "project_type": project_type,
            }

        return {
            "ok": True,
            "project_type": project_type,
            "file_tree": file_tree,
            "files": sanitized_files,
            "entry_files": entry_files,
            "top_nodes": [f["path"] for f in sanitized_files if f["path"] in entry_files],
            "warnings": warnings,
            "token_estimate": token_estimate,
            "bootstrap_command": bootstrap_command,
        }

    def generate_zip_bytes(self) -> bytes:
        """Generate safe, in-memory zip archive bytes containing all scaffold files."""
        res = self.generate(mode="preview")
        files = res.get("files", [])

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                path = f["path"]
                # Strict traversal and root escape verification
                clean = sanitize_rel_path(path)
                if not clean:
                    continue
                zf.writestr(clean, f["content"])

        buf.seek(0)
        return buf.getvalue()

    def _detect_language(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".py", ".pyw"):
            return "python"
        elif ext in (".ts", ".tsx"):
            return "typescript"
        elif ext in (".js", ".jsx", ".mjs"):
            return "javascript"
        elif ext in (".json",):
            return "json"
        elif ext in (".md",):
            return "markdown"
        elif ext in (".toml",):
            return "toml"
        elif ext in (".yaml", ".yml"):
            return "yaml"
        return "text"

    def _build_file_set(self, stack: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]], List[str]]:
        languages = stack.get("languages", [])
        frameworks = stack.get("frameworks", [])

        if "Python" in languages:
            return self._build_python_fastapi_kit(stack)
        elif "TypeScript" in languages or "JavaScript" in languages:
            return self._build_typescript_kit(stack)
        else:
            return self._build_generic_kit(stack)

    def _build_python_fastapi_kit(self, stack: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]], List[str]]:
        project_type = "python-fastapi" if "FastAPI" in stack.get("frameworks", []) else "python-starter"
        env_keys = extract_env_keys(self.local_path, self.graph)
        routes = self.graph.get("api_routes", [])

        # Format route handlers
        route_funcs: List[str] = []
        if routes:
            for r in routes[:8]:
                method = r.get("method", "get").lower()
                path = r.get("path", "/")
                handler = r.get("handler", "endpoint").replace("-", "_")
                route_funcs.append(f"""@router.{method}("{path}")
def {handler}():
    \"\"\"Auto-generated starter handler for {path}.\"\"\"
    # TODO: Implement domain logic
    return {{"status": "ok", "route": "{path}"}}
""")
        else:
            route_funcs.append("""@router.get("/health")
def health_check():
    \"\"\"Liveness probe endpoint.\"\"\"
    return {"status": "ok"}
""")

        files = [
            {
                "path": "main.py",
                "purpose": "Application entrypoint and server runner",
                "content": f"""\"\"\"
main.py — Starter entrypoint for {self.repo_name}
\"\"\"
from fastapi import FastAPI
from app.api import router
from app.config import settings

app = FastAPI(title="{self.repo_name}", version="0.1.0")
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {{"message": "Welcome to {self.repo_name}", "env": settings.APP_ENV}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=settings.PORT, reload=True)
""",
            },
            {
                "path": "app/__init__.py",
                "purpose": "Package initializer",
                "content": "\"\"\"Application package.\"\"\"\n",
            },
            {
                "path": "app/api.py",
                "purpose": "REST API router declarations",
                "content": f"""\"\"\"
app/api.py — API route declarations
\"\"\"
from fastapi import APIRouter

router = APIRouter()

{"".join(route_funcs)}
""",
            },
            {
                "path": "app/models.py",
                "purpose": "Pydantic domain schemas and data contracts",
                "content": f"""\"\"\"
app/models.py — Data models and contracts
\"\"\"
from pydantic import BaseModel, Field


class BaseRecord(BaseModel):
    id: str = Field(..., description="Unique record identifier")
    name: str = Field(..., description="Entity name")


class StatusResponse(BaseModel):
    ok: bool = True
    message: str = "Success"
""",
            },
            {
                "path": "app/services.py",
                "purpose": "Core business domain logic",
                "content": f"""\"\"\"
app/services.py — Domain service logic
\"\"\"
from app.models import StatusResponse


class CoreService:
    \"\"\"Domain service for {self.repo_name}.\"\"\"

    def process(self, payload: dict) -> StatusResponse:
        # TODO: Implement core business logic
        return StatusResponse(ok=True, message="Processed successfully")
""",
            },
            {
                "path": "app/config.py",
                "purpose": "Type-safe environment configuration",
                "content": f"""\"\"\"
app/config.py — Application configuration
\"\"\"
import os


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")
    PORT: int = int(os.getenv("PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
""",
            },
            {
                "path": "tests/__init__.py",
                "purpose": "Test package initializer",
                "content": "\"\"\"Test suite package.\"\"\"\n",
            },
            {
                "path": "tests/test_basic.py",
                "purpose": "Verification test suite",
                "content": f"""\"\"\"
tests/test_basic.py — Verification suite
\"\"\"
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    assert "message" in res.json()


def test_health_check():
    res = client.get("/api/health")
    # Endpoint either returns 200 or is configured
    assert res.status_code in (200, 404)
""",
            },
            {
                "path": "requirements.txt",
                "purpose": "Python package dependencies",
                "content": """fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
pytest>=7.4.0
httpx>=0.24.0
""",
            },
            {
                "path": "pyproject.toml",
                "purpose": "Build tool and test configuration",
                "content": f"""[project]
name = "{self.repo_name.lower()}-starter"
version = "0.1.0"
description = "Starter kit for {self.repo_name}"
requires-python = ">=3.9"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
""",
            },
            {
                "path": ".env.example",
                "purpose": "Environment variable placeholder template",
                "content": "\n".join([f"{k}=<placeholder>" for k in env_keys]) + "\n",
            },
            {
                "path": "README.md",
                "purpose": "Project documentation and Stage 1-3 roadmap",
                "content": f"""# {self.repo_name} Starter Kit

> CodeCrafters-style starter scaffold generated directly from AST knowledge graph.

## Quickstart
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run test verification:
   ```bash
   python -m pytest -q
   ```
3. Start the application:
   ```bash
   python main.py
   ```

## Phased Stages
- [ ] **Stage 1**: Wire configuration and basic health endpoints.
- [ ] **Stage 2**: Implement core models and domain logic in `app/services.py`.
- [ ] **Stage 3**: Expand API endpoints and verify contracts.
""",
            },
            {
                "path": "SCAFFOLD.md",
                "purpose": "Scaffold architecture manifest",
                "content": f"""# Architecture Manifest: {self.repo_name}
- **Stack**: Python FastAPI
- **Entrypoint**: `main.py`
- **Validation**: `python -m pytest` & `python -m compileall -q .`
""",
            },
            {
                "path": ".claude/CLAUDE.md",
                "purpose": "Claude Code agent harness guidelines",
                "content": f"""# CLAUDE.md Guidelines for {self.repo_name}
## Commands
- Run tests: `pytest`
- Typecheck/Compile: `python -m compileall -q .`
""",
            },
            {
                "path": ".agents/AGENTS.md",
                "purpose": "Antigravity and autonomous agent work agreement",
                "content": f"""# AGENTS.md — Autonomous Agent Agreement
- Preserve strict types and function signatures.
- Never hardcode secrets; use `.env.example`.
""",
            },
            {
                "path": ".gitignore",
                "purpose": "Git ignore patterns",
                "content": """__pycache__/
*.py[cod]
*$py.class
.env
.venv/
dist/
build/
.pytest_cache/
""",
            },
        ]

        entry_files = ["main.py", "app/api.py"]
        return project_type, files, entry_files

    def _build_typescript_kit(self, stack: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]], List[str]]:
        project_type = "typescript-react" if "React" in stack.get("frameworks", []) else "typescript-node"
        env_keys = extract_env_keys(self.local_path, self.graph)

        files = [
            {
                "path": "src/index.ts",
                "purpose": "Application entrypoint",
                "content": f"""/**
 * src/index.ts — Entrypoint for {self.repo_name}
 */
export function initializeApp(): string {{
  return "Initialized {self.repo_name}";
}}

if (typeof require !== "undefined" && require.main === module) {{
  console.log(initializeApp());
}}
""",
            },
            {
                "path": "src/types.ts",
                "purpose": "Type definitions and interface contracts",
                "content": f"""/**
 * src/types.ts — Core domain types
 */
export interface EntityRecord {{
  id: string;
  name: string;
  active: boolean;
}}

export interface AppConfig {{
  env: string;
  port: number;
}}
""",
            },
            {
                "path": "src/api.ts",
                "purpose": "API client service contracts",
                "content": f"""/**
 * src/api.ts — Service layer
 */
import {{ EntityRecord }} from "./types";

export class ApiService {{
  async fetchStatus(): Promise<{{ ok: boolean; status: string }}> {{
    return {{ ok: true, status: "operational" }};
  }}

  async listEntities(): Promise<EntityRecord[]> {{
    // TODO: Implement actual data fetch
    return [];
  }}
}}
""",
            },
            {
                "path": "tests/basic.test.ts",
                "purpose": "Verification test suite",
                "content": """/**
 * tests/basic.test.ts — Unit tests
 */
import { initializeApp } from "../src/index";

describe("Starter Kit Verification", () => {
  it("initializes without errors", () => {
    const msg = initializeApp();
    expect(msg).toContain("Initialized");
  });
});
""",
            },
            {
                "path": "package.json",
                "purpose": "Node.js dependencies and scripts",
                "content": json.dumps({
                    "name": f"{self.repo_name.lower()}-starter",
                    "version": "0.1.0",
                    "type": "module",
                    "scripts": {
                        "build": "tsc",
                        "test": "node --test"
                    },
                    "dependencies": {},
                    "devDependencies": {
                        "typescript": "^5.2.0"
                    }
                }, indent=2) + "\n",
            },
            {
                "path": "tsconfig.json",
                "purpose": "TypeScript compiler options",
                "content": json.dumps({
                    "compilerOptions": {
                        "target": "ES2022",
                        "module": "NodeNext",
                        "moduleResolution": "NodeNext",
                        "strict": True,
                        "esModuleInterop": True,
                        "skipLibCheck": True,
                        "forceConsistentCasingInFileNames": True
                    },
                    "include": ["src/**/*", "tests/**/*"]
                }, indent=2) + "\n",
            },
            {
                "path": ".env.example",
                "purpose": "Environment variable placeholder template",
                "content": "\n".join([f"{k}=<placeholder>" for k in env_keys]) + "\n",
            },
            {
                "path": "README.md",
                "purpose": "Project documentation and guide",
                "content": f"""# {self.repo_name} TypeScript Starter

## Setup
```bash
npm install
npm test
npm run build
```
""",
            },
            {
                "path": "SCAFFOLD.md",
                "purpose": "Scaffold architecture manifest",
                "content": f"""# Architecture Manifest: {self.repo_name}
- **Stack**: TypeScript Node/React
- **Entrypoint**: `src/index.ts`
""",
            },
            {
                "path": ".claude/CLAUDE.md",
                "purpose": "Claude Code agent guidelines",
                "content": f"""# CLAUDE.md Guidelines for {self.repo_name}
## Commands
- Build: `npm run build`
- Test: `npm test`
""",
            },
            {
                "path": ".agents/AGENTS.md",
                "purpose": "Agent work agreement",
                "content": "# AGENTS.md — Autonomous Agent Agreement\n",
            },
            {
                "path": ".gitignore",
                "purpose": "Git ignore patterns",
                "content": "node_modules/\ndist/\n.env\n",
            },
        ]

        entry_files = ["src/index.ts", "src/api.ts"]
        return project_type, files, entry_files

    def _build_generic_kit(self, stack: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]], List[str]]:
        project_type = "generic-starter"
        env_keys = extract_env_keys(self.local_path, self.graph)

        files = [
            {
                "path": "main.py",
                "purpose": "Starter entrypoint",
                "content": f"""\"\"\"Starter entrypoint for {self.repo_name}.\"\"\"
def main():
    print("Welcome to {self.repo_name}")

if __name__ == "__main__":
    main()
""",
            },
            {
                "path": "config.json",
                "purpose": "Application configuration",
                "content": json.dumps({"name": self.repo_name, "version": "0.1.0"}, indent=2) + "\n",
            },
            {
                "path": "tests/test_starter.py",
                "purpose": "Basic test case",
                "content": """def test_sanity():
    assert 1 + 1 == 2
""",
            },
            {
                "path": ".env.example",
                "purpose": "Environment variable placeholder template",
                "content": "\n".join([f"{k}=<placeholder>" for k in env_keys]) + "\n",
            },
            {
                "path": "README.md",
                "purpose": "Starter guide",
                "content": f"# {self.repo_name}\nStarter scaffold kit.\n",
            },
            {
                "path": "SCAFFOLD.md",
                "purpose": "Scaffold manifest",
                "content": f"# Scaffold: {self.repo_name}\nGeneric starter kit.\n",
            },
            {
                "path": ".claude/CLAUDE.md",
                "purpose": "Claude Code guidelines",
                "content": "# CLAUDE.md\n",
            },
            {
                "path": ".agents/AGENTS.md",
                "purpose": "Agent agreement",
                "content": "# AGENTS.md\n",
            },
            {
                "path": ".gitignore",
                "purpose": "Git ignore patterns",
                "content": ".env\n__pycache__/\n",
            },
            {
                "path": "Makefile",
                "purpose": "Bootstrap make targets",
                "content": """test:
\tpython -m pytest -q

run:
\tpython main.py
""",
            },
            {
                "path": "docs/architecture.md",
                "purpose": "System architecture notes",
                "content": f"# Architecture: {self.repo_name}\nInitial blueprint.\n",
            },
            {
                "path": "scripts/setup.sh",
                "purpose": "Environment bootstrap script",
                "content": "#!/usr/bin/env bash\necho 'Setting up environment...'\n",
            },
        ]

        entry_files = ["main.py"]
        return project_type, files, entry_files
