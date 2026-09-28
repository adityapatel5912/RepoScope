# RepoScope — Features

Every feature, how to use it, and its limits. All screenshots live in
[screenshots/](screenshots/).

## Architecture Graph
- **What**: a connectivity pyramid built from AST (Python) and regex (JS/TS)
  parsing. The repo sits at the top (row 0); files are bucketed into five
  connectivity-ranked rows below it (most-imported first), with key functions
  of core files expanded as smaller child nodes at half-rank. Nodes are
  colored by architecture layer (client / backend / storage / external /
  compute) with a legend, minimap, and zoom controls.
- **What the pyramid means**: rows rank importance, computed from the import
  graph — score = incoming ×2 + outgoing. Entry points float to the top;
  config, docs, and test data sink to the bottom. Rows wider than 18 nodes
  wrap into continuation slots.
- **How to read edges**: every edge is directed and flows downward.
  `imports` edges run from importer to imported; `contains` edges connect a
  file to its functions/classes; the repo node fans out to the top row.
  Arrowheads show direction; the node drawer lists incoming/outgoing counts.
- **Expand/collapse function nodes**: "Group by directory" in the floating
  toolbar toggles function/class children for core files (rows 1–2). Toggle
  layout direction flips the pyramid (bottom-up view); Re-run layout resets
  the camera to the repo root.
- **How to export**: the toolbar's camera buttons export the current viewport
  as high-res PNG or SVG. Zoom/fit first — the export captures what's on
  screen.
- **Use**: load a repo (demo buttons or URL) and ask any chat question — the
  graph renders from the `context` SSE event. Click any node for the details
  drawer (Ask / Analyze impact / Start tour).
- **Limits**: edge rendering is capped at 1,000 edges (imports + containment
  win over noise); a deterministic collision pass guarantees no two nodes
  overlap, at the cost of occasionally nudging crowded child nodes sideways.

![Graph](screenshots/graph.png)

## Conversational Q&A
- **What**: SSE-streamed answers grounded in the code graph + README, with
  file/function/line citations rendered as clickable pills, markdown tables,
  and dark copy-able code blocks. Three modes: Understand, Track, Incident.
- **Use**: type in the chat panel; Enter sends, Shift+Enter adds a newline,
  the mic button (left) accepts voice input (Web Speech API).
- **Limits**: answers are grounded in the built graph — files absent from the
  graph (e.g. assets) may not be cited.

![Chat](screenshots/chat.png)

## Code Tours
- **What**: type a topic ("auth", "encryption") and the LLM picks an ordered
  reading list. The graph auto-pans to each stop; the current node gets a
  numbered badge and coral ring, past steps get a check, a progress bar tracks
  position, and each step explains why the file matters.
- **Use**: sidebar → Code Tour → topic → Start → Prev/Next or the step dots.
- **Limits**: topic ≤ 100 chars; generation takes 15–60 s (LLM-backed).

![Tour](screenshots/tour.png)

## What-If Impact Analysis
- **What**: pick a function or file and get its blast radius — direct and
  transitive callers — plus a risk score, narrative, and suggested tests.
  The graph dims unaffected nodes and rings target/direct/transitive.
- **Use**: sidebar → What-If Impact → target name → Analyze (depth 1–5).
- **Limits**: target must match a node label; depth > 3 can get noisy.

![Impact](screenshots/impact.png)

## Repo Tracking
- **What**: on-demand check for new commits, PRs, issues, and releases since
  the last check, grouped by change type (feat/fix/breaking/…).
- **Use**: Track mode → "check the repo" or "what changed?".
- **Limits**: unauthenticated GitHub is rate-limited; add `GITHUB_TOKENS`.

![Tracking](screenshots/tracking.png)

## Reverse Build Prompt
- **What**: generates an agent-ready "Build me a…" prompt that would rebuild
  the loaded repo — purpose, stack, architecture, features, data flow, UI
  feel — under 400 words.
- **Use**: graph toolbar → **Build Prompt** → Copy or Save as .md.
- **Limits**: LLM-backed (up to ~2 min on slow providers).

## File Tree
- **What**: GitIngest-style tree (`├─` / `│`) of every analyzed file with
  search filter and single-file download (original filename preserved).
- **Use**: sidebar → File Tree → filter or download.

## Export (PNG / SVG)
- **What**: toolbar → camera / SVG icons. High-res PNG (2× pixel ratio);
  toolbar, minimap, legend, and drawer are excluded automatically.

## BYOK
- **What**: paste a GitHub PAT (`ghp_…` / `github_pat_…`) to clone private
  repos and raise API limits. Stored in memory only, per browser session.
- **Limits**: session-scoped — reload clears it.

## Multi-key rotation & health
- **What**: every LLM provider accepts comma-separated keys
  (`GROQ_API_KEYS=k1,k2`); 429s rotate to the next key, then to the next
  provider (OpenRouter → Groq → NVIDIA NIM). `GET /api/health` reports
  uptime, memory, and configured key counts.
- **Use**: set keys in `.env`; watch the status bar's "Backend: ok" dot.

---

# NEW in 3.0

## PR Bot (Impact Report as a GitHub Comment)
- **What**: computes the blast radius of every file changed in a pull request
  (reverse-BFS over the code graph) and renders a GitHub-ready markdown
  comment: risk score /10, affected-files table with direct/transitive impact
  counts, suggested tests, and a mermaid impact graph (GitHub renders mermaid
  natively in PR comments).
- **Use (UI)**: Impact panel → PR Bot → enter PR number → **Generate PR
  Comment Preview** → Copy comment → paste into the PR. Export the graph as
  PNG (toolbar) to attach the highlighted blast radius.
- **Use (CI)**: copy [.github/workflows/pr-impact.yml](../.github/workflows/pr-impact.yml)
  into your repo — it calls `POST /api/impact/pr` on every PR and posts the
  report automatically (needs `pull-requests: write`).
- **API**: `POST /api/impact/pr` `{repo_url, pr_number, github_token?,
  post_comment?}` → `{risk_score, risk_level, affected_files, comment, …}`.
- **Limits**: analyzes the first 25 changed files; files not present in the
  graph (new files, assets) are reported but not traversed.

## Student Onboarding Mode
- **What**: ranks every file by the pyramid score (incoming ×2 + outgoing)
  into Rows 1–5 and builds a 3-level curriculum: **Level 1** = Row 1 entry
  points, **Level 2** = Rows 2–3 core modules, **Level 3** = Rows 4–5 utils &
  leaves. Each file gets an LLM-written "why it matters" note; each level has
  a 3-question checkpoint quiz (click-to-answer with explanations). The
  low-traffic Rows 4–5 also seed **3 Good First Issues** (title, file,
  description, first step).
- **Use**: toggle **Student** in the top bar → the Student Path card appears
  in the sidebar. Quiz out a level (or hit "Mark level complete") — progress
  persists per-repo in localStorage.
- **API**: `POST /api/onboard` `{repo_url?}` → `{levels[3], good_first_issues[3]}`.
- **Limits**: LLM-backed; on provider failure each level falls back to
  heuristic notes and template issues so the path is always usable.

## Voice Code Tours
- **What**: narrated tours — the Code Tour panel gains **▶ Play Tour**, which
  speaks each step ("Step 2 of 7. Now in auth_router. This handles…"),
  auto-advances to the next stop, and keeps the graph camera + highlight
  synced with the audio. Server voice: OpenRouter TTS chain
  (`fish-audio/s2.1-pro-free:free` → `deepgram/flux-tts:free`, key rotation
  preserved, `Models_TTS` env override). Fallback: browser `speechSynthesis`.
- **Use**: Code Tour → generate a tour → **▶ Play Tour**. Prev/Next/dots
  restart narration at the chosen step; 🔊 speaks just the current step;
  ⏹ stops.
- **API**: `POST /api/tts` `{text}` → `{audio_base64, format, model}`.
- **Limits**: narration ≤ 1,200 chars per request; if both server TTS and
  browser speech are unavailable the panel shows an error toast.

## Security Scan (Breaking Change + Secret + CVE)
- **What**: deterministic (no-LLM) scan of the loaded clone + optional PR
  patch + last 20 commit messages. Flags:
  - **SECRET** — GitHub/AWS/OpenRouter/Groq/NVIDIA/OpenAI/Anthropic/Google/
    Slack keys, private-key blocks, generic `api_key = "…"` assignments
    (placeholders excluded), committed `.env` files, and `process.env`
    usage in diffs. Details are redacted.
  - **BREAKING** — function signature changes in patches, removed functions,
    major version bumps in `package.json`, conventional-commit `BREAKING` /
    `!:` markers.
  - **CVE** — dependency pins below known-vulnerable ranges (curated map:
    requests, urllib3, lodash, axios, flask, django, jinja2, minimist, …).
  Every suggestion carries remediation guidance with a Nord Security /
  NordPass reference.
- **Use**: sidebar → **Tracking | Security** tabs → Security → **Run Security
  Scan**. Flags sort worst-severity first with colored badges.
- **API**: `POST /api/security/scan` `{repo_url?, pr_number?}` →
  `{flags, total_flags, summary, scanned}`.

## Reverse Prompt → Scaffold
- **What**: extends the Reverse Build Prompt with a CodeCrafters-style
  starter scaffold. The LLM sees only shallow context — README excerpt
  (4,000 chars), depth-1 file tree, graph layers + most-imported Row 1 nodes,
  and the first 100 lines of at most 2 entry files (never the full codebase)
  — and returns `{project_type, file_tree, files[{path, content, purpose}]}`
  with 6–12 boilerplate files (<50 lines each, TODOs included) and a
  Stage 1/2/3 README stub.
- **Use**: graph toolbar → **Scaffold** (or **Build Prompt** → ⚡ Scaffold) →
  browse the scaffold tree, preview files, **Download ZIP** (jszip, includes
  a `SCAFFOLD.md` manifest) or **Open in StackBlitz** (form-POST project).
- **API**: `POST /api/scaffold` → validated scaffold JSON (paths sanitized,
  contents capped at 80 lines/file).
- **Limits**: StackBlitz runs JS/TS templates best; Python scaffolds open as
  editable files.
