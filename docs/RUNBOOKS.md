# Runbooks

## RB-001 — Repo Sync
Trigger: "check repo"
Steps: read last_check → GitHub API → classify → report → update state.

## RB-002 — Dependency Bump
Trigger: change to package.json / requirements.txt
Steps: extract old+new version → if major, flag breaking → summarize.

## RB-003 — Architecture Change
Trigger: new/deleted top-level directory
Steps: re-index with codebase-memory-mcp → diff graph → report delta.

## RB-004 — Incident Response (optional)
Trigger: injected alert
Steps: identify service → reverse calls for blast radius → recent commits
→ rank hypotheses → propose mitigation → postmortem.
