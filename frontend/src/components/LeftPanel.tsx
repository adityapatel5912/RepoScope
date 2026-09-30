import { useState } from "react";
import { setBYOK } from "../api/client";
import { loadDemo } from "../api/features";
import type { RepoLoader } from "../hooks/useRepoLoader";
import FileTree from "./FileTree";
import SecurityPanel from "./SecurityPanel";
import CommitPanel from "./CommitPanel";
import TourPanel, { type TourRequest, type TourState } from "./TourPanel";
import ImpactPanel, { type ImpactRequest } from "./ImpactPanel";
import AIKeyPanel from "./AIKeyPanel";
import OnboardingPath from "./OnboardingPath";
import { toast } from "./Toasts";
import { Github, CheckCircle2, Keyboard, Bug, RotateCw, Eraser, FileWarning, Play, X } from "lucide-react";

interface RepoInfo {
  owner: string;
  repo: string;
  file_count?: number;
  node_count?: number;
  edge_count?: number;
  readme_length?: number;
}

interface Props {
  onLoaded: (info: RepoInfo) => void;
  repoInfo: RepoInfo | null;
  trackingData: unknown;
  contextInfo: { file_count?: number; node_count?: number; edge_count?: number; readme_length?: number } | null;
  rawNodes?: unknown[];
  loader: RepoLoader;
  studentMode?: boolean;
  onHighlightNode?: (nodeId: string | null) => void;
  onHighlightImpact?: (targetId: string | null, directIds: string[], transitiveIds: string[]) => void;
  tourRequest?: TourRequest | null;
  impactRequest?: ImpactRequest | null;
  onTourState?: (state: TourState | null) => void;
  onShowShortcuts?: () => void;
  onToggleDebug?: () => void;
  onClose?: () => void;
}

// Sidebar card shell — white panel, black border, label-caps header
const DEMO_LIST: { id: string; label: string }[] = [
  { id: "verdict",  label: "Verdict — Decision Lab" },
  { id: "studyrot", label: "StudyRot — Study Scheduler" },
];

function Card({
  title, icon, children,
}: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="card p-4 flex flex-col gap-3 overflow-hidden min-w-0">
      <div className="flex items-center gap-1.5 min-w-0">
        {icon}
        <h3 className="label-caps truncate">{title}</h3>
      </div>
      {children}
    </section>
  );
}

export default function LeftPanel({
  onLoaded, repoInfo, trackingData, contextInfo, rawNodes = [], loader, studentMode = false,
  onHighlightNode, onHighlightImpact, tourRequest, impactRequest, onTourState,
  onShowShortcuts, onToggleDebug, onClose,
}: Props) {
  const [byokToken, setByokToken]   = useState("");
  const [byokSaved, setByokSaved]   = useState(false);
  const [byokStatus, setByokStatus] = useState<"idle" | "saved" | "error">("idle");
  const [byokError, setByokError]   = useState<string | null>(null);

  const saveBYOK = async () => {
    const token = byokToken.trim();
    if (!token) return;
    if (!/^(ghp_|github_pat_)/.test(token)) {
      setByokStatus("error");
      setByokError("PAT must start with ghp_ or github_pat_");
      return;
    }
    try {
      await setBYOK(token);
      setByokSaved(true);
      setByokStatus("saved");
      setByokError(null);
      setByokToken("");
      toast.success("GitHub PAT saved (session only)");
    } catch {
      setByokStatus("error");
      setByokError("Failed to save PAT — is the backend running?");
      toast.error("Failed to save PAT");
    }
  };

  const clearCache = () => {
    try {
      localStorage.removeItem("reposcope-layout");
      toast.success("Cached layout cleared — reloading");
      setTimeout(() => window.location.reload(), 600);
    } catch {
      toast.error("Could not clear cache");
    }
  };

  // ── Demo repos (one-click) ──
  const [demoLoading, setDemoLoading] = useState<string | null>(null);
  const runDemo = async (id: string) => {
    if (demoLoading) return;
    setDemoLoading(id);
    try {
      const info = await loadDemo(id);
      onLoaded(info);
      toast.success(`Loaded demo ${info.owner}/${info.repo}`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Demo failed to load");
    } finally {
      setDemoLoading(null);
    }
  };

  const stats = [
    { label: "Files",  value: contextInfo?.file_count  ?? repoInfo?.file_count },
    { label: "Nodes",  value: contextInfo?.node_count ?? repoInfo?.node_count },
    { label: "Edges",  value: contextInfo?.edge_count ?? repoInfo?.edge_count },
    { label: "README", value: contextInfo?.readme_length != null
        ? `${(contextInfo.readme_length / 1000).toFixed(1)}k`
        : (repoInfo?.readme_length != null ? `${(repoInfo.readme_length / 1000).toFixed(1)}k` : undefined) },
  ];

  return (
    <div className="w-full h-full overflow-y-auto overflow-x-hidden p-4 flex flex-col gap-4 [&>*]:shrink-0">
      {onClose && (
        <div className="lg:hidden flex items-center justify-between pb-2 border-b border-border-hairline">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">Explorer Sidebar</span>
          <button
            onClick={onClose}
            aria-label="Close sidebar"
            className="btn-ghost w-7 h-7 !p-0 items-center justify-center flex"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* ── Card 1 · REPOSITORY ── */}
      <Card title="Repository">
        {repoInfo ? (
          <>
            <span
              className="mono text-text-primary text-xs truncate block font-medium"
              title={`${repoInfo.owner}/${repoInfo.repo}`}
            >
              {repoInfo.owner}/{repoInfo.repo}
            </span>
            <div className="grid grid-cols-2 gap-2">
              {stats.map(({ label, value }) => (
                <div
                  key={label}
                  className="px-3 py-2 rounded-md bg-bg-panel-alt border border-border-hairline flex flex-col gap-0.5"
                >
                  <span className="label-caps !text-[10px]">{label}</span>
                  <span className="text-lg font-bold text-accent-cyan leading-tight">
                    {value ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex items-start gap-2 text-xs text-text-muted leading-relaxed">
            <FileWarning size={14} className="shrink-0 mt-0.5 text-text-muted" />
            Load a repository from the bar above to see its stats, graph, and tour.
          </div>
        )}
      </Card>

      {/* ── Student Mode: guided learning path (pyramid-ranked) ── */}
      {studentMode && (
        <OnboardingPath repo={repoInfo ? `${repoInfo.owner}/${repoInfo.repo}` : null} />
      )}

      {/* ── Card 2 · FILE TREE (FILE 4 format) ── */}
      <FileTree rawNodes={rawNodes} />

      {/* ── Tracking results + Security scan (tabbed) ── */}
      <SecurityPanel
        trackingData={trackingData as never}
        repo={repoInfo ? `${repoInfo.owner}/${repoInfo.repo}` : null}
      />

      {/* ── Card · DEMO REPOS (one-click examples) ── */}
      <Card title="Try a demo">
        <div className="flex flex-col gap-2">
          {DEMO_LIST.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => void runDemo(id)}
              disabled={demoLoading != null}
              className="btn-secondary w-full justify-start !text-xs"
            >
              <Play size={12} className="text-accent-cyan shrink-0" />
              {demoLoading === id ? "Loading…" : label}
            </button>
          ))}
        </div>
      </Card>

      {/* ── Card 3 · GITHUB PAT (BYOK) ── */}
      <Card title="GitHub PAT (BYOK)" icon={<Github size={12} className="text-text-muted" />}>
        <p className="text-[11px] text-text-muted leading-relaxed">
          Stored in memory only — never written to disk.
        </p>
        <div className="flex gap-2 items-center">
          <input
            type="password"
            value={byokToken}
            onChange={(e) => { setByokToken(e.target.value); setByokStatus("idle"); setByokError(null); }}
            onKeyDown={(e) => e.key === "Enter" && void saveBYOK()}
            placeholder="ghp_…"
            aria-label="GitHub personal access token"
            className="input flex-1 !py-1.5 font-mono !text-xs"
          />
          <button
            onClick={() => void saveBYOK()}
            disabled={!byokToken.trim()}
            className="btn-secondary !py-1.5 !px-3 !text-xs shrink-0"
          >
            {byokStatus === "saved"
              ? <><CheckCircle2 size={12} className="text-accent-emerald" /> Saved</>
              : byokStatus === "error"
              ? "Error ✗"
              : "Save"}
          </button>
        </div>
        {byokError && (
          <p className="text-[11px] text-accent-rose leading-relaxed" role="alert">
            {byokError}
          </p>
        )}
        <a
          href="https://github.com/settings/tokens/new"
          target="_blank"
          rel="noreferrer"
          className="text-[11px] text-accent-hover hover:text-accent underline underline-offset-2 transition-colors"
        >
          How to create a PAT →
        </a>
      </Card>

      {/* ── AI Provider (BYOK) ── */}
      <AIKeyPanel />

      {/* ── Card 4 · COMMIT ── */}
      <CommitPanel disabled={!byokSaved} />

      {/* ── Code Tours ── */}
      <TourPanel onHighlightNode={onHighlightNode} onTourState={onTourState} request={tourRequest} />

      {/* ── What-If Impact Analysis + PR Bot ── */}
      <ImpactPanel
        repo={repoInfo ? `${repoInfo.owner}/${repoInfo.repo}` : null}
        onHighlightImpact={onHighlightImpact}
        request={impactRequest}
      />

      {/* ── Card 5 · SETTINGS SHORTCUTS ── */}
      <Card title="Quick actions">
        <div className="flex flex-col gap-0.5">
          <button onClick={() => onShowShortcuts?.()} className="btn-ghost justify-start !text-xs">
            <Keyboard size={13} /> Keyboard shortcuts
            <span className="ml-auto font-mono text-[10px] text-text-muted">?</span>
          </button>
          <button onClick={() => onToggleDebug?.()} className="btn-ghost justify-start !text-xs">
            <Bug size={13} /> Toggle debug logs
          </button>
          <button
            onClick={() => loader.resubmit()}
            disabled={!loader.hasLastUrl() || loader.loading}
            className="btn-ghost justify-start !text-xs"
          >
            <RotateCw size={13} /> Reload repository
          </button>
          <button onClick={clearCache} className="btn-ghost justify-start !text-xs">
            <Eraser size={13} /> Clear cached layout
          </button>
        </div>
      </Card>
    </div>
  );
}
