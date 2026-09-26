/**
 * GraphControls.tsx
 * Graph toolbar (FILE 3 placement): actions row + vertical zoom stack,
 * anchored bottom-left. Must live inside <ReactFlowProvider>.
 */
import { useReactFlow } from "reactflow";
import {
  Plus, Minus, Maximize, LayoutGrid, ArrowLeftRight, ArrowUpDown,
  FolderTree, LocateFixed, Map as MapIcon, Image, FileCode2, Wand2,
} from "lucide-react";

interface Props {
  onRelayout: () => void;
  onToggleDirection: () => void;
  onToggleGroup: () => void;
  onToggleLegend: () => void;
  onFocus: () => void;
  onExportPng: () => void;
  onExportSvg: () => void;
  onReversePrompt: () => void;
  direction: "LR" | "TB";
  grouped: boolean;
  legendShown: boolean;
  exporting: boolean;
  promptBusy: boolean;
}

const btn = (active?: boolean) => `
  w-8 h-8 flex items-center justify-center rounded-md
  ${active
    ? "bg-bg-panel-alt text-text-primary"
    : "text-text-secondary hover:bg-bg-panel-alt hover:text-text-primary"}
  transition-all duration-150
`;

export default function GraphControls({
  onRelayout, onToggleDirection, onToggleGroup, onToggleLegend, onFocus,
  onExportPng, onExportSvg, onReversePrompt,
  direction, grouped, legendShown, exporting, promptBusy,
}: Props) {
  const { fitView, zoomIn, zoomOut } = useReactFlow();

  return (
    <div className="graph-toolbar absolute bottom-4 left-4 z-10 flex flex-col gap-2 items-start">
      {/* Action row */}
      <div className="flex items-center gap-0.5 p-1 rounded-lg bg-bg-panel border border-border-hairline">
        <button onClick={onRelayout} title="Re-run layout" aria-label="Re-run layout" className={btn()}>
          <LayoutGrid size={14} />
        </button>
        <button
          onClick={onToggleDirection}
          title={`Layout direction: ${direction === "TB" ? "top-down" : "left-right"} (click to flip)`}
          aria-label="Toggle layout direction"
          className={btn()}
        >
          {direction === "LR" ? <ArrowUpDown size={14} /> : <ArrowLeftRight size={14} />}
        </button>
        <button
          onClick={onToggleGroup}
          title={grouped ? "Grouped by directory (click to flatten)" : "Flat file list (click to group by directory)"}
          aria-label="Toggle group by directory"
          className={btn(grouped)}
        >
          <FolderTree size={14} />
        </button>
        <button
          onClick={onToggleLegend}
          title={legendShown ? "Hide legend" : "Show legend"}
          aria-label="Toggle legend"
          className={btn(legendShown)}
        >
          <MapIcon size={14} />
        </button>
        <button
          onClick={onFocus}
          title="Focus selected node"
          aria-label="Focus selected node"
          className={btn()}
        >
          <LocateFixed size={14} />
        </button>
        <div className="w-px h-5 bg-border-hairline mx-0.5" />
        <button
          onClick={onExportPng}
          disabled={exporting}
          title="Export as PNG (high-res)"
          aria-label="Export as PNG"
          className={btn()}
        >
          <Image size={14} />
        </button>
        <button
          onClick={onExportSvg}
          disabled={exporting}
          title="Export as SVG"
          aria-label="Export as SVG"
          className={btn()}
        >
          <FileCode2 size={14} />
        </button>
        <div className="w-px h-5 bg-border-hairline mx-0.5" />
        <button
          onClick={onReversePrompt}
          disabled={promptBusy}
          title="Generate Build Prompt — reverse-engineer an agent prompt from this repo"
          aria-label="Generate Build Prompt"
          className="h-8 px-2.5 flex items-center gap-1.5 rounded-md text-[11px] font-semibold
            bg-accent-cyan text-white border border-border-subtle shadow-sm
            hover:bg-accent-hover hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none
            disabled:opacity-40 transition-all duration-100"
        >
          {promptBusy ? <span className="btn-spinner" /> : <Wand2 size={13} />}
          Build Prompt
        </button>
      </div>

      {/* Vertical zoom stack */}
      <div className="flex flex-col p-1 rounded-lg bg-bg-panel border border-border-hairline">
        <button onClick={() => zoomIn({ duration: 200 })} title="Zoom in" aria-label="Zoom in" className={btn()}>
          <Plus size={14} />
        </button>
        <button onClick={() => zoomOut({ duration: 200 })} title="Zoom out" aria-label="Zoom out" className={btn()}>
          <Minus size={14} />
        </button>
        <button
          onClick={() => fitView({ padding: 0.2, duration: 400 })}
          title="Fit view"
          aria-label="Fit view"
          className={btn()}
        >
          <Maximize size={13} />
        </button>
      </div>
    </div>
  );
}
