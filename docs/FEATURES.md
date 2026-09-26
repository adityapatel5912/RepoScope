# RepoScope — Features

Every feature, how to use it, and its limits. All screenshots live in
[screenshots/](screenshots/).

## Architecture Graph
- **What**: layered code graph (client / backend / storage / external /
  compute) built from AST (Python) and regex (JS/TS) parsing. Folders,
  files, and functions with per-layer pastel colors, legend, cluster bands,
  right-angle edges, minimap, and zoom controls.
- **Use**: load a repo (demo buttons or URL) and ask any chat question — the
  graph renders from the `context` SSE event. Toggle direction (TB/LR),
  re-layout, group/flatten, and focus from the toolbar.
- **Limits**: rendering is capped at 500 nodes (directories stay grouped);
  very wide trees zoom best via the tour / focus controls rather than Fit.

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
