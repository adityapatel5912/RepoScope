/**
 * Skeleton.tsx
 * Shimmer loading placeholders (see .skeleton styles in app.css).
 */

export function SkeletonLine({ width = "100%" }: { width?: string }) {
  return <div className="skeleton skeleton-line" style={{ width }} />;
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="rounded-xl bg-bg-panel-alt border border-border-subtle px-3 py-3 mb-2">
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} width={i === lines - 1 ? "55%" : `${100 - i * 12}%`} />
      ))}
    </div>
  );
}
