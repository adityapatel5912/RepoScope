/**
 * RepoMapPanel.tsx
 * The context-savings readout.
 *
 * Milestone 8.1. This is the number the 2026 market for code intelligence
 * buys on: how many tokens does an agent burn to understand a repository?
 * Every competitor publishes one — `codegraph` claims 62% fewer tokens,
 * Repomix ~70%, GitNexus 88% fewer tool calls. RepoScope published none,
 * which meant a reviewer had no reason to believe RepoScope.
 *
 * The panel states the comparison plainly:
 *
 *     RepoScope map:  7,926 tokens
 *     Full repo:  2,006,931 tokens
 *     Reduction:  99.6%
 *
 * The baseline is MEASURED — the backend reads the repository and counts
 * its tokens — not extrapolated. When the baseline was truncated because
 * the repository is enormous, the panel says so rather than presenting a
 * partial number as a complete one.
 */
import { useEffect, useState } from "react";
import { Copy, FileText, Loader2, TriangleAlert } from "lucide-react";
import { getRepoMap, type RepoMapEntry, type RepoMapResponse } from "../api/analysis";
import { toast } from "./Toasts";

interface Props {
  /** Only fetch when a repository is loaded. */
  enabled: boolean;
  /**
   * Identifies the loaded repository.
   *
   * The map MUST be re-fetched when the repository changes. Without this
   * the panel would keep showing the previous repository's savings — the
   * same staleness bug the Insights panel had.
   */
  repoKey?: string;
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(value);
}

export default function RepoMapPanel({ enabled, repoKey }: Props) {
  const [data, setData] = useState<RepoMapResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    getRepoMap(8000)
      .then((response) => {
        if (cancelled) return;
        setData(response);
      })
      .catch(() => {
        if (!cancelled) setError("The repo map is unavailable");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, repoKey]);

  if (!enabled) return null;

  const copyMap = async () => {
    if (!data?.text) return;
    try {
      await navigator.clipboard.writeText(data.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
      toast.success("Repo map copied — paste it into your agent's prompt");
    } catch {
      toast.error("Could not copy the map. Select the text and copy it manually.");
    }
  };

  const reduction = data?.reduction_pct ?? 0;
  const entries: RepoMapEntry[] = data?.entries ?? [];

  return (
    <div className="card-flat !border-border-hairline px-3 py-2.5" data-testid="repo-map-panel">
      <div className="flex items-center justify-between mb-2">
        <p className="label-caps !text-[10px]">Agent context</p>
        {loading && <Loader2 size={11} className="animate-spin text-text-muted" />}
      </div>

      {error && <p className="text-[11px] text-text-muted">{error}</p>}

      {!error && data && !data.available && (
        <p className="text-[11px] text-text-muted">{data.reason}</p>
      )}

      {!error && data?.available && (
        <>
          {/* The headline number. It is the whole point of the panel, so
              it gets the emphasis — and it is stated with the two
              numbers it comes from, so it can be checked. */}
          <div className="flex items-baseline gap-1.5 mb-1">
            <span
              className="text-2xl font-bold leading-none text-accent-emerald"
              data-testid="repo-map-reduction"
            >
              {reduction.toFixed(1)}%
            </span>
            <span className="text-[10px] text-text-muted">less context</span>
          </div>

          <p className="text-[10px] text-text-muted leading-snug mb-2">
            RepoScope map{" "}
            <span className="font-mono text-text-secondary">
              {formatTokens(data.tokens)}
            </span>{" "}
            tokens · full repo{" "}
            <span className="font-mono text-text-secondary">
              {formatTokens(data.full_context_tokens)}
            </span>{" "}
            tokens
          </p>

          {data.baseline?.truncated && (
            <p className="text-[10px] text-accent-amber leading-snug mb-2 flex items-start gap-1">
              <TriangleAlert size={10} className="shrink-0 mt-0.5" />
              The baseline was measured over part of the repository, so the
              reduction is a floor rather than an exact figure.
            </p>
          )}

          {entries.length > 0 && (
            <>
              <p className="text-[10px] text-text-muted mb-1">
                {data.files_included} of {data.files_total} files, ranked by
                centrality
              </p>
              <ul className="flex flex-col gap-0.5 mb-2">
                {entries.slice(0, 5).map((entry) => (
                  <li
                    key={entry.path}
                    className="text-[10px] font-mono text-text-secondary truncate"
                    title={`${entry.path} — ${entry.symbols.join(", ")}`}
                  >
                    {entry.path}
                    <span className="opacity-60"> · {entry.layer}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <button
            onClick={() => void copyMap()}
            className="btn-ghost !text-[10px] w-full justify-center"
            title="Copy the plain-text repo map"
          >
            {copied ? (
              <>
                <Copy size={11} className="text-accent-emerald" /> Copied
              </>
            ) : (
              <>
                <FileText size={11} /> Copy repo map
              </>
            )}
          </button>
        </>
      )}

      {!error && !loading && !data && (
        <p className="text-[11px] text-text-muted leading-relaxed">
          Load a repository to see what RepoScope's map costs an agent,
          against what the whole codebase would.
        </p>
      )}
    </div>
  );
}
