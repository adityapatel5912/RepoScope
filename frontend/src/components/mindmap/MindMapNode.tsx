/**
 * MindMapNode.tsx
 * Canvas node container positioning the memoized card in the mindmap layout.
 */

import React, { memo } from "react";
import type { LayoutNode } from "../../lib/mindmapTypes";
import { MindMapNodeCard, type MindMapNodeCardProps } from "./MindMapNodeCard";

export interface MindMapNodeProps
  extends Omit<MindMapNodeCardProps, "node"> {
  layoutNode: LayoutNode;
}

export const MindMapNode: React.FC<MindMapNodeProps> = memo(
  ({
    layoutNode,
    isExpanded,
    hasChildren,
    childCount,
    isSelected,
    impactState,
    isSearchMatch,
    onToggleExpand,
    onSelectNode,
    onOpenInEditor,
    onToggleBlastRadius,
    isBlastTarget,
    repoOwner,
    repoName,
    repoBranch,
    localRoot,
  }) => {
    const left = layoutNode.x - layoutNode.width / 2;
    const top = layoutNode.y - layoutNode.height / 2;

    return (
      <div
        className="absolute z-10 select-none"
        style={{
          transform: `translate3d(${left}px, ${top}px, 0)`,
          width: layoutNode.width,
        }}
      >
        <MindMapNodeCard
          node={layoutNode.data}
          isExpanded={isExpanded}
          hasChildren={hasChildren}
          childCount={childCount}
          isSelected={isSelected}
          impactState={impactState}
          isSearchMatch={isSearchMatch}
          onToggleExpand={onToggleExpand}
          onSelectNode={onSelectNode}
          onOpenInEditor={onOpenInEditor}
          onToggleBlastRadius={onToggleBlastRadius}
          isBlastTarget={isBlastTarget}
          repoOwner={repoOwner}
          repoName={repoName}
          repoBranch={repoBranch}
          localRoot={localRoot}
        />
      </div>
    );
  },
);

MindMapNode.displayName = "MindMapNode";
