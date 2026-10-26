/**
 * MindMapOutline.tsx
 * Semantic, accessible <ul role="tree"> alternative mirroring the visible mind map tree.
 * Supports full WAI-ARIA keyboard navigation:
 * - Arrow keys move between items
 * - Enter expands / collapses
 * - Space selects and centers the node
 * - Every treeitem has an accessible name
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileCode2,
  Code2,
  Boxes,
  X,
} from "lucide-react";
import type { MindmapNode } from "../../lib/mindmapTypes";

export interface MindMapOutlineProps {
  visibleTree: MindmapNode | null;
  expandedIds: Set<string>;
  onToggleExpand: (id: string) => void;
  selectedNodeId: string | null;
  onSelectNode: (node: MindmapNode) => void;
  onClose?: () => void;
}

interface FlatOutlineItem {
  node: MindmapNode;
  level: number;
  hasChildren: boolean;
  isExpanded: boolean;
  parentId: string | null;
}

export const MindMapOutline: React.FC<MindMapOutlineProps> = ({
  visibleTree,
  expandedIds,
  onToggleExpand,
  selectedNodeId,
  onSelectNode,
  onClose,
}) => {
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const treeRef = useRef<HTMLUListElement>(null);

  // Flatten the visible tree into an array preserving parent-child hierarchy
  const items: FlatOutlineItem[] = [];

  function walk(node: MindmapNode, level: number, parentId: string | null) {
    if (!node) return;
    const hasChildren = Boolean(node.children && node.children.length > 0);
    const isExpanded = expandedIds.has(node.id);

    items.push({
      node,
      level,
      hasChildren,
      isExpanded,
      parentId,
    });

    if (isExpanded && node.children) {
      for (const child of node.children) {
        walk(child, level + 1, node.id);
      }
    }
  }

  if (visibleTree) {
    walk(visibleTree, 1, null);
  }

  // Set default focus to first item if none set
  useEffect(() => {
    if (!focusedId && items.length > 0) {
      setFocusedId(items[0].node.id);
    }
  }, [items, focusedId]);

  // Keep focused element scrolled into view
  useEffect(() => {
    if (!focusedId || !treeRef.current) return;
    const el = treeRef.current.querySelector<HTMLElement>(
      `[data-outline-id="${focusedId}"]`,
    );
    if (el) {
      el.focus();
    }
  }, [focusedId]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (items.length === 0) return;

      const currentIndex = items.findIndex((it) => it.node.id === focusedId);
      const currentItem = currentIndex >= 0 ? items[currentIndex] : items[0];

      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          const nextIndex = Math.min(items.length - 1, currentIndex + 1);
          setFocusedId(items[nextIndex].node.id);
          break;
        }
        case "ArrowUp": {
          e.preventDefault();
          const prevIndex = Math.max(0, currentIndex - 1);
          setFocusedId(items[prevIndex].node.id);
          break;
        }
        case "ArrowRight": {
          e.preventDefault();
          if (currentItem.hasChildren) {
            if (!currentItem.isExpanded) {
              onToggleExpand(currentItem.node.id);
            } else if (currentIndex + 1 < items.length) {
              setFocusedId(items[currentIndex + 1].node.id);
            }
          }
          break;
        }
        case "ArrowLeft": {
          e.preventDefault();
          if (currentItem.hasChildren && currentItem.isExpanded) {
            onToggleExpand(currentItem.node.id);
          } else if (currentItem.parentId) {
            setFocusedId(currentItem.parentId);
          }
          break;
        }
        case "Enter": {
          e.preventDefault();
          if (currentItem.hasChildren) {
            onToggleExpand(currentItem.node.id);
          }
          break;
        }
        case " ": {
          e.preventDefault();
          onSelectNode(currentItem.node.id ? currentItem.node : items[0].node);
          break;
        }
        case "Home": {
          e.preventDefault();
          if (items.length > 0) setFocusedId(items[0].node.id);
          break;
        }
        case "End": {
          e.preventDefault();
          if (items.length > 0) setFocusedId(items[items.length - 1].node.id);
          break;
        }
        default:
          break;
      }
    },
    [items, focusedId, onToggleExpand, onSelectNode],
  );

  const getItemIcon = (node: MindmapNode, isExpanded: boolean) => {
    switch (node.kind) {
      case "root":
        return <Boxes size={13} className="text-accent-cyan shrink-0" />;
      case "pillar":
        return <Boxes size={13} className="text-rose-600 shrink-0" />;
      case "folder":
        return isExpanded ? (
          <FolderOpen size={13} className="text-text-muted shrink-0" />
        ) : (
          <Folder size={13} className="text-text-muted shrink-0" />
        );
      case "file":
        return <FileCode2 size={13} className="text-text-muted shrink-0" />;
      case "symbol":
        return <Code2 size={13} className="text-text-muted shrink-0" />;
      default:
        return null;
    }
  };

  return (
    <aside
      data-testid="mindmap-outline"
      aria-label="Mind map outline panel"
      className="
        w-72 max-w-[85vw] h-full flex flex-col bg-bg-panel border-r-[1.5px] border-border-subtle
        shrink-0 overflow-hidden shadow-sm z-10
      "
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-hairline shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-extrabold text-xs text-text-primary tracking-tight">
            Mind Map Outline
          </span>
          <span className="text-[10px] font-mono text-text-muted">
            ({items.length} visible)
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close outline"
            className="p-1 rounded hover:bg-bg-panel-hover text-text-muted hover:text-text-primary"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Keyboard hints banner */}
      <div className="px-3 py-1.5 bg-bg-panel-alt border-b border-border-hairline text-[10px] text-text-muted font-mono flex items-center justify-between">
        <span>↑↓ move</span>
        <span>Enter expand</span>
        <span>Space select</span>
      </div>

      {/* Accessible Tree List */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-2">
        <ul
          ref={treeRef}
          role="tree"
          aria-label="Mind map hierarchy"
          onKeyDown={handleKeyDown}
          tabIndex={0}
          className="space-y-0.5 focus:outline-none"
        >
          {items.map((item) => {
            const isSelected = selectedNodeId === item.node.id;
            const isFocused = focusedId === item.node.id;

            const accessibleName = `${item.node.label} (${item.node.kind}${
              item.node.role ? `, ${item.node.role}` : ""
            })`;

            return (
              <li
                key={item.node.id}
                role="treeitem"
                data-outline-id={item.node.id}
                aria-label={accessibleName}
                aria-level={item.level}
                aria-expanded={item.hasChildren ? item.isExpanded : undefined}
                aria-selected={isSelected}
                tabIndex={isFocused ? 0 : -1}
                onClick={() => {
                  setFocusedId(item.node.id);
                  onSelectNode(item.node);
                }}
                style={{ paddingLeft: `${(item.level - 1) * 14 + 6}px` }}
                className={`
                  flex items-center gap-1.5 py-1 pr-2 rounded text-xs font-mono cursor-pointer
                  transition-colors select-none focus:outline-none
                  ${
                    isSelected
                      ? "bg-accent-cyan/15 text-text-primary font-semibold ring-1 ring-accent-cyan"
                      : isFocused
                      ? "bg-bg-panel-hover text-text-primary"
                      : "text-text-secondary hover:bg-bg-panel-alt hover:text-text-primary"
                  }
                `}
              >
                {/* Expand / Collapse toggle icon */}
                {item.hasChildren ? (
                  <button
                    type="button"
                    tabIndex={-1}
                    aria-hidden="true"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleExpand(item.node.id);
                    }}
                    className="p-0.5 rounded hover:bg-bg-panel-hover text-text-muted"
                  >
                    {item.isExpanded ? (
                      <ChevronDown size={12} />
                    ) : (
                      <ChevronRight size={12} />
                    )}
                  </button>
                ) : (
                  <span className="w-3.5 inline-block" />
                )}

                {/* Node icon */}
                {getItemIcon(item.node, item.isExpanded)}

                {/* Label & badges */}
                <span className="truncate flex-1">{item.node.label}</span>

                {item.node.role && (
                  <span className="text-[9px] px-1 rounded bg-bg-panel border border-border-hairline text-text-muted">
                    {item.node.role}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
};
