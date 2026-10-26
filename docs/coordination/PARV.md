# PARV — work log and claims

Owner: Parv. Frontend, accessibility, config fixtures, documentation, and
independent verification. This file records claims, commits, tests, and
limits. It is not a substitute for the commit history.

## Current assignment

Wait for the Phase 1 freeze in `DIALOGUE.md`, then start **Phase 2 only**:
the vertical six-pillar mind-map UI against the frozen `GET /api/mindmap`
contract. The self-contained prompt is in `HANDOFF_PHASE_2.md`.

No work has started. No files are claimed.

## Claims

| File | Status | Notes |
|---|---|---|
| — | — | — |

## Preconditions

- Phase 1 commit is on `experimental`.
- `GET /api/mindmap` returns the documented payload.
- `npm --prefix frontend run build` is green on `experimental`.
- Divy has posted the handoff in `DIALOGUE.md`.

## Rules for this batch

- Work in a separate worktree on `parv/phase-2-mindmap`.
- Do not edit backend graph code, the graph schema, or the mind-map API.
- Do not add a second pillar classifier. Consume the server’s `pillar` field.
- Keep `GraphView.tsx` as the dependency-network renderer. Add a separate
  `MindMapView.tsx`; do not rewrite the existing canvas.
- One writer per file. Claim files here before editing.
- Do not commit `.env`, tokens, or generated `dist/` output.
- Merge into `experimental` only after the gate is green and post the handoff.

## Results

Status: waiting for Phase 1 handoff.
