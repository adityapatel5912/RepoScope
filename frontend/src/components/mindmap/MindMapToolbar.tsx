/**
 * MindMapToolbar.tsx
 * Floating / anchored toolbar for MindMapView:
 * View mode toggle (Graph / Mind Map), Orientation toggle (TB / LR),
 * Expand All, Collapse All, Outline toggle, Zoom controls, and Search.
 */

import React from "react";
import {
  Network,
  ArrowDown,
  ArrowRight,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ListTree,
  AlertTriangle,
} from "lucide-react";
import type { MindmapOrientation } from "../../lib/mindmapTypes";
import { MindMapSearch } from "./MindMapSearch";

export interface MindMapToolbarProps {
  orientation: MindmapOrientation;
  onToggleOrientation: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onSwitchToGraph: () => void;
  onToggleOutline: () => void;
  isOutlineOpen: boolean;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFitView?: () => void;
  searchQuery: string;
  onSearchQueryChange: (q: string) => void;
  searchMatchCount: number;
  currentMatchIndex?: number;
  onNextMatch?: () => void;
  onPrevMatch?: () => void;
  truncated?: boolean;
  omittedCount?: number;
}

export const MindMapToolbar: React.FC<MindMapToolbarProps> = ({
  orientation,
  onToggleOrientation,
  onExpandAll,
  onCollapseAll,
  onSwitchToGraph,
  onToggleOutline,
  isOutlineOpen,
  onZoomIn,
  onZoomOut,
  onFitView,
  searchQuery,
  onSearchQueryChange,
  searchMatchCount,
  currentMatchIndex = 0,
  onNextMatch,
  onPrevMatch,
  truncated = false,
  omittedCount = 0,
}) => {
  return (
    <div
      data-testid="mindmap-toolbar"
      className="
        flex flex-wrap items-center justify-between gap-2 px-3 py-2
        bg-bg-panel/95 backdrop-blur-sm border-b-[1.5px] border-border-subtle
        shrink-0 z-20 shadow-sm
      "
    >
      {/* ── Left: View switcher & Orientation ── */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {/* Network / Graph toggle button */}
        <button
          type="button"
          data-testid="switch-to-graph-btn"
          onClick={onSwitchToGraph}
          title="Switch to Dependency Network view"
          aria-label="Switch to Graph"
          className="
            flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold
            bg-bg-panel-alt hover:bg-bg-panel-hover border border-border-subtle
            text-text-primary transition-colors
          "
        >
          <Network size={14} className="text-accent-cyan" />
          <span className="hidden sm:inline">Graph</span>
        </button>

        {/* Orientation toggle */}
        <button
          type="button"
          data-testid="toggle-orientation-btn"
          onClick={onToggleOrientation}
          title={`Current orientation: ${
            orientation === "TB" ? "Top-to-Bottom (Vertical)" : "Left-to-Right (Horizontal)"
          }. Click to switch.`}
          aria-label={`Switch to ${orientation === "TB" ? "horizontal" : "vertical"} layout`}
          className="
            flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold
            bg-bg-panel-alt hover:bg-bg-panel-hover border border-border-subtle
            text-text-primary transition-colors
          "
        >
          {orientation === "TB" ? (
            <>
              <ArrowDown size={14} className="text-text-primary" />
              <span>TB (Vertical)</span>
            </>
          ) : (
            <>
              <ArrowRight size={14} className="text-text-primary" />
              <span>LR (Horizontal)</span>
            </>
          )}
        </button>

        {/* Expand / Collapse All */}
        <div className="flex items-center rounded-md border border-border-subtle overflow-hidden">
          <button
            type="button"
            data-testid="expand-all-btn"
            onClick={onExpandAll}
            title="Expand all branches"
            aria-label="Expand all"
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium bg-bg-panel hover:bg-bg-panel-hover text-text-primary transition-colors"
          >
            <Maximize2 size={12} />
            <span className="hidden md:inline">Expand All</span>
          </button>
          <div className="w-[1px] h-4 bg-border-subtle" />
          <button
            type="button"
            data-testid="collapse-all-btn"
            onClick={onCollapseAll}
            title="Collapse back to root and pillars"
            aria-label="Collapse all"
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium bg-bg-panel hover:bg-bg-panel-hover text-text-primary transition-colors"
          >
            <Minimize2 size={12} />
            <span className="hidden md:inline">Collapse</span>
          </button>
        </div>

        {/* Outline toggle button */}
        <button
          type="button"
          data-testid="toggle-outline-btn"
          onClick={onToggleOutline}
          title={isOutlineOpen ? "Hide tree outline" : "Show accessible tree outline"}
          aria-label="Toggle tree outline"
          aria-pressed={isOutlineOpen}
          className={`
            flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium border transition-colors
            ${
              isOutlineOpen
                ? "bg-accent-cyan text-white border-border-subtle"
                : "bg-bg-panel-alt hover:bg-bg-panel-hover border-border-subtle text-text-primary"
            }
          `}
        >
          <ListTree size={13} />
          <span className="hidden sm:inline">Outline</span>
        </button>
      </div>

      {/* ── Center: Search ── */}
      <div className="flex items-center gap-2">
        <MindMapSearch
          query={searchQuery}
          onQueryChange={onSearchQueryChange}
          matchCount={searchMatchCount}
          currentMatchIndex={currentMatchIndex}
          onNextMatch={onNextMatch}
          onPrevMatch={onPrevMatch}
        />

        {truncated && (
          <span
            data-testid="truncated-badge"
            title={`Tree capped deterministically. ${omittedCount} deeper nodes were omitted.`}
            className="
              hidden lg:flex items-center gap-1 px-2 py-0.5 rounded-full
              bg-amber-100 border border-amber-300 text-amber-900 text-[10px] font-mono font-semibold
            "
          >
            <AlertTriangle size={11} className="text-amber-700" />
            <span>Capped ({omittedCount} omitted)</span>
          </span>
        )}
      </div>

      {/* ── Right: Zoom & Reset controls ── */}
      <div className="flex items-center gap-1">
        {onZoomIn && (
          <button
            type="button"
            data-testid="zoom-in-btn"
            onClick={onZoomIn}
            aria-label="Zoom in"
            title="Zoom in"
            className="p-1.5 rounded-md hover:bg-bg-panel-hover text-text-primary border border-border-hairline"
          >
            <ZoomIn size={14} />
          </button>
        )}
        {onZoomOut && (
          <button
            type="button"
            data-testid="zoom-out-btn"
            onClick={onZoomOut}
            aria-label="Zoom out"
            title="Zoom out"
            className="p-1.5 rounded-md hover:bg-bg-panel-hover text-text-primary border border-border-hairline"
          >
            <ZoomOut size={14} />
          </button>
        )}
        {onFitView && (
          <button
            type="button"
            data-testid="fit-view-btn"
            onClick={onFitView}
            aria-label="Reset zoom and fit view"
            title="Fit to view (Space)"
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-mono hover:bg-bg-panel-hover text-text-primary border border-border-hairline"
          >
            <RotateCcw size={12} />
            <span className="hidden xl:inline">Fit</span>
          </button>
        )}
      </div>
    </div>
  );
};
