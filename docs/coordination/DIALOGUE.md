# DIALOGUE — Rook ↔ Wren

Append-only. Newest at the bottom. The plan is authoritative; this file
records decisions, handoffs, and verification.

---

## 2026-10-26 — Rook — Plan approved, first batch starts

The owner approved the plan and authorized execution. The first batch is
Phase 0 (CI stabilization) and Phase 1 (graph schema v2, resolver, API
linker, mind-map contract). Wren starts Phase 2 after Phase 1 is frozen.

Baseline: 335 passed locally with Python 3.14; 30 failed / 305 passed on a
clean Python 3.11 install. The known causes are missing `numpy`/`scipy`,
missing `mcp`/`typer`/`watchdog` in `backend/requirements.txt`, `mcp 2.x`
removing `mcp.server.fastmcp.FastMCP`, and the L2 health assertion expecting
`"ok"` from `/api/health`.

Rook claims: `backend/requirements.txt`, `pyproject.toml`,
`.github/workflows/qa.yml`, `backend/main.py`, `backend/graph_store.py`,
`backend/graph_builder.py`, `backend/parse_cache.py`, `backend/symbol_resolver.py`,
`backend/mindmap_classifier.py`, `backend/mindmap.py`,
`backend/api/routers/mindmap.py`, `backend/api/__init__.py`,
`backend/tests/test_dependency_contract.py`, `backend/tests/test_graph_v2.py`,
`backend/tests/test_symbol_resolver.py`, `backend/tests/test_mindmap_classifier.py`,
`backend/tests/test_mindmap_api.py`, `backend/tests/test_health.py`,
`backend/tests/test_graph_golden.py`, `docs/API.md`, `docs/FEATURES.md`,
`docs/QA_REPORT.md`, `CHANGELOG.md`.

Wren: no claims yet. Do not start until the Phase 1 mind-map contract is
announced below.

---

## 2026-10-26 — Rook — Phase 0 gate

Status: in progress.

Planned changes: pin `mcp>=1.29,<2`; declare `numpy`, `scipy`, `typer`,
`watchdog`, and `sse-starlette` in both dependency files; add `pip check`,
`compileall`, a Python 3.11/3.12 matrix, and a frontend build job; fix the
L2 health assertion; add `schema_version` and graph counts to `/api/health`
without changing `status: "healthy"` or `/health`.

Verification will be posted here with exact counts.

---

## 2026-10-26 — Rook — Phase 1 gate

Status: in progress.

Frozen contract: `GET /api/mindmap` as specified in
`docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §4. No client-side pillar
classification. The graph schema is additive: v1 ids and edges stay; new
node fields and `api_calls`/`inherits`/`exports` edges carry evidence.

Wren's first batch is Phase 2, and only Phase 2. The self-contained prompt is
in `HANDOFF_PHASE_2.md`. It is safe to copy into a fresh agent session.

---

## 2026-10-26 — Rook — Handoff 001 to Wren

Branch: `wren/phase-2-mindmap` from `experimental` at the Phase 1 commit.
Scope: the vertical mind-map UI against the frozen `GET /api/mindmap`
contract. Do not edit backend graph code. Do not add a second classifier.

Acceptance: `npm --prefix frontend run build`, `npx tsc --noEmit`, and the
new Playwright journey pass; the dependency network remains the default; no
horizontal overflow at 1600×900 or 1280×800.

When done: commit, merge into `experimental` with `--no-ff`, post the handoff
with the commit hash and commands, and update `WREN.md`.

---

## 2026-10-26 — Rook — Phase 0 complete

`facbf86 chore(ci): restore green baseline and pin runtime dependencies`.

- Pinned `mcp>=1.29,<2`; declared `numpy`, `scipy`, `typer`, `watchdog`, and
  `sse-starlette` in both dependency files.
- CI now runs `pip check`, `compileall`, Python 3.11/3.12, frontend build, and
  extension jobs on `main` and `experimental`.
- `/api/health` adds `schema_version` and cached graph counts without changing
  `status: "healthy"`; `/health` stays `{"status": "ok"}`.
- Verified: **343 passed** on Python 3.11, 3.12, and 3.14 locally; L2 health
  probe passed live.

---

## 2026-10-26 — Rook — Phase 1 complete; CI hermeticity fixes

`d885d92 feat(graph): add schema v2 evidence, resolver, and mind-map contract`.

- Schema v2 is additive; `GET /api/mindmap` is frozen in `docs/API.md` and
  plan §4. Folder ids keep the repository-relative path and do not repeat the
  pillar root.
- Local gate: **405 passed** on Python 3.11, 3.12, and 3.14; frontend build;
  extension 20/20; 17/17 Playwright journeys.
- CI run 40319380840 failed **7 / 398** on both Python versions. The causes
  were test-environment leaks, not product regressions: six endpoint tests
  resolved a real AI provider before their stubbed LLM (CI has no `.env`), and
  one churn test read a one-commit shallow checkout.
- `275d66b fix(ci): isolate endpoint provider resolution and fetch full
  history` adds a synthetic-provider fixture and `fetch-depth: 0`.
- CI run 40320122480 then exposed a stdio test that closed stdin before
  `tools/list` could be read. `25ba011 test(mcp): keep the stdio pipe open
  until every response` makes the harness wait for each response.
- CI run 40320667722 exposed two L3 harness defects: Playwright tried to start
  a second backend on the port `scripts/qa.py` already owned, then the
  harness's process-group cleanup terminated the CI runner. `da0e892` and
  `7c5b467` fix server ownership and process isolation.
- Final CI run 40322052797 is **green on all six jobs** (Python 3.11, Python
  3.12, L2 contract, L3 journeys, frontend build, extension).
- The fixes after `d885d92` are test/CI infrastructure only. They do not
  change the graph schema, the mind-map payload, or any endpoint.

---

## 2026-10-26 — Rook — Handoff 002 to Wren (Phase 2)

Phase 1 is frozen at `d885d92`; `experimental` is CI-green at `7c5b467` plus
this documentation commit.

Branch `wren/phase-2-mindmap` from `origin/experimental` (at or after
`7c5b467`). Scope is Phase 2 only: the vertical six-pillar mind map against
the frozen `GET /api/mindmap` contract in `docs/API.md` and plan §4. Do not
edit backend graph code, do not add a second classifier, and keep
`GraphView.tsx` as the default dependency canvas.

Acceptance: `npm --prefix frontend run build`, `npx tsc --noEmit`, and the new
Playwright journey pass; the dependency network remains the default; no
horizontal overflow at 1600×900 or 1280×800.

When done: commit on `wren/phase-2-mindmap`, push that branch, post the
handoff in this file with the commit hash and commands, and update `WREN.md`.
Rook reviews and merges into `experimental` with `--no-ff`.


---

## 2026-10-26 — Wren — Phase 2 started

Status: in progress.

- Branch `wren/phase-2-mindmap` branched from `origin/experimental` at `699e8b6` in isolated worktree.
- Precondition verified: baseline `npm --prefix frontend run build` passes cleanly.
- Files claimed in `WREN.md`.
- Scope: vertical six-pillar mind-map UI against frozen `GET /api/mindmap` contract. No backend edits, no duplicated classifier, dependency graph remains default.


---

## 2026-10-26 — Wren — Handoff 003 to Rook (Phase 2 complete)

Phase 2 implementation of the vertical six-pillar mind-map UI is complete and verified against the frozen `GET /api/mindmap` contract.

- **Branch & Commit:** `wren/phase-2-mindmap` (branch head at handoff (see git log -1), based on `origin/experimental` at `699e8b6`).
- **Files created:**
  - `frontend/src/components/MindMapView.tsx` (mode container, data fetch, expand/collapse, toolbar, outline)
  - `frontend/src/components/mindmap/MindMapNode.tsx` (canvas node renderer)
  - `frontend/src/components/mindmap/MindMapNodeCard.tsx` (memoized node card, badges, client-side GitHub / IDE / Blast Radius actions)
  - `frontend/src/components/mindmap/MindMapToolbar.tsx` (expand all, collapse all, orientation TB/LR toggle, search input, stats)
  - `frontend/src/components/mindmap/MindMapOutline.tsx` (accessible `<ul role="tree">` mirroring visible tree with full arrow/Enter/Space keyboard navigation)
  - `frontend/src/components/mindmap/MindMapSearch.tsx` (debounced search with live ARIA announcements)
  - `frontend/src/lib/mindmapLayout.ts` (pure tidy-tree layout via `d3-hierarchy` for TB and LR orientations)
  - `frontend/src/lib/mindmapTree.ts` (tree normalization, visible node filtering, ancestor expansion)
  - `frontend/src/lib/mindmapTypes.ts` (types matching frozen schema)
  - `frontend/tests/e2e/mindmap.spec.ts` (Playwright journeys MM01, MM02, MM03)
  - `docs/screenshots/v2/mindmap/*.png` (visual evidence for overview, expanded, outline, LR orientation)
- **Files edited:**
  - `frontend/src/api/client.ts` (`getMindmap()` and payload types)
  - `frontend/src/App.tsx` (view-mode switch `graph` | `mindmap`, default `graph`, key={repo ?? "none"} for clean remount on repo switch)
  - `frontend/src/components/TopBar.tsx` (mode switcher buttons with data-testid and ARIA roles)
  - `frontend/package.json` (added `d3-hierarchy` and `@types/d3-hierarchy`)
  - `docs/coordination/WREN.md` (claims updated and marked done)
- **Verification results:**
  - `npm --prefix frontend run build`: exit 0
  - `tsc --noEmit`: exit 0 (zero errors)
  - `npx playwright test tests/e2e/mindmap.spec.ts`: 3/3 passed (MM01, MM02, MM03)
  - `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"`: 16/16 passed (J22 excluded: pre-existing synthetic 50,000-node scale stress test runs ~103–148 ms vs 100 ms budget on this machine)
- **Manual verification for repository change:**
  Load repo A, expand branches, load repo B, confirm only the root and six pillars are open (reset via `key={repo ?? "none"}` and `sessionStorage` cache isolation).
- **Visual evidence:**
  Screenshots committed in `docs/screenshots/v2/mindmap/`. Interactive browser tested on desktop with live local repository loading.
- **Contract check:**
  Frozen `GET /api/mindmap` contract is fully sufficient and strictly adhered to. No backend edits made.

Ready for Rook to review and merge into `experimental` with `--no-ff`.


---

## 2026-10-26 — Rook — Phase 2 review accepted

Status: accepted; merging into `experimental`.

- Reviewed Wren's amended head `478376d`. Both required fixes are present: the
  mind map remounts on repository change and falls back to root + six pillars
  when the new key has no saved state; the handoff no longer cites a stale
  hash. Item 3 was skipped because Rook had already covered it.
- Gate on the rebased `rook/phase-2-minor`: build pass;
  `tsc --noEmit -p frontend/tsconfig.json` pass; `mindmap.spec.ts` 3/3;
  `journeys.spec.ts` 16/16 with J22 excluded.
- J22 is still an environmental failure on this machine: 165.2/137 ms
  standalone on this head, 103.3/147.8 ms on base `699e8b6`. The 100 ms
  threshold is unchanged.
- Rook's minor fixes are in the commit immediately before the merge:
  selected-state attributes, search-focus and full hierarchy assertions,
  `HEAD` GitHub fallback, route-count badge, and corrected gate commands.
- Merge is `--no-ff` into `experimental`; `main` stays untouched until the
  user tests `experimental`.

---

## 2026-10-26 — Rook — Phase 3 prepared; handoff 004 to Wren

Status: planned, not started. Phase 2 is merged into `main` at `ff4ac6a` and
CI run `40339282947` is green. The owner will signal Phase 3 separately; no
branch, worktree, or code change exists yet.

Phase 3 is the nine-agent harness generator from plan §6. The frozen scope is
in `HANDOFF_PHASE_3.md`:

- **Wren:** re-verify the nine official paths, formats, and transports from
  the vendors' documentation; validate generated configs against real CLIs
  where installed; build `HarnessModal`, the entry point, the Playwright
  journey, `docs/AGENT_INTEGRATION.md`, and screenshots.
- **Rook:** freeze the API contract; implement
  `backend/harness_generator.py`, `backend/api/routers/harness.py`, the
  backend tests, and the docs; review Wren's UI commit; squash it into the
  single phase commit; merge with `--no-ff`.

Sequence: owner signal → Wren registry handoff → Rook backend commit on
`rook/phase-3-harness` → Wren UI commit on `wren/phase-3-harness` based on
that backend commit → Rook review and merge into `experimental`. `main` stays
untouched until the owner authorizes it.

The preview is always available. `apply: true` is refused unless
`REPOSCOPE_HARNESS_APPLY=1`; existing files require a diff and `force: true`;
global paths (Windsurf, Cline) are display-only; no endpoint calls the
network. `GET /api/harness/skills` returns the five skill descriptors only;
the `SKILL.md` bodies are Phase 4.

Acceptance: nine target fixtures, JSON/TOML parsing, path-traversal
rejection, no writes outside the root, nine modal previews without writing,
Antigravity dogfood, L2 API tests, the L3 journey, the full suite, frontend
build, `tsc`, `compileall`, `pip check`, and a green CI run. J22's 100 ms
threshold is unchanged.

No Phase 3 implementation has started.

---

## 2026-10-26 — Wren — Phase 3 registry handoff

Status: complete. Nine targets re-verified against the vendors' current
documentation, with local CLI checks where a tool is installed. Research date
is `2026-10-26`; this is the `verified_at` value in the registry.

### Verified registry

| # | Target | Project MCP file | Format | Transports | Official docs |
|---|---|---|---|---|---|
| 1 | Claude Code | `.mcp.json` + `CLAUDE.md` | JSON `mcpServers` | stdio + Streamable HTTP | https://docs.claude.com/en/docs/claude-code/mcp |
| 2 | Cursor | `.cursor/mcp.json` + `.cursor/rules/reposcope.mdc` | JSON `mcpServers` | stdio + Streamable HTTP | https://cursor.com/docs/context/mcp |
| 3 | VS Code / Copilot | `.vscode/mcp.json` + `.github/copilot-instructions.md` | JSON `servers` | stdio + Streamable HTTP | https://code.visualstudio.com/docs/copilot/customization/mcp-servers |
| 4 | Codex CLI | `.codex/config.toml` + `AGENTS.md` | TOML `[mcp_servers.reposcope]` | stdio + Streamable HTTP | https://developers.openai.com/codex/mcp |
| 5 | Kiro | `.kiro/settings/mcp.json` + `.kiro/steering/reposcope.md` | JSON `mcpServers` | stdio + Streamable HTTP | https://kiro.dev/docs/mcp/configuration/ |
| 6 | Antigravity | `.agents/mcp_config.json` + `AGENTS.md` | JSON `mcpServers` (`serverUrl` for HTTP) | stdio + Streamable HTTP | https://antigravity.google/docs/mcp |
| 7 | Windsurf / Devin | `.devin/mcp_config.json` + `.windsurf/rules/reposcope.md` | JSON `mcpServers` (`serverUrl`/`url` for HTTP) | stdio + Streamable HTTP | https://docs.windsurf.com/windsurf/cascade/mcp |
| 8 | Cline / Roo | `.roo/mcp.json` + `.clinerules` | JSON `mcpServers` (`type: streamable-http` for HTTP) | stdio + Streamable HTTP | https://docs.cline.bot/mcp/configuring-mcp-servers and https://docs.roocode.com/features/mcp/using-mcp-in-roo |
| 9 | OpenCode | `opencode.json` | JSON `mcp.<name>` (`type: local`/`remote`) | stdio + Streamable HTTP | https://opencode.ai/docs/mcp-servers |

All nine support both transports. stdio is the default for every target. The
HTTP entry points at RepoScope's own endpoint, `http://127.0.0.1:8765/mcp`.

### Deltas from plan Appendix E

1. **OpenCode:** the current schema is `mcp.<name>` with `type: local` or
   `type: remote`. There is no `mcp.servers` key. The stale
   `docs/opencode-mcp.json` is corrected in this phase. The L3 journey must
   assert `mcp.reposcope`, not the old nested `mcp.servers` shape.
2. **Windsurf / Devin:** the project file is `.devin/mcp_config.json`;
   project rules use `.windsurf/rules/reposcope.md`. The legacy Cascade global
   path and the new `~/.config/devin/mcp_config.json` are display-only.
3. **Cline / Roo:** Cline's global settings live at
   `~/.cline/data/settings/cline_mcp_settings.json`; the project file written
   here is Roo Code's `.roo/mcp.json`.
4. **Antigravity:** `.agents/skills/` remains Phase 4. Phase 3 writes only
   `.agents/mcp_config.json` and does not fabricate `SKILL.md` bodies.

### Local validation

- Installed and checked: Claude Code, Cursor, VS Code 1.143.1, OpenCode.
  - `claude mcp add --help` confirms `--scope project`, `--transport http`,
    and the `-- <command>` form.
  - Cursor and VS Code both expose `--add-mcp <json>`; VS Code's own help
    states it writes the user profile.
  - `opencode mcp add` confirms `--url` for remote and `-- <command...>` for
    local; project config is the default without `--global`.
- Not installed: Codex CLI, Kiro, Antigravity, Windsurf, Cline. Their configs
  are verified from official docs, not executed. The Antigravity dogfood will
  be recorded as `not installed` with the exact command attempted.

No backend code, contract shape, or UI was touched in this step.

---

## 2026-10-27 — Rook — Phase 3 backend ready; handoff 005 to Wren

Status: backend complete on `rook/phase-3-harness`; UI not started. The
backend commit is `69b9620 feat(api): add nine-agent harness generator`,
based on `a667ac4`. **The branch is local and has not been pushed.** The owner
has asked for no push until permission.

### What shipped

- `backend/harness_generator.py` — the frozen nine-target registry, stdio and
  Streamable HTTP entries, JSON/TOML/markdown merging, path safety, atomic
  writes, preview, and gated apply.
- `backend/api/routers/harness.py` — `GET /api/harness/agents`,
  `GET /api/harness/config`, `POST /api/harness/apply`, and
  `GET /api/harness/skills`, mounted in `backend/api/__init__.py`.
- `backend/tests/test_harness_generator.py` and
  `backend/tests/test_harness_api.py` — 68 harness tests.
- `docs/API.md`, `docs/FEATURES.md`, `CHANGELOG.md`, and
  `docs/opencode-mcp.json` corrected to the current OpenCode `mcp.<name>`
  schema.

### Live responses (server on `127.0.0.1:8011`, root = `v2_contract`)

- `GET /api/health` → `200 {"status": "healthy"}`.
- `GET /api/harness/agents` → `apply_enabled: false`; ids in order:
  `claude, cursor, vscode, codex, kiro, antigravity, windsurf, cline,
  opencode`.
- `GET /api/harness/config?agent=claude&transport=stdio` → files
  `.mcp.json`, `CLAUDE.md`; command:
  `claude mcp add --scope project --transport stdio reposcope -- reposcope-mcp --root "D:\…\v2_contract"`
  (the path is quoted because it contains spaces).
- `GET /api/harness/config?agent=vscode` → `.vscode/mcp.json` with
  `servers.reposcope` and `"type": "stdio"`.
- `GET /api/harness/config?agent=codex` → `.codex/config.toml` with
  `[mcp_servers.reposcope]`; no empty parent table.
- `GET /api/harness/config?agent=opencode&transport=http` → `opencode.json`
  with `mcp.reposcope`, `"type": "remote"`, and the HTTP URL. There is no
  `mcp.servers` key.
- `POST /api/harness/apply` with `apply: false` → `200`, `applied: []`,
  no writes.
- `POST /api/harness/apply` with `apply: true` and the flag off → `403`.
- With `REPOSCOPE_HARNESS_APPLY=1` and a throwaway copy, `apply: true` →
  `200`, `applied: [".mcp.json", "CLAUDE.md"]`, both files present.
- `GET /api/harness/skills` → five descriptors; `content_available: false`.

### Gate

- `python -m pytest -q`: **473 passed, 1 skipped**. The skip is a Windows
  file-symlink creation that needs a privilege; the junction escape test
  runs and passes.
- `python -m compileall -q backend`: pass.
- `pip check`: no broken requirements.
- `git diff --check`: clean.

### Contract note for Wren

The frozen `HANDOFF_PHASE_3.md` test list said “preview OpenCode and assert
nested `mcp.servers`”. That was the old schema. Wren’s registry research is
authoritative: assert `mcp.reposcope` and record the delta. The backend
returns `mcp.reposcope`.

### Next

Wren creates `wren/phase-3-harness` from the local
`rook/phase-3-harness` head, implements the modal, entry point, client, L3
journey, `docs/AGENT_INTEGRATION.md`, and screenshots. The self-contained
prompt is `WREN_PROMPT_PHASE_3.md`. Wren commits on its branch and **does not
push or merge**. Rook reviews and integrates later. No Phase 4 work.

---

## 2026-10-27 — Rook — Phase 3 prompt and handoff docs ready

Status: the backend is frozen at `69b9620`; the handoff documentation and the
self-contained Wren prompt are ready on the local `rook/phase-3-harness`.
Nothing was pushed.

- `docs/coordination/WREN_PROMPT_PHASE_3.md` — the prompt the owner can hand
  to Wren. It contains the start state, branch rule, frozen registry, API
  contract, live responses, UI requirements, test gate, Antigravity dogfood
  step, and the no-push rule.
- `docs/coordination/HANDOFF_PHASE_3.md` — corrected for the verified OpenCode
  `mcp.reposcope` schema, the local-only branch, and the owner's no-push rule.
- `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §6 and Appendix E — corrected for
  the three registry deltas and marked backend-ready.
- `docs/coordination/WREN.md` and `ROOK.md` — updated to backend-ready status.

Wren must branch from the local `rook/phase-3-harness` head, not from
`origin`, commit on `wren/phase-3-harness`, and stop without pushing. Rook will
review and integrate only after the owner has the UI commit and gives
permission. Phase 4 remains out of scope.

---

## 2026-10-27 — Wren — Handoff 006 to Rook (Phase 3 complete)

Phase 3 implementation of the nine-agent harness configurator is complete and fully verified against the frozen `/api/harness/*` backend contract.

- **Branch & Commit:** `wren/phase-3-harness` — final local commit `4a8a5de` (`feat(ui): add nine-agent harness configurator`), based on the frozen backend plus handoff docs at `5d1f3f0`.
- **Files Changed:**
  - *Files created*:
    - `frontend/src/components/HarnessModal.tsx`: accessible dialog with focus trap, Escape dismissal, localRoot requirement empty state, tabs for Agents and Phase 4 Skills.
    - `frontend/src/components/harness/AgentList.tsx`: lists all nine agents from API in frozen registry order with config paths, transports, and official documentation links.
    - `frontend/src/components/harness/PreviewPane.tsx`: one tab per file, exact content with whitespace preservation, copy buttons for command and files, unified diff viewer for modified existing files, warning banner, and gated apply action.
    - `frontend/src/components/harness/DiffViewer.tsx`: color-coded syntax-highlighted unified diff viewer for modified files.
    - `frontend/src/components/harness/SkillsSection.tsx`: Phase 4 preview of 5 architectural skill descriptors.
    - `frontend/tests/e2e/harness.spec.ts`: 4 Playwright tests covering 9-agent preview, OpenCode `mcp.reposcope` (and absence of `mcp.servers`), Claude quoted command, VS Code `servers.reposcope`, Codex `[mcp_servers.reposcope]`, apply disabled validation, unified diff viewer on modified file with visible existing-file warning banner, 1280x800 zero overflow assertion, keyboard focus trap, Escape dismissal, and write confirmation backdrop dismissal block (§7.2).
    - `docs/AGENT_INTEGRATION.md`: comprehensive 9-agent integration guide, copy-paste CLI commands, preview vs apply architecture, REPOSCOPE_HARNESS_APPLY=1 server flag, force rule, OpenCode schema warning, and Antigravity dogfood findings.
    - `docs/screenshots/v2/harness/harness-claude-preview.png`
    - `docs/screenshots/v2/harness/harness-opencode-preview.png`
    - `docs/screenshots/v2/harness/harness-diff-preview.png`
    - `docs/screenshots/v2/harness/harness-skills-preview.png`
    - `docs/screenshots/v2/harness/harness-1280x800-layout.png`
  - *Files edited*:
    - `frontend/src/api/client.ts`: typed harness methods (`getHarnessAgents`, `getHarnessConfig`, `applyHarnessConfig`, `getHarnessSkills`) and response shapes without duplicating backend config logic.
    - `frontend/src/App.tsx`: modal state wiring and localRoot passing.
    - `frontend/src/components/TopBar.tsx`: discoverable `Connect AI agent` button with `data-testid="open-harness"`, accessible keyboard navigation, and responsive label.
    - `docs/coordination/WREN.md`: claims, verification results, and known limits.
    - `docs/coordination/DIALOGUE.md`: this handoff log.

### Verified Registry Table & Deltas from Appendix E

| # | Target | Project MCP file | Format | Transports | Official docs |
|---|---|---|---|---|---|
| 1 | Claude Code | `.mcp.json` + `CLAUDE.md` | JSON `mcpServers` | stdio + Streamable HTTP | https://docs.claude.com/en/docs/claude-code/mcp |
| 2 | Cursor | `.cursor/mcp.json` + `.cursor/rules/reposcope.mdc` | JSON `mcpServers` | stdio + Streamable HTTP | https://cursor.com/docs/context/mcp |
| 3 | VS Code / Copilot | `.vscode/mcp.json` + `.github/copilot-instructions.md` | JSON `servers` | stdio + Streamable HTTP | https://code.visualstudio.com/docs/copilot/customization/mcp-servers |
| 4 | Codex CLI | `.codex/config.toml` + `AGENTS.md` | TOML `[mcp_servers.reposcope]` | stdio + Streamable HTTP | https://developers.openai.com/codex/mcp |
| 5 | Kiro | `.kiro/settings/mcp.json` + `.kiro/steering/reposcope.md` | JSON `mcpServers` | stdio + Streamable HTTP | https://kiro.dev/docs/mcp/configuration/ |
| 6 | Antigravity | `.agents/mcp_config.json` + `AGENTS.md` | JSON `mcpServers` (`serverUrl` for HTTP) | stdio + Streamable HTTP | https://antigravity.google/docs/mcp |
| 7 | Windsurf / Devin | `.devin/mcp_config.json` + `.windsurf/rules/reposcope.md` | JSON `mcpServers` (`serverUrl`/`url` for HTTP) | stdio + Streamable HTTP | https://docs.windsurf.com/windsurf/cascade/mcp |
| 8 | Cline / Roo | `.roo/mcp.json` + `.clinerules` | JSON `mcpServers` (`type: streamable-http` for HTTP) | stdio + Streamable HTTP | https://docs.cline.bot/mcp/configuring-mcp-servers |
| 9 | OpenCode | `opencode.json` | JSON `mcp.<name>` (`type: local`/`remote`) | stdio + Streamable HTTP | https://opencode.ai/docs/mcp-servers |

*Deltas verified*:
1. OpenCode schema: uses `mcp.reposcope` with `type: local` or `remote`. No `mcp.servers` key exists. Asserted in L3 journey.
2. Windsurf/Devin: project config at `.devin/mcp_config.json`, rules at `.windsurf/rules/reposcope.md`.
3. Cline/Roo: project config at `.roo/mcp.json` and `.clinerules`.
4. Antigravity: `.agents/mcp_config.json` generated; `.agents/skills/` remains Phase 4.

### Visual Evidence & Screenshots

Committed under `docs/screenshots/v2/harness/`:
- `harness-claude-preview.png`: Claude Code selected; `.mcp.json` and `CLAUDE.md` tabs; stdio transport; copyable install command with quoted path; disabled Write button explaining server writes disabled.
- `harness-opencode-preview.png`: OpenCode selected; HTTP transport; `opencode.json` tab with `mcp.reposcope` (no `mcp.servers` key).
- `harness-diff-preview.png`: Unified diff viewer for existing modified file showing additions/deletions, warning badge, and force checkbox.
- `harness-skills-preview.png`: Skills tab showing 5 architectural skill descriptors with "Available in Phase 4" badges.
- `harness-1280x800-layout.png`: Modal rendering cleanly at 1280x800 with zero horizontal document overflow, scrollable independent columns.

### Antigravity Dogfood Result

Attempted `Get-Command antigravity`. Command returned `CommandNotFoundException` (exit code 1).
Recorded accurately as **not installed** in `docs/AGENT_INTEGRATION.md` and this log. No global writes or fabricated skills performed.

### Verification Record

- `npm --prefix frontend run build` → exit 0 (built in 11.24s).
- `npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json` → exit 0 (0 errors).
- `npx playwright test tests/e2e/harness.spec.ts` → 4/4 passed (H01, H02, H03, H04 in 44.7s).
- `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"` → 16/16 passed (1.3m).
- `npx playwright test tests/e2e/mindmap.spec.ts` → 3/3 passed (31.8s).
- `python -m pytest -q` → 473 passed, 1 skipped (29.60s).
- `git diff --check` → clean (0 whitespace errors).

### Known Limits & Skipped Checks

1. **J22 Journey Excluded**: Playwright journey J22 is excluded via `--grep-invert "J22"` as instructed in §9. The fixed 100 ms threshold for the synthetic 50,000-node scale benchmark is an environmental failure on this hardware (~103–148 ms vs 100 ms budget).
2. **Windows Symlink Test Skipped in Pytest**: 1 test skipped (`test_symlink_traversal_rejected` in `backend/tests/test_harness_generator.py`) due to Windows unprivileged file-symlink creation privileges; the Windows junction-escape traversal test runs and passes (473 passed, 1 skipped).
3. **Antigravity CLI Not Installed Locally**: `Get-Command antigravity` returned `CommandNotFoundException` (exit code 1); recorded as `not installed` per §10. No global writes or fabricated skill bodies.
4. **Phase 4 Skills Bodies Deferred**: `GET /api/harness/skills` returns `content_available: false`. Five skill descriptors rendered with "Available in Phase 4" badges; `.agents/skills/*` generation is strictly deferred to Phase 4 per §1.
5. **Server Writes Gated by Flag**: `apply_enabled: false` by default and in QA backend (REPOSCOPE_HARNESS_APPLY unset); verified that Write button is disabled with explanatory note.

### Contract Assessment

The frozen `/api/harness/*` contract from Rook was completely deterministic and sufficient. No backend modifications were required.

---

## 2026-10-27 — Rook — Phase 3 review and integration

Reviewed Wren's final UI commit `4a8a5de` against the frozen backend at `69b9620` and the handoff docs at `5d1f3f0`. The commit touched only frontend, tests, docs, and screenshots; no backend, `GraphView.tsx`, `package.json`, MCP tool/resource, or Phase 4 file changed.

### Review findings fixed before the squash

1. **Apply success banner was cleared immediately.** `handleApply()` set the success result and then called `fetchPreview()`, which began by clearing the same result. The preview refresh now preserves the apply result, so the written/unchanged paths stay visible after the refresh.
2. **Initial focus stayed behind the dialog.** The modal trapped Tab and restored focus on close, but never moved focus inside on open. The dialog panel now receives focus on mount, Shift+Tab from the panel is trapped, and focus restoration is asserted.
3. **Nine-target preview assertions were too weak.** The loop clicked all nine rows but only checked that the pane was still visible, which could pass on stale content. It now asserts each target's own file tab and exact preview token.
4. **The force gate was not exercised.** H02 now enables server writes in the intercepted preview response only, seeds an existing `.mcp.json`, asserts the warning, diff, force checkbox, disabled Write button before the checkbox, enabled action after it, and the second confirmation. It cancels without a POST.
5. **No regression test for the success-banner bug.** H05 mocks the apply POST and asserts the success banner survives the post-write preview refresh.
6. **Documentation corrections.** The integration guide's command-kind table now matches the registry (Cursor `deeplink`, Codex `install`), and the coordination logs cite Wren's actual final commit `4a8a5de`, not the stale `b3e1582`.

### Final independent gate

- `npm --prefix frontend run build` → pass.
- `npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json` → pass, 0 errors.
- `npx playwright test tests/e2e/harness.spec.ts` → **5/5 passed** (H01–H05).
- `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"` → **16/16 passed**.
- `npx playwright test tests/e2e/mindmap.spec.ts` → **3/3 passed**.
- `python -m pytest -q` → **473 passed, 1 skipped**.
- `python -m compileall -q .` → clean; `pip check` → no broken requirements.
- `git diff --check` → clean.

J22 remains excluded because of its unchanged 100 ms threshold and the recorded environmental timings. The Windows symlink test remains the single skip. Antigravity remains recorded as **not installed** from the prior `Get-Command antigravity` check.

### Integration

The backend commit `69b9620`, handoff docs `5d1f3f0`, Wren's UI commit `4a8a5de`, and the review fixes above were squashed into one Phase 3 commit and merged into local `experimental` with `--no-ff`. The owner authorized pushing `experimental` on 2026-10-27. `main` remained untouched until the owner authorized the main merge.

---

## 2026-10-27 — Rook — Phase 3 merged into main

The owner authorized the main merge and branch cleanup. `experimental` was
merged into `main` with `--no-ff` at `4d39537`, and both branches now carry
the same Phase 3 tree. The local feature branches `rook/phase-3-harness`,
`rook/phase-3-integration`, `wren/phase-3-harness`, and `nine_agent_harness_ui`
were deleted. The remote already contained only `main` and `experimental`; the existing
tags were left in place.
