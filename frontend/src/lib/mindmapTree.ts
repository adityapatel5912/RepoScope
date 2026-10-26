/**
 * mindmapTree.ts
 * Pure tree operations for the hierarchical mind map:
 * visibility filtering, expand/collapse sets, ancestor paths, search matching.
 */

import type { MindmapNode } from "./mindmapTypes";

/**
 * Returns the default expanded node IDs on first paint:
 * only the root and its direct pillar children.
 */
export function getInitialExpandedIds(root: MindmapNode): Set<string> {
  const set = new Set<string>();
  if (!root) return set;
  set.add(root.id);
  for (const pillar of root.children || []) {
    set.add(pillar.id);
  }
  return set;
}

/**
 * Prunes the full hierarchical tree to only include visible branches.
 * A node's children are only kept if `expandedIds` contains the node's id.
 */
export function filterVisibleTree(
  root: MindmapNode,
  expandedIds: Set<string>,
): MindmapNode {
  if (!root) return root;

  function prune(node: MindmapNode): MindmapNode {
    const isExpanded = expandedIds.has(node.id);
    if (!isExpanded || !node.children || node.children.length === 0) {
      return {
        ...node,
        children: [],
      };
    }
    return {
      ...node,
      children: node.children.map(prune),
    };
  }

  return prune(root);
}

/**
 * Recursively find a node by its ID.
 */
export function findNodeById(root: MindmapNode, id: string): MindmapNode | null {
  if (!root) return null;
  if (root.id === id) return root;
  for (const child of root.children || []) {
    const found = findNodeById(child, id);
    if (found) return found;
  }
  return null;
}

/**
 * Find all ancestor node IDs for a given target ID.
 * Returns array of IDs from root down to direct parent.
 */
export function findAncestors(root: MindmapNode, targetId: string): string[] {
  const ancestors: string[] = [];

  function dfs(curr: MindmapNode): boolean {
    if (curr.id === targetId) {
      return true;
    }
    for (const child of curr.children || []) {
      if (dfs(child)) {
        ancestors.push(curr.id);
        return true;
      }
    }
    return false;
  }

  dfs(root);
  return ancestors.reverse();
}

/**
 * Collect all IDs of nodes that have at least one child (expandable nodes).
 */
export function getAllExpandableIds(root: MindmapNode): Set<string> {
  const set = new Set<string>();

  function dfs(node: MindmapNode) {
    if (node.children && node.children.length > 0) {
      set.add(node.id);
      for (const child of node.children) {
        dfs(child);
      }
    }
  }

  dfs(root);
  return set;
}

/**
 * Pre-order flat list of all nodes in a tree.
 */
export function flattenVisibleTree(node: MindmapNode): MindmapNode[] {
  const result: MindmapNode[] = [];

  function dfs(curr: MindmapNode) {
    if (!curr) return;
    result.push(curr);
    for (const child of curr.children || []) {
      dfs(child);
    }
  }

  dfs(node);
  return result;
}

export interface SearchResult {
  matches: MindmapNode[];
  ancestorIds: Set<string>;
}

/**
 * Search the full tree by query string.
 * Matches case-insensitively against node.label and node.path.
 * Returns matching nodes and all ancestor IDs required to expand their paths.
 */
export function searchTree(root: MindmapNode, query: string): SearchResult {
  const q = query.trim().toLowerCase();
  const matches: MindmapNode[] = [];
  const ancestorIds = new Set<string>();

  if (!q || !root) {
    return { matches, ancestorIds };
  }

  // Pre-calculate parent map for fast ancestor lookup
  const parentMap = new Map<string, string>();
  function buildParentMap(node: MindmapNode) {
    for (const child of node.children || []) {
      parentMap.set(child.id, node.id);
      buildParentMap(child);
    }
  }
  buildParentMap(root);

  function dfs(node: MindmapNode) {
    const labelMatch = node.label.toLowerCase().includes(q);
    const pathMatch = node.path ? node.path.toLowerCase().includes(q) : false;

    if (labelMatch || pathMatch) {
      matches.push(node);
      // Collect ancestors up to root
      let currId: string | undefined = node.id;
      while (currId && parentMap.has(currId)) {
        const nextParentId: string = parentMap.get(currId)!;
        ancestorIds.add(nextParentId);
        currId = nextParentId;
      }
    }

    for (const child of node.children || []) {
      dfs(child);
    }
  }

  dfs(root);
  return { matches, ancestorIds };
}
