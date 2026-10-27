# RepoScope Agent Integration Guide (Phase 3)

The RepoScope Nine-Agent Harness Configurator connects local AI coding agents directly to RepoScope's live architectural graph via the Model Context Protocol (MCP).

---

## 1. Configurator Overview: Preview vs. Apply

The harness configurator provides deterministic, project-scoped MCP configurations for nine major AI coding agents.

### Security Boundary & Separation of Concerns

* **The browser never writes files**: The frontend UI is strictly a display and review layer.
* **The backend is the sole writer**: The RepoScope backend owns file resolution, path traversal validation, syntax-preserving JSON/TOML merging, and atomic disk writes.
* **Preview is guaranteed side-effect-free**: Opening the configurator, inspecting agents, toggling transports, and viewing diffs never creates or alters files on disk. No network requests are made outside the local RepoScope backend.
* **Writes require two explicit gates**:
  1. **Server environment gate**: The backend refuses write requests (`POST /api/harness/apply` with `apply: true`) with HTTP 403 Forbidden unless the server process was started with the environment variable `REPOSCOPE_HARNESS_APPLY=1`. When this flag is unset, the UI keeps the write action disabled and explains that server writes are off.
  2. **Force confirmation gate**: If a configuration target already exists on disk and its content would change, the backend refuses to overwrite it with HTTP 409 Conflict unless `force: true` is explicitly passed. In the UI, a force checkbox and a secondary confirmation step are required.

---

## 2. Supported Agents Matrix

All nine supported agents provide project-scoped MCP configuration and support both `stdio` and `http` transports (`stdio` is the default).

| Agent ID | Label | Project Files | Transports | Default Transport | Command Kind | Official Documentation |
|---|---|---|---|---|---|---|
| `claude` | Claude Code | `.mcp.json`, `CLAUDE.md` | `stdio`, `http` | `stdio` | `install` | [Claude Code MCP Docs](https://docs.claude.com/en/docs/claude-code/mcp) |
| `cursor` | Cursor | `.cursor/mcp.json`, `.cursor/rules/reposcope.mdc` | `stdio`, `http` | `stdio` | `deeplink` | [Cursor MCP Docs](https://cursor.com/docs/context/mcp) |
| `vscode` | VS Code / Copilot | `.vscode/mcp.json`, `.github/copilot-instructions.md` | `stdio`, `http` | `stdio` | `install` | [VS Code MCP Docs](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) |
| `codex` | Codex CLI | `.codex/config.toml`, `AGENTS.md` | `stdio`, `http` | `stdio` | `install` | [Codex MCP Docs](https://developers.openai.com/codex/mcp) |
| `kiro` | Kiro | `.kiro/settings/mcp.json`, `.kiro/steering/reposcope.md` | `stdio`, `http` | `stdio` | `server` | [Kiro MCP Docs](https://kiro.dev/docs/mcp/configuration/) |
| `antigravity` | Antigravity | `.agents/mcp_config.json`, `AGENTS.md` | `stdio`, `http` | `stdio` | `server` | [Antigravity Docs](https://antigravity.google/docs/mcp) |
| `windsurf` | Windsurf / Devin | `.devin/mcp_config.json`, `.windsurf/rules/reposcope.md` | `stdio`, `http` | `stdio` | `server` | [Windsurf Cascade Docs](https://docs.windsurf.com/windsurf/cascade/mcp) |
| `cline` | Cline / Roo | `.roo/mcp.json`, `.clinerules` | `stdio`, `http` | `stdio` | `server` | [Cline Docs](https://docs.cline.bot/mcp/configuring-mcp-servers) |
| `opencode` | OpenCode | `opencode.json` | `stdio`, `http` | `stdio` | `install` | [OpenCode MCP Docs](https://opencode.ai/docs/mcp-servers) |

---

## 3. Verified Configuration Formats & Deltas

These specifications were re-verified against official vendor documentation on 2026-10-26:

1. **OpenCode (`opencode.json`)**:
   Current OpenCode schema uses the top-level `mcp.<name>` block:
   ```json
   {
     "mcp": {
       "reposcope": {
         "type": "local",
         "command": ["reposcope-mcp", "--root", "/path/to/repo"],
         "enabled": true
       }
     }
   }
   ```
   > ⚠️ **Warning**: Older documentation referenced an `mcp.servers` key. There is **no** `mcp.servers` key in current OpenCode releases. Do not use `mcp.servers`.

2. **Windsurf / Devin Desktop**:
   Devin Desktop reads the project MCP configuration at `.devin/mcp_config.json`. Project rules are written to `.windsurf/rules/reposcope.md`. Legacy Cascade paths remain display-only.

3. **Cline / Roo Code**:
   Project-scoped MCP configuration is written to Roo Code's `.roo/mcp.json` alongside `.clinerules`. Cline's CLI global settings live in user home and are display-only.

4. **Antigravity**:
   Phase 3 writes project MCP configuration to `.agents/mcp_config.json` and instructions to `AGENTS.md`. The `.agents/skills/` directory and `SKILL.md` files are scheduled for Phase 4.

---

## 4. Display-Only Global Paths

Several agents maintain global user-level configuration files (such as `~/.config/opencode/opencode.json`, `~/.cline/data/settings/cline_mcp_settings.json`, `~/.gemini/config/mcp_config.json`, `~/.codeium/windsurf/mcp_config.json`, or `~/.codex/config.toml`).

* **Why they are display-only**: RepoScope strictly confines all filesystem writes to the active repository root. Writing to user home directories risks corrupting global agent settings or leaking repository-specific roots into global environments.
* **In the UI**: Global paths are clearly flagged with an informational badge: *"Display-only global paths (never written by RepoScope)"*.

---

## 5. Step-by-Step Setup Guide

### General Workflow

1. **Open the Configurator**: Click the **Connect AI agent** button in the RepoScope top navigation bar.
2. **Select Target Agent**: Pick one of the nine agents from the left sidebar.
3. **Select Transport**: Choose `stdio` (default, spawns `reposcope-mcp` on demand) or `http` (connects to running HTTP endpoint, default `http://127.0.0.1:8765/mcp`).
4. **Review Configuration & Diff**:
   - Inspect the file tabs to see the exact JSON, TOML, or Markdown content.
   - If an existing file already exists, review the color-coded unified diff.
5. **Apply Configuration**:
   - **Manual CLI**: Copy the exact command from the **Agent Command** card and run it in your terminal.
   - **Direct Write (when server writes enabled)**: If `REPOSCOPE_HARNESS_APPLY=1` is set, review the changes, check the force box if updating existing files, click **Write files**, and confirm.
6. **Restart Agent & Verify**:
   - Restart the agent CLI or reload the IDE window.
   - Verify that `reposcope` appears in the list of active MCP servers.
   - Run a prompt invoking RepoScope tools (e.g. `get_architecture_overview` or `calculate_blast_radius`).

---

## 6. Target-Specific Setup Instructions

### 1. Claude Code
* **Project Files**: `.mcp.json`, `CLAUDE.md`
* **Copy-paste command**:
  ```bash
  claude mcp add --scope project --transport stdio reposcope -- reposcope-mcp --root "/path/to/repo"
  ```
* **Verification**: Run `claude mcp list` inside the repository and confirm `reposcope` is listed as a project-scoped server.

### 2. Cursor
* **Project Files**: `.cursor/mcp.json`, `.cursor/rules/reposcope.mdc`
* **Setup**: Apply or save `.cursor/mcp.json` containing `mcpServers.reposcope`.
* **Verification**: Open Cursor Settings → Features → MCP. Verify `reposcope` has a green status indicator.

### 3. VS Code / Copilot
* **Project Files**: `.vscode/mcp.json`, `.github/copilot-instructions.md`
* **Setup**: Writes `servers.reposcope` with `"type": "stdio"` (or `"http"`).
* **Verification**: Open GitHub Copilot Chat in VS Code and verify RepoScope tools are available.

### 4. Codex CLI
* **Project Files**: `.codex/config.toml`, `AGENTS.md`
* **Format**: TOML table `[mcp_servers.reposcope]`.
* **Verification**: Run `codex mcp list` and ensure `reposcope` is active.

### 5. Kiro
* **Project Files**: `.kiro/settings/mcp.json`, `.kiro/steering/reposcope.md`
* **Setup**: Project-level settings under `.kiro/settings/mcp.json`.
* **Verification**: Reload Kiro workspace and check MCP server status in developer tools.

### 6. Antigravity
* **Project Files**: `.agents/mcp_config.json`, `AGENTS.md`
* **Setup**: Project-level MCP config at `.agents/mcp_config.json`.
* **Dogfood Result**: Checked via `Get-Command antigravity`. Command returned `CommandNotFoundException` (exited code 1); recorded as **not installed** on this machine. If installed in your environment, place `.agents/mcp_config.json` in the workspace root and relaunch Antigravity.

### 7. Windsurf / Devin
* **Project Files**: `.devin/mcp_config.json`, `.windsurf/rules/reposcope.md`
* **Setup**: Project config in `.devin/mcp_config.json`.
* **Verification**: Open Windsurf Cascade settings → MCP Servers → verify `reposcope`.

### 8. Cline / Roo Code
* **Project Files**: `.roo/mcp.json`, `.clinerules`
* **Setup**: Written to `.roo/mcp.json` with `mcpServers.reposcope`.
* **Verification**: Open the Cline / Roo sidebar → MCP Servers tab → verify connection.

### 9. OpenCode
* **Project Files**: `opencode.json`
* **Command**:
  ```bash
  opencode mcp add reposcope -- reposcope-mcp --root "/path/to/repo"
  ```
* **Verification**: Run `opencode mcp list` and verify `reposcope` with type `local` or `remote`.

---

## 7. Phase 4 Skills Preview

RepoScope defines five specialized architectural skills designed for AI coding agents:

1. **Blast Radius Guard** (`blast-radius-guard`): Checks direct and transitive dependents before changing a file or symbol.
2. **Zero-Grep Architect** (`zero-grep-architect`): Answers architecture, layer boundary, and ownership questions from the graph instead of broad textual search.
3. **PR Contract Shield** (`pr-contract-shield`): Validates interface contracts, API boundaries, and cross-layer imports before opening pull requests.
4. **Onboarding Navigator** (`onboarding-navigator`): Generates a ranked reading path through an unfamiliar repository using architectural hubs and central symbols.
5. **Dead Code Surgeon** (`dead-code-surgeon`): Identifies unreferenced symbols with structural graph evidence for safe deprecation and refactoring.

*Status*: In Phase 3, skill descriptors and target file bindings are previewable in the UI via the **Skills** tab. Full executable `SKILL.md` bodies will be delivered in Phase 4.

---

## 8. Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| **"Local repository required"** empty state in modal | RepoScope was opened with a browser preview or without an active local root | Launch RepoScope pointing to a local directory: `reposcope run <directory>`. Browser folder previews cannot write to disk. |
| **"Write files" button disabled** | Server was started without write authorization | Restart the RepoScope backend with `REPOSCOPE_HARNESS_APPLY=1` if you want RepoScope to write configuration files directly. |
| **HTTP 403 Forbidden on apply** | Attempted write request while server write flag is off | The backend blocks writes unless `REPOSCOPE_HARNESS_APPLY=1` is set in the environment. |
| **HTTP 409 Conflict on apply** | Target file already exists on disk and would change, but `force: false` | In the UI, check the *"Overwrite existing file modifications"* checkbox. On the CLI, pass `"force": true` in the apply body. |
| **"Failed to reach backend"** | Backend server is not running | Ensure `python -m uvicorn main:app` or `reposcope run` is running on the expected port (default `:8000`). |
| **Warning: Lost TOML comments** | Editing an existing `.codex/config.toml` file | Python's standard `tomllib` parser does not retain comment tokens. The configurator preserves all existing keys and tables and surfaces this warning. |
