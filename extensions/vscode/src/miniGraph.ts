/**
 * miniGraph.ts
 * The Activity Bar mini-graph.
 *
 * A dark-mode canvas that mirrors the web app's architecture map, and
 * that CENTRES on the node for the file you are editing. The idea is
 * that the map is always there, in the corner of your eye, showing where
 * the file you are in sits in the shape of the system.
 *
 * The graph is rendered as inline SVG — no runtime dependency, no
 * canvas library, and the webview's CSP stays tight. The extension
 * fetches the graph and passes the DATA in; the webview never makes a
 * network request of its own.
 *
 * The rendering logic lives in `model.ts`, which has no `vscode` import
 * and is therefore unit-testable on its own.
 */
import * as vscode from "vscode";
import { Graph } from "./graphClient";
import { escapeXml, renderSvg } from "./model";

/** The HTML shell for the webview. */
export function webviewHtml(svg: string, summary: string): string {
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;" />
<style>
  body { margin: 0; background: #0f172a; color: #cbd5e1;
         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
  .header { padding: 8px 10px 4px; font-size: 11px; color: #64748b;
            font-family: monospace; }
  .header b { color: #38bdf8; font-weight: 600; }
  svg { display: block; width: 100%; height: auto; }
  circle { cursor: pointer; }
  circle:hover { stroke: #e2e8f0; stroke-width: 1; }
</style>
</head>
<body>
<div class="header"><b>RepoScope</b> · ${escapeXml(summary)}</div>
${svg}
<script>
  const vscode = acquireVsCodeApi();
  document.addEventListener('click', (event) => {
    const target = event.target;
    if (target && target.dataset && target.dataset.id) {
      vscode.postMessage({ type: 'select', id: target.dataset.id });
    }
  });
</script>
</body>
</html>`;
}

/** The webview panel that hosts the mini-graph. */
export class MiniGraphView {
  private panel: vscode.WebviewPanel | undefined;

  constructor(private readonly onSelect: (nodeId: string) => void) {}

  /** Show (or reveal) the panel, centred on the focused node. */
  show(graph: Graph, focusId?: string): void {
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        "reposcope.graph",
        "Architecture",
        vscode.ViewColumn.One,
        { enableScripts: true, retainContextWhenHidden: true },
      );
      this.panel.onDidDispose(() => { this.panel = undefined; });
      this.panel.webview.onDidReceiveMessage((message) => {
        if (message?.type === "select" && typeof message.id === "string") {
          this.onSelect(message.id);
        }
      });
    }
    this.panel.webview.html = webviewHtml(renderSvg(graph, focusId), graph.summary);
    this.panel.reveal(vscode.ViewColumn.One);
  }

  dispose(): void {
    this.panel?.dispose();
  }
}
