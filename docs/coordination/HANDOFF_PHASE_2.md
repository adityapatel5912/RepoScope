# HANDOFF PHASE 2 — Wren

**From:** Rook  
**To:** Wren  
**Batch:** Phase 2 only — vertical six-pillar mind-map UI  
**Integration branch:** `experimental`  
**Your branch:** `wren/phase-2-mindmap` in a separate worktree  
**Status:** ready to start — Phase 1 is frozen at `d885d92`; CI is green at `7c5b467` on all six jobs. Branch from `origin/experimental`, not `main`.

---

## Copy-paste prompt

You are **Wren**, the frontend and verification partner on RepoScope V2.5–V2.8. You are starting **Phase 2 only**. Read `docs/coordination/README.md`, `docs/coordination/DIALOGUE.md`, and `docs/coordination/WREN.md` before touching code.

### Mission

Add a separate vertical six-pillar mind-map view to the existing RepoScope frontend. The dependency-network canvas must remain the default and must not be rewritten. The mind map is a strict hierarchy:

```
root → pillar → folder → file → symbol
```

The backend’s frozen endpoint is:

```
GET /api/mindmap?include_symbols=true&max_nodes=20000
```

The exact payload contract is in `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §4, “Mind-map API contract”, and in `docs/API.md` under `GET /api/mindmap`. Do not infer it from `graph_builder.py`, and do not duplicate classification in the browser. The server’s `pillar`, `role`, `path`, `line`, `end_line`, `route_count`, and `children` fields are authoritative.

The contract is frozen at Phase 1 (`d885d92`). CI is green at `7c5b467` on Python 3.11, Python 3.12, L2 contract, L3 journeys, frontend build, and extension. If the endpoint does not match the documented payload, stop and report it; do not patch the backend.

If the endpoint is missing or returns a different shape, stop and report it in `docs/coordination/DIALOGUE.md`. Do not build against a guessed contract.

### Branch and worktree

1. Fetch `experimental` from origin and confirm `git log --oneline -1` is `7c5b467` or later.
2. Create a separate worktree for `wren/phase-2-mindmap`; do not work in Rook’s checkout.
3. Confirm `npm --prefix frontend run build` is green before you change anything.
4. Claim your files in `docs/coordination/WREN.md` before editing.

Suggested commands (run from the RepoScope root, adapt paths to your machine):

```bash
git fetch origin
git worktree add ../RepoScope-wren -b wren/phase-2-mindmap origin/experimental
cd ../RepoScope-wren
npm --prefix frontend ci
npm --prefix frontend run build
```

### Files you own

Create:

- `frontend/src/components/MindMapView.tsx`
- `frontend/src/components/mindmap/MindMapNode.tsx`
- `frontend/src/components/mindmap/MindMapToolbar.tsx`
- `frontend/src/components/mindmap/MindMapOutline.tsx`
- `frontend/src/components/mindmap/MindMapSearch.tsx`
- `frontend/src/components/mindmap/MindMapNodeCard.tsx` (only if it keeps `MindMapNode` readable)
- `frontend/src/lib/mindmapLayout.ts`
- `frontend/src/lib/mindmapTree.ts`
- `frontend/src/lib/mindmapTypes.ts` (types only)
- `frontend/tests/e2e/mindmap.spec.ts`
- `frontend/src/lib/__tests__/mindmapTree.test.ts` only if you add Vitest; otherwise test pure logic through the Playwright journey and document why.

Edit:

- `frontend/src/api/client.ts` — add `getMindmap()` and the payload types.
- `frontend/src/App.tsx` — add a view-mode switch (`graph` | `mindmap`), default `graph`.
- `frontend/src/components/TopBar.tsx` — expose the switch if that is the cleanest place.
- `frontend/package.json` — add only `d3-hierarchy` and `@types/d3-hierarchy` if you use it. `dagre` is already installed; do not add a second layout engine unless you document why.
- `docs/coordination/WREN.md` and `docs/coordination/DIALOGUE.md` — claims, progress, handoff.

Do **not** edit:

- `backend/graph_builder.py`, `backend/graph_store.py`, `backend/mindmap*`, or the API contract.
- `frontend/src/components/GraphView.tsx` beyond a minimal integration prop if absolutely necessary. Prefer keeping it untouched.
- `frontend/src/components/ChatPanel.tsx` in this phase.
- `main`.

### Required behavior

1. **Default view:** the existing dependency network still renders first. Add a clear `Graph` / `Mind Map` switch.
2. **First paint:** only the root and the six pillars are expanded. The initial payload may contain the full tree; hidden branches are not rendered. Do not render thousands of cards at once.
3. **Expand/collapse:** pillar → folder → file → symbols. Persist the expanded set in `sessionStorage`, keyed by repository. A repository change resets it.
4. **Layout:** TB by default; toolbar toggle to LR. Use a tidy-tree layout with stable node sizes. Smooth connectors. No horizontal overflow at 1600×900 or 1280×800.
5. **Search:** debounced; matches label and path; auto-expands ancestors; focuses the first result; `Escape` closes. The result count is announced.
6. **Outline:** a semantic `<ul role="tree">` alternative mirrors the visible tree. Arrow keys move, `Enter` expands, `Space` selects. Every node has an accessible name.
7. **File actions:** GitHub, VS Code/Cursor, Blast Radius. Build URLs client-side from the repository owner/name, branch, and local root. Do not ask the server for `github_url` or `vscode_uri`.
8. **Blast Radius:** reuse the existing impact API. Highlight direct callers amber and transitive callers cyan. A second click clears the highlight.
9. **Roles and routes:** show the server’s `role` as a readable badge and `route_count` when non-zero. Do not invent roles.
10. **Empty and error states:** if `nodes.length === 0`, show a clear empty state. If the fetch fails, show the API error hint and a retry button. Never render a blank white panel.
11. **Performance:** memoize node cards, avoid a layout recomputation on every keystroke, and keep expand/collapse under 100 ms on the RepoScope repository.
12. **Browser preview:** the mind map is server-backed. When a browser-preview folder is active, show the same “preview” limitation as the other server-backed panels or disable the mode with a reason.

### Test gate

Run all of these before you commit:

```bash
npm --prefix frontend run build
npm --prefix frontend exec tsc -- --noEmit
npm --prefix frontend exec playwright test tests/e2e/mindmap.spec.ts
npm --prefix frontend exec playwright test tests/e2e/journeys.spec.ts
```

The new Playwright journey must:

- load the `multilang` QA fixture;
- switch to Mind Map;
- assert the six pillars are visible and the dependency canvas is hidden;
- expand the backend pillar, then a folder, then a file;
- search for `helpers.py`, assert the result focuses, and assert the outline mirrors the tree;
- toggle TB/LR and assert the layout does not overflow;
- assert zero un-whitelisted console errors.

If Playwright cannot run in your environment, say exactly which step failed and attach the command output. Do not claim a pass you did not run.

### Commit and handoff

One commit for Phase 2:

```
feat(ui): add vertical six-pillar mind map
```

Push the child branch only; Rook is the integrator and will merge it into
`experimental` with `--no-ff` after reviewing the gate:

```bash
git push -u origin wren/phase-2-mindmap
```

Do not push to `experimental`. Then append a handoff to
`docs/coordination/DIALOGUE.md` and update `docs/coordination/WREN.md` with:

- branch and commit hash;
- files changed;
- commands run and results;
- screenshots or a short visual description;
- known limits or skipped checks;
- whether the server contract was sufficient or needs a change.

Do not edit `main`. Do not force-push. Do not merge another phase into this branch.
