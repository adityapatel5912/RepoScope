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

/** The layers, with the names a reader would use. */
export const LAYER_LABELS: Record<string, string> = {
  client: "client",
  backend: "backend",
  storage: "data",
  external: "external",
  compute: "compute",
};

/** The bands, from the most central outwards. */
const BAND_NAMES = ["core", "next", "then", "rest"];

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
 * Build the SVG for the sidebar map.
 *
 * A sidebar is not a canvas. Two views, each answering the question the
 * panel is actually for:
 *
 *   - With a file open, the map is that file's NEIGHBOURHOOD: what it
 *     uses, what uses it, labelled, with counts. That is the question a
 *     developer has while editing.
 *   - With nothing open, it is the repository at a glance: how the files
 *     split by layer, the most central modules, the biggest folders.
 *
 * An earlier version drew every file as a dot in ranked bands. On this
 * repository that was 1,947 dots and 109 rows in a 270-pixel panel:
 * technically the graph, and completely unreadable.
 */

const MAP_WIDTH = 320;

/** Open the SVG at a computed height. */
function svgOpen(height: number): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="${height}" ` +
    `viewBox="0 0 ${MAP_WIDTH} ${height}" preserveAspectRatio="xMinYMin meet">`
  );
}

interface TextOptions {
  size?: number;
  fill?: string;
  weight?: number;
  spacing?: string;
  anchor?: "start" | "end";
}

/** A text run. Everything is escaped here, once. */
function text(x: number, y: number, value: string, options: TextOptions = {}): string {
  const size = options.size ?? 10;
  const fill = options.fill ?? "#cbd5e1";
  const weight = options.weight ? ` font-weight="${options.weight}"` : "";
  const spacing = options.spacing ? ` letter-spacing="${options.spacing}"` : "";
  const anchor = options.anchor ? ` text-anchor="${options.anchor}"` : "";
  return (
    `<text x="${x}" y="${y}" fill="${fill}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" ` +
    `font-size="${size}"${weight}${spacing}${anchor}>${escapeXml(value)}</text>`
  );
}

/** A node dot. The click handler reads `data-id`, the mouse reads `<title>`. */
function dot(
  x: number,
  y: number,
  radius: number,
  colour: string,
  title?: string,
  id?: string,
): string {
  const data = id ? ` data-id="${escapeXml(id)}"` : "";
  const hover = title ? `<title>${escapeXml(title)}</title>` : "";
  return `<circle cx="${x}" cy="${y}" r="${radius}" fill="${colour}"${data}>${hover}</circle>`;
}

/**
 * Shorten a path for the panel, keeping the part that identifies it.
 *
 * "backend/tests/fixtures/real_small/src/tomli/_parser.py" is noise in a
 * 300-pixel column; "_parser.py" is not. The tail is kept because that
 * is the file name; the head is dropped first.
 */
export function shortenLabel(path: string, max = 42): string {
  const value = String(path);
  if (value.length <= max) return value;
  const parts = value.split("/");
  const base = parts[parts.length - 1] ?? value;
  if (base.length >= max - 1) return `…${base.slice(-(max - 1))}`;
  let tail = base;
  for (let index = parts.length - 2; index >= 0; index--) {
    const candidate = `${parts[index]}/${tail}`;
    if (candidate.length + 2 > max) break;
    tail = candidate;
  }
  return `…/${tail}`;
}

/** The empty state: say what to do, not just that there is nothing. */
function emptySvg(): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="120" viewBox="0 0 320 120">` +
    `<rect width="100%" height="100%" fill="#0f172a"/>` +
    `<text x="14" y="58" fill="#64748b" font-family="monospace" font-size="11">No index yet</text>` +
    `<text x="14" y="76" fill="#475569" font-family="monospace" font-size="10">run: reposcope run .</text>` +
    `</svg>`
  );
}

/**
 * The map for the file you are in: its neighbours, labelled.
 *
 * The centre is the file. "Uses" is what it imports; "used by" is what
 * imports it. Both are ranked by the graph's own PageRank, so the first
 * row is the neighbour that matters most. Only the first six of each are
 * drawn; a count says how many are left, because a 270-pixel panel is
 * not the place to list seventeen dependents.
 */
function renderFocusMap(graph: Graph, focus: GraphNode, byId: Map<string, GraphNode>): string {
  const uses: GraphNode[] = [];
  const usedBy: GraphNode[] = [];
  const seenUse = new Set<string>();
  const seenBy = new Set<string>();

  for (const edge of graph.edges) {
    if (edge.type !== "imports" && edge.type !== "calls") continue;
    if (edge.source === focus.id) {
      const target = byId.get(edge.target);
      if (target?.type === "file" && !seenUse.has(target.id)) {
        seenUse.add(target.id);
        uses.push(target);
      }
    } else if (edge.target === focus.id) {
      const source = byId.get(edge.source);
      if (source?.type === "file" && !seenBy.has(source.id)) {
        seenBy.add(source.id);
        usedBy.push(source);
      }
    }
  }

  const rank = (a: GraphNode, b: GraphNode) =>
    (b.pagerank ?? 0) - (a.pagerank ?? 0) || String(a.label).localeCompare(String(b.label));
  uses.sort(rank);
  usedBy.sort(rank);

  const LIMIT = 6;
  const parts: string[] = [];
  let y = 20;

  parts.push(text(12, y, "THIS FILE", { size: 9, fill: "#64748b", spacing: "0.08em" }));
  y += 20;
  const colour = LAYER_COLOURS[layerOf(focus)] ?? DEFAULT_COLOUR;
  parts.push(dot(18, y - 3.5, 5, colour, `${focus.label} · ${layerOf(focus)}`, focus.id));
  parts.push(text(32, y, shortenLabel(focus.label, 40), { size: 11, fill: "#e2e8f0", weight: 600 }));
  y += 18;

  const section = (caption: string, items: GraphNode[], empty: string) => {
    parts.push(text(12, y, `${caption} (${items.length})`, { size: 9, fill: "#64748b", spacing: "0.08em" }));
    y += 16;
    if (items.length === 0) {
      parts.push(text(32, y, empty, { size: 9.5, fill: "#475569" }));
      y += 18;
      return;
    }
    for (const node of items.slice(0, LIMIT)) {
      const nodeColour = LAYER_COLOURS[layerOf(node)] ?? DEFAULT_COLOUR;
      parts.push(dot(18, y - 3, 3.4, nodeColour, `${node.label} · ${layerOf(node)}`, node.id));
      parts.push(text(32, y, shortenLabel(node.label, 42), { size: 9.5, fill: "#cbd5e1" }));
      y += 17;
    }
    if (items.length > LIMIT) {
      parts.push(text(32, y, `+${items.length - LIMIT} more`, { size: 9, fill: "#475569" }));
      y += 16;
    }
    y += 6;
  };

  section("USES", uses, "nothing - a leaf");
  section("USED BY", usedBy, "nothing - no dependents");

  const height = Math.ceil(y + 4);
  return [svgOpen(height), ...parts, "</svg>"].join("");
}

/**
 * The repository at a glance, for when no file is open: the layer split,
 * the most central modules, the biggest folders.
 */
function renderOverview(graph: Graph, files: GraphNode[]): string {
  const parts: string[] = [];
  const left = 12;
  const right = MAP_WIDTH - 12;

  const counts = new Map<string, number>();
  for (const file of files) {
    const layer = layerOf(file);
    counts.set(layer, (counts.get(layer) ?? 0) + 1);
  }
  const layers = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));

  let y = 20;
  parts.push(
    text(left, y, `${files.length.toLocaleString("en-US")} files, ${layers.length} layers`, {
      size: 11,
      fill: "#e2e8f0",
      weight: 600,
    }),
  );
  y += 12;

  // The layer split as one bar, then as counts. The bar is the shape;
  // the counts are the evidence.
  const barHeight = 8;
  parts.push(
    `<rect x="${left}" y="${y}" width="${right - left}" height="${barHeight}" rx="4" fill="#1e293b"/>`,
  );
  let x = left;
  for (const [layer, count] of layers) {
    const width = ((right - left) * count) / files.length;
    parts.push(
      `<rect x="${x.toFixed(1)}" y="${y}" width="${Math.max(1, width).toFixed(1)}" ` +
        `height="${barHeight}" fill="${LAYER_COLOURS[layer] ?? DEFAULT_COLOUR}" opacity="0.9"/>`,
    );
    x += width;
  }
  y += barHeight + 18;

  layers.forEach(([layer, count], index) => {
    const column = index % 2;
    const row = Math.floor(index / 2);
    const layerX = column === 0 ? left : left + 150;
    const layerY = y + row * 16;
    parts.push(dot(layerX + 3, layerY - 3, 3.2, LAYER_COLOURS[layer] ?? DEFAULT_COLOUR));
    parts.push(
      text(layerX + 12, layerY, `${LAYER_LABELS[layer] ?? layer} ${count.toLocaleString("en-US")}`, {
        size: 9.5,
      }),
    );
  });
  y += Math.ceil(layers.length / 2) * 16 + 10;

  const ranked = [...files].sort(
    (a, b) => (b.pagerank ?? 0) - (a.pagerank ?? 0) || String(a.label).localeCompare(String(b.label)),
  );
  parts.push(text(left, y, "MOST CENTRAL", { size: 9, fill: "#64748b", spacing: "0.08em" }));
  y += 15;
  for (const node of ranked.slice(0, 5)) {
    const nodeColour = LAYER_COLOURS[layerOf(node)] ?? DEFAULT_COLOUR;
    parts.push(dot(left + 6, y - 3, 3.4, nodeColour, `${node.label} · ${layerOf(node)}`, node.id));
    parts.push(text(left + 20, y, shortenLabel(node.label, 42), { size: 9.5, fill: "#cbd5e1" }));
    y += 16;
  }
  y += 6;

  const folders = new Map<string, number>();
  for (const file of files) {
    const segments = String(file.label).split("/");
    const folder = segments.length > 1 ? `${segments[0]}/` : "(root)";
    folders.set(folder, (folders.get(folder) ?? 0) + 1);
  }
  const topFolders = [...folders.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 4);
  if (topFolders.length > 0) {
    parts.push(text(left, y, "TOP FOLDERS", { size: 9, fill: "#64748b", spacing: "0.08em" }));
    y += 15;
    for (const [folder, count] of topFolders) {
      parts.push(text(left + 2, y, folder, { size: 9.5, fill: "#94a3b8" }));
      parts.push(text(right, y, String(count), { size: 9.5, fill: "#64748b", anchor: "end" }));
      y += 16;
    }
  }

  const height = Math.ceil(y + 4);
  return [svgOpen(height), ...parts, "</svg>"].join("");
}

/**
 * Render the map. Focused when the editor has a file in the graph,
 * otherwise the repository overview.
 */
export function renderSvg(graph: Graph, focusId?: string): string {
  const files = graph.nodes.filter((node) => node.type === "file");
  if (files.length === 0) return emptySvg();
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const focus = focusId ? byId.get(focusId) : undefined;
  if (focus && focus.type === "file") return renderFocusMap(graph, focus, byId);
  return renderOverview(graph, files);
}

/**
 * The legend for the map: which colour means which layer.
 *
 * Only the layers this repository actually uses are listed. A legend
 * with five entries for a repository with one layer is noise.
 */
export function renderLegend(graph: Graph): string {
  const files = graph.nodes.filter((n) => n.type === "file");
  const used = new Set(files.map((n) => layerOf(n)));
  const entries = Object.keys(LAYER_COLOURS).filter((layer) => used.has(layer));
  if (entries.length === 0) return "";

  const parts: string[] = [];
  for (const layer of entries) {
    const colour = LAYER_COLOURS[layer];
    const label = LAYER_LABELS[layer] ?? layer;
    parts.push(
      `<span class="legend-item">` +
        `<span class="legend-dot" style="background:${colour}"></span>` +
        `${escapeXml(label)}` +
        `</span>`,
    );
  }
  return `<div class="legend">${parts.join("")}</div>`;
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

/**
 * Read the file and line out of a `reposcope://open` link.
 *
 * The web app emits this when a code-tour step is clicked: the map
 * points at a place in the code, and the editor goes there. The parsing
 * lives here, away from `vscode`, so it can be tested.
 */
export function parseOpenUri(query: string): { path: string; line: number } | null {
  const params = new URLSearchParams(query);
  const path = params.get("path");
  if (!path) return null;
  const line = Number(params.get("line") ?? 1);
  return { path, line: Number.isFinite(line) && line > 0 ? Math.floor(line) : 1 };
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
