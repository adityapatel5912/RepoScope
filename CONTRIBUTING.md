# Contributing to RepoScope

## Setup
1. Fork the repo.
2. Clone your fork.
3. Copy `.env.example` to `.env` and fill in your keys.
4. `cd backend && pip install -r requirements.txt`
5. `cd frontend && npm install`

## Development
- **Backend**: `cd backend && uvicorn main:app --reload --port 8000`
- **Frontend**: `cd frontend && npm run dev`

## Env Vars Reference

| Variable             | Purpose                           |
|----------------------|-----------------------------------|
| `OPENROUTER_API_KEY` | Primary LLM (free models available) |
| `Base_URL_OPENROUTER`| OpenRouter base URL               |
| `Models_OPENROUTER`  | Comma-separated model list        |
| `GROQ_API_KEY`       | Secondary LLM                     |
| `Base_URL_GROQ`      | Groq base URL                     |
| `Models_GROQ`        | Comma-separated model list        |
| `NVIDIA_API_KEY`     | Tertiary LLM fallback             |
| `Base_URL_NVIDIA`    | NVIDIA NIM base URL               |
| `Models_NVIDIA`      | Comma-separated model list        |
| `GITHUB_PAT`         | GitHub REST API + private repos   |

## Commit Convention
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — maintenance / tooling
- `refactor:` — code change without feature/fix

## Pull Requests
- One feature per PR.
- Update `docs/` docs if the API contract changes.
- Run the smoke test before submitting: `curl http://localhost:8000/api/health`

## Reporting a Bug
Open a GitHub issue with: what you did, what you expected, what happened,
and the backend log line from `backend/logs/app.log` (include the request id
in brackets). Never paste API keys.

## Proposing a Feature
Open an issue tagged `proposal` — describe the user problem first, then the
proposed behavior. Features that fit the knowledge-graph model get priority.

## Code of Conduct
Be excellent to each other — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
