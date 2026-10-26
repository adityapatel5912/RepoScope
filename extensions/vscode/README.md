# RepoScope for VS Code, Cursor and VSCodium

The code graph, in your editor.

RepoScope parses your repository with Tree-sitter and serves the result as
a dependency graph. The web app draws that graph; **this extension puts it
where you work** — the cost of a change, visible before you make it.

> The extension never parses code. It reads the RepoScope backend over
> HTTP on localhost — the same index the web canvas draws — so the numbers
> in your editor and the numbers a human sees are the same numbers.

---

## Install

### From the .vsix (the fallback)

```bash
code --install-extension reposcope-2.0.0.vsix
```

Cursor and VSCodium read the same file:

```bash
cursor --install-extension reposcope-2.0.0.vsix
```

### From Open VSX (recommended)

Cursor and VSCodium read Open VSX. The VS Code Marketplace requires a
publisher account, so Open VSX is published first.

### Build it yourself

```bash
cd extensions/vscode
npm install
npm run compile
npm test          # 11 unit tests, no extension host needed
npx @vscode/vsce package --no-dependencies
```

---

## What you get

### 1. A blast-radius indicator in the status bar

```
RepoScope: ⚠️ 12 dependents | Risk: Med
```

Click it for the breakdown — direct dependents, transitive dependents, and
the risk score. The point is that the cost of a change is visible **before**
you make it: opening a file is a decision, and this tells you what the
decision costs.

### 2. "View Callers (8)" above every exported symbol

The count comes from the graph's own call edges — the same edges the MCP
tool reads. An agent asking "what calls this?" and you looking at the
lens get the same number.

Click it to jump to a caller.

### 3. An architecture mini-graph in the Activity Bar

A dark-mode map of the repository that centres on the file you are
editing. The file you are in is haloed; the rest of the system is the
context.

Click a node to open it in the RepoScope canvas.

### 4. "Visualize in RepoScope Canvas" in the explorer menu

Right-click any file in the Explorer.

### 5. `reposcope://open` — the web app can open a file here

When you click a code-tour step in the web app, it emits a
`reposcope://open?path=…&line=…` link. This extension handles it and
opens the exact file and line. That is the loop closing: **map → code →
agent → map.**

---

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `reposcope.backendUrl` | `http://127.0.0.1:8000` | The RepoScope backend. |
| `reposcope.canvasUrl` | `http://127.0.0.1:5173` | The web app. |
| `reposcope.statusBar` | `true` | Show the blast-radius indicator. |
| `reposcope.codeLens` | `true` | Show the caller count. |

Start a backend for your repository:

```bash
cd /path/to/your/repo
reposcope run .          # serves on :4100
```

…then point the extension at it:

```json
{ "reposcope.backendUrl": "http://127.0.0.1:4100" }
```

---

## Why the numbers are trustworthy

Every number this extension shows comes from the graph — never from a
regex, never from a guess:

| Shown | Comes from |
|---|---|
| The caller count | The graph's `calls` edges |
| The blast radius | A reverse-BFS over the dependency edges |
| The risk level | The same score the web app's risk panel shows |
| The mini-graph | The same PageRank-ranked layout the canvas draws |

When the backend is unreachable, the extension says **"RepoScope: offline"**
rather than showing zero. A missing index is not an index with no
dependents.

---

## License

MIT
