/**
 * SecurityPanel.tsx
 * Breaking Change + Secret Scan (Nord Security angle) with a tab switcher
 * that hosts the existing Tracking results next to the new Security tab.
 * Scan sources: loaded clone (committed secrets, .env leaks, vulnerable
 * dependency pins) + optional PR patch + recent commit BREAKING markers.
 */
import { useState } from "react";
import { securityScan, type SecurityScan } from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";
import TrackingPanel from "./TrackingPanel";
import {
  ShieldAlert, ShieldCheck, Radio, ScanSearch, RefreshCw,
} from "lucide-react";

interface Props {
  /** Tracking results from the SSE stream (existing feature). */
  trackingData: unknown;
  /** owner/repo of the loaded repository. */
  repo: string | null;
}

type Tab = "tracking" | "security";

const TYPE_BADGE: Record<string, string> = {
  SECRET:   "text-accent-rose    border-accent-rose/30    bg-accent-rose/10",
  BREAKING: "text-accent-amber   border-accent-amber/30   bg-accent-amber/10",
  CVE:      "text-orange-600     border-orange-400/40     bg-orange-100",
};

const SEV_BADGE: Record<string, string> = {
  critical: "text-white bg-accent-rose",
  high:     "text-accent-rose bg-accent-rose/15",
  medium:   "text-accent-amber bg-accent-amber/15",
  low:      "text-text-muted bg-bg-panel-alt",
};

export default function SecurityPanel({ trackingData, repo }: Props) {
  const [tab, setTab]       = useState<Tab>("tracking");
  const [scan, setScan]     = useState<SecurityScan | null>(null);
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState<string | null>(null);

  const runScan = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const data = await securityScan();
      setScan(data);
      const s = data.summary;
      toast.success(
        `Scan done — ${s.SECRET} secret${s.SECRET === 1 ? "" : "s"}, ` +
        `${s.BREAKING} breaking, ${s.CVE} CVE`,
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Scan failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const summary = scan?.summary;

  return (
    <div className="card p-4 flex flex-col gap-3">
      {/* ── Tab bar: Tracking | Security ── */}
      <div className="flex items-center gap-1 p-0.5 rounded-lg bg-bg-panel-alt border border-border-hairline">
        {([
          { id: "tracking" as Tab, label: "Tracking", icon: <Radio size={11} /> },
          { id: "security" as Tab, label: "Security", icon: <ShieldAlert size={11} /> },
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
                  ? "bg-accent-rose/20 text-accent-rose"
                  : "bg-accent-emerald/15 text-accent-emerald"}
              `}>
                {scan.total_flags}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tracking tab (existing feature, wrapped) ── */}
      {tab === "tracking" && (
        trackingData ? (
          // Cancel the card padding so TrackingPanel keeps its native
          // edge-to-edge look with the bottom border.
          <div className="-mx-4 -my-4">
            <TrackingPanel data={trackingData} />
          </div>
        ) : (
          <p className="text-[11px] text-text-muted leading-relaxed m-0">
            Switch the mode above to <span className="font-semibold">Track</span> and
            ask a question — new commits, PRs, issues, and releases appear here.
          </p>
        )
      )}

      {/* ── Security tab ── */}
      {tab === "security" && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => void runScan()}
              disabled={busy || !repo}
              className="btn-primary flex-1 !py-1.5 !px-3 !text-xs justify-center"
            >
              {busy ? <span className="btn-spinner" /> : <ScanSearch size={12} />}
              {busy ? "Scanning…" : scan ? "Re-scan" : "Run Security Scan"}
            </button>
            {scan && !busy && (
              <button
                onClick={() => void runScan()}
                title="Re-scan"
                aria-label="Re-scan"
                className="btn-ghost w-7 h-7 !p-0 items-center justify-center"
              >
                <RefreshCw size={12} />
              </button>
            )}
          </div>

          {error && (
            <div className="px-3 py-2 rounded-lg text-xs bg-accent-rose/10 border border-accent-rose/25 text-accent-rose">
              {error}
            </div>
          )}

          {busy && !scan && <SkeletonCard lines={3} />}

          {scan && summary && (
            <>
              {/* Summary chips */}
              <div className="flex flex-wrap gap-1.5">
                <span className={`px-2 py-0.5 rounded text-2xs font-mono border ${TYPE_BADGE.SECRET}`}>
                  🔑 {summary.SECRET} secret{summary.SECRET === 1 ? "" : "s"}
                </span>
                <span className={`px-2 py-0.5 rounded text-2xs font-mono border ${TYPE_BADGE.BREAKING}`}>
                  ⚠ {summary.BREAKING} breaking
                </span>
                <span className={`px-2 py-0.5 rounded text-2xs font-mono border ${TYPE_BADGE.CVE}`}>
                  🛡 {summary.CVE} CVE
                </span>
              </div>

              {scan.total_flags === 0 ? (
                <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-accent-emerald/10 border border-accent-emerald/25">
                  <ShieldCheck size={14} className="text-accent-emerald shrink-0" />
                  <span className="text-xs text-accent-emerald font-semibold">
                    Clean — no secrets, breaking changes, or known CVEs detected.
                  </span>
                </div>
              ) : (
                <div className="flex flex-col gap-2 overflow-y-auto max-h-80">
                  {scan.flags.map((f, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-border-hairline bg-bg-panel-alt px-2.5 py-2 flex flex-col gap-1"
                    >
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={`text-2xs font-bold uppercase px-1.5 py-0.5 rounded border ${TYPE_BADGE[f.type] ?? ""}`}>
                          {f.type}
                        </span>
                        <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${SEV_BADGE[f.severity] ?? ""}`}>
                          {f.severity}
                        </span>
                        <span className="font-mono text-[10px] text-text-muted ml-auto truncate">
                          {f.file}{f.line > 1 ? `:${f.line}` : ""}
                        </span>
                      </div>
                      <p className="m-0 text-xs text-text-primary leading-snug">{f.detail}</p>
                      <p className="m-0 text-2xs text-text-muted leading-relaxed">{f.suggestion}</p>
                    </div>
                  ))}
                  {scan.total_flags > scan.flags.length && (
                    <p className="m-0 text-2xs text-text-muted">
                      +{scan.total_flags - scan.flags.length} more flags (capped)
                    </p>
                  )}
                </div>
              )}

              <p className="m-0 text-2xs text-text-muted leading-relaxed border-t border-border-hairline pt-2">
                Scanned clone files{scan.scanned.commits ? ` + ${scan.scanned.commits} commit messages` : ""}
                {scan.scanned.pr ? ` + PR #${scan.scanned.pr} patch` : ""}. Heuristic
                scan — verify CVEs against the advisory. Secrets guidance powered by
                NordPass (Nord Security).
              </p>
            </>
          )}

          {!scan && !busy && !error && (
            <p className="m-0 text-2xs text-text-muted leading-relaxed">
              Detects committed API keys, leaked .env files, breaking function
              signature changes, major version bumps, and known-vulnerable
              dependencies — with Nord Security–backed remediation tips.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
