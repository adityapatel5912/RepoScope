# WREN — work log and claims

Owner: Wren. Frontend, accessibility, config fixtures, documentation, and
independent verification. This file records claims, commits, tests, and
limits. It is not a substitute for the commit history.

## Current assignment

Phase 2 completed and merged into `main` at `ff4ac6a` (CI green
`40339282947`).

Phase 3 — nine-agent harness configurator. **Planned, not started.** Start
only after the owner signals Phase 3 and Rook announces the backend commit.
The self-contained prompt is `docs/coordination/HANDOFF_PHASE_3.md`.

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

## Phase 3 — planned, not started

### Assignment

Nine-agent harness configurator UI. Wren owns the nine-target registry
research, fixture validation, `HarnessModal`, the entry point, the L3 journey,
`docs/AGENT_INTEGRATION.md`, and visual evidence. Rook owns the API contract,
generator, apply safety, backend tests, and merge.

Do not start until the owner signals Phase 3 and Rook announces the backend
commit. The self-contained prompt is `HANDOFF_PHASE_3.md`.

### Claims (planned)

| File | Status | Notes |
|---|---|---|
| `docs/AGENT_INTEGRATION.md` | planned | Nine-target setup guide and dogfood results. |
| `frontend/src/components/HarnessModal.tsx` | planned | Agent selector, transport, preview, diff, apply confirmation. |
| `frontend/src/components/harness/*` | planned | Split only if it keeps the modal readable. |
| `frontend/src/api/client.ts` | planned | Harness types and calls; no duplicated config logic. |
| `frontend/src/App.tsx` | planned | Modal state and entry point. |
| `frontend/src/components/TopBar.tsx` | planned | Discoverable “Connect AI agent” entry. |
| `frontend/tests/e2e/harness.spec.ts` | planned | L3 preview, nine agents, no writes, accessibility. |
| `docs/screenshots/v2/harness/*.png` | planned | Visual evidence. |
| `docs/coordination/WREN.md`, `DIALOGUE.md` | done | This planning record. |
| `frontend/package.json` | not claimed | No new dependency expected; ask Rook first if one is needed. |

### Preconditions

- [x] Phase 2 is merged into `main` at `ff4ac6a`; CI is green.
- [ ] Owner has signaled the start of Phase 3.
- [ ] Wren has re-verified the nine target paths/formats/transports against
  official documentation and posted the registry handoff.
- [ ] Rook has announced the backend commit on `rook/phase-3-harness` with
  live `GET /api/harness/agents`, `GET /api/harness/config`, and
  `POST /api/harness/apply` responses.
- [ ] The contract in plan §6 is frozen.
- [ ] `npm --prefix frontend run build` is green before the first UI edit.

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
- Commit on `wren/phase-3-harness`, push that branch only, and post the
  handoff. Rook reviews, squashes the UI commit into the phase commit, and
  merges the phase into `experimental` with `--no-ff`.
- Do not push to `experimental` or `main`.

### Gate

```bash
npm --prefix frontend run build
npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json
cd frontend
npx playwright test tests/e2e/harness.spec.ts
npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"
```

J22's 100 ms threshold is unchanged. A local J22 failure is recorded with its
numbers and is not “fixed” by changing the budget.

### Deliverables

- A discoverable **Connect AI agent** entry that opens `HarnessModal`.
- Nine selectable targets with transport, config paths, command, and docs.
- A preview pane with one tab per file, exact content, and a unified diff for
  existing files.
- Apply disabled unless `REPOSCOPE_HARNESS_APPLY=1`; a second confirmation
  and `force` opt-in for existing files.
- Error states for unknown agent, unsupported transport, unsafe root, existing
  file, and apply-disabled.
- `docs/AGENT_INTEGRATION.md` with copy-paste setup for all nine targets and
  the Antigravity dogfood result.
- Screenshots in `docs/screenshots/v2/harness/`.
- A handoff in `DIALOGUE.md` and this file with branch, commit, commands,
  results, and limits.
