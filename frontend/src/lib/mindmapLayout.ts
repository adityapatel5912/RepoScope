/**
 * mindmapLayout.ts
 * Pure tidy-tree layout computation using d3-hierarchy.
 * Computes exact (x, y) coordinates for nodes and smooth cubic bezier paths for connectors.
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

function getNodeDimensions(node: MindmapNode): { width: number; height: number } {
  switch (node.kind) {
    case "root":
      return { width: 200, height: 56 };
    case "pillar":
      return { width: 220, height: 74 };
    case "folder":
      return { width: 200, height: 48 };
    case "file":
      return { width: 240, height: 68 };
    case "symbol":
      return { width: 210, height: 42 };
    default:
      return { width: 200, height: 52 };
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

  // Spacing configuration
  // TB: dx is sibling gap (horizontal), dy is depth gap (vertical)
  // LR: dx is sibling gap (vertical), dy is depth gap (horizontal)
  const siblingGap = isTB ? 250 : 72;
  const depthGap = isTB ? 110 : 270;

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
    const posX = isTB ? rawX : rawY;
    const posY = isTB ? rawY : rawX;

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

  // Generate connector links with smooth cubic beziers
  const links: LayoutLink[] = [];

  for (const child of rawNodes) {
    if (!child.parent) continue;
    const parent = child.parent;

    let sx = parent.x;
    let sy = parent.y;
    let tx = child.x;
    let ty = child.y;
    let dPath = "";

    if (isTB) {
      // Connect parent bottom-center to child top-center
      sy = parent.y + parent.height / 2;
      ty = child.y - child.height / 2;
      const midY = (sy + ty) / 2;
      dPath = `M ${sx} ${sy} C ${sx} ${midY}, ${tx} ${midY}, ${tx} ${ty}`;
    } else {
      // Connect parent right-center to child left-center
      sx = parent.x + parent.width / 2;
      tx = child.x - child.width / 2;
      const midX = (sx + tx) / 2;
      dPath = `M ${sx} ${sy} C ${midX} ${sy}, ${midX} ${ty}, ${tx} ${ty}`;
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
