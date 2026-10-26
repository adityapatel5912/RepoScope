# RepoScope v2.0 — remaining verification checklist

**Status: OPEN.** Only four manual checks remain: **3, 4, 8, and 9**.

- Release under test: backend/package **2.0.0**, extension **2.0.1**
- Checklist updated: 2026-10-25
- Do not tick a box because the code "looks right". Run it.
- If a check fails, leave it unchecked and add a short note with the date,
  environment, and the observed error.
- Do not push, deploy, or publish without explicit approval.

Agent-run evidence for the rest of the release is recorded in
[`QA_REPORT.md`](QA_REPORT.md#agent-run-evidence--2026-10-25). This checklist
is the manual gate, not the full test log.

---

## 3. Cursor / VSCodium extension

Install the current VSIX in both editors:

```powershell
cursor --install-extension extensions/vscode/reposcope-2.0.1.vsix
codium --install-extension extensions/vscode/reposcope-2.0.1.vsix
```

The default backend is `http://127.0.0.1:8000`; for local mode, point
`reposcope.backendUrl` at `http://127.0.0.1:4100`.

- [ ] The extension installs and appears as version **2.0.1**.
- [ ] The **RepoScope** Activity Bar view loads a focus-first mini-graph.
- [ ] The status bar and **View Callers** CodeLens show graph data.
- [ ] The Explorer menu reads **RepoScope: Focus this node in the canvas** and
      opens the canvas.
- [ ] `reposcope://open` opens the correct file and line.
- [ ] A wrong `reposcope.backendUrl` shows **RepoScope: offline**, then
      recovers after the URL is fixed and the window reloads.
- [ ] Uninstalling leaves no broken commands or status-bar items.

## 4. Open VSX namespace

The listing is already searchable. Agent evidence: version **2.0.1**, **288
downloads**, search API returns the listing, direct page HTTP 200.

- [ ] The publisher namespace `adityapatel5912` has a verified email.
- [ ] The Open VSX listing shows the **verified** badge.

## 8. Render deployment

Render currently runs the old build that reports `1.0.0`. Deploy only after
explicit approval.

- [ ] The approved deploy completes successfully.
- [ ] `https://<render-host>/api/health` returns **200**.
- [ ] The response reports version **2.0.0**, matching `pyproject.toml`.
- [ ] The frontend rewrite still points at the deployed Render hostname.

## 9. VS Code Marketplace

Blocked on an Azure DevOps Personal Access Token with **Marketplace (Manage)**
scope. Extension **2.0.1** is already MIT; publish a higher version for the
source-available terms.

- [ ] The PAT exists and is scoped correctly.
- [ ] The extension version is bumped above 2.0.1.
- [ ] `npx @vscode/vsce publish <new-version>` succeeds.
- [ ] The listing is visible and installable from VS Code.
- [ ] The Marketplace version matches the Open VSX release.
- [ ] If no PAT is available, leave the boxes unchecked and record the block;
      do not claim Marketplace availability.

---

## Sign-off

| Area | Verified by | Date | Result / notes |
|---|---|---|---|
| 3. Cursor / VSCodium | | | |
| 4. Open VSX namespace | | | |
| 8. Render deployment | | | |
| 9. VS Code Marketplace | | | |

When these four are checked, update this file in the same commit as the
evidence. Until then, the release is **agent-verified only**.
