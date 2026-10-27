# WREN PROMPT — PHASE 3

**From:** Rook  
**To:** Wren  
**Phase:** 3 only — nine-agent harness configurator  
**Backend commit:** `69b9620 feat(api): add nine-agent harness generator`  
**Backend branch:** local `rook/phase-3-harness`, based on `a667ac4`  
**Your branch:** `wren/phase-3-harness`  
**Status:** backend frozen and verified; UI, docs, screenshots, and the L3 journey are yours.

> **Do not push anything.** The owner has explicitly withheld push permission.
> Commit locally on `wren/phase-3-harness` and stop. Rook reviews and
> integrates. Do not touch `main` or `experimental`.

---

## 1. Who you are and what this phase is

You are **Wren**, the frontend and verification partner on RepoScope
V2.5–V2.8. You own the UI, accessibility, the browser journey, the integration
guide, and visual evidence. Rook owns the backend contract, generator, apply
safety, backend tests, API docs, review, and integration.

Phase 3 adds the **nine-agent harness configurator**:

- a user opens a modal from the RepoScope top bar;
- picks one of nine supported AI coding agents;
- sees the exact MCP config files, exact command, and a unified diff for any
  existing file;
- gets a preview by default;
- can write only after a second explicit action, and only when the server says
  writes are enabled.

The browser never writes files. The backend is the only writer. The backend
owns the registry, paths, formats, merge behavior, and safety. The UI consumes
that contract. Do not hardcode nine configs in React, do not invent a path, and
do not "fix" the backend to match the UI.

Phase 3 only. Do not start Phase 4, do not write `SKILL.md` bodies, do not add
MCP tools or resources, and do not do packaging work.

---

## 2. Exact start state

- Repo root (Rook's worktree):
  `D:\Aditya\Hackathon Projects\RepoScope-rook-phase3`
- Main worktree:
  `D:\Aditya\Hackathon Projects\RepoScope` is on `main` at `a667ac4`.
- `main` and local `experimental` are both at `a667ac4`.
- `origin/experimental` is stale at `b4e0def`; do not use it.
- `rook/phase-3-harness` is local and **unpushed**. It contains the backend
  commit `69b9620` plus the handoff docs.
- `wren/phase-3-harness` does not exist yet.
- Only Rook and Wren names are used in coordination. Do not expose any
  underlying model or tool name in docs or commits.

Create your worktree from the **local** branch:

```powershell
git worktree add "D:\Aditya\Hackathon Projects\RepoScope-wren-phase3" -b wren/phase-3-harness rook/phase-3-harness
cd "D:\Aditya\Hackathon Projects\RepoScope-wren-phase3"
git log --oneline -3
git merge-base --is-ancestor 69b9620 HEAD
```

The ancestor check must exit `0`. `git log --oneline -3` must show
`69b9620 feat(api): add nine-agent harness generator`; the branch head may be
a later handoff-docs commit on top of it.

**Do not** run `git fetch origin rook/phase-3-harness` and **do not** branch
from `origin`. That branch does not exist remotely. If the worktree command
fails because the branch or directory already exists, stop and report it; do
not reuse or delete someone else's work.

Then install and establish a green baseline:

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
```

If the build is red before your first edit, stop and report the exact error.
Do not "fix" unrelated frontend code.

---

## 3. Backend that is already done — do not edit it

Rook shipped and committed:

- `backend/harness_generator.py` — frozen nine-target registry, stdio and
  Streamable HTTP entries, JSON/TOML/markdown merging, path safety, atomic
  writes, side-effect-free preview, gated apply.
- `backend/api/routers/harness.py` — the four endpoints.
- `backend/api/__init__.py` — router mounted.
- `backend/tests/test_harness_generator.py` and
  `backend/tests/test_harness_api.py` — 68 harness tests.
- `docs/API.md`, `docs/FEATURES.md`, `CHANGELOG.md`, and
  `docs/opencode-mcp.json` — updated for the current OpenCode schema.

Backend gate at handoff:

- `python -m pytest -q` → **473 passed, 1 skipped**;
- the skip is a Windows file-symlink creation privilege; the junction-escape
  test runs and passes;
- harness tests → **68 passed, 1 skipped**;
- `python -m compileall -q backend` → pass;
- `pip check` → no broken requirements.

Live verification used `127.0.0.1:8011` and a throwaway copy of
`backend/tests/fixtures/v2_contract`. Do not run a write test against a
committed fixture. Do not edit `backend/harness_generator.py`,
`backend/api/routers/harness.py`, `backend/api/__init__.py`, or
`backend/tests/test_harness_*`.

If the live response differs from the contract below, stop and report it in
`docs/coordination/DIALOGUE.md`. Do not patch the backend and do not build
against a guessed shape.

---

## 4. Frozen registry — nine targets

The backend returns these in this order:

`claude`, `cursor`, `vscode`, `codex`, `kiro`, `antigravity`, `windsurf`,
`cline`, `opencode`.

| id | label | project paths | display-only global paths |
|---|---|---|---|
| `claude` | Claude Code | `.mcp.json`, `CLAUDE.md` | — |
| `cursor` | Cursor | `.cursor/mcp.json`, `.cursor/rules/reposcope.mdc` | — |
| `vscode` | VS Code / Copilot | `.vscode/mcp.json`, `.github/copilot-instructions.md` | — |
| `codex` | Codex CLI | `.codex/config.toml`, `AGENTS.md` | `~/.codex/config.toml` |
| `kiro` | Kiro | `.kiro/settings/mcp.json`, `.kiro/steering/reposcope.md` | `~/.kiro/settings/mcp.json` |
| `antigravity` | Antigravity | `.agents/mcp_config.json`, `AGENTS.md` | `~/.gemini/config/mcp_config.json` |
| `windsurf` | Windsurf / Devin | `.devin/mcp_config.json`, `.windsurf/rules/reposcope.md` | `~/.codeium/windsurf/mcp_config.json`, `~/.config/devin/mcp_config.json` |
| `cline` | Cline / Roo | `.roo/mcp.json`, `.clinerules` | `~/.cline/data/settings/cline_mcp_settings.json` |
| `opencode` | OpenCode | `opencode.json` | `~/.config/opencode/opencode.json` |

All nine support `stdio` and `http`; the default is `stdio` for all nine. The
UI must use the server's `transport` and `default_transport`, not this table.

### Verified deltas that override older docs

These were verified against official documentation on 2026-10-26 and are
already implemented by the backend:

1. **OpenCode** uses `mcp.reposcope` with
   `"type": "local"` for stdio or `"type": "remote"` for HTTP. There is no
   `mcp.servers` key in the current schema. The L3 journey must assert
   `mcp.reposcope` and must not assert `mcp.servers`.
2. **Windsurf / Devin** writes `.devin/mcp_config.json` and
   `.windsurf/rules/reposcope.md`. The legacy Cascade path is display-only.
3. **Cline / Roo** writes Roo Code's project file `.roo/mcp.json` and
   `.clinerules`. Cline's global settings path is display-only.
4. **Antigravity** `.agents/skills/` remains Phase 4. Phase 3 writes only
   `.agents/mcp_config.json`; do not fabricate skill bodies.

Exact config shapes the backend returns:

- Claude: `.mcp.json` with `mcpServers.reposcope`.
- Cursor: `.cursor/mcp.json` with `mcpServers.reposcope`.
- VS Code: `.vscode/mcp.json` with `servers.reposcope` and a `type` field.
- Codex: `.codex/config.toml` with `[mcp_servers.reposcope]`; no empty parent
  table.
- Kiro: `.kiro/settings/mcp.json` with `mcpServers.reposcope`.
- Antigravity: `.agents/mcp_config.json` with `mcpServers.reposcope`.
- Windsurf/Devin: `.devin/mcp_config.json` with `mcpServers.reposcope`.
- Cline/Roo: `.roo/mcp.json` with `mcpServers.reposcope`.
- OpenCode: `opencode.json` with `mcp.reposcope` and `type: local | remote`.

The preview's `command` is the exact copy-paste command. Do not synthesize one.
For Claude, the verified live command with a spaced root was:

```text
claude mcp add --scope project --transport stdio reposcope -- reposcope-mcp --root "D:\Aditya\Hackathon Projects\RepoScope-rook-phase3\backend\tests\fixtures\v2_contract"
```

The path is quoted by the backend so a repository root containing spaces stays
copy-pasteable.

---

## 5. Frozen API contract

All four endpoints are under `/api/harness`, return JSON, and never call the
network. Preview is guaranteed side-effect-free.

### `GET /api/harness/agents`

Returns:

```json
{
  "agents": [
    {
      "id": "claude",
      "label": "Claude Code",
      "config_paths": [".mcp.json", "CLAUDE.md"],
      "transport": ["stdio", "http"],
      "default_transport": "stdio",
      "global_preview_paths": [],
      "docs_url": "https://docs.claude.com/en/docs/claude-code/mcp",
      "verified_at": "2026-10-26",
      "notes": ["Project scope is .mcp.json; the CLI needs --scope project."]
    }
  ],
  "apply_enabled": false
}
```

- `config_paths` are repository-relative.
- `global_preview_paths` are display-only; never write them.
- `apply_enabled` reflects the server environment, not a client preference.

### `GET /api/harness/config`

Query: `agent=<id>&transport=stdio|http&root=<absolute path>`.

`root` must be an existing absolute directory. There is no implicit current
directory fallback. The UI must pass the active local repository's absolute
path. The server accepts an omitted root only when a backend-loaded local
repository supplies one; the UI should not rely on that.

Returns a preview:

```json
{
  "ok": true,
  "agent": "claude",
  "label": "Claude Code",
  "transport": "stdio",
  "root": "D:\\repo",
  "command": "claude mcp add --scope project --transport stdio reposcope -- reposcope-mcp --root \"D:\\repo\"",
  "command_kind": "install",
  "command_note": "Writes the project-scoped .mcp.json. Review the diff before running it.",
  "apply_enabled": false,
  "requires_force": false,
  "files": [
    {
      "path": ".mcp.json",
      "format": "json",
      "content": "{...}\n",
      "exists": false,
      "diff": null,
      "will_write": true
    }
  ],
  "warnings": []
}
```

- `format` is `json`, `toml`, or `markdown`.
- `content` is the exact text that would be written.
- `exists` is whether the target file is already present.
- `diff` is a unified diff when an existing file would change; otherwise
  `null`.
- `will_write` is `false` for an identical file.
- `requires_force` is `true` when any existing file would change.
- `warnings` can report unparseable files, lost TOML comments, legacy OpenCode
  keys, and display-only global paths. Render warnings; do not hide them.
- `command_kind` is `install`, `server`, or `deeplink`; `command_note` explains
  how to use it. Render the label and note; for a deeplink, show and copy the
  exact link but do not navigate automatically.

### `POST /api/harness/apply`

Body:

```json
{
  "agent": "claude",
  "transport": "stdio",
  "root": "D:\\repo",
  "apply": false,
  "force": false
}
```

- `apply: false` is a dry run and writes nothing. The response is the preview
  shape plus `"apply": false`, `"applied": []`, `"unchanged": []`.
- `apply: true` writes only the writable files under `root` when the server
  flag is on. The response adds `"apply": true`, `"applied": [...]`,
  `"unchanged": [...]`.
- Existing JSON/TOML files are merged, not replaced: unrelated keys and
  servers survive. Markdown files get one delimited RepoScope section. A second
  apply is a no-op.
- Writes are atomic.

Status codes:

| Status | Meaning |
|---|---|
| `400` | unknown agent, unsupported transport, invalid root, or unsafe path |
| `403` | `apply: true` while `REPOSCOPE_HARNESS_APPLY` is not `1` |
| `409` | an existing file would change and `force` is false |
| `422` | the request body is missing a required field |

### `GET /api/harness/skills`

Returns the five bundle descriptors and `"content_available": false`:

`blast-radius-guard`, `zero-grep-architect`, `pr-contract-shield`,
`onboarding-navigator`, `dead-code-surgeon`.

Each has `id`, `label`, `description`, `targets`, `files`, and
`content_available: false`. Phase 3 shows them; it does not write `SKILL.md`
bodies and does not expose `.agents/skills/*`. That is Phase 4.

### Live verification at handoff

- `GET /api/health` → `200 {"status":"healthy"}`.
- `GET /api/harness/agents` → nine ids in the order above; `apply_enabled:
  false`.
- Claude preview → `.mcp.json`, `CLAUDE.md`; command as quoted above.
- VS Code preview → `.vscode/mcp.json`, `servers.reposcope`, `"type":
  "stdio"`.
- Codex preview → `.codex/config.toml`, `[mcp_servers.reposcope]`, no empty
  parent table.
- OpenCode HTTP preview → `opencode.json`, `mcp.reposcope`, `"type":
  "remote"`, URL `http://127.0.0.1:8765/mcp` (unless the server's
  `REPOSCOPE_MCP_HTTP_URL` overrides it). There is no `mcp.servers` key.
- `POST /api/harness/apply` with `apply: false` → `200`, `applied: []`, no
  writes.
- `POST /api/harness/apply` with `apply: true` and the flag off → `403`.
- With `REPOSCOPE_HARNESS_APPLY=1` and a throwaway copy, `apply: true` →
  `200`, `applied: [".mcp.json", "CLAUDE.md"]`, both files present.
- `GET /api/harness/skills` → five descriptors, `content_available: false`.

The QA backend used by Playwright runs with `REPOSCOPE_QA=1` and no apply flag,
so the default journey must see `apply_enabled: false`.

---

## 6. Frontend integration points

These files exist; you own the changes listed in §8.

- `frontend/src/api/client.ts` — add harness types and calls. Reuse
  `_fetchWithTimeout` and `_json`; nothing else in this client needs to change.
- `frontend/src/App.tsx` — add modal state, pass the entry callback to
  `TopBar`, render the modal, and pass `localRoot`.
- `frontend/src/components/TopBar.tsx` — add a discoverable, keyboard-
  accessible “Connect AI agent” entry. A labelled icon button is fine; use an
  existing lucide icon such as `Bot` or `PlugZap`, not a new dependency.
- `localRoot` in `App.tsx` is the absolute local path from the backend's
  `/api/repo/status` when `is_local` is true. That is the only root the modal
  should use. A browser File System Access preview has no backend index and no
  usable root; the modal must explain that a local repository is required
  instead of asking the user to type an arbitrary path.
- Reuse the existing modal styling (`card`, `btn-primary`, `btn-secondary`,
  `input`, `label-caps`) and the existing `toast` helper if useful.
  `EditorSettings.tsx` is a simple reference, but it does not fully trap focus;
  your modal must do better.

Suggested TypeScript shapes:

```ts
export type HarnessTransport = "stdio" | "http";

export interface HarnessAgent {
  id: string;
  label: string;
  config_paths: string[];
  transport: HarnessTransport[];
  default_transport: HarnessTransport;
  global_preview_paths: string[];
  docs_url: string;
  verified_at: string;
  notes: string[];
}

export interface HarnessFilePreview {
  path: string;
  format: "json" | "toml" | "markdown";
  content: string;
  exists: boolean;
  diff: string | null;
  will_write: boolean;
}

export interface HarnessPreview {
  ok: boolean;
  agent: string;
  label: string;
  transport: HarnessTransport;
  root: string;
  command: string;
  command_kind: "install" | "server" | "deeplink";
  command_note: string;
  apply_enabled: boolean;
  requires_force: boolean;
  files: HarnessFilePreview[];
  warnings: string[];
}

export interface HarnessApplyResult extends HarnessPreview {
  apply: boolean;
  applied: string[];
  unchanged: string[];
}

export interface HarnessSkill {
  id: string;
  label: string;
  description: string;
  targets: string[];
  files: string[];
  content_available: boolean;
}

export interface HarnessSkills {
  skills: HarnessSkill[];
  content_available: boolean;
}
```

Suggested calls:

```ts
getHarnessAgents(): Promise<{ agents: HarnessAgent[]; apply_enabled: boolean }>
getHarnessConfig(params: {
  agent: string;
  transport: HarnessTransport;
  root: string;
}): Promise<HarnessPreview>
applyHarnessConfig(body: {
  agent: string;
  transport: HarnessTransport;
  root: string;
  apply: boolean;
  force: boolean;
}): Promise<HarnessApplyResult>
getHarnessSkills(): Promise<HarnessSkills>
```

Encode the root with `URLSearchParams`; it contains spaces and backslashes.
For apply, send JSON with `Content-Type: application/json`. Do not add an
`X-Session-Id` requirement; the endpoint does not use one.

---

## 7. Required UI behavior

1. **Entry point.** A discoverable “Connect AI agent” control in the top bar.
   It must be keyboard reachable, have an accessible name, and open the modal
   without changing the loaded repository. Add `data-testid="open-harness"` for
   the journey.
2. **Modal shell.** `role="dialog"`, `aria-modal="true"`, a labelled title,
   focus trapped inside, `Escape` closes, and focus returns to the trigger on
   close. A backdrop click may close only when there is no unsaved write
   confirmation in progress. Add `data-testid="harness-modal"`.
3. **Agent list.** Render all nine from `GET /api/harness/agents`. Show label,
   config paths, transport, and a docs link. Do not hardcode labels or paths.
   Use `data-testid="harness-agent-<id>"` on each selectable row.
4. **Transport.** Default to `default_transport`. Disable any transport the
   server did not list and show why. Changing agent or transport fetches a new
   preview. Ignore out-of-order responses with a request-sequence ref; do not
   let a slow Claude response overwrite a newer OpenCode preview.
5. **Preview.** One tab per file. Show exact content in a `<pre>` (preserve
   whitespace), a copy button per file, and the exact `command` with a copy
   button. Show `command_note` and the `command_kind` label (`install`,
   `server`, or `deeplink`). Do not auto-open a deeplink. For an existing
   changed file, show the unified `diff` and a visible “existing file will
   change” warning. Never call apply on preview. Add
   `data-testid="harness-preview"`.
6. **Apply.** The primary action is “Preview” or “Review changes”; writes
   require a second explicit action labelled “Write files” (or equivalent).
   Disable it when `apply_enabled` is false and explain that the server has
   writes disabled. When enabled, require a `force` checkbox for any
   `requires_force` preview and keep the diff visible. After apply, show the
   `applied` and `unchanged` paths and keep the preview visible. Never show a
   success/write confirmation on a preview. Add `data-testid="harness-apply"`.
7. **Warnings.** Render `warnings` as a distinct list, not console noise.
   Global paths are display-only; label them that way. Unparseable files and
   lost TOML comments need to be visible before the user writes.
8. **Root handling.** Use `localRoot`. If it is null, render a clear empty
   state: a local repository is required, and link/point to the local-folder
   flow. Do not ask the user to type an arbitrary path and do not call the
   preview with a guessed root. If the root changes while the modal is open,
   reset the preview and refetch.
9. **Skills.** Show the five descriptors from `GET /api/harness/skills` in a
   “Skills” section or tab. Mark them “Available in Phase 4” when
   `content_available` is false. Do not fabricate bodies or write
   `.agents/skills/*`.
10. **Errors.** Handle registry load failure, preview failure, unknown agent,
    unsupported transport, unsafe root, existing-file conflict, apply disabled,
    `403`, `409`, `422`, and network failure. Each gets a clear message and a
    retry or dismiss action. Never render a blank modal.
11. **Accessibility.** ARIA tabs for agents/files, visible focus rings,
    labelled copy/apply buttons, disabled reasons via `aria-describedby`, no
    keyboard trap outside the modal, and no focus loss when the preview
    refreshes.
12. **Layout.** At 1600×900 and 1280×800: no horizontal overflow; the agent
    list and preview pane scroll independently; the modal stays usable with the
    longest command and a unified diff. Use a two-column layout on wide screens
    and a stacked layout on narrow ones.
13. **Performance.** Fetch the registry once per open. Fetch a preview only
    when agent/transport/root changes. Do not fetch all nine previews at once.
    Do not refetch on every keystroke; there is no editable root in the modal.
14. **No telemetry, no automatic external calls.** The browser talks only to
    the local RepoScope backend for data; user-initiated docs links are fine.
    No LLM call. No network call to “verify” a config. No secrets, no `.env`
    contents, and no tokens in the UI or committed files.

---

## 8. Files you own

Create:

- `frontend/src/components/HarnessModal.tsx`
- `frontend/src/components/harness/*` (only if splitting keeps the modal
  readable)
- `frontend/tests/e2e/harness.spec.ts`
- `docs/AGENT_INTEGRATION.md`
- `docs/screenshots/v2/harness/*.png`

Edit:

- `frontend/src/api/client.ts` — harness types and calls.
- `frontend/src/App.tsx` — modal state and entry wiring.
- `frontend/src/components/TopBar.tsx` — the entry control.
- `docs/coordination/WREN.md` and `docs/coordination/DIALOGUE.md` — claims,
  progress, handoff.

Do **not** edit:

- `backend/harness_generator.py`, `backend/api/routers/harness.py`,
  `backend/api/__init__.py`, or `backend/tests/test_harness_*`.
- `docs/API.md`, `docs/FEATURES.md`, `CHANGELOG.md`, or
  `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md`; Rook owns those.
- `frontend/src/components/GraphView.tsx` or `frontend/src/components/mindmap/*`.
- `frontend/package.json` unless a dependency is essential; ask Rook first.
- `main` or `experimental`.
- Any `.env`, token, generated `dist/`, `node_modules`, or QA temp copy.

One writer per file. Claim your files in `WREN.md` before editing.

### `docs/AGENT_INTEGRATION.md` content

Write a real setup guide, not a changelog. Include:

- what the configurator does and the preview-versus-apply distinction;
- the nine-target table with project paths, transports, and command kind;
- per-target setup steps: preview, review the diff, apply if enabled, restart
  the agent, and verify `reposcope` appears as an MCP server;
- the display-only global paths and why they are never written;
- the `REPOSCOPE_HARNESS_APPLY=1` gate, `force` behavior, and what a `409`
  means;
- the OpenCode `mcp.reposcope` schema and the explicit warning that there is no
  `mcp.servers` key;
- the Antigravity dogfood result, or `not installed` with the exact command
  tried;
- troubleshooting for backend unavailable, missing local root, disabled
  writes, changed existing file, and unparseable config;
- a Phase 4 note for the five skills; do not include fabricated `SKILL.md`
  bodies.

---

## 9. Test gate

Run these before you commit. From the repository root:

```powershell
npm --prefix frontend run build
npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json
```

Then, from `frontend/`:

```powershell
npx playwright test tests/e2e/harness.spec.ts
npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"
```

Playwright lives in `frontend/` because that is where its config and tests are.
The config starts a hermetic QA backend on `127.0.0.1:8010` with
`REPOSCOPE_QA=1` and Vite on `127.0.0.1:5183`. The QA backend has
`REPOSCOPE_HARNESS_APPLY` unset, so `apply_enabled` is false. Do not start a
second backend on those ports.

The new `harness.spec.ts` journey must:

- load the `v2_contract` QA fixture (`/api/qa/load-fixture?name=v2_contract`),
  then `page.goto("/")` so the app reads the local path from
  `/api/repo/status`; wait for `[data-testid="local-mode-badge"]` (or another
  stable local-mode signal) before opening the modal, otherwise `localRoot`
  can still be null;
- open the modal from `data-testid="open-harness"` and assert all nine target
  labels/ids are listed;
- preview Claude and assert `.mcp.json`, `mcpServers.reposcope`, and the
  command (including a quoted root if the fixture path contains spaces);
- preview VS Code and assert `servers.reposcope`;
- preview Codex and assert `[mcp_servers.reposcope]`;
- preview OpenCode and assert `mcp.reposcope`; **do not assert `mcp.servers`**;
- preview every one of the nine targets at least once and assert the preview
  pane is non-empty;
- assert the preview never shows a success/write confirmation and that no
  `POST /api/harness/apply` request is made before an explicit write action;
- assert the apply control is disabled and explains that server writes are off
  when `apply_enabled` is false;
- check the modal at 1280×800 for no horizontal overflow (document scroll width
  must not exceed the viewport, and the modal/preview must stay usable);
- assert zero un-whitelisted console/network errors with
  `attachErrorCollector` + `assertNoErrors`;
- capture screenshots through `captureJourney(page, "harness", "...")` so they
  land in `docs/screenshots/v2/harness/`.

If practical, seed a changed `.mcp.json` into a writable QA copy and assert the
diff and `requires_force` UI. If you cannot do that cleanly in the journey,
record the gap in your handoff; backend tests already cover write diffs and
`force`.

J22's 100 ms threshold is fixed. Do not raise it. If J22 fails on this machine,
record the observed numbers and environment as an environmental failure; do not
change the budget. The command above deliberately excludes J22.

Also run:

```powershell
git diff --check
git status --short --branch
```

and confirm no secret, `.env`, `dist/`, `node_modules`, or QA temp file is
staged.

---

## 10. Antigravity dogfood

Try to verify the Antigravity config against a real Antigravity install.

- First check whether it is installed (`Get-Command antigravity` or the
  vendor's documented launcher). If it is not installed, record
  `not installed` with the exact command you tried. Do not claim a pass.
- If it is installed, use a **throwaway copy** of
  `backend/tests/fixtures/v2_contract`, not the committed fixture. Start a
  temporary backend with `REPOSCOPE_HARNESS_APPLY=1`, apply the Antigravity
  config to the copy, open Antigravity, and confirm `reposcope` appears as an
  MCP server. Record the exact steps and result.
- Never write a global Antigravity path. `.agents/skills/` is Phase 4.

The registry handoff already recorded Antigravity as not installed on
2026-10-26. If that is still true, say so plainly in
`docs/AGENT_INTEGRATION.md` and the handoff.

---

## 11. Commit and handoff

Commit locally on `wren/phase-3-harness`:

```text
feat(ui): add nine-agent harness configurator
```

Do **not** push. Do not merge. Do not touch `experimental` or `main`.

Update `docs/coordination/WREN.md` and append a handoff to
`docs/coordination/DIALOGUE.md` with:

- branch and commit hash;
- files changed;
- the verified registry table and any delta from Appendix E;
- commands run and exact results;
- screenshots or a short visual description;
- the Antigravity dogfood result, or why it could not run;
- known limits or skipped checks;
- whether the server contract was sufficient or needs a change.

Then stop and report to the owner. Rook will review the local commit, run the
full backend/frontend/Playwright gate, squash the backend and UI into one Phase
3 commit, and merge `--no-ff` into local `experimental`. `main` stays untouched
until the owner explicitly authorizes it. Nothing is pushed until the owner
explicitly authorizes it.

---

## 12. Definition of done

Phase 3 is done when:

- the modal lists and previews all nine targets from the API;
- the exact files, command, diff, and warnings are visible;
- preview never writes and never shows a write confirmation;
- apply is disabled when `apply_enabled` is false and requires a second
  explicit action plus `force` where needed;
- OpenCode is asserted as `mcp.reposcope`, not `mcp.servers`;
- the 1280×800 layout has no horizontal overflow;
- the L3 journey passes with zero un-whitelisted console errors;
- `docs/AGENT_INTEGRATION.md` documents all nine targets and the Antigravity
  dogfood result;
- screenshots are committed under `docs/screenshots/v2/harness/`;
- one local UI commit exists on `wren/phase-3-harness`, unpushed;
- no backend, MCP tool/resource, `SKILL.md`, packaging, or Phase 4 file is
  changed.

If anything in the contract is missing or wrong, stop and report it. Do not
guess, do not patch the backend, and do not claim a test you did not run.
