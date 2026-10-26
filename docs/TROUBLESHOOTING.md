# Troubleshooting

Failures we have actually seen, and the fix that worked. If a symptom is not
here, check the backend log and the browser console before changing code.

---

## Local mode

### `reposcope` is not recognized

Install from the checkout:

```bash
pip install -e .
```

The PyPI name currently resolves to an unrelated older package. Do not use
`pip install reposcope` for this codebase.

### Port 4100 is already in use

```bash
python -m cli.main run . --port 4101 --no-open
```

Or stop the previous process:

```powershell
Get-NetTCPConnection -LocalPort 4100 | Select-Object OwningProcess
Stop-Process -Id <pid>
```

### The browser opens but the API is unreachable

- Check `http://127.0.0.1:4100/api/health`.
- Use `127.0.0.1`, not a stale LAN address.
- Check the terminal for a uvicorn bind error.
- The local server serves `frontend/dist`; run `cd frontend && npm run build`
  if the frontend assets are missing.

### The graph is stale after an edit

- Confirm the CLI banner says `watching: on`.
- Edits inside `.git`, `node_modules`, virtual environments, and build output
  are intentionally ignored.
- Force a rebuild: `reposcope index .`.
- Check `.reposcope/graph.json` mtime and the watcher log.
- A server restart resumes the persisted local session, except in QA mode.

### “Clear loaded repository” leaves the old graph

The state file may still point at the old local session. Stop the server,
delete `.reposcope/local-session.json` and `data/repo_state.json`, then restart.
Both files are disposable.

### Nothing leaves the machine, but a GitHub token is in `.env`

Local mode never uses it. The local router has no GitHub code path. If you see
an outbound request during local mode, treat it as a bug and capture the
request URL.

---

## Graph and canvas

### The graph shows modules instead of every file

That is the large-repository grouping. Click a module card to open its file
list. The backend still returns every file; the canvas collapses the view.
Use zoom/fit to inspect the cards.

### The graph is tiny after loading a large repository

Click **Fit view**, then zoom in. The default fit shows the whole map. The
grouped view is intentionally compact.

### Nodes overlap or edges cross awkwardly

- Use a 1600x900 or larger viewport.
- Fit the view after a data change.
- The layout is custom; report the repository size and a screenshot. Do not
  add a generic DAG layout dependency as a “fix”.

### The graph is empty after a load

- Confirm the repository has supported files.
- Check `/api/repo/graph` directly.
- Look for a parser exception in the backend log.
- Unsupported languages still appear as file nodes, but without symbols or
  call edges.

### PNG/SVG export fails

- Export after the canvas has finished laying out.
- Pop-up blockers can block the download.
- For SVG, confirm the browser supports the serialization path; try PNG first.

---

## Native folder picker / browser preview

### The button does nothing

`window.showDirectoryPicker` needs a **secure context**:

- `http://localhost` or `http://127.0.0.1` is allowed;
- a plain `http://192.168.x.x` address is not.

Use Chrome or Edge. Firefox does not implement the API.

### The picker opens but selecting a folder fails

- Grant the browser folder permission. A refusal now shows **Folder access was
  not granted. Choose the folder again and allow access when the browser
  asks.** rather than doing nothing.
- If the parser cannot load, the UI names WebAssembly or the security policy
  as the likely cause. Confirm the page's CSP includes `'wasm-unsafe-eval'`;
  do not add `'unsafe-eval'`.
- Do not select a drive root, a folder with millions of files, or a folder
  containing `node_modules` if you want a fast preview.
- Cancel the dialog and try again; a cancel keeps the previous preview and is
  not a backend error.
- An empty folder or one without Python, JavaScript, TypeScript, Go, or Rust
  files reports that no supported source files were found.

### The preview has fewer edges than the server graph

Expected. The browser preview has imports and symbols but no cross-file symbol
resolution. It is not the server index. The UI labels it as a browser preview.

### The preview uploaded nothing, but I want the server graph

The browser preview is local-only by design. Use `reposcope run .` and the
normal canvas for the full graph.

---

## MCP server

### The server starts from the wrong directory

Run it from `backend/`:

```bash
cd backend
python -m mcp_server.server --root ..
```

Or use the installed entry point from anywhere:

```bash
reposcope-mcp --root /absolute/path/to/repo
```

### The first call is slow

The first call builds a cold index. Later calls use `.reposcope/graph.json`
and are fast. On a large repository, allow the initial build to finish rather
than starting several servers at once.

### The client cannot read `reposcope://graph/summary`

Known client bridge issue: one OpenCode build stalled for several minutes and
then reported `Received a response for an unknown message ID`. Direct stdio
reads complete immediately and tool calls still work.

- Test the same resource with a direct stdio client.
- Update the client.
- Capture the client version and the server log.
- Do not “fix” the server by removing the resource; it is part of the API.

### Streamable HTTP port is in use

```bash
reposcope-mcp --root . --http --port 8766
```

The HTTP transport has no authentication. Keep it on localhost or behind an
authenticated proxy.

### Windows path problems

Quote paths with spaces. Use absolute paths in client JSON. Prefer forward
slashes or escaped backslashes in JSON:

```json
{ "args": ["--root", "C:/path/to/RepoScope"] }
```

---

## VS Code / Cursor / VSCodium extension

### The Activity Bar view is blank

- The backend must be running and reachable.
- The default `reposcope.backendUrl` is `http://127.0.0.1:8000`.
- For local mode, set it to `http://127.0.0.1:4100`.
- Check the Developer Tools console in the editor.

### The status bar says “RepoScope: offline”

That is intentional when the backend is unreachable: the extension does not
show zero dependents for a missing index. Start the backend or fix
`reposcope.backendUrl`.

### The CodeLens does not appear

- `reposcope.codeLens` must be `true`.
- The symbol must be exported and have call edges.
- The extension asks once before enabling the lens; accept the prompt.
- Reload the editor window after changing the setting.

### The canvas URL opens the wrong port

`reposcope.canvasUrl` defaults to `http://127.0.0.1:4100`. If you use the
full stack, set it to `http://127.0.0.1:5173`.

### The Explorer menu item has a different name

The current label is **RepoScope: Focus this node in the canvas**. Older docs
called it "Visualize in RepoScope Canvas"; the command ID is still
`reposcope.focusNode`.

### The VSIX version is old

Install the current file:

```bash
code --install-extension extensions/vscode/reposcope-2.0.1.vsix
```

Cursor and VSCodium use the same file. Reload the window after installing.

---

## Open VSX and Marketplace

### The extension is published but the verified badge is missing

The listing is now returned by Open VSX search. The publisher namespace is
still `verified:false`, so Open VSX does not show the verified badge and does
not guarantee stable search placement. Verify the namespace email, then
re-check the listing. Do not describe an unverified namespace as verified.

### `ovsx publish` returns 401/403

- `OVSX_TOKEN` is missing, expired, or belongs to another namespace.
- Load it from the gitignored `.env`; do not commit it.
- Confirm the publisher in `extensions/vscode/package.json` matches the token.

### VS Code Marketplace publish fails

It needs an Azure DevOps PAT with **Marketplace (Manage)** scope. Open VSX is
the supported path for Cursor/VSCodium until that PAT exists.

---

## LLM features

### `503` or “no provider configured”

Add at least one key to `.env` and restart the backend. The graph and local
mode still work without a key.

### `429` from every provider

- Add more comma-separated keys for rotation.
- Check the key limits.
- Try a smaller model.
- The chat surface should report the provider error rather than silently
  returning an empty answer.

### Chat answers without citations

- Confirm the graph loaded and the request includes repository context.
- Check the backend log for a context-assembly error.
- Do not treat uncited output as a verified answer.

### PR Bot does not comment

- The token needs `pull-requests: write` and `contents: read`.
- The PR must be in a repository the token can write to.
- Check the Action log; a missing token should fail loudly, not silently.
- Test on your own PR, never a third party's.

---

## Deployment

### Render health check times out

The free instance may be asleep. Warm it and retry. A timeout is not proof of
a healthy service. Check the Render logs for a startup exception.

### The frontend gets CORS errors

Add the origin to `ALLOWED_ORIGINS` on Render. The default allowlist covers
localhost and `*.vercel.app`.

### The frontend calls the wrong backend

Check the rewrite destination in `frontend/vercel.json` against the current
Render hostname. The committed hostname should be treated as configuration,
not as a guarantee.

### The backend starts but `/api/health` is 500

Check the Render logs for a missing environment variable or an import error.
The health endpoint reports provider key counts; a bad key shape can surface
at startup.

### `/api/health` reports version `1.0.0`

The code fix is in `backend/main.py`; the response should report **2.0.0**.
A long-running local process or the current Render deploy may still be serving
the old build. Restart the local server, or redeploy Render with approval. The
regression test compares the health response to `pyproject.toml`, so a version
bump that misses one of them fails the backend suite.

---

## Tests and QA

### Backend tests fail with a port in use

The QA harness uses 8010/5183 to avoid the development ports. Stop any old QA
process before starting a new run.

### Playwright cannot find Chromium

```bash
cd frontend
npx playwright install chromium
```

### The QA report is missing screenshots

The harness writes them under `docs/screenshots/v2/`. Check that the process
had write permission and that the run did not fail before the screenshot step.

### The extension tests fail after a compile

```bash
cd extensions/vscode
npm run compile
npm test
```

The tests use `node --test` and do not need the editor host.
