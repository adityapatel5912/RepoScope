# RepoScope — QA Report

What is verified, how, and — explicitly — what is **not** covered.

## Current verification — 2026-10-23

This is the status of the shipped v2.0 tree. The Sprint 3 journey table below
is kept as a historical record; where it disagrees with this section, this
section wins.

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest -q` | **333 passed** |
| Frontend type-check | `npx tsc --noEmit` | **clean** |
| Frontend production build | `npm run build` | **built successfully** |
| Local mode | `GET http://127.0.0.1:4100/api/health` | **200**, watcher on |
| Graph snapshot | sidebar in local mode | **363 files, 1,864 nodes, 3,418 edges** (last run; screenshot captures may differ) |
| MCP stdio sweep | `tools/list`, `resources/list`, read rounds | **8 tools, 5 resources**, clean ping |
| MCP over HTTP | `POST /mcp` Streamable HTTP | initialize + tool call succeeded |
| OpenCode client | `opencode mcp list` | **`✓ reposcope connected`** |

Manual checks are **not** covered by those commands and remain unchecked in
[`VERIFICATION_CHECKLIST.md`](VERIFICATION_CHECKLIST.md):

- selecting a folder in the native OS dialog;
- installing and exercising the extension in a real VS Code/Cursor window;
- Open VSX search visibility after publisher email verification;
- a live PR Bot comment against a real pull request;
- one OpenCode `read_mcp_resource` bridge, which stalled and returned an
  unknown message ID while direct stdio reads and tool calls worked.

The QA harness lives in [`scripts/qa.py`](../scripts/qa.py) and
[`frontend/tests/e2e/`](../frontend/tests/e2e/). Run it with:

```bash
python scripts/qa.py          # boot, wait, test, report
python scripts/qa.py --grep J01
python scripts/qa.py --headed  # watch it run
```

It writes `qa-report/index.html` and `qa-report/results.json`, and commits
screenshots to [`docs/screenshots/v2/`](screenshots/v2/).

## Why this exists

Unit tests prove functions work. **Only opening localhost proves the
product works.**

RepoScope already had a browser-QA history — `.playwright-mcp/`, 13 console
logs and 100+ page snapshots from 2026-09-26. That audit found real
defects that no unit test can catch:

| Defect found by the manual audit | Why unit tests miss it |
|---|---|
| `<circle> attribute cx: Expected length, "NaN"` (×318 in one session) | React SVG geometry error — only exists in a rendered DOM |
| `<pattern> attribute x/y: Expected length, "NaN"` | Same class — SVG defs, not application state |
| `Failed to load resource: 404 → /api/tour/generate` | Route-level failure |
| `Password field is not contained in a form` | DOM semantics — an a11y defect |

But that directory is **gitignored**, so none of it prevented regression,
and RepoScope had no e2e suite, no Playwright dependency, no test script
in `frontend/package.json`, and no CI workflow that opened a browser.

This harness closes that gap.

## The four-layer gate — "Definition of Verified"

No feature is Done until it clears all four layers.

| Layer | Tool | Target | Proves |
|---|---|---|---|
| **L1 Unit** | `pytest` | functions in isolation | logic is correct |
| **L2 Contract** | `httpx` → live `uvicorn` | `127.0.0.1:8010` | the API contract holds on a running server |
| **L3 Journey** | Playwright | real Chromium, real DOM | the user flow works end-to-end |
| **L4 Visual + console** | Playwright screenshots + chrome-devtools MCP | rendered pixels + browser console | it **looks** right **and** is error-free |

**L4 is the layer that did not exist.** A journey can render perfectly
while the console fills with React key warnings, unhandled rejections,
404 assets, and CORS failures.

### Hard rules

| Rule | Detail |
|---|---|
| R-QA1 | **Zero console errors** per journey (`console.error`, `pageerror`, unhandled rejections). |
| R-QA2 | **Zero unexpected HTTP failures.** No 4xx/5xx the app initiates, except declared intents. |
| R-QA3 | **Every journey commits a screenshot** to `docs/screenshots/v2/`. That directory is deliberately **not** gitignored — the evidence must survive. |
| R-QA4 | **Every journey has a visual-regression baseline** via Playwright `toHaveScreenshot()`. Baselines are committed; updates are explicit (`--update-snapshots`), never automatic. |
| R-QA5 | **A known-bad whitelist exists and is reviewed.** Each entry carries an inline justification. An unexplained console error fails the build. |
| R-QA6 | **QA is a gate in every sprint**, not a phase at the end. |
| R-QA7 | **MCP servers are instruments, not the gate.** The committed Playwright suite is the gate. |

## Hermeticity

`REPOSCOPE_QA=1` makes a QA run hermetic:

- No GitHub API calls — a fixture repository is loaded instead.
- No LLM provider calls.
- No writes to the real `data/repo_state.json`.
- Fixed seed and fixed clock.

A QA run that depends on the network fails for the wrong reason, and a
failure you cannot distinguish from a product bug is worse than no gate.

## The smoke matrix

> **Numbering note (2026-10-22).** This report is the Sprint 3 record and predates the final
> journey numbering in `docs/ROADMAP_V2.md` §18.4. Its "J18 — local mode" is **J12** in the
> committed suite, and its "J19 — repo map" is unchanged. The rows below are left as written so
> the report remains an accurate account of the run it describes; the authoritative mapping is
> the roadmap table and `frontend/tests/e2e/journeys.spec.ts`.

| # | Journey | Status |
|---|---|---|
| J00 | Backend healthy, UI mounts | ✅ implemented |
| J01 | A loaded repo renders a populated graph (not a blank canvas) | ✅ implemented |
| J02 | Clicking a file node opens the detail drawer | ✅ implemented |
| J03 | `GET /api/arch/rules` serves the shared rule set | ✅ implemented |
| J04 | The graph survives a page reload with no console errors | ✅ implemented |
| J05 | No graph node is painted under the sticky header | ✅ implemented |
| J06 | The analysis endpoints serve the graph intelligence (hubs, cycles, unreachable) | ✅ implemented |
| J07 | The churn heatmap overlay renders, and the layer legend stays readable | ✅ implemented |
| J08 | The architecture cluster view renders | ✅ implemented |
| J09 | Ask a question → SSE streams an answer with citation pills | ⬜ Sprint 4 |
| J10 | Impact analysis → risk score and rings render | ⬜ Sprint 4 |
| J11 | Code tour → steps render and advance | ⬜ Sprint 4 |
| J12 | PR bot → markdown comment preview renders | ⬜ Sprint 4 |
| J13 | Export PNG + SVG → downloads produced, non-zero size | ⬜ Sprint 4 |
| J14 | File tree → filter narrows the list | ⬜ Sprint 4 |
| J15 | BYOK → provider set, status bar reflects it | ⬜ Sprint 4 |
| J16 | Student mode → 3 levels and quizzes render | ⬜ Sprint 4 |
| J17 | Security scan → flags render, severity ordered | ⬜ Sprint 4 |
| J18 | **Local mode** — the LOCAL MODE badge shows, a file edit updates the graph **without a page reload** | ✅ implemented |
| J19 | **Repo map** — the budgeted map renders and the token reduction % is shown | ✅ implemented |
| J20 | **MCP server** — stdio handshake, `tools/list`, one real tool call | ✅ backend-tested (8 tools, 5 resources); OpenCode client connected |
| J21 | **IDE deep link** — node click produces the exact expected URI per editor | ✅ implemented (`frontend/src/utils/ideLinks.ts`); ⬜ no committed browser journey |
| J22 | **Call edges** — graph renders `calls` edges after the parser rewrite | ✅ implemented; covered by parser and graph tests |
| J23 | **Clusters** — expand/collapse preserves the pyramid when toggled off | ✅ implemented; ⬜ no committed browser journey |
| J24 | **Churn heatmap** — hotspot rings distinct from the layer fill | ✅ implemented |
| J25 | **Cycles** — cycle list matches the API result | ✅ implemented; covered by graph-analysis tests |
| J26 | **PR boundary violation** — flagged in the PR comment | ⬜ Sprint 6 |
| J27 | **SARIF** — valid against the 2.1.0 schema | ⬜ Sprint 6 |
| J28 | **50k-file traversal** — latency budget met | ⬜ Sprint 7 |

**11 journeys pass**, 0 console errors, 0 unexpected HTTP failures.

Two of them are new in Sprint 3:

- **J18 (local mode)** — loads a **writable copy** of a fixture, asserts the LOCAL MODE
  badge is visible, edits a file, and asserts the graph's node count rises **without a page
  reload**. The "without a reload" part is proved with a marker written onto `window`: a
  reload would wipe it. It also checks the backend's own graph really contains the new
  symbol — the browser is verified against the source, not against itself.

  The copy matters. Editing the committed fixture would corrupt it for every later run,
  and the failure would look like a product bug.

- **J19 (repo map)** — asserts the reduction percentage is a real number, and that the
  API's own answer agrees with the panel: the map is inside its token budget, the baseline
  is non-zero, and the map names files, symbols and layers.

> **One assertion in J18 was rewritten after it failed for the WRONG reason.** It originally
> counted the ReactFlow nodes in the DOM. ReactFlow only renders what is in the viewport,
> so adding a symbol reflows the pyramid and changes which nodes are on screen — the count
> went *down*. The graph's own node count is the honest signal.

## The role of each MCP server

| MCP server | Role in QA | Explicitly **not** for |
|---|---|---|
| **Playwright** (`@playwright/mcp`) | Interactive exploration; triaging a failure by hand; **drafting the first version of a journey spec** from a recorded interaction | The CI gate. CI must run the committed suite, not an agent |
| **chrome-devtools** | Console error triage; network waterfall inspection; performance tracing; catching React key warnings, unhandled rejections, oversized payloads, CORS failures — none of which a screenshot shows | — |
| **Tavily** | Resolving **expected** behaviour where the spec is ambiguous — the correct `vscode://` URI form, current MCP transport wording, correct ReactFlow LOD thresholds, GitHub REST shapes for webhooks; competitor-parity checks | — |

**The distinction that matters:** MCP servers are how a human or an
autonomous agent *investigates*. The committed Playwright suite is how the
build *gates*. Using an MCP agent as the CI gate would make every run
non-deterministic and non-reproducible — the opposite of QA.

## Defects found by this harness

| Severity | Defect | Status |
|---|---|---|
| **P1** | **The analysis endpoints and the UI could describe DIFFERENT codebases.** Two sources for "the current graph" — the live session and the orchestrator's cache — and a request could read one from each. The repo-map panel showed a map for one repository beside a "full repository" figure for another. | ✅ Fixed — one function, `orchestrator.current_graph()`, returns the graph and the root it describes. Guarded by `backend/tests/test_graph_source.py` |
| **P1** | **The QA gate could test YESTERDAY'S BUILD.** `start_backend()` reused any server already listening on :8010. The backend IS the thing under test, so a QA run against someone else's server tested an hour-old build — and could be green while the code on disk was broken. | ✅ Fixed — the harness now takes its ports from whatever was there and always starts its own servers |
| **P1** | **The QA run wrote to the developer's real state file**, and the stale state made the QA server resume a session over the developer's own repository. | ✅ Fixed — in QA mode the state lives in the temp directory, and the server never resumes a session |
| **P1** | **Loading a second repository kept serving the first one's graph.** The orchestrator's graph cache was never invalidated when the active repo changed, so the analysis endpoints and the UI described a codebase that was no longer loaded. | ✅ Fixed — `orchestrator.clear_graph_cache()` |
| **P2** | **Duplicate node ids.** Four `__init__` methods in one file all produced the id `func:<rel>:__init__`. Duplicate ids break React list keys in the graph renderer and corrupt the graph store. Found by the vendored real-world fixture. | ✅ Fixed — colliding names now get a deterministic `@{lineno}` suffix |
| **P2** | **Root node painted under the sticky header.** `fitView` clamped its zoom at 0.3, could not fit a tall pyramid, and centred the overflow. The top 24px was under the TopBar (`z-50`): the root node was clipped and unclickable. | ✅ Fixed — the fit-view floor now matches the `minZoom` prop (0.2). Guarded by journey J05. |
| **P2** | **Mojibake in the graph title** after a Windows-1252 round-trip re-encoded `GraphView.tsx`. Invisible to unit tests and to the console gate — only a human reading the screenshot caught it. | ✅ Fixed — `scripts/repair_mojibake.py` reverses the mis-decode; the encoding test names it in its failure message |
| **P2** | **The node drawer covered the LAYERS legend** — both were `absolute top-4 right-4`. | ✅ Fixed — the legend yields while a node is selected |
| **P2** | **The churn legend covered the LAYERS legend** — same cause. | ✅ Fixed — the churn spectrum now lives inside the layer legend card |
| **P2** | **The `cluster` node type was never registered in `nodeTypes`**, so ReactFlow drew plain white boxes with no layer colour and no file count. | ✅ Fixed |
| **P2** | **Cluster cards overlapped each other** — a 190px pitch against a 260px card. | ✅ Fixed — the pitch is now `width + 40` |
| **P2** | **The fit-view placed the cluster cards under the floating toolbar**, making them unclickable. ReactFlow 11 only supports a numeric `padding`, so an asymmetric fit is impossible. | ✅ Fixed — `fitClearOfToolbar()` nudges the viewport after the fit |
| **P3** | The Repository card showed em dashes for NODES and EDGES on both the load and mount paths. | ✅ Fixed |
| **P3** | The ReactFlow canvas overlaps the header by 6px. Cosmetic — the canvas background sits behind the header's bottom edge. | ⬜ Not fixed (Sprint 0 scope) |

## What is NOT covered — read this

Stating the gaps matters more than claiming completeness.

- **No visual-regression baselines yet.** J00–J05 assert behaviour and
  capture screenshots, but no `toHaveScreenshot()` comparison is wired up.
  Rule R-QA4 is specified but not yet enforced.
- **No CI wiring for the browser run.** `.github/workflows/qa.yml` runs
  the unit and contract layers; the journey layer runs locally and in the
  nightly job.
- **The chat journey is not automated** — it needs a stubbed LLM
  provider, which arrives with the `REPOSCOPE_QA=1` provider stub.
- **Only Chromium is covered.** Firefox and WebKit are not in the project
  matrix.
- **No accessibility audit.** The manual audit found a password field
  outside a form; that defect class is not yet asserted automatically.
- **The VS Code extension cannot be driven by Playwright.** It has a
  documented manual checklist and committed screenshots instead.
- **No performance budget is asserted** in CI — the 50k-file traversal
  target (J25) is still a plan.

## Reproducing a failure

```bash
python scripts/qa.py --headed --grep J01     # watch one journey
cd frontend && npx playwright show-trace test-results/<dir>/trace.zip
cd frontend && npx playwright test --ui      # interactive
```

The trace, the failure screenshot, and the captured console output are
all written to `frontend/test-results/`.
