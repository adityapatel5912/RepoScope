# Runbooks

Short, repeatable procedures for the operations that actually come up.

---

## RB-01 — Start local mode

```bash
python -m cli.main run . --port 4100 --no-open
```

1. Confirm the banner prints the repository path, file/node/edge counts, and
   `watching: on`.
2. Check `http://127.0.0.1:4100/api/health` returns 200.
3. Open the canvas.
4. If the port is busy, use `--port 4101` and update the extension's
   `reposcope.backendUrl`/`reposcope.canvasUrl`.

Stop with `Ctrl+C`. Verify the port is released.

---

## RB-02 — Force a reindex

```bash
reposcope index .
```

Use when:

- the watcher missed a change;
- generated files were added or removed;
- the graph looks stale after a branch switch.

The command rewrites `.reposcope/graph.json` and the parse cache. The server
can keep running; reload the canvas after it finishes.

If the index is corrupted:

```powershell
Remove-Item -Recurse -Force .reposcope
reposcope index .
```

`.reposcope/` is disposable.

---

## RB-03 — Resume or clear a local session

A server restart resumes the last local session from
`.reposcope/local-session.json`.

To clear it:

```powershell
Remove-Item .reposcope/local-session.json -ErrorAction SilentlyContinue
Remove-Item data/repo_state.json -ErrorAction SilentlyContinue
```

Restart the server. QA mode (`REPOSCOPE_QA=1`) does not resume a persisted
session.

---

## RB-04 — Run the full stack

```bash
# Terminal 1
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

1. Confirm `http://127.0.0.1:8000/api/health` is 200.
2. Open `http://localhost:5173`.
3. Confirm Vite proxies `/api` without CORS errors.

---

## RB-05 — Start the MCP server

### stdio

```bash
cd backend
python -m mcp_server.server --root ..
```

The client owns stdin/stdout. Do not run it in a terminal that will print
other output into the same stream.

### Streamable HTTP

```bash
cd backend
python -m mcp_server.server --root .. --http --host 127.0.0.1 --port 8765
```

Keep it on localhost. There is no auth layer.

Smoke test: list 8 tools, 5 resources, call
`get_architecture_overview`, read `reposcope://graph/summary`, then ping.

---

## RB-06 — QA run

```bash
python scripts/qa.py
python scripts/qa.py --headed --grep J23
```

1. The harness boots on ports 8010/5183.
2. It writes `qa-report/index.html` and `qa-report/results.json`.
3. It writes screenshots to `docs/screenshots/v2/`.
4. A failed run leaves traces in `frontend/test-results/`.

Do not commit transient QA artifacts unless they are intended evidence.

---

## RB-07 — Publish the extension to Open VSX

```bash
cd extensions/vscode
npm ci
npm run compile
npm test
npx @vscode/vsce package --no-dependencies

# PowerShell (2.0.2 is an example; use the version you just bumped to)
$env:OVSX_TOKEN = "<token from the gitignored .env>"
npx ovsx publish reposcope-2.0.2.vsix -p "$env:OVSX_TOKEN"
```

1. Confirm the version in `package.json` is bumped. **2.0.1** remains MIT;
   do not republish it as source-available.
2. Confirm `LICENSE` is included and the listing describes the extension as
   source-available, not OSI Open Source.
3. The listing is searchable without namespace verification, but the
   `verified` badge stays off until the email is verified.
4. Check the direct listing:
   <https://open-vsx.org/extension/adityapatel5912/reposcope>
5. Never commit or log the token.

---

## RB-08 — Publish to the VS Code Marketplace

Requires an Azure DevOps PAT with **Marketplace (Manage)** scope. Extension
**2.0.1** is already MIT; bump the version before publishing the
source-available terms. The command uses **2.0.2** as an example.

```bash
cd extensions/vscode
npx @vscode/vsce publish 2.0.2 -p "$VSCE_PAT"
```

If no PAT exists, record the block and leave the Marketplace checklist
unchecked.

---

## RB-09 — Deploy backend + frontend

### Backend (Render)

1. Push the intended commit to the deploy branch.
2. Confirm the Render build succeeds.
3. Confirm `/api/health` returns 200 and reports version **2.0.0**.
4. Check `ALLOWED_ORIGINS` if the frontend origin changed.

### Frontend (Vercel)

1. Confirm the API rewrite destination matches the current Render hostname.
2. Deploy.
3. Open the production URL and check one API call.
4. Check a deep link (the SPA rewrite must return `index.html`).

---

## RB-10 — Roll back

- **Render:** redeploy the previous release, then re-check `/api/health` and
  its reported version.
- **Vercel:** promote the previous deployment.
- **Extension:** publish a higher patch version; do not delete a version
  unless it contains a secret.
- **Local:** reinstall the previous checkout and rebuild `.reposcope/`.

---

## RB-11 — Leaked credential

1. Revoke the key at the provider immediately.
2. Replace it in the environment/secret store; do not reuse it.
3. Check whether the key appears in git history:
   `git log -S "<prefix>" --all`.
4. If it was committed, rotate first, then decide whether history rewriting is
   necessary.
5. Never paste the key into an issue, screenshot, or chat.

---

## RB-12 — MCP resource read stalls

1. Reproduce with a direct stdio read; confirm it returns immediately.
2. Call a tool through the same client; confirm tools still work.
3. Capture the client name/version and the exact error.
4. Restart the client bridge.
5. Record the result in `VERIFICATION_CHECKLIST.md`; do not remove the
   resource from the server.
