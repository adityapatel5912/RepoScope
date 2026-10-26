import ReactFlow, {
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  useViewport,
  useNodesInitialized,
  getNodesBounds,
  ReactFlowProvider,
  type Node,
  type Edge,
  type NodeTypes,
  MarkerType,
  ConnectionLineType,
} from "reactflow";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X, MessageSquare, ArrowUpRight, ArrowDownRight, Zap, Map as MapIcon, Flame, Network, ExternalLink } from "lucide-react";
import LayerNode, { NODE_W, NODE_H, CHILD_W, RANK_CONFIGS, type LayerNodeData } from "./graph/LayerNode";
import { classify, LAYER_STYLE, type Layer } from "./graph/layerClassifier";
import EmptyState from "./EmptyState";
import GraphControls from "./GraphControls";
import ReversePromptModal from "./ReversePromptModal";
import ScaffoldModal from "./ScaffoldModal";
import { exportGraphPng, exportGraphSvg } from "../utils/graphExport";
import { generateReversePrompt, generateScaffold, type Scaffold } from "../api/features";
import { getHotspots, churnColor, churnLabel } from "../api/analysis";
import { toast } from "./Toasts";
import { log } from "../utils/logger";
import "reactflow/dist/style.css";

// Tour progress emitted by TourPanel (badges + progress bar on the graph)
export interface TourGraphState {
  currentNodeId: string | null;
  pastNodeIds: string[];
  step: number;
  total: number;
}

// ── Rank Label Node (A8) ───────────────────────────────────────────────────
function RankLabelNode({ data }: { data: { rank: number; label: string } }) {
  // The rank guides are orientation, not content. ReactFlow scales every
  // node with the viewport, so at a 0.2 zoom — which is what a large
  // repository fits to — the guides shrink to 2px and the view loses the
  // only thing it could still communicate: which band is which.
  //
  // Counter-scaling keeps them at a constant screen size. They grow
  // LEFTWARDS (transform-origin: right center) so they never overlap a
  // node, and the scale is capped so a very zoomed-out graph does not
  // produce giant overlapping labels.
  //
  // The cap is 2.6, not 3.2: a label scaled 3.2x is about 125px wide on
  // screen, which reaches past the gutter the fit reserves for it and
  // gets clipped by the canvas edge. At 2.6x the longest label
  // ("Routers and services") is 100px and stays inside its lane.
  const { zoom } = useViewport();
  const scale = Math.min(1 / Math.max(zoom, 0.18), 2.6);

  return (
    <div
      className="rs-rank-label pointer-events-none select-none text-right pr-4 whitespace-nowrap"
      style={{ transform: `scale(${scale})` }}
    >
      <div className="text-[11px] font-bold uppercase text-[#94A3B8] tracking-[0.08em]">
        Rank {data.rank}
      </div>
      <div className="text-[10px] uppercase font-semibold text-[#94A3B8]/90 tracking-[0.08em]">
        {data.label}
      </div>
    </div>
  );
}

// ── Node type registrations (all types render through LayerNode) ────────────
const nodeTypes: NodeTypes = {
  root:      LayerNode,
  folder:    LayerNode,
  file:      LayerNode,
  function:  LayerNode,
  class:     LayerNode,
  import:    LayerNode,
  commit:    LayerNode,
  repo:      LayerNode,
  // The architecture-cluster view (Milestone 1.2). Without this entry
  // ReactFlow falls back to its DEFAULT node renderer, which draws a
  // plain white box with a label and none of the layer styling.
  cluster:   LayerNode,
  rankLabel: RankLabelNode,
};

// ── Canvas palette (A10: #FAF8FF container, #D9D2C0 dots) ───────────────────
const CANVAS_BG  = "#FAF8FF";

/**
 * Shared fit-view options.
 *
 * The floor MUST match the ReactFlow `minZoom` prop (0.2). It used to be
 * 0.3, which was HIGHER than the prop — so when the pyramid was taller
 * than the canvas, fitView clamped the zoom at 0.3, could not fit the
 * content, and centred the overflow. The overflow at the top was painted
 * under the sticky TopBar (z-50), which clipped the root node and made it
 * unclickable.
 *
 * Measured by the browser-QA harness (journey J05): the root node
 * overlapped the header by 24px before this fix.
 */
const FIT_VIEW_OPTIONS = {
  padding: 0.15,
  minZoom: 0.2,
  maxZoom: 0.9,
} as const;

/**
 * How far to nudge the fitted view up and to the right.
 *
 * The toolbar floats in the bottom-left of the canvas. A fit centres the
 * content in the raw container, so a narrow graph — the architecture
 * cluster view, for instance — lands squarely on top of the toolbar and
 * its nodes become unclickable. Nudging the viewport after the fit moves
 * the content clear of the toolbar without changing the zoom.
 */
/**
 * The space the floating toolbar occupies at the bottom-left of the canvas.
 *
 * The toolbar is one row now — actions and zoom side by side — so it is
 * about 48px tall. The fit reserves 80px, which includes the 16px gutter
 * below it.
 */
const TOOLBAR_INSET = { width: 640, height: 80 };

/**
 * The space the floating pieces of the canvas need, so the fit keeps the
 * graph clear of them.
 *
 * The LEGEND floats in the top-right corner and the RANK LABELS sit to
 * the left of the leftmost column. Neither is part of the graph's
 * bounding box in the way a reader expects:
 *
 *   - the legend is an overlay, so the fitted content used to slide
 *     underneath it and two nodes were hidden behind the card;
 *   - the rank labels are counter-scaled so they stay readable at a
 *     0.2 zoom, which means they are WIDER on screen than the node box
 *     the fit measures. The label "Routers and services" grows about 90px
 *     to the left of the graph's own edge and was clipped by the canvas.
 *
 * Both are reserved here, so the fit lands the graph in the space that
 * is actually free.
 */
const LEGEND_INSET = { width: 196, height: 0 };
const RANK_LABEL_INSET = { width: 132, height: 0 };

const DOT_COLOR  = "#D9D2C0";

// ── Layout constants (A6: 280 vertical spacing, 280 / 220 sibling spacing) ─
const RANK_Y          = 280;
/**
 * The grouped map has at most one card per module, not one per file, so
 * the wide sub-row spacing of the file pyramid would just make the whole
 * map smaller. The compact pitch keeps an 11-13 card map readable.
 */
const RANK_Y_GROUPED  = 112;
const SIBLING_X       = 280;
const SIBLING_X_TIGHT = 220;
const MAX_ROW_WIDTH   = 6000;
const MIN_CLEAR_X     = 24;

/**
 * The number of files above which the map groups by directory.
 *
 * Below it, the flat list is the clearer view: nine files are nine
 * nodes, and grouping them would hide the very thing the map is for.
 */
const GROUPING_THRESHOLD = 40;

const RANK_TITLES: Record<number, string> = {
  1: "Backbone files",
  2: "Core modules",
  3: "Routers and services",
  4: "UI components",
  5: "Config",
  6: "Docs and data",
};

interface RawNode {
  id: string;
  type: string;
  label: string;
  line?: number;
  file?: string;
  size?: number;
  /** PageRank centrality, computed server-side (Milestone 7.1). */
  pagerank?: number;
  /** Number of dependency edges pointing at this node. */
  in_degree?: number;
  /** Number of dependency edges leaving this node. */
  out_degree?: number;
  /** Betweenness centrality — is this node on the critical path? */
  betweenness?: number;
}

function basename(p: string): string {
  const parts = p.split("/");
  return parts[parts.length - 1] || p;
}

/**
 * The directory a file belongs to on the grouped map.
 *
 * The immediate parent is the wrong granularity for a large repository:
 * this one has 347 files in 70 directories, so "grouped" still drew 70
 * nodes and the fit shrank them to unreadable dots. The map groups by
 * MODULE — the top-level directory — and only splits a module further
 * when it is too large to read as one card. A 13-card map fits the canvas
 * at a readable zoom; the drawer still lists every file in the card.
 */
function directoryOf(path: string): string {
  const idx = path.lastIndexOf("/");
  return idx === -1 ? "" : path.slice(0, idx);
}

/** Above this many files, a module is split into its subdirectories. */
const MAX_MODULE_FILES = 200;

interface DirectoryTree {
  path: string;
  files: string[];
  children: Map<string, DirectoryTree>;
  total: number;
}

/**
 * Assign every file to the module card that will represent it.
 *
 * The tree is built from the paths, then walked top-down. A directory
 * with at most MAX_MODULE_FILES files becomes one card; a larger one is
 * split into its children, with the files that live directly in it kept
 * on a card of their own. That gives small repositories one card per
 * top-level directory and large ones a card per package.
 */
function buildModuleGroups(paths: string[]): Map<string, string> {
  const root: DirectoryTree = { path: "", files: [], children: new Map(), total: 0 };

  for (const path of paths) {
    const parts = path.split("/");
    let node = root;
    for (const part of parts.slice(0, -1)) {
      let child = node.children.get(part);
      if (!child) {
        child = {
          path: node.path ? `${node.path}/${part}` : part,
          files: [],
          children: new Map(),
          total: 0,
        };
        node.children.set(part, child);
      }
      node = child;
    }
    node.files.push(path);
  }

  const count = (node: DirectoryTree): number => {
    node.total = node.files.length;
    for (const child of node.children.values()) node.total += count(child);
    return node.total;
  };
  count(root);

  const groups = new Map<string, string>();
  const collect = (node: DirectoryTree, groupPath: string): void => {
    for (const file of node.files) groups.set(file, groupPath);
    for (const child of node.children.values()) collect(child, groupPath);
  };
  const assign = (node: DirectoryTree): void => {
    if (node.total <= MAX_MODULE_FILES || node.children.size === 0) {
      collect(node, node.path);
      return;
    }
    // The files sitting directly in this directory keep their own card;
    // the subdirectories are considered separately.
    for (const file of node.files) groups.set(file, node.path);
    for (const child of node.children.values()) assign(child);
  };
  assign(root);
  return groups;
}

/**
 * Disambiguate repeated file names.
 *
 * A Python package has an `__init__.py` in every sub-package, so a
 * repository routinely shows eight nodes all labelled "__init__.py" in a
 * row — indistinguishable. When a basename repeats, the label gains its
 * parent directory, so the row reads "chat/__init__.py", "engine/__init__.py".
 *
 * Returns a lookup from the full path to the label to show.
 */
function buildLabelResolver(fileNodes: RawNode[]): (path: string) => string {
  const counts = new Map<string, number>();
  for (const node of fileNodes) {
    const base = basename(String(node.label));
    counts.set(base, (counts.get(base) ?? 0) + 1);
  }
  return (path: string): string => {
    const base = basename(path);
    if ((counts.get(base) ?? 0) < 2) return base;
    const parts = path.split("/").filter(Boolean);
    if (parts.length > 1) return `${parts[parts.length - 2]}/${base}`;
    return base;
  };
}

// ── Connectivity scoring ────────────────────────────────────────────────────
//
// The backend computes PageRank over the dependency graph and attaches it
// to every node (Milestone 7.1). PageRank is used when it is available,
// because it is a real centrality measure — the old `incoming x 2 +
// outgoing` heuristic cannot tell a widely-imported leaf from a genuine
// hub. The degree heuristic remains as the fallback for a graph built
// without the analysis pass, and the path heuristic remains the last
// resort for a file with no edges at all.
function scoreNode(
  nodeId: string,
  importEdges: Array<{ source: string; target: string }>,
  pagerankById?: Map<string, number>,
): number {
  const pagerank = pagerankById?.get(nodeId);
  if (pagerank !== undefined && pagerank > 0) {
    // PageRank sums to 1 across the graph, so scale it into the same
    // range as the degree heuristic to keep the ranking comparable.
    return pagerank * 1000;
  }

  let incoming = 0;
  let outgoing = 0;
  for (const e of importEdges) {
    if (e.target === nodeId) incoming += 1;
    else if (e.source === nodeId) outgoing += 1;
  }
  return incoming * 2 + outgoing;
}

/** Index the PageRank scores by node id, once per graph build. */
function pagerankIndex(rawNodes: RawNode[]): Map<string, number> {
  const index = new Map<string, number>();
  for (const node of rawNodes) {
    if (typeof node.pagerank === "number" && node.pagerank > 0) {
      index.set(node.id, node.pagerank);
    }
  }
  return index;
}

// Path-based fallback when a file has no import edges at all
function fallbackScore(path: string): number {
  const id = path.toLowerCase();
  if (/(^|\/)(main|app)\.(py|tsx)$|(^|\/)(db|types)\.(py|ts)$/.test(id)) return 100;
  if (/(^|\/)(state|api)\.(py|ts)$|decision_model/.test(id)) return 90;
  if (/provider_router|system_prompts/.test(id)) return 80;
  if (/(^|\/)(routers|services|redteam|export)\//.test(id) || /exporters/.test(id)) return 60;
  if (/(^|\/)(components|store|workers|hooks)\//.test(id)) return 40;
  if (/utils\//.test(id)) return 30;
  if (/requirements|package\.json/.test(id)) return 20;
  if (/render\.yaml|vercel\.json|build\.sh|tsconfig|vite\.config/.test(id)) return 15;
  if (/\.md$|(^|\/)(docs|test data|demo data)/i.test(id)) return 5;
  return 25;
}

function categorizeFile(label: string): number {
  const lower = label.toLowerCase();
  if (
    /\.(md|txt|csv|tsv|jsonl|rst)$/i.test(lower) ||
    /(^|\/)(docs?|fixtures|mock|data|demo_data|examples?)\//i.test(lower)
  ) {
    return 6; // Docs and data
  }
  if (
    /(config|setup|\.env|package\.json|tsconfig|vite\.config|docker|requirements|cargo\.toml|go\.mod|webpack|eslint|\.ya?ml|\.toml|\.ini)$/i.test(lower) ||
    /(^|\/)(config|docker)\//i.test(lower)
  ) {
    return 5; // Config
  }
  if (
    /(^|\/)(components?|pages?|views?|screens?|ui|styles?|frontend|client)\//i.test(lower) ||
    /\.(tsx|jsx|vue|svelte|css|scss|html)$/i.test(lower)
  ) {
    return 4; // UI components
  }
  if (
    /(^|\/)(routers?|routes?|services?|handlers?|controllers?|api|endpoints?)\//i.test(lower)
  ) {
    return 3; // Routers and services
  }
  return 2; // Core candidate
}

/**
 * Pyramid layout (A1-A8):
 * - Repo root at top (Rank 0)
 * - Files bucketed into Ranks 1..6
 * - 280px vertical spacing, horizontal centering
 * - Max row width 6000px (wraps to sub-rows with 40px gap)
 * - Edges with sourceHandle 'out' and targetHandle 'in'
 * - Filtered strictly to parent-child only (t === s + 1)
 */
/**
 * Build the architecture-cluster view (Milestone 1.2).
 *
 * The file pyramid shows every file. That is the right view for reading
 * a codebase and the wrong view for understanding its SHAPE: with 300
 * files, the important question — "what are the layers, and how big is
 * each one?" — is answered by squinting at a wall of nodes.
 *
 * The cluster view collapses the graph into the five canonical layers.
 * Each cluster node shows the layer, its file count, and its share of
 * the repository. Clicking one opens the drawer with its file list.
 *
 * The layout is a deliberate, simple vertical stack: the repo root at the
 * top, the five layers beneath it. It is not a force layout — the point
 * is that it is always readable and always the same.
 */
function buildClusterGraph(
  raw: unknown[],
  _rawEdges: unknown[],
  repoTitle: string,
): { nodes: Node[]; edges: Edge[] } {
  const rn = raw as RawNode[];
  if (rn.length === 0) return { nodes: [], edges: [] };

  const fileNodes = rn.filter((n) => n.type === "file");
  const byLayer = new Map<Layer, RawNode[]>();
  for (const layer of Object.keys(LAYER_STYLE) as Layer[]) {
    byLayer.set(layer, []);
  }
  for (const node of fileNodes) {
    const layer = classify(String(node.id), String(node.label));
    byLayer.get(layer)?.push(node);
  }

  const repoCfg = RANK_CONFIGS[0] ?? RANK_CONFIGS[2];
  const cfg = RANK_CONFIGS[1] ?? RANK_CONFIGS[2];

  const out: Node[] = [];
  const edges: Edge[] = [];

  out.push({
    id: "repo:root",
    type: "root",
    position: { x: 0, y: 0 },
    width: repoCfg.width,
    height: repoCfg.height,
    data: {
      label: repoTitle,
      kind: "root",
      layer: classify("repo:root", repoTitle),
      rank: 0,
      fullPath: repoTitle,
    } satisfies LayerNodeData,
  });

  const layers = (Object.keys(LAYER_STYLE) as Layer[])
    .filter((layer) => (byLayer.get(layer)?.length ?? 0) > 0);
  // The pitch must exceed the node width, or the cluster cards overlap.
  // RANK_CONFIGS[1].width is 260, so 300 leaves a 40px gutter.
  const pitch = cfg.width + 40;
  const totalWidth = (layers.length - 1) * pitch;

  layers.forEach((layer, index) => {
    const files = byLayer.get(layer) ?? [];
    const style = LAYER_STYLE[layer];
    const id = `cluster:${layer}`;
    out.push({
      id,
      type: "cluster",
      position: { x: -totalWidth / 2 + index * pitch, y: 140 },
      width: cfg.width,
      height: cfg.height,
      data: {
        label: style.name,
        kind: "cluster",
        layer,
        rank: 1,
        subtitle: `${files.length} file${files.length === 1 ? "" : "s"}`,
        fullPath: style.name,
        // The drawer reads this to list the cluster's files.
        symbols: files.slice(0, 12).map((f) => String(f.label)),
      } satisfies LayerNodeData,
    });
    edges.push({
      id: `e-root-${layer}`,
      source: "repo:root",
      target: id,
      type: "smoothstep",
      sourceHandle: "out",
      targetHandle: "in",
    });
  });

  return { nodes: out, edges };
}

function buildPyramidGraph(
  raw: unknown[],
  rawEdges: unknown[],
  repoTitle: string,
  grouped: boolean,
  _invert: boolean,
  churnScores?: Map<string, number>,
): { nodes: Node[]; edges: Edge[] } {
  const rn = raw as RawNode[];
  if (rn.length === 0) return { nodes: [], edges: [] };

  const fileNodes = rn.filter((n) => n.type === "file");
  const edgeList = (rawEdges as Array<{ source: string; target: string; type?: string }>)
    .filter((e) => typeof e?.source === "string" && typeof e?.target === "string");
  const importEdges = edgeList.filter((e) => e.type === "imports" || e.type === "calls");

  // The symbols each file defines, with their line numbers.
  //
  // This is what makes "open in editor" open the EXACT line rather than
  // the top of the file: the drawer can offer `greet() — line 19` and
  // take the user straight there.
  const symbolsByFile = new Map<string, { name: string; line: number }[]>();
  for (const node of rn) {
    if (node.type !== "function" && node.type !== "class") continue;
    if (!node.file) continue;
    const list = symbolsByFile.get(node.file) ?? [];
    list.push({ name: String(node.label), line: Number(node.line ?? 0) });
    symbolsByFile.set(node.file, list);
  }
  for (const list of symbolsByFile.values()) {
    list.sort((a, b) => a.line - b.line);
  }

  log(
    `[EDGE DIAG] nodes: ${rn.length} · edges in: ${edgeList.length} · ` +
    `matching IDs: ${edgeList.filter((e) =>
      rn.some((n) => n.id === e.source) && rn.some((n) => n.id === e.target),
    ).length}`,
  );

  // Score and sort files.
  //
  // PageRank is used when the backend supplied it, so the pyramid's rows
  // are ranked by a real centrality measure rather than by a degree
  // heuristic. The fallback chain is unchanged, so a graph built without
  // the analysis pass still ranks sensibly.
  const pagerankById = pagerankIndex(rn);
  const labelFor = buildLabelResolver(fileNodes);
  const scored = fileNodes
    .map((n) => ({
      node: n,
      score: scoreNode(n.id, importEdges, pagerankById) || fallbackScore(String(n.label)),
      category: categorizeFile(String(n.label)),
    }))
    .sort((a, b) => (b.score !== a.score ? b.score - a.score : a.node.id.localeCompare(b.node.id)));

  // Partition into Ranks 1..6
  const rankBuckets = new Map<number, Array<{ node: RawNode; score: number; category: number }>>();
  for (let r = 1; r <= 6; r++) rankBuckets.set(r, []);

  const backboneCandidates: Array<{ node: RawNode; score: number; category: number }> = [];
  scored.forEach((item) => {
    if (item.category === 6) {
      rankBuckets.get(6)!.push(item);
    } else if (item.category === 5) {
      rankBuckets.get(5)!.push(item);
    } else {
      backboneCandidates.push(item);
    }
  });

  // Top up to 6 files by connectivity/importance become Rank 1 (Backbone files)
  const topBackboneCount = Math.min(6, Math.max(1, Math.min(backboneCandidates.length, 6)));
  const topBackbones = backboneCandidates.slice(0, topBackboneCount);
  const remaining = backboneCandidates.slice(topBackboneCount);

  rankBuckets.get(1)!.push(...topBackbones);

  remaining.forEach((item) => {
    if (item.category === 4) {
      rankBuckets.get(4)!.push(item);
    } else if (item.category === 3) {
      rankBuckets.get(3)!.push(item);
    } else {
      rankBuckets.get(2)!.push(item);
    }
  });

  const out: Node[] = [];
  const placedIds = new Set<string>();

  // ── Grouping ────────────────────────────────────────────────────────────
  //
  // "Group by directory" is the difference between a map you can read and
  // a wall of dots. A repository with 450 files has about 60
  // directories; the pyramid draws 60 nodes instead of 450, and each one
  // says how many files it holds.
  //
  // The RANKS do not change: a group sits in the rank of its most
  // important member, so the shape of the map still means "how central is
  // this, and how central is that".
  const groupOfFile = new Map<string, string>();
  const groupedItems = new Map<number, Array<{
    node: RawNode;
    score: number;
    category: number;
    files?: string[];
  }>>();

  if (grouped) {
    const byDir = new Map<string, {
      path: string;
      files: string[];
      size: number;
      score: number;
      category: number;
      rank: number;
    }>();
    const moduleOf = buildModuleGroups(fileNodes.map((n) => String(n.label)));

    for (let r = 1; r <= 6; r++) {
      for (const item of rankBuckets.get(r) || []) {
        const fileId = String(item.node.id);
        const path = String(item.node.label);
        const dir = moduleOf.get(path) ?? directoryOf(path);
        const gid = `dir:${dir || "."}`;
        groupOfFile.set(fileId, gid);

        let group = byDir.get(gid);
        if (!group) {
          group = {
            path: dir,
            files: [],
            size: 0,
            score: 0,
            category: item.category,
            rank: r,
          };
          byDir.set(gid, group);
        }
        group.files.push(path);
        group.size += Number(item.node.size ?? 0);
        if (item.score > group.score) {
          group.score = item.score;
          group.category = item.category;
        }
        if (r < group.rank) group.rank = r;
      }
    }

    for (const group of byDir.values()) {
      const list = groupedItems.get(group.rank) ?? [];
      list.push({
        node: {
          id: `dir:${group.path || "."}`,
          label: group.path || "(repository root)",
          size: group.size,
        } as RawNode,
        score: group.score,
        category: group.category,
        files: group.files,
      });
      groupedItems.set(group.rank, list);
    }
  }

  const buckets: Map<number, Array<{ node: RawNode; score: number; category: number; files?: string[] }>> =
    grouped ? groupedItems : rankBuckets;

  // Rank 0 — repo node (320x80)
  const repoCfg = RANK_CONFIGS[0];
  out.push({
    id: "repo:root",
    type: "root",
    position: { x: 0, y: 0 },
    width: repoCfg.width,
    height: repoCfg.height,
    data: {
      label: repoTitle,
      kind: "root",
      layer: classify("repo:root", repoTitle),
      rank: 0,
      fullPath: repoTitle,
    } satisfies LayerNodeData,
  });
  placedIds.add("repo:root");

  // Ranks 1..6 — file nodes, or folder nodes when the map is grouped.
  const rankY = grouped ? RANK_Y_GROUPED : RANK_Y;
  // Empty ranks are common once modules are grouped (a repository may have
  // no group whose best file sits in rank 3 or 4). Leaving those rows in
  // the layout pushes the lower ranks off the canvas and forces the fit to
  // zoom out for rows that contain nothing.
  const visualRow = new Map<number, number>();
  let occupiedRows = 0;
  for (let r = 1; r <= 6; r++) {
    if ((buckets.get(r) || []).length > 0) visualRow.set(r, ++occupiedRows);
  }
  for (let r = 1; r <= 6; r++) {
    const items = buckets.get(r) || [];
    if (items.length === 0) continue;
    const row = visualRow.get(r) ?? r;

    const cfg = RANK_CONFIGS[r] ?? RANK_CONFIGS[2];
    const pitch = Math.max(cfg.width + MIN_CLEAR_X, items.length > 12 ? SIBLING_X_TIGHT : SIBLING_X);
    const totalRowWidth = (items.length - 1) * pitch;

    // One node, whether it is a file or a directory.
    const makeNode = (item: { node: RawNode; files?: string[] }, x: number, y: number): Node => {
      const path = String(item.node.label);
      const isGroup = Boolean(item.files);
      if (isGroup) {
        const files = item.files!;
        const dir = path === "(repository root)" ? "" : path;
        return {
          id: String(item.node.id),
          type: "folder",
          position: { x, y },
          width: cfg.width,
          height: cfg.height,
          data: {
            label: dir === "" ? "(root)" : dir,
            kind: "folder",
            layer: classify(String(item.node.id), path),
            subtitle: `${files.length} file${files.length === 1 ? "" : "s"}`,
            fullPath: dir,
            size: item.node.size,
            rank: r,
            files,
          } satisfies LayerNodeData,
        };
      }
      return {
        id: String(item.node.id),
        type: "file",
        position: { x, y },
        width: cfg.width,
        height: cfg.height,
        data: {
          label: labelFor(path),
          kind: "file",
          layer: classify(String(item.node.id), path),
          subtitle: path,
          fullPath: path,
          size: item.node.size,
          rank: r,
          churn: churnScores?.get(path) ?? 0,
          symbolRefs: symbolsByFile.get(path)?.slice(0, 8),
        } satisfies LayerNodeData,
      };
    };

    if (totalRowWidth > MAX_ROW_WIDTH) {
      // Wrap into sub-rows with a 40px vertical gap between node edges (A6)
      const maxPerRow = Math.max(1, Math.floor(MAX_ROW_WIDTH / pitch));
      const subRowCount = Math.ceil(items.length / maxPerRow);
      const rowStepY = cfg.height + 40;
      const startBaseY = row * rankY - ((subRowCount - 1) * rowStepY) / 2;

      for (let sIdx = 0; sIdx < subRowCount; sIdx++) {
        const subItems = items.slice(sIdx * maxPerRow, (sIdx + 1) * maxPerRow);
        const subWidth = (subItems.length - 1) * pitch;
        const subStartX = -subWidth / 2;
        const subY = startBaseY + sIdx * rowStepY;

        subItems.forEach((item, i) => {
          const node = makeNode(item, subStartX + i * pitch, subY);
          out.push(node);
          placedIds.add(node.id);
        });
      }
    } else {
      const startX = -totalRowWidth / 2;
      items.forEach((item, i) => {
        const node = makeNode(item, startX + i * pitch, row * rankY);
        out.push(node);
        placedIds.add(node.id);
      });
    }
  }

  // Centering pyramid horizontally (A6)
  const xs = out.map((n) => n.position.x);
  if (xs.length > 0) {
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const offsetX = -(minX + maxX) / 2;
    out.forEach((n) => {
      n.position.x += offsetX;
    });
  }

  // Add Rank Labels on left edge of the canvas (A8)
  const centeredXs = out.map((n) => n.position.x);
  const leftEdgeX = Math.min(...centeredXs) - 180;
  for (let r = 1; r <= 6; r++) {
    if ((buckets.get(r) || []).length > 0) {
      out.push({
        id: `rank-label-${r}`,
        type: "rankLabel",
        position: { x: leftEdgeX, y: (visualRow.get(r) ?? r) * rankY + 16 },
        width: 140,
        height: 50,
        data: { rank: r, label: RANK_TITLES[r] },
        selectable: false,
        draggable: false,
        focusable: false,
      });
    }
  }

  // Synthesize containment edges: repo root → rank 1
  const validEdges: Array<{ source: string; target: string; type?: string }> = [];
  const rank1Nodes = buckets.get(1) || [];
  for (const item of rank1Nodes) {
    validEdges.push({ source: "repo:root", target: String(item.node.id), type: "groups" });
  }

  // Real edges from imports/calls.
  //
  // In a GROUPED map the drawn nodes are directories, so a file-level
  // edge is lifted to the edge between the two directories. The lift
  // loses the file detail — that is what the "flat" view is for — but it
  // keeps the dependency STRUCTURE, which is the thing the map is for.
  const seenEdges = new Set<string>();
  for (const e of edgeList) {
    const source = grouped ? (groupOfFile.get(e.source) ?? e.source) : e.source;
    const target = grouped ? (groupOfFile.get(e.target) ?? e.target) : e.target;
    if (!placedIds.has(source) || !placedIds.has(target) || source === target) continue;
    const key = `${source}->${target}`;
    if (seenEdges.has(key)) continue;
    seenEdges.add(key);
    validEdges.push({ source, target, type: e.type });
  }

  // Ensure every node in rank r (r >= 2) has a connection from rank r - 1
  const nodesByRank = new Map<number, Node[]>();
  out.forEach((n) => {
    if (n.type !== "rankLabel") {
      const r = (n.data as LayerNodeData)?.rank ?? 0;
      const list = nodesByRank.get(r) || [];
      list.push(n);
      nodesByRank.set(r, list);
    }
  });

  const rankOfId: Record<string, number> = {};
  out.forEach((n) => {
    rankOfId[n.id] = (n.data as LayerNodeData)?.rank ?? 0;
  });

  const hasParentFromPrevRank = new Set<string>();
  validEdges.forEach((e) => {
    const s = rankOfId[e.source] ?? 0;
    const t = rankOfId[e.target] ?? 0;
    if (t === s + 1) {
      hasParentFromPrevRank.add(e.target);
    }
  });

  for (let r = 2; r <= 6; r++) {
    const currentNodes = nodesByRank.get(r) || [];
    const prevNodes = nodesByRank.get(r - 1) || [];
    if (prevNodes.length === 0) continue;

    for (const node of currentNodes) {
      if (!hasParentFromPrevRank.has(node.id)) {
        let closest = prevNodes[0];
        let minDist = Math.abs(node.position.x - closest.position.x);
        for (let i = 1; i < prevNodes.length; i++) {
          const d = Math.abs(node.position.x - prevNodes[i].position.x);
          if (d < minDist) {
            minDist = d;
            closest = prevNodes[i];
          }
        }
        validEdges.push({ source: closest.id, target: node.id, type: "flow" });
        hasParentFromPrevRank.add(node.id);
      }
    }
  }

  // A2 — FIX EDGE DEFINITIONS
  const styledEdges = validEdges.map((e, i) => ({
    ...e,
    id: `e-${e.source}--${e.target}-${i}`,
    sourceHandle: "out",
    targetHandle: "in",
    type: "smoothstep",
    style: {
      stroke: "#94A3B8",
      strokeWidth: 1.5,
      opacity: 0.7,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 14,
      height: 14,
      color: "#94A3B8",
    },
    pathOptions: {
      borderRadius: 12,
      offset: 20,
    },
  }));

  // A3 — FILTER EDGES TO PARENT-CHILD ONLY
  const rankMap: Record<string, number> = {};
  out.forEach((n) => {
    rankMap[n.id] = (n.data as LayerNodeData)?.rank ?? 0;
  });
  const visibleEdges = styledEdges.filter((e) => {
    const s = rankMap[e.source] ?? 0;
    const t = rankMap[e.target] ?? 0;
    return t === s + 1;
  });

  return { nodes: fixOverlaps(out), edges: visibleEdges };
}

/**
 * Collision pass (Section 2): sweep every row left→right and enforce a minimum
 * center-to-center gutter so no two nodes can overlap. Uses real node widths
 * (from RANK_CONFIGS), so the result is deterministic.
 */
function fixOverlaps(nodes: Node[]): Node[] {
  const widthOf = (n: Node) => {
    if ((n.data as LayerNodeData)?.child) return CHILD_W;
    const r = (n.data as LayerNodeData)?.rank;
    return r != null ? (RANK_CONFIGS[r]?.width ?? NODE_W) : (n.width ?? NODE_W);
  };
  const heightOf = (n: Node) => {
    const r = (n.data as LayerNodeData)?.rank;
    return r != null ? (RANK_CONFIGS[r]?.height ?? NODE_H) : (n.height ?? NODE_H);
  };

  const workNodes = nodes.filter((n) => n.type !== "rankLabel");
  const MIN_GAP_X = 24;

  // Multiple passes to resolve any 2D bounding-box collisions
  for (let pass = 0; pass < 6; pass++) {
    let hadCollision = false;
    workNodes.sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x);

    for (let i = 0; i < workNodes.length; i++) {
      for (let j = i + 1; j < workNodes.length; j++) {
        const a = workNodes[i];
        const b = workNodes[j];

        const aW = widthOf(a);
        const aH = heightOf(a);
        const bW = widthOf(b);
        const bH = heightOf(b);

        const aRight = a.position.x + aW;
        const bRight = b.position.x + bW;
        const aBottom = a.position.y + aH;
        const bBottom = b.position.y + bH;

        // Check if bounding boxes overlap
        const xOverlap = Math.min(aRight, bRight) - Math.max(a.position.x, b.position.x);
        const yOverlap = Math.min(aBottom, bBottom) - Math.max(a.position.y, b.position.y);

        if (xOverlap > 0 && yOverlap > 0) {
          hadCollision = true;
          // Shift whichever node is further to the right by xOverlap + MIN_GAP_X
          if (b.position.x >= a.position.x) {
            b.position = { ...b.position, x: aRight + MIN_GAP_X };
          } else {
            a.position = { ...a.position, x: bRight + MIN_GAP_X };
          }
        }
      }
    }
    if (!hadCollision) break;
  }

  return nodes;
}

// ── Legend (FILE 3: top-right, white card, one swatch per layer) ────────────
function Legend({ visible, churn }: { visible: boolean; churn?: boolean }) {
  if (!visible) return null;
  return (
    <div className="graph-legend absolute top-4 right-4 z-[5] card-flat !border-border-hairline px-3 py-2.5 pointer-events-none">
      <p className="label-caps !text-[10px] mb-1.5">Layers</p>
      <ul className="flex flex-col gap-1">
        {(Object.keys(LAYER_STYLE) as Layer[]).map((l) => (
          <li key={l} className="flex items-center gap-2">
            <span
              className="w-3.5 h-3.5 rounded-sm border"
              style={{ background: LAYER_STYLE[l].fill, borderColor: LAYER_STYLE[l].border }}
            />
            <span className="text-[11px] font-medium text-text-secondary">{LAYER_STYLE[l].name}</span>
          </li>
        ))}
      </ul>

      {/*
        The churn spectrum lives in the SAME card. It used to be a second
        absolutely-positioned card at the same corner, which painted over
        the layer legend and cut it in half.
      */}
      {churn && (
        <>
          <p className="label-caps !text-[10px] mt-2.5 mb-1.5 pt-2 border-t border-border-hairline">
            Churn
          </p>
          <ul className="flex flex-col gap-1">
            {[
              { score: 0.1, label: "Stable" },
              { score: 0.4, label: "Churn" },
              { score: 0.8, label: "Hotspot" },
            ].map((entry) => (
              <li key={entry.label} className="flex items-center gap-2">
                <span
                  className="w-3.5 h-3.5 rounded-sm border-2 bg-transparent"
                  style={{ borderColor: churnColor(entry.score) }}
                />
                <span className="text-[11px] font-medium text-text-secondary">{entry.label}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/**
 * The churn spectrum legend (Milestone 1.3).
 *
 * The layer keeps the node's fill; the churn is a separate outer ring.
 * Two signals, one colour each — never mixed into a single swatch.
 *
 * The spectrum is rendered inside the LAYER legend card rather than as a
 * second floating card — two cards in the same corner painted over each
 * other.
 */

// ── Node detail drawer ──────────────────────────────────────────────────────
interface NodeDrawerProps {
  node: Node;
  edges: Edge[];
  onClose: () => void;
  onAskAbout: (label: string) => void;
  onAnalyzeImpact?: (label: string) => void;
  onStartTour?: (label: string) => void;
  /**
   * Open the node's file in the user's editor.
   *
   * `localRoot` is the absolute path of the repository on this machine
   * (known in local mode); without it the path is copied instead.
   */
  onOpenInEditor?: (path: string, line: number) => void;
  localRoot?: string | null;
  /** True when the node belongs to a browser-parsed preview. */
  preview?: boolean;
}

function NodeDrawer({
  node, edges, onClose, onAskAbout, onAnalyzeImpact, onStartTour,
  onOpenInEditor, localRoot, preview = false,
}: NodeDrawerProps) {
  const data = node.data as LayerNodeData;
  const style = LAYER_STYLE[data.layer];
  const incoming = edges.filter((e) => e.target === node.id).length;
  const outgoing = edges.filter((e) => e.source === node.id).length;
  // A folder card groups files from a whole subtree, so show each file
  // relative to that card ("api/routers/local.py"), not just its basename.
  const groupDir = data.kind === "folder" ? String(data.fullPath ?? "") : "";

  return (
    <div className="
      drawer-slide-in node-drawer
      absolute top-4 right-4 z-10 w-72 max-h-[calc(100%-2rem)] overflow-y-auto
      card p-4
    ">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <span
            className="inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border mb-1.5"
            style={{ color: style.text, borderColor: style.border, background: style.fill }}
          >
            {data.kind} · {style.name.split(" /")[0]}
          </span>
          <div className="font-mono text-sm text-text-primary break-all leading-snug">
            {data.label}
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close details"
          className="ml-2 shrink-0 w-7 h-7 flex items-center justify-center rounded-lg
            text-text-muted hover:text-text-primary hover:bg-bg-panel-hover transition-all duration-150"
        >
          <X size={14} />
        </button>
      </div>

      {/* Meta */}
      <div className="space-y-1.5 mb-3">
        {data.size != null && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-muted">Size</span>
            <span className="font-mono text-text-primary">
              {data.size >= 1024 ? `${(data.size / 1024).toFixed(1)} KB` : `${data.size} B`}
            </span>
          </div>
        )}
        {data.line != null && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-muted">Line</span>
            <span className="font-mono text-text-primary">{data.line}</span>
          </div>
        )}
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-muted flex items-center gap-1">
            <ArrowDownRight size={11} /> Incoming
          </span>
          <span className="font-mono text-accent-cyan">{incoming}</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-muted flex items-center gap-1">
            <ArrowUpRight size={11} /> Outgoing
          </span>
          <span className="font-mono text-accent-hover">{outgoing}</span>
        </div>
        {data.churn != null && data.churn > 0 && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-muted flex items-center gap-1">
              <Flame size={11} /> Churn
            </span>
            <span
              className="font-mono font-semibold"
              style={{ color: churnColor(data.churn) }}
            >
              {churnLabel(data.churn)}
            </span>
          </div>
        )}
        {data.pagerank != null && data.pagerank > 0 && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-muted flex items-center gap-1">
              <Network size={11} /> Centrality
            </span>
            <span className="font-mono text-text-primary">
              {(data.pagerank * 100).toFixed(2)}%
            </span>
          </div>
        )}
        <div className="pt-1 text-[10px] font-mono text-text-muted break-all leading-relaxed border-t border-border-hairline">
          {node.id}
        </div>
        {data.symbols && data.symbols.length > 0 && (
          <div className="pt-1.5 border-t border-border-hairline">
            <p className="label-caps !text-[10px] mb-1.5">Key symbols</p>
            <div className="flex flex-wrap gap-1">
              {data.symbols.map((s) => (
                <span
                  key={s}
                  className="font-mono text-[10px] px-1.5 py-0.5 rounded border border-border-hairline bg-bg-panel-alt text-text-secondary"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}
        {data.files && data.files.length > 0 && (
          <div className="pt-1.5 border-t border-border-hairline">
            <p className="label-caps !text-[10px] mb-1.5">
              Files ({data.files.length})
            </p>
            <ul className="flex flex-col gap-0.5 max-h-52 overflow-y-auto pr-1">
              {data.files.map((file) => (
                <li key={file}>
                  <button
                    onClick={() => onOpenInEditor?.(file, 1)}
                    className="text-[10px] font-mono text-text-secondary hover:text-accent-cyan
                      transition-colors text-left truncate max-w-full"
                    title={`Open ${file} in your editor`}
                    data-testid="open-folder-file-in-editor"
                  >
                    {groupDir && file.startsWith(`${groupDir}/`) ? file.slice(groupDir.length + 1) : basename(file)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.symbolRefs && data.symbolRefs.length > 0 && data.fullPath && (
          <div className="pt-1.5 border-t border-border-hairline">
            <p className="label-caps !text-[10px] mb-1.5">Symbols</p>
            <ul className="flex flex-col gap-0.5">
              {data.symbolRefs.map((symbol) => (
                <li key={`${symbol.name}:${symbol.line}`}>
                  <button
                    onClick={() =>
                      onOpenInEditor?.(data.fullPath!, symbol.line)
                    }
                    className="text-[10px] font-mono text-text-secondary hover:text-accent-cyan
                      transition-colors text-left truncate max-w-full"
                    title={`Open ${data.fullPath}:${symbol.line} in your editor`}
                    data-testid="open-symbol-in-editor"
                  >
                    {symbol.name}
                    {symbol.line > 0 && (
                      <span className="opacity-60"> : {symbol.line}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Actions */}
      {preview ? (
        <p className="text-[10px] text-text-muted leading-relaxed border-t border-border-hairline pt-2">
          Browser preview. The assistant, impact analysis, and tours need the
          server-side index — run <code className="font-mono">reposcope run .</code>{" "}
          for those.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {data.kind === "file" && data.fullPath && (
            <button
              onClick={() => void onOpenInEditor?.(data.fullPath!, data.line ?? 0)}
              className="btn-secondary w-full !text-xs"
              title={
                localRoot
                  ? `Open ${data.fullPath}${data.line ? `:${data.line}` : ""} in your editor`
                  : "Copy the path — set a workspace root in Settings to open it directly"
              }
              data-testid="open-in-editor"
            >
              <ExternalLink size={12} />
              Open in editor
            </button>
          )}
          <button onClick={() => onAskAbout(data.label)} className="btn-secondary w-full !text-xs">
            <MessageSquare size={12} />
            Ask about this
          </button>
          <button onClick={() => onAnalyzeImpact?.(data.label)} className="btn-primary w-full !text-xs">
            <Zap size={12} />
            Analyze impact
          </button>
          <button onClick={() => onStartTour?.(data.label)} className="btn-secondary w-full !text-xs">
            <MapIcon size={12} />
            Start tour from here
          </button>
        </div>
      )}
    </div>
  );
}

// ── Inner graph component (needs ReactFlowProvider context) ─────────────────
interface InnerProps {
  rawNodes: unknown[];
  rawEdges: unknown[];
  onAskAbout?: (msg: string) => void;
  onAnalyzeImpact?: (label: string) => void;
  onStartTour?: (label: string) => void;
  /** Open a file in the user's editor (Milestone 2.1). */
  onOpenInEditor?: (path: string, line: number) => void;
  /** The absolute path of the repository on this machine, in local mode. */
  localRoot?: string | null;
  repoTitle?: string;
  /** Set when the graph was parsed in the browser, not by the server. */
  previewName?: string;
  highlightNode?: string | null;
  impactTarget?: string | null;
  impactDirect?: string[];
  impactTransitive?: string[];
  tourState?: TourGraphState | null;
}

function GraphInner({
  rawNodes, rawEdges, onAskAbout, onAnalyzeImpact, onStartTour, repoTitle,
  onOpenInEditor, localRoot, previewName,
  highlightNode = null, impactTarget = null,
  impactDirect = [], impactTransitive = [],
  tourState = null,
}: InnerProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selected, setSelected]          = useState<Node | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [expandFuncs, setExpandFuncs]    = useState(true);
  /**
   * Whether the user has chosen the grouping themselves.
   *
   * Until they do, the default follows the SIZE of the repository: nine
   * files read better as nine files, and four hundred read better as
   * sixty directories. Once they choose, their choice is the default
   * forever.
   */
  const groupedTouched = useRef(false);
  const [invert, setInvert]              = useState(false);
  const [legendShown, setLegendShown]    = useState(true);
  // The fit reads the legend through a ref, not through the state
  // directly: putting the state in the callback's dependencies would
  // re-fit the graph every time the legend is toggled, and a user who
  // has panned to somewhere would lose their place.
  const legendShownRef = useRef(legendShown);
  legendShownRef.current = legendShown;
  const [churnShown, setChurnShown]      = useState(false);
  // Architecture-cluster view (Milestone 1.2) — the pyramid collapses to
  // the five canonical layers.
  const [clustered, setClustered]        = useState(false);
  // Churn scores per repo-relative path (Milestone 1.3).
  const [churnScores, setChurnScores]     = useState<Map<string, number>>(new Map());
  const [churnLoading, setChurnLoading]   = useState(false);
  const [churnLoaded, setChurnLoaded]     = useState(false);
  const [exporting, setExporting]        = useState(false);
  const [promptBusy, setPromptBusy]      = useState(false);
  const [reversePrompt, setReversePrompt] = useState<string | null>(null);
  const [scaffoldBusy, setScaffoldBusy]  = useState(false);
  const [scaffold, setScaffold]          = useState<Scaffold | null>(null);
  const { fitView, setCenter, setViewport, getNodes } = useReactFlow();

  /**
   * Fit the graph into the part of the canvas the toolbar does not cover.
   *
   * ReactFlow's own `fitView` centres the content in the raw container,
   * and the toolbar occupies the bottom-left corner. On a narrow graph —
   * the architecture cluster view, for instance — the content lands
   * squarely on top of the toolbar and those nodes become unclickable.
   *
   * An earlier version nudged the viewport after the fit. That traded one
   * defect for another: the content moved up far enough to clip the root
   * node off the top of the canvas.
   *
   * This computes the fit directly instead. The content is fitted into
   * the region ABOVE the toolbar, so the toolbar never covers a node AND
   * the root node is never clipped.
   */
  const fitClearOfToolbar = useCallback((duration = 400) => {
    const container = containerRef.current;
    const nodes = getNodes();
    if (!container || nodes.length === 0) {
      fitView({ ...FIT_VIEW_OPTIONS, duration });
      return;
    }

    const bounds = getNodesBounds(nodes);
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width <= 0 || height <= 0) {
      fitView({ ...FIT_VIEW_OPTIONS, duration });
      return;
    }

    const contentW = Math.max(1, bounds.width);
    const contentH = Math.max(1, bounds.height);

    // The region of the canvas the graph is allowed to occupy: clear of
    // the rank labels on the left, the legend on the right, and the
    // toolbar at the bottom.
    const leftInset = RANK_LABEL_INSET.width;
    const rightInset = legendShownRef.current ? LEGEND_INSET.width : 16;
    const topInset = 12;
    const bottomInset = TOOLBAR_INSET.height;

    const availableW = Math.max(160, width - leftInset - rightInset);
    const availableH = Math.max(120, height - topInset - bottomInset);

    const zoom = Math.min(
      availableW / contentW,
      availableH / contentH,
      FIT_VIEW_OPTIONS.maxZoom,
    );
    if (!Number.isFinite(zoom) || zoom <= 0) {
      fitView({ ...FIT_VIEW_OPTIONS, duration });
      return;
    }

    // Centre the content in the FREE region — not in the raw container.
    const nextX = leftInset + (availableW - contentW * zoom) / 2 - bounds.x * zoom;
    const nextY = topInset + (availableH - contentH * zoom) / 2 - bounds.y * zoom;
    setViewport({ x: nextX, y: nextY, zoom }, { duration });
  }, [fitView, setViewport, getNodes, getNodesBounds]);
  const { zoom } = useViewport();

  // Fit only once the nodes have been MEASURED.
  //
  // `getNodesBounds` uses each node's measured width and height. Before
  // ReactFlow has measured them, the bounds are wrong and the fit lands
  // in the wrong place — which is what clipped the root node off the top
  // of the canvas. `useNodesInitialized` flips exactly when every node
  // has its dimensions, so the fit runs on real geometry.
  const nodesInitialized = useNodesInitialized();
  useEffect(() => {
    if (!nodesInitialized) return;
    fitClearOfToolbar(400);
  }, [nodesInitialized, fitClearOfToolbar]);

  // ── Level-of-detail culling (Milestone 1.4) ─────────────────────────────
  // Below a certain zoom the graph is unreadable in full detail, and
  // rendering every label and every edge is what makes a large graph
  // sluggish. Two thresholds, both in one place so they are easy to tune:
  //   below 0.40 — hide the subtitle line on each node
  //   below 0.25 — hide the edges entirely
  //
  // The culling is done in CSS, driven by one class on the ReactFlow
  // container. Rebuilding the graph on every zoom change would cost a
  // full re-layout; a class change costs nothing.
  const lodLevel = zoom >= 0.4 ? "full" : zoom >= 0.25 ? "compact" : "minimal";
  const containerRef                     = useRef<HTMLDivElement>(null);
  const exportIdRef                      = useRef(0);

  // Hover path highlighting (A9):
  // When a user hovers any node, walk parent chain up to repo node and highlight all edges
  const highlightedEdgeIds = useMemo(() => {
    if (!hoveredNodeId) return new Set<string>();
    const chain = new Set<string>();
    const inEdges = new Map<string, Array<{ id: string; source: string }>>();
    edges.forEach((e) => {
      const list = inEdges.get(e.target) || [];
      list.push({ id: e.id, source: e.source });
      inEdges.set(e.target, list);
    });

    const queue = [hoveredNodeId];
    const visited = new Set<string>([hoveredNodeId]);
    while (queue.length > 0) {
      const curr = queue.shift()!;
      const parents = inEdges.get(curr) || [];
      for (const p of parents) {
        chain.add(p.id);
        if (!visited.has(p.source)) {
          visited.add(p.source);
          queue.push(p.source);
        }
      }
    }
    return chain;
  }, [hoveredNodeId, edges]);

  const renderedEdges = useMemo(() => {
    return edges.map((e) => {
      const isHighlighted = highlightedEdgeIds.has(e.id);
      return {
        ...e,
        className: isHighlighted ? "highlighted" : "",
        style: isHighlighted
          ? { stroke: "#10B981", strokeWidth: 2.5, opacity: 1 }
          : e.style,
        markerEnd: isHighlighted
          ? { type: MarkerType.ArrowClosed, width: 14, height: 14, color: "#10B981" }
          : e.markerEnd,
      };
    });
  }, [edges, highlightedEdgeIds]);

  // Keep a live ref of nodes for resize handling (non-reactive reads)
  const nodesRef = useRef<Node[]>([]);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let timer = 0;
    const ro = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const ns = nodesRef.current;
        if (ns.length === 0) return;
        fitClearOfToolbar(300);
      }, 150);
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      window.clearTimeout(timer);
    };
  }, [fitView]);

  const buildGraph = useCallback((
    rn: unknown[], re: unknown[], name: string, expand: boolean, inv: boolean,
    clusteredOverride?: boolean,
  ) => {
    if (rn.length === 0) { setNodes([]); setEdges([]); return; }
    const useClusters = clusteredOverride ?? clustered;
    const { nodes: pyramid, edges: pe } = useClusters
      ? buildClusterGraph(rn, re, name)
      : buildPyramidGraph(rn, re, name, expand, inv, churnScores);
    setNodes(pyramid);
    setEdges(pe);
    setSelected(null);
    setTimeout(() => {
      fitClearOfToolbar(400);
    }, 50);
  }, [fitView, setNodes, setEdges, churnScores, clustered]);

  useEffect(() => {
    buildGraph(rawNodes, rawEdges, repoTitle ?? "Repository", expandFuncs, invert);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawNodes, rawEdges, repoTitle, expandFuncs]);

  // ── Churn heatmap (Milestone 1.3) ────────────────────────────────────────
  // The churn metrics come from `git log --numstat`, which is not free on
  // a large repository — so they are fetched the first time the user
  // turns the overlay on, not on every graph load.
  const toggleChurn = useCallback(() => {
    const next = !churnShown;
    setChurnShown(next);
    if (!next || churnLoaded || churnLoading) return;

    setChurnLoading(true);
    getHotspots(90)
      .then((response) => {
        if (!response.available) return;
        const scores = new Map<string, number>();
        for (const entry of response.files) {
          scores.set(entry.path, entry.hotspot_score);
        }
        setChurnScores(scores);
        setChurnLoaded(true);
      })
      .catch(() => {
        // The overlay simply stays off — a failed metrics call must never
        // break the graph.
      })
      .finally(() => setChurnLoading(false));
  }, [churnShown, churnLoaded, churnLoading]);

  // Rebuild once the churn scores arrive, so the rings appear.
  useEffect(() => {
    if (churnScores.size === 0) return;
    buildGraph(rawNodes, rawEdges, repoTitle ?? "Repository", expandFuncs, invert);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [churnScores]);

  // The default view follows the size of the repository.
  //
  // A small repository reads better as a flat list of files — grouping
  // nine files into one folder hides everything the map exists to show.
  // A large one reads better grouped: 450 files is a wall of dots, and
  // 60 directories is a map you can actually look at.
  useEffect(() => {
    if (groupedTouched.current) return;
    const fileCount = rawNodes.filter(
      (n) => (n as RawNode)?.type === "file",
    ).length;
    const wanted = fileCount > GROUPING_THRESHOLD;
    setExpandFuncs((v) => (v === wanted ? v : wanted));
  }, [rawNodes]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelected(node);
  }, []);

  const relayout = useCallback(() => {
    buildGraph(rawNodes, rawEdges, repoTitle ?? "Repository", expandFuncs, invert);
  }, [rawNodes, rawEdges, repoTitle, expandFuncs, invert, buildGraph]);

  const toggleDirection = useCallback(() => {
    setInvert((v) => {
      buildGraph(rawNodes, rawEdges, repoTitle ?? "Repository", expandFuncs, !v);
      return !v;
    });
  }, [rawNodes, rawEdges, repoTitle, expandFuncs, buildGraph]);

  const toggleGrouped = useCallback(() => {
    // The graph is rebuilt by the effect that watches `expandFuncs`, so
    // the toggle and the rebuild can never disagree about what is drawn.
    groupedTouched.current = true;
    setExpandFuncs((v) => !v);
  }, []);

  // Switch between the file pyramid and the architecture-cluster view.
  const toggleClustered = useCallback(() => {
    const next = !clustered;
    setClustered(next);
    buildGraph(
      rawNodes, rawEdges, repoTitle ?? "Repository", expandFuncs, invert, next,
    );
  }, [clustered, rawNodes, rawEdges, repoTitle, expandFuncs, invert, buildGraph]);

  // Focus mode — center the highlighted (tour/impact) or selected node
  const focusNode = useCallback(() => {
    const targetId = highlightNode ?? impactTarget ?? selected?.id;
    const n = nodes.find((nd) => nd.id === targetId) ?? selected;
    if (!n) {
      fitView({ padding: 0.2, duration: 400 });
      return;
    }
    setCenter(
      n.position.x + NODE_W / 2,
      n.position.y + NODE_H / 2,
      { zoom: 1.2, duration: 500 }
    );
  }, [highlightNode, impactTarget, selected, nodes, fitView, setCenter]);

  // ── Highlight styling: impact states + tour badges, via node data ──
  const hasImpact = Boolean(impactTarget || impactDirect.length || impactTransitive.length);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === "cluster" || n.type === "rankLabel") return n;
        const d = n.data as LayerNodeData;
        let impactState: LayerNodeData["impactState"] | undefined;
        if (impactTarget && n.id === impactTarget)       impactState = "target";
        else if (impactDirect.includes(n.id))            impactState = "direct";
        else if (impactTransitive.includes(n.id))        impactState = "transitive";
        else if (hasImpact)                              impactState = "dim";
        const isCurrent = tourState != null && n.id === tourState.currentNodeId;
        const stepBadge = isCurrent ? (tourState!.step + 1) : undefined;
        const pastStep = tourState != null && tourState.pastNodeIds.includes(n.id);
        const highlight = (!hasImpact && highlightNode === n.id) || isCurrent;
        if (
          impactState === d.impactState &&
          highlight === Boolean(d.highlight) &&
          stepBadge === d.stepBadge &&
          pastStep === Boolean(d.pastStep)
        ) return n;
        return { ...n, data: { ...d, impactState, highlight, stepBadge, pastStep } };
      })
    );
  }, [highlightNode, impactTarget, impactDirect, impactTransitive, hasImpact, tourState, setNodes]);

  // ── Camera follows the current tour stop ──────────────────────────────────
  useEffect(() => {
    if (!highlightNode) return;
    const n = nodes.find((nd) => nd.id === highlightNode);
    if (!n) return;
    setCenter(
      n.position.x + NODE_W / 2,
      n.position.y + NODE_H / 2,
      { zoom: 1.1, duration: 500 }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightNode]);

  // ── Export PNG / SVG (race-guarded) ────────────────────────────────────────
  const runExport = useCallback(async (kind: "png" | "svg") => {
    const el = containerRef.current;
    if (!el || exporting) return;
    const id = ++exportIdRef.current;
    setExporting(true);
    try {
      if (kind === "png") await exportGraphPng(el, repoTitle, CANVAS_BG);
      else await exportGraphSvg(el, repoTitle, CANVAS_BG);
      if (id !== exportIdRef.current) return;
      toast.success(`Graph exported as ${kind.toUpperCase()}`);
    } catch (e: unknown) {
      if (id !== exportIdRef.current) return;
      const msg = e instanceof Error ? e.message : "Export failed";
      toast.error(msg);
    } finally {
      if (id === exportIdRef.current) setExporting(false);
    }
  }, [exporting, repoTitle]);

  // ── Reverse Build Prompt (GitReverse) ──────────────────────────────────────
  const runReversePrompt = useCallback(async () => {
    if (promptBusy) return;
    const id = ++exportIdRef.current;
    setPromptBusy(true);
    try {
      const { prompt } = await generateReversePrompt();
      if (id !== exportIdRef.current) return;
      setReversePrompt(prompt);
    } catch (e: unknown) {
      if (id !== exportIdRef.current) return;
      const msg = e instanceof Error ? e.message : "Failed to generate build prompt";
      toast.error(msg);
    } finally {
      if (id === exportIdRef.current) setPromptBusy(false);
    }
  }, [promptBusy]);

  // ── Scaffold (CodeCrafters-style starter) ──────────────────────────────────
  const runScaffold = useCallback(async () => {
    if (scaffoldBusy) return;
    const id = ++exportIdRef.current;
    setScaffoldBusy(true);
    try {
      const data = await generateScaffold();
      if (id !== exportIdRef.current) return;
      setReversePrompt(null);      // close the prompt modal if it was open
      setScaffold(data);
      toast.success(`Scaffold ready — ${data.files.length} files`);
    } catch (e: unknown) {
      if (id !== exportIdRef.current) return;
      const msg = e instanceof Error ? e.message : "Failed to generate scaffold";
      toast.error(msg);
    } finally {
      if (id === exportIdRef.current) setScaffoldBusy(false);
    }
  }, [scaffoldBusy]);

  const minimapColor = useMemo(() => {
    return (n: Node) => {
      const d = n.data as LayerNodeData;
      if (d.kind === "root") return "#141414";
      if (d.child) return "#D4AF37";
      // The fill colours are intentionally pale (they carry the card's
      // background). A pale minimap on a pale canvas is invisible, so the
      // miniature uses the saturated layer border instead.
      return LAYER_STYLE[d.layer]?.border ?? "#A8A29E";
    };
  }, []);

  if (nodes.length === 0) return <EmptyState />;

  // The legend and the node drawer both sit at `absolute top-4 right-4`,
  // so an open drawer painted over the legend and cut it in half. The
  // drawer is the focus while a node is selected, so the legend yields and
  // returns when the drawer closes.
  const legendVisible = legendShown && !selected;

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative"
      style={{ background: CANVAS_BG }}
    >
      {/* Title — fixed top-left (FILE 3) */}
      <div className="graph-title absolute top-4 left-4 z-[5] pointer-events-none">
        <h2 className="text-sm font-extrabold tracking-[-0.01em] text-text-primary">
          {repoTitle ?? "Repository"} <span className="text-text-muted font-semibold">· Architecture</span>
        </h2>
        {previewName && (
          <span
            className="mt-1 inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider
              px-1.5 py-0.5 rounded border border-accent-amber/40 text-accent-amber bg-bg-panel/80"
            title="This graph was parsed in the browser. The assistant and tracking still refer to the server-loaded repository."
          >
            Browser preview · {previewName}
          </span>
        )}
      </div>

      <Legend visible={legendVisible} churn={churnShown} />

      {/* Tour progress bar — top of the graph (4.5) */}
      {tourState && tourState.total > 0 && (
        <div className="absolute top-0 left-0 right-0 h-2 z-20 bg-black/10" aria-hidden="true">
          <div
            className="h-full bg-accent-cyan border-r-2 border-border-subtle transition-all duration-300"
            style={{ width: `${((tourState.step + 1) / tourState.total) * 100}%` }}
          />
        </div>
      )}

      {/* Impact state legend — bottom-center (4.4) */}
      {hasImpact && (
        <div className="
          graph-impact-legend
          absolute bottom-4 left-1/2 -translate-x-1/2 z-10
          card-flat !border-border-hairline px-3 py-2
          flex items-center gap-4 pointer-events-none
        ">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-bg-panel-alt" style={{ boxShadow: "0 0 0 2px #F0503C" }} />
            <span className="text-[11px] font-medium text-text-secondary">Target</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-bg-panel-alt" style={{ boxShadow: "0 0 0 2px #D97706" }} />
            <span className="text-[11px] font-medium text-text-secondary">Direct</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-bg-panel-alt" style={{ boxShadow: "0 0 0 2px rgba(217,119,6,0.55)" }} />
            <span className="text-[11px] font-medium text-text-secondary">Transitive</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm bg-bg-panel-alt opacity-25" />
            <span className="text-[11px] font-medium text-text-secondary">Unaffected</span>
          </span>
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={renderedEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        className={`lod-${lodLevel}`}
        onNodeClick={onNodeClick}
        onPaneClick={() => setSelected(null)}
        onNodeMouseEnter={(_, node) => {
          if (node.type !== "rankLabel") setHoveredNodeId(node.id);
        }}
        onNodeMouseLeave={() => setHoveredNodeId(null)}
        fitView
        fitViewOptions={FIT_VIEW_OPTIONS}
        minZoom={0.2}
        maxZoom={2}
        connectionLineType={ConnectionLineType.SmoothStep}
        defaultEdgeOptions={{
          type: "smoothstep",
          ...({ sourceHandle: "out", targetHandle: "in" } as object),
        }}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        onlyRenderVisibleElements
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color={DOT_COLOR}
        />
        <MiniMap
          position="bottom-right"
          style={{
            width: 176,
            height: 112,
            background: "#F6F2E8",
            border: "1px solid #E2DCCB",
            borderRadius: 10,
            boxShadow: "0 2px 10px rgba(28, 25, 20, 0.06)",
          }}
          nodeColor={minimapColor}
          maskColor="rgba(246, 242, 232, 0.55)"
          nodeStrokeWidth={0}
          pannable
          zoomable
        />
      </ReactFlow>

      {/* Floating graph toolbar — bottom-left per FILE 3 */}
      <GraphControls
        onRelayout={relayout}
        onToggleDirection={toggleDirection}
        onToggleGroup={toggleGrouped}
        onToggleLegend={() => setLegendShown((v) => !v)}
        onToggleChurn={toggleChurn}
        onToggleClustered={toggleClustered}
        clustered={clustered}
        onFocus={focusNode}
        onExportPng={() => void runExport("png")}
        onExportSvg={() => void runExport("svg")}
        onReversePrompt={() => void runReversePrompt()}
        onScaffold={() => void runScaffold()}
        direction={invert ? "LR" : "TB"}
        grouped={expandFuncs}
        legendShown={legendShown}
        churnShown={churnShown}
        exporting={exporting}
        promptBusy={promptBusy}
        scaffoldBusy={scaffoldBusy}
      />

      {/* Reverse Build Prompt modal */}
      <ReversePromptModal
        open={reversePrompt != null}
        prompt={reversePrompt ?? ""}
        onClose={() => setReversePrompt(null)}
        onScaffold={() => void runScaffold()}
      />

      {/* Scaffold modal */}
      <ScaffoldModal
        open={scaffold != null}
        scaffold={scaffold}
        onClose={() => setScaffold(null)}
      />

      {/* Node drawer */}
      {selected && (
        <NodeDrawer
          node={selected}
          edges={edges}
          onClose={() => setSelected(null)}
          onAskAbout={(label) => {
            setSelected(null);
            onAskAbout?.(`Tell me about "${label}" in this codebase.`);
          }}
          onAnalyzeImpact={(label) => {
            setSelected(null);
            onAnalyzeImpact?.(label);
          }}
          onStartTour={(label) => {
            setSelected(null);
            onStartTour?.(label);
          }}
          onOpenInEditor={onOpenInEditor}
          localRoot={localRoot}
          preview={Boolean(previewName)}
        />
      )}
    </div>
  );
}

// ── Public component (wraps with provider) ──────────────────────────────────
interface Props {
  rawNodes: unknown[];
  rawEdges: unknown[];
  onAskAbout?: (msg: string) => void;
  onAnalyzeImpact?: (label: string) => void;
  onStartTour?: (label: string) => void;
  /** Open a file in the user's editor (Milestone 2.1). */
  onOpenInEditor?: (path: string, line: number) => void;
  /** The absolute path of the repository on this machine, in local mode. */
  localRoot?: string | null;
  repoTitle?: string;
  /** Set when the graph was parsed in the browser, not by the server. */
  previewName?: string;
  highlightNode?: string | null;
  impactTarget?: string | null;
  impactDirect?: string[];
  impactTransitive?: string[];
  tourState?: TourGraphState | null;
}

export default function GraphCanvas({
  rawNodes, rawEdges, onAskAbout, onAnalyzeImpact, onStartTour, repoTitle,
  onOpenInEditor, localRoot, previewName,
  highlightNode, impactTarget, impactDirect, impactTransitive, tourState,
}: Props) {
  return (
    <ReactFlowProvider>
      <GraphInner
        rawNodes={rawNodes}
        rawEdges={rawEdges}
        onAskAbout={onAskAbout}
        onAnalyzeImpact={onAnalyzeImpact}
        onStartTour={onStartTour}
        onOpenInEditor={onOpenInEditor}
        localRoot={localRoot}
        previewName={previewName}
        repoTitle={repoTitle}
        highlightNode={highlightNode}
        impactTarget={impactTarget}
        impactDirect={impactDirect}
        impactTransitive={impactTransitive}
        tourState={tourState}
      />
    </ReactFlowProvider>
  );
}
