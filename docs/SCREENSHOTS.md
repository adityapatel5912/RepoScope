# Screenshots

This is the index for the current v2.0 screenshots and the older feature
gallery. The app screenshots are captured at **1600×900** from the local-mode
build; the two OpenCode client captures keep their native panel size. The
sidebar and status bar show the live counts at capture time, so images from
different capture sessions may show slightly different counts.

## Current screenshots (v2.0 UI)

All files are in [`docs/screenshots/v2/`](screenshots/v2/).

**Chat:** there is no current v2 chat capture in this set. The README's
**Chat with citations** section uses the earlier
[`screenshots/chat.png`](screenshots/chat.png) and labels it as an older UI
generation; the current assistant still streams cited answers with a
**Next steps** section.

### Workspace

| File | Shows |
|---|---|
| [`readme-hero.png`](screenshots/v2/readme-hero.png) | Full local-mode workspace: grouped architecture graph, file tree, insights, agent context, chat, LOCAL MODE badge |
| [`readme-module-drawer.png`](screenshots/v2/readme-module-drawer.png) | Module drawer for `backend`: size, incoming/outgoing edges, complete file list, **Ask about this** |
| [`readme-side-panels.png`](screenshots/v2/readme-side-panels.png) | The left rail with Code Tour, What-If Impact, PR Bot, Quick Actions, and the assistant |

### Graph modes

| File | Shows |
|---|---|
| [`readme-graph-grouped.png`](screenshots/v2/readme-graph-grouped.png) | Large-repository grouped view: top-level modules as cards, rank labels, layer legend |
| [`readme-graph-clusters.png`](screenshots/v2/readme-graph-clusters.png) | Architecture cluster view grouped by layer (Client/UI, Backend/API, Storage/Data, External/Integrations, Compute/Workers) |
| [`readme-graph-flat.png`](screenshots/v2/readme-graph-flat.png) | Flat inspection mode: every file node rendered, useful for inventory rather than a first read |
| [`readme-graph-churn.png`](screenshots/v2/readme-graph-churn.png) | Churn heatmap toggle with the Stable/Churn/Hotspot legend |
| [`readme-graph-small.png`](screenshots/v2/readme-graph-small.png) | Small-repository full connectivity pyramid, loaded from `backend/tests/fixtures/real_small` |

### Side panels

| File | Shows |
|---|---|
| [`readme-tour.png`](screenshots/v2/readme-tour.png) | Code Tour form and the generated-tour entry point |
| [`readme-impact.png`](screenshots/v2/readme-impact.png) | What-If Impact form: target, depth slider, Analyze action |
| [`readme-prbot.png`](screenshots/v2/readme-prbot.png) | PR Bot form: PR number and Preview Comment |
| [`readme-byok.png`](screenshots/v2/readme-byok.png) | GitHub PAT and AI provider BYOK panels; both say “stored in memory only” |
| [`readme-tracking.png`](screenshots/v2/readme-tracking.png) | Tracking/Security tab strip with the Tracking empty state |
| [`readme-security.png`](screenshots/v2/readme-security.png) | Security tab with the Run Security Scan action and what it detects |
| [`readme-track.png`](screenshots/v2/readme-track.png) | Track mode active in the top bar, with the “what changed?” assistant prompt |
| [`readme-student.png`](screenshots/v2/readme-student.png) | Student Mode active, showing the Entry Points level and file explanations |
| [`readme-demo.png`](screenshots/v2/readme-demo.png) | Demo repository picker and the BYOK provider form |

### MCP

| File | Shows |
|---|---|
| [`opencode-mcp.png`](screenshots/v2/opencode-mcp.png) | OpenCode MCP servers panel with `reposcope` connected |
| [`opencode-mcp-status.png`](screenshots/v2/opencode-mcp-status.png) | Compact status list: `reposcope` connected alongside other local servers |

### Local folder preview

| File | Shows |
|---|---|
| [`readme-local-panel.png`](screenshots/v2/readme-local-panel.png) | **Open a local folder** panel: browser-preview warning, Choose a folder, file tree |

## Capture notes

- Server: `python -m cli.main run . --port 4100 --no-open`
- Browser: Chromium via Playwright, viewport **1600×900**, device scale 1
- Wait for the graph counts to settle before capturing.
- The module drawer is opened by clicking a module card.
- The graph-mode screenshots are produced with the toolbar buttons, in this
  order: grouped (default), architecture clusters, flat, churn. Load a small
  fixture for the full-pyramid image, then restore the root repository.
- The side panels are produced by scrolling the left rail to the relevant
  heading. They show the controls, not generated results, unless a real result
  is present.
- The native folder picker is **not** automated; the image shows the panel, not
  the OS dialog.
- Do not capture `.env`, tokens, personal paths, or unrelated browser tabs.
- The MCP screenshots are real client captures. `opencode-mcp.png` is the
  servers panel; `opencode-mcp-status.png` is the status list.

## Re-capture

```powershell
python -m cli.main run . --port 4100 --no-open
# In a Playwright session:
#   browser_resize 1600x900
#   browser_navigate http://127.0.0.1:4100
#   wait for the graph
#   browser_take_screenshot docs/screenshots/v2/readme-hero.png
```

For the module drawer, click a module card first. For the local panel, scroll
the left sidebar to **Open a local folder**. For the small graph, load
`backend/tests/fixtures/real_small` through the local API, then restore the
root repository.

## Feature gallery (older UI generation)

These images document features that still exist, but the layout and chrome are
from an earlier UI generation. Use them for feature context, not as a picture
of the current canvas.

| File | Feature |
|---|---|
| [`chat.png`](screenshots/chat.png) | Cited chat answer with **Next steps**; used in the README's chat section, labelled as earlier UI |
| [`graph.png`](screenshots/graph.png) | Earlier connectivity pyramid |
| [`hero.png`](screenshots/hero.png) | Earlier full workspace |
| [`impact.png`](screenshots/impact.png) | Impact analysis / blast radius |
| [`tour.png`](screenshots/tour.png) | Code tour stops |
| [`student.png`](screenshots/student.png) | Student Mode path |
| [`security.png`](screenshots/security.png) | Security scan |
| [`scaffold.png`](screenshots/scaffold.png) | Scaffold stages |
| [`tracking.png`](screenshots/tracking.png) | Repository tracking |
| [`prbot.png`](screenshots/prbot.png) | PR Bot comment |
| [`demo-repos.png`](screenshots/demo-repos.png) | Demo repository picker |

If a feature screenshot is replaced, update both the table and the README link
in the same commit.

## Screenshot rules

1. **Current UI only in current docs.** If an image shows an older layout,
   label it as a feature gallery image.
2. **1600×900** for README images; keep the aspect ratio.
3. **No secrets.** Check the terminal, env panels, and chat input.
4. **Counts are capture-time values.** Screenshots may show slightly different
   file/node counts because docs and assets changed after capture; captions must
   not present a different number as the current count. Re-capture only when the
   UI intentionally changes, not for every docs edit.
5. **The native picker is evidence of the panel, not the dialog.** Say so.
6. **Do not include build-session screenshots.** Product screenshots only.
7. **Generated art is not evidence.** Banners and diagrams go in
   `docs/assets/`, not in `docs/screenshots/v2/`.

## Brand and generated assets

These are not product screenshots. The logo is unchanged; the generated art
uses the same palette and is decorative.

| Asset | Location | Size / use |
|---|---|---|
| Logo and brand kit | [`frontend/public/brand/brand-kit.html`](../frontend/public/brand/brand-kit.html) | Existing mark, favicon, app icon, palette |
| Social card | [`frontend/public/brand/og-image.png`](../frontend/public/brand/og-image.png) | 2192×1152; Open Graph image |
| README hero | [`docs/assets/readme-hero.png`](assets/readme-hero.png) | 2048×1152; generated brand hero |
| One-index diagram | [`docs/assets/one-index-diagram.png`](assets/one-index-diagram.png) | 2048×1152; generated architecture diagram |

## Directories

| Directory | Purpose |
|---|---|
| `docs/screenshots/` | Feature gallery from earlier UI generations |
| `docs/screenshots/v2/` | Current README/QA screenshots |
| `docs/screenshots/demo/` | Demo-specific captures |
| `docs/assets/` | Generated banners, diagrams, and social cards |

`qa-report/` is generated output and is not a screenshot source.
