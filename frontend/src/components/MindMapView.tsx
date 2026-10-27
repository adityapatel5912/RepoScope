/**
 * MindMapView.tsx
 * Vertical six-pillar mind map view (Phase 2).
 *
 * Strict hierarchy:
 *   root → pillar → folder → file → symbol
 *
 * Features:
 * - Reads frozen GET /api/mindmap endpoint
 * - First paint: only root and 6 pillars expanded
 * - SessionStorage persistence for expanded set keyed by repository
 * - Tidy-tree layout with TB (vertical default) and LR toggle
 * - Debounced search with auto-ancestor expansion and focus
 * - Accessible semantic <ul role="tree"> outline mirroring visible tree
 * - Client-constructed file actions: GitHub, VS Code/Cursor, Blast Radius
 * - Empty & error states with retry
 * - Browser preview limitation message
 */

import React, {
  useState,
  useEffect,
  useRef,
  useMemo,
  useCallback,
} from "react";
import {
  Network,
  RotateCcw,
  AlertCircle,
  FileQuestion,
  HelpCircle,
} from "lucide-react";
import { getMindmap } from "../api/client";
import { analyzeImpact } from "../api/features";
import { openInEditor } from "../utils/openInEditor";
import { toast } from "./Toasts";
import type {
  ImpactHighlightState,
  MindmapNode,
  MindmapOrientation,
  MindmapPayload,
} from "../lib/mindmapTypes";
import {
  filterVisibleTree,
  getInitialExpandedIds,
  getAllExpandableIds,
  searchTree,
  findAncestors,
} from "../lib/mindmapTree";
import { computeMindmapLayout } from "../lib/mindmapLayout";
import { MindMapToolbar } from "./mindmap/MindMapToolbar";
import { MindMapNode } from "./mindmap/MindMapNode";
import { MindMapOutline } from "./mindmap/MindMapOutline";

export interface MindMapViewProps {
  repo: string | null;
  repoOwner?: string;
  repoName?: string;
  repoBranch?: string;
  localRoot?: string | null;
  previewName?: string | null;
  onSwitchToGraph: () => void;
  onOpenInEditor?: (path: string, line?: number) => void;
  impactTarget?: string | null;
  impactDirect?: string[];
  impactTransitive?: string[];
  focusNodeId?: string | null;
}

export default function MindMapView({
  repo,
  repoOwner = "",
  repoName = "",
  repoBranch = "HEAD",
  localRoot = null,
  previewName = null,
  onSwitchToGraph,
  onOpenInEditor: onOpenInEditorProp,
  impactTarget: externalImpactTarget = null,
  impactDirect: externalImpactDirect = [],
  impactTransitive: externalImpactTransitive = [],
  focusNodeId = null,
}: MindMapViewProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<MindmapPayload | null>(null);

  // Layout & View Options
  const [orientation, setOrientation] = useState<MindmapOrientation>("TB");
  const [isOutlineOpen, setIsOutlineOpen] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);

  // Blast Radius
  const [localBlastTarget, setLocalBlastTarget] = useState<string | null>(null);
  const [localBlastDirect, setLocalBlastDirect] = useState<string[]>([]);
  const [localBlastTransitive, setLocalBlastTransitive] = useState<string[]>([]);

  // Canvas Pan & Zoom
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const canvasContainerRef = useRef<HTMLDivElement>(null);

  // ── SessionStorage persistence for expanded set keyed by repository ──
  const storageKey = `reposcope-mindmap-expanded:${repo || "default"}`;

  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const arr = JSON.parse(saved);
        if (Array.isArray(arr)) {
          return new Set<string>(arr);
        }
      }
    } catch {
      /* ignore */
    }
    return new Set<string>();
  });

  // Reset expandedIds when repository changes
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const arr = JSON.parse(saved);
        if (Array.isArray(arr)) {
          setExpandedIds(new Set<string>(arr));
          return;
        }
      }
    } catch {
      /* ignore */
    }
    // If no saved state for the new repository key, reset to root + pillars
    if (payload?.root) {
      setExpandedIds(getInitialExpandedIds(payload.root));
    } else {
      setExpandedIds(new Set<string>());
    }
  }, [storageKey, payload]);

  // Persist expandedIds changes to sessionStorage
  const updateExpanded = useCallback(
    (newSet: Set<string>) => {
      setExpandedIds(newSet);
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(Array.from(newSet)));
      } catch {
        /* storage full / unavailable */
      }
    },
    [storageKey],
  );

  // ── Fetch Mindmap Data ──
  const fetchMindmap = useCallback(async () => {
    if (previewName) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getMindmap({ includeSymbols: true, maxNodes: 20000 });
      setPayload(data);

      // Check if we need to initialize expandedIds
      setExpandedIds((curr) => {
        if (curr.size === 0 && data.root) {
          const initSet = getInitialExpandedIds(data.root);
          try {
            sessionStorage.setItem(
              storageKey,
              JSON.stringify(Array.from(initSet)),
            );
          } catch {
            /* ignore */
          }
          return initSet;
        }
        return curr;
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [previewName, storageKey]);

  useEffect(() => {
    fetchMindmap();
  }, [fetchMindmap]);

  // ── Map of all nodes with children in the full payload ──
  const expandableNodesMap = useMemo(() => {
    const map = new Map<string, number>();
    if (!payload?.root) return map;

    function dfs(n: MindmapNode) {
      if (n.children && n.children.length > 0) {
        map.set(n.id, n.children.length);
        for (const c of n.children) {
          dfs(c);
        }
      }
    }
    dfs(payload.root);
    return map;
  }, [payload]);

  // ── Filter visible tree ──
  const visibleTree = useMemo(() => {
    if (!payload?.root) return null;
    return filterVisibleTree(payload.root, expandedIds);
  }, [payload, expandedIds]);

  // ── Compute Tidy Tree Layout ──
  const layout = useMemo(() => {
    return computeMindmapLayout(visibleTree, orientation);
  }, [visibleTree, orientation]);

  // ── Auto-fit view ──
  const fitView = useCallback(() => {
    if (!canvasContainerRef.current || layout.width === 0 || layout.height === 0) {
      return;
    }
    const container = canvasContainerRef.current;
    const cw = container.clientWidth;
    const ch = container.clientHeight;

    const pad = 64;
    const fitScale = Math.min(
      1.1,
      Math.max(0.25, Math.min((cw - pad) / layout.width, (ch - pad) / layout.height)),
    );

    const fitX = Math.round((cw - layout.width * fitScale) / 2);
    const fitY = Math.round((ch - layout.height * fitScale) / 2);

    setPan({ x: fitX, y: fitY });
    setScale(fitScale);
  }, [layout.width, layout.height]);

  // Fit view on first layout generation or orientation change
  const initialFitDoneRef = useRef(false);
  useEffect(() => {
    if (layout.nodes.length > 0) {
      if (!initialFitDoneRef.current) {
        fitView();
        initialFitDoneRef.current = true;
      }
    }
  }, [layout.nodes.length, fitView]);

  // Re-fit when orientation changes
  useEffect(() => {
    fitView();
  }, [orientation, fitView]);

  // ── Search & auto-expand ancestors ──
  const searchResults = useMemo(() => {
    if (!payload?.root || !searchQuery.trim()) {
      return { matches: [], ancestorIds: new Set<string>() };
    }
    return searchTree(payload.root, searchQuery);
  }, [payload, searchQuery]);

  const searchMatchIds = useMemo(() => {
    return new Set(searchResults.matches.map((m) => m.id));
  }, [searchResults.matches]);

  // Auto-expand ancestors when search returns results
  useEffect(() => {
    if (searchResults.matches.length > 0 && searchResults.ancestorIds.size > 0) {
      setExpandedIds((prev) => {
        let changed = false;
        const next = new Set(prev);
        for (const aId of searchResults.ancestorIds) {
          if (!next.has(aId)) {
            next.add(aId);
            changed = true;
          }
        }
        if (changed) {
          try {
            sessionStorage.setItem(storageKey, JSON.stringify(Array.from(next)));
          } catch {
            /* ignore */
          }
          return next;
        }
        return prev;
      });
    }
    setCurrentMatchIndex(0);
  }, [searchResults, storageKey]);

  // Center node in canvas
  const centerNode = useCallback(
    (nodeId: string) => {
      const node = layout.nodes.find((n) => n.id === nodeId);
      if (!node || !canvasContainerRef.current) return;
      const cw = canvasContainerRef.current.clientWidth;
      const ch = canvasContainerRef.current.clientHeight;

      const targetX = Math.round(cw / 2 - node.x * scale);
      const targetY = Math.round(ch / 2 - node.y * scale);
      setPan({ x: targetX, y: targetY });
    },
    [layout.nodes, scale],
  );

  // Focus external node (e.g. from citation click)
  useEffect(() => {
    if (!focusNodeId || !payload?.root) return;
    const ancestors = findAncestors(payload.root, focusNodeId);
    if (ancestors.length > 0) {
      setExpandedIds((prev) => {
        const next = new Set(prev);
        ancestors.forEach((id) => next.add(id));
        next.add(focusNodeId);
        return next;
      });
    }
    setSelectedNodeId(focusNodeId);
    centerNode(focusNodeId);
  }, [focusNodeId, payload?.root, centerNode]);

  // Listen for citation click event
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.nodeId && payload?.root) {
        const ancestors = findAncestors(payload.root, detail.nodeId);
        if (ancestors.length > 0) {
          setExpandedIds((prev) => {
            const next = new Set(prev);
            ancestors.forEach((id) => next.add(id));
            next.add(detail.nodeId);
            return next;
          });
        }
        setSelectedNodeId(detail.nodeId);
        centerNode(detail.nodeId);
      }
    };
    window.addEventListener("reposcope:focus-node", handler);
    return () => window.removeEventListener("reposcope:focus-node", handler);
  }, [payload?.root, centerNode]);

  // Focus current search match
  useEffect(() => {
    if (searchResults.matches.length > 0) {
      const match = searchResults.matches[currentMatchIndex];
      if (match) {
        setSelectedNodeId(match.id);
        centerNode(match.id);
      }
    }
  }, [searchResults.matches, currentMatchIndex, centerNode]);

  const handleNextMatch = useCallback(() => {
    if (searchResults.matches.length === 0) return;
    setCurrentMatchIndex((i) => (i + 1) % searchResults.matches.length);
  }, [searchResults.matches.length]);

  const handlePrevMatch = useCallback(() => {
    if (searchResults.matches.length === 0) return;
    setCurrentMatchIndex(
      (i) => (i - 1 + searchResults.matches.length) % searchResults.matches.length,
    );
  }, [searchResults.matches.length]);

  // ── Expand / Collapse Handler ──
  const handleToggleExpand = useCallback(
    (id: string) => {
      const next = new Set(expandedIds);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      updateExpanded(next);
    },
    [expandedIds, updateExpanded],
  );

  const handleExpandAll = useCallback(() => {
    if (!payload?.root) return;
    const all = getAllExpandableIds(payload.root);
    updateExpanded(all);
    toast.success("Expanded all nodes");
  }, [payload, updateExpanded]);

  const handleCollapseAll = useCallback(() => {
    if (!payload?.root) return;
    const initial = getInitialExpandedIds(payload.root);
    updateExpanded(initial);
    toast.success("Collapsed to pillars");
  }, [payload, updateExpanded]);

  // ── Select Node ──
  const handleSelectNode = useCallback(
    (node: MindmapNode) => {
      setSelectedNodeId(node.id);
      centerNode(node.id);
    },
    [centerNode],
  );

  // ── File Actions: Editor & Blast Radius ──
  const handleOpenInEditor = useCallback(
    (path: string, line = 1) => {
      if (onOpenInEditorProp) {
        onOpenInEditorProp(path, line);
      } else {
        void openInEditor({ path, line }, localRoot);
      }
    },
    [onOpenInEditorProp, localRoot],
  );

  const handleToggleBlastRadius = useCallback(
    async (node: MindmapNode) => {
      const targetLabel = node.path || node.label;
      // Toggle off if already active
      if (
        localBlastTarget === targetLabel ||
        localBlastTarget === node.id ||
        localBlastTarget === node.label
      ) {
        setLocalBlastTarget(null);
        setLocalBlastDirect([]);
        setLocalBlastTransitive([]);
        toast.success("Cleared Blast Radius highlight");
        return;
      }

      try {
        const impact = await analyzeImpact(targetLabel);
        setLocalBlastTarget(targetLabel);
        setLocalBlastDirect(impact.direct_impacts.map((d) => d.id));
        setLocalBlastTransitive(impact.transitive_impacts.map((tr) => tr.id));
        toast.success(`Blast radius: ${impact.total_impacted} impacted nodes`);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Impact analysis failed";
        toast.error(msg);
      }
    },
    [localBlastTarget],
  );

  // ── Drag & Zoom interaction handlers ──
  const handlePointerDown = (e: React.PointerEvent) => {
    // Only pan on left click on the canvas background
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("[data-node-id]")) return;

    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      panX: pan.x,
      panY: pan.y,
    };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    setPan({
      x: dragStartRef.current.panX + dx,
      y: dragStartRef.current.panY + dy,
    });
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (isDragging) {
      setIsDragging(false);
      (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    const newScale = Math.min(2.0, Math.max(0.2, scale * zoomFactor));

    if (!canvasContainerRef.current) return;
    const rect = canvasContainerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Zoom centered at mouse position
    const newPanX = mouseX - (mouseX - pan.x) * (newScale / scale);
    const newPanY = mouseY - (mouseY - pan.y) * (newScale / scale);

    setScale(newScale);
    setPan({ x: Math.round(newPanX), y: Math.round(newPanY) });
  };

  const handleZoomIn = () => setScale((s) => Math.min(2.0, s * 1.2));
  const handleZoomOut = () => setScale((s) => Math.max(0.2, s * 0.8));

  // ── Browser Preview Notice ──
  if (previewName) {
    return (
      <div
        data-testid="mindmap-preview-notice"
        className="w-full h-full flex flex-col items-center justify-center p-6 bg-bg-base text-center"
      >
        <div className="max-w-md p-6 bg-bg-panel border-[1.5px] border-border-subtle rounded-xl shadow-md flex flex-col items-center gap-3">
          <HelpCircle size={32} className="text-accent-cyan" />
          <h2 className="font-extrabold text-base text-text-primary">
            Browser Preview Active
          </h2>
          <p className="text-xs text-text-secondary leading-relaxed">
            Mind Map is server-backed and requires the backend index. You are currently
            viewing a local browser preview for <strong>{previewName}</strong>.
          </p>
          <button
            type="button"
            onClick={onSwitchToGraph}
            className="btn-primary !text-xs !py-1.5 !px-3 mt-2 flex items-center gap-1.5"
          >
            <Network size={14} />
            <span>Switch to Dependency Graph</span>
          </button>
        </div>
      </div>
    );
  }

  // ── Error State ──
  if (error) {
    return (
      <div
        data-testid="mindmap-error-state"
        className="w-full h-full flex flex-col items-center justify-center p-6 bg-bg-base text-center"
      >
        <div className="max-w-md p-6 bg-bg-panel border-[1.5px] border-border-subtle rounded-xl shadow-md flex flex-col items-center gap-3">
          <AlertCircle size={32} className="text-accent-rose" />
          <h2 className="font-extrabold text-base text-text-primary">
            Could Not Load Mind Map
          </h2>
          <p className="text-xs text-text-secondary leading-relaxed font-mono">
            {error}
          </p>
          <div className="flex items-center gap-2 mt-2">
            <button
              type="button"
              onClick={fetchMindmap}
              className="btn-primary !text-xs !py-1.5 !px-3 flex items-center gap-1.5"
            >
              <RotateCcw size={13} />
              <span>Retry</span>
            </button>
            <button
              type="button"
              onClick={onSwitchToGraph}
              className="btn-secondary !text-xs !py-1.5 !px-3"
            >
              Back to Graph
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Loading State ──
  if (loading) {
    return (
      <div
        data-testid="mindmap-loading-state"
        className="w-full h-full flex flex-col items-center justify-center p-6 bg-bg-base text-center"
      >
        <div className="flex flex-col items-center gap-3">
          <div className="btn-spinner !w-6 !h-6" />
          <span className="text-xs font-mono text-text-muted">
            Building six-pillar mind map...
          </span>
        </div>
      </div>
    );
  }

  // ── Empty State ──
  const isEmpty =
    !payload?.root ||
    !payload.root.children ||
    payload.root.children.length === 0 ||
    payload.stats.files === 0;

  if (isEmpty) {
    return (
      <div
        data-testid="mindmap-empty-state"
        className="w-full h-full flex flex-col items-center justify-center p-6 bg-bg-base text-center"
      >
        <div className="max-w-md p-6 bg-bg-panel border-[1.5px] border-border-subtle rounded-xl shadow-md flex flex-col items-center gap-3">
          <FileQuestion size={32} className="text-text-muted" />
          <h2 className="font-extrabold text-base text-text-primary">
            No Files in Repository
          </h2>
          <p className="text-xs text-text-muted leading-relaxed">
            The active repository contains no parsed source files.
          </p>
          <button
            type="button"
            onClick={fetchMindmap}
            className="btn-secondary !text-xs !py-1.5 !px-3 mt-2 flex items-center gap-1.5"
          >
            <RotateCcw size={13} />
            <span>Refresh</span>
          </button>
        </div>
      </div>
    );
  }

  // Merge external and local impact states
  const effectiveBlastTarget = localBlastTarget ?? externalImpactTarget;
  const effectiveBlastDirect = [
    ...localBlastDirect,
    ...externalImpactDirect,
  ];
  const effectiveBlastTransitive = [
    ...localBlastTransitive,
    ...externalImpactTransitive,
  ];

  return (
    <div
      data-testid="mindmap-view"
      className="w-full h-full flex flex-col overflow-hidden bg-bg-base select-none"
    >
      {/* ── Toolbar ── */}
      <MindMapToolbar
        orientation={orientation}
        onToggleOrientation={() =>
          setOrientation((o) => (o === "TB" ? "LR" : "TB"))
        }
        onExpandAll={handleExpandAll}
        onCollapseAll={handleCollapseAll}
        onSwitchToGraph={onSwitchToGraph}
        onToggleOutline={() => setIsOutlineOpen((o) => !o)}
        isOutlineOpen={isOutlineOpen}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onFitView={fitView}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        searchMatchCount={searchResults.matches.length}
        currentMatchIndex={currentMatchIndex}
        onNextMatch={handleNextMatch}
        onPrevMatch={handlePrevMatch}
        truncated={payload?.truncated}
        omittedCount={payload?.omitted}
      />

      {/* ── Main Canvas + Outline Container ── */}
      <div className="relative flex-1 min-h-0 flex overflow-hidden">
        {/* Outline Side Panel */}
        {isOutlineOpen && (
          <MindMapOutline
            visibleTree={visibleTree}
            expandedIds={expandedIds}
            onToggleExpand={handleToggleExpand}
            selectedNodeId={selectedNodeId}
            onSelectNode={handleSelectNode}
            onClose={() => setIsOutlineOpen(false)}
          />
        )}

        {/* Canvas Area */}
        <div
          ref={canvasContainerRef}
          role="region"
          aria-label="Mind map canvas. Drag to pan, scroll to zoom."
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onWheel={handleWheel}
          className={`
            relative flex-1 h-full overflow-hidden outline-none
            ${isDragging ? "cursor-grabbing" : "cursor-grab"}
          `}
        >
          {/* Scalable & Pannable Mind Map Content */}
          <div
            className="absolute origin-top-left transition-transform duration-75 will-change-transform"
            style={{
              transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${scale})`,
              width: layout.width,
              height: layout.height,
            }}
          >
            {/* SVG Connector Lines */}
            <svg
              className="absolute inset-0 pointer-events-none"
              width={layout.width}
              height={layout.height}
              style={{ overflow: "visible" }}
            >
              {layout.links.map((link) => (
                <path
                  key={link.id}
                  d={link.d}
                  fill="none"
                  stroke="#141414"
                  strokeWidth="1.5"
                  strokeOpacity="0.35"
                />
              ))}
            </svg>

            {/* Render Layout Nodes */}
            {layout.nodes.map((layoutNode) => {
              const node = layoutNode.data;
              const hasChildren = expandableNodesMap.has(node.id);
              const childCount = expandableNodesMap.get(node.id) ?? 0;
              const isExpanded = expandedIds.has(node.id);
              const isSelected = selectedNodeId === node.id;
              const isSearchMatch = searchMatchIds.has(node.id);

              let impactState: ImpactHighlightState = null;
              const isBlastTarget =
                Boolean(effectiveBlastTarget) &&
                (effectiveBlastTarget === node.label ||
                  effectiveBlastTarget === node.id ||
                  effectiveBlastTarget === node.path);

              if (effectiveBlastTarget) {
                if (isBlastTarget) {
                  impactState = "target";
                } else if (
                  effectiveBlastDirect.includes(node.id) ||
                  (node.path && effectiveBlastDirect.includes(node.path)) ||
                  effectiveBlastDirect.includes(node.label)
                ) {
                  impactState = "direct";
                } else if (
                  effectiveBlastTransitive.includes(node.id) ||
                  (node.path && effectiveBlastTransitive.includes(node.path)) ||
                  effectiveBlastTransitive.includes(node.label)
                ) {
                  impactState = "transitive";
                } else {
                  impactState = "dim";
                }
              }

              return (
                <MindMapNode
                  key={node.id}
                  layoutNode={layoutNode}
                  isExpanded={isExpanded}
                  hasChildren={hasChildren}
                  childCount={childCount}
                  isSelected={isSelected}
                  impactState={impactState}
                  isSearchMatch={isSearchMatch}
                  onToggleExpand={handleToggleExpand}
                  onSelectNode={handleSelectNode}
                  onOpenInEditor={handleOpenInEditor}
                  onToggleBlastRadius={handleToggleBlastRadius}
                  isBlastTarget={isBlastTarget}
                  repoOwner={repoOwner}
                  repoName={repoName}
                  repoBranch={repoBranch}
                  localRoot={localRoot}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
