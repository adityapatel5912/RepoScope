/**
 * InsightsPanel.tsx
 * Surfaces the graph-intelligence findings in the sidebar.
 *
 * Milestones 7.1, 7.2, 7.3 and 1.3 compute four things the graph alone
 * cannot show:
 *
 *   cycles      dependency loops, at file level and at symbol level
 *   unreachable symbols that no entry point can reach
 *   hubs        the most central nodes, by PageRank
 *   hotspots    files that change often AND are widely depended upon
 *
 * The panel is deliberately honest. The unreachable count is labelled as
 * an estimate, because static analysis cannot see dynamic dispatch or
 * reflection — calling it "dead code" would be a lie.
 */
import { useEffect, useState } from "react";
import { AlertTriangle, Network, Unlink, Loader2 } from "lucide-react";
import {
  getCycles,
  getHubs,
  getUnreachable,
  type CycleDetail,
  type HubEntry,
  type UnreachableEntry,
} from "../api/analysis";

interface Props {
  /** Only fetch when a repository is loaded. */
  enabled: boolean;
  /**
   * Identifies the loaded repository.
   *
   * The analysis MUST be re-fetched when the repository changes, not
   * just when the panel first mounts. Without this the panel kept showing
   * the previous repository's numbers — a stale "Most central" list that
   * looked like it belonged to the repo on screen.
   */
  repoKey?: string;
  onSelectNode?: (nodeId: string) => void;
}

export default function InsightsPanel({ enabled, repoKey, onSelectNode }: Props) {
  const [cycles, setCycles] = useState<CycleDetail[] | null>(null);
  const [unreachable, setUnreachable] = useState<UnreachableEntry[] | null>(null);
  const [unreachableTotal, setUnreachableTotal] = useState(0);
  const [hubs, setHubs] = useState<HubEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([getCycles(), getUnreachable(), getHubs(6)])
      .then(([cycleResponse, unreachableResponse, hubResponse]) => {
        if (cancelled) return;
        setCycles(cycleResponse.available ? cycleResponse.cycles : []);
        setUnreachable(
          unreachableResponse.available ? unreachableResponse.unreachable : [],
        );
        setUnreachableTotal(unreachableResponse.total ?? 0);
        setHubs(hubResponse.available ? hubResponse.hubs : []);
      })
      .catch(() => {
        if (!cancelled) setError("Analysis unavailable");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // `repoKey` is in the dependency list on purpose — it is what makes
    // the panel re-fetch when a different repository is loaded.
  }, [enabled, repoKey]);

  if (!enabled) return null;

  const hasFindings =
    (cycles?.length ?? 0) > 0 || unreachableTotal > 0 || hubs.length > 0;

  return (
    <div className="card-flat !border-border-hairline px-3 py-2.5">
      <div className="flex items-center justify-between mb-2">
        <p className="label-caps !text-[10px]">Insights</p>
        {loading && <Loader2 size={11} className="animate-spin text-text-muted" />}
      </div>

      {error && (
        <p className="text-[11px] text-text-muted">{error}</p>
      )}

      {!error && !loading && !hasFindings && (
        <p className="text-[11px] text-text-muted leading-relaxed">
          No cycles, no unreachable symbols, and no central hubs detected.
        </p>
      )}

      {!error && (cycles?.length ?? 0) > 0 && (
        <div className="mb-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertTriangle size={11} className="text-accent-amber" />
            <span className="text-[11px] font-semibold text-text-primary">
              {cycles!.length} dependency cycle{cycles!.length === 1 ? "" : "s"}
            </span>
          </div>
          <ul className="flex flex-col gap-1">
            {cycles!.slice(0, 3).map((cycle) => (
              <li
                key={cycle.members.join("|")}
                className="text-[10px] text-text-secondary leading-snug"
              >
                <span
                  className="inline-block w-1.5 h-1.5 rounded-full mr-1 align-middle"
                  style={{
                    background: cycle.crosses_layers ? "#DC2626" : "#F59E0B",
                  }}
                />
                {cycle.length} nodes
                {cycle.crosses_layers && " — crosses layers"}
                {cycle.members[0].startsWith("file:")
                  ? " (files)"
                  : " (symbols)"}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!error && unreachableTotal > 0 && (
        <div className="mb-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <Unlink size={11} className="text-text-muted" />
            <span className="text-[11px] font-semibold text-text-primary">
              {unreachableTotal} unreachable symbol
              {unreachableTotal === 1 ? "" : "s"}
            </span>
          </div>
          <p className="text-[10px] text-text-muted leading-snug mb-1">
            A static estimate — dynamic dispatch and reflection are invisible
            to it.
          </p>
          <ul className="flex flex-col gap-0.5">
            {unreachable!.slice(0, 4).map((entry) => (
              <li key={entry.id}>
                <button
                  onClick={() => onSelectNode?.(entry.id)}
                  className="text-[10px] font-mono text-text-secondary hover:text-accent-cyan transition-colors text-left truncate max-w-full"
                  title={`${entry.file || ""} — ${entry.label}`}
                >
                  {/*
                    Several unreachable symbols can live in the same file,
                    so the symbol name is shown alongside the path —
                    otherwise the list reads as the same row repeated.
                  */}
                  {entry.file || entry.label}
                  {entry.label && entry.label !== entry.file && (
                    <span className="opacity-70"> · {entry.label}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!error && hubs.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <Network size={11} className="text-accent-cyan" />
            <span className="text-[11px] font-semibold text-text-primary">
              Most central
            </span>
          </div>
          <ul className="flex flex-col gap-0.5">
            {hubs.slice(0, 4).map((hub) => (
              <li
                key={hub.id}
                className="flex items-center justify-between gap-2 text-[10px]"
              >
                <button
                  onClick={() => onSelectNode?.(hub.id)}
                  className="font-mono text-text-secondary hover:text-accent-cyan transition-colors truncate text-left"
                  title={hub.file || hub.label}
                >
                  {hub.label}
                </button>
                <span className="font-mono text-text-muted shrink-0">
                  {(hub.pagerank * 100).toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
