# RepoScope — 3-Minute Demo Script

## Setup (before recording)
- Backend running: `cd backend && uvicorn main:app --port 8000`
- Frontend running: `cd frontend && npm run dev`
- Browser at http://localhost:5173, 1440×900, 100% zoom
- Demo repos ready: Verdict, StudyRot
- Chat panel cleared
- Graph zoomed to fit view

## Shot list

### 0:00–0:15 — Hook
**On screen:** RepoScope home with the demo repo selector.
**Say:** "Every developer has inherited a codebase and spent the first week
figuring out what's going on. Today that means five different tools that don't
talk to each other."

### 0:15–0:35 — Load a repo
**Action:** Click the "Verdict — Decision Lab" demo repo.
**On screen:** Progress stepper → graph renders as a pyramid.
**Say:** "RepoScope loads any GitHub repo in seconds and renders it as a
connectivity pyramid — the most-imported files at the top, documentation and
test data at the bottom."

### 0:35–1:00 — Read the graph
**Action:** Hover over `decision_model.py` in the top row. Click it.
**On screen:** Node details drawer slides in.
**Say:** "decision_model.py sits at the top because the whole app depends on
it. Its key functions — calculate_decision, calculate_solar — appear as child
nodes directly below it, with every import drawn as a directed edge."

### 1:00–1:30 — Ask a question
**Action:** Type "How does the decision model work?" in chat.
**On screen:** Answer streams in with citation chips.
**Say:** "Ask anything in plain English. Every answer cites the file, the
function, and the line that supports it — no hallucinated APIs."

### 1:30–2:00 — Impact analysis
**Action:** Type "calculate_decision" into What-If Impact. Click Analyze.
**On screen:** Blast radius highlights on the graph — target, direct,
transitive, unaffected.
**Say:** "Before you change anything, RepoScope shows you the blast radius —
every caller that depends on the function you're about to touch, with a risk
score and suggested tests."

### 2:00–2:20 — Code tours
**Action:** Type "decision_model" into Code Tour. Click Start.
**On screen:** Numbered step badges appear; the graph pans to each stop.
Next/Prev work.
**Say:** "For new team members, code tours walk through any module step by
step — the graph follows along."

### 2:20–2:40 — Tracking + BYOK
**Action:** Click the Track tab. Then show the BYOK panel in the sidebar.
**On screen:** Commit timeline appears. PAT input field.
**Say:** "Track commits, PRs, and issues on demand. Paste your GitHub PAT to
unlock private repos — it stays in memory, never on disk."

### 2:40–3:00 — CTA
**Action:** Click Export as PNG. Then show the README with links.
**On screen:** Exported graph image. README with demo, deck, and docs links.
**Say:** "Export the graph as PNG or SVG. Full source, live demo, and pitch
deck are in the README. Built entirely with IBM Bob. RepoScope — see your
repo, understand it, track it."

## Recording checklist
- [ ] No notifications visible
- [ ] No terminal output visible in frame
- [ ] Chat cleared between takes
- [ ] Repo reloaded fresh for each take
- [ ] Voiceover at 150 wpm (≈450 words total)
- [ ] Video exported at 1080p, under 200 MB
