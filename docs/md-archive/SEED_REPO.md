# Seed Repository

## Local Demo Repo
A small demo repo is included at `demo-repo/` with three modules:
- auth.py     — login, tokens
- checkout.py — cart → order
- payment.py  — charge, retry

Load flow (for any repo):
1. Shallow clone (--depth=50) to /tmp/reposcope/<hash>
2. Index with codebase-memory-mcp
3. Fetch GitHub metadata
4. Merge into graph store
5. Return graph to UI

Demo script:
Act 1 — Understanding: paste URL → ask "what does this repo do?"
Act 2 — Tracking: click "Check Repo" → see new commits/PRs
Act 3 — Incident (optional): inject alert → blast radius → postmortem
