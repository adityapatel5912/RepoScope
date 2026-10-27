# RepoScope Phase 5–14 — execution and publishing plan

**Status:** Owner-approved workflow. Wren implements Phases 5–14 in one continuous run, one commit per phase on local `experimental`; verification is batched after Phase 14; Rook pushes only after sign-off.
**Baseline:** `main` at `839bb6e` (Phase 4 merged and pushed). Local `experimental` is at the current Phase 5–14 plan tip (Phase 4 plus this plan), fast-forwarded from `7ff5291`; confirm with `git log -1 --format=%H experimental`. Later phases start at the then-current `experimental` tip. `origin/experimental` remains at `7ff5291` until Rook pushes after the batch verification.
**Integration target:** `experimental` (owner decision, 2026-10-27). One phase per commit; no per-phase branch; verification of the full range after Phase 14.
**Source of truth:** `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §§8–17. This document assigns the post-Phase-4 workflow, order, verification, and publishing scope. It does not replace any phase contract.
**Scope exclusion:** extension publishing (Open VSX, VS Code Marketplace, VSIX publication) is out of scope for this plan.

---

## 1. Baseline after Phase 4

- Phase 4 implementation and review are merged into `main` at `74bd2fb`; the merge record is `839bb6e`.
- The MCP surface is exactly 13 tools and 8 resources. All pre-existing names and URIs are unchanged.
- JSON is the default context format; TOON is opt-in and `REPOSCOPE_TOON=0` disables the REST export.
- Independent TOON rerun: 5/5 roundtrip PASS, median +39.1% token saving and +26.8% byte saving against compact JSON at five exact commits.
- Backend gate: 509 passed, 1 skipped. Playwright: harness 5/5, journeys 16/16 with J22 excluded, mindmap 3/3.
- Known limits carried forward: J22 is excluded locally because of its unchanged 100 ms threshold; the Windows symlink test is the single expected skip; `npm ci` reported 6 vulnerabilities (4 moderate, 2 high) that are not yet triaged; the deployed Render service still reports an older version.
- Local `experimental` is fast-forwarded past the Phase 3 tree to include `main`'s Phase 4 tree and this plan. `origin/experimental` still points at `7ff5291` until Rook pushes after the Phase 5–14 batch sign-off.

---

## 2. Roles under the new workflow

| Role | Responsibility |
|---|---|
| **Owner** | May name an independent verifier; approves pushes, releases, tags, and credentials. If no separate agent is named, the owner accepts Rook as the verifier for the batch. |
| **Rook** | Freezes or corrects the contract, writes the Wren prompt, verifies the Phase 5–14 range when the owner accepts Rook as verifier, pushes after sign-off, and records the result. Rook does not edit a file Wren has claimed. |
| **Wren** | Implements Phases 5–14 in order (backend, frontend, tests, docs) directly on local `experimental` as one commit per phase, runs the author gate after each phase, and hands off the full range. Wren never pushes, merges to `main`, tags, or publishes. |
| **Verifier (Rook or owner's agent)** | Rook or a separate agent introduced by the owner. After Phase 14, runs the gate on a fresh detached worktree for the full commit range 5–14, checks each phase diff and claim adversarially, and signs off or rejects in `docs/coordination/VERIFIER.md` and `DIALOGUE.md`. The verifier is never Wren. |

Verification is batched after Phase 14. Wren does not wait for external sign-off between phases. The verifier must be confirmed before the batch starts; if Rook verifies, the owner accepts Rook as the verifier for the batch and Rook may push after sign-off.

---

## 3. Non-negotiable rules

1. **One phase per commit on `experimental`.** Do not create a per-phase branch. Do not mix two phases, packaging, or a refactor into one commit. Wren commits after every phase, before starting the next phase; the commit includes the implementation, tests, docs, CHANGELOG, and the coordination handoff. No phase is left uncommitted.
2. **Preserve compatibility.** v1 node ids (`file:`, `func:`, `class:`) and edge meanings (`contains`, `imports`, `calls`) stay unchanged. Existing endpoint paths and keys remain; new keys are additive. Existing MCP tool names and resource URIs remain.
3. **Deterministic evidence.** The graph, AST, git history, or a deterministic template is the source of truth. An LLM may write prose, never a fact, path, line, signature, or file set.
4. **JSON remains the default.** TOON stays opt-in. No unverified token-saving claim ships.
5. **No secrets.** Never read, print, commit, or send `.env` or a PAT. Agent configs contain placeholders only. No `.opencode/skills` directory is written.
6. **No test deletion.** A failing test is fixed, or the exact environmental reason is documented. New behavior gets a unit test, an L2 contract test, and an L3 journey where a user-visible surface exists.
7. **No push, no merge to `main`, no tag, no extension publish.** Wren commits each phase to local `experimental` through Phase 14 and stops after the final handoff. Rook pushes `experimental` only after the batch verifier signs off 5–14; `main` changes require separate owner approval.
8. **Real paths over plan placeholders.** The plan is authoritative for behavior, not for every suggested filename. Wren reconciles each phase against the real tree and records deviations in the handoff. The corrections in §6 are binding.
9. **One writer per file.** Claim files in `WREN.md` before editing. If a file is claimed by another writer, stop and ask Rook.
10. **Rollback is understood.** Every phase states how to revert it and whether any data or schema migration is involved.
11. **Cross-phase fixes are forward-only.** If a later phase must fix earlier-phase code, the fix goes in the current phase commit and is recorded in that handoff. Never amend an earlier phase commit.

---

## 4. Order and release checkpoints

| Wave | Phases | Release | Outcome |
|---|---|---|---|
| 1 | 5, 6, 7 | V2.6 | Verified citations; four-mode reverse-prompt compiler; deterministic multi-file scaffolding. |
| 2 | 8, 9, 10, 11, 12 | V2.7 | Four tour tracks; topological onboarding; churn/bus-factor/time machine; symbol-level PR impact; explainable impact simulator. |
| 3 | 13 | V2.8 | Six-engine graph-contextual security suite, scorecard, patch diffs, SARIF 2.1.0. |
| 4 | 14 | Release train | Hardening, cross-platform verification, packaging, performance budgets, release checklist, rollback. |

Run Phases 5–14 in numeric order, with each phase committed directly to local `experimental`. Wren starts Phase N+1 immediately after Phase N is committed and its author gate is green; there is no external verification stop between phases. Batch verification after Phase 14 covers all ten commits. Release checkpoints after Phase 7 (V2.6), Phase 12 (V2.7), Phase 13 (V2.8), and Phase 14 (release train). Tags and publishes require explicit owner approval.

Parallel implementation is not the default. If the owner explicitly asks for it, only disjoint files may run in parallel; citations, PR impact, and security are hard dependencies and are never parallelized across.

---

## 5. Phase assignments

### Phase 5 — Verified chat citations (V2.6)

- **Goal:** Every citation is checked against the indexed symbol table; near misses snap; hallucinations are visibly unverified.
- **Real surfaces:** `POST /api/chat/stream` in `backend/main.py`; `backend/sse.py`; `backend/orchestrator.py`; `frontend/src/components/ChatPanel.tsx`; `frontend/src/api/client.ts`.
- **New surface:** final SSE event `citations`; `GET /api/citation/verify`; a `CitationPill` component.
- **Must preserve:** existing SSE event names and old-client behavior; no citation is invented; hover previews never read outside the repository root.
- **Verifier focus:** exact, snapped, partial, and hallucinated cases; a citation to a missing path; a range spanning two symbols; a click that focuses the mind map.
- **Commit:** `feat(citations): verify and snap AST citations`.

### Phase 6 — Four-mode reverse-prompt compiler (V2.6)

- **Goal:** Emit `rebuild`, `feature`, `spec`, and `context` modes deterministically from the real graph.
- **Real surfaces:** `POST /api/repo/reverse-prompt` in `backend/main.py`; `frontend/src/components/ReversePromptModal.tsx`; `frontend/src/api/features.ts`.
- **New surface:** optional `mode`, `target_node_id`, `budget`, and `format` on the existing body; response `files`, `tokens`, `source`, and `warnings`.
- **Must preserve:** the existing `{prompt: "..."}` callers and the existing `/api/repo/reverse-prompt` path. If the plan's `/api/reverse-prompt` alias is added, it is additive and documented.
- **Verifier focus:** byte-identical output for identical graph and parameters; topological build order with cycles called out; every route/model/signature exists in the graph; a feature slice has its 2-hop interface closure and no unrelated files; token count is within 2% of the context pack.
- **Commit:** `feat(reverse-prompt): compile four deterministic blueprint modes`.

### Phase 7 — Executable multi-file scaffolder (V2.6)

- **Goal:** Generate a runnable 12–20 file starter kit with a preview tree, zip download, and bootstrap command.
- **Real surfaces:** `POST /api/scaffold` and `_validate_scaffold` in `backend/main.py`; `frontend/src/components/ScaffoldModal.tsx`; `frontend/src/api/features.ts`; `backend/tests/test_feature_5_scaffold.py`.
- **New surface:** `mode=preview|zip|command`; `POST /api/scaffold/download-zip`; path-safe archive.
- **Must preserve:** existing endpoint path and current response fields; the existing scaffold tests either pass or are updated to the new contract, never deleted.
- **Verifier focus:** generated Python kit compiles; TypeScript kit type-checks when Node is available; zip roundtrip equals the preview; no path escapes the output root; no secret is copied from `.env`; a stack with no template gets a documented generic kit.
- **Commit:** `feat(scaffold): generate executable multi-file starter kits`.

### Phase 8 — Four deterministic tour tracks (V2.7)

- **Goal:** Replace the single generic tour with `request_lifecycle`, `data_flow`, `change_impact`, and `onboarding` tracks.
- **Real surfaces:** `backend/tour_generator.py`; `POST /api/tour/generate` in `backend/main.py`; `frontend/src/components/TourPanel.tsx`; `frontend/src/api/features.ts`.
- **New surface:** `track`, `target_node_id`, and `max_stops` in the request; `track_label`, `why_this_order`, and `source` in the response; `GET /api/tour/export?format=codetour`.
- **Must preserve:** the existing `/api/tour/generate` path and the existing response fields; a track with no valid start returns `available: false`, never a fabricated stop.
- **Verifier focus:** all four tracks produce different deterministic orders on the fixture; every stop resolves to a real node and line; CodeTour export validates; a file edit cannot leave a stale line; the existing tour tests pass.
- **Commit:** `feat(tour): add four deterministic guided tracks`.

### Phase 9 — Topological student onboarding (V2.7)

- **Goal:** Build a deterministic curriculum from SCC condensation and topological layers, with graph-graded challenges.
- **Real surfaces:** `backend/onboarding.py`; `POST /api/onboard` in `backend/main.py`; `frontend/src/components/OnboardingPath.tsx`; `frontend/src/api/features.ts`.
- **New surface:** lessons with `layer`, `node_ids`, `reading_order`, `prerequisite_ids`, and `challenge`; graph-verified answers; localStorage progress.
- **Must preserve:** the existing `/api/onboard` path and the existing `levels`/`good_first_issues` fields until the new contract is additive; no server-side personal data; a cycle is shown as a cycle.
- **Verifier focus:** every lesson node exists; every prerequisite layer precedes its dependents; challenges are reproducible and graded by graph evidence; deterministic across runs; keyboard and screen-reader outline.
- **Commit:** `feat(onboarding): build a verified topological curriculum`.

### Phase 10 — Churn, hotspots, bus factor, and the time machine (V2.7)

- **Goal:** Extend the event feed into a repository-health view with named formulas and date windows.
- **Real surfaces:** `backend/repo_tracker.py`; `backend/git_history.py`; `backend/api/routers/analysis.py`; `frontend/src/components/TrackingPanel.tsx`.
- **New surface:** `GET /api/metrics/summary?window_days=90`, `/api/metrics/files?metric=hotspot&limit=20`, `/api/metrics/compare?base=<sha>&head=<sha>`, and `/api/metrics/release-notes?from=<ref>&to=<ref>`.
- **Must preserve:** existing `/api/analysis/hotspots` and `/api/analysis/ownership` behavior; no duplicate churn engine; no history command outside the loaded root; a repository with no git history returns `available: false` with a reason.
- **Verifier focus:** formulas and windows appear in every response; churn comes from git, not an LLM; a single-author repository reports bus factor 1; the time machine shows a node/edge delta; no command escapes the root.
- **Commit:** `feat(metrics): add churn, hotspots, bus factor, and history compare`.

### Phase 11 — Symbol-level PR impact (V2.7)

- **Goal:** Replace the 25-file cap and file-level risk with a symbol-level contract diff.
- **Real surfaces:** `backend/pr_impact.py`; `backend/impact_analyzer.py`; `backend/api/routers/pr_chat.py`; `POST /api/impact/pr` in `backend/main.py`; `frontend/src/components/ImpactPanel.tsx`; `frontend/tests` PR tests.
- **New surface:** `schema_version: 2`, `breaking`, `api_contracts`, `test_gaps`, and `risk` with `score`, `band`, and `breakdown`; explicit `truncated` and cutoff.
- **Must preserve:** the existing `/api/impact/pr` path and `/api/pr/report` behavior; existing PR-bot tests; no claim of completeness when the budget is exceeded.
- **Verifier focus:** a changed signature reports every caller, including a frontend `api_calls` caller; a removed route is an API contract break; the 25-file cap is gone; the SARIF/JSON report is stable and path-safe.
- **Commit:** `feat(pr-impact): analyze symbol-level contract breaks without a file cap`.

### Phase 12 — Explainable impact simulator (V2.7)

- **Goal:** Turn "what breaks?" into a three-hop, scored, explainable simulation.
- **Real surfaces:** `backend/impact_analyzer.py`; `POST /api/impact/analyze` in `backend/main.py`; `frontend/src/components/ImpactPanel.tsx`; `frontend/src/api/features.ts`.
- **New surface:** `hops`, `paths`, `score_breakdown`, `api_boundaries`, `test_gaps`, and `explanation_ids`; each hop is `{from, to, edge_type, evidence}`.
- **Must preserve:** the existing `/api/impact/analyze` path and response fields; a three-hop limit; every path is a real graph path.
- **Verifier focus:** direct/transitive sets on a hand-built fixture; no invented edge; the score breakdown sums to the score; the panel explains and opens each included node.
- **Commit:** `feat(impact): add a three-hop explainable impact simulator`.

### Phase 13 — Six-engine graph-contextual security suite (V2.8)

- **Goal:** Replace regex-only security with six deterministic engines, a scorecard, suggested patches, and SARIF 2.1.0.
- **Real surfaces:** `backend/security_scanner.py`; `backend/taint.py`; `backend/sarif.py`; `POST /api/security/scan` and `/api/security/taint` in `backend/main.py`; `frontend/src/components/SecurityPanel.tsx`.
- **New surface:** `engines`, `min_severity`, `offline`, and `include_patches` on the existing scan body; `GET /api/security/sarif?scan_id=...`; `POST /api/security/patch`.
- **Must preserve:** the existing `/api/security/scan` and `/api/security/taint` paths and behavior; no secret value in logs, responses, SARIF, or the UI; offline dependency checks say `skipped`, not `passed`; a patch is a suggestion and is never applied.
- **Verifier focus:** positive and negative fixtures per engine; cross-file taint finds a path the old same-file scanner missed; OSV is never called in tests; SARIF validates against 2.1.0; patch diffs apply to a temp copy and pass a syntax check; no P1 false positive on the repository's own fixtures.
- **MCP decision:** `run_security_scan` in the plan's Appendix D would be a 14th tool. Do not add it by default. The Phase 4 frozen surface stays 13 tools and 8 resources unless the owner approves a documented contract change, tests, and docs.
- **Commit:** `feat(security): add six graph-contextual security engines`.

### Phase 14 — Hardening, packaging, and release (release train)

- **Goal:** Make the release reproducible without adding feature scope.
- **Work:** single version source (`backend/version.py`); PyPI metapackage `reposcope-ai` while keeping `reposcope`; `packages/reposcope-mcp/` Node launcher that delegates to Python; docs, `CHANGELOG.md`, migration notes, `docs/KNOWN_LIMITS.md`; cross-platform matrix; performance budgets; release checklist; rollback rehearsal; vulnerability triage.
- **Out of scope:** extension publishing. Do not publish to Open VSX or the VS Code Marketplace, do not build or upload a VSIX, and do not add marketplace credentials. Extension compile/test may remain a pre-existing artifact check only if the extension is touched.
- **Deployment:** do not redeploy Render or Vercel without explicit owner approval. The deployed Render service still reports an older version than the checkout.
- **Verifier focus:** one version source with no drift; clean install from packaged artifacts, not the checkout; all L1/L2/L3 gates green on Windows and Linux; performance budgets recorded with hardware and repository size; `docs/QA_REPORT.md` reflects the final numbers.
- **Commit:** `chore(release): harden, package, and verify the v2.5–v2.8 train`.

---

## 6. Real-surface corrections (binding)

Phase 4 shipped docs that named tools and resources that did not exist. Do not repeat that. At `839bb6e`, these are the real surfaces:

| Plan text | Reality at `839bb6e` | Instruction |
|---|---|---|
| `POST /api/reverse-prompt` | `POST /api/repo/reverse-prompt` in `backend/main.py` | Preserve the existing path. Add `/api/reverse-prompt` only as a documented additive alias if the contract requires it. |
| `backend/api/routers/chat.py` | `POST /api/chat/stream` in `backend/main.py` | Extend the existing endpoint and `backend/sse.py`; do not create a second stream. |
| A new `backend/api/routers/onboarding.py` | `POST /api/onboard` in `backend/main.py` | Preserve `/api/onboard`. A router extraction must keep the path and response. |
| `ReversePromptPanel.tsx` | `frontend/src/components/ReversePromptModal.tsx` | Extend the real component. |
| `ScaffoldPanel.tsx` | `frontend/src/components/ScaffoldModal.tsx` | Extend the real component. |
| `StudentModePanel.tsx` | `frontend/src/components/OnboardingPath.tsx` | Extend the real component. |
| `PRImpactPanel.tsx` | `frontend/src/components/ImpactPanel.tsx` and the PR bot surfaces | Extend the real component; do not create a parallel panel without wiring and deleting the dead one. |
| `TrackerPanel.tsx` | `frontend/src/components/TrackingPanel.tsx` | Extend the real component. |
| `backend/security/` package | `backend/security_scanner.py`, `backend/taint.py`, `backend/sarif.py` | Evolve the real modules. A package split is allowed only if every existing import and endpoint keeps working. |
| `/api/metrics/*` | Existing `/api/analysis/hotspots` and `/api/analysis/ownership` | Add the new endpoints; preserve the existing ones and do not duplicate the engine. |

`POST /api/scaffold`, `POST /api/tour/generate`, `POST /api/impact/analyze`, `POST /api/impact/pr`, and `POST /api/security/scan` already exist and match the plan paths.

---

## 7. Verification protocol

### 7.1 Author gate (Wren, after every phase)

Run from the phase worktree on `experimental` after each phase and record the exact results in that phase's handoff. Commit the phase only when the gate is green; then continue to the next phase. Only one worktree can have `experimental` checked out; detach or remove the previous phase worktree before creating the next one.

```powershell
python -m pytest -q
python -m compileall -q backend
python -m pip check
npm --prefix frontend run build
npm --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json
cd frontend
npx playwright test tests/e2e/<phase>.spec.ts
npx playwright test tests/e2e/journeys.spec.ts --grep-invert "J22"
npx playwright test tests/e2e/mindmap.spec.ts
cd ..
git diff --check
```

Add `python -m pytest -q backend/tests/<phase>_tests.py` and the phase-specific benchmark or fixture commands where applicable. If the extension is touched, run its compile and tests. The Windows symlink test and J22 remain the only documented local exclusions unless a new, reproduced environmental cause is recorded.

### 7.2 Batch verifier gate (after Phase 14)

The verifier is Rook or an agent named by the owner. It starts from a fresh detached worktree at the final handoff SHA and does not reuse Wren's working tree. The verifier covers the full range 5–14:

1. Confirms the base SHA, the ten phase SHAs, the final SHA, and that the range is exactly ten phase commits on `experimental` with no unrelated commits.
2. Checks out each phase commit in order and verifies its diff against that phase's contract and the compatibility checklist in Appendix B of the implementation plan.
3. Confirms each commit is one complete phase: implementation, tests, docs, CHANGELOG, and the coordination handoff; no later-phase files in an earlier commit.
4. Runs the phase-specific fixtures at each phase commit and the full author gate at the final SHA. The full gate must be green on the cumulative tree.
5. Reproduces every measured claim (token counts, benchmark tables, coverage counts) from the stated commands and exact revisions.
6. Adds adversarial fixtures for each phase's failure modes; a new finding gets a test before the fix.
7. Checks docs against the real code: endpoint paths, field names, defaults, status codes, tool names, and resource URIs.
8. Checks for secret exposure, `.env` access, and leaked absolute paths across the whole range.
9. Writes a signed verdict in `docs/coordination/VERIFIER.md` and `DIALOGUE.md`: pass the range, or reject with numbered findings grouped by phase.

A rejected phase goes back to Wren. Wren fixes the findings with new commits on `experimental`, re-runs the affected phase gate and the full gate, and re-hands off. The verifier re-runs the full range verification, not only the changed test.

### 7.3 Integration gate (Rook)

Rook pushes only after the batch verifier signs off the full range:

- Confirm the base SHA, the ten phase SHAs, the final SHA, and the verifier's verdict.
- The Phase 5+ target is `experimental`. Push `experimental` after sign-off. Do not merge to `main` or push `main` without separate owner approval.
- Preserve all ten phase commits; one phase per commit. Do not squash or rewrite them.
- Record the range, the final SHA, and the push result in `COMS.md`, `DIALOGUE.md`, and `ROOK.md`.
- The range is integrated only when `origin/experimental` contains the signed-off final SHA and `main` is unchanged.

---

## 8. Publishing and release workstream

Phase 14 is the only phase that changes packaging or publishing. It runs after Phases 5–13 are committed on `experimental`; all ten phases are verified together after Phase 14.

### In scope

- One version source used by `/api/health`, the CLI, SARIF, and package metadata.
- `reposcope-ai` as a thin PyPI metapackage; the existing `reposcope` name remains.
- `packages/reposcope-mcp/` as a Node launcher/configurator that delegates to Python. It never parses code in Node.
- `CHANGELOG.md`, migration notes, `docs/FEATURES.md` limits, and `docs/KNOWN_LIMITS.md`.
- Cross-platform verification: Python 3.11/3.12, Node 20, Windows and Linux, frontend build, Playwright journeys.
- Performance budgets with recorded hardware and repository size: graph build, mind-map render, PageRank, security scan, and context pack.
- Release checklist and rollback rehearsal.
- Triage the reported `npm ci` vulnerabilities (4 moderate, 2 high) and record the outcome.
- Re-measure the TOON benchmark on the release commit; do not reuse a stale table.
- Render/Vercel deployment only with explicit owner approval.

### Explicitly excluded

- Extension publishing to Open VSX.
- Extension publishing to the VS Code Marketplace.
- Building or uploading a VSIX for publication.
- Marketplace publisher accounts, Azure DevOps PATs, or `OVSX_TOKEN` work.
- Any release note that claims an extension publication.

The extension remains a separately versioned client. If it is touched by a phase, its compile and test suite still run as a pre-existing artifact check, but that is not publishing.

### Publishing gates

1. The exact release SHA is recorded and matches the verified commit.
2. The working tree is clean and the gate is green on both operating systems.
3. Artifacts are built from the release commit and installed from the artifact, not from the checkout.
4. No secret, token, `.env` value, or local absolute path is embedded in an artifact or a log.
5. The TOON table and any other measured claim are reproduced at the release commit.
6. The rollback path is rehearsed or read end to end and recorded.
7. The owner approves the publish or deployment explicitly. Credentials stay in the environment; they are never printed or put on a command line.

---

## 9. Decisions and open items

1. **Verifier identity and timing.** Rook or an agent named by the owner verifies the full range 5–14 after Phase 14. Wren starts immediately; the verifier must be confirmed before batch verification and the push.
2. **Resolved — Phase 5+ integration target.** `experimental` (owner, 2026-10-27). One phase per commit; no per-phase branch; batch verification after Phase 14. Local `experimental` is fast-forwarded to include Phase 4 and this plan; Rook pushes it after batch sign-off.
3. **Phase 13 MCP surface.** Keep the Phase 4 surface at 13 tools and 8 resources (security over REST only), or approve `run_security_scan` as a documented 14th tool with tests and docs. Default: do not add it.
4. **Phase 6 alias.** Preserve `/api/repo/reverse-prompt` and, only if the contract requires it, add `/api/reverse-prompt` as an alias. Default: preserve the existing path and document it.
5. **Release names and namespaces.** Confirm the PyPI metapackage name, npm package name, tag format, and who holds the publish credentials. No credential is committed.
6. **Extension publishing.** Out of scope for this plan. If it is ever scheduled, it needs a separate contract, a separate release gate, and explicit owner approval.

---

## 10. Definition of done

### Phase ready for the next phase

A phase is ready to continue when:

- It is one commit on `experimental` with the prescribed message.
- Its author gate is green and recorded in the phase handoff.
- The contract and limits are documented against the real code.
- No existing endpoint, schema, tool, resource, or test regressed.
- The working tree is clean and the next phase starts from that commit.
- The phase's changes are not mixed into another phase commit.

Wren does not wait for external verification between phases. A red author gate stops the run until it is fixed.

### Range done (verification and integration)

The Phase 5–14 range is done only when:

- All ten phase commits exist on `experimental`, in order, one phase per commit.
- The batch verifier signs off the full range and the final SHA.
- The full gate is green at the final SHA, including each phase's L2 contract test and L3 journey.
- Every phase contract is documented against the real code and no endpoint, schema, tool, resource, or test regressed.
- The rollback is understood and recorded.
- Rook pushes `experimental`; `origin/experimental` contains the signed-off final SHA and `main` is unchanged.
- No phase commit was squashed or rewritten.

Phase 14 is done when the release artifacts install cleanly, the measured numbers are reproduced at the release commit, the rollback is rehearsed, and the owner has approved the release. Extension publishing is not part of that definition.
