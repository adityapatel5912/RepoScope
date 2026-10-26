import { memo } from "react";
import { Handle, Position } from "reactflow";
import { Monitor, Server, Database, Globe, Cpu, FileCode2, Folder, Boxes, type LucideIcon } from "lucide-react";
import { LAYER_STYLE, type Layer } from "./layerClassifier";

export interface LayerNodeData {
  label: string;
  kind: "root" | "folder" | "file" | "function" | "class" | "import" | "commit" | "repo";
  layer: Layer;
  rank?: number;
  fullPath?: string;
  subtitle?: string;         // file path or role — muted mono line
  line?: number;
  size?: number;             // file size in bytes (files only) — shown in the drawer
  symbols?: string[];        // key function/class names (files only) — shown in the drawer
  child?: boolean;           // expanded function/class child — small card
  // Impact analysis state (FILE 3 emphasis language)
  impactState?: "target" | "direct" | "transitive" | "dim";
  // Tour / generic highlight
  highlight?: boolean;
  stepBadge?: number;        // 1-based number for the current tour step
  pastStep?: boolean;
}

export interface RankConfig {
  width: number;
  height: number;
  fontSize: number;
  fontWeight: number | string;
  borderRadius: number;
  borderWidth: number;
  fill?: string;
  border?: string;
  text?: string;
}

export const RANK_CONFIGS: Record<number, RankConfig> = {
  0: { width: 320, height: 80, fontSize: 18, fontWeight: 700, borderRadius: 16, borderWidth: 1, fill: "#1A1A1A", border: "#1A1A1A", text: "#FFFFFF" },
  1: { width: 260, height: 72, fontSize: 14, fontWeight: 700, borderRadius: 12, borderWidth: 2 },
  2: { width: 240, height: 64, fontSize: 13, fontWeight: 700, borderRadius: 10, borderWidth: 1.5 },
  3: { width: 220, height: 58, fontSize: 12, fontWeight: 500, borderRadius: 10, borderWidth: 1 },
  4: { width: 200, height: 52, fontSize: 11, fontWeight: 500, borderRadius: 8, borderWidth: 1 },
  5: { width: 180, height: 46, fontSize: 11, fontWeight: 400, borderRadius: 8, borderWidth: 1 },
  6: { width: 160, height: 40, fontSize: 10, fontWeight: 400, borderRadius: 8, borderWidth: 1, fill: "#F1F5F9", border: "#CBD5E1", text: "#64748B" },
};

export const NODE_W = 240;
export const NODE_H = 68;
export const CHILD_W = 200;
export const CHILD_H = 48;

const LAYER_ICONS: Record<Layer, LucideIcon> = {
  client: Monitor,
  backend: Server,
  storage: Database,
  external: Globe,
  compute: Cpu,
};

const KIND_ICONS: Partial<Record<LayerNodeData["kind"], LucideIcon>> = {
  root: Boxes,
  folder: Folder,
  file: FileCode2,
};

function splitFilePath(fullPath: string, label: string) {
  const p = fullPath || label || "";
  const lastSlash = p.lastIndexOf("/");
  let dir = "";
  let filename = p;
  if (lastSlash >= 0) {
    dir = p.slice(0, lastSlash);
    filename = p.slice(lastSlash + 1);
  }

  // If total length exceeds 30 characters, show only the filename with ellipsis. Never truncate the extension.
  let displayFilename = filename;
  if (p.length > 30) {
    const dotIdx = filename.lastIndexOf(".");
    if (dotIdx > 0) {
      const ext = filename.slice(dotIdx);
      const base = filename.slice(0, dotIdx);
      const maxBase = Math.max(6, 18 - ext.length);
      displayFilename = base.length > maxBase ? `${base.slice(0, maxBase)}…${ext}` : filename;
    } else {
      displayFilename = filename.length > 18 ? `${filename.slice(0, 16)}…` : filename;
    }
  }

  return { dir, filename: displayFilename, fullPath: p };
}

function LayerNodeInner({ data, selected, rank: propRank }: { data: LayerNodeData; selected?: boolean; rank?: number }) {
  const rank = propRank ?? data.rank ?? (data.kind === "root" || data.kind === "repo" ? 0 : 2);
  const cfg = RANK_CONFIGS[rank] ?? RANK_CONFIGS[2];
  const style = LAYER_STYLE[data.layer];
  const Icon = KIND_ICONS[data.kind] ?? LAYER_ICONS[data.layer];
  const isRoot = rank === 0 || data.kind === "root" || data.kind === "repo";
  const isChild = Boolean(data.child);
  const isFunctionChild = isChild && data.kind === "function";
  const isClassChild = isChild && data.kind === "class";
  const isFolder = data.kind === "folder";

  // Per-kind fills
  let fill = cfg.fill ?? style.fill;
  let border = cfg.border ?? style.border;
  let textColor = cfg.text ?? style.text;
  let subColor = rank === 6 ? "#94A3B8" : "#64748B";

  if (isRoot) {
    fill = "#1A1A1A";
    border = "#1A1A1A";
    textColor = "#FFFFFF";
    subColor = "rgba(255,255,255,0.7)";
  } else if (isFunctionChild) {
    fill = "#FFFFFF";
    border = "#D4AF37";
    textColor = "#141414";
  } else if (isClassChild) {
    fill = "#EDE9FE";
    border = "#C4B5FD";
    textColor = "#4C1D95";
  } else if (isFolder) {
    fill = "#FAF7F0";
    border = "#D4AF37";
    textColor = "#141414";
  } else if (rank === 6) {
    fill = "#F1F5F9";
    border = "#CBD5E1";
    textColor = "#64748B";
  }

  const w = isChild ? CHILD_W : cfg.width;
  const h = isChild ? CHILD_H : cfg.height;

  // Impact rings
  let ring = "none";
  if (data.impactState === "target") ring = `0 0 0 4px #F0503C`;
  else if (data.impactState === "direct") ring = `0 0 0 3px #D97706`;
  else if (data.impactState === "transitive") ring = `0 0 0 2px rgba(217, 119, 6, 0.55)`;
  else if (data.highlight || selected) ring = `0 0 0 3px #F0503C`;

  const { dir, filename, fullPath } = splitFilePath(data.fullPath || data.subtitle || data.label, data.label);
  const rootFontSize = isRoot
    ? data.label.length > 22
      ? 13
      : data.label.length > 15
      ? 15
      : cfg.fontSize
    : cfg.fontSize;

  return (
    <div
      className={`
        relative flex items-center gap-2 transition-transform duration-100 overflow-hidden
        hover:scale-[1.02] ${isChild ? "px-2" : "px-3"}
      `}
      style={{
        width: w,
        height: h,
        background: fill,
        borderColor: border,
        borderWidth: cfg.borderWidth,
        borderStyle: "solid",
        borderRadius: cfg.borderRadius,
        boxShadow: ring,
        opacity: data.impactState === "dim" ? 0.25 : 1,
      }}
      title={fullPath || data.label}
    >
      {/* Halo for repo node (A10) */}
      {isRoot && <div className="repo-halo -translate-x-1/2 -translate-y-1/2" style={{ left: "50%", top: "50%", zIndex: -1 }} />}

      {/* Target handle: in (A1) */}
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        className="rs-handle"
        isConnectable={false}
      />

      <Icon size={isRoot ? 20 : isChild ? 14 : rank <= 2 ? 18 : 15} style={{ color: textColor }} className="shrink-0" />
      <div className="min-w-0 flex-1 overflow-hidden">
        <div
          className="leading-tight truncate min-w-0"
          title={isRoot ? data.label : fullPath || filename}
          style={{
            color: textColor,
            fontSize: isChild ? 11 : isRoot ? rootFontSize : cfg.fontSize,
            fontWeight: isChild ? 700 : cfg.fontWeight,
          }}
        >
          {isRoot ? data.label : filename}
        </div>
        {!isRoot && !isChild && dir && rank <= 4 && (
          <div
            className="font-mono text-[9px] leading-tight truncate min-w-0 opacity-80 mt-0.5"
            title={dir}
            style={{ color: subColor }}
          >
            {dir}
          </div>
        )}
      </div>

      {/* Tour badges */}
      {data.stepBadge != null && (
        <span
          className="
            absolute -top-2 -right-2 w-5 h-5 rounded-full
            bg-accent-cyan text-white text-[10px] font-bold
            border border-[#141414] flex items-center justify-center
          "
        >
          {data.stepBadge}
        </span>
      )}
      {data.pastStep && data.stepBadge == null && (
        <span
          className="
            absolute -top-2 -right-2 w-5 h-5 rounded-full
            bg-[#EFE8D8] text-[#837D6E] text-[10px] font-bold
            border border-[#B9B2A0] flex items-center justify-center
          "
          aria-label="Completed step"
        >
          ✓
        </span>
      )}

      {/* Source handle: out (A1) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        className="rs-handle"
        isConnectable={false}
      />
    </div>
  );
}

const LayerNode = memo(LayerNodeInner);
export default LayerNode;
