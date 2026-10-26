/**
 * MindMapNodeCard.tsx
 * Memoized card renderer for mindmap hierarchy nodes (root, pillar, folder, file, symbol).
 * Displays server-authoritative roles, route counts, metrics, expand/collapse toggles,
 * and client-constructed file actions (GitHub, VS Code/Cursor, Blast Radius).
 */

import React, { memo } from "react";
import {
  Boxes,
  Server,
  Monitor,
  Database,
  Cloud,
  CheckCircle2,
  BookOpen,
  Folder,
  FolderOpen,
  FileCode2,
  Code2,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Flame,
} from "lucide-react";
import type {
  ImpactHighlightState,
  MindmapNode,
  MindmapPillarId,
} from "../../lib/mindmapTypes";

export interface MindMapNodeCardProps {
  node: MindmapNode;
  isExpanded: boolean;
  hasChildren: boolean;
  childCount?: number;
  isSelected?: boolean;
  impactState?: ImpactHighlightState;
  isSearchMatch?: boolean;
  onToggleExpand: (id: string) => void;
  onSelectNode: (node: MindmapNode) => void;
  onOpenInEditor?: (path: string, line?: number) => void;
  onToggleBlastRadius?: (node: MindmapNode) => void;
  isBlastTarget?: boolean;
  repoOwner?: string;
  repoName?: string;
  repoBranch?: string;
  localRoot?: string | null;
}

function getPillarIcon(pillar?: MindmapPillarId) {
  switch (pillar) {
    case "frontend":
      return <Monitor size={15} className="text-cyan-600 shrink-0" />;
    case "backend":
      return <Server size={15} className="text-rose-600 shrink-0" />;
    case "data":
      return <Database size={15} className="text-emerald-600 shrink-0" />;
    case "infrastructure":
      return <Cloud size={15} className="text-amber-600 shrink-0" />;
    case "tests":
      return <CheckCircle2 size={15} className="text-green-600 shrink-0" />;
    case "docs":
      return <BookOpen size={15} className="text-purple-600 shrink-0" />;
    default:
      return <Boxes size={15} className="text-text-primary shrink-0" />;
  }
}

function formatRole(role: string): string {
  // Format snake_case to readable badge text
  return role.replace(/_/g, " ");
}

export const MindMapNodeCard: React.FC<MindMapNodeCardProps> = memo(
  ({
    node,
    isExpanded,
    hasChildren,
    childCount = 0,
    isSelected = false,
    impactState = null,
    isSearchMatch = false,
    onToggleExpand,
    onSelectNode,
    onOpenInEditor,
    onToggleBlastRadius,
    isBlastTarget = false,
    repoOwner,
    repoName,
    repoBranch = "HEAD",
  }) => {
    // ── Build GitHub URL client-side ──
    const canHaveGitHub = Boolean(repoOwner && repoName && node.path);
    const githubUrl = canHaveGitHub
      ? `https://github.com/${repoOwner}/${repoName}/blob/${repoBranch}/${node.path}${
          node.line ? `#L${node.line}` : ""
        }`
      : null;

    // ── Determine impact styling ──
    let impactBorder = "";
    let impactBg = "";
    if (isBlastTarget) {
      impactBorder = "!border-[#F0503C] !ring-2 !ring-[#F0503C]";
      impactBg = "bg-[#F0503C]/10";
    } else if (impactState === "direct") {
      impactBorder = "!border-amber-500 !ring-2 !ring-amber-500";
      impactBg = "bg-amber-500/10";
    } else if (impactState === "transitive") {
      impactBorder = "!border-cyan-500 !ring-2 !ring-cyan-500";
      impactBg = "bg-cyan-500/10";
    } else if (impactState === "dim") {
      impactBg = "opacity-40";
    }

    const searchRing = isSearchMatch ? "ring-2 ring-amber-400 bg-amber-50/50" : "";
    const selectedRing = isSelected ? "ring-2 ring-accent-cyan" : "";

    const handleCardClick = (e: React.MouseEvent) => {
      e.stopPropagation();
      onSelectNode(node);
    };

    const handleExpandToggle = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (hasChildren) {
        onToggleExpand(node.id);
      }
    };

    // ── ROOT CARD ──
    if (node.kind === "root") {
      return (
        <div
          data-node-id={node.id}
          data-node-kind={node.kind}
          data-selected={isSelected ? "true" : "false"}
          aria-current={isSelected ? "true" : undefined}
          tabIndex={0}
          role="button"
          aria-label={`Root: ${node.label}`}
          onClick={handleCardClick}
          className={`
            w-[200px] px-3.5 py-2.5 rounded-lg bg-bg-panel border-[1.5px] border-border-subtle shadow-md
            flex items-center justify-between gap-2 cursor-pointer transition-all duration-150
            hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent-cyan
            ${selectedRing} ${searchRing}
          `}
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="p-1 rounded bg-bg-panel-alt border border-border-subtle">
              <Boxes size={16} className="text-accent-cyan" />
            </span>
            <div className="min-w-0">
              <span className="block font-extrabold text-sm text-text-primary truncate">
                {node.label}
              </span>
              <span className="text-[10px] uppercase font-bold text-text-muted tracking-wider">
                System Root
              </span>
            </div>
          </div>
          {hasChildren && (
            <button
              onClick={handleExpandToggle}
              aria-label={isExpanded ? "Collapse root" : "Expand root"}
              className="p-1 rounded hover:bg-bg-panel-hover text-text-muted"
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
          )}
        </div>
      );
    }

    // ── PILLAR CARD ──
    if (node.kind === "pillar") {
      return (
        <div
          data-node-id={node.id}
          data-node-kind={node.kind}
          data-selected={isSelected ? "true" : "false"}
          aria-current={isSelected ? "true" : undefined}
          tabIndex={0}
          role="button"
          aria-label={`Pillar: ${node.label}`}
          onClick={handleCardClick}
          className={`
            w-[220px] p-2.5 rounded-lg bg-bg-panel border-[1.5px] border-border-subtle shadow-sm
            flex flex-col gap-1.5 cursor-pointer transition-all duration-150
            hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-cyan
            ${selectedRing} ${searchRing} ${impactBorder} ${impactBg}
          `}
        >
          <div className="flex items-center justify-between gap-1.5 min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <span className="p-1 rounded bg-bg-panel-alt border border-border-hairline">
                {getPillarIcon(node.pillar)}
              </span>
              <span className="font-bold text-xs text-text-primary truncate">
                {node.label}
              </span>
            </div>
            {hasChildren && (
              <button
                onClick={handleExpandToggle}
                aria-label={isExpanded ? `Collapse ${node.label}` : `Expand ${node.label}`}
                className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[11px] font-mono text-text-muted hover:bg-bg-panel-hover"
              >
                <span>{childCount}</span>
                {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              </button>
            )}
          </div>
          {node.metrics && (
            <div className="flex items-center gap-2 text-[10px] font-mono text-text-muted pt-1 border-t border-border-hairline">
              <span>{node.metrics.files} files</span>
              <span>·</span>
              <span>{node.metrics.symbols} sym</span>
              {node.metrics.routes > 0 && (
                <>
                  <span>·</span>
                  <span className="text-rose-600 font-semibold">{node.metrics.routes} routes</span>
                </>
              )}
            </div>
          )}
        </div>
      );
    }

    // ── FOLDER CARD ──
    if (node.kind === "folder") {
      return (
        <div
          data-node-id={node.id}
          data-node-kind={node.kind}
          data-selected={isSelected ? "true" : "false"}
          aria-current={isSelected ? "true" : undefined}
          tabIndex={0}
          role="button"
          aria-label={`Folder: ${node.label}`}
          onClick={handleCardClick}
          className={`
            w-[200px] px-2.5 py-1.5 rounded-md bg-bg-panel border-[1.5px] border-border-subtle shadow-sm
            flex items-center justify-between gap-1.5 cursor-pointer transition-all duration-150
            hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-cyan
            ${selectedRing} ${searchRing} ${impactBorder} ${impactBg}
          `}
        >
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-text-muted">
              {isExpanded ? <FolderOpen size={14} /> : <Folder size={14} />}
            </span>
            <span className="font-mono text-xs text-text-primary truncate font-medium">
              {node.label}
            </span>
          </div>
          {hasChildren && (
            <button
              onClick={handleExpandToggle}
              aria-label={isExpanded ? `Collapse ${node.label}` : `Expand ${node.label}`}
              className="flex items-center gap-0.5 px-1 py-0.5 rounded text-[10px] font-mono text-text-muted hover:bg-bg-panel-hover"
            >
              <span>{childCount}</span>
              {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
          )}
        </div>
      );
    }

    // ── FILE CARD ──
    if (node.kind === "file") {
      return (
        <div
          data-node-id={node.id}
          data-node-kind={node.kind}
          data-selected={isSelected ? "true" : "false"}
          aria-current={isSelected ? "true" : undefined}
          tabIndex={0}
          role="button"
          aria-label={`File: ${node.label}${node.role ? `, ${node.role}` : ""}`}
          onClick={handleCardClick}
          className={`
            w-[240px] p-2 rounded-lg bg-bg-panel border-[1.5px] border-border-subtle shadow-sm
            flex flex-col gap-1.5 cursor-pointer transition-all duration-150
            hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-cyan
            ${selectedRing} ${searchRing} ${impactBorder} ${impactBg}
          `}
        >
          <div className="flex items-center justify-between gap-1.5 min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <FileCode2 size={14} className="text-text-muted shrink-0" />
              <span className="font-mono text-xs font-semibold text-text-primary truncate">
                {node.label}
              </span>
            </div>
            {hasChildren && (
              <button
                onClick={handleExpandToggle}
                aria-label={isExpanded ? `Collapse symbols for ${node.label}` : `Expand symbols for ${node.label}`}
                title={isExpanded ? "Collapse symbols" : "Expand symbols"}
                className="flex items-center gap-0.5 px-1 py-0.5 rounded text-[10px] font-mono text-text-muted hover:bg-bg-panel-hover shrink-0"
              >
                <span>{childCount}</span>
                {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </button>
            )}
          </div>

          {/* Badges row: server role & route count */}
          <div className="flex items-center flex-wrap gap-1">
            {node.role && (
              <span
                data-testid="role-badge"
                className="px-1.5 py-0.5 rounded bg-bg-panel-alt border border-border-hairline text-[10px] font-mono font-medium text-text-secondary"
              >
                {formatRole(node.role)}
              </span>
            )}
            {node.route_count !== undefined && node.route_count > 0 && (
              <span
                data-testid="route-count-badge"
                className="px-1.5 py-0.5 rounded bg-rose-50 border border-rose-200 text-[10px] font-mono font-semibold text-rose-700"
              >
                {node.route_count} {node.route_count === 1 ? "route" : "routes"}
              </span>
            )}
          </div>

          {/* Actions toolbar: GitHub, VS Code/Editor, Blast Radius */}
          <div className="flex items-center justify-between gap-1 pt-1 border-t border-border-hairline">
            <div className="flex items-center gap-1">
              {githubUrl && (
                <a
                  href={githubUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  title="Open file on GitHub"
                  aria-label="Open on GitHub"
                  className="p-1 rounded text-text-muted hover:text-text-primary hover:bg-bg-panel-hover transition-colors"
                >
                  <ExternalLink size={12} />
                </a>
              )}
              {onOpenInEditor && node.path && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenInEditor(node.path!, node.line ?? 1);
                  }}
                  title="Open file in IDE (VS Code / Cursor)"
                  aria-label="Open in editor"
                  className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold text-text-secondary hover:text-text-primary hover:bg-bg-panel-hover transition-colors border border-border-hairline"
                >
                  IDE
                </button>
              )}
            </div>

            {onToggleBlastRadius && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleBlastRadius(node);
                }}
                title={
                  isBlastTarget
                    ? "Clear Blast Radius highlight"
                    : "Analyze Blast Radius (callers & downstream impact)"
                }
                aria-label="Analyze blast radius"
                className={`
                  flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold transition-colors
                  ${
                    isBlastTarget
                      ? "bg-[#F0503C] text-white"
                      : "text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200"
                  }
                `}
              >
                <Flame size={10} />
                <span>Impact</span>
              </button>
            )}
          </div>
        </div>
      );
    }

    // ── SYMBOL CARD ──
    if (node.kind === "symbol") {
      return (
        <div
          data-node-id={node.id}
          data-node-kind={node.kind}
          data-selected={isSelected ? "true" : "false"}
          aria-current={isSelected ? "true" : undefined}
          tabIndex={0}
          role="button"
          aria-label={`Symbol: ${node.label}${node.role ? `, ${node.role}` : ""}`}
          onClick={handleCardClick}
          className={`
            w-[210px] px-2 py-1.5 rounded-md bg-bg-panel border-[1.5px] border-border-subtle shadow-sm
            flex items-center justify-between gap-1.5 cursor-pointer transition-all duration-150
            hover:shadow-md focus:outline-none focus:ring-2 focus:ring-accent-cyan
            ${selectedRing} ${searchRing} ${impactBorder} ${impactBg}
          `}
        >
          <div className="flex items-center gap-1.5 min-w-0">
            <Code2 size={13} className="text-text-muted shrink-0" />
            <span className="font-mono text-xs text-text-primary truncate font-medium">
              {node.label}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {node.line && (
              <span className="text-[10px] font-mono text-text-muted">
                L{node.line}
              </span>
            )}
            {node.route_count !== undefined && node.route_count > 0 && (
              <span
                data-testid="symbol-route-count-badge"
                title={`${node.route_count} API route${node.route_count === 1 ? "" : "s"}`}
                className="px-1 py-0.2 rounded bg-rose-50 border border-rose-200 text-[9px] font-mono font-semibold text-rose-700"
              >
                {node.route_count} route{node.route_count === 1 ? "" : "s"}
              </span>
            )}
            {node.role && (
              <span className="px-1 py-0.2 rounded bg-bg-panel-alt border border-border-hairline text-[9px] font-mono text-text-secondary">
                {formatRole(node.role)}
              </span>
            )}
          </div>
        </div>
      );
    }

    // Fallback generic card
    return (
      <div
        data-node-id={node.id}
        data-selected={isSelected ? "true" : "false"}
        aria-current={isSelected ? "true" : undefined}
        tabIndex={0}
        role="button"
        onClick={handleCardClick}
        className="w-[200px] p-2 rounded bg-bg-panel border border-border-subtle text-xs font-mono"
      >
        {node.label}
      </div>
    );
  },
);

MindMapNodeCard.displayName = "MindMapNodeCard";
