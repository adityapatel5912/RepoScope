/**
 * mindmapLayout.ts
 * Pure tidy-tree layout computation using d3-hierarchy.
 * Computes exact (x, y) coordinates for nodes and smooth rounded step paths for connectors.
 * Supports Top-to-Bottom (TB, default) and Left-to-Right (LR).
 */

import { hierarchy, tree } from "d3-hierarchy";
import type {
  LayoutLink,
  LayoutNode,
  MindmapLayoutResult,
  MindmapNode,
  MindmapOrientation,
} from "./mindmapTypes";

export function getNodeDimensions(node: MindmapNode): { width: number; height: number } {
  switch (node.kind) {
    case "root":
      return { width: 200, height: 56 };
    case "pillar":
      return { width: 220, height: 76 };
    case "folder":
      return { width: 200, height: 48 };
    case "file":
      // File card contains header, role badge, and action buttons row (IDE + Impact)
      return { width: 240, height: 104 };
    case "symbol":
      return { width: 210, height: 44 };
    default:
      return { width: 200, height: 52 };
  }
}

/**
 * Generates a clean orthogonal step path with rounded corners (like React Flow / GraphView).
 */
export function generateSmoothStepPath(
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  orientation: MindmapOrientation = "LR",
  radius = 12,
): string {
  if (orientation === "TB") {
    const midY = Math.round((sy + ty) / 2);
    if (Math.abs(sx - tx) < 4) {
      return `M ${sx} ${sy} L ${tx} ${ty}`;
    }
    const r = Math.min(radius, Math.abs(midY - sy), Math.abs(tx - sx) / 2);
    const dirX = tx > sx ? 1 : -1;
    return `M ${sx} ${sy} L ${sx} ${midY - r} Q ${sx} ${midY} ${sx + dirX * r} ${midY} L ${tx - dirX * r} ${midY} Q ${tx} ${midY} ${tx} ${midY + r} L ${tx} ${ty}`;
  } else {
    const midX = Math.round((sx + tx) / 2);
    if (Math.abs(sy - ty) < 4) {
      return `M ${sx} ${sy} L ${tx} ${ty}`;
    }
    const r = Math.min(radius, Math.abs(midX - sx), Math.abs(ty - sy) / 2);
    const dirY = ty > sy ? 1 : -1;
    return `M ${sx} ${sy} L ${midX - r} ${sy} Q ${midX} ${sy} ${midX} ${sy + dirY * r} L ${midX} ${ty - dirY * r} Q ${midX} ${ty} ${midX + r} ${ty} L ${tx} ${ty}`;
  }
}

export function computeMindmapLayout(
  visibleTree: MindmapNode | null,
  orientation: MindmapOrientation = "TB",
): MindmapLayoutResult {
  if (!visibleTree) {
    return {
      nodes: [],
      links: [],
      width: 0,
      height: 0,
      minX: 0,
      minY: 0,
      maxX: 0,
      maxY: 0,
    };
  }

  // Build d3 hierarchy from visible tree clone
  const rootHierarchy = hierarchy<MindmapNode>(visibleTree, (d) => d.children);

  const isTB = orientation === "TB";

  // Spacing configuration:
  // In TB mode: dx is horizontal sibling gap (270px for 240px cards -> 30px gap)
  //             dy is vertical depth gap (160px)
  // In LR mode: dx is vertical sibling gap (132px for 104px cards -> 28px gap: ZERO OVERLAP!)
  //             dy is horizontal depth gap (320px for clean spacing)
  const siblingGap = isTB ? 270 : 132;
  const depthGap = isTB ? 160 : 320;

  const treeLayout = tree<MindmapNode>().nodeSize([siblingGap, depthGap]);
  treeLayout(rootHierarchy);

  // Collect raw layout nodes
  const rawNodes: LayoutNode[] = [];
  const nodeMap = new Map<string, LayoutNode>();

  rootHierarchy.each((d) => {
    const { width, height } = getNodeDimensions(d.data);

    // Map d.x and d.y depending on orientation
    const rawX = d.x ?? 0;
    const rawY = d.y ?? 0;

    let posX: number;
    let posY: number;

    if (isTB) {
      // In TB mode: align row tops cleanly
      posX = rawX;
      posY = rawY;
    } else {
      // In LR mode: align column lefts cleanly so cards at each depth line up
      posX = rawY;
      posY = rawX;
    }

    const layoutNode: LayoutNode = {
      id: d.data.id,
      data: d.data,
      x: posX,
      y: posY,
      width,
      height,
      depth: d.depth,
      children: [],
      parent: null,
    };

    rawNodes.push(layoutNode);
    nodeMap.set(layoutNode.id, layoutNode);
  });

  // Reconnect parent and children
  rootHierarchy.each((d) => {
    const current = nodeMap.get(d.data.id);
    if (!current) return;
    if (d.parent) {
      current.parent = nodeMap.get(d.parent.data.id) ?? null;
    }
    if (d.children) {
      current.children = d.children
        .map((c) => nodeMap.get(c.data.id))
        .filter((c): c is LayoutNode => Boolean(c));
    }
  });

  if (rawNodes.length === 0) {
    return {
      nodes: [],
      links: [],
      width: 0,
      height: 0,
      minX: 0,
      minY: 0,
      maxX: 0,
      maxY: 0,
    };
  }

  // Compute bounding box
  let minLeft = Infinity;
  let maxRight = -Infinity;
  let minTop = Infinity;
  let maxBottom = -Infinity;

  for (const n of rawNodes) {
    const left = n.x - n.width / 2;
    const right = n.x + n.width / 2;
    const top = n.y - n.height / 2;
    const bottom = n.y + n.height / 2;

    if (left < minLeft) minLeft = left;
    if (right > maxRight) maxRight = right;
    if (top < minTop) minTop = top;
    if (bottom > maxBottom) maxBottom = bottom;
  }

  const margin = 48;
  const offsetX = -minLeft + margin;
  const offsetY = -minTop + margin;

  // Normalize all node positions into positive coordinates
  for (const n of rawNodes) {
    n.x = Math.round(n.x + offsetX);
    n.y = Math.round(n.y + offsetY);
  }

  const totalWidth = Math.ceil(maxRight - minLeft + margin * 2);
  const totalHeight = Math.ceil(maxBottom - minTop + margin * 2);

  // Generate connector links with clean rounded step curves
  const links: LayoutLink[] = [];

  for (const child of rawNodes) {
    if (!child.parent) continue;
    const parent = child.parent;

    let dPath = "";
    if (isTB) {
      // Connect parent bottom-center to child top-center
      const sx = parent.x;
      const sy = Math.round(parent.y + parent.height / 2);
      const tx = child.x;
      const ty = Math.round(child.y - child.height / 2);
      dPath = generateSmoothStepPath(sx, sy, tx, ty, "TB");
    } else {
      // Connect parent right-center to child left-center
      const sx = Math.round(parent.x + parent.width / 2);
      const sy = parent.y;
      const tx = Math.round(child.x - child.width / 2);
      const ty = child.y;
      dPath = generateSmoothStepPath(sx, sy, tx, ty, "LR");
    }

    links.push({
      id: `${parent.id}->${child.id}`,
      source: parent,
      target: child,
      d: dPath,
    });
  }

  return {
    nodes: rawNodes,
    links,
    width: totalWidth,
    height: totalHeight,
    minX: margin,
    minY: margin,
    maxX: totalWidth - margin,
    maxY: totalHeight - margin,
  };
}
