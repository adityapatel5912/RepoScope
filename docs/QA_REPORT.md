# RepoScope — QA Report

What is verified, how, and — explicitly — what is **not** covered.

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

| # | Journey | Status |
|---|---|---|
| J00 | Backend healthy, UI mounts | ✅ implemented |
| J01 | A loaded repo renders a populated graph (not a blank canvas) | ✅ implemented |
| J02 | Clicking a file node opens the detail drawer | ✅ implemented |
| J03 | `GET /api/arch/rules` serves the shared rule set | ✅ implemented |
| J04 | The graph survives a page reload with no console errors | ✅ implemented |
| J05 | No graph node is painted under the sticky header | ✅ implemented |
| J06 | Ask a question → SSE streams an answer with citation pills | ⬜ Sprint 1 |
| J07 | Impact analysis → risk score and rings render | ⬜ Sprint 1 |
| J08 | Code tour → steps render and advance | ⬜ Sprint 1 |
| J09 | PR bot → markdown comment preview renders | ⬜ Sprint 1 |
| J10 | Export PNG + SVG → downloads produced, non-zero size | ⬜ Sprint 1 |
| J11 | File tree → filter narrows the list | ⬜ Sprint 1 |
| J12 | BYOK → provider set, status bar reflects it | ⬜ Sprint 1 |
| J13 | Student mode → 3 levels and quizzes render | ⬜ Sprint 1 |
| J14 | Security scan → flags render, severity ordered | ⬜ Sprint 1 |
| J15 | **Local mode** — `reposcope run .` boots, graph renders, file edit updates the graph **without reload** | ⬜ Sprint 3 |
| J16 | **MCP server** — stdio handshake, `tools/list`, one real tool call | ⬜ Sprint 4 |
| J17 | **IDE deep link** — node click produces the exact expected URI per editor | ⬜ Sprint 4 |
| J18 | **Call edges** — graph renders `calls` edges after the parser rewrite | ⬜ Sprint 1 |
| J19 | **Clusters** — expand/collapse preserves the pyramid when toggled off | ⬜ Sprint 2 |
| J20 | **Churn heatmap** — hotspot rings distinct from the layer fill | ⬜ Sprint 2 |
| J21 | **Cycles** — cycle list matches the API result | ⬜ Sprint 2 |
| J22 | **Repo map** — budgeted map renders, token reduction % shown | ⬜ Sprint 3 |
| J23 | **PR boundary violation** — flagged in the PR comment | ⬜ Sprint 6 |
| J24 | **SARIF** — valid against the 2.1.0 schema | ⬜ Sprint 6 |
| J25 | **50k-file traversal** — latency budget met | ⬜ Sprint 7 |

The ✅ journeys are the Sprint 0 foundation. The rest fill in as their
sprints land.

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
| **P2** | **Duplicate node ids.** Four `__init__` methods in one file all produced the id `func:<rel>:__init__`. Duplicate ids break React list keys in the graph renderer and corrupt the graph store. Found by the vendored real-world fixture. | ✅ Fixed — colliding names now get a deterministic `@{lineno}` suffix |
| **P2** | **Root node painted under the sticky header.** `fitView` clamped its zoom at 0.3, could not fit a tall pyramid, and centred the overflow. The top 24px was under the TopBar (`z-50`): the root node was clipped and unclickable. | ✅ Fixed — the fit-view floor now matches the `minZoom` prop (0.2). Guarded by journey J05. |
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
