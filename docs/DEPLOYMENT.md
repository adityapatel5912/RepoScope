# Deployment

RepoScope has three deployable pieces:

1. the FastAPI backend (Render);
2. the static frontend (Vercel);
3. the VS Code extension (Open VSX, later the VS Code Marketplace).

Local mode is not deployed. It runs on the developer's machine and serves the
built frontend from the Python process.

---

## 1. Backend — Render

[`render.yaml`](../render.yaml) defines the service:

```yaml
services:
  - type: web
    name: reposcope-api
    runtime: python
    plan: free
    region: oregon
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
```

Set these environment variables in the Render dashboard (they are marked
`sync: false` so they are not committed):

- `OPENROUTER_API_KEYS`
- `GROQ_API_KEYS`
- `NVIDIA_API_KEYS`
- `GITHUB_TOKENS` (optional)
- `ALLOWED_ORIGINS` (for example, the Vercel production and preview origins)
- `Models_OPENROUTER`, `Models_GROQ`, `Models_NVIDIA` (optional overrides)

Do **not** commit a `.env` file or a key. The health check must return 200 at
`https://<render-host>/api/health` before the frontend is pointed at it.

### Verify the deploy

```bash
curl -i https://<render-host>/api/health
curl -i https://<render-host>/api/repo/demos
```

If the free instance is asleep, the first request can take longer than the
health check timeout. Warm it, then re-check. A timed-out health check is not
proof that the service is healthy.

### Notes

- `render.yaml` still contains an old `CODEBASE_MEMORY_PATH` value from an
  earlier index backend. The current graph does not need it. Remove it from
  the dashboard if it is present; it has no effect on the Tree-sitter index.
- The backend CORS allowlist is `localhost:5173`, `localhost:4173`, and any
  `https://*.vercel.app` origin. Add a custom origin to `ALLOWED_ORIGINS` if
  needed.

---

## 2. Frontend — Vercel

[`frontend/vercel.json`](../frontend/vercel.json) defines the build and the
API rewrite:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://<backend-host>/api/:path*" }
  ]
}
```

Before deploying, confirm that the rewrite destination is the current Render
hostname. The committed value is `https://reposope.onrender.com`; confirm it
against the Render dashboard rather than assuming the service slug.

Deploy:

```bash
cd frontend
npm ci
npm run build
# Vercel: connect the repository and use frontend/ as the root,
# or run `vercel --prod` from frontend/.
```

The frontend is a static SPA. The catch-all rewrite to `/index.html` is
required for deep links.

### Local production preview

```bash
cd frontend
npm run build
npm run preview
```

The backend must be running on the URL the client expects. For local mode,
serve the built frontend from the CLI instead (`reposcope run .`).

---

## 3. Extension — Open VSX

The extension is version **2.0.1**, publisher `adityapatel5912`.

```bash
cd extensions/vscode
npm ci
npm run compile
npx @vscode/vsce package --no-dependencies

export OVSX_TOKEN=...        # PowerShell: $env:OVSX_TOKEN = "..."
npx ovsx publish reposcope-2.0.1.vsix -p "$OVSX_TOKEN"
```

The token lives in the gitignored `.env`; never commit it. Do not paste it into
a log or an issue.

### Listing visibility

The VSIX is published, but the listing stays hidden from Open VSX search until
the publisher namespace email is verified. Direct URL:

<https://open-vsx.org/extension/adityapatel5912/reposcope>

Checklist:

- [ ] Namespace email verified.
- [ ] `ovsx publish` succeeds.
- [ ] Direct URL resolves.
- [ ] The listing appears in search.
- [ ] Version 2.0.1 is shown.
- [ ] Install from VSCodium works.

These are manual checks; see
[`VERIFICATION_CHECKLIST.md`](VERIFICATION_CHECKLIST.md).

---

## 4. Extension — VS Code Marketplace

Blocked on an Azure DevOps Personal Access Token with **Marketplace
(Manage)** scope.

```bash
cd extensions/vscode
npx @vscode/vsce publish -p "$VSCE_PAT"
```

Do not claim Marketplace availability until the listing is live and installable.
The Open VSX release is the supported Cursor/VSCodium path.

---

## 5. MCP server

### Local stdio

```bash
cd backend
python -m mcp_server.server --root /absolute/path/to/repo
```

The client launches the process; no port is opened.

### Streamable HTTP

```bash
cd backend
python -m mcp_server.server --root /absolute/path/to/repo --http --host 127.0.0.1 --port 8765
```

There is no authentication layer in the MCP HTTP transport. Keep it on
localhost or behind an authenticated proxy. Do not expose it to the public
internet as-is.

The MCP server is intentionally not deployed as part of the Render web
service. It reads a repository on disk, which a stateless web dyno does not
have.

---

## 6. Environment matrix

| Variable | Backend | Local CLI | Extension | Notes |
|---|---|---|---|---|
| `OPENROUTER_API_KEYS` | Yes | Optional | No | Primary LLM |
| `GROQ_API_KEYS` | Yes | Optional | No | Secondary |
| `NVIDIA_API_KEYS` | Optional | Optional | No | Fallback |
| `GITHUB_TOKENS` | Optional | No | No | Rate limits |
| `ALLOWED_ORIGINS` | Optional | No | No | Extra CORS origins |
| `OVSX_TOKEN` | No | No | Publish | Never commit |
| `VSCE_PAT` | No | No | Publish | Azure DevOps PAT |

---

## 7. Rollback

- **Backend:** redeploy the previous Render release; then check
  `/api/health`.
- **Frontend:** promote the previous Vercel deployment.
- **Extension:** publish a higher patch version; Open VSX does not support
  deleting a published version. Unpublish only if the package contains a
  secret or is unusable.
- **Local mode:** reinstall the previous wheel/checkout. `.reposcope/` is
  disposable and can be rebuilt.

---

## 8. Release checklist

- [ ] Backend tests pass (`333 passed` baseline).
- [ ] `npx tsc --noEmit` is clean.
- [ ] `npm run build` succeeds.
- [ ] Extension tests pass (20).
- [ ] Version is bumped in `pyproject.toml` and/or
      `extensions/vscode/package.json`.
- [ ] Screenshots paths resolve.
- [ ] `.env` is untracked.
- [ ] Health check is 200 on the deployed backend.
- [ ] The frontend rewrite points at the right backend host.
- [ ] The Open VSX namespace email is verified before claiming search
      visibility.
- [ ] The commit is local; push only with explicit approval.
