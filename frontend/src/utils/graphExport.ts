/**
 * graphExport.ts
 * PNG + SVG export for the graph canvas (html-to-image).
 * Toolbar, minimap, controls and legend are excluded from the capture by
 * class name; the canvas background color is preserved via the html2canvas-
 * style `backgroundColor` option.
 */
import { toPng, toSvg } from "html-to-image";

const EXCLUDED_CLASSES = [
  "react-flow__controls",
  "react-flow__minimap",
  "graph-toolbar",
  "graph-legend",
  "graph-title",
  "graph-impact-legend",
  "node-drawer",
];

function download(dataUrl: string, filename: string) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function exportFilename(repo: string | undefined, ext: string): string {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const slug = (repo ?? "graph").replace(/[^A-Za-z0-9-]+/g, "-").replace(/^-+|-+$/g, "") || "graph";
  return `reposcope-${slug}-${stamp}.${ext}`;
}

function filterNode(node: HTMLElement): boolean {
  const cls = node.className;
  if (typeof cls !== "string") return true;
  return !EXCLUDED_CLASSES.some((c) => cls.includes(c));
}

/** Common capture options. */
function options(backgroundColor: string) {
  return {
    filter: filterNode as (node: HTMLElement) => boolean,
    backgroundColor,
    pixelRatio: 2,
    // Remote Google Fonts can't be inlined cross-origin (SecurityError spam)
    skipFonts: true,
  };
}

/** Export the graph canvas as a high-res PNG (pixelRatio 2). */
export async function exportGraphPng(
  element: HTMLElement,
  repo?: string,
  backgroundColor = "#ECE9F5",
): Promise<void> {
  const dataUrl = await toPng(element, options(backgroundColor));
  download(dataUrl, exportFilename(repo, "png"));
}

/** Export the graph canvas as an SVG image. */
export async function exportGraphSvg(
  element: HTMLElement,
  repo?: string,
  backgroundColor = "#ECE9F5",
): Promise<void> {
  const dataUrl = await toSvg(element, options(backgroundColor));
  download(dataUrl, exportFilename(repo, "svg"));
}
