# RepoScope — Pitch Deck (text version)

> Editable source of `pitch-deck.pptx` · PDF: `pitch-deck.pdf`
> See your repo. Understand it. Track it.

---

## Slide 1 — Title
**RepoScope**
See your repo. Understand it. Track it.
Built with IBM Bob + Z Code · IBM Bob 2.0 Hackathon · lablab.ai · 2026

## Slide 2 — Problem
**Understanding a repo is broken.**
New hires, reviewers, and open-source contributors lose hours jumping between
five tools: an IDE to read, a browser to search, a chatbot to ask (which
hallucinates), a diff view to track, and a whiteboard to map architecture.
Nothing cites its sources, so nothing is trustworthy.

## Slide 3 — Insight
**Five tools become one.**
Every question about a codebase has the same shape: *what is this, where is
it, what touches it, what changed?* Answer all four from a single knowledge
graph and every answer comes with receipts — file, line, commit.

## Slide 4 — Solution
**RepoScope — the workspace for any GitHub repo.**
Paste a URL. A layered architecture graph renders in seconds; ask questions
in natural language with file/function/commit citations; track commits, PRs,
issues, and releases on demand. *(real UI screenshot on slide)*

## Slide 5 — Features
**What you get on day one.**
Architecture Graph · Conversational Q&A · Code Tours · What-If Impact
Analysis · Repo Tracking · Reverse Build Prompt · File Tree with downloads ·
PNG/SVG export · BYOK for private repos.

## Slide 6 — Architecture
**Built on a single knowledge graph.**
React UI (Vite + TS) → SSE → FastAPI (Python 3.11) → MCP servers →
LLM chain (OpenRouter → Groq → NVIDIA NIM, multi-key rotation) →
GitHub REST API → code graph store.

## Slide 7 — Why it wins
**Five tools vs. one workspace.**
IDE/search/chatbot/diff/whiteboard each do one thing, with no shared truth.
RepoScope does all five from one graph — with citations on every claim.

## Slide 8 — Built with AI
**Built with IBM Bob + Z Code.**
Most tasks ran through IBM Bob (8 guided sessions — architecture, backend,
frontend, tours, impact, tracking, docs). Z Code (GLM) paired on the complex
ones: graph layout diagnosis, hardening, regression, and this deck.
Real session screenshots on the slide.

## Slide 9 — Demo highlights
**What it looks like in action.**
01 Paste a URL — the graph renders in seconds.
02 Ask "How does auth work?" — get cited answers.
03 Change a function — see the blast radius.

## Slide 10 — CTA
**Try RepoScope.**
GitHub: github.com/adityapatel5912/RepoScope · Live demo · One-click demo
repos inside the app.
