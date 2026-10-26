# Repo Tracking

## On-Demand Check
User says: "check the repo" / "what changed?"

Flow:
1. Read last_check from data/repo_state.json
2. Call GitHub API:
   GET /repos/{o}/{r}/commits?since={last_check}
   GET /repos/{o}/{r}/pulls?state=all&sort=updated
   GET /repos/{o}/{r}/issues?since={last_check}
   GET /repos/{o}/{r}/releases
3. Diff against cached state
4. Classify each change
5. Update last_check
6. Summarize in plain English

Rate limits: 5000/hr authenticated (GITHUB_PAT), 60/hr anon.

## Change Classification
feat | fix | chore | docs | refactor | breaking | deps

## Breaking Change Detection
Flag if:
- Commit message contains BREAKING CHANGE or !:
- PR labeled "breaking"
- Major dependency version bump
- Public API file changed

## Local State (data/repo_state.json)
{
  "repo": null,
  "loaded_at": null,
  "last_check": null,
  "known_commits": [],
  "known_prs": [],
  "known_issues": [],
  "known_releases": []
}
