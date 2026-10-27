"""
test_harness_generator.py
L2 tests for the Phase 3 nine-agent harness generator.

The generator is a data registry plus four deterministic writers:

* the registry is frozen and every target has a verified provenance date;
* preview never touches the filesystem;
* writes are refused unless REPOSCOPE_HARNESS_APPLY=1;
* an existing file that would change needs `force`, and JSON/TOML merges
  preserve unrelated keys;
* a path that escapes the repository root is rejected, including a
  symlink or Windows junction.
"""
from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

import harness_generator as H

EXPECTED_IDS = [
    "claude",
    "cursor",
    "vscode",
    "codex",
    "kiro",
    "antigravity",
    "windsurf",
    "cline",
    "opencode",
]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def _apply_flag_off(monkeypatch):
    monkeypatch.delenv("REPOSCOPE_HARNESS_APPLY", raising=False)
    monkeypatch.delenv("REPOSCOPE_MCP_HTTP_URL", raising=False)


def _snapshot(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def _json_file(preview: dict, path: str) -> dict:
    item = next(file for file in preview["files"] if file["path"] == path)
    return json.loads(item["content"])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


# ── Registry ────────────────────────────────────────────────────────────────


def test_registry_has_the_nine_targets_with_provenance():
    assert [agent.id for agent in H.AGENTS] == EXPECTED_IDS
    assert [agent.id for agent in H.AGENTS] == list(H.AGENTS_BY_ID)
    assert len({agent.label for agent in H.AGENTS}) == 9

    for agent in H.AGENTS:
        assert agent.verified_at == "2026-10-26"
        assert agent.docs_url.startswith("https://")
        assert agent.transport == ("stdio", "http")
        assert agent.default_transport == "stdio"
        assert agent.config_paths
        assert len(agent.config_paths) == len(agent.files)


def test_registry_paths_are_project_relative_and_mcp_paths_are_unique():
    mcp_paths: list[str] = []
    for agent in H.AGENTS:
        for path in agent.config_paths:
            assert not Path(path).is_absolute()
            assert ".." not in Path(path).parts
        # Codex and Antigravity intentionally share AGENTS.md; the MCP
        # config files are what must never collide.
        mcp_paths.extend(
            spec.path
            for spec in agent.files
            if spec.kind in {"mcp_json", "mcp_toml"}
        )
    assert len(mcp_paths) == len(set(mcp_paths))
    assert H.AGENTS_BY_ID["codex"].config_paths[-1] == "AGENTS.md"
    assert H.AGENTS_BY_ID["antigravity"].config_paths[-1] == "AGENTS.md"


def test_agents_payload_matches_the_contract():
    payload = H.list_agents()
    assert payload["apply_enabled"] is False
    assert len(payload["agents"]) == 9
    claude = next(agent for agent in payload["agents"] if agent["id"] == "claude")
    assert claude["label"] == "Claude Code"
    assert claude["config_paths"] == [".mcp.json", "CLAUDE.md"]
    assert claude["transport"] == ["stdio", "http"]
    assert claude["default_transport"] == "stdio"
    assert claude["global_preview_paths"] == []
    assert claude["verified_at"] == "2026-10-26"


# ── Preview ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent", [agent.id for agent in H.AGENTS])
@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_every_target_previews_both_transports_without_writing(repo, agent, transport):
    before = _snapshot(repo)
    preview = H.build_preview(agent, transport, str(repo))
    after = _snapshot(repo)

    assert before == after
    assert preview["ok"] is True
    assert preview["agent"] == agent
    assert preview["transport"] == transport
    assert preview["root"] == str(repo.resolve())
    assert preview["apply_enabled"] is False
    assert preview["command"]
    assert len(preview["files"]) == len(H.AGENTS_BY_ID[agent].files)
    assert {item["format"] for item in preview["files"]} <= {"json", "toml", "markdown"}
    assert all(item["exists"] is False for item in preview["files"])
    assert all(item["diff"] is None for item in preview["files"])
    assert all(item["will_write"] is True for item in preview["files"])


def test_stdio_entries_point_at_the_entry_point_and_the_root(repo):
    for agent in H.AGENTS:
        preview = H.build_preview(agent.id, "stdio", str(repo))
        json_files = [item for item in preview["files"] if item["format"] == "json"]
        if not json_files:
            continue
        data = json.loads(json_files[0]["content"])
        if agent.id == "opencode":
            entry = data["mcp"]["reposcope"]
            assert entry["type"] == "local"
            assert entry["command"][0] == "reposcope-mcp"
            assert entry["command"][1] == "--root"
            assert entry["command"][2] == str(repo.resolve())
        else:
            entry = next(iter(data.values()))["reposcope"]
            assert entry["command"] == "reposcope-mcp"
            assert entry["args"] == ["--root", str(repo.resolve())]


def test_http_entries_use_streamable_http_shapes(repo):
    for agent in H.AGENTS:
        preview = H.build_preview(agent.id, "http", str(repo))
        json_files = [item for item in preview["files"] if item["format"] == "json"]
        if not json_files:
            continue
        data = json.loads(json_files[0]["content"])

        if agent.id == "opencode":
            entry = data["mcp"]["reposcope"]
            assert entry["type"] == "remote"
            assert entry["url"] == H.DEFAULT_HTTP_URL
        elif agent.id == "antigravity":
            entry = data["mcpServers"]["reposcope"]
            assert entry["serverUrl"] == H.DEFAULT_HTTP_URL
        elif agent.id in {"vscode", "claude"}:
            entry = next(iter(data.values()))["reposcope"]
            assert entry["type"] == "http"
            assert entry["url"] == H.DEFAULT_HTTP_URL
        elif agent.id == "cline":
            entry = data["mcpServers"]["reposcope"]
            assert entry["type"] == "streamable-http"
            assert entry["url"] == H.DEFAULT_HTTP_URL
        else:
            entry = next(iter(data.values()))["reposcope"]
            assert entry["url"] == H.DEFAULT_HTTP_URL


def test_http_url_can_be_overridden(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_MCP_HTTP_URL", "http://127.0.0.1:9999/mcp/")
    preview = H.build_preview("claude", "http", str(repo))
    entry = _json_file(preview, ".mcp.json")["mcpServers"]["reposcope"]
    assert entry["url"] == "http://127.0.0.1:9999/mcp"
    assert preview["command"].endswith("http://127.0.0.1:9999/mcp")


def test_codex_merges_a_toml_table_and_warns_about_comments(repo):
    config = repo / ".codex" / "config.toml"
    _write(
        config,
        '# my settings\nmodel = "gpt-5"\n\n'
        '[mcp_servers.other]\ncommand = "other-mcp"\nargs = ["--x"]\n',
    )
    preview = H.build_preview("codex", "stdio", str(repo))
    toml_file = next(item for item in preview["files"] if item["path"] == ".codex/config.toml")

    assert preview["requires_force"] is True
    assert toml_file["diff"] is not None
    assert any("comments" in warning for warning in preview["warnings"])

    data = tomllib.loads(toml_file["content"])
    assert data["model"] == "gpt-5"
    assert data["mcp_servers"]["other"]["command"] == "other-mcp"
    assert data["mcp_servers"]["reposcope"]["command"] == "reposcope-mcp"


def test_global_paths_are_display_only_and_never_files(repo):
    preview = H.build_preview("windsurf", "stdio", str(repo))
    assert preview["files"]
    assert all(not item["path"].startswith("~") for item in preview["files"])
    assert all(not Path(item["path"]).is_absolute() for item in preview["files"])
    assert any("display-only" in warning for warning in preview["warnings"])
    assert any("~/.codeium/windsurf/mcp_config.json" in warning for warning in preview["warnings"])


def test_antigravity_skills_are_not_written_in_phase_three(repo):
    preview = H.build_preview("antigravity", "stdio", str(repo))
    assert all(".agents/skills/" not in item["path"] for item in preview["files"])
    assert any("Phase 4" in note for note in H.AGENTS_BY_ID["antigravity"].notes)


# ── Commands ────────────────────────────────────────────────────────────────


def test_commands_are_copy_pasteable_and_transport_specific(repo):
    root = str(repo.resolve())
    quoted = f'"{root}"'

    claude = H.build_preview("claude", "stdio", root)
    assert claude["command"] == (
        f"claude mcp add --scope project --transport stdio reposcope -- "
        f"reposcope-mcp --root {quoted}"
    )
    assert H.build_preview("claude", "http", root)["command"].startswith(
        "claude mcp add --scope project --transport http reposcope "
    )

    cursor = H.build_preview("cursor", "stdio", root)
    assert cursor["command"].startswith(
        "cursor://anysphere.cursor-deeplink/mcp/install?"
    )
    assert "config=" in cursor["command"]

    vscode = H.build_preview("vscode", "stdio", root)
    assert vscode["command"].startswith("code --add-mcp '")
    assert '"name":"reposcope"' in vscode["command"]

    codex = H.build_preview("codex", "stdio", root)
    assert codex["command"] == (
        f"codex mcp add reposcope -- reposcope-mcp --root {quoted}"
    )
    assert H.build_preview("codex", "http", root)["command"].startswith(
        "reposcope-mcp --http"
    )

    opencode = H.build_preview("opencode", "stdio", root)
    assert opencode["command"] == (
        f"opencode mcp add reposcope -- reposcope-mcp --root {quoted}"
    )
    assert H.build_preview("opencode", "http", root)["command"] == (
        f"opencode mcp add reposcope --url {H.DEFAULT_HTTP_URL}"
    )

    for agent_id in ("kiro", "antigravity", "windsurf", "cline"):
        stdio = H.build_preview(agent_id, "stdio", root)
        http = H.build_preview(agent_id, "http", root)
        assert stdio["command"] == f"reposcope-mcp --root {quoted}"
        assert http["command"] == f"reposcope-mcp --http --root {quoted}"


def test_commands_quote_a_root_with_spaces(repo):
    spaced = repo / "a folder with spaces"
    spaced.mkdir()
    preview = H.build_preview("claude", "stdio", str(spaced))
    assert f'--root "{spaced.resolve()}"' in preview["command"]


# ── Apply safety ────────────────────────────────────────────────────────────


def test_apply_is_refused_when_the_flag_is_off(repo):
    with pytest.raises(H.HarnessError) as exc:
        H.apply_config(
            "claude", "stdio", str(repo), apply=True, force=False
        )
    assert exc.value.status_code == 403
    assert "REPOSCOPE_HARNESS_APPLY=1" in exc.value.detail
    assert _snapshot(repo) == set()


def test_apply_false_is_a_dry_run_and_never_writes(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    result = H.apply_config("claude", "stdio", str(repo), apply=False, force=True)
    assert result["apply"] is False
    assert result["applied"] == []
    assert result["unchanged"] == []
    assert result["files"]
    assert _snapshot(repo) == set()


def test_apply_creates_files_and_a_second_apply_is_a_no_op(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    first = H.apply_config("claude", "stdio", str(repo), apply=True, force=False)

    assert first["apply"] is True
    assert sorted(first["applied"]) == [".mcp.json", "CLAUDE.md"]
    assert first["unchanged"] == []
    assert (repo / ".mcp.json").exists()
    assert (repo / "CLAUDE.md").exists()
    assert "reposcope" in (repo / ".mcp.json").read_text(encoding="utf-8")

    second = H.apply_config("claude", "stdio", str(repo), apply=True, force=False)
    assert second["applied"] == []
    assert sorted(second["unchanged"]) == [".mcp.json", "CLAUDE.md"]
    assert second["requires_force"] is False
    assert all(item["diff"] is None for item in second["files"])


def test_changed_existing_file_requires_force_then_merges(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    _write(
        repo / ".mcp.json",
        json.dumps(
            {"mcpServers": {"other": {"command": "other-mcp"}}, "unrelated": 1},
            indent=2,
        )
        + "\n",
    )

    with pytest.raises(H.HarnessError) as exc:
        H.apply_config("claude", "stdio", str(repo), apply=True, force=False)
    assert exc.value.status_code == 409
    assert ".mcp.json" in exc.value.detail
    # The 409 must not have written anything.
    assert json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"] == {
        "other": {"command": "other-mcp"}
    }

    result = H.apply_config("claude", "stdio", str(repo), apply=True, force=True)
    assert ".mcp.json" in result["applied"]
    data = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))
    assert data["unrelated"] == 1
    assert data["mcpServers"]["other"]["command"] == "other-mcp"
    assert data["mcpServers"]["reposcope"]["command"] == "reposcope-mcp"


def test_switching_transport_removes_the_other_transports_keys(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    H.apply_config("claude", "stdio", str(repo), apply=True, force=False)
    H.apply_config("claude", "http", str(repo), apply=True, force=True)

    entry = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["reposcope"]
    assert entry["type"] == "http"
    assert "url" in entry
    assert "command" not in entry
    assert "args" not in entry


def test_unparseable_json_requires_force_to_replace(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    _write(repo / ".mcp.json", "{not json")

    preview = H.build_preview("claude", "stdio", str(repo))
    assert preview["requires_force"] is True
    assert any("not valid JSON" in warning for warning in preview["warnings"])

    with pytest.raises(H.HarnessError) as exc:
        H.apply_config("claude", "stdio", str(repo), apply=True, force=False)
    assert exc.value.status_code == 409

    H.apply_config("claude", "stdio", str(repo), apply=True, force=True)
    data = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))
    assert data["mcpServers"]["reposcope"]["command"] == "reposcope-mcp"


def test_markdown_merge_keeps_surrounding_text_and_is_idempotent(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    _write(
        repo / "CLAUDE.md",
        "# House rules\n\nKeep this line.\n\n"
        f"{H.MARKER_BEGIN}\nold section\n{H.MARKER_END}\n\nTail line.\n",
    )
    H.apply_config("claude", "stdio", str(repo), apply=True, force=True)

    text = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert text.count(H.MARKER_BEGIN) == 1
    assert text.count(H.MARKER_END) == 1
    assert "Keep this line." in text
    assert "Tail line." in text
    assert "old section" not in text

    second = H.apply_config("claude", "stdio", str(repo), apply=True, force=False)
    assert "CLAUDE.md" in second["unchanged"]
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == text


def test_opencode_adds_mcp_reposcope_and_leaves_legacy_key_alone(repo, monkeypatch):
    monkeypatch.setenv("REPOSCOPE_HARNESS_APPLY", "1")
    _write(
        repo / "opencode.json",
        json.dumps(
            {"$schema": "https://opencode.ai/config.json", "mcp": {"servers": {"old": {}}}},
            indent=2,
        )
        + "\n",
    )
    preview = H.build_preview("opencode", "stdio", str(repo))
    assert any("mcp.servers" in warning for warning in preview["warnings"])

    H.apply_config("opencode", "stdio", str(repo), apply=True, force=True)
    data = json.loads((repo / "opencode.json").read_text(encoding="utf-8"))
    assert data["$schema"] == "https://opencode.ai/config.json"
    assert data["mcp"]["servers"] == {"old": {}}
    assert data["mcp"]["reposcope"]["type"] == "local"


# ── Path safety and roots ───────────────────────────────────────────────────


# On POSIX, a backslash is an ordinary filename character, so
# "..\\escape.json" names a file inside the root rather than escaping it.
# Only include that case where the platform treats the backslash as a
# separator.
_UNSAFE_CONFIG_PATHS = [
    "../escape.json",
    "/etc/passwd",
    "C:\\Windows\\x.json",
]
if os.name == "nt":
    _UNSAFE_CONFIG_PATHS.append("..\\escape.json")


@pytest.mark.parametrize("bad", _UNSAFE_CONFIG_PATHS)
def test_unsafe_config_paths_are_rejected(repo, bad):
    with pytest.raises(H.HarnessError) as exc:
        H.resolve_config_path(repo, bad)
    assert exc.value.status_code == 400


def _make_directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"cannot create a junction: {result.stderr.strip()}")
        return
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform permission
        pytest.skip(f"cannot create a symlink: {exc}")


def test_a_junction_or_symlink_outside_the_root_is_rejected(tmp_path, repo):
    outside = tmp_path / "outside"
    outside.mkdir()
    _make_directory_link(repo / "linked", outside)

    with pytest.raises(H.HarnessError) as exc:
        H.resolve_config_path(repo, "linked/mcp.json")
    assert exc.value.status_code == 400
    assert "escapes the repository root" in exc.value.detail


def test_an_existing_file_symlink_outside_the_root_is_rejected(tmp_path, repo):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = repo / "linked.json"
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", str(link), str(outside)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"cannot create a file symlink: {result.stderr.strip()}")
    else:
        try:
            link.symlink_to(outside)
        except OSError as exc:  # pragma: no cover
            pytest.skip(f"cannot create a symlink: {exc}")

    with pytest.raises(H.HarnessError) as exc:
        H.resolve_config_path(repo, "linked.json")
    assert exc.value.status_code == 400


def test_a_config_path_that_is_a_directory_is_rejected(repo):
    (repo / ".mcp.json").mkdir()
    with pytest.raises(H.HarnessError) as exc:
        H.build_preview("claude", "stdio", str(repo))
    assert exc.value.status_code == 400
    assert "not a file" in exc.value.detail


def test_root_must_exist_and_be_absolute(repo, tmp_path):
    with pytest.raises(H.HarnessError) as exc:
        H.resolve_root("repo")
    assert exc.value.status_code == 400
    assert "absolute" in exc.value.detail

    missing = tmp_path / "missing"
    with pytest.raises(H.HarnessError) as exc:
        H.resolve_root(str(missing))
    assert exc.value.status_code == 400
    assert "does not exist" in exc.value.detail

    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(H.HarnessError) as exc:
        H.resolve_root(str(file_path))
    assert exc.value.status_code == 400
    assert "not a directory" in exc.value.detail


def test_root_defaults_to_the_active_local_repository(repo, monkeypatch):
    import orchestrator

    monkeypatch.setattr(orchestrator, "current_graph", lambda: ({}, str(repo)))
    assert H.resolve_root(None) == repo.resolve()


def test_root_is_required_when_no_repository_is_active(monkeypatch):
    import orchestrator

    monkeypatch.setattr(orchestrator, "current_graph", lambda: ({}, None))
    with pytest.raises(H.HarnessError) as exc:
        H.resolve_root(None)
    assert exc.value.status_code == 400
    assert "Load a local folder first" in exc.value.detail


def test_unknown_agent_and_transport_are_400(repo):
    with pytest.raises(H.HarnessError) as exc:
        H.build_preview("unknown", "stdio", str(repo))
    assert exc.value.status_code == 400

    with pytest.raises(H.HarnessError) as exc:
        H.build_preview("claude", "sse", str(repo))
    assert exc.value.status_code == 400
    assert "Unsupported transport" in exc.value.detail


# ── Skills ──────────────────────────────────────────────────────────────────


def test_skills_are_descriptors_only_in_phase_three():
    payload = H.list_skills()
    assert payload["content_available"] is False
    assert [skill["id"] for skill in payload["skills"]] == [
        "blast-radius-guard",
        "zero-grep-architect",
        "pr-contract-shield",
        "onboarding-navigator",
        "dead-code-surgeon",
    ]
    for skill in payload["skills"]:
        assert skill["content_available"] is False
        assert "content" not in skill
        assert skill["description"]
        assert skill["files"]
