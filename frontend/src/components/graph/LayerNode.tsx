import { memo } from "react";
import { Handle, Position } from "reactflow";
import { Monitor, Server, Database, Globe, Cpu, FileCode2, Folder, Boxes, type LucideIcon } from "lucide-react";
import { LAYER_STYLE, type Layer } from "./layerClassifier";

export interface LayerNodeData {
  label: string;
  kind: "root" | "folder" | "file" | "function" | "class" | "import" | "commit" | "repo";
  layer: Layer;
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

/**
 * Flat pastel node per FILE 3: rounded rectangle, 1px layer border,
 * icon left · bold label · muted mono subtitle. No shadows, no gradients.
 * Child nodes (expanded functions/classes) render smaller with distinct
 * styling: functions white/gold, classes purple, no subtitle.
 */
function LayerNodeInner({ data, selected }: { data: LayerNodeData; selected?: boolean }) {
  const style = LAYER_STYLE[data.layer];
  const Icon = KIND_ICONS[data.kind] ?? LAYER_ICONS[data.layer];
  const isRoot = data.kind === "root" || data.kind === "repo";
  const isChild = Boolean(data.child);
  const isFunctionChild = isChild && data.kind === "function";
  const isClassChild = isChild && data.kind === "class";
  const isFolder = data.kind === "folder";

  // Per-kind fills (Section 8 node styling)
  let fill = style.fill;
  let border = style.border;
  let textColor = style.text;
  let subColor = "#837D6E";
  if (isRoot)        { fill = "#1A1A1A"; border = "#1A1A1A"; textColor = "#FFFFFF"; subColor = "rgba(255,255,255,0.7)"; }
  else if (isFunctionChild) { fill = "#FFFFFF"; border = "#D4AF37"; textColor = "#141414"; }
  else if (isClassChild)    { fill = "#EDE9FE"; border = "#C4B5FD"; textColor = "#4C1D95"; }
  else if (isFolder)        { fill = "#FAF7F0"; border = "#D4AF37"; textColor = "#141414"; }

  const w = isChild ? CHILD_W : NODE_W;
  const h = isChild ? CHILD_H : NODE_H;

  // Impact rings (4.4) — box-shadow rings, no blur glow
  let ring = "none";
  if (data.impactState === "target")        ring = `0 0 0 4px #F0503C`;
  else if (data.impactState === "direct")   ring = `0 0 0 3px #D97706`;
  else if (data.impactState === "transitive") ring = `0 0 0 2px rgba(217, 119, 6, 0.55)`;
  else if (data.highlight || selected)      ring = `0 0 0 3px #F0503C`;

  return (
    <div
      className={`
        relative flex items-center gap-2 border rounded-md transition-transform duration-100
        hover:scale-[1.03] ${isChild ? "px-2" : "px-3"}
      `}
      style={{
        width: w,
        height: h,
        background: fill,
        borderColor: border,
        borderWidth: 1,
        boxShadow: ring,
        opacity: data.impactState === "dim" ? 0.25 : 1,
      }}
      title={data.subtitle ?? data.label}
    >
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-0 !w-1 !h-1 !min-w-0 !min-h-0 opacity-0" />
      <Icon size={isChild ? 14 : 18} style={{ color: textColor }} className="shrink-0" />
      <div className="min-w-0 flex-1">
        <div
          className={`font-bold leading-tight truncate ${isChild ? "text-[11px]" : "text-[13px]"}`}
          style={{ color: textColor }}
        >
          {data.label}
        </div>
        {data.subtitle && !isChild && (
          <div
            className="font-mono text-[10px] leading-tight truncate mt-0.5"
            style={{ color: subColor }}
          >
            {data.subtitle}
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

      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0 !w-1 !h-1 !min-w-0 !min-h-0 opacity-0" />
    </div>
  );
}

const LayerNode = memo(LayerNodeInner);
export default LayerNode;
