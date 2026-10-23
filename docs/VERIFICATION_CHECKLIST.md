# RepoScope v2.0 — manual verification checklist

**Status: OPEN.** This file is the persistent reminder for the checks that a
human still has to perform. Nothing below is marked complete until a person
actually does it and records the result.

- Release under test: backend/package **2.0.0**, extension **2.0.1**
- Checklist created: 2026-10-23
- Do not tick a box because the code "looks right". Run it.
- If a check fails, leave it unchecked and add a short note with the date,
  browser/editor version, and the observed error.

Already verified by automation (for context, not manual sign-off):

- `cd backend && python -m pytest -q` → 333 passed
- `cd frontend && npx tsc --noEmit` → clean
- `cd frontend && npm run build` → success
- local health endpoint → 200
- MCP stdio sweep → 8 tools, 5 resources, 3 read rounds, clean ping
- OpenCode MCP status → `✓ reposcope connected`

---

## 1. Local mode

Start from the repository root:

```powershell
python -m cli.main run . --port 4100 --no-open
```

- [ ] The process starts without a traceback and prints the repository path.
- [ ] `Invoke-RestMethod http://127.0.0.1:4100/api/health` returns 200.
- [ ] The banner reports the current file, node, and edge counts. Record the
      actual values; they change as files are added and may differ from the
      counts visible in older screenshots.
- [ ] The watcher reports **on**.
- [ ] Open <http://127.0.0.1:4100>; the graph renders without a console error.
- [ ] Edit a tracked source file, save it, and confirm the graph updates
      without a full page reload.
- [ ] Stop the server; confirm the port is released.
- [ ] Run the CLI without `--no-open` and confirm it opens the browser.
- [ ] Confirm no outbound GitHub request is required for local mode.

## 2. Graph and large-repository grouping

Load this repository at 1600x900.

- [ ] The graph opens in the grouped view rather than thousands of individual
      file nodes.
- [ ] Top-level modules appear as cards with file counts.
- [ ] The canvas shows the rank labels (`Rank 1 Backbone files`, etc.).
- [ ] Zoom in/out works; **Fit view** restores the whole graph.
- [ ] Clicking a module card opens the drawer.
- [ ] The drawer lists the module's files and the folder name.
- [ ] The drawer's **Ask about this** action focuses chat with the module
      context.
- [ ] Select an individual file node; its details and edges are readable.
- [ ] A rank label or module card is not clipped at the default viewport.
- [ ] Export PNG and SVG from the toolbar; both files open and contain the
      graph.
- [ ] Load a small repository (fewer than the grouping threshold) and confirm
      the full connectivity pyramid is still used.
- [ ] Reload the page; the loaded local repository is restored.
- [ ] Clear the loaded repository; the empty state returns.

## 3. Native folder picker (browser preview)

This cannot be automated: the OS dialog is outside the browser. Use **Chrome
or Edge** on `http://127.0.0.1:4100` (localhost is a secure context) or HTTPS.
Firefox does not implement `window.showDirectoryPicker`.

- [ ] In the left panel, **Open a local folder** is visible and says
      **Choose a folder**.
- [ ] Clicking it opens the native folder picker (not a file input, not a
      text box).
- [ ] Select a small folder containing at least one Python and one TypeScript
      file.
- [ ] A graph appears and the panel explicitly says it is a **browser
      preview** (no cross-file resolution, server never sees it).
- [ ] The preview's file count matches the selected folder (ignore
      `node_modules`, `.git`, and other ignored directories).
- [ ] Select **the same folder again**; the preview refreshes without a
      duplicate graph.
- [ ] Cancel the dialog; the panel returns to its previous state without an
      error toast.
- [ ] Deny folder permission; the UI shows a useful message rather than a
      blank canvas.
- [ ] Choose **Clear** / reload; the browser preview is gone and the main graph
      is unaffected.
- [ ] Confirm no network request uploaded the folder contents (DevTools →
      Network; the backend log has no local-load request).

## 4. PR Bot and GitHub Action

Use a repository and pull request you control. Never test by commenting on a
third-party PR.

- [ ] Open a pull request with at least one changed source file.
- [ ] In RepoScope, run the impact/PR preview and confirm it names the changed
      files, the risk score, the blast radius, and suggested tests.
- [ ] The generated markdown includes a Mermaid impact graph.
- [ ] Post the comment to your own PR; GitHub renders the Mermaid block.
- [ ] Re-run on the same PR; the bot updates or replaces its comment instead
      of duplicating it.
- [ ] Confirm the token used has only the minimum permissions needed
      (`pull-requests: write`, `contents: read`).
- [ ] Run the included GitHub Action on a PR in a fork; confirm it does not
      leak the token or post to the base repository unexpectedly.
- [ ] Comment failure path: remove the token and confirm the action fails with
      a clear message, not a silent success.

## 5. MCP server

### stdio

```powershell
cd backend
python -m mcp_server.server --root ..
```

- [ ] The server starts and responds to the MCP initialize/ping exchange.
- [ ] All **8 tools** are listed:
      `get_architecture_overview`, `calculate_blast_radius`,
      `get_dependency_lineage`, `explain_architectural_rule`,
      `get_repo_map`, `find_dependency_cycles`, `get_hotspots`,
      `find_unreachable_symbols`.
- [ ] All **5 resources** are listed:
      `reposcope://graph/summary`, `reposcope://hotspots`,
      `reposcope://repo-map`, `reposcope://dead-code`, `reposcope://cycles`.
- [ ] `get_architecture_overview` returns the repository name and counts.
- [ ] `calculate_blast_radius` on a known file returns its dependents.
- [ ] `get_repo_map` returns within a few seconds on a warm index.
- [ ] `find_dependency_cycles` returns a JSON list (empty is valid).
- [ ] Read each of the five resources three times; all complete.
- [ ] A clean ping after the reads still succeeds.

### OpenCode bridge

- [ ] `opencode mcp list` shows `✓ reposcope connected`.
- [ ] Tool calls from OpenCode work.
- [ ] Reading `reposcope://graph/summary` from OpenCode completes. **Known
      issue:** one bridge stalled for minutes and then reported
      `Received a response for an unknown message ID`; direct stdio reads
      worked. Record whether this reproduces on the current client version.
- [ ] If the bridge still stalls, attach the client version and the server log
      to the issue; do not claim the server is broken.

### Streamable HTTP

```powershell
cd backend
python -m mcp_server.server --root .. --http --port 8765
```

- [ ] The HTTP transport starts and accepts an MCP client connection.
- [ ] The same 8 tools and 5 resources are available.
- [ ] Stopping the server releases port 8765.
- [ ] SSE is not offered (the server deliberately supports stdio and
      Streamable HTTP only).

## 6. VS Code / Cursor / VSCodium extension

Build/install the current VSIX:

```powershell
code --install-extension extensions/vscode/reposcope-2.0.1.vsix
# or: cursor --install-extension extensions/vscode/reposcope-2.0.1.vsix
```

- [ ] The extension appears as version **2.0.1** in the Extensions view.
- [ ] The **RepoScope** Activity Bar icon is present.
- [ ] With the local backend on port 4100, the view loads a focus-first
      mini-graph for the open file (no blank webview).
- [ ] The status bar shows the blast-radius indicator.
- [ ] **View Callers** CodeLens appears above an exported symbol and opens the
      callers list.
- [ ] The CodeLens asks before enabling itself (the opt-in prompt appears
      once, not on every file).
- [ ] Right-click a file in Explorer → **Visualize in RepoScope Canvas**; the
      browser canvas opens on that file.
- [ ] `reposcope://open` URI handling opens the correct file.
- [ ] Change `reposcope.backendUrl` to a wrong port; the extension shows a
      clear connection error and recovers when the backend returns.
- [ ] Reload the editor window; the view reconnects.
- [ ] Test in Cursor and/or VSCodium, not only VS Code.
- [ ] Uninstall leaves no broken commands or status-bar items.

## 7. Open VSX

- [ ] The publisher namespace `adityapatel5912` has a verified email.
- [ ] `ovsx publish` succeeds with `OVSX_TOKEN` loaded from the gitignored
      `.env`.
- [ ] <https://open-vsx.org/extension/adityapatel5912/reposcope> resolves.
- [ ] The listing is visible in Open VSX search (not only by direct URL).
- [ ] The version shown is **2.0.1**.
- [ ] Install from Open VSX in VSCodium; the Activity Bar view loads.
- [ ] The README and icon render on the listing page.
- [ ] No token or `.env` content is present in the published package.

## 8. VS Code Marketplace (optional, blocked on PAT)

- [ ] An Azure DevOps PAT with **Marketplace (Manage)** scope exists.
- [ ] `vsce publish` succeeds.
- [ ] The listing is visible and installable from VS Code.
- [ ] The version matches the Open VSX release.
- [ ] If no PAT is available, leave every box unchecked and record the block;
      do not claim Marketplace availability.

## 9. Optional LLM-backed features

These require at least one provider key. Test with a throwaway key.

- [ ] Chat streams an answer with file/function citations.
- [ ] Chat handles a provider 429 by rotating keys or reporting a clear error.
- [ ] Impact analysis returns risk, direct/transitive files, and suggested
      tests.
- [ ] Code tour generates stops and pans the canvas.
- [ ] Voice tour plays audio or falls back to browser speech.
- [ ] Student Mode returns a three-level path, quizzes, and Good First Issues.
- [ ] Security scan redacts secrets and flags breaking changes.
- [ ] Scaffold downloads a ZIP and opens StackBlitz without the full codebase.
- [ ] Tracking lists commits/PRs/issues/releases for a repository.
- [ ] Reverse build prompt copies/saves a Markdown prompt.
- [ ] With no key configured, these features fail with a useful message and
      the graph/local mode still work.

## 10. Release and repository hygiene

- [ ] `git status` contains only intended docs, screenshots, and code changes.
- [ ] `.env` is not tracked; `OVSX_TOKEN` is not in any committed file.
- [ ] The README screenshot paths resolve.
- [ ] The docs index links resolve.
- [ ] The version in `pyproject.toml` and the extension `package.json` match
      the release notes.
- [ ] The final commit is local; **do not push** without explicit
      instruction.

---

## Sign-off

| Area | Verified by | Date | Result / notes |
|---|---|---|---|
| Local mode | | | |
| Graph and grouping | | | |
| Native folder picker | | | |
| PR Bot / Action | | | |
| MCP stdio | | | |
| MCP HTTP | | | |
| OpenCode bridge | | | |
| VS Code extension | | | |
| Open VSX | | | |
| Marketplace | | | |
| LLM features | | | |

When every applicable box is checked, update this file in the same commit as
the evidence (screenshots, logs, or links). Until then, the release is
**verified by automation only**, not manually signed off.
