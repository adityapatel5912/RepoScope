"""
harness_generator.py
Generate exact MCP configuration for the nine supported agents.

The generator is deliberately boring: the registry is a frozen data
structure, the formats are written by small deterministic functions, and
the only writer is `apply_config`. The browser never writes a file, and the
API never calls the network.

Design rules
------------
* Every project-relative path is checked before it is read or written. A
  path that escapes the repository root is rejected, including a symlink
  or junction that resolves outside it.
* Preview never writes. Apply is refused unless
  ``REPOSCOPE_HARNESS_APPLY=1``; an existing file that would change needs a
  diff and ``force: true``.
* JSON and TOML files are merged, not replaced: unrelated keys and servers
  survive. Markdown instruction files get one delimited RepoScope section
  and a second apply is a no-op.
* The five skill descriptors are visible in Phase 3, but the ``SKILL.md``
  bodies belong to Phase 4.

Registry provenance (verified 2026-10-26)
-----------------------------------------
Claude Code     https://docs.claude.com/en/docs/claude-code/mcp
Cursor          https://cursor.com/docs/context/mcp
VS Code         https://code.visualstudio.com/docs/copilot/customization/mcp-servers
Codex CLI       https://developers.openai.com/codex/mcp
Kiro            https://kiro.dev/docs/mcp/configuration/
Antigravity     https://antigravity.google/docs/mcp
Windsurf/Devin  https://docs.windsurf.com/windsurf/cascade/mcp
Cline / Roo     https://docs.cline.bot/mcp/configuring-mcp-servers
                https://docs.roocode.com/features/mcp/using-mcp-in-roo
OpenCode        https://opencode.ai/docs/mcp-servers

The plan's Appendix E was checked against those pages. Three deltas are
intentional and are also reported in ``docs/AGENT_INTEGRATION.md``:

1. OpenCode's current schema uses ``mcp.<name>`` with ``type: local`` or
   ``type: remote``. There is no ``mcp.servers`` key.
2. Devin Desktop (the Windsurf successor) reads the project MCP file at
   ``.devin/mcp_config.json``. The legacy Cascade path remains display-only.
3. Cline's CLI settings live at ``~/.cline/data/settings/...``. The
   project-scoped file written here is Roo Code's ``.roo/mcp.json``.
"""
from __future__ import annotations

import base64
import difflib
import json
import math
import os
import re
import tempfile
import tomllib
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable

#: The stable server name every target should use.
SERVER_NAME = "reposcope"

#: The default Streamable HTTP endpoint exposed by ``reposcope-mcp --http``.
DEFAULT_HTTP_URL = "http://127.0.0.1:8765/mcp"

#: The two markers that delimit the RepoScope section in instruction files.
MARKER_BEGIN = "<!-- reposcope:begin -->"
MARKER_END = "<!-- reposcope:end -->"

#: The stable Phase 1 MCP tool names. Phase 4 adds tools; it does not rename
#: these, so an instruction file written today remains correct.
TOOL_NAMES = (
    "get_architecture_overview",
    "calculate_blast_radius",
    "get_dependency_lineage",
    "explain_architectural_rule",
    "get_repo_map",
    "find_dependency_cycles",
    "get_hotspots",
    "find_unreachable_symbols",
)

RESOURCE_URIS = (
    "reposcope://graph/summary",
    "reposcope://hotspots",
    "reposcope://repo-map",
    "reposcope://dead-code",
    "reposcope://cycles",
)

SUPPORTED_TRANSPORTS = ("stdio", "http")


class HarnessError(Exception):
    """An error the API can translate into a precise HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class FileSpec:
    """One file the generator would write for an agent."""

    path: str
    fmt: str  # "json", "toml", or "markdown"
    kind: str  # "mcp_json", "mcp_toml", or "instructions"
    root_key: str = ""
    frontmatter: str = ""


@dataclass(frozen=True)
class AgentSpec:
    """One agent target in the frozen registry."""

    id: str
    label: str
    config_paths: tuple[str, ...]
    files: tuple[FileSpec, ...]
    transport: tuple[str, ...]
    default_transport: str
    global_preview_paths: tuple[str, ...]
    docs_url: str
    verified_at: str
    notes: tuple[str, ...]
    command_kind: str
    command_note: str


def _json_file(path: str, root_key: str) -> FileSpec:
    return FileSpec(path=path, fmt="json", kind="mcp_json", root_key=root_key)


def _toml_file(path: str) -> FileSpec:
    return FileSpec(path=path, fmt="toml", kind="mcp_toml")


def _markdown_file(path: str, frontmatter: str = "") -> FileSpec:
    return FileSpec(path=path, fmt="markdown", kind="instructions", frontmatter=frontmatter)


CLAUDE = AgentSpec(
    id="claude",
    label="Claude Code",
    config_paths=(".mcp.json", "CLAUDE.md"),
    files=(
        _json_file(".mcp.json", "mcpServers"),
        _markdown_file("CLAUDE.md"),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=(),
    docs_url="https://docs.claude.com/en/docs/claude-code/mcp",
    verified_at="2026-10-26",
    notes=(
        "Project scope is .mcp.json; the CLI needs --scope project.",
        "A JSON entry with a url and no type is treated as stdio by Claude Code.",
    ),
    command_kind="install",
    command_note="Writes the project-scoped .mcp.json. Review the diff before running it.",
)

CURSOR = AgentSpec(
    id="cursor",
    label="Cursor",
    config_paths=(".cursor/mcp.json", ".cursor/rules/reposcope.mdc"),
    files=(
        _json_file(".cursor/mcp.json", "mcpServers"),
        _markdown_file(
            ".cursor/rules/reposcope.mdc",
            "---\ndescription: RepoScope code intelligence for this repository\nalwaysApply: true\n---\n",
        ),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=(),
    docs_url="https://cursor.com/docs/context/mcp",
    verified_at="2026-10-26",
    notes=(
        "Project config is .cursor/mcp.json.",
        "The preview includes Cursor's documented install link.",
    ),
    command_kind="deeplink",
    command_note="Cursor install link; it encodes the same server entry shown below.",
)

VSCODE = AgentSpec(
    id="vscode",
    label="VS Code / Copilot",
    config_paths=(".vscode/mcp.json", ".github/copilot-instructions.md"),
    files=(
        _json_file(".vscode/mcp.json", "servers"),
        _markdown_file(".github/copilot-instructions.md"),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=(),
    docs_url="https://code.visualstudio.com/docs/copilot/customization/mcp-servers",
    verified_at="2026-10-26",
    notes=(
        ".vscode/mcp.json uses the servers key and requires type.",
        "Portable workspace-root .mcp.json uses mcpServers; this target writes the VS Code shape.",
    ),
    command_kind="install",
    command_note="`code --add-mcp` writes your user profile; Apply writes the project file below.",
)

CODEX = AgentSpec(
    id="codex",
    label="Codex CLI",
    config_paths=(".codex/config.toml", "AGENTS.md"),
    files=(
        _toml_file(".codex/config.toml"),
        _markdown_file("AGENTS.md"),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=("~/.codex/config.toml",),
    docs_url="https://developers.openai.com/codex/mcp",
    verified_at="2026-10-26",
    notes=(
        "Codex reads a project .codex/config.toml only in trusted projects.",
        "The table is [mcp_servers.reposcope].",
    ),
    command_kind="install",
    command_note="`codex mcp add` writes the user-level config; Apply writes the project file below.",
)

KIRO = AgentSpec(
    id="kiro",
    label="Kiro",
    config_paths=(".kiro/settings/mcp.json", ".kiro/steering/reposcope.md"),
    files=(
        _json_file(".kiro/settings/mcp.json", "mcpServers"),
        _markdown_file(".kiro/steering/reposcope.md"),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=("~/.kiro/settings/mcp.json",),
    docs_url="https://kiro.dev/docs/mcp/configuration/",
    verified_at="2026-10-26",
    notes=("Workspace config is .kiro/settings/mcp.json.",),
    command_kind="server",
    command_note="Kiro has no verified project-scoped installer; use the file below or start the server with this command.",
)

ANTIGRAVITY = AgentSpec(
    id="antigravity",
    label="Antigravity",
    config_paths=(".agents/mcp_config.json", "AGENTS.md"),
    files=(
        _json_file(".agents/mcp_config.json", "mcpServers"),
        _markdown_file("AGENTS.md"),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=("~/.gemini/config/mcp_config.json",),
    docs_url="https://antigravity.google/docs/mcp",
    verified_at="2026-10-26",
    notes=(
        "The workspace file is .agents/mcp_config.json.",
        "Writes five RepoScope skills to .agents/skills/<id>/SKILL.md.",
    ),
    command_kind="server",
    command_note="Antigravity installs through its /mcp manager or the file below; start the server with this command.",
)

WINDSURF = AgentSpec(
    id="windsurf",
    label="Windsurf / Devin",
    config_paths=(".devin/mcp_config.json", ".windsurf/rules/reposcope.md"),
    files=(
        _json_file(".devin/mcp_config.json", "mcpServers"),
        _markdown_file(".windsurf/rules/reposcope.md"),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=(
        "~/.codeium/windsurf/mcp_config.json",
        "~/.config/devin/mcp_config.json",
    ),
    docs_url="https://docs.windsurf.com/windsurf/cascade/mcp",
    verified_at="2026-10-26",
    notes=(
        "Devin Desktop reads the project MCP file at .devin/mcp_config.json.",
        "The legacy Cascade global path is display-only and is never written.",
        "Project rules use the .windsurf/rules/*.md fallback path.",
    ),
    command_kind="server",
    command_note="Windsurf/Devin has no verified project-scoped installer; use the file below or start the server with this command.",
)

CLINE = AgentSpec(
    id="cline",
    label="Cline / Roo",
    config_paths=(".roo/mcp.json", ".clinerules"),
    files=(
        _json_file(".roo/mcp.json", "mcpServers"),
        _markdown_file(".clinerules"),
    ),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=("~/.cline/data/settings/cline_mcp_settings.json",),
    docs_url="https://docs.cline.bot/mcp/configuring-mcp-servers",
    verified_at="2026-10-26",
    notes=(
        "Roo Code reads the project file at .roo/mcp.json.",
        "Cline's global settings file is display-only and is never written by default.",
    ),
    command_kind="server",
    command_note="Cline's CLI writes global settings; Apply writes Roo's project file below.",
)

OPENCODE = AgentSpec(
    id="opencode",
    label="OpenCode",
    config_paths=("opencode.json",),
    files=(_json_file("opencode.json", "mcp"),),
    transport=SUPPORTED_TRANSPORTS,
    default_transport="stdio",
    global_preview_paths=("~/.config/opencode/opencode.json",),
    docs_url="https://opencode.ai/docs/mcp-servers",
    verified_at="2026-10-26",
    notes=(
        "Current OpenCode schema is mcp.<name> with type local or remote.",
        "There is no mcp.servers key in the current schema.",
    ),
    command_kind="install",
    command_note="`opencode mcp add` writes the project opencode.json by default.",
)

AGENTS: tuple[AgentSpec, ...] = (
    CLAUDE,
    CURSOR,
    VSCODE,
    CODEX,
    KIRO,
    ANTIGRAVITY,
    WINDSURF,
    CLINE,
    OPENCODE,
)

AGENTS_BY_ID = {agent.id: agent for agent in AGENTS}


SKILLS: tuple[dict[str, Any], ...] = (
    {
        "id": "blast-radius-guard",
        "label": "Blast Radius Guard",
        "description": "Check direct and transitive dependents before changing a file or symbol.",
        "targets": ["claude", "antigravity"],
        "files": [
            ".claude/skills/blast-radius-guard/SKILL.md",
            ".agents/skills/blast-radius-guard/SKILL.md",
        ],
    },
    {
        "id": "zero-grep-architect",
        "label": "Zero-Grep Architect",
        "description": "Answer architecture and ownership questions from the graph instead of grep.",
        "targets": ["claude", "antigravity"],
        "files": [
            ".claude/skills/zero-grep-architect/SKILL.md",
            ".agents/skills/zero-grep-architect/SKILL.md",
        ],
    },
    {
        "id": "pr-contract-shield",
        "label": "PR Contract Shield",
        "description": "Check interface contracts and cross-layer imports before opening a pull request.",
        "targets": ["claude", "antigravity"],
        "files": [
            ".claude/skills/pr-contract-shield/SKILL.md",
            ".agents/skills/pr-contract-shield/SKILL.md",
        ],
    },
    {
        "id": "onboarding-navigator",
        "label": "Onboarding Navigator",
        "description": "Build a ranked reading path through an unfamiliar repository.",
        "targets": ["claude", "antigravity"],
        "files": [
            ".claude/skills/onboarding-navigator/SKILL.md",
            ".agents/skills/onboarding-navigator/SKILL.md",
        ],
    },
    {
        "id": "dead-code-surgeon",
        "label": "Dead Code Surgeon",
        "description": "Find unreachable symbols with evidence, then remove them safely.",
        "targets": ["claude", "antigravity"],
        "files": [
            ".claude/skills/dead-code-surgeon/SKILL.md",
            ".agents/skills/dead-code-surgeon/SKILL.md",
        ],
    },
)


# ── Public registry ─────────────────────────────────────────────────────────


def apply_enabled() -> bool:
    """Writes are off unless the server operator explicitly enables them."""
    return os.getenv("REPOSCOPE_HARNESS_APPLY") == "1"


def http_url() -> str:
    """The Streamable HTTP endpoint the generated configs point at."""
    configured = os.getenv("REPOSCOPE_MCP_HTTP_URL") or DEFAULT_HTTP_URL
    return configured.rstrip("/")


def list_agents() -> dict[str, Any]:
    """The registry payload consumed by the UI."""
    return {
        "agents": [
            {
                "id": agent.id,
                "label": agent.label,
                "config_paths": list(agent.config_paths),
                "transport": list(agent.transport),
                "default_transport": agent.default_transport,
                "global_preview_paths": list(agent.global_preview_paths),
                "docs_url": agent.docs_url,
                "verified_at": agent.verified_at,
                "notes": list(agent.notes),
            }
            for agent in AGENTS
        ],
        "apply_enabled": apply_enabled(),
    }


def list_skills() -> dict[str, Any]:
    """The five canonical skill descriptors and bodies."""
    import skill_library

    return {
        "skills": [
            {
                **skill,
                "content": skill_library.skill_body(skill["id"]),
                "content_available": True,
            }
            for skill in SKILLS
        ],
        "content_available": True,
    }


# ── Root and path safety ────────────────────────────────────────────────────


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _looks_absolute(path: str) -> bool:
    if Path(path).is_absolute():
        return True
    # On POSIX, a Windows drive path is not absolute to pathlib. Reject it
    # anyway; it is never a project-relative config path.
    if re.match(r"^[A-Za-z]:[\\/]", path):
        return True
    return path.startswith("\\\\") or path.startswith("//")


def resolve_config_path(root: Path, relpath: str) -> Path:
    """
    Resolve a project-relative config path, refusing every escape.

    The registry only contains constants, but this function is the guard
    that a future registry change (or a test) cannot walk around. It
    rejects absolute paths, ``..``, and a symlink or junction whose real
    target is outside the root.
    """
    if not relpath or _looks_absolute(relpath):
        raise HarnessError(400, f"Unsafe config path: {relpath!r}")

    relative = Path(relpath)
    if any(part == ".." for part in relative.parts):
        raise HarnessError(400, f"Unsafe config path: {relpath!r}")

    root_resolved = root.resolve()
    target = root / relative
    parent_resolved = target.parent.resolve(strict=False)
    if not _is_within(parent_resolved, root_resolved):
        raise HarnessError(400, f"Config path escapes the repository root: {relpath}")

    if target.exists():
        if target.is_dir():
            raise HarnessError(400, f"Config path is a directory, not a file: {relpath}")
        target_resolved = target.resolve()
        if not _is_within(target_resolved, root_resolved):
            raise HarnessError(400, f"Config path escapes the repository root: {relpath}")

    return target


def resolve_root(root: str | None) -> Path:
    """
    Resolve an explicit root or the active local repository.

    A root is required when no repository is loaded. The path must be an
    existing absolute directory; a relative path is never interpreted
    against the server's current directory.
    """
    candidate = root
    if candidate is None:
        from orchestrator import current_graph

        _graph, active = current_graph()
        if not active:
            raise HarnessError(
                400,
                "A local repository root is required. Load a local folder first.",
            )
        candidate = str(active)

    if not candidate or not str(candidate).strip():
        raise HarnessError(400, "A local repository root is required.")

    path = Path(candidate).expanduser()
    if not _looks_absolute(str(path)):
        raise HarnessError(400, f"Root must be an absolute path: {candidate}")

    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise HarnessError(400, f"Root does not exist: {candidate}") from exc

    if not resolved.is_dir():
        raise HarnessError(400, f"Root is not a directory: {candidate}")

    return resolved


# ── Transport-specific MCP entries ─────────────────────────────────────────


def _stdio_entry(agent: AgentSpec, root: str) -> dict[str, Any]:
    command = "reposcope-mcp"
    args = ["--root", root]
    if agent.id == "opencode":
        return {"type": "local", "command": [command, *args], "enabled": True}
    entry: dict[str, Any] = {"command": command, "args": args}
    if agent.id in {"cursor", "vscode"}:
        entry["type"] = "stdio"
    return entry


def _http_entry(agent: AgentSpec) -> dict[str, Any]:
    url = http_url()
    if agent.id == "opencode":
        return {"type": "remote", "url": url, "enabled": True}
    if agent.id == "antigravity":
        return {"serverUrl": url}
    if agent.id == "vscode":
        return {"type": "http", "url": url}
    if agent.id == "claude":
        return {"type": "http", "url": url}
    if agent.id == "cline":
        # Roo Code's Streamable HTTP type is hyphenated.
        return {"type": "streamable-http", "url": url}
    return {"url": url}


def _entry(agent: AgentSpec, transport: str, root: str) -> dict[str, Any]:
    if transport == "stdio":
        return _stdio_entry(agent, root)
    if transport == "http":
        return _http_entry(agent)
    raise HarnessError(
        400,
        f"Unsupported transport {transport!r} for {agent.label}. "
        f"Supported: {', '.join(agent.transport)}.",
    )


# ── Commands ───────────────────────────────────────────────────────────────


def _cursor_deeplink(entry: dict[str, Any]) -> str:
    payload = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    query = urllib.parse.urlencode({"name": SERVER_NAME, "config": encoded})
    return f"cursor://anysphere.cursor-deeplink/mcp/install?{query}"


def _code_add_mcp(entry: dict[str, Any]) -> str:
    payload = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)
    # Single quotes are the Windows PowerShell and POSIX-shell form that
    # survives the embedded double quotes. A JSON payload never contains a
    # single quote unless a path does; escape it for those rare paths.
    return "code --add-mcp '" + payload.replace("'", "'\\''") + "'"


def _shell_arg(value: str) -> str:
    """
    Quote a repository path for the command line shown to the user.

    A checkout path routinely contains spaces ("D:\\Hackathon Projects\\…").
    Leaving it bare made the "copy-pasteable" command split at the first
    space. Double quotes are accepted by PowerShell, cmd.exe, and POSIX
    shells; Windows paths cannot contain a double quote.
    """
    return '"' + value.replace('"', '""') + '"'


def build_command(agent: AgentSpec, transport: str, root: str) -> str:
    """The exact copy-paste command shown with a preview."""
    url = http_url()
    quoted_root = _shell_arg(root)

    if agent.id == "claude":
        if transport == "http":
            return (
                "claude mcp add --scope project --transport http "
                f"{SERVER_NAME} {url}"
            )
        return (
            "claude mcp add --scope project --transport stdio "
            f"{SERVER_NAME} -- reposcope-mcp --root {quoted_root}"
        )

    if agent.id == "cursor":
        return _cursor_deeplink(_entry(agent, transport, root))

    if agent.id == "vscode":
        entry = {"name": SERVER_NAME, **_entry(agent, transport, root)}
        return _code_add_mcp(entry)

    if agent.id == "codex":
        if transport == "http":
            # The Codex CLI's HTTP add syntax is not stable enough to
            # promise here. The server command is always correct.
            return f"reposcope-mcp --http --root {quoted_root}"
        return f"codex mcp add {SERVER_NAME} -- reposcope-mcp --root {quoted_root}"

    if agent.id == "opencode":
        if transport == "http":
            return f"opencode mcp add {SERVER_NAME} --url {url}"
        return f"opencode mcp add {SERVER_NAME} -- reposcope-mcp --root {quoted_root}"

    if transport == "http":
        return f"reposcope-mcp --http --root {quoted_root}"
    return f"reposcope-mcp --root {quoted_root}"


# ── JSON and TOML merging ──────────────────────────────────────────────────


def _clean_transport_keys(current: dict[str, Any], transport: str) -> dict[str, Any]:
    """
    Drop keys that belong to the other transport before merging.

    The point is that switching an existing entry from stdio to HTTP must
    not leave a ``command`` beside a ``url``; some clients reject the
    mixed shape, and the user asked for the other transport.
    """
    cleaned = dict(current)
    cleaned.pop("type", None)
    if transport == "stdio":
        for key in ("url", "serverUrl", "headers"):
            cleaned.pop(key, None)
    else:
        for key in ("command", "args", "env", "cwd", "environment"):
            cleaned.pop(key, None)
    return cleaned


def _merge_entry(
    current: Any, entry: dict[str, Any], transport: str
) -> dict[str, Any]:
    if isinstance(current, dict):
        return {**_clean_transport_keys(current, transport), **entry}
    return dict(entry)


def _new_json_content(root_key: str, entry: dict[str, Any]) -> str:
    return json.dumps({root_key: {SERVER_NAME: entry}}, indent=2, ensure_ascii=False) + "\n"


def _merge_json(
    existing: str,
    file_spec: FileSpec,
    entry: dict[str, Any],
    transport: str,
) -> tuple[str, list[str], bool]:
    """Return (content, warnings, unparseable)."""
    path = file_spec.path
    try:
        data = json.loads(existing)
    except json.JSONDecodeError as exc:
        return (
            _new_json_content(file_spec.root_key, entry),
            [
                f"{path} is not valid JSON ({exc.msg}); force is required to replace it."
            ],
            True,
        )

    if not isinstance(data, dict):
        return (
            _new_json_content(file_spec.root_key, entry),
            [f"{path} is valid JSON but not an object; force is required to replace it."],
            True,
        )

    warnings: list[str] = []
    container = data.get(file_spec.root_key)
    if container is None:
        container = {}
        data[file_spec.root_key] = container
    elif not isinstance(container, dict):
        warnings.append(
            f"{path} has a non-object {file_spec.root_key!r} value; "
            "force is required to replace it."
        )
        container = {}
        data[file_spec.root_key] = container

    current = container.get(SERVER_NAME)
    container[SERVER_NAME] = _merge_entry(current, entry, transport)

    if file_spec.root_key == "mcp" and "servers" in container:
        warnings.append(
            "The existing opencode.json has an `mcp.servers` key; current "
            "OpenCode uses `mcp.<name>`. RepoScope added `mcp.reposcope` and "
            "left the old key untouched."
        )

    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return content, warnings, False


def _toml_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    return json.dumps(key, ensure_ascii=False)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, list):
        if any(isinstance(item, dict) for item in value):
            raise TypeError("A list of tables must be emitted as [table] blocks")
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{ "
            + ", ".join(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items())
            + " }"
        )
    raise TypeError(f"Unsupported TOML value: {value!r}")


def _toml_dump(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def blank() -> None:
        if lines and lines[-1] != "":
            lines.append("")

    def emit_table(table: dict[str, Any], path: list[str], header: bool) -> None:
        scalar_items: list[tuple[str, Any]] = []
        table_items: list[tuple[str, Any]] = []
        array_items: list[tuple[str, list[dict[str, Any]]]] = []

        for key, value in table.items():
            if isinstance(value, dict):
                table_items.append((key, value))
            elif isinstance(value, list) and value and all(
                isinstance(item, dict) for item in value
            ):
                array_items.append((key, value))
            elif value is None:
                continue
            else:
                scalar_items.append((key, value))

        # A table whose only content is child tables needs no header of
        # its own; TOML implies the parent from `[a.b]`. Emitting it
        # anyway produces a noisy empty `[mcp_servers]` block.
        if header and scalar_items:
            blank()
            lines.append("[" + ".".join(_toml_key(part) for part in path) + "]")
        elif header and not scalar_items and not table_items and not array_items:
            blank()
            lines.append("[" + ".".join(_toml_key(part) for part in path) + "]")

        for key, value in scalar_items:
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")

        for key, value in table_items:
            emit_table(value, [*path, key], header=True)

        for key, values in array_items:
            for item in values:
                blank()
                lines.append(
                    "[[" + ".".join(_toml_key(part) for part in [*path, key]) + "]]"
                )
                emit_table(item, [*path, key], header=False)

    emit_table(data, [], header=False)
    return "\n".join(lines).rstrip() + "\n"


def _new_toml_content(entry: dict[str, Any]) -> str:
    return _toml_dump({"mcp_servers": {SERVER_NAME: entry}})


def _merge_toml(
    existing: str,
    file_spec: FileSpec,
    entry: dict[str, Any],
    transport: str,
) -> tuple[str, list[str], bool]:
    path = file_spec.path
    try:
        data = tomllib.loads(existing)
    except tomllib.TOMLDecodeError as exc:
        return (
            _new_toml_content(entry),
            [
                f"{path} is not valid TOML ({exc}); force is required to replace it."
            ],
            True,
        )

    if not isinstance(data, dict):
        return (
            _new_toml_content(entry),
            [f"{path} is not a TOML table; force is required to replace it."],
            True,
        )

    warnings: list[str] = []
    if "#" in existing:
        warnings.append(
            f"{path} contains TOML comments; merging re-serializes the file and "
            "does not preserve them."
        )

    servers = data.get("mcp_servers")
    if servers is None:
        servers = {}
        data["mcp_servers"] = servers
    elif not isinstance(servers, dict):
        warnings.append(
            f"{path} has a non-table mcp_servers value; force is required to replace it."
        )
        servers = {}
        data["mcp_servers"] = servers

    servers[SERVER_NAME] = _merge_entry(servers.get(SERVER_NAME), entry, transport)
    return _toml_dump(data), warnings, False


# ── Markdown instruction files ─────────────────────────────────────────────


def _markdown_section(root: str) -> str:
    tools = ", ".join(f"`{name}`" for name in TOOL_NAMES)
    resources = ", ".join(f"`{uri}`" for uri in RESOURCE_URIS)
    return (
        f"{MARKER_BEGIN}\n"
        "## RepoScope\n\n"
        "RepoScope indexes this repository and exposes the graph over the "
        "`reposcope` MCP server. Prefer the graph over grep for architecture, "
        "callers, impact, and dead-code questions.\n\n"
        f"- Server: `{SERVER_NAME}`\n"
        f"- Root: `{root}`\n"
        "- Transport: see this agent's MCP config file.\n"
        f"- Tools: {tools}.\n"
        f"- Resources: {resources}.\n"
        f"{MARKER_END}\n"
    )


def _new_markdown_content(file_spec: FileSpec, root: str) -> str:
    section = _markdown_section(root)
    if file_spec.frontmatter:
        return file_spec.frontmatter.rstrip("\n") + "\n\n" + section
    return section


_MARKDOWN_BLOCK = re.compile(
    re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END),
    re.DOTALL,
)


def _merge_markdown(existing: str, file_spec: FileSpec, root: str) -> str:
    section = _markdown_section(root)
    if _MARKDOWN_BLOCK.search(existing):
        # A replacement function, not a string: the section contains the
        # absolute root, and on Windows its backslashes would be read as
        # regex escapes (``\U`` fails outright).
        merged = _MARKDOWN_BLOCK.sub(lambda _match: section.rstrip("\n"), existing, count=1)
        return merged if merged.endswith("\n") else merged + "\n"

    base = existing.rstrip()
    if not base:
        return _new_markdown_content(file_spec, root)
    return base + "\n\n" + section


# ── Preview ────────────────────────────────────────────────────────────────


def _read_existing(target: Path) -> tuple[str | None, bool]:
    """
    Return (text, unparseable).

    A missing file is (None, False). A directory, a binary file, or any
    read error is (None, True), which forces an explicit replacement.
    """
    if not target.exists():
        return None, False
    try:
        return target.read_text(encoding="utf-8"), False
    except (OSError, UnicodeDecodeError):
        return None, True


def _diff(path: str, existing: str, content: str) -> str | None:
    if existing == content:
        return None
    return "".join(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def build_preview(
    agent_id: str,
    transport: str = "stdio",
    root: str | None = None,
) -> dict[str, Any]:
    """Build a preview. This function never writes a file."""
    agent = AGENTS_BY_ID.get(agent_id)
    if agent is None:
        known = ", ".join(agent.id for agent in AGENTS)
        raise HarnessError(400, f"Unknown agent {agent_id!r}. Known agents: {known}.")
    if transport not in agent.transport:
        raise HarnessError(
            400,
            f"Unsupported transport {transport!r} for {agent.label}. "
            f"Supported: {', '.join(agent.transport)}.",
        )

    resolved_root = resolve_root(root)
    root_text = str(resolved_root)
    entry = _entry(agent, transport, root_text)
    warnings: list[str] = []
    files: list[dict[str, Any]] = []
    requires_force = False

    if agent.global_preview_paths:
        warnings.append(
            "Global paths are display-only and are never written: "
            + ", ".join(agent.global_preview_paths)
        )

    for file_spec in agent.files:
        target = resolve_config_path(resolved_root, file_spec.path)
        existing, unparseable = _read_existing(target)
        exists = target.exists()

        if existing is None:
            content = (
                _new_json_content(file_spec.root_key, entry)
                if file_spec.kind == "mcp_json"
                else _new_toml_content(entry)
                if file_spec.kind == "mcp_toml"
                else _new_markdown_content(file_spec, root_text)
            )
            if unparseable:
                warnings.append(
                    f"{file_spec.path} exists but cannot be read as UTF-8 text; "
                    "force is required to replace it."
                )
            diff = None
        else:
            if file_spec.kind == "mcp_json":
                content, merge_warnings, unparseable = _merge_json(
                    existing, file_spec, entry, transport
                )
            elif file_spec.kind == "mcp_toml":
                content, merge_warnings, unparseable = _merge_toml(
                    existing, file_spec, entry, transport
                )
            else:
                content = _merge_markdown(existing, file_spec, root_text)
                merge_warnings = []
            warnings.extend(merge_warnings)
            diff = _diff(file_spec.path, existing, content)

        changed = (not exists) or existing != content
        needs_force = exists and changed
        requires_force = requires_force or needs_force

        files.append(
            {
                "path": file_spec.path,
                "format": file_spec.fmt,
                "content": content,
                "exists": exists,
                "diff": diff,
                "will_write": changed,
            }
        )

    if agent.id in ("claude", "antigravity"):
        import skill_library

        for skill_id in skill_library.SKILL_IDS:
            if agent.id == "claude":
                skill_path = f".claude/skills/{skill_id}/SKILL.md"
            else:
                skill_path = f".agents/skills/{skill_id}/SKILL.md"

            target = resolve_config_path(resolved_root, skill_path)
            existing, unparseable = _read_existing(target)
            exists = target.exists()
            canonical = skill_library.skill_body(skill_id)
            norm_content = canonical.replace("\r\n", "\n").rstrip("\n") + "\n"

            if existing is None:
                if unparseable:
                    warnings.append(
                        f"{skill_path} exists but cannot be read as UTF-8 text; "
                        "force is required to replace it."
                    )
                content = norm_content
                diff = None
                changed = True
            else:
                content = norm_content
                existing_norm = existing.replace("\r\n", "\n")
                if existing_norm != norm_content:
                    changed = True
                    diff = _diff(skill_path, existing, norm_content)
                else:
                    changed = False
                    diff = None

            needs_force = exists and changed
            requires_force = requires_force or needs_force

            files.append(
                {
                    "path": skill_path,
                    "format": "markdown",
                    "content": content,
                    "exists": exists,
                    "diff": diff,
                    "will_write": changed,
                }
            )

    return {
        "ok": True,
        "agent": agent.id,
        "label": agent.label,
        "transport": transport,
        "root": root_text,
        "command": build_command(agent, transport, root_text),
        "command_kind": agent.command_kind,
        "command_note": agent.command_note,
        "apply_enabled": apply_enabled(),
        "requires_force": requires_force,
        "files": files,
        "warnings": warnings,
    }


# ── Apply ──────────────────────────────────────────────────────────────────


def _atomic_write(target: Path, content: str) -> None:
    """Write a file atomically inside its own directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def apply_config(
    agent_id: str,
    transport: str,
    root: str | None,
    *,
    apply: bool,
    force: bool,
) -> dict[str, Any]:
    """
    Return a dry run or write the previewed files.

    ``apply: false`` is always a dry run. ``apply: true`` is refused with
    403 when the server flag is off, and 409 when an existing file would
    change and ``force`` is false.
    """
    preview = build_preview(agent_id, transport, root)
    if not apply:
        return {
            **preview,
            "apply": False,
            "applied": [],
            "unchanged": [],
        }

    if not preview["apply_enabled"]:
        raise HarnessError(
            403,
            "Writes are disabled. Set REPOSCOPE_HARNESS_APPLY=1 on the server "
            "to enable them.",
        )

    if preview["requires_force"] and not force:
        changed = [f["path"] for f in preview["files"] if f["will_write"] and f["exists"]]
        raise HarnessError(
            409,
            "Existing files would change and force is false: "
            + ", ".join(changed)
            + ". Review the diff and retry with force=true.",
        )

    resolved_root = Path(preview["root"])
    applied: list[str] = []
    unchanged: list[str] = []

    for file in preview["files"]:
        if not file["will_write"]:
            unchanged.append(file["path"])
            continue
        target = resolve_config_path(resolved_root, file["path"])
        _atomic_write(target, file["content"])
        applied.append(file["path"])

    return {
        **preview,
        "apply": True,
        "applied": applied,
        "unchanged": unchanged,
    }
