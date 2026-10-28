# COMS - Phase 4 coordination board

This is the live claim and status board for Phase 4. `DIALOGUE.md` is the
append-only decision log; `ROOK.md` and `WREN.md` are the per-agent work logs.
Git commits, tests, and the frozen contracts are the source of truth.

## Phase status

| Field | Value |
|---|---|
| Phase | 4 - token-compact context, MCP surface, and skills |
| Release | V2.5 |
| Planning branch | `rook/phase-4-context` at `5b881b4` (local, unpushed) |
| Implementation branch | `wren/phase-4-context` at `cae15fb` |
| Verification branch | `rook/phase-4-review` at `74bd2fb`, based on `cae15fb` |
| Implementation worktree | `D:\Aditya\Hackathon Projects\RepoScope-wren-phase4` |
| Verification worktree | `D:\Aditya\Hackathon Projects\RepoScope-rook-phase4-verify` |
| Base | `main` at `7ff5291` (Phase 3 merged) |
| Contract status | frozen |
| Implementation status | `verified` |
| Review status | `complete` |
| Merge status | `merged into main at 74bd2fb; pushed to origin/main` |

## Ownership

| Area | Owner | Status |
|---|---|---|
| Planning documents, contract, prompt | Rook | `done` |
| `backend/context_compressor.py` | Wren | `done` |
| `backend/skill_library.py` and ten checked-in `SKILL.md` copies | Wren | `done` |
| `backend/api/routers/context.py` and router mount | Wren | `done` |
| `backend/mcp_server/tools.py` and `server.py` Phase 4 surface | Wren | `done` |
| `backend/harness_generator.py` skill preview/apply | Wren | `done` |
| Frontend `SkillsSection` and browser journey | Wren | `done` |
| TOON benchmark and measured documentation | Wren | `done` |
| Full test gate, diff review, merge | Rook | `done` |
| `main` merge and push | Owner authorized; Rook executed | `done` |
| `experimental` | Unchanged at `7ff5291`; not in Phase 4 scope | `not-in-scope` |

## Frozen surface

- 13 MCP tools and 8 MCP resources. The existing 8 tools and 5 resources keep
  their names, signatures, and URIs.
- New tools: `get_mindmap_hierarchy`, `get_ast_skeleton`, `get_context_pack`,
  `diff_interface_contracts`, `get_ranked_reading_path`.
- New resources: `reposcope://mindmap`, `reposcope://api-routes`,
  `reposcope://context-pack`.
- New HTTP route: `GET /api/context/pack`.
- Context defaults: `format=json`, `detail=skeleton`, `budget=8000`.
- Context hash excludes `format`, `since_hash`, `root`, and token-count fields.
  JSON and TOON share the content hash. A matching `since_hash` returns a
  compact JSON `unchanged: true` envelope.
- TOON is opt-in, lazily imported, and disabled by `REPOSCOPE_TOON=0`.
- Five frozen skill IDs: `blast-radius-guard`, `zero-grep-architect`,
  `pr-contract-shield`, `onboarding-navigator`, `dead-code-surgeon`.

## Verification record (2026-10-27)

Rook verified Wren's handoff at `cae15fb` in a fresh worktree
(`RepoScope-rook-phase4-verify`) on `rook/phase-4-review` and re-ran the full
gate. The review found documentation that described tools and resources that do
not exist, a context-pack contract that did not match the implementation, a
path-dependent benchmark, and missing coverage for the per-symbol character cap.

### Gate

| Check | Result |
|---|---|
| `python -m pytest -q` | **509 passed, 1 skipped** (30.55 s) |
| `python -m compileall -q backend` | pass |
| `python -m pip check` | no broken requirements |
| `npm --prefix frontend run build` | pass |
| `npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json` | pass, 0 errors |
| `npx playwright test tests/e2e/harness.spec.ts` | **5/5** |
| `npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"` | **16/16** |
| `npx playwright test tests/e2e/mindmap.spec.ts` | **3/3** |
| `git diff --check` | clean |

The single pytest skip is the Windows unprivileged symlink test. J22 remains
excluded for the recorded environmental 100 ms threshold; the threshold is
unchanged.

### Independent TOON rerun

Rook re-cloned the five repositories at the exact commits in
`docs/TOON_BENCHMARK.md` and re-ran `benchmarks/toon_benchmark.py` with
`budget=8000`, `detail=skeleton`. Every commit was verified with
`git rev-parse HEAD`. Results: **5/5 roundtrip PASS**, **median +39.1% token
saving**, **median +26.8% byte saving** against compact JSON. The previous
runner embedded the absolute checkout path in `root`, which made byte counts
depend on the clone directory; the runner now replaces `root` with `<repo>`
before serialization, and the documented table matches the normalized rerun.

### Review fixes

- `README.md`, `docs/FEATURES.md`, `docs/MCP.md`: replaced eight tool names and
  five resource URIs that do not exist with the real 13 tools and 8 resources;
  corrected signatures, argument defaults, caveats, and the nine-agent skill
  matrix.
- `docs/API.md`, `docs/MCP.md`: corrected the context-pack contract — `tokens`
  is `{pack, budget}`, `counts` is `{files_included, files_requested,
  symbols_included}`, omission reasons are `budget`, `not-indexed`,
  `ambiguous`, `outside-root`, and `unreadable`, caps apply **per symbol** at
  120 lines / 12,000 characters, the unchanged envelope has no `message`, and
  path traversal is an omission rather than HTTP 400.
- `docs/MCP.md`: documented that the MCP `get_context_pack` tool is JSON-only
  and that `REPOSCOPE_TOON=0` affects only the REST export.
- `benchmarks/toon_benchmark.py`: normalized the volatile `root` field before
  measuring, so byte and token counts reproduce from any checkout path.
- `backend/tests/test_context_compressor.py`: added
  `test_context_pack_full_detail_char_cap`, which exercises `MAX_BODY_CHARS`
  and the `max-chars` cap.
- `docs/screenshots/v2/`: restored 16 unrelated journey and harness binaries
  to `5b881b4`; only `harness/harness-skills-preview.png` is retained as Phase 4
  evidence.

No graph schema, edge meaning, MCP tool name, resource URI, or existing
endpoint path changed in the review fixes. The Phase 4 surface remains 13 tools
and 8 resources.

The review commit `74bd2fb` was fast-forwarded into `main` and pushed to
`origin/main` (`7ff5291..74bd2fb`) on 2026-10-27. `experimental` remains at
`7ff5291`.

## Claim protocol

1. Wren claims the Phase 4 implementation files in `WREN.md` before editing.
2. Rook does not edit a claimed implementation file. If a contract correction
   is needed, Rook posts it in `DIALOGUE.md` and `COMS.md` first.
3. Wren commits locally on `wren/phase-4-context`; no push.
4. Wren updates this board to `handed-off` and posts the five-part handoff.
5. Rook creates a fresh verification worktree, runs the gate, and reviews.
6. Only the owner authorizes a merge into `experimental` or `main`.

## Handoff checklist

- [x] Branch and commit hash recorded.
- [x] Files changed and claims released.
- [x] Every command and result recorded.
- [x] Measured TOON table with five real repositories and exact commits.
- [x] Known limits and skipped checks recorded with reasons.
- [x] No push; no `main` or `experimental` change; no secret exposure.

## Blockers

None. Phase 4 is merged into `main` at `74bd2fb` and pushed. The only expected
environmental skips are the Windows symlink test and the locally excluded J22
journey; both are recorded in the Phase 3 baseline and repeated in the Phase 4
handoff.


---

## Phase 5 status board

| Field | Value |
|---|---|
| Phase | 5 — Verified chat citations |
| Release | V2.6 |
| Target branch | `experimental` (direct commit) |
| Worktree | `D:\Aditya\Hackathon Projects\RepoScope-wren-phase5-14` |
| Base | `experimental` at `2b896df` |
| Contract status | `frozen` |
| Author gate status | `523 passed, 1 skipped; tsc 0 errors; build pass; Playwright 20/20 pass (J22 excluded)` |
| Self-verification verdict | `PASS` |
| Implementation status | `complete` |
| Handoff | Recorded in `WREN.md` and `DIALOGUE.md` |
---

## Phase 6 status board

| Field | Value |
|---|---|
| Phase | 6 — Four-mode reverse-prompt compiler |
| Release | V2.6 |
| Target branch | `experimental` (direct commit) |
| Worktree | `D:\Aditya\Hackathon Projects\RepoScope-wren-phase5-14` |
| Base | `experimental` at `1d8c573` |
| Contract status | `frozen` |
| Author gate status | `536 passed, 1 skipped; tsc 0 errors; build pass; Playwright 5/5 pass` |
| Self-verification verdict | `PASS` |
| Implementation status | `complete` |
| Handoff | Recorded in `WREN.md` and `DIALOGUE.md` |
