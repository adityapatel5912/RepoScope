# RepoScope — QA Report

What is verified, how, and — explicitly — what is **not** covered.

## Phase 0 baseline restoration — 2026-10-26

The CI suite was red before any V2.5 feature work. This section records the
measured before/after so the fix can be audited.

| Check | Before | After |
|---|---|---|
| `pytest -q`, Python 3.11, `backend/requirements.txt` only | **30 failed, 305 passed** | **343 passed** |
| `pytest -q`, Python 3.12, `backend/requirements.txt` only | not run (missing numerical stack) | **343 passed** |
| `pytest -q`, local Python 3.14 | 335 passed | **343 passed** |
| `python -m pip check` | not run | **no broken requirements** |
| `python -m compileall -q backend/` | not run | **clean** |
| `GET /health` | `{"status": "ok"}` | **`{"status": "ok"}`** |
| `GET /api/health` | `"healthy"`, but `qa.yml` asserted `"ok"` | **`"healthy"` + additive `schema_version` and cached `graph`** |
| Frontend production build | not gated in CI | **built successfully** (`assets/index-CMSb0cnC.js`) |
| VS Code extension | compiled/tested | **compile clean, 20/20 tests pass** |

**Root causes fixed:** `numpy` and `scipy` were missing from the deployment
requirements while PageRank needs them; `mcp`, `typer`, and `watchdog` were
declared only in `pyproject.toml`; `mcp 2.x` removes
`mcp.server.fastmcp.FastMCP`; and the L2 contract asserted the liveness
string against the application endpoint. `mcp` is now pinned to
`>=1.29,<2`, and both dependency files are checked by
`backend/tests/test_dependency_contract.py`.

**Still not covered at Phase 0:** the L3 Playwright journeys were not part of
the Phase 0 gate; they now run on every push and are green at Phase 1 (below).
The Python 3.13/3.14 runs are local confidence checks, not deployment targets.

## Phase 1 CI gate — 2026-10-26

Phase 1 (`d885d92`) adds graph schema v2 and freezes `GET /api/mindmap`. The
first CI runs exposed test-infrastructure defects, not product regressions.
Each run below is recorded with the fix that closed it.

| Run | Result | Finding | Fix |
|---|---|---|---|
| `40319380840` | **7 failed / 398 passed** on 3.11 and 3.12 | Six endpoint tests required a real AI provider before their stubbed LLM; one churn test saw a one-commit shallow checkout. | `275d66b`: synthetic-provider fixture and `fetch-depth: 0`. |
| `40320122480` | **1 failed / 404 passed**; L2/L3 skipped | The MCP stdio helper closed stdin before `tools/list` was read. | `25ba011`: hold the pipe open and wait per response. |
| `40320667722` | L1 and L2 green; L3 failed | Playwright tried to start a second backend on the port `scripts/qa.py` already owned. | `da0e892`: the harness tells Playwright it owns the servers. |
| `40321455598` | 17/17 journeys passed, job exit 143 | The harness's process-group cleanup terminated the CI runner. | `7c5b467`: start harness servers in their own session. |
| `40322052797` | **green on all six jobs** | — | Python 3.11, Python 3.12, L2 contract, L3 journeys, frontend build, extension. |

Local verification for Phase 1: **405 passed** on Python 3.11, 3.12, and
3.14; `pip check` and `compileall` clean; frontend build green; extension
20/20; 17/17 Playwright journeys under `CI=1`. The golden v1 snapshots were
not regenerated.

## Current verification — 2026-10-25

This is the status of the shipped v2.0 tree. The Sprint 3 journey table below
is kept as a historical record; where it disagrees with this section, this
section wins.

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest -q` | **335 passed** |
| Frontend type-check | `npx tsc --noEmit` | **clean** |
| Frontend production build | `npm run build` | **built successfully** (`assets/index-CMSb0cnC.js`) |
| Health contract | `GET /api/health` | **200**; response version **2.0.0**, matching `pyproject.toml` |
| Local mode | `GET http://127.0.0.1:4100/api/health` | **200**, watcher on. The UI evidence predates the health-version-only fix; graph behavior is unchanged. |
| Graph snapshot | sidebar in local mode | **348 files, 1,863 nodes, 3,419 edges** |
| Browser preview | native folder picker + in-browser parser | **75 files, 315 nodes, 310 edges**; Python, JavaScript, TypeScript |
| VS Code extension | VS Code 1.143.0, `adityapatel5912.reposcope@2.0.1` | Activity map, status bar, CodeLens, context menu, URI handler, offline/recovery |
| Open VSX | API + search + listing page | **2.0.1**, **288 downloads**, searchable, direct page HTTP 200, namespace `verified:false` |
| CSP / WebAssembly | production CSP | parser WASM and all five grammars loaded |
| MCP stdio sweep | `tools/list`, `resources/list`, read rounds | **8 tools, 5 resources**, clean ping |
| MCP over HTTP | `POST /mcp` Streamable HTTP | initialize + tool call succeeded |
| OpenCode client | `opencode mcp list` | **`✓ reposcope connected`** |

The remaining manual checks are:

- Cursor/VSCodium extension testing;
- Open VSX namespace verification and the verified badge;
- Render redeployment showing version 2.0.0;
- VS Code Marketplace publishing (Azure DevOps PAT).

### Agent-run evidence — 2026-10-25

The final pass used Windows automation and browser instrumentation. This is
evidence, not a substitute for the four remaining manual checks.

| Area | Evidence |
|---|---|
| Native folder picker | Win32 child enumeration plus `BM_CLICK` on the dialog's **Open** button selected the same folder twice. Result: **75 files, 315 nodes, 310 edges**, languages `python, javascript, typescript`; the canvas showed **BROWSER PREVIEW · VERDICT**. |
| Picker cancel | Closing the dialog preserved the previous preview and did not raise an error toast. |
| Picker refusal | A Playwright monkeypatch made `showDirectoryPicker` throw `NotAllowedError`; the UI showed: “Folder access was not granted. Choose the folder again and allow access when the browser asks.” |
| Preview privacy | The network trace after selection contained only `GET` requests; no folder contents were uploaded. |
| Browser preview scope | Chat, Track/Incident, Student Mode, Insights, Repo Map, Security, Commit, Tour, and Impact panels are hidden while a preview is active. The graph takes the full height. |
| Server local mode | **348 files, 1,863 nodes, 3,419 edges**; watcher add/remove updated the canvas without a reload. |
| Reload / clear | Reload restored the server repository and cleared the browser preview; **Clear repository** showed the empty state; reload restored the backend repository. |
| Graph modes / export | Grouped, flat, cluster, churn, and layout direction worked; PNG and SVG exports produced non-empty files on separate page loads. |
| VS Code extension | Activity map: **348 files, 1,863 nodes, 3,419 edges**. Status bar: `RepoScope: 12 dependents | Risk: Critical` on `backend/graph_store.py`, `9 dependents` on `backend/main.py`. CodeLens: `View Callers (6)` for `graph_summary`, `No callers` for `health`. Explorer menu: **RepoScope: Focus this node in the canvas**. `reposcope://open` opened `backend/main.py` at line 392. |
| Extension failure/recovery | Wrong port `9999` showed `RepoScope: offline`; restoring `:8000` and reloading recovered the status bar and CodeLens. Reload reconnected the view. |
| CSP / parser | With the production CSP, the in-browser parser loaded WebAssembly and Python, JavaScript, TypeScript, Go, and Rust grammars. Regression test asserts `wasm-unsafe-eval` is present and `'unsafe-eval'` is absent. |
| Health version | `backend/main.py` now reports **2.0.0**; a temporary server on `:4101` returned `{"version":"2.0.0",...}`. A new test reads `pyproject.toml` and fails if the health version drifts. |
| Quiz layout | The longest Student Mode quiz text satisfies `clientWidth == scrollWidth` after the overflow fix. |

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

### Final v2 pass

| Severity | Defect | Status |
|---|---|---|
| **P1** | **The production CSP blocked the in-browser parser.** Chrome refuses `WebAssembly.instantiate` under `script-src 'self'`, so choosing a folder could leave the preview empty. | ✅ Fixed — CSP now includes `wasm-unsafe-eval`; it does not re-enable JavaScript `eval`. Guarded by `backend/tests/test_health.py` and a five-grammar browser check. |
| **P1** | **`/api/health` reported version `1.0.0` while the package was `2.0.0`.** A deploy could look healthy while advertising the wrong release. | ✅ Fixed — health now returns `2.0.0`; a regression test reads `pyproject.toml` and compares it to the live response. Render needs a redeploy. |
| **P2** | **A refused folder picker looked exactly like a cancel.** Every rejection was swallowed, so a blocked picker left the button idle with no explanation. | ✅ Fixed — `AbortError` remains a quiet cancel; `SecurityError`, `NotAllowedError`, and unknown failures surface actionable messages. |
| **P2** | **A browser preview could show server-backed panels for a different repository.** Chat, Track, Student Mode, and analysis cards read the server's index while the canvas showed a folder parsed in the browser. | ✅ Fixed — the preview hides those surfaces, uses the folder name without an owner prefix, and gives the graph the full height. |
| **P3** | **Long Student Mode quiz text overflowed its card.** | ✅ Fixed — wrapping and `min-w-0` constraints; verified with `clientWidth == scrollWidth`. |

### Earlier v2 passes

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
- **Cursor and VSCodium have not been exercised.** VS Code 1.143.0 was driven
  with Windows UI automation; Cursor/VSCodium remain in the checklist.
- **No performance budget is asserted** in CI — the 50k-file traversal
  target is still a plan.
- **The deployed Render service still reports `1.0.0`.** The fix is local and
  must not be deployed without explicit approval.
- **The Open VSX namespace is still unverified.** The listing is searchable,
  but the verified badge and stable ranking are not guaranteed.

## Reproducing a failure

```bash
python scripts/qa.py --headed --grep J01     # watch one journey
cd frontend && npx playwright show-trace test-results/<dir>/trace.zip
cd frontend && npx playwright test --ui      # interactive
```

The trace, the failure screenshot, and the captured console output are
all written to `frontend/test-results/`.
