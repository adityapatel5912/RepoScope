# Contributing to RepoScope

Thanks for helping. RepoScope is a code graph with four front-ends — the
canvas, the CLI, the MCP server, and the editor extension — all reading the
same index. Changes should preserve that property.

## Setup

Requires **Python 3.11+**, **Node.js 20+** (24 is used in this repository),
and npm.

```bash
git clone https://github.com/adityapatel5912/RepoScope.git
cd RepoScope

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env

cd frontend
npm install
```

At least one LLM key is needed for chat, tours, Student Mode, security
narratives, scaffolds, and the PR Bot. The graph, local mode, CLI, and MCP
server work without any key.

## Run it

```bash
# Local mode (recommended for graph work)
python -m cli.main run . --port 4100 --no-open

# API only
cd backend
uvicorn main:app --reload --port 8000

# Frontend dev server
cd frontend
npm run dev
```

Open <http://127.0.0.1:4100> for local mode or
<http://localhost:5173> for the full Vite app.

## Tests and checks

```bash
# Backend
python -m pytest -q

# MCP server
python -m pytest backend/tests/test_mcp_server.py -q

# Frontend type-check and production build
cd frontend
npx tsc --noEmit
npm run build

# Extension unit tests
cd extensions/vscode
npm install
npm test
npx @vscode/vsce package --no-dependencies

# Browser QA harness (needs Playwright)
python scripts/qa.py --headed --grep J00
```

The exact numbers from the last verified run are in
[`docs/QA_REPORT.md`](docs/QA_REPORT.md) and
[`docs/VERIFICATION_CHECKLIST.md`](docs/VERIFICATION_CHECKLIST.md). Manual
checks stay unchecked until a human confirms them; do not mark them passed
because CI is green.

## Environment variables

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEYS` | Primary LLM; comma-separate for rotation |
| `GROQ_API_KEYS` | Secondary LLM |
| `NVIDIA_API_KEYS` | Tertiary LLM fallback |
| `Models_OPENROUTER` / `Models_GROQ` / `Models_NVIDIA` | Optional model overrides |
| `Base_URL_OPENROUTER` / `Base_URL_GROQ` / `Base_URL_NVIDIA` | Optional OpenAI-compatible endpoints |
| `GITHUB_TOKENS` | GitHub API tokens; comma-separate |
| `GITHUB_PAT` | Legacy single GitHub token |
| `OVSX_TOKEN` | Open VSX publish token; keep it in the gitignored `.env` |

Never commit `.env`, tokens, private repository contents, or generated
screenshots that contain either.

## Commit convention

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — maintenance or tooling
- `refactor:` — code change without a feature or fix
- `test:` — test-only change

Keep the subject under ~72 characters. Explain the user-visible effect in the
body when the change is not obvious.

## Pull requests

- One coherent change per PR.
- Update the relevant docs when an API contract, default, or limitation
  changes. The docs index is [`docs/README.md`](docs/README.md).
- Add or update a test for a bug fix. Parser changes should keep the golden
  graph test green.
- Run the backend tests, the frontend type-check, and the extension tests.
- Do not include real tokens, `.env` contents, or private repository text in
  logs or screenshots.
- If a manual step is still required (native dialog, marketplace visibility,
  live PR comment), leave it unchecked in
  [`docs/VERIFICATION_CHECKLIST.md`](docs/VERIFICATION_CHECKLIST.md).
- Do not push release tags or publish packages without the maintainer's
  approval.

## Reporting a bug

Open a GitHub issue with:

- what you did;
- what you expected;
- what happened;
- the relevant backend log line from `backend/logs/app.log` (include the
  request id in brackets);
- the RepoScope version and whether you were in local mode.

Never paste API keys or private source code. If the report needs private
material, say so and the maintainer will arrange a private channel.

## Proposing a feature

Open an issue tagged `proposal`. Describe the user problem first, then the
proposed behaviour, then the smallest version that would be useful. Features
that fit the one-index model — the canvas, CLI, MCP server, and extension all
reading the same graph — get priority.

## Code of Conduct

Be excellent to each other. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
