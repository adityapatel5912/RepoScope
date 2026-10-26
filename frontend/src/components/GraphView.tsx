import ReactFlow, {
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  getNodesBounds,
  type Node,
  type Edge,
  type NodeTypes,
  MarkerType,
} from "reactflow";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X, MessageSquare, ArrowUpRight, ArrowDownRight, Zap, Map as MapIcon } from "lucide-react";
import LayerNode, { NODE_W, NODE_H, CHILD_W, type LayerNodeData } from "./graph/LayerNode";import { classify, LAYER_STYLE, type Layer } from "./graph/layerClassifier";
import EmptyState from "./EmptyState";
import GraphControls from "./GraphControls";
import ReversePromptModal from "./ReversePromptModal";
import { exportGraphPng, exportGraphSvg } from "../utils/graphExport";
import { generateReversePrompt } from "../api/features";
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

// ── Node type registrations (all types render through LayerNode) ────────────
const nodeTypes: NodeTypes = {
  root:     LayerNode,
  folder:   LayerNode,
  file:     LayerNode,
  function: LayerNode,
  class:    LayerNode,
  import:   LayerNode,
  commit:   LayerNode,
  repo:     LayerNode,
};

// ── Canvas palette (FILE 3: lavender-white + faint dotted grid) ─────────────
const CANVAS_BG    = "#ECE9F5";
const DOT_COLOR    = "#CDC6E0";
const EDGE_COLOR   = "#57534E";

// ── Pyramid layout constants (no dagre — deterministic manual layout) ───────
// Pitches sized so adjacent nodes keep a positive gutter even before the
// collision pass (NODE_GAP_X − NODE_W, CHILD_GAP_X − CHILD_W > 0).
const NODE_GAP_X   = 300;           // horizontal pitch between file nodes
const RANK_GAP_Y   = 220;           // vertical pitch between rank slots
const CHILD_GAP_X  = 220;           // pitch between expanded function children
const CHILD_DY     = RANK_GAP_Y / 2; // child row at half-rank — clear of both neighbours
const MAX_PER_ROW  = 18;            // wrap ranks wider than this into continuation slots
const MIN_CLEAR_X  = 24;            // minimum gutter enforced by the collision pass

interface RawNode {
  id: string;
  type: string;
  label: string;
  line?: number;
  file?: string;
}

function basename(p: string): string {
  const parts = p.split("/");
  return parts[parts.length - 1] || p;
}

// ── Connectivity scoring (Section 3): incoming ×2 + outgoing ────────────────
function scoreNode(nodeId: string, importEdges: Array<{ source: string; target: string }>): number {
  let incoming = 0;
  let outgoing = 0;
  for (const e of importEdges) {
    if (e.target === nodeId) incoming += 1;
    else if (e.source === nodeId) outgoing += 1;
  }
  return incoming * 2 + outgoing;
}

// Path-based fallback when a file has no import edges at all.
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

/**
 * Pyramid layout (Section 6): repo at the top, files bucketed into five
 * connectivity-ranked rows (widest at the bottom), key functions expanded as
 * smaller child nodes directly under their parent file. No dagre.
 */
function buildPyramidGraph(
  raw: unknown[],
  rawEdges: unknown[],
  repoTitle: string,
  expandFuncs: boolean,
  invert: boolean,
): { nodes: Node[]; edges: Edge[] } {
  const rn = raw as RawNode[];
  if (rn.length === 0) return { nodes: [], edges: [] };

  const fileNodes = rn.filter((n) => n.type === "file");
  const symbolNodes = rn.filter((n) => n.type === "function" || n.type === "class");
  // Real backend edges (imports/calls) — drive ranking AND rendering.
  const edgeList = (rawEdges as Array<{ source: string; target: string; type?: string }>)
    .filter((e) => typeof e?.source === "string" && typeof e?.target === "string");
  const importEdges = edgeList.filter((e) => e.type === "imports" || e.type === "calls");

  // Dev-only EDGE DIAG plumbing check (stripped from production builds).
  log(
    `[EDGE DIAG] nodes: ${rn.length} · edges in: ${edgeList.length} · ` +
    `matching IDs: ${edgeList.filter((e) =>
      rn.some((n) => n.id === e.source) && rn.some((n) => n.id === e.target),
    ).length}`,
  );

  // Symbols grouped by parent file id
  const symbolsByFile = new Map<string, RawNode[]>();
  for (const s of symbolNodes) {
    const parent = s.file ? `file:${s.file}` : "";
    if (!parent) continue;
    const list = symbolsByFile.get(parent) ?? [];
    list.push(s);
    symbolsByFile.set(parent, list);
  }

  // Score + sort files: connectivity desc, then alphabetical
  const scored = fileNodes
    .map((n) => ({ node: n, score: scoreNode(n.id, importEdges) || fallbackScore(String(n.label)) }))
    .sort((a, b) => (b.score !== a.score ? b.score - a.score : a.node.id.localeCompare(b.node.id)));

  // Five buckets (rank 1..5) — rank 0 is the repo node
  const total = scored.length;
  const r1 = Math.min(6, Math.ceil(total * 0.05));
  const r2 = Math.min(12, Math.ceil(total * 0.10));
  const r3 = Math.min(20, Math.ceil(total * 0.15));
  const r4 = Math.min(30, Math.ceil(total * 0.20));
  const buckets: Array<typeof scored> = [
    scored.slice(0, r1),
    scored.slice(r1, r1 + r2),
    scored.slice(r1 + r2, r1 + r2 + r3),
    scored.slice(r1 + r2 + r3, r1 + r2 + r3 + r4),
    scored.slice(r1 + r2 + r3 + r4),
  ].filter((b) => b.length > 0);

  // Wrap each bucket into slots of ≤ MAX_PER_ROW so no row gets absurdly wide
  const slots: Array<typeof scored> = [];
  for (const bucket of buckets) {
    for (let i = 0; i < bucket.length; i += MAX_PER_ROW) {
      slots.push(bucket.slice(i, i + MAX_PER_ROW));
    }
  }
  if (invert) slots.reverse();

  const widest = Math.max(...slots.map((s) => s.length), 1);
  const centerX = (widest * NODE_GAP_X) / 2;

  const out: Node[] = [];
  const placedIds = new Set<string>();

  // Rank 0 — repo node, always at the very top
  out.push({
    id: "repo:root",
    type: "root",
    position: { x: centerX - NODE_W / 2, y: 0 },
    data: { label: repoTitle, kind: "root", layer: classify("repo:root", repoTitle) } satisfies LayerNodeData,
  });
  placedIds.add("repo:root");

  const mkFile = (n: RawNode): Node => ({
    id: String(n.id),
    type: "file",
    position: { x: 0, y: 0 },
    data: {
      label: basename(String(n.label)),
      kind: "file",
      layer: classify(String(n.id), String(n.label)),
      subtitle: String(n.label),
    } satisfies LayerNodeData,
  });

  // Ranks 1..5 — file rows, expanding key symbols under core modules
  slots.forEach((slot, slotIdx) => {
    const rowY = (slotIdx + 1) * RANK_GAP_Y;
    const rowWidth = slot.length * NODE_GAP_X;
    const startX = centerX - rowWidth / 2 + NODE_GAP_X / 2;

    slot.forEach((item, i) => {
      const x = startX + i * NODE_GAP_X;
      const node = mkFile(item.node);
      node.position = { x, y: rowY };
      out.push(node);
      placedIds.add(node.id);

      // Expand key functions of core modules (ranks 1–2) as child nodes
      const isCore = slotIdx < 2 || (invert && slotIdx >= slots.length - 2);
      if (expandFuncs && isCore) {
        const children = (symbolsByFile.get(item.node.id) ?? [])
          .slice()
          .sort((a, b) => a.label.localeCompare(b.label))
          .slice(0, 4);
        const childStartX = x - ((children.length - 1) * CHILD_GAP_X) / 2;
        children.forEach((child, ci) => {
          const isClass = child.type === "class";
          out.push({
            id: String(child.id),
            type: child.type,
            position: { x: childStartX + ci * CHILD_GAP_X, y: rowY + CHILD_DY },
            data: {
              label: String(child.label),
              kind: isClass ? "class" : "function",
              layer: classify(String(child.id), String(child.label)),
              child: true,
            } satisfies LayerNodeData,
          });
          placedIds.add(String(child.id));
        });
      }
    });
  });

  // Keep only real edges whose endpoints were placed
  const validEdges = edgeList.filter(
    (e) => placedIds.has(e.source) && placedIds.has(e.target) && e.source !== e.target,
  );

  // Synthesized containment edges: repo root → first visual row. The backend
  // graph deliberately carries no structural dir/repo edges (they would pollute
  // the impact analyzer's reverse-BFS), so the layout adds rank-0 connectivity
  // at render time.
  for (const item of slots[0] ?? []) {
    const target = String(item.node.id);
    if (placedIds.has(target)) {
      validEdges.push({ source: "repo:root", target, type: "groups" });
    }
  }

  const edges: Edge[] = validEdges.slice(0, 1000).map((e, i) => ({
    id: `e${i}`,
    source: e.source,
    target: e.target,
    type: "smoothstep",
    data: { type: e.type },
    pathOptions: { borderRadius: 10 },
    style: { stroke: EDGE_COLOR, strokeWidth: 1.5 },
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: EDGE_COLOR },
  }));

  return { nodes: fixOverlaps(out), edges };
}

/**
 * Collision pass (Section 2): sweep every row left→right and enforce a minimum
 * center-to-center gutter so no two nodes can overlap. Uses real node widths
 * (file vs. child cards), so the result is deterministic — a hashed-grid nudge
 * can miss pairs that land in different cells.
 */
function fixOverlaps(nodes: Node[]): Node[] {
  const widthOf = (n: Node) => ((n.data as LayerNodeData).child ? CHILD_W : NODE_W);
  const byRow = new Map<number, Node[]>();
  for (const n of nodes) {
    const row = byRow.get(n.position.y);
    if (row) row.push(n);
    else byRow.set(n.position.y, [n]);
  }
  for (const row of byRow.values()) {
    row.sort((a, b) => a.position.x - b.position.x);
    for (let i = 1; i < row.length; i++) {
      const prev = row[i - 1];
      const minDist = (widthOf(prev) + widthOf(row[i])) / 2 + MIN_CLEAR_X;
      if (row[i].position.x - prev.position.x < minDist) {
        row[i].position = { ...row[i].position, x: prev.position.x + minDist };
      }
    }
  }
  return nodes;
}

// ── Legend (FILE 3: top-right, white card, one swatch per layer) ────────────
function Legend({ visible }: { visible: boolean }) {
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
    </div>
  );
}

// ── Node detail drawer ──────────────────────────────────────────────────────
interface NodeDrawerProps {
  node: Node;
  edges: Edge[];
  onClose: () => void;
  onAskAbout: (label: string) => void;
  onAnalyzeImpact?: (label: string) => void;
  onStartTour?: (label: string) => void;
}

function NodeDrawer({
  node, edges, onClose, onAskAbout, onAnalyzeImpact, onStartTour,
}: NodeDrawerProps) {
  const data = node.data as LayerNodeData;
  const style = LAYER_STYLE[data.layer];
  const incoming = edges.filter((e) => e.target === node.id).length;
  const outgoing = edges.filter((e) => e.source === node.id).length;

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
        <div className="pt-1 text-[10px] font-mono text-text-muted break-all leading-relaxed border-t border-border-hairline">
          {node.id}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2">
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
  repoTitle?: string;
  highlightNode?: string | null;
  impactTarget?: string | null;
  impactDirect?: string[];
  impactTransitive?: string[];
  tourState?: TourGraphState | null;
}

function GraphInner({
  rawNodes, rawEdges, onAskAbout, onAnalyzeImpact, onStartTour, repoTitle,
  highlightNode = null, impactTarget = null,
  impactDirect = [], impactTransitive = [],
  tourState = null,
}: InnerProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selected, setSelected]          = useState<Node | null>(null);
  const [expandFuncs, setExpandFuncs]    = useState(true);
  const [invert, setInvert]              = useState(false);
  const [legendShown, setLegendShown]    = useState(true);
  const [exporting, setExporting]        = useState(false);
  const [promptBusy, setPromptBusy]      = useState(false);
  const [reversePrompt, setReversePrompt] = useState<string | null>(null);
  const { fitView, setCenter }           = useReactFlow();
  const containerRef                     = useRef<HTMLDivElement>(null);
  const exportIdRef                      = useRef(0);
  // Camera plumbing: setCenter can fire before ReactFlow finishes init, so
  // the requested camera is stashed and flushed from onInit if needed.
  const rfInstanceRef                    = useRef<unknown>(null);
  const pendingCameraRef                 = useRef<{ x: number; y: number; zoom: number } | null>(null);

  const applyCamera = useCallback((x: number, y: number, zoom: number, duration = 600) => {
    pendingCameraRef.current = { x, y, zoom };
    if (rfInstanceRef.current) {
      setCenter(x, y, { zoom, duration });
      pendingCameraRef.current = null;
    }
  }, [setCenter]);

  // Keep a live ref of nodes for resize handling (non-reactive reads)
  const nodesRef = useRef<Node[]>([]);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);

  // Re-fit the view when the container resizes (panel drag / collapse) —
  // but ONLY when the graph still fits at a readable zoom. Huge graphs
  // would zoom out to a thin horizontal strip, destroying the user's
  // camera; in that case we leave the viewport exactly where it is.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let timer = 0;
    const ro = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const ns = nodesRef.current;
        if (ns.length === 0) return;
        const bounds = getNodesBounds(ns);
        const pad = 1.4; // 0.2 padding each side ⇒ ~1.4× content box
        const fitZoom = Math.min(
          el.clientWidth / (bounds.width * pad),
          el.clientHeight / (bounds.height * pad),
          0.9,
        );
        // Below ~0.3 the graph becomes unreadable — keep the camera instead.
        if (fitZoom >= 0.3) {
          fitView({ padding: 0.2, maxZoom: 0.9, duration: 300 });
        }
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
  ) => {
    if (rn.length === 0) { setNodes([]); setEdges([]); return; }
    const { nodes: pyramid, edges: pe } = buildPyramidGraph(rn, re, name, expand, inv);
    setNodes(pyramid);
    setEdges(pe);
    setSelected(null);
    setTimeout(() => {
      // Center on the repo root at a readable zoom — the full pyramid is
      // wider than the viewport; "Fit view" shows the whole shape.
      const root = pyramid.find((n) => n.id === "repo:root");
      if (root) {
        applyCamera(root.position.x + NODE_W / 2, root.position.y + NODE_H / 2 + 140, 0.85);
      } else {
        fitView({ padding: 0.2, duration: 600 });
      }
    }, 50);
  }, [fitView, setNodes, setEdges, setCenter, applyCamera]);

  useEffect(() => {
    buildGraph(rawNodes, rawEdges, repoTitle ?? "Repository", expandFuncs, invert);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawNodes, rawEdges, repoTitle]);

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
    setExpandFuncs((v) => {
      buildGraph(rawNodes, rawEdges, repoTitle ?? "Repository", !v, invert);
      return !v;
    });
  }, [rawNodes, rawEdges, repoTitle, invert, buildGraph]);

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
        if (n.type === "cluster") return n;
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

  const minimapColor = useMemo(() => {
    return (n: Node) => {
      const d = n.data as LayerNodeData;
      if (d.kind === "root") return "#141414";
      if (d.child) return "#D4AF37";
      return LAYER_STYLE[d.layer]?.fill ?? "#DDD7C8";
    };
  }, []);

  if (nodes.length === 0) return <EmptyState />;

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
      </div>

      <Legend visible={legendShown} />

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
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        onPaneClick={() => setSelected(null)}
        onInit={(instance) => {
          rfInstanceRef.current = instance;
          const pending = pendingCameraRef.current;
          if (pending) {
            setCenter(pending.x, pending.y, { zoom: pending.zoom, duration: 400 });
            pendingCameraRef.current = null;
          }
        }}
        // No `fitView` prop: the camera is owned by buildGraph (root-centered
        // at readable zoom) + manual controls. The internal init-fit would
        // collapse the pyramid into a strip.
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{ type: "smoothstep" }}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        onlyRenderVisibleElements
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={22}
          size={1.3}
          color={DOT_COLOR}
        />
        <MiniMap
          position="bottom-right"
          style={{ width: 200, height: 140 }}
          nodeColor={minimapColor}
          maskColor="rgba(236,233,245,0.8)"
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
        onFocus={focusNode}
        onExportPng={() => void runExport("png")}
        onExportSvg={() => void runExport("svg")}
        onReversePrompt={() => void runReversePrompt()}
        direction={invert ? "LR" : "TB"}
        grouped={expandFuncs}
        legendShown={legendShown}
        exporting={exporting}
        promptBusy={promptBusy}
      />

      {/* Reverse Build Prompt modal */}
      <ReversePromptModal
        open={reversePrompt != null}
        prompt={reversePrompt ?? ""}
        onClose={() => setReversePrompt(null)}
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
  repoTitle?: string;
  highlightNode?: string | null;
  impactTarget?: string | null;
  impactDirect?: string[];
  impactTransitive?: string[];
  tourState?: TourGraphState | null;
}

export default function GraphCanvas({
  rawNodes, rawEdges, onAskAbout, onAnalyzeImpact, onStartTour, repoTitle,
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
