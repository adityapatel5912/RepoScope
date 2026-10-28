/**
 * SecurityPanel.tsx
 * Six-Engine Graph-Contextual Security Suite (V2.8)
 *
 * Engines:
 *   1. Cross-File Taint Propagation (source -> propagator -> sink trace)
 *   2. Hardcoded Secrets & Shannon Entropy (H >= 4.2) with strict <redacted> masking
 *   3. Offline Dependency CVEs (curated local OSV advisory map)
 *   4. Injection Sinks (SQL, Command Injection, Code Eval, Path Traversal)
 *   5. Insecure Configuration & CORS (Wildcard CORS, Disabled SSL, Debug Flags)
 *   6. Permission & Authentication Bypass (State-mutating routes without auth guards)
 *
 * Features:
 *   - Tab switcher hosting TrackingPanel next to SecurityPanel
 *   - Category filtering across all 6 engines + breaking changes
 *   - Severity level filters (Critical, High, Medium, Low)
 *   - Step-by-step Taint Flow Trace diagram
 *   - Non-destructive suggested patch viewer with AST syntax verification & copy
 *   - OASIS SARIF 2.1.0 export
 */
import { useEffect, useState } from "react";
import {
  securityScan,
  fetchSecurityPatch,
  fetchSecuritySarif,
  type SecurityScan,
  type SecurityFlag,
  type SecurityPatch,
} from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";
import TrackingPanel from "./TrackingPanel";
import {
  ShieldAlert,
  ShieldCheck,
  Radio,
  ScanSearch,
  RefreshCw,
  Download,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileCode,
  ArrowRight,
  Flame,
  KeyRound,
  Shield,
  Code2,
  Settings,
  Lock,
} from "lucide-react";

interface Props {
  /** Tracking results from the SSE stream (existing feature). */
  trackingData: unknown;
  /** owner/repo of the loaded repository. */
  repo: string | null;
}

type Tab = "tracking" | "security";

const ENGINE_LABELS: Record<string, { label: string; icon: any }> = {
  all:              { label: "All", icon: ShieldAlert },
  cross_file_taint: { label: "Taint Flow", icon: Flame },
  secrets_entropy:  { label: "Secrets", icon: KeyRound },
  dependency_cve:   { label: "CVEs", icon: Shield },
  injection_sinks:  { label: "Injections", icon: Code2 },
  insecure_config:  { label: "Config", icon: Settings },
  auth_bypass:      { label: "Auth Bypass", icon: Lock },
  breaking:         { label: "Breaking", icon: FileCode },
};

const SEV_BADGE: Record<string, string> = {
  critical: "text-white bg-accent-rose font-bold",
  high:     "text-accent-rose bg-accent-rose/15 font-semibold",
  medium:   "text-accent-amber bg-accent-amber/15 font-medium",
  low:      "text-text-muted bg-bg-panel-alt",
};

const TYPE_BADGE: Record<string, string> = {
  SECRET:      "text-accent-rose border-accent-rose/30 bg-accent-rose/10",
  BREAKING:    "text-accent-amber border-accent-amber/30 bg-accent-amber/10",
  CVE:         "text-orange-600 border-orange-400/40 bg-orange-100",
  TAINT:       "text-red-500 border-red-500/30 bg-red-500/10",
  INJECTION:   "text-rose-600 border-rose-500/30 bg-rose-500/10",
  CONFIG:      "text-yellow-600 border-yellow-500/30 bg-yellow-500/10",
  AUTH_BYPASS: "text-purple-500 border-purple-500/30 bg-purple-500/10",
};

export default function SecurityPanel({ trackingData, repo }: Props) {
  const [tab, setTab] = useState<Tab>("tracking");
  const [scan, setScan] = useState<SecurityScan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedEngine, setSelectedEngine] = useState<string>("all");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");

  // Expanded patches state: flag_index -> SecurityPatch | "loading"
  const [patchMap, setPatchMap] = useState<Record<number, SecurityPatch | "loading">>({});
  const [copiedPatchIdx, setCopiedPatchIdx] = useState<number | null>(null);

  const runScan = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const data = await securityScan();
      setScan(data);
      const count = data.total_flags;
      toast.success(
        `6-Engine Scan complete — ${count} finding${count === 1 ? "" : "s"} identified`,
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Scan failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleExportSarif = async () => {
    try {
      const sarifData = await fetchSecuritySarif();
      const jsonStr = JSON.stringify(sarifData, null, 2);
      // Trigger download
      const blob = new Blob([jsonStr], { type: "application/sarif+json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "reposcope-security.sarif";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      await navigator.clipboard.writeText(jsonStr);
      toast.success("SARIF 2.1.0 report downloaded and copied to clipboard");
    } catch (e) {
      toast.error("Failed to export SARIF report");
    }
  };

  const handleTogglePatch = async (f: SecurityFlag, index: number) => {
    if (patchMap[index]) {
      setPatchMap((prev) => {
        const copy = { ...prev };
        delete copy[index];
        return copy;
      });
      return;
    }

    setPatchMap((prev) => ({ ...prev, [index]: "loading" }));
    try {
      const patch = await fetchSecurityPatch({
        file: f.file,
        line: f.line,
        engine: f.engine || f.type,
        detail: f.detail,
        type: f.type,
      });
      setPatchMap((prev) => ({ ...prev, [index]: patch }));
    } catch (e) {
      toast.error("Failed to generate remediation patch");
      setPatchMap((prev) => {
        const copy = { ...prev };
        delete copy[index];
        return copy;
      });
    }
  };

  const handleCopyPatch = async (diff: string, index: number) => {
    await navigator.clipboard.writeText(diff);
    setCopiedPatchIdx(index);
    toast.success("Remediation patch copied to clipboard");
    setTimeout(() => setCopiedPatchIdx(null), 2500);
  };

  // Listen for chat action events
  useEffect(() => {
    const handleOpenTab = () => {
      setTab("security");
      if (!scan && !busy && repo) {
        void runScan();
      }
    };
    const handleExport = () => {
      setTab("security");
      void handleExportSarif();
    };
    window.addEventListener("reposcope:open-security-tab", handleOpenTab);
    window.addEventListener("reposcope:export-sarif", handleExport);
    return () => {
      window.removeEventListener("reposcope:open-security-tab", handleOpenTab);
      window.removeEventListener("reposcope:export-sarif", handleExport);
    };
  }, [scan, busy, repo]);

  const summary = scan?.summary;

  // Filter flags
  const flags = (scan?.flags || []).filter((f) => {
    if (selectedEngine !== "all") {
      const eng = f.engine || f.type.toLowerCase();
      if (eng !== selectedEngine && f.type.toLowerCase() !== selectedEngine) return false;
    }
    if (selectedSeverity !== "all" && f.severity !== selectedSeverity) {
      return false;
    }
    return true;
  });

  return (
    <div className="card p-4 flex flex-col gap-3 overflow-hidden min-w-0">
      {/* ── Tab bar: Tracking | Security ── */}
      <div className="flex items-center gap-1 p-0.5 rounded-lg bg-bg-panel-alt border border-border-hairline">
        {([
          { id: "tracking" as Tab, label: "Tracking", icon: <Radio size={11} /> },
          { id: "security" as Tab, label: "Security Suite", icon: <ShieldAlert size={11} /> },
        ]).map(({ id, label, icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`
              flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md
              text-2xs font-semibold uppercase tracking-wider transition-all duration-150
              ${tab === id
                ? "bg-bg-panel text-text-primary border border-border-subtle shadow-sm"
                : "text-text-muted hover:text-text-primary"}
            `}
          >
            {icon}
            {label}
            {id === "security" && scan && summary && (
              <span className={`
                font-mono px-1 rounded text-[9px]
                ${(summary.critical + summary.high) > 0
                  ? "bg-accent-rose/20 text-accent-rose font-bold"
                  : "bg-accent-emerald/15 text-accent-emerald"}
              `}>
                {scan.total_flags}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tracking tab (Hotspots, Time Machine, Incidents & Feed) ── */}
      {tab === "tracking" && (
        <div className="-mx-4 -my-4">
          <TrackingPanel data={trackingData as any} />
        </div>
      )}

      {/* ── Security Suite tab ── */}
      {tab === "security" && (
        <div className="flex flex-col gap-3">
          {/* Action buttons bar */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => void runScan()}
              disabled={busy || !repo}
              className="btn-primary flex-1 !py-1.5 !px-3 !text-xs justify-center"
            >
              {busy ? <span className="btn-spinner" /> : <ScanSearch size={12} />}
              {busy ? "Scanning 6 Engines…" : scan ? "Re-scan Repository" : "Run 6-Engine Audit"}
            </button>

            {scan && !busy && (
              <>
                <button
                  onClick={() => void handleExportSarif()}
                  title="Export SARIF 2.1.0"
                  aria-label="Export SARIF"
                  className="btn-secondary !py-1.5 !px-2.5 !text-xs flex items-center gap-1.5"
                >
                  <Download size={12} />
                  <span>SARIF</span>
                </button>
                <button
                  onClick={() => void runScan()}
                  title="Re-scan"
                  aria-label="Re-scan"
                  className="btn-ghost w-7 h-7 !p-0 items-center justify-center"
                >
                  <RefreshCw size={12} />
                </button>
              </>
            )}
          </div>

          {error && (
            <div className="px-3 py-2 rounded-lg text-xs bg-accent-rose/10 border border-accent-rose/25 text-accent-rose">
              {error}
            </div>
          )}

          {busy && !scan && <SkeletonCard lines={4} />}

          {scan && summary && (
            <>
              {/* Severity breakdown chips */}
              <div className="flex flex-wrap items-center gap-1.5 py-1 border-b border-border-hairline">
                <span className="text-[10px] text-text-muted uppercase tracking-wider font-semibold mr-1">Severity:</span>
                {[
                  { id: "all", label: "All", count: scan.total_flags },
                  { id: "critical", label: "Critical", count: summary.critical, color: "text-accent-rose" },
                  { id: "high", label: "High", count: summary.high, color: "text-orange-600" },
                  { id: "medium", label: "Medium", count: summary.medium ?? 0, color: "text-accent-amber" },
                  { id: "low", label: "Low", count: summary.low ?? 0, color: "text-text-muted" },
                ].map(({ id, label, count, color }) => (
                  <button
                    key={id}
                    onClick={() => setSelectedSeverity(id)}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-all ${
                      selectedSeverity === id
                        ? "bg-bg-panel border-border-strong text-text-primary shadow-xs font-bold"
                        : "border-border-hairline bg-bg-panel-alt/50 text-text-muted hover:text-text-primary"
                    }`}
                  >
                    <span className={color}>{label}</span> ({count})
                  </button>
                ))}
              </div>

              {/* Engine filter tabs */}
              <div className="flex flex-wrap gap-1">
                {Object.entries(ENGINE_LABELS).map(([engKey, meta]) => {
                  const Icon = meta.icon;
                  const count =
                    engKey === "all"
                      ? scan.total_flags
                      : (summary.by_engine?.[engKey] ?? 0);
                  if (engKey !== "all" && count === 0) return null;

                  return (
                    <button
                      key={engKey}
                      onClick={() => setSelectedEngine(engKey)}
                      className={`
                        flex items-center gap-1 px-2 py-1 rounded text-2xs font-medium border transition-colors
                        ${selectedEngine === engKey
                          ? "bg-accent-primary/10 border-accent-primary/40 text-accent-primary font-semibold"
                          : "bg-bg-panel-alt border-border-hairline text-text-muted hover:text-text-primary"}
                      `}
                    >
                      <Icon size={10} />
                      <span>{meta.label}</span>
                      <span className="font-mono text-[9px] opacity-75">({count})</span>
                    </button>
                  );
                })}
              </div>

              {/* Finding list */}
              {flags.length === 0 ? (
                <div className="flex items-center gap-2 px-3 py-3 rounded-lg bg-accent-emerald/10 border border-accent-emerald/25">
                  <ShieldCheck size={16} className="text-accent-emerald shrink-0" />
                  <span className="text-xs text-accent-emerald font-semibold">
                    Clean — no security vulnerabilities matching current filter.
                  </span>
                </div>
              ) : (
                <div className="flex flex-col gap-2.5 overflow-y-auto max-h-96 pr-1">
                  {flags.map((f, i) => {
                    const patchState = patchMap[i];
                    return (
                      <div
                        key={i}
                        className="rounded-lg border border-border-subtle bg-bg-panel-alt/80 p-2.5 flex flex-col gap-1.5 transition-all shadow-xs"
                      >
                        {/* Header: Type, Engine, Severity, File:Line */}
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className={`text-2xs font-bold uppercase px-1.5 py-0.5 rounded border ${TYPE_BADGE[f.type] ?? ""}`}>
                            {f.type}
                          </span>
                          {f.cwe && (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-bg-panel border border-border-hairline text-text-secondary">
                              {f.cwe}
                            </span>
                          )}
                          <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded ${SEV_BADGE[f.severity] ?? ""}`}>
                            {f.severity}
                          </span>
                          <span
                            className="font-mono text-[10px] text-text-muted ml-auto truncate max-w-[150px]"
                            title={`${f.file}:${f.line}`}
                          >
                            {f.file}:{f.line}
                          </span>
                        </div>

                        {/* Detail & Suggestion */}
                        <p className="m-0 text-xs font-medium text-text-primary leading-snug break-words">
                          {f.detail}
                        </p>
                        <p className="m-0 text-2xs text-text-muted leading-relaxed break-words">
                          {f.suggestion}
                        </p>

                        {/* Taint Flow Trace Visualizer */}
                        {f.trace && (
                          <div className="mt-1 p-2 rounded-md bg-bg-panel border border-border-subtle flex flex-col gap-1.5">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-accent-rose flex items-center gap-1">
                              <Flame size={10} />
                              Taint Propagation Trace
                            </span>
                            <div className="flex flex-col gap-1 text-[10px] font-mono">
                              <div className="flex items-center gap-1 text-accent-rose">
                                <span className="w-1.5 h-1.5 rounded-full bg-accent-rose shrink-0" />
                                <span>Source:</span>
                                <span className="text-text-primary truncate">
                                  {f.trace.source_file}:{f.trace.source_line} ({f.trace.source_label})
                                </span>
                              </div>
                              {f.trace.propagators.map((p, pIdx) => (
                                <div key={pIdx} className="flex items-center gap-1 text-text-secondary pl-3">
                                  <ArrowRight size={9} className="text-text-muted shrink-0" />
                                  <span>Propagator:</span>
                                  <span className="text-text-primary truncate">
                                    {p.file}:{p.line} ({p.symbol} via {p.via})
                                  </span>
                                </div>
                              ))}
                              <div className="flex items-center gap-1 text-accent-amber">
                                <ArrowRight size={9} className="text-accent-amber shrink-0" />
                                <span className="font-bold">Sink:</span>
                                <span className="text-text-primary truncate font-bold">
                                  {f.trace.sink_file}:{f.trace.sink_line} ({f.trace.sink_label})
                                </span>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Patch Suggestions */}
                        {f.patch_available && (
                          <div className="mt-1 flex flex-col gap-1">
                            <button
                              onClick={() => void handleTogglePatch(f, i)}
                              className="self-start text-[10px] font-medium text-accent-primary hover:underline flex items-center gap-1"
                            >
                              <FileCode size={10} />
                              <span>{patchState ? "Hide Suggested Patch" : "View Suggested Patch"}</span>
                              {patchState ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                            </button>

                            {patchState === "loading" && (
                              <div className="p-2 rounded bg-bg-panel text-[10px] text-text-muted flex items-center gap-2">
                                <span className="btn-spinner" /> Generating verified patch…
                              </div>
                            )}

                            {typeof patchState === "object" && patchState !== null && (
                              <div className="p-2 rounded bg-bg-panel border border-border-subtle flex flex-col gap-1.5 text-2xs">
                                <div className="flex items-center justify-between">
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-accent-emerald flex items-center gap-1">
                                    <Check size={10} />
                                    {patchState.syntax_valid ? "AST Syntax Verified" : "Remediation Patch"}
                                  </span>
                                  <button
                                    onClick={() => void handleCopyPatch(patchState.diff, i)}
                                    className="btn-ghost !py-0.5 !px-1.5 !text-[10px] flex items-center gap-1"
                                    title="Copy unified diff"
                                  >
                                    {copiedPatchIdx === i ? <Check size={10} className="text-accent-emerald" /> : <Copy size={10} />}
                                    <span>{copiedPatchIdx === i ? "Copied" : "Copy Patch"}</span>
                                  </button>
                                </div>
                                <p className="m-0 text-[10px] text-text-muted">{patchState.explanation}</p>
                                <pre className="m-0 p-1.5 rounded bg-bg-canvas font-mono text-[9px] overflow-x-auto text-text-secondary leading-tight max-h-36">
                                  {patchState.diff.split("\n").map((line, lIdx) => (
                                    <div
                                      key={lIdx}
                                      className={
                                        line.startsWith("+")
                                          ? "text-emerald-400 bg-emerald-950/20"
                                          : line.startsWith("-")
                                          ? "text-rose-400 bg-rose-950/20"
                                          : line.startsWith("@@")
                                          ? "text-accent-cyan"
                                          : ""
                                      }
                                    >
                                      {line}
                                    </div>
                                  ))}
                                </pre>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              <p className="m-0 text-2xs text-text-muted leading-relaxed border-t border-border-hairline pt-2">
                RepoScope 6-Engine Security Suite: Cross-File Taint • Secrets & Entropy • Offline CVEs • Injection Sinks • Insecure Config • Auth Bypass. OASIS SARIF 2.1.0 compliant.
              </p>
            </>
          )}

          {!scan && !busy && !error && (
            <div className="flex flex-col gap-2 p-3 rounded-lg bg-bg-panel-alt border border-border-hairline text-2xs text-text-muted">
              <span className="font-semibold text-text-primary text-xs">Deterministic 6-Engine Security Suite</span>
              <ul className="m-0 pl-4 list-disc space-y-1">
                <li><strong>Cross-File Taint:</strong> Tracks untrusted inputs across module boundaries to sinks.</li>
                <li><strong>Secrets & Entropy:</strong> Identifies high-entropy credentials (H &ge; 4.2) with strict redaction.</li>
                <li><strong>Offline CVEs:</strong> Bundled local OSV dependency advisory database without external queries.</li>
                <li><strong>Injection Sinks:</strong> Detects SQL interpolation, subprocess shell execution, and eval.</li>
                <li><strong>Insecure Config:</strong> Flags wildcard CORS, disabled SSL checks, and debug mode.</li>
                <li><strong>Auth Bypass:</strong> Flags state-mutating HTTP endpoints lacking authentication guards.</li>
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
