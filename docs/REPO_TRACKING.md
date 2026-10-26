# Repository tracking

RepoScope checks a loaded GitHub repository on demand and reports what changed.
Local mode is not tracked: it has no GitHub remote and makes no outbound
request.

## Flow

1. Read `last_check` from `data/repo_state.json`.
2. Call the GitHub REST API for:
   - commits since `last_check`;
   - pull requests, sorted by update time;
   - issues since `last_check`;
   - releases.
3. Diff against the cached state.
4. Classify each change.
5. Update `last_check` and the known-item lists.
6. Summarize in plain English and cite the SHA/PR/issue number.

The UI action is **Track**; the API route is `GET /api/repo/check`.

## Authentication

- `GITHUB_TOKENS`: comma-separated tokens for rotation.
- `GITHUB_PAT`: a single token; takes precedence over the list.
- BYOK: `POST /api/byok/set` stores a token in memory for the session only.
  It is never written to disk.

Rate limits: 5,000 requests/hour authenticated, 60/hour anonymous. A missing
token is not an error, but the UI should say that the rate limit is lower.

## Change classification

`feat` · `fix` · `chore` · `docs` · `refactor` · `breaking` · `deps`

## Breaking-change detection

Flag a change when:

- the commit subject contains `BREAKING CHANGE` or `!:`.
- the PR has a breaking label.
- a major dependency version changes.
- a public API file changes.

Treat this as a heuristic. Say “flagged” rather than “confirmed breaking”
unless the evidence is explicit.

## Local state

`data/repo_state.json` holds:

```json
{
  "repo": null,
  "owner": null,
  "loaded_at": null,
  "last_check": null,
  "known_commits": [],
  "known_prs": [],
  "known_issues": [],
  "known_releases": []
}
```

The file is runtime state. Do not commit real tokens or private repository
contents into it.

## Failure modes

- **No token:** lower rate limit; the response should say so.
- **Rate limited:** rotate to the next token or ask the user to wait.
- **Repository moved/private:** report the HTTP status, not an empty change
  list.
- **Local mode:** tracking is disabled; do not fall back to GitHub.
