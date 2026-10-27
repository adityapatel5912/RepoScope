# HANDOFF PHASE 3 — Wren

**From:** Rook  
**To:** Wren  
**Batch:** Phase 3 only — nine-agent harness configurator  
**Integration branch:** `experimental`  
**Your branch:** `wren/phase-3-harness` in a separate worktree, based on Rook's announced backend commit  
**Status:** **complete.** This file is the historical assignment. The backend
is `69b9620`, Wren's final UI commit is `4a8a5de`, and Rook reviewed, fixed,
squashed, and merged Phase 3 into `experimental` and `main`. See `DIALOGUE.md`
for the final gate, the owner-authorized pushes, and the branch cleanup.

---

## Backend ready (2026-10-27)

- Backend commit: `69b9620 feat(api): add nine-agent harness generator`.
- Branch: `rook/phase-3-harness`, based on `a667ac4`. Local only; not pushed.
- Live contract verified on `127.0.0.1:8011`:
  `GET /api/harness/agents` returns nine ids and `apply_enabled: false`;
  `GET /api/harness/config` returns the exact files, content, diff, and
  command; `POST /api/harness/apply` is a dry run by default and returns
  `403` when `apply: true` is requested with the flag off;
  `GET /api/harness/skills` returns five descriptors with
  `content_available: false`.
- Backend gate: **473 passed, 1 skipped** (Windows file-symlink privilege);
  68 harness tests; `compileall` and `pip check` pass.
- The backend keeps the registry; the UI must not hardcode it.
- OpenCode's verified delta: assert `mcp.reposcope`, not `mcp.servers`.

Create your worktree from the local branch, not from origin:

```bash
git worktree add "../RepoScope-wren-phase3" -b wren/phase-3-harness rook/phase-3-harness
```

Do not push until the owner authorizes it. Do not merge your own branch.

---

## Copy-paste prompt

You are **Wren**, the frontend and verification partner on RepoScope V2.5–V2.8. You are starting **Phase 3 only**. Read `docs/coordination/README.md`, `docs/coordination/DIALOGUE.md`, `docs/coordination/WREN.md`, and plan §6 in `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` before touching code.

### Mission

Add the **nine-agent harness configurator** to the RepoScope frontend. A user opens a modal, picks one of the nine supported agents, sees the exact MCP configuration and command that would be written, reviews a diff for any existing file, and only then chooses to apply it. The default is always a preview; the browser never writes files.

The backend is the only writer. It owns the registry, the exact config formats, path safety, merge behavior, and the apply flag. The frontend consumes that contract; it does not hardcode nine configs or invent a path.

### Start condition and sequence

Phase 3 is **ready**. The owner has signaled it, Wren's registry handoff is
posted in `DIALOGUE.md`, and Rook's backend commit `69b9620` is announced with
live `GET /api/harness/*` responses.

Wren's registry research is complete (2026-10-26). The remaining work is the
UI and verification. Create your branch **from the local
`rook/phase-3-harness` head**, not from `main` or an older `experimental`
head. This is the one cross-branch dependency in the phase: the UI needs the
live preview endpoint.

Order:

```
owner signal + registry handoff (done)
  → Rook backend commit + announcement (done: 69b9620)
  → Wren UI commit on wren/phase-3-harness
  → owner review + permission to push
  → Rook squash and merge into experimental
  → owner permission before main
```

Wren commits but **does not push**. The owner will authorize the push after
review.

### Registry research (done 2026-10-26; frozen)

Wren's registry handoff is posted in `DIALOGUE.md` and is the authority. These
are the paths and shapes the backend now returns.

| Agent | Project file(s) | Notes |
|---|---|---|
| Claude Code | `.mcp.json`, `CLAUDE.md` | `claude mcp add --scope project --transport …` in the preview. |
| Cursor | `.cursor/mcp.json`, `.cursor/rules/reposcope.mdc` | Deep-link command in the preview. |
| VS Code / Copilot | `.vscode/mcp.json` (`servers`), `.github/copilot-instructions.md` | `servers.reposcope`, with `type`. |
| Codex CLI | `.codex/config.toml`, `AGENTS.md` | `[mcp_servers.reposcope]`; no empty parent table. |
| Kiro | `.kiro/settings/mcp.json`, `.kiro/steering/reposcope.md` | Project-scoped. |
| Antigravity | `.agents/mcp_config.json`, `AGENTS.md` | `.agents/skills/` is Phase 4. Also dogfood against RepoScope. |
| Windsurf / Devin | `.devin/mcp_config.json`, `.windsurf/rules/reposcope.md` | Global `~/.codeium/windsurf/mcp_config.json` and `~/.config/devin/mcp_config.json` are display-only. |
| Cline / Roo | `.roo/mcp.json`, `.clinerules` | Global `~/.cline/data/settings/cline_mcp_settings.json` is display-only. |
| OpenCode | `opencode.json` with `mcp.reposcope` | Current schema is `mcp.<name>` with `"type": "local"` or `"remote"`. There is no `mcp.servers` key. |

For each target record:

- `id` and `label`;
- exact project-relative config paths;
- format (`json`, `toml`, or `markdown`);
- supported transport(s), and the default;
- the exact copy-paste command;
- the official docs URL and the section you checked;
- `verified_at` (the date you checked);
- any global path that must be shown but not written;
- any target that cannot be verified. Mark it `unsupported`; do not guess.

Phase 3 must support `stdio` for all nine. `http` is included only where the vendor's official format is verified. If a target has no verified HTTP shape, the API returns `400 unsupported_transport` and the UI disables that option. Do not invent a URL shape.

### Branch and worktree

The backend branch is **local and unpushed**. Create your worktree directly
from it:

```bash
git worktree add "../RepoScope-wren-phase3" -b wren/phase-3-harness rook/phase-3-harness
cd ../RepoScope-wren-phase3
git log --oneline -1
npm --prefix frontend ci
npm --prefix frontend run build
```

`git log --oneline -3` must include `69b9620 feat(api): add nine-agent harness
generator`. The branch head may be a later handoff-docs commit; verify the
backend commit is in your history with `git merge-base --is-ancestor 69b9620
HEAD`. Do not `git fetch origin` for this branch; origin does not have it.
Do not branch from `main` or from an older `experimental` head.

### Files you own

Create:

- `frontend/src/components/HarnessModal.tsx`
- `frontend/src/components/harness/*` (only if splitting keeps the modal readable)
- `frontend/tests/e2e/harness.spec.ts`
- `docs/AGENT_INTEGRATION.md`
- `docs/screenshots/v2/harness/*.png`

Edit:

- `frontend/src/api/client.ts` — add the harness types and calls.
- `frontend/src/App.tsx` — modal state and the entry point.
- `frontend/src/components/TopBar.tsx` — a discoverable “Connect AI agent” entry.
- `docs/coordination/WREN.md` and `docs/coordination/DIALOGUE.md` — claims, progress, handoff.

Do **not** edit:

- `backend/harness_generator.py`, `backend/api/routers/harness.py`, `backend/api/__init__.py`, or `backend/tests/test_harness_*`.
- `docs/API.md` — Rook owns the API reference.
- `frontend/src/components/GraphView.tsx` or `frontend/src/components/mindmap/*`.
- `frontend/package.json` unless a dependency is essential; ask Rook first.
- `main` or `experimental`.

### Frozen API contract

The full contract is in plan §6. The parts you consume:

`GET /api/harness/agents` returns `{agents, apply_enabled}`. Each agent has `id`, `label`, `config_paths`, `transport`, `default_transport`, `global_preview_paths`, `docs_url`, and `verified_at`.

`GET /api/harness/config?agent=<id>&transport=stdio&root=<absolute path>` returns a preview:

```json
{
  "ok": true,
  "agent": "claude",
  "label": "Claude Code",
  "transport": "stdio",
  "root": "D:\\repo",
  "command": "claude mcp add --scope project --transport stdio reposcope -- reposcope-mcp --root \"D:\\repo\"",
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

`POST /api/harness/apply` takes `{agent, transport, root, apply, force}`. `apply: false` is a dry run. `apply: true` writes only after the server confirms the flag and `force` where required. The response adds `applied` and `unchanged` path lists.

`GET /api/harness/skills` returns five descriptors. Phase 3 shows them; it does **not** write `SKILL.md` bodies. That is Phase 4.

If the live response is missing or differs from this contract, stop and report it in `DIALOGUE.md`. Do not patch the backend and do not build against a guessed shape.

### Required behavior

1. **Entry point:** a discoverable “Connect AI agent” control in the top bar or settings, keyboard accessible, with a clear label. It opens the modal without changing the loaded repository.
2. **Agent selection:** all nine targets are listed from the API. Show label, config paths, transport, and docs link. Do not hardcode labels or paths.
3. **Transport:** default to the server's `default_transport`. Disable transports the server does not list for that agent. Show a clear reason when a transport is unsupported.
4. **Preview:** one tab per file. Show the exact content, a copy button, and the exact command. For an existing file, show a unified diff and a `requires_force` warning. Never call apply on preview.
5. **Apply:** disabled unless `apply_enabled` is true. The primary button is “Preview” or “Review changes”; writing requires a second explicit action (“Write files”). Existing files require a `force` checkbox and a visible diff. After apply, show the files written and keep the preview visible.
6. **Root:** use the active repository's local path. If there is no local path, explain that a local repository is required and link to the local-folder flow. Do not ask the user to type a path unless the server explicitly supports it.
7. **Safety:** the browser never writes files and never calls an external URL. All writes go through the backend. No telemetry.
8. **Empty and error states:** no agents, unknown agent, unsupported transport, unsafe root, existing file, apply disabled, and network failure each get a clear message and a retry or dismiss action. Never render a blank modal.
9. **Accessibility:** focus trap, `Escape` closes, ARIA tabs for agents/files, visible focus rings, labelled copy/apply buttons, and no keyboard trap outside the modal.
10. **Layout:** fit 1600×900 and 1280×800 without horizontal overflow. The preview pane scrolls independently; the agent list stays usable.
11. **Performance:** fetch the registry once per open; fetch a preview only when the agent/transport changes; do not re-render all nine previews at once.
12. **Skills:** show the five bundle descriptors from `/api/harness/skills`, marked “available in Phase 4” if content is not present. Do not fabricate skill bodies.
13. **Antigravity dogfood:** if Antigravity is installed, apply its config to a throwaway copy of `backend/tests/fixtures/v2_contract`, open Antigravity, and confirm RepoScope appears as an MCP server. If it is not installed, record `not installed` and the exact command you tried. Do not claim a pass you did not run.

### Test gate

Run all of these before you commit:

```bash
npm --prefix frontend run build
npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json
```

Then, from `frontend/`:

```bash
npx playwright test tests/e2e/harness.spec.ts
npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"
```

Playwright runs from `frontend/` because that is where its config and `tests/` live. J22's 100 ms threshold is fixed; a failure on slow hardware is recorded with its numbers, not “fixed” by changing the budget.

The new Playwright journey must:

- load a QA fixture (`v2_contract` is the fast one);
- open the harness modal and assert all nine targets are listed;
- preview Claude and assert `.mcp.json`, `mcpServers.reposcope`, and the command;
- preview VS Code and assert the `servers` key;
- preview Codex and assert `[mcp_servers.reposcope]`;
- preview OpenCode and assert `mcp.reposcope` (not `mcp.servers`);
- assert the preview never shows a success/write confirmation;
- assert the apply control is disabled when `apply_enabled` is false;
- check the modal at 1280×800 for no horizontal overflow;
- assert zero un-whitelisted console errors.

Backend tests cover the actual writes, diffs, path traversal, and `force` behavior. Do not duplicate those in Playwright.

### Commit and handoff

One commit on your branch:

```text
feat(ui): add nine-agent harness configurator
```

Commit locally and **do not push**:

```bash
git add <your files>
git commit -m "feat(ui): add nine-agent harness configurator"
git log --oneline -1
git status --short --branch
```

Leave `wren/phase-3-harness` local. The owner reviews it and explicitly
authorizes any push. Rook reviews the local commit, squashes the backend and UI
into the single Phase 3 commit, and merges with `--no-ff` into local
`experimental`. Do not merge your branch yourself. `main` stays untouched until
the owner authorizes it separately.

Append a handoff to `docs/coordination/DIALOGUE.md` and update `docs/coordination/WREN.md` with:

- branch and commit hash;
- files changed;
- the verified registry table and any deltas from Appendix E;
- commands run and results;
- screenshots or a short visual description;
- the Antigravity dogfood result, or why it could not run;
- known limits or skipped checks;
- whether the server contract was sufficient or needs a change.

### Non-goals

- No MCP tool or resource changes.
- No `SKILL.md` bodies or `.agents/skills/*` files.
- No npm package, PyPI packaging, or zero-clone work.
- No writes to global agent config paths.
- No LLM call and no network call to validate a config.
- No change to the mind map, graph canvas, citations, tours, or security UI.

### Definition of done

Phase 3 is done when the nine-target registry is verified, the backend gate is green, the modal previews all nine without writing, the apply path is refused unless explicitly enabled, path traversal is rejected, Antigravity is dogfooded or documented as unavailable, the Playwright journey passes, and the phase lands as one commit on `experimental`. `main` is untouched until the owner authorizes it.
