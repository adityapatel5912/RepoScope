/**
 * extension.ts
 * RepoScope for VS Code, Cursor and VSCodium.
 *
 * Milestone 4. Five features, one idea: **the cost of a change should be
 * visible before you make it.**
 *
 *   1. An Activity Bar mini-graph that centres on the file you are in.
 *   2. A status-bar blast-radius indicator.
 *   3. A CodeLens on every exported symbol: "View Callers (8)".
 *   4. An explorer context menu: "Visualize in RepoScope Canvas".
 *   5. A `reposcope://open` URI handler, so a code-tour step in the web
 *      app opens the exact file and line HERE.
 *
 * The extension never parses code. It reads the RepoScope backend over
 * HTTP on localhost — the same index the web canvas draws — so the
 * numbers in the editor and the numbers a human sees are the same
 * numbers.
 */
import * as vscode from "vscode";
import { CallerCodeLensProvider, relativePath } from "./codeLens";
import { GraphClient } from "./graphClient";
import { MiniGraphView } from "./miniGraph";
import { parseOpenUri } from "./model";
import { StatusBarController } from "./statusBar";

/** The web app's URL, for the "open the canvas" command. */
let canvasUrl = "http://127.0.0.1:5173";

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const config = vscode.workspace.getConfiguration("reposcope");
  const backendUrl = config.get<string>("backendUrl") ?? "http://127.0.0.1:8000";
  canvasUrl = config.get<string>("canvasUrl") ?? canvasUrl;

  const client = new GraphClient({ baseUrl: backendUrl });

  // ── 1. The mini-graph ──────────────────────────────────────────────────
  const miniGraph = new MiniGraphView(async (nodeId) => {
    await focusInCanvas(nodeId);
  });
  context.subscriptions.push(
    miniGraph,
    vscode.window.registerWebviewViewProvider("reposcope.graph", miniGraph, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
  );

  // ── 2. The status bar ──────────────────────────────────────────────────
  let statusBar: StatusBarController | undefined;
  if (config.get<boolean>("statusBar") !== false) {
    statusBar = new StatusBarController(client);
    context.subscriptions.push(statusBar);
  }

  // ── 3. The CodeLens ────────────────────────────────────────────────────
  const codeLensProvider = new CallerCodeLensProvider(client);
  if (config.get<boolean>("codeLens") !== false) {
    context.subscriptions.push(
      vscode.languages.registerCodeLensProvider(
        [
          { scheme: "file", language: "python" },
          { scheme: "file", language: "typescript" },
          { scheme: "file", language: "typescriptreact" },
          { scheme: "file", language: "javascript" },
          { scheme: "file", language: "javascriptreact" },
          { scheme: "file", language: "go" },
          { scheme: "file", language: "rust" },
        ],
        codeLensProvider,
      ),
    );
  }
  context.subscriptions.push(codeLensProvider);

  // ── 5. The `reposcope://open` URI handler ──────────────────────────────
  // The web app emits this when a code-tour step is clicked. This is the
  // loop closing: map -> code -> agent -> map.
  context.subscriptions.push(
    vscode.window.registerUriHandler({
      handleUri(uri: vscode.Uri) {
        const target = parseOpenUri(uri.query);
        if (!target) return;
        void openFileAtLine(target.path, target.line).catch((err) => {
          // The link points at a file this workspace does not have — a
          // tour from another repository, or a link shared in chat. Say
          // so instead of failing silently.
          vscode.window.showInformationMessage(
            `RepoScope: ${target.path} is not in this workspace.`,
          );
          console.warn("RepoScope could not open the file:", err);
        });
      },
    }),
  );

  // ── The commands ───────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("reposcope.refresh", async () => {
      codeLensProvider.refresh();
      await refreshEverything(client, miniGraph, statusBar);
      vscode.window.showInformationMessage("RepoScope: index refreshed.");
    }),

    vscode.commands.registerCommand("reposcope.openCanvas", async () => {
      await vscode.env.openExternal(vscode.Uri.parse(canvasUrl));
    }),

    vscode.commands.registerCommand("reposcope.showGraph", async () => {
      // Bring the Activity Bar map to the front. The view is registered
      // as `reposcope.graph`, and VS Code gives every view a focus
      // command with that id.
      await vscode.commands.executeCommand("reposcope.graph.focus");
    }),

    vscode.commands.registerCommand(
      "reposcope.showCallers",
      async (file?: string, symbol?: string, count?: number) => {
        if (!file || !symbol) return;
        const result = await client.getCallers(file, symbol);
        if (!result.available || !result.found) {
          vscode.window.showInformationMessage(
            `RepoScope does not know the symbol "${symbol}" in ${file}.`,
          );
          return;
        }
        const items = result.callers.map((caller) => ({
          label: `${caller.label} — ${caller.file}:${caller.line}`,
          description: caller.file,
          detail: `line ${caller.line}`,
          caller,
        }));
        if (items.length === 0) {
          vscode.window.showInformationMessage(
            `Nothing calls "${symbol}" (${file}).`,
          );
          return;
        }
        const picked = await vscode.window.showQuickPick(items, {
          title: `Callers of ${symbol} (${result.count})`,
          placeHolder: "Jump to a caller",
        });
        if (picked) {
          await openFileAtLine(picked.caller.file, picked.caller.line || 1);
        }
      },
    ),

    vscode.commands.registerCommand(
      "reposcope.showBlastRadius",
      async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        const file = relativePath(editor.document);
        if (!file) return;
        const result = await client.getDependents(file);
        if (!result.available || !result.found) {
          vscode.window.showInformationMessage(
            "RepoScope has no index for this file. Run `reposcope run .`.",
          );
          return;
        }
        const detail = [
          `File: ${result.file}`,
          `Direct dependents: ${result.direct}`,
          `Transitive dependents: ${result.transitive}`,
          `Risk: ${result.risk} (${result.risk_score}/10)`,
        ].join("\n");
        await vscode.window.showInformationMessage(detail, { modal: false });
      },
    ),

    vscode.commands.registerCommand(
      "reposcope.focusNode",
      async (uri?: vscode.Uri) => {
        const target = uri ?? vscode.window.activeTextEditor?.document.uri;
        if (!target) return;
        const file = relativePath({ uri: target } as vscode.TextDocument);
        await focusInCanvas(file ? `file:${file}` : "");
      },
    ),
  );

  // ── The live wiring ────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(async (editor) => {
      if (!editor) {
        await statusBar?.update(null);
        return;
      }
      const file = relativePath(editor.document);
      await statusBar?.update(file);
      codeLensProvider.refresh();
      // The mini-graph centres on the file you are in.
      if (file) {
        try {
          const graph = await client.getGraph();
          miniGraph.show(graph, `file:${file}`);
        } catch {
          /* the backend is offline — the panel keeps whatever it had */
        }
      }
    }),
  );

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(() => {
      codeLensProvider.refresh();
    }),
  );

  // The first paint.
  let backendAlive = await refreshEverything(client, miniGraph, statusBar);

  // ── Keep trying ─────────────────────────────────────────────────────────
  //
  // A developer usually starts the editor and the backend at the same
  // time, and the backend needs a moment to build its index. The
  // extension used to decide once — "the backend is not there" — and then
  // say "offline" for the rest of the session, even after the backend
  // came up two seconds later. This retries until it is there.
  const retry = setInterval(async () => {
    if (backendAlive) return;
    const alive = await client.isAlive();
    if (!alive) return;
    backendAlive = true;
    codeLensProvider.refresh();
    await refreshEverything(client, miniGraph, statusBar);
  }, 10_000);
  context.subscriptions.push({ dispose: () => clearInterval(retry) });
}

/** Refresh the index, the status bar and the mini-graph. */
async function refreshEverything(
  client: GraphClient,
  miniGraph: MiniGraphView,
  statusBar: StatusBarController | undefined,
): Promise<boolean> {
  const alive = await client.isAlive();
  if (!alive) {
    statusBar?.offline();
    return false;
  }
  try {
    const graph = await client.getGraph();
    miniGraph.show(graph);
  } catch {
    /* ignore — the panel keeps its last contents */
  }
  const editor = vscode.window.activeTextEditor;
  if (editor) {
    await statusBar?.update(relativePath(editor.document));
  }
  return true;
}

/** Open a repo-relative file at a line. */
async function openFileAtLine(relative: string, line: number): Promise<void> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) return;
  const root = folders[0];
  const uri = vscode.Uri.file(`${root.uri.fsPath}/${relative.replace(/^\/+/, "")}`);
  const document = await vscode.workspace.openTextDocument(uri);
  const target = new vscode.Range(
    Math.max(0, line - 1),
    0,
    Math.max(0, line - 1),
    0,
  );
  await vscode.window.showTextDocument(document, { selection: target });
}

/** Open the web canvas, focused on a node. */
async function focusInCanvas(nodeId: string): Promise<void> {
  const url = nodeId ? `${canvasUrl}/?repo=&node=${encodeURIComponent(nodeId)}` : canvasUrl;
  await vscode.env.openExternal(vscode.Uri.parse(url));
}

export function deactivate(): void {
  /* nothing to clean up — everything is disposed through subscriptions */
}
