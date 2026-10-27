# Wren — Phase 5–14 execution prompts

**Status:** Ready for Wren. Wren runs Phases 5–14 in one continuous session, one commit per phase on local `experimental`; verification is batched after Phase 14.
**Baseline:** local `experimental` at the current Phase 5–14 plan tip (Phase 4 plus this plan), fast-forwarded from `7ff5291`. Later phases start at the then-current `experimental` tip; confirm with `git log -1 --format=%H experimental`. `origin/experimental` remains at `7ff5291` until Rook pushes after the batch verification.
**Companion plan:** `docs/coordination/PLAN_PHASE_5_14.md`.
**Authoritative contracts:** `docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md` §§8–17.

## How to use this file

1. Give Wren the **common preamble** and **all ten phase blocks**. Wren runs Phases 5–14 in numeric order in one session.
2. Wren creates one worktree on local **`experimental`**, implements Phase 5, runs the author gate, updates the coordination files, and **commits Phase 5 directly to `experimental` — one commit per phase, no phase branch**. Wren then immediately starts Phase 6.
3. Wren repeats for Phases 6–13. Each phase is one commit on `experimental`. Wren does not wait for external verification between phases.
4. Phase 14 is the final phase. Wren commits it, stops, and hands off the full range: the base SHA before Phase 5, all ten phase SHAs, and the final SHA.
5. Rook or the owner's independent verifier verifies the entire range 5–14, commit by commit, on a fresh detached worktree. Only after sign-off does Rook push `experimental`.
6. `main` is not touched. A `main` merge requires separate owner approval.

### Commit policy

Wren commits after every phase, before starting the next, directly to local
`experimental`. One phase is one local commit containing the implementation,
tests, docs, CHANGELOG, and the `WREN.md`/`COMS.md`/`DIALOGUE.md` handoff. Do
not create a per-phase branch. After committing Phase N, Wren starts Phase N+1
from that commit immediately. Wren does not stop between phases for a verifier;
verification is batched after Phase 14. If a phase's author gate fails, fix it
before committing that phase; never carry a red gate or uncommitted work into
the next phase. If the batch verifier rejects a phase, the fixes go on
`experimental` as new commits; never amend or rewrite the reviewed commit.

---

## Common preamble (include with every phase)

```text
You are Wren, the implementation agent for RepoScope. You implement Phases 5
through 14 in order in one continuous run, one commit per phase. Rook or the
owner's independent verifier verifies the whole range after Phase 14. You do
not push, merge to main, tag, publish, or self-certify.

Baseline: local experimental at the current Phase 5-14 plan tip (Phase 4 plus
this plan), fast-forwarded from 7ff5291. Confirm with
`git log -1 --format=%H experimental` before starting. origin/experimental
remains at 7ff5291 until Rook pushes after the batch verification.

Authoritative contract: docs/IMPLEMENTATION_PLAN_V2.5_V2.8.md sections 8-17,
plus the phase blocks below. docs/coordination/PLAN_PHASE_5_14.md section 6
contains binding corrections where the plan's suggested paths differ from the
real tree.

Setup:
0. Run `git worktree list`. Only one worktree can have experimental checked
   out. If an older worktree holds it, detach that worktree with
   `git -C <path> switch --detach` before adding yours.
1. Create one fresh worktree on local experimental and use it for all ten
   phases:
   git worktree add "D:\Aditya\Hackathon Projects\RepoScope-wren-phase5-14" experimental
2. Do NOT create a per-phase branch or a worktree per phase. Commit directly to
   experimental.
3. Claim every file you will edit in docs/coordination/WREN.md before editing.
4. Implement the current phase completely: backend, frontend, tests, docs,
   CHANGELOG.
5. Run the author gate and record the exact commands and results.
6. Update WREN.md, COMS.md, and DIALOGUE.md with the five-part handoff for the
   phase: branch/commit; files and claims released; commands/results;
   limits/skips; next open decision.
7. Commit the phase directly to experimental. Stage and commit the complete
   phase — code, tests, docs, CHANGELOG, and the coordination handoff — with the
   prescribed message. One phase = one commit. Do not amend or rewrite history.
8. Continue immediately to the next phase from that commit. Do not wait for
   external verification between phases.
9. Repeat steps 4-8 through Phase 14, committing each phase separately and in
   order.
10. After Phase 14, stop and hand off the full range: the base SHA before
    Phase 5, the ten phase SHAs, and the final SHA. Do not push.

Rules:
- One phase per commit. Commit to local experimental; do not create a per-phase
  branch. No later-phase files in an earlier phase, no packaging before Phase
  14, no extension publishing.
- Commit after every phase before starting the next. A phase is not done until
  the phase commit exists and `git status` is clean. Never carry a red gate or
  uncommitted work into the next phase.
- Verification is batched after Phase 14. Do not stop between phases for a
  verifier. If the batch verifier rejects a phase, fix it with new commits on
  experimental; never amend or rewrite the reviewed commit.
- If a later phase requires a fix to earlier-phase code, include the fix in the
  current phase commit and record it in that phase's handoff. Never amend an
  earlier phase commit.
- Preserve v1 node ids and edge meanings, existing endpoint paths and keys, and
  existing MCP tool names and resource URIs. New keys and endpoints are additive.
- JSON remains the default; TOON stays opt-in; never ship an unverified token
  claim.
- Do not create .opencode/skills. Never read, print, commit, or expose .env or a
  PAT. Agent configs contain placeholders only.
- The graph/AST/git history or a deterministic template is the source of truth.
  An LLM may write prose, never a path, line, signature, or file set.
- Do not delete a test to make the gate green. Add a unit test, an L2 contract
  test, and an L3 Playwright journey for every user-visible surface.
- The Windows symlink test and J22 are the only documented local exclusions.
  Do not widen them without a reproduced environmental cause.
- If the plan and the code disagree on a path, preserve the real endpoint and
  record the deviation. If a contract is ambiguous, stop and ask Rook in
  DIALOGUE.md. Do not invent a path.
- Keep the working tree clean at each phase commit. No untracked build output,
  no secrets, no generated screenshots outside docs/screenshots/v2/<phase>/.
```

### Author gate (record all results)

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

If the extension is touched, also run:

```powershell
npm --prefix extensions/vscode run compile
npm --prefix extensions/vscode test
```

Add phase-specific fixtures, benchmarks, or syntax checks where the phase block requires them.

---

## Phase index

| Phase | Release | Commit message (one commit on `experimental`) |
|---|---|---|
| 5 | V2.6 | `feat(citations): verify and snap AST citations` |
| 6 | V2.6 | `feat(reverse-prompt): compile four deterministic blueprint modes` |
| 7 | V2.6 | `feat(scaffold): generate executable multi-file starter kits` |
| 8 | V2.7 | `feat(tour): add four deterministic guided tracks` |
| 9 | V2.7 | `feat(onboarding): build a verified topological curriculum` |
| 10 | V2.7 | `feat(metrics): add churn, hotspots, bus factor, and history compare` |
| 11 | V2.7 | `feat(pr-impact): analyze symbol-level contract breaks without a file cap` |
| 12 | V2.7 | `feat(impact): add a three-hop explainable impact simulator` |
| 13 | V2.8 | `feat(security): add six graph-contextual security engines` |
| 14 | Release train | `chore(release): harden, package, and verify the v2.5–v2.8 train` |

---

## Phase 5 — Verified chat citations (V2.6)

```text
Implement Phase 5, Verified chat citations.

Goal: every citation is checked against the indexed symbol table. Exact matches
stay exact, near misses snap to the real symbol range, and hallucinations are
visibly unverified. The model writes prose; the AST writes citations.

Real surfaces at 839bb6e:
- POST /api/chat/stream is implemented in backend/main.py, not in a chat
  router. The SSE framing helper is backend/sse.py.
- The chat UI is frontend/src/components/ChatPanel.tsx.
- The API client is frontend/src/api/client.ts.
- There is no CitationPill.tsx yet; create it if the UI needs a separate
  component, then wire it into ChatPanel.tsx.

Contract:
- Keep every existing SSE event name. Add exactly one final event:
  {"type":"citations","citations":[{raw,path,start_line,end_line,symbol,node_id,
  verified,confidence,reason,preview}]}
- Add GET /api/citation/verify?path=...&line=... as a read-only debug endpoint.
  It returns the same citation object or a well-formed miss.
- A citation to a non-existent path is verified:false; never invent a path.
- A near-miss start within 5 lines of a known symbol snaps to that symbol and
  records reason:"snapped".
- A range that spans two symbols is split or marked partial.
- A citation with no symbol but a valid file line is verified:true with the
  file node and a narrow preview.
- The verifier never calls an LLM.
- Hover previews must not read outside the repository root.
- The UI must visually distinguish verified from unverified pills; unverified
  must not look authoritative.

Tests:
- backend/tests/test_citation_verifier.py: exact, snapped, partial,
  hallucinated, missing-path, and path-escape cases.
- backend/tests/test_chat_citations.py: the final SSE event and old-client
  compatibility.
- frontend/tests/e2e/citations.spec.ts: verified/unverified rendering, click
  focuses the mind map, hover preview, no console errors.

Acceptance gate:
- Exact, snapped, partial, and hallucinated cases pass.
- The final SSE event does not break an old client.
- Citation clicks expand the mind map and focus the file.
- Hover previews never read outside the repository root.
- No raw model text is trusted as a citation without verification.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(citations): verify and snap AST citations

Then continue to Phase 6. Do not push.
```

---

## Phase 6 — Four-mode reverse-prompt compiler (V2.6)

```text
Implement Phase 6, the four-mode reverse-prompt compiler.

Goal: replace the single generic prompt with a deterministic compiler that
emits four modes from the real graph: rebuild, feature, spec, and context. The
LLM may polish prose only after the structure is assembled and verified.

Real surfaces at 839bb6e:
- The existing endpoint is POST /api/repo/reverse-prompt in backend/main.py,
  not /api/reverse-prompt. Preserve the existing path and body compatibility.
- The existing UI is frontend/src/components/ReversePromptModal.tsx.
- The existing client call is in frontend/src/api/features.ts.
- If you add /api/reverse-prompt as an alias, it must be additive and
  documented. Do not remove the existing path.

Contract:
- Keep the existing body. Add optional mode, target_node_id, budget, and format.
- mode defaults to "context". Existing {prompt: "..."} callers keep working:
  prompt is the same string as content.
- Response: {ok, mode, content, files:[{path,content}], tokens, format,
  source:{nodes,edges,root}, warnings}.
- rebuild: stack, build order, routes, models, env keys, test commands; 100%
  graph-derived; LLM optional for prose.
- feature: a self-contained prompt for the selected node/feature and its 2-hop
  interface closure; deterministic subgraph and signatures.
- spec: CLAUDE.md, AGENTS.md, llms.txt, and .kiro/specs/* from deterministic
  templates.
- context: compact/standard/full context pack with a token count; TOON only if
  the format is explicitly requested and already supported.

Rules:
- Same graph and parameters produce byte-identical output. No timestamps or
  random ids inside the content.
- Build order is topological; cycles are called out, not hidden.
- Every route, model, and signature in a blueprint exists in the graph.
- A feature slice includes its 2-hop interface closure and no unrelated files.
- The token counter is deterministic and within 2% of the context pack.
- Do not invent a framework, dependency, route, or file.

Tests:
- backend/tests/test_reverse_prompt.py: determinism, all four modes, topological
  order with a cycle, 2-hop closure, invalid target, and old {prompt} body.
- An L2 contract test for POST /api/repo/reverse-prompt (and the optional
  alias, if added).
- frontend/tests/e2e/reverse-prompt.spec.ts: preview, copy, download, and every
  mode.

Acceptance gate:
- Byte-identical output for the same graph and parameters.
- Build order is topological with cycles visible.
- Every route/model/signature exists in the graph.
- Feature slices contain the 2-hop interface closure and no unrelated files.
- Token count is deterministic and within 2% of the context pack.
- The panel previews, copies, and downloads every mode.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(reverse-prompt): compile four deterministic blueprint modes

Then continue to Phase 7. Do not push.
```

---

## Phase 7 — Executable multi-file scaffolder (V2.6)

```text
Implement Phase 7, the executable multi-file scaffolder.

Goal: generate a runnable 12-20 file starter kit from the analyzed repository's
real stack, with a preview tree, a zip download, and a terminal bootstrap
command. Templates are deterministic; the LLM is not allowed to invent the file
set.

Real surfaces at 839bb6e:
- POST /api/scaffold and _validate_scaffold are in backend/main.py. Keep the
  endpoint path and the existing response fields.
- The existing UI is frontend/src/components/ScaffoldModal.tsx.
- The existing client call is in frontend/src/api/features.ts.
- Existing tests are in backend/tests/test_feature_5_scaffold.py. They must
  pass or be updated to the new contract; never delete them.
- A new backend/scaffolder.py is appropriate if it keeps the generator
  deterministic and testable.

Contract:
- POST /api/scaffold keeps its path. Add optional mode=preview|zip|command. The
  default preserves the current response fields.
- Response: {ok, project_type, files:[{path,content,language}], file_tree,
  entry_files, warnings, token_estimate}.
- POST /api/scaffold/download-zip streams application/zip with a path-safe
  archive.
- npx reposcope-mcp scaffold --from <owner/repo> --out ./app is generated as
  text, not executed by the backend.

Rules:
- Path traversal is rejected in both the generator and the zip.
- The kit includes a test file, an .env.example with placeholders only, a
  README, and the chosen harness config plus skills.
- No secret is ever copied from .env.
- A stack with no template gets a documented generic kit, not a broken one.
- Validate the generated kit by writing it to a temp directory and running the
  language syntax check: compileall for Python, tsc --noEmit when Node is
  available.
- The deterministic generator is the source of the file set. Do not let the
  model add or remove files.

Tests:
- backend/tests/test_scaffolder.py: determinism, all modes, path traversal,
  zip roundtrip, placeholder-only .env.example, and a generic-stack fallback.
- Keep backend/tests/test_feature_5_scaffold.py green or update it to the new
  contract.
- frontend/tests/e2e/scaffold.spec.ts: preview tree, keyboard navigation, zip
  download, and copy command.

Acceptance gate:
- The Python kit compiles; the TypeScript kit type-checks when Node is
  available.
- The zip roundtrip preserves the preview exactly.
- No file escapes the output root.
- The preview tree is interactive and keyboard accessible.
- The existing scaffold behavior remains backward compatible.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(scaffold): generate executable multi-file starter kits

Then continue to Phase 8. Do not push.
```

---

## Phase 8 — Four deterministic tour tracks (V2.7)

```text
Implement Phase 8, four deterministic tour tracks.

Goal: replace the single generic BFS tour with four tracks that answer
different questions:
1. request_lifecycle: entry point -> route -> handler -> service -> storage.
2. data_flow: a model/table/state node and the code that reads and writes it.
3. change_impact: a high-risk file/symbol and its blast radius.
4. onboarding: the shortest path from an entry point to core domain concepts.

Real surfaces at 839bb6e:
- backend/tour_generator.py contains build_tour(graph, topic, max_steps=12,
  provider=None).
- POST /api/tour/generate is in backend/main.py.
- The existing UI is frontend/src/components/TourPanel.tsx.
- The existing client call is in frontend/src/api/features.ts.

Contract:
- POST /api/tour/generate keeps its path. The body gains track,
  target_node_id, and max_stops.
- The response keeps stops and adds track, track_label, why_this_order, and
  source evidence.
- GET /api/tour/export?format=codetour returns a CodeTour-compatible JSON file.
- A track with no valid start returns available:false and a reason; it never
  fabricates a stop.
- Stops are unique; a cycle is cut at the repeated node with a warning.
- Each stop carries path, line, end_line, role, reason, and verified (from the
  Phase 5 verifier).
- "Ask about this stop" sends the stop's exact node/line context, not just its
  label.

Rules:
- The LLM writes a short explanation per stop only. The stop order, paths, and
  lines are deterministic.
- Every stop resolves to a real node and line.
- Keep the existing tour endpoint backward compatible.
- A file edit must not leave a stale line in a regenerated tour.

Tests:
- backend/tests/test_tour_tracks.py: all four tracks, different deterministic
  orders on the fixture, no-start behavior, cycle cut, and real node/line
  resolution.
- An L2 test for GET /api/tour/export.
- frontend/tests/e2e/tour.spec.ts: track selection, stop navigation, export,
  and no console errors.

Acceptance gate:
- All four tracks produce different, deterministic orders on the fixture.
- Every stop resolves to a real node and line.
- CodeTour export validates against the schema subset.
- The tour survives a file edit without a stale line.
- The existing tour endpoint remains backward compatible.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(tour): add four deterministic guided tracks

Then continue to Phase 9. Do not push.
```

---

## Phase 9 — Topological student onboarding (V2.7)

```text
Implement Phase 9, topological student onboarding.

Goal: replace hub-first ranking and LLM quizzes with a deterministic
curriculum: topological layers over real dependencies, prerequisite chains,
and challenges whose answers are verified against the repository.

Real surfaces at 839bb6e:
- backend/onboarding.py contains build_onboarding(graph, provider=None).
- The existing endpoint is POST /api/onboard in backend/main.py. Preserve the
  path. A new router file must keep the same path and response.
- The existing UI is frontend/src/components/OnboardingPath.tsx.
- The existing client call is in frontend/src/api/features.ts.
- Existing tests are in backend/tests/test_feature_2_onboard.py.

Contract:
- Layers are computed by SCC condensation then topological order. A cycle is
  one layer with an explicit note.
- A lesson is {id, layer, title, node_ids, reading_order, prerequisite_ids,
  challenge}.
- A challenge is one of: locate a symbol, trace a call, identify a route, or
  explain a boundary. The verifier checks the answer against the graph, not a
  hidden LLM rubric.
- Progress is stored in localStorage; no account and no server-side personal
  data.
- "Skip ahead" is allowed but shows the prerequisites that were skipped.
- Keep the existing levels and good_first_issues fields until the new fields
  are additive and the UI migrates.

Rules:
- Every lesson node exists in the graph.
- Every prerequisite layer precedes its dependents.
- A cycle is displayed as a cycle, not silently flattened.
- The curriculum is deterministic across runs.
- The LLM may write explanations, not the lesson order or the answers.

Tests:
- backend/tests/test_onboarding.py: SCC/topological layers, prerequisites,
  graph-graded challenges, cycle display, and determinism.
- Keep backend/tests/test_feature_2_onboard.py green or update it to the new
  contract.
- frontend/tests/e2e/onboarding.spec.ts: path, skip-ahead warning, challenge
  feedback, localStorage persistence, and keyboard/screen-reader labels.

Acceptance gate:
- Every lesson node exists and every prerequisite layer precedes its
  dependents.
- Challenges are reproducible and graded by graph evidence.
- A cycle is displayed as a cycle.
- The curriculum is deterministic across runs.
- Keyboard and screen-reader labels pass the outline journey.
- The existing /api/onboard behavior remains backward compatible.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(onboarding): build a verified topological curriculum

Then continue to Phase 10. Do not push.
```

---

## Phase 10 — Churn, hotspots, bus factor, and the time machine (V2.7)

```text
Implement Phase 10, repository health metrics.

Goal: extend the event feed into a repository-health view: churn velocity,
hotspot score, ownership/bus factor, commit comparison, and a time-machine
overlay. Every metric has a named formula and a date window.

Real surfaces at 839bb6e:
- backend/git_history.py and backend/repo_tracker.py already exist.
- Existing endpoints include GET /api/analysis/hotspots and
  GET /api/analysis/ownership. Preserve them.
- The existing UI is frontend/src/components/TrackingPanel.tsx.
- backend/repo_metrics.py is new; backend/api/routers/metrics.py is new and
  must be mounted in backend/api/__init__.py.

Contract:
- GET /api/metrics/summary?window_days=90
- GET /api/metrics/files?metric=hotspot&limit=20
- GET /api/metrics/compare?base=<sha>&head=<sha>
- GET /api/metrics/release-notes?from=<ref>&to=<ref>
- Every response includes the formula and the window.
- A repository with no git history returns available:false with a reason; it
  never fails the whole panel.

Metrics:
- Churn: added + deleted lines per file per window, from git log --numstat.
- Hotspot: normalized_churn * normalized_pagerank, both min-max scaled.
- Bus factor: the smallest number of authors whose combined line ownership
  exceeds 50% of a file; use git blame or a documented fallback.
- Time machine: a commit SHA/date selects a graph snapshot; the diff is
  node/edge-level, not file-only.
- Release notes: commits between two refs grouped by conventional-commit type
  and affected pillar.

Rules:
- Metrics come from git, not an LLM.
- Never run a history command outside the loaded repository root.
- A single-author repository reports bus factor 1, not an error.
- Do not duplicate the existing churn or ownership engine; extend it.
- Keep the existing analysis endpoints unchanged.

Tests:
- backend/tests/test_repo_metrics.py: formulas, windows, single-author bus
  factor, no-history behavior, compare, release notes, and root confinement.
- L2 tests for all four /api/metrics endpoints.
- frontend/tests/e2e/tracker.spec.ts: summary cards, hotspot table, compare,
  time machine, and empty-history state.

Acceptance gate:
- Metrics are computed from git, not an LLM.
- Formula and window are present in every response.
- A one-author repository reports bus factor 1.
- The time machine selects a commit and shows the node/edge delta.
- No history command runs outside the loaded repository root.
- Existing /api/analysis endpoints still pass.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(metrics): add churn, hotspots, bus factor, and history compare

Then continue to Phase 11. Do not push.
```

---

## Phase 11 — Symbol-level PR impact (V2.7)

```text
Implement Phase 11, symbol-level PR impact.

Goal: replace the 25-file cap and file-level risk with a symbol-level contract
diff: removed/changed signatures, removed exports, changed routes, broken
cross-stack callers, and missing tests. Keep the existing endpoint and add the
deeper fields.

Real surfaces at 839bb6e:
- backend/pr_impact.py contains build_pr_impact.
- backend/impact_analyzer.py contains the existing impact logic.
- backend/api/routers/pr_chat.py serves /api/pr/report, /api/pr/chat, and
  /api/pr/sarif. Preserve those paths.
- POST /api/impact/pr is in backend/main.py.
- The existing UI is frontend/src/components/ImpactPanel.tsx and the PR bot
  surfaces. Do not create a parallel panel without wiring and deleting the
  dead one.
- Existing tests are in backend/tests/test_feature_1_pr_bot.py.

Contract:
- POST /api/impact/pr keeps its path. Additive fields:
  schema_version:2, base, head, files_analyzed, truncated,
  breaking:[{kind,node_id,path,old_signature,new_signature,callers,
  missing_tests}], api_contracts:{added,removed,changed}, test_gaps, and
  risk:{score,band,breakdown}.
- Remove MAX_FILES_ANALYZED = 25. Use a time/byte budget. If the budget is
  exceeded, return truncated:true with the exact cutoff and never claim
  completeness.
- A breaking change requires evidence: an old/new signature, a removed node, or
  a changed route.
- A test gap is a heuristic with a reason, not a certainty.
- CI can run the endpoint in report-only mode first; blocking mode is opt-in
  per repository.
- Private code never leaves the machine.

Rules:
- A changed function signature reports every caller, including a frontend
  api_calls caller.
- A removed route is an API contract break.
- The 25-file cap is gone; truncation is explicit.
- The SARIF/JSON report is stable and path-safe.
- Keep the existing PR-bot tests green.

Tests:
- backend/tests/test_pr_impact_symbols.py: changed signature, removed export,
  removed route, cross-stack caller, missing tests, and truncation.
- backend/tests/test_pr_impact_api.py: L2 contract and backward compatibility.
- Keep backend/tests/test_feature_1_pr_bot.py green.
- frontend/tests/e2e/pr-impact.spec.ts: findings, callers, risk breakdown, and
  report-only/blocking state.

Acceptance gate:
- A fixture PR that changes a function signature reports every caller,
  including a frontend api_calls caller.
- A removed route is reported as an API contract break.
- The 25-file cap is gone; budget truncation is explicit.
- The SARIF/JSON report is stable and path-safe.
- Existing PR-bot tests pass.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(pr-impact): analyze symbol-level contract breaks without a file cap

Then continue to Phase 12. Do not push.
```

---

## Phase 12 — Explainable impact simulator (V2.7)

```text
Implement Phase 12, the explainable impact simulator.

Goal: turn "what breaks?" into a three-hop, scored, explainable simulation.
The user selects a file, symbol, or route; the engine returns direct and
transitive impact with the exact paths that explain each hop, plus a score
breakdown.

Real surfaces at 839bb6e:
- backend/impact_analyzer.py contains the existing blast-radius logic.
- POST /api/impact/analyze is in backend/main.py.
- The existing UI is frontend/src/components/ImpactPanel.tsx.
- The existing client call is in frontend/src/api/features.ts.

Contract:
- POST /api/impact/analyze keeps its path. Add hops, paths, score_breakdown,
  api_boundaries, test_gaps, and explanation_ids.
- A hop is {from, to, edge_type, evidence}.
- score = min(10, 2.0*breaking + 1.0*direct + 0.5*transitive +
  0.5*api_boundary + 0.5*test_gap - 0.5*covered).
- Return the coefficients, the inputs, and every contributing node. The score
  is deterministic; the LLM writes at most a narrative, clearly labelled as
  commentary.

Rules:
- Direct/transitive sets are correct on a hand-built fixture.
- Every path is a real graph path; no edge is invented.
- The score breakdown sums to the score.
- Three hops are enforced and documented; no unbounded BFS.
- The panel shows why a node is included and lets the user open it.

Tests:
- backend/tests/test_impact_simulator.py: three-hop traversal, path evidence,
  score arithmetic, no-edge-invention, and a cycle.
- An L2 test for POST /api/impact/analyze.
- frontend/tests/e2e/impact.spec.ts: hop paths, score breakdown, node open, and
  no console errors.

Acceptance gate:
- Direct/transitive sets are correct on the fixture.
- Every path is a real graph path.
- The score breakdown sums to the score.
- Three hops are enforced.
- The panel shows why a node is included and lets the user open it.
- The existing /api/impact/analyze response remains backward compatible.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(impact): add a three-hop explainable impact simulator

Then continue to Phase 13. Do not push.
```

---

## Phase 13 — Six-engine graph-contextual security suite (V2.8)

```text
Implement Phase 13, the six-engine security suite.

Goal: replace regex-only security with six deterministic engines that use the
graph, a scorecard, suggested patch diffs, and SARIF 2.1.0.

Real surfaces at 839bb6e:
- backend/security_scanner.py, backend/taint.py, and backend/sarif.py already
  exist. Evolve them; do not create a duplicate scanner.
- POST /api/security/scan and POST /api/security/taint are in backend/main.py.
  Preserve both paths.
- The existing UI is frontend/src/components/SecurityPanel.tsx.
- A backend/security/ package split is allowed only if every existing import
  and endpoint keeps working.

The six engines:
1. Secrets: entropy + known-pattern scan, excluding fixtures and lockfiles;
   evidence includes path/line/matched rule, never the secret value.
2. Dependencies: parse lockfiles/manifests; query OSV only when the network is
   allowed; cache the result; offline mode returns "not checked", not "clean".
3. Taint: cross-file source -> sink propagation using imports, calls, and
   api_calls; preserve same-file behavior; show every path.
4. AI/MCP audit: prompt-injection surfaces, tool-permission overreach,
   unpinned/unsafe MCP configs, secrets in agent configs, and risky npx/uvx
   launchers.
5. Auth/CORS/session: route auth coverage, permissive CORS, missing rate
   limits, cookie flags, and unauthenticated state changes, mapped to real
   handlers.
6. Architecture/CI: layer violations, cycles, unreachable dangerous code, and
   unsafe workflow permissions, using the arch_rules taxonomy.

Contract:
- POST /api/security/scan keeps its path. The body gains engines,
  min_severity, offline, and include_patches.
- Response: {schema_version, available, scorecard, findings, engines,
  generated_at, limits}.
- Finding: {id, engine, severity, confidence, title, path, line, end_line,
  node_id, evidence, remediation, patch?}.
- GET /api/security/sarif?scan_id=... returns SARIF 2.1.0 with
  runs[0].tool.driver.rules.
- POST /api/security/patch returns a unified diff; it never writes to the
  repository.
- Finding ids are deterministic hashes of (engine, path, line, rule).

Rules:
- No secret value in logs, responses, SARIF, or the UI.
- Offline mode is explicit: dependency checks show "skipped", not "passed".
- Each engine returns available + reason independently.
- A patch is a suggestion, never auto-applied.
- A finding without evidence is dropped before scoring.
- The scorecard formula is published: severity weights, confidence weighting,
  and a cap per file.
- Do not add an MCP tool in this phase. The Phase 4 surface stays 13 tools and
  8 resources. run_security_scan from the plan's Appendix D is a separate,
  owner-approved contract change.

Tests:
- backend/tests/test_security_engines.py: positive and negative fixtures per
  engine, cross-file taint, offline dependency behavior, and deterministic ids.
- backend/tests/test_security_sarif.py: SARIF 2.1.0 shape, real lines, and no
  secret values.
- backend/tests/test_security_patch.py: diff applies to a temp copy and passes a
  syntax check.
- Keep backend/tests/test_feature_4_security.py and the taint tests green.
- frontend/tests/e2e/security.spec.ts: scorecard, engine filters, finding
  evidence, SARIF link, and suggested patch.

Acceptance gate:
- Every engine has positive and negative fixtures.
- Cross-file taint finds a path the old same-file scanner missed.
- OSV is never called in tests; the cache/offline path is tested.
- SARIF validates against 2.1.0 and points at real lines.
- Patch diffs apply to a temp copy and pass the syntax check.
- The scorecard is deterministic and explainable.
- No P1 false positive on the repository's own fixtures.
- The MCP surface remains 13 tools and 8 resources.
- The full author gate is green.

Commit to local experimental (one commit, no phase branch): feat(security): add six graph-contextual security engines

Then continue to Phase 14. Do not push.
```

---

## Phase 14 — Hardening, packaging, and release (release train)

```text
Implement Phase 14, hardening, packaging, and release.

Goal: make the release reproducible without adding feature scope. This phase
runs only after Phases 5-13 are committed on experimental.

Real surfaces at 839bb6e:
- pyproject.toml is the Python package definition; backend/version.py is new.
- The extension is separately versioned under extensions/vscode. Its compile
  and test suite may run as an artifact check, but you do not publish it.
- Deployment files live in render.yaml and frontend/vercel.json. Do not deploy
  without explicit owner approval.

Work:
- Add backend/version.py as the single version source; make /api/health, the
  CLI, SARIF, and package metadata agree.
- Prepare reposcope-ai as a thin metapackage; keep the PyPI reposcope package.
  Uploading is an owner-approved release action, not part of the Wren handoff.
- Add packages/reposcope-mcp/ as a launcher/configurator that delegates to
  Python; never parse code in Node.
- Add CHANGELOG.md entries, migration notes, docs/FEATURES.md limits, and
  docs/KNOWN_LIMITS.md.
- Run the full matrix: Python 3.11/3.12, Node 20, Windows and Linux, extension
  compile/test, frontend build, Playwright journeys.
- Add performance budgets: graph build on the RepoScope repository, mind-map
  render, PageRank, security scan, and context pack. Record the numbers.
- Add a release checklist and a rollback rehearsal.
- Triage the reported npm ci vulnerabilities (4 moderate, 2 high) and record
  the outcome.
- Re-measure the TOON benchmark at the release commit; do not reuse a stale
  table.
- Verify main is clean; tag only when the owner approves.

Explicitly out of scope:
- Extension publishing to Open VSX.
- Extension publishing to the VS Code Marketplace.
- Building or uploading a VSIX for publication.
- Marketplace publisher accounts, Azure DevOps PATs, or OVSX_TOKEN work.
- Any release note that claims an extension publication.

Rules:
- One version source; no drift between API, CLI, SARIF, and package metadata.
- A clean install must work from the packaged artifacts, not the checkout.
- All L1/L2/L3 gates green on both operating systems.
- Performance budgets are recorded with hardware and repository size.
- docs/QA_REPORT.md reflects the final numbers.
- No secret, token, .env value, or local absolute path is embedded in an
  artifact or a log.
- Do not push, tag, publish, or deploy. Produce the artifacts, the checklist,
  and the rollback evidence; the owner approves the release actions.
- The owner must have tested the release candidate and approved the release.

Acceptance gate:
- One version source; no drift.
- Clean install from the packaged artifacts.
- All L1/L2/L3 gates green on Windows and Linux.
- Performance budgets recorded.
- docs/QA_REPORT.md reflects the final numbers.
- The rollback rehearsal is recorded.
- The release checklist is complete and the owner has approved the release.
- No extension publishing work is present.

Commit to local experimental (one commit, no phase branch): chore(release): harden, package, and verify the v2.5–v2.8 train

Stop after the handoff. This is the final phase; hand off the full range 5-14 for batch verification.
```

---

## Handoff template

Every phase handoff in `WREN.md`, `COMS.md`, and `DIALOGUE.md` must contain:

1. **Branch and commit:** `experimental`, exact SHA, base SHA (the prior
   `experimental` tip), and confirmation that the phase is committed and
   `git status` is clean.
2. **Files and claims:** every changed file, every claim released, and any
   deviation from the plan's suggested paths.
3. **Commands and results:** the exact gate commands and their results,
   including the phase-specific fixture or benchmark.
4. **Limits and skips:** every skipped test or unsupported environment with the
   reason.
5. **Next open decision:** the one thing Rook or the verifier must decide before
   the batch verification.

A handoff without all five parts is incomplete. The phase commit is mandatory
before starting the next phase; a handoff with uncommitted changes is rejected.

After Phase 14, add one final range summary to `WREN.md`, `COMS.md`, and
`DIALOGUE.md` with the base SHA before Phase 5, the ten phase SHAs in order, the
final SHA, the aggregate gate results, and any cross-phase limits. Then stop and
wait for the batch verifier. Do not push.
