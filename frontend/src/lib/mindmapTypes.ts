/**
 * mindmapTypes.ts
 * Pure TypeScript definitions for the vertical six-pillar mind map.
 * Matches the frozen GET /api/mindmap contract in docs/API.md and plan §4.
 */

export type MindmapPillarId =
  | "frontend"
  | "backend"
  | "data"
  | "infrastructure"
  | "tests"
  | "docs";

export type MindmapNodeKind = "root" | "pillar" | "folder" | "file" | "symbol";

export type MindmapOrientation = "TB" | "LR";

export type ImpactHighlightState = "target" | "direct" | "transitive" | "dim" | null;

export interface MindmapMetrics {
  files: number;
  symbols: number;
  routes: number;
}

export interface MindmapRoute {
  method: string;
  path: string;
  line?: number;
}

export interface MindmapNode {
  id: string;
  kind: MindmapNodeKind;
  label: string;
  parent_id: string | null;
  children: MindmapNode[];

  // Kind-specific optional fields:
  pillar?: MindmapPillarId;
  description?: string;
  metrics?: MindmapMetrics;
  path?: string;
  line?: number;
  end_line?: number;
  role?: string;
  language?: string;
  pagerank?: number;
  route_count?: number;
  routes?: MindmapRoute[];
}

export interface MindmapPillarDescriptor {
  id: MindmapPillarId;
  label: string;
  description: string;
  file_count: number;
}

export interface MindmapStats {
  files: number;
  symbols: number;
  pillars: number;
  routes: number;
  api_calls: number;
}

export interface MindmapSource {
  nodes: number;
  edges: number;
  root: string | null;
}

export interface MindmapPayload {
  schema_version: number;
  generated_at: string;
  source: MindmapSource;
  stats: MindmapStats;
  pillars: MindmapPillarDescriptor[];
  root: MindmapNode;
  truncated: boolean;
  omitted: number;
  max_nodes: number;
}

export interface LayoutNode {
  id: string;
  data: MindmapNode;
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
  children?: LayoutNode[];
  parent?: LayoutNode | null;
}

export interface LayoutLink {
  id: string;
  source: LayoutNode;
  target: LayoutNode;
  d: string;
}

export interface MindmapLayoutResult {
  nodes: LayoutNode[];
  links: LayoutLink[];
  width: number;
  height: number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}
