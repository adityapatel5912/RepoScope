/**
 * ImpactPanel.tsx
 * Agentic "What-If" Impact Analysis — ask what breaks if you change a
 * function/class; get blast radius, risk score, and graph highlighting.
 */
import { useEffect, useRef, useState } from "react";
import { analyzeImpact, type Impact, type ImpactNode } from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";
import { Zap, X, ChevronDown } from "lucide-react";

export interface ImpactRequest {
  target: string;
  ts: number;
}

interface Props {
  onHighlightImpact?: (
    targetId: string | null,
    directIds: string[],
    transitiveIds: string[]
  ) => void;
  request?: ImpactRequest | null;
}

// Risk badge styles per level
const RISK_BADGE: Record<Impact["risk_level"], string> = {
  low:      "text-accent-emerald border-accent-emerald/30 bg-accent-emerald/10",
  medium:   "text-accent-amber   border-accent-amber/30   bg-accent-amber/10",
  high:     "text-orange-700     border-orange-400/40    bg-orange-100",
  critical: "text-accent-rose    border-accent-rose/40    bg-accent-rose/15 risk-pulse",
};

export default function ImpactPanel({ onHighlightImpact, request }: Props) {
  const [target, setTarget]   = useState("");
  const [impact, setImpact]   = useState<Impact | null>(null);
  const [loading, setLoading] = useState(false);
  const requestIdRef           = useRef(0);
  const [error, setError]     = useState<string | null>(null);
  const [depth, setDepth]     = useState(3);

  const analyze = async (override?: string) => {
    const t = (override ?? target).trim();
    if (!t || loading) return;
    if (t.length > 100) {
      setError('Impact target must be 100 characters or fewer');
      return;
    }
    const reqId = ++requestIdRef.current;
    setTarget(t);
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeImpact(t, depth);
      if (reqId !== requestIdRef.current) return;  // stale
      setImpact(data);
      onHighlightImpact?.(
        data.target.id,
        data.direct_impacts.map((d: ImpactNode) => d.id),
        data.transitive_impacts.map((tr: ImpactNode) => tr.id)
      );
      toast.success(`Analysis complete — ${data.total_impacted} impacted`);
    } catch (e: unknown) {
      if (reqId !== requestIdRef.current) return;  // stale
      const msg = e instanceof Error ? e.message : "Analysis failed";
      setError(msg);
      setImpact(null);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setImpact(null);
    setError(null);
    onHighlightImpact?.(null, [], []);
  };

  // External request (e.g. "Analyze impact" in the node drawer)
  useEffect(() => {
    if (request?.target) analyze(request.target);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request?.ts]);

  return (
    <div className="card p-4 flex flex-col gap-3">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h3 className="label-caps flex items-center gap-1.5">
          <Zap size={12} className="text-accent-amber" />
          What-If Impact
        </h3>
        {impact && (
          <button
            onClick={clear}
            title="Clear analysis"
            aria-label="Clear analysis"
            className="w-6 h-6 flex items-center justify-center rounded-md
              text-text-muted hover:text-text-primary hover:bg-bg-panel-hover
              transition-all duration-150"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* ── Input row ── */}
      <div className="flex gap-2 items-center">
        <input
          id="impact-target-input" maxLength={100}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && analyze()}
          placeholder="e.g., process_payment, UserService"
          disabled={loading}
          aria-label="Impact target"
          className="
            flex-1 min-w-0 px-3 py-2 rounded-lg text-xs font-mono
            bg-bg-panel-alt border border-border-subtle
            text-text-primary placeholder:text-text-muted placeholder:font-sans
            focus:outline-none focus:border-accent-amber/50 focus:ring-1 focus:ring-accent-amber/20
            disabled:opacity-50 transition-all duration-200
          "
        />
        <button
          onClick={() => analyze()}
          disabled={loading || !target.trim()}
          className="
            flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold
            bg-accent-amber/10 border border-accent-amber/25 text-accent-amber
            hover:bg-accent-amber/20 disabled:opacity-40 disabled:cursor-not-allowed
            transition-all duration-200 whitespace-nowrap shrink-0
          "
        >
          {loading ? <span className="btn-spinner" /> : null}
          {loading ? "Scanning" : "Analyze"}
        </button>
      </div>

      {/* ── Depth slider ── */}
      <div className="flex items-center gap-2 mt-2.5 text-2xs text-text-muted">
        <label htmlFor="impact-depth">Depth: <span className="text-accent-amber font-mono">{depth}</span></label>
        <input
          id="impact-depth"
          type="range"
          min={1}
          max={5}
          value={depth}
          onChange={(e) => setDepth(Number(e.target.value))}
          className="flex-1 accent-[#F0503C] h-1"
        />
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="
          mt-2.5 px-3 py-2 rounded-lg text-xs
          bg-accent-rose/10 border border-accent-rose/25 text-accent-rose
        ">
          {error}
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loading && !impact && (
        <div className="mt-2.5">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={3} />
        </div>
      )}

      {/* ── Result ── */}
      {impact && (
        <div className="mt-3">
          {/* Risk badge */}
          <div className="flex items-center justify-between mb-2">
            <span className={`
              inline-block px-2.5 py-1 rounded-lg border text-2xs font-bold
              uppercase tracking-[0.08em]
              ${RISK_BADGE[impact.risk_level]}
            `}>
              {impact.risk_level} · {impact.risk_score}/10
            </span>
            <span className="text-2xs text-text-muted font-mono">
              {impact.total_impacted} impacted
            </span>
          </div>

          {/* Narrative */}
          <p className="text-xs text-text-muted leading-relaxed m-0 mb-2.5">
            {impact.narrative}
          </p>

          {/* Stats chips */}
          <div className="flex gap-1.5 flex-wrap mb-2.5">
            <span className="px-2 py-0.5 rounded bg-accent-rose/10 text-accent-rose text-2xs font-mono">
              ● {impact.direct_impacts.length} direct
            </span>
            <span className="px-2 py-0.5 rounded bg-accent-amber/10 text-accent-amber text-2xs font-mono">
              ● {impact.transitive_impacts.length} transitive
            </span>
          </div>

          {/* Direct impacts */}
          {impact.direct_impacts.length > 0 && (
            <details open className="mb-1.5 group">
              <summary className="
                flex items-center gap-1 cursor-pointer select-none
                text-2xs font-semibold uppercase tracking-wider text-accent-rose/80 py-1
              ">
                <ChevronDown size={11} className="transition-transform group-open:rotate-180" />
                Direct impacts
              </summary>
              <ul className="list-none p-0 m-1 max-h-40 overflow-y-auto">
                {impact.direct_impacts.slice(0, 20).map((d) => (
                  <li key={d.id} className="py-0.5 text-2xs leading-snug text-text-muted">
                    <code className="text-accent-cyan font-mono">{d.file || d.id}</code>
                    {" "}· {d.label}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* Transitive impacts */}
          {impact.transitive_impacts.length > 0 && (
            <details className="mb-1.5 group">
              <summary className="
                flex items-center gap-1 cursor-pointer select-none
                text-2xs font-semibold uppercase tracking-wider text-accent-amber/80 py-1
              ">
                <ChevronDown size={11} className="transition-transform group-open:rotate-180" />
                Transitive impacts
              </summary>
              <ul className="list-none p-0 m-1 max-h-40 overflow-y-auto">
                {impact.transitive_impacts.slice(0, 20).map((t) => (
                  <li key={t.id} className="py-0.5 text-2xs leading-snug text-text-muted">
                    <code className="text-accent-cyan font-mono">{t.file || t.id}</code>
                    {" "}· {t.label}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* Suggested tests */}
          {impact.suggested_tests.length > 0 && (
            <div className="mt-2 pt-2 border-t border-border-subtle">
              <h4 className="m-0 mb-1 text-2xs font-semibold uppercase tracking-wider text-accent-emerald">
                Tests to run
              </h4>
              <ul className="list-none p-0 m-0">
                {impact.suggested_tests.map((t) => (
                  <li key={t} className="py-0.5">
                    <code className="text-accent-emerald/80 font-mono text-2xs break-all">{t}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* ── Empty hint ── */}
      {!impact && !loading && !error && (
        <p className="mt-2 text-2xs text-text-muted leading-relaxed">
          See the full blast radius before you change a line.
        </p>
      )}
    </div>
  );
}
