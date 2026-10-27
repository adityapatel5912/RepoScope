# COMS - Phase 4 coordination board

This is the live claim and status board for Phase 4. `DIALOGUE.md` is the
append-only decision log; `ROOK.md` and `WREN.md` are the per-agent work logs.
Git commits, tests, and the frozen contracts are the source of truth.

## Phase status

| Field | Value |
|---|---|
| Phase | 4 - token-compact context, MCP surface, and skills |
| Release | V2.5 |
| Planning branch | `rook/phase-4-context` (local, unpushed) |
| Implementation branch | `wren/phase-4-context` (to be created) |
| Implementation worktree | `D:\Aditya\Hackathon Projects\RepoScope-wren-phase4` |
| Base | `main` at `7ff5291` (Phase 3 merged) |
| Contract status | frozen |
| Implementation status | `planned` |
| Review status | `not-started` |
| Merge status | `blocked on owner approval` |

## Ownership

| Area | Owner | Status |
|---|---|---|
| Planning documents, contract, prompt | Rook | `done` |
| `backend/context_compressor.py` | Wren | `planned` |
| `backend/skill_library.py` and ten checked-in `SKILL.md` copies | Wren | `planned` |
| `backend/api/routers/context.py` and router mount | Wren | `planned` |
| `backend/mcp_server/tools.py` and `server.py` Phase 4 surface | Wren | `planned` |
| `backend/harness_generator.py` skill preview/apply | Wren | `planned` |
| Frontend `SkillsSection` and browser journey | Wren | `planned` |
| TOON benchmark and measured documentation | Wren | `planned` |
| Full test gate, diff review, merge | Rook | `not-started` |
| `main` / `experimental` | Owner only | `blocked` |

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

## Claim protocol

1. Wren claims the Phase 4 implementation files in `WREN.md` before editing.
2. Rook does not edit a claimed implementation file. If a contract correction
   is needed, Rook posts it in `DIALOGUE.md` and `COMS.md` first.
3. Wren commits locally on `wren/phase-4-context`; no push.
4. Wren updates this board to `handed-off` and posts the five-part handoff.
5. Rook creates a fresh verification worktree, runs the gate, and reviews.
6. Only the owner authorizes a merge into `experimental` or `main`.

## Handoff checklist

- [ ] Branch and commit hash recorded.
- [ ] Files changed and claims released.
- [ ] Every command and result recorded.
- [ ] Measured TOON table with five real repositories and exact commits.
- [ ] Known limits and skipped checks recorded with reasons.
- [ ] No push; no `main` or `experimental` change; no secret exposure.

## Blockers

None. The only expected environmental skips are the Windows symlink test and
the locally excluded J22 journey; both are recorded in the Phase 3 baseline and
must be repeated in the Phase 4 handoff.
