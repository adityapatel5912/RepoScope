# WREN — work log and claims

Owner: Wren. Frontend, accessibility, config fixtures, documentation, and
independent verification. This file records claims, commits, tests, and
limits. It is not a substitute for the commit history.

## Current assignment

Phase 2 completed and merged into `main` at `ff4ac6a` (CI green
`40339282947`).

Phase 3 — nine-agent harness configurator. **Complete; reviewed and merged
into `experimental` and `main` by Rook.** The final UI commit is `4a8a5de`; Rook added the
review fixes, the force-gate assertion, and H05, then squashed the backend,
handoff docs, UI, and fixes into one Phase 3 commit. The self-contained prompt
is `docs/coordination/WREN_PROMPT_PHASE_3.md`.

## Claims

| File | Status | Notes |
|---|---|---|
| `frontend/src/components/MindMapView.tsx` | done | Mode container, data fetch, expand/collapse, toolbar, outline |
| `frontend/src/components/mindmap/MindMapNode.tsx` | done | Canvas node renderer and connector anchor |
| `frontend/src/components/mindmap/MindMapNodeCard.tsx` | done | Node card UI, badges, file actions, blast radius |
| `frontend/src/components/mindmap/MindMapToolbar.tsx` | done | Expand/collapse controls, TB/LR toggle, search input, stats |
| `frontend/src/components/mindmap/MindMapOutline.tsx` | done | Accessible `<ul role="tree">` alternative and keyboard navigation |
| `frontend/src/components/mindmap/MindMapSearch.tsx` | done | Debounced search and query state |
| `frontend/src/lib/mindmapLayout.ts` | done | Pure tidy-tree layout for TB and LR orientations |
| `frontend/src/lib/mindmapTree.ts` | done | Tree normalization, visible node filtering, ancestor expansion |
| `frontend/src/lib/mindmapTypes.ts` | done | Pure TypeScript definitions matching backend frozen schema |
| `frontend/tests/e2e/mindmap.spec.ts` | done | L3 Playwright journeys for Phase 2 |
| `frontend/src/api/client.ts` | done | Added `getMindmap()` and typed payload |
| `frontend/src/App.tsx` | done | Added view-mode switch (`graph` \| `mindmap`), default `graph` |
| `frontend/src/components/TopBar.tsx` | done | Exposed view-mode switch |
| `frontend/package.json` | done | Added `d3-hierarchy` and `@types/d3-hierarchy` for tidy-tree layout |

## Preconditions

- [x] Phase 1 commit is on `experimental` (`d885d92`) and the contract is
  frozen.
- [x] `GET /api/mindmap` returns the documented payload (`docs/API.md` and
  plan §4).
- [x] `npm --prefix frontend run build` is green on `experimental`.
- [x] CI run
  [40322052797](https://github.com/adityapatel5912/RepoScope/actions/runs/40322052797)
  is green on all six jobs at `7c5b467`.
- [x] Rook has posted the handoff in `DIALOGUE.md`.

## Rules for this batch

- Work in a separate worktree on `wren/phase-2-mindmap`.
- Do not edit backend graph code, the graph schema, or the mind-map API.
- Do not add a second pillar classifier. Consume the server’s `pillar` field.
- Keep `GraphView.tsx` as the dependency-network renderer. Add a separate
  `MindMapView.tsx`; do not rewrite the existing canvas.
- One writer per file. Claim files here before editing.
- Do not commit `.env`, tokens, or generated `dist/` output.
- Commit on `wren/phase-2-mindmap`, push the branch, and post the handoff.
  Rook reviews and merges into `experimental`; do not push to `experimental`.

## Results

- **Status:** handed-off to Rook for review and merge.
- **Branch & Commit:** `wren/phase-2-mindmap` (branch head at handoff (see git log -1), based on `origin/experimental` at `699e8b6`).
- **Gate verification:**
  - `npm --prefix frontend run build` → exit 0.
  - `npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json` → exit 0 (0 errors).
  - `npx playwright test tests/e2e/mindmap.spec.ts` → 3 passed.
  - `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"` → 16/16 passed (J22 excluded: pre-existing synthetic 50,000-node scale stress test runs ~103–148 ms vs 100 ms budget on this machine).
- **Screenshots:**
  Committed to `docs/screenshots/v2/mindmap/`:
  - `mindmap-overview.png`: first paint with root and six pillars.
  - `mindmap-expanded.png`: hierarchical expansion through pillar, folders, files, and symbols.
  - `mindmap-outline.png`: semantic accessible `<ul role="tree">` outline and keyboard focus.
  - `mindmap-lr.png`: horizontal (LR) orientation.
  - `mindmap-multilang.png`: Playwright fixture journey.
- **Manual verification for repository change:**
  Load repo A, expand branches, load repo B, confirm only the root and six pillars are open (reset via `key={repo ?? "none"}` and `sessionStorage` cache isolation).
- **Known limits:**
  Mind map is server-backed. When browser preview is active, a limitation banner warns the user and provides a one-click button back to Dependency Graph.
- **Server contract assessment:**
  The Phase 1 contract (`GET /api/mindmap`) was completely sufficient and deterministic; no contract modifications or backend changes were needed.

---

## Phase 3 — backend ready; UI not started

### Assignment

Nine-agent harness configurator UI. Wren owns the nine-target registry
research, fixture validation, `HarnessModal`, the entry point, the L3 journey,
`docs/AGENT_INTEGRATION.md`, and visual evidence. Rook owns the API contract,
generator, apply safety, backend tests, and merge.

The backend is ready at `69b9620` on the local `rook/phase-3-harness`. The
self-contained prompt is `WREN_PROMPT_PHASE_3.md`.

### Claims

| File | Status | Notes |
|---|---|---|
| `docs/AGENT_INTEGRATION.md` | done | Nine-target setup guide and dogfood results. |
| `frontend/src/components/HarnessModal.tsx` | done | Agent selector, transport, preview, diff, apply confirmation. |
| `frontend/src/components/harness/AgentList.tsx` | done | Keyboard-accessible list of nine agents with transports and docs. |
| `frontend/src/components/harness/PreviewPane.tsx` | done | File tabs, whitespace-preserving pre, copy buttons, gated apply. |
| `frontend/src/components/harness/DiffViewer.tsx` | done | Unified diff viewer with syntax highlights and change alerts. |
| `frontend/src/components/harness/SkillsSection.tsx` | done | Phase 4 preview of 5 architectural skill descriptors. |
| `frontend/src/api/client.ts` | done | Harness types and calls; no duplicated config logic. |
| `frontend/src/App.tsx` | done | Modal state and entry point. |
| `frontend/src/components/TopBar.tsx` | done | Discoverable “Connect AI agent” entry. |
| `frontend/tests/e2e/harness.spec.ts` | done | L3 preview, nine agents, diff viewer, no writes, accessibility. |
| `docs/screenshots/v2/harness/*.png` | done | Visual evidence (5 screenshots). |
| `docs/coordination/WREN.md`, `DIALOGUE.md` | done | Coordination and handoff. |
| `frontend/package.json` | not modified | Zero new dependencies added. |

### Preconditions

- [x] Phase 2 is merged into `main` at `ff4ac6a`; CI is green.
- [x] Owner has signaled the start of Phase 3.
- [x] Wren has re-verified the nine target paths/formats/transports against
  official documentation and posted the registry handoff.
- [x] Rook has announced the backend commit on `rook/phase-3-harness` with
  live `GET /api/harness/agents`, `GET /api/harness/config`, and
  `POST /api/harness/apply` responses. Backend commit: `69b9620`.
- [x] The contract in plan §6 is frozen, with the verified registry deltas.
- [x] `npm --prefix frontend run build` is green before the first UI edit.

**Ready to start.** Use `WREN_PROMPT_PHASE_3.md`. Branch from the local
`rook/phase-3-harness` head; do not fetch the unpushed branch from origin.
Commit on `wren/phase-3-harness` only. Do not push, do not merge, and do not
touch `experimental` or `main`.

### Rules for this batch

- Branch `wren/phase-3-harness` from Rook's announced backend commit in a
  separate worktree. Do not branch from `main`.
- Consume `/api/harness/agents` and `/api/harness/config`; do not hardcode the
  nine configs or duplicate path/format logic in the browser.
- Never call `apply: true` without an explicit user confirmation. The default
  is preview.
- Never write files from the browser. The backend is the only writer.
- Do not edit `backend/harness_generator.py`, the harness router, or the
  backend tests.
- Do not add `SKILL.md` bodies, MCP tools/resources, or Phase 4 work.
- One writer per file. Claim files here before editing.
- Commit on `wren/phase-3-harness` and post the handoff. **Do not push.**
  The owner reviews the local commit and authorizes any push. Rook reviews,
  squashes the UI commit into the phase commit, and merges the phase into
  local `experimental` with `--no-ff`.
- Do not merge your own branch. Do not touch `main`.

### Gate Verification

- `npm --prefix frontend run build` → exit 0 (built in 11.24s).
- `npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json` → exit 0 (0 errors).
- `npx playwright test tests/e2e/harness.spec.ts` → 4/4 passed (H01, H02, H03, H04 in 44.7s).
- `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"` → 16/16 passed (1.3m).
- `npx playwright test tests/e2e/mindmap.spec.ts` → 3/3 passed (31.8s).
- `python -m pytest -q` → 473 passed, 1 skipped (29.60s).

### Results

- **Status:** Complete, verified locally on `wren/phase-3-harness`. Handoff posted to Rook.
- **Branch & Commit:** `wren/phase-3-harness` — final local commit `4a8a5de` (`feat(ui): add nine-agent harness configurator`), based on the frozen backend plus handoff docs at `5d1f3f0`.
- **Files created:**
  - `frontend/src/components/HarnessModal.tsx`
  - `frontend/src/components/harness/AgentList.tsx`
  - `frontend/src/components/harness/PreviewPane.tsx`
  - `frontend/src/components/harness/DiffViewer.tsx`
  - `frontend/src/components/harness/SkillsSection.tsx`
  - `frontend/tests/e2e/harness.spec.ts`
  - `docs/AGENT_INTEGRATION.md`
  - `docs/screenshots/v2/harness/harness-claude-preview.png`
  - `docs/screenshots/v2/harness/harness-opencode-preview.png`
  - `docs/screenshots/v2/harness/harness-diff-preview.png`
  - `docs/screenshots/v2/harness/harness-skills-preview.png`
  - `docs/screenshots/v2/harness/harness-1280x800-layout.png`
- **Files edited:**
  - `frontend/src/api/client.ts`
  - `frontend/src/App.tsx`
  - `frontend/src/components/TopBar.tsx`
  - `docs/coordination/WREN.md`
  - `docs/coordination/DIALOGUE.md`
- **Visual evidence & screenshots:**
  - `harness-claude-preview.png`: Claude Code selected; `.mcp.json` and `CLAUDE.md` tabs; stdio transport; copyable install command with quoted path; disabled Write button explaining server writes disabled.
  - `harness-opencode-preview.png`: OpenCode selected; HTTP transport; `opencode.json` tab with `mcp.reposcope` (no `mcp.servers` key).
  - `harness-diff-preview.png`: Unified diff viewer for existing modified file showing additions/deletions, warning badge, and force checkbox.
  - `harness-skills-preview.png`: Skills tab showing 5 architectural skill descriptors with "Available in Phase 4" badges.
  - `harness-1280x800-layout.png`: Modal rendering cleanly at 1280x800 with zero horizontal document overflow, scrollable independent columns.
- **Antigravity Dogfood:**
  - Command: `Get-Command antigravity`
  - Result: `CommandNotFoundException` (exit code 1). Recorded as `not installed`. No global writes or fabricated skills performed.
- **Known limits & skipped checks:**
  1. J22 excluded from journey suite as instructed in §9 (pre-existing synthetic 50,000-node scale benchmark with fixed 100 ms threshold; environmental on this hardware running ~103–148 ms).
  2. 1 skipped test in pytest out of 474 due to Windows unprivileged symlink creation privileges (`test_symlink_traversal_rejected`); junction-escape test passes.
  3. Antigravity dogfood recorded as `not installed` (`Get-Command antigravity` returned `CommandNotFoundException`); no global writes or fabricated skills.
  4. Phase 4 skills bodies deferred per §1: `GET /api/harness/skills` returns `content_available: false`; `.agents/skills/*` generation not implemented.
  5. Server writes disabled by default (`apply_enabled: false` in QA/default mode without `REPOSCOPE_HARNESS_APPLY=1`), verified by test asserting the Write button is disabled.
- **Contract check:**
  - The frozen `/api/harness/*` contract from Rook was completely deterministic and sufficient. No backend modifications were required.


---

## Phase 4 — token-compact context, MCP surface, and skills

### Assignment
End-to-end execution of Phase 4 per `docs/coordination/WREN_PROMPT_PHASE_4.md`.
- `backend/context_compressor.py`: AST skeleton, deterministic context pack, budget accounting, SHA-256 delta hash, lazy TOON adapter.
- `backend/skill_library.py` plus ten checked-in SKILL.md copies under `.claude/skills/<id>/` and `.agents/skills/<id>/`.
- `GET /api/context/pack` in `backend/api/routers/context.py` and router mount in `backend/api/__init__.py`.
- Five new MCP tools and three new MCP resources in `backend/mcp_server/tools.py` and `server.py`.
- Harness preview/apply support for skill files in `backend/harness_generator.py`.
- Frontend Skills panel update and harness browser journey in `frontend/tests/e2e/harness.spec.ts`.
- Measured TOON benchmark and documentation updates.

### Claims

| File | Status | Notes |
|---|---|---|
| `backend/context_compressor.py` | released | AST skeleton, context pack, hash, TOON adapter |
| `backend/skill_library.py` | released | Canonical skill bodies and validation |
| `.claude/skills/<id>/SKILL.md` (5 files) | released | Checked-in skill copies |
| `.agents/skills/<id>/SKILL.md` (5 files) | released | Checked-in skill copies |
| `backend/api/routers/context.py` | released | `GET /api/context/pack` endpoint |
| `backend/api/__init__.py` | released | Mount context router |
| `backend/mcp_server/tools.py` | released | 5 new tools + api_routes helper |
| `backend/mcp_server/server.py` | released | MCP tool wrappers and 3 resources |
| `backend/harness_generator.py` | released | Skill file preview/apply for Claude and Antigravity |
| `frontend/src/api/client.ts` | released | HarnessSkill content property |
| `frontend/src/components/harness/SkillsSection.tsx` | released | Ready badge and SKILL.md preview |
| `frontend/tests/e2e/harness.spec.ts` | released | Skills preview tests |
| `benchmarks/toon_benchmark.py` | released | TOON corpus benchmark runner |
| `docs/MCP.md` | released | Complete MCP reference |
| `docs/TOON_BENCHMARK.md` | released | Measured benchmark results |
| `docs/API.md`, `docs/AGENT_INTEGRATION.md`, `docs/FEATURES.md`, `README.md`, `CHANGELOG.md` | released | Documentation updates |
| `pyproject.toml`, `.github/workflows/qa.yml` | released | Module and optional dependency updates |
| `backend/tests/test_context_compressor.py` | released | Context compressor tests |
| `backend/tests/test_context_api.py` | released | Context API tests |
| `backend/tests/test_skill_library.py` | released | Skill library tests |
| `backend/tests/test_mcp_v25.py` | released | MCP v25 tests |
| `backend/tests/test_mcp_server.py` | released | Update expected tools/resources |
| `backend/tests/test_harness_generator.py`, `test_harness_api.py` | released | Harness generator/API skill tests |

### Baseline verification
- `python -m pytest -q`: 473 passed, 1 skipped.
- `python -m compileall -q backend`: clean.
- `python -m pip check`: clean.
- `npm --prefix frontend run build`: pass.
- `npx playwright test tests/e2e/harness.spec.ts`: 5/5 passed.

### Handoff Details

1. **Branch & Commit**:
   - Branch: `wren/phase-4-context`
   - Implementation commit: `bb4b268` (`feat(context): add skeleton, context packs, TOON flag, and MCP tools`)
   - Base commit: `rook/phase-4-context` (`5b881b4`), base `main` (`7ff5291`).

2. **Files Changed & Claims Released**:
   - All 23 claimed files released (see table above).
   - 10 checked-in `SKILL.md` files (5 in `.claude/skills/`, 5 in `.agents/skills/`).
   - Final MCP surface: exactly 13 tools and 8 resources.
   - TOON compression documented without 85% claim.

3. **Commands Run & Gate Results**:
   - `python -m pytest -q`: **508 passed, 1 skipped** in 67.85s (Windows symlink test is expected skip).
   - `python -m compileall -q backend`: clean (0 errors).
   - `python -m pip check`: clean (`No broken requirements found`).
   - `npm --prefix frontend run build`: built in 43.01s (clean).
   - `npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json`: clean (0 errors).
   - `npx playwright test tests/e2e/harness.spec.ts`: **5/5 passed** (1.9m).
   - `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"`: **16/16 passed** (3.7m).
   - `npx playwright test tests/e2e/mindmap.spec.ts`: **3/3 passed** (40.7s).
   - `git diff --check`: clean (0 whitespace/conflict errors).

4. **Measured TOON Benchmark Results**:
   - Corpus: 5 real open-source repositories (`requests` @ `3c7baaa`, `flask` @ `d086db8`, `httpx` @ `b5addb6`, `express` @ `1c6f1b0`, `got` @ `05b4476`).
   - `requests`: 7,855 -> 4,796 tokens (**+38.94%** saving, roundtrip PASS).
   - `flask`: 7,696 -> 4,664 tokens (**+39.40%** saving, roundtrip PASS).
   - `httpx`: 8,078 -> 4,931 tokens (**+38.96%** saving, roundtrip PASS).
   - `express`: 7,106 -> 4,702 tokens (**+33.83%** saving, roundtrip PASS).
   - `got`: 5,332 -> 3,088 tokens (**+42.09%** saving, roundtrip PASS).
   - **Median Token Saving**: **+39.0%** (38.96%) over compact JSON.
   - **Median Byte Saving**: **+26.6%** (26.65%).
   - **Roundtrip Equality**: 5/5 PASS (100% loss-free representation).
   - Decision: Compact JSON default; TOON opt-in; no unverified 85% claim.

5. **Known Limits & Skips**:
   - J22 journey test excluded: pre-existing synthetic 50,000-node scale stress test runs ~103–148 ms vs 100 ms budget on this Windows machine.
   - Windows symlink test skipped in `test_harness_generator.py` (requires elevated privileges/Developer Mode on Windows).

6. **Next Open Decision**:
   - Phase 4 implementation is complete and ready for Rook to create a verification worktree, review the diff, run the gate, and request owner authorization to merge.
