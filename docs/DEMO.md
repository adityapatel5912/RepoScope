# RepoScope — three-minute demo

A current walkthrough. The graph, local mode, and MCP work without an LLM key;
the chat/impact beats need one.

## Before recording

- Local server: `python -m cli.main run . --port 4100 --no-open`
- Browser: Chrome or Edge at <http://127.0.0.1:4100>, **1600x900**, 100% zoom
- A second terminal for the MCP command
- A second window with the extension installed, or a recorded extension clip
- Close extra tabs and panels; clear the chat
- Confirm `http://127.0.0.1:4100/api/health` is 200

If the graph is still indexing, wait for the file/node counts to settle before
recording. Do not record a spinner.

---

## 0:00–0:15 — Hook

**On screen:** the loaded canvas.

**Say:** “Every developer inherits a codebase and spends the first week
learning its shape. Agents have the same problem, except they pay for the
whole repository every time they ask. RepoScope builds one graph and gives it
to both.”

---

## 0:15–0:40 — Local mode

**Action:** show the terminal banner, then the LOCAL MODE badge and the graph.

**Say:** “This is the RepoScope repository itself. No GitHub account, no token,
no upload. It parsed the repository into the node and edge counts shown in the
banner, and it is watching the folder. If I edit a file, the graph updates
without a reload.”

**On screen:** the file tree, the local mode badge, the counts.

---

## 0:40–1:10 — The grouped graph

**Action:** show the module cards. Click **backend**; the module drawer
opens. Close it. Click a file node.

**Say:** “A graph this size is not readable as a hairball, so the canvas groups
the top-level modules into cards. The backend is the largest module; the card
keeps the map readable and the drawer keeps every file reachable. This is the
same PageRank-ranked graph the rest of the product reads.”

**On screen:** module cards, rank labels, drawer with the file list.

---

## 1:10–1:40 — Ask the graph

**Action:** open chat and ask a repository-specific question. Use a question
whose answer is in the graph, for example: “What depends on `graph_store.py`,
and what breaks if I change it?”

**Say:** “The answer is cited. The model is not reading the whole repository;
it is reading the graph and the files the graph says matter. That is the
difference between a summary and an answer you can check.”

**Fallback if no LLM key:** use the impact panel on `graph_store.py` and show
the direct/transitive dependents and risk score.

---

## 1:40–2:10 — The same index over MCP

**Action:** switch to the terminal.

```bash
cd backend
python -m mcp_server.server --root ..
```

List the tools and call `get_architecture_overview`.

**Say:** “This is the same graph, not a second index. Eight tools and five
resources. An agent can ask for a blast radius, a dependency lineage, the
cycles, the hotspots, or a repo map that fits a token budget. The numbers match
the canvas because they come from the same store.”

**On screen:** the MCP server output/tool result.

---

## 2:10–2:40 — The editor

**Action:** switch to VS Code / Cursor. Show the RepoScope Activity Bar view
on an open file, the status-bar blast radius, and the **View Callers** CodeLens.

**Say:** “The editor is another client of the same index. The status bar shows
the cost of changing this file before I change it. The CodeLens jumps to the
callers. The miniature graph centres on the file I am in.”

---

## 2:40–3:00 — Close

**Say:** “One index, four surfaces: the canvas, the CLI, MCP, and the editor.
Local mode is private, the graph is deterministic, and the agent gets the map
instead of the repository. That is RepoScope.”

**On screen:** the canvas with the hero screenshot framing.

---

## Optional beats

- **PR Bot:** show a generated comment on a real PR. Do not post to a
  third-party repository.
- **Code tour:** play a short tour; the canvas pans to each stop.
- **Browser preview:** click **Open a local folder**, select a small folder,
  and point out the “browser preview” label. This is the only beat that needs
  a human in an OS dialog.
- **Student Mode:** show the three-level path and one quiz.

## What not to claim

- Do not say the browser preview has full cross-file resolution.
- Do not say the extension is in the VS Code Marketplace; it is on Open VSX.
- Do not say the Open VSX listing is searchable until the namespace email is
  verified.
- Do not say every language is parsed; the supported set is Python,
  TypeScript/TSX, JavaScript, Go, and Rust.
