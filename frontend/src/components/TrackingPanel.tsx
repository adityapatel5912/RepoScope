import { useState, useEffect } from "react";
import {
  Radio,
  Flame,
  AlertTriangle,
  History,
  UserCheck,
  RefreshCw,
  GitBranch,
} from "lucide-react";
import {
  getHotspots,
  compareRefs,
  getIncidents,
  type HotspotsReport,
  type CompareResult,
  type IncidentRecord,
} from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";

interface Commit {
  sha: string;
  _type: string;
  commit?: { message?: string };
}

interface PR {
  id: number;
  number: number;
  title: string;
  state: string;
}

interface TrackingData {
  new_commits?: Commit[];
  pulls?: PR[];
  issues?: unknown[];
  releases?: unknown[];
}

interface Props {
  data: TrackingData | null;
}

const TYPE_COLOR: Record<string, string> = {
  breaking: "text-accent-rose bg-accent-rose/10 border-accent-rose/20",
  feat: "text-accent-emerald bg-accent-emerald/10 border-accent-emerald/20",
  fix: "text-accent-amber bg-accent-amber/10 border-accent-amber/20",
  chore: "text-text-muted bg-bg-panel-alt border-border-strong",
  docs: "text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20",
  refactor: "text-accent-violet bg-accent-violet/10 border-accent-violet/20",
  deps: "text-orange-400 bg-orange-400/10 border-orange-400/20",
  other: "text-text-muted bg-bg-panel-alt border-border-strong",
};

const RISK_BADGE: Record<string, string> = {
  critical: "text-white bg-accent-rose border-accent-rose",
  high: "text-accent-rose bg-accent-rose/15 border-accent-rose/30",
  medium: "text-accent-amber bg-accent-amber/15 border-accent-amber/30",
  low: "text-accent-emerald bg-accent-emerald/15 border-accent-emerald/30",
};

export default function TrackingPanel({ data }: Props) {
  const [view, setView] = useState<"hotspots" | "timemachine" | "incidents" | "feed">("hotspots");
  const [hotspots, setHotspots] = useState<HotspotsReport | null>(null);
  const [loadingHotspots, setLoadingHotspots] = useState(false);

  const [refA, setRefA] = useState("HEAD~10");
  const [refB, setRefB] = useState("HEAD");
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [comparing, setComparing] = useState(false);

  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [loadingIncidents, setLoadingIncidents] = useState(false);

  // Load hotspots when switching to hotspots view
  const fetchHotspots = async () => {
    setLoadingHotspots(true);
    try {
      const res = await getHotspots(50);
      setHotspots(res);
    } catch {
      // Graceful fallback
    } finally {
      setLoadingHotspots(false);
    }
  };

  // Run compare
  const runCompare = async (a = refA, b = refB) => {
    setComparing(true);
    try {
      const res = await compareRefs(a, b);
      setCompareResult(res);
      toast.success(`Compared ${a}..${b}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Compare failed";
      toast.error(msg);
    } finally {
      setComparing(false);
    }
  };

  // Load incidents
  const fetchIncidents = async () => {
    setLoadingIncidents(true);
    try {
      const res = await getIncidents(30);
      setIncidents(res.incidents || []);
    } catch {
      // Graceful fallback
    } finally {
      setLoadingIncidents(false);
    }
  };

  useEffect(() => {
    if (view === "hotspots" && !hotspots) void fetchHotspots();
    if (view === "timemachine" && !compareResult) void runCompare("HEAD~10", "HEAD");
    if (view === "incidents" && incidents.length === 0) void fetchIncidents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  const commits = data?.new_commits ?? [];

  return (
    <div className="px-4 py-4 border-b border-border-subtle flex flex-col gap-3 min-w-0">
      {/* Header and view modes */}
      <div className="flex items-center justify-between gap-1 flex-wrap">
        <div className="flex items-center gap-1.5 min-w-0">
          <Radio size={13} className="text-accent-cyan shrink-0" />
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted truncate">
            Repository Tracking & Git Intelligence
          </h3>
        </div>

        <div className="flex bg-bg-panel-alt rounded-md p-0.5 border border-border-hairline text-[10px] shrink-0">
          <button
            onClick={() => setView("hotspots")}
            className={`px-2 py-0.5 rounded transition-colors ${
              view === "hotspots" ? "bg-accent-cyan/20 text-accent-cyan font-bold" : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Hotspots
          </button>
          <button
            onClick={() => setView("timemachine")}
            className={`px-2 py-0.5 rounded transition-colors ${
              view === "timemachine" ? "bg-accent-cyan/20 text-accent-cyan font-bold" : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Time Machine
          </button>
          <button
            onClick={() => setView("incidents")}
            className={`px-2 py-0.5 rounded transition-colors ${
              view === "incidents" ? "bg-accent-cyan/20 text-accent-cyan font-bold" : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Incidents
          </button>
          <button
            onClick={() => setView("feed")}
            className={`px-2 py-0.5 rounded transition-colors ${
              view === "feed" ? "bg-accent-cyan/20 text-accent-cyan font-bold" : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Live Feed
          </button>
        </div>
      </div>

      {/* VIEW 1: Hotspots & Bus Factor */}
      {view === "hotspots" && (
        <div className="flex flex-col gap-3">
          {loadingHotspots && <SkeletonCard lines={3} />}

          {hotspots && (
            <>
              {/* Quadrant Summary */}
              <div className="grid grid-cols-4 gap-1.5 text-center text-[10px]">
                <div className="p-1.5 rounded-md bg-accent-rose/10 border border-accent-rose/30">
                  <div className="font-bold text-accent-rose">{hotspots.quadrant_summary.critical}</div>
                  <div className="text-2xs text-text-muted">Critical</div>
                </div>
                <div className="p-1.5 rounded-md bg-accent-amber/10 border border-accent-amber/30">
                  <div className="font-bold text-accent-amber">{hotspots.quadrant_summary.debt}</div>
                  <div className="text-2xs text-text-muted">Debt</div>
                </div>
                <div className="p-1.5 rounded-md bg-accent-cyan/10 border border-accent-cyan/30">
                  <div className="font-bold text-accent-cyan">{hotspots.quadrant_summary.active}</div>
                  <div className="text-2xs text-text-muted">Active</div>
                </div>
                <div className="p-1.5 rounded-md bg-accent-emerald/10 border border-accent-emerald/30">
                  <div className="font-bold text-accent-emerald">{hotspots.quadrant_summary.stable}</div>
                  <div className="text-2xs text-text-muted">Stable</div>
                </div>
              </div>

              {/* Bus Factor Warnings */}
              {hotspots.bus_factor_warnings.length > 0 && (
                <div className="p-2.5 rounded-lg border border-accent-amber/30 bg-accent-amber/10 flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-accent-amber">
                    <UserCheck size={13} />
                    <span>Bus Factor Single-Point-of-Failure Risk</span>
                  </div>
                  <p className="m-0 text-2xs text-text-muted leading-relaxed">
                    {hotspots.bus_factor_warnings.length} module(s) have &ge;80% of recent commits by a single contributor:
                  </p>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {hotspots.bus_factor_warnings.slice(0, 4).map((f) => (
                      <span key={f.path} className="px-1.5 py-0.5 rounded bg-bg-panel border border-border-subtle font-mono text-[10px] text-accent-amber">
                        {f.path.split("/").pop()} ({f.primary_author}: {Math.round(f.author_share * 100)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Ranked Hotspots */}
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted flex items-center gap-1">
                  <Flame size={12} className="text-accent-rose" /> Top Risk Hotspots (H = log10(churn + 1) × complexity)
                </span>

                <div className="flex flex-col gap-1.5">
                  {hotspots.files.slice(0, 6).map((f) => (
                    <div key={f.path} className="rounded-lg bg-bg-panel-alt border border-border-hairline p-2 flex items-center justify-between gap-2 min-w-0">
                      <div className="flex flex-col min-w-0 flex-1">
                        <span className="font-mono text-2xs text-text-primary truncate" title={f.path}>
                          {f.path}
                        </span>
                        <span className="text-[10px] text-text-muted">
                          churn: {f.churn_score} | branches: {f.complexity} | author: {f.primary_author}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="font-mono text-xs font-bold text-text-primary">
                          {f.hotspot_score}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-bold border ${RISK_BADGE[f.risk_level] || RISK_BADGE.low}`}>
                          {f.risk_level}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* VIEW 2: Time Machine (Compare) */}
      {view === "timemachine" && (
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center gap-1.5 text-2xs">
            <History size={12} className="text-accent-cyan" />
            <span className="font-semibold text-text-primary">Historical Compare</span>
          </div>

          <div className="flex items-center gap-1.5">
            <input
              type="text"
              value={refA}
              onChange={(e) => setRefA(e.target.value)}
              placeholder="Ref A (e.g. HEAD~10)"
              className="bg-bg-panel-alt border border-border-subtle rounded px-2 py-1 text-2xs font-mono flex-1 min-w-0 text-text-primary"
            />
            <span className="text-text-muted text-xs">..</span>
            <input
              type="text"
              value={refB}
              onChange={(e) => setRefB(e.target.value)}
              placeholder="Ref B (e.g. HEAD)"
              className="bg-bg-panel-alt border border-border-subtle rounded px-2 py-1 text-2xs font-mono flex-1 min-w-0 text-text-primary"
            />
            <button
              onClick={() => void runCompare(refA, refB)}
              disabled={comparing}
              className="btn-primary !py-1 !px-2.5 !text-2xs font-semibold shrink-0"
            >
              {comparing ? "..." : "Compare"}
            </button>
          </div>

          <div className="flex gap-1 text-[10px]">
            <button onClick={() => { setRefA("HEAD~5"); void runCompare("HEAD~5", "HEAD"); }} className="px-1.5 py-0.5 rounded border border-border-subtle hover:bg-bg-panel-hover text-text-muted">Last 5</button>
            <button onClick={() => { setRefA("HEAD~10"); void runCompare("HEAD~10", "HEAD"); }} className="px-1.5 py-0.5 rounded border border-border-subtle hover:bg-bg-panel-hover text-text-muted">Last 10</button>
            <button onClick={() => { setRefA("HEAD~20"); void runCompare("HEAD~20", "HEAD"); }} className="px-1.5 py-0.5 rounded border border-border-subtle hover:bg-bg-panel-hover text-text-muted">Last 20</button>
          </div>

          {compareResult && (
            <div className="flex flex-col gap-2 border-t border-border-hairline pt-2">
              <div className="p-2 rounded bg-bg-panel-alt border border-border-subtle text-2xs font-mono text-accent-cyan">
                {compareResult.summary}
              </div>

              {compareResult.architectural_drift.length > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] uppercase font-bold text-accent-amber flex items-center gap-1">
                    <GitBranch size={11} /> Architectural Drift
                  </span>
                  {compareResult.architectural_drift.map((d, i) => (
                    <div key={i} className="text-2xs text-text-muted flex items-start gap-1">
                      <span className="text-accent-cyan">•</span>
                      <span>{d}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-col gap-1">
                <span className="text-[10px] uppercase text-text-muted">Modified Files ({compareResult.modified_files.length})</span>
                <div className="max-h-32 overflow-y-auto flex flex-col gap-1">
                  {compareResult.modified_files.map((f) => (
                    <div key={f} className="text-2xs font-mono text-text-secondary truncate">{f}</div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* VIEW 3: Incident Triage */}
      {view === "incidents" && (
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <span className="text-2xs font-semibold text-text-primary flex items-center gap-1">
              <AlertTriangle size={12} className="text-accent-rose" /> Incident Triage Log
            </span>
            <button onClick={() => void fetchIncidents()} className="text-text-muted hover:text-text-primary">
              <RefreshCw size={11} className={loadingIncidents ? "animate-spin" : ""} />
            </button>
          </div>

          {incidents.length === 0 ? (
            <p className="text-2xs text-text-muted m-0">No active incidents recorded. Systems healthy.</p>
          ) : (
            <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
              {incidents.map((inc) => (
                <div key={inc.id} className="rounded-lg bg-bg-panel-alt border border-border-hairline p-2 flex flex-col gap-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-2xs font-bold text-text-primary">{inc.event_type}</span>
                    <span className={`px-1 py-0.2 rounded text-[9px] uppercase font-bold border ${RISK_BADGE[inc.severity] || RISK_BADGE.low}`}>
                      {inc.severity}
                    </span>
                  </div>
                  <p className="m-0 text-2xs text-text-muted leading-relaxed">
                    <span className="font-semibold text-accent-cyan">Triage:</span> {inc.triage}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* VIEW 4: Live Feed (Existing Commit / PR List) */}
      {view === "feed" && (
        <div className="flex flex-col gap-2">
          {commits.length === 0 ? (
            <p className="text-xs text-text-muted">No new commits since last check.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {commits.map((c) => {
                const typeClass = TYPE_COLOR[c._type] ?? TYPE_COLOR.other;
                return (
                  <li key={c.sha} className="flex items-start gap-2 min-w-0">
                    <code className="shrink-0 font-mono text-[10px] text-text-muted bg-bg-panel-alt border border-border-subtle px-1.5 py-0.5 rounded">
                      {c.sha.slice(0, 7)}
                    </code>
                    <span className={`shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${typeClass}`}>
                      {c._type}
                    </span>
                    <span className="text-xs text-text-muted leading-tight truncate min-w-0 flex-1" title={c.commit?.message?.split("\n")[0]}>
                      {c.commit?.message?.split("\n")[0]}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
