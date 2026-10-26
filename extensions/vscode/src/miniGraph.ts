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
import { escapeXml, renderLegend, renderSvg } from "./model";

/** The HTML shell for the webview. */
export function webviewHtml(svg: string, summary: string, legend = "", focus?: string): string {
  const focusLine = focus
    ? `<div class="focus" title="${escapeXml(focus)}">${escapeXml(focus)}</div>`
    : "";
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;" />
<style>
  :root { color-scheme: dark; }
  body {
    margin: 0;
    background: #0b1220;
    color: #cbd5e1;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px;
  }
  .header {
    display: flex; align-items: baseline; gap: 6px;
    padding: 10px 12px 6px;
    border-bottom: 1px solid #1e293b;
  }
  .header b { color: #38bdf8; font-weight: 600; letter-spacing: 0.01em; }
  .header .summary {
    margin-left: auto; color: #64748b; font-size: 10px; font-family: monospace;
  }
  .focus {
    padding: 6px 12px 8px;
    color: #e2e8f0;
    font-family: monospace; font-size: 11px;
    border-bottom: 1px solid #1e293b;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .focus::before { content: "● "; color: #38bdf8; }
  .map { padding: 6px 0 2px; }
  svg { display: block; width: 100%; height: auto; }
  .legend {
    display: flex; flex-wrap: wrap; gap: 4px 10px;
    padding: 8px 12px 12px;
    border-top: 1px solid #1e293b;
    color: #64748b; font-size: 10px;
  }
  .legend-item { display: inline-flex; align-items: center; gap: 4px; }
  .legend-dot {
    width: 7px; height: 7px; border-radius: 50%; display: inline-block;
  }
  circle { cursor: pointer; }
  circle:hover { stroke: #e2e8f0; stroke-width: 1.5; }
  .empty { padding: 18px 12px; color: #64748b; font-family: monospace; font-size: 11px; }
</style>
</head>
<body>
<div class="header"><b>RepoScope</b><span class="summary">${escapeXml(summary)}</span></div>
${focusLine}
<div class="map">${svg}</div>
${legend}
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

/**
 * The Activity Bar mini-graph.
 *
 * It lives in the Activity Bar view the package declares
 * (`reposcope.graph`) — NOT in an editor tab. An earlier version opened a
 * webview PANEL and revealed it on every file switch, which took the
 * editor away from the developer mid-keystroke and left the status bar
 * claiming "no file" while they were looking at one. A side panel that
 * updates itself cannot do that.
 */
export class MiniGraphView implements vscode.WebviewViewProvider, vscode.Disposable {
  private view: vscode.WebviewView | undefined;
  private graph: Graph | undefined;
  private focusId: string | undefined;

  constructor(private readonly onSelect: (nodeId: string) => void) {}

  /** The Activity Bar asks for the view when the user opens the container. */
  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((message) => {
      if (message?.type === "select" && typeof message.id === "string") {
        this.onSelect(message.id);
      }
    });
    webviewView.onDidDispose(() => { this.view = undefined; });
    this.render();
  }

  /** Show (or refresh) the graph, centred on the focused node. */
  show(graph: Graph, focusId?: string): void {
    this.graph = graph;
    this.focusId = focusId;
    this.render();
  }

  /** Paint the latest graph into the view, if the view exists yet. */
  private render(): void {
    if (!this.view || !this.graph) return;
    const focusLabel = this.focusId
      ? this.focusId.replace(/^file:/, "")
      : undefined;
    this.view.webview.html = webviewHtml(
      renderSvg(this.graph, this.focusId),
      this.graph.summary,
      renderLegend(this.graph),
      focusLabel,
    );
  }

  dispose(): void {
    this.view = undefined;
  }
}
