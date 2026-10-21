/**
 * model.ts
 * The extension's PURE logic.
 *
 * No `vscode` import. That is deliberate: everything that can be
 * decided without an editor host lives here, so it can be unit-tested
 * with a plain `node --test` — no extension host, no mocking, no
 * "it works on my machine".
 *
 * The colour rules here are a coarse copy of the web app's taxonomy,
 * used for PICTURE ONLY. The authoritative classification is the
 * backend's; the extension's job is to make the map readable, not to
 * re-implement a taxonomy it could get wrong.
 */
import type { Graph, GraphNode } from "./graphClient";

/** The layers, with the same colours as the web app. */
export const LAYER_COLOURS: Record<string, string> = {
  client: "#3b82f6",
  backend: "#f59e0b",
  storage: "#10b981",
  external: "#ef4444",
  compute: "#8b5cf6",
};

export const DEFAULT_COLOUR = "#94a3b8";

/** Decide which layer a file belongs to. */
export function layerOf(node: GraphNode): string {
  const path = String(node.label || "").toLowerCase();
  if (/\.(tsx?|jsx?|vue|svelte|css|scss|html)$/.test(path)) return "client";
  if (/\.(md|rst|txt|pdf|docx?|xlsx?|csv|json|ya?ml|toml|lock)$/.test(path)) {
    return "storage";
  }
  if (/\.(go|rs)$/.test(path)) return "compute";
  if (/(^|\/)(tests?|specs?|__tests__)\//.test(path)) return "external";
  return "backend";
}

/**
 * Lay the file nodes out in bands, most central first.
 *
 * The bands use the graph's own PageRank, which is the same ranking the
 * web app's pyramid uses — so the two pictures match.
 */
export function layoutBands(graph: Graph, perBand = 18): Map<string, number> {
  const files = graph.nodes.filter((n) => n.type === "file");
  const ranked = [...files].sort(
    (a, b) => (b.pagerank ?? 0) - (a.pagerank ?? 0) || a.id.localeCompare(b.id),
  );
  const bands = new Map<string, number>();
  ranked.forEach((node, index) => {
    bands.set(node.id, Math.floor(index / perBand));
  });
  return bands;
}

export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Build the SVG for the graph.
 *
 * The edges are drawn first so the nodes sit on top, and the focused
 * node gets a halo — the file you are in should be the obvious one.
 */
export function renderSvg(graph: Graph, focusId?: string, perBand = 18): string {
  const files = graph.nodes.filter((n) => n.type === "file");
  if (files.length === 0) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="120">
      <text x="12" y="60" fill="#64748b" font-family="monospace" font-size="11">
        No index yet - run: reposcope run .
      </text>
    </svg>`;
  }

  const bands = layoutBands(graph, perBand);
  const width = 320;
  const rowHeight = 26;
  const bandCount = Math.max(1, Math.ceil(files.length / perBand));

  const parts: string[] = [];
  parts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${
      bandCount * rowHeight + 16
    }" viewBox="0 0 ${width} ${bandCount * rowHeight + 16}">`,
  );
  parts.push(`<rect width="100%" height="100%" fill="#0f172a"/>`);

  const byId = new Map(graph.nodes.map((n) => [n.id, n]));

  // Each node's position within its band.
  const indexInBand = new Map<string, number>();
  const bandSeen = new Map<number, number>();
  for (const node of files) {
    const band = bands.get(node.id);
    if (band === undefined) continue;
    const seen = bandSeen.get(band) ?? 0;
    bandSeen.set(band, seen + 1);
    indexInBand.set(node.id, seen);
  }

  // The edges between files, drawn first so the nodes sit on top.
  for (const edge of graph.edges) {
    if (edge.type !== "imports" && edge.type !== "calls") continue;
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) continue;
    if (source.type !== "file" || target.type !== "file") continue;
    const sourceBand = bands.get(source.id);
    const targetBand = bands.get(target.id);
    if (sourceBand === undefined || targetBand === undefined) continue;

    const x1 = 16 + (indexInBand.get(source.id) ?? 0) * 16;
    const y1 = 12 + sourceBand * rowHeight;
    const x2 = 16 + (indexInBand.get(target.id) ?? 0) * 16;
    const y2 = 12 + targetBand * rowHeight;

    parts.push(
      `<path d="M ${x1} ${y1} C ${x1} ${y1 + 18}, ${x2} ${y2 - 18}, ${x2} ${y2}" ` +
        `fill="none" stroke="#334155" stroke-width="0.7" opacity="0.7"/>`,
    );
  }

  // The nodes.
  files.forEach((node) => {
    const band = bands.get(node.id);
    if (band === undefined) return;
    const x = 12 + (indexInBand.get(node.id) ?? 0) * 16;
    const y = 8 + band * rowHeight;
    const colour = LAYER_COLOURS[layerOf(node)] ?? DEFAULT_COLOUR;
    const focused = node.id === focusId;
    const size = focused ? 8 : 5;

    if (focused) {
      parts.push(
        `<circle cx="${x + 3}" cy="${y + 3}" r="${size + 4}" fill="${colour}" opacity="0.28"/>`,
      );
    }
    parts.push(
      `<circle cx="${x + 3}" cy="${y + 3}" r="${size}" fill="${colour}" ` +
        `data-id="${escapeXml(node.id)}" data-label="${escapeXml(String(node.label))}"/>`,
    );
  });

  parts.push("</svg>");
  return parts.join("");
}

// ── The CodeLens logic ──────────────────────────────────────────────────────

/** A definition-ish word at the cursor: an identifier. */
const IDENTIFIER = /[A-Za-z_$][A-Za-z0-9_$]*/g;

/** Keywords that are never symbols. */
const KEYWORDS = new Set([
  "def", "class", "function", "const", "let", "var", "func", "fn", "struct",
  "type", "interface", "public", "private", "static", "async", "export",
  "return", "if", "else", "for", "while", "import", "from", "new", "self",
  "pub", "mut", "impl", "trait", "enum", "where", "match", "def", "lambda",
]);

/**
 * The candidate symbol names on a line.
 *
 * Conservative: the identifiers on the line, minus the keywords. A
 * definition line looks like this in every language RepoScope supports.
 */
export function candidateSymbols(lineText: string): string[] {
  const withoutStrings = lineText.replace(/"[^"]*"|'[^']*'/g, " ");
  const names = withoutStrings.match(IDENTIFIER);
  if (!names) return [];
  return [...new Set(names)].filter((n) => !KEYWORDS.has(n));
}

/** Does this line look like a definition? */
export function isDefinitionLine(lineText: string): boolean {
  return /^\s*(export\s+)?(async\s+)?(pub\s+)?(def|function|func|fn|class|struct|interface|type|const|let|var|impl|trait|enum)\b/.test(
    lineText,
  );
}

/** The label of the "view callers" lens. */
export function callersLensText(count: number): string {
  if (count === 0) return "No callers";
  if (count === 1) return "View Callers (1)";
  return `View Callers (${count})`;
}

// ── The status bar ──────────────────────────────────────────────────────────

/** The status-bar text. */
export function formatStatusText(
  dependents: number,
  risk: string,
  available = true,
): string {
  if (!available) return "RepoScope: offline";
  if (dependents === 0) return "RepoScope: no dependents";
  const plural = dependents === 1 ? "dependent" : "dependents";
  return `$(git-merge) RepoScope: ${dependents} ${plural} | Risk: ${risk}`;
}

/** The status-bar tooltip. */
export function formatStatusTooltip(result: {
  direct: number;
  transitive: number;
  risk_score: number;
}): string {
  return (
    `RepoScope blast radius\n` +
    `Direct dependents: ${result.direct}\n` +
    `Transitive dependents: ${result.transitive}\n` +
    `Risk score: ${result.risk_score}/10\n` +
    `Click for the list.`
  );
}
