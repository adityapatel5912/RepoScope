import { useEffect, useRef, useState } from "react";
import { Bug, Keyboard, Settings, Link2, X, Menu, GraduationCap, ShieldCheck, ExternalLink, Network, Boxes } from "lucide-react";
import { clsx } from "clsx";
import type { RepoLoader } from "../hooks/useRepoLoader";
import LoadingStepper from "./LoadingStepper";

type Mode = "understanding" | "tracking" | "incident";
export type ViewMode = "graph" | "mindmap";

interface Props {
  repo: string | null;
  mode: Mode;
  onModeChange: (m: Mode) => void;
  viewMode?: ViewMode;
  onViewModeChange?: (v: ViewMode) => void;
  debugMode: boolean;
  onDebugToggle: () => void;
  studentMode: boolean;
  onStudentModeToggle: () => void;
  onShowShortcuts?: () => void;
  loader: RepoLoader;
  onClearRepo: () => void;
  onToggleSidebar?: () => void;
  /** Open the editor settings modal (Milestone 2.1). */
  onOpenEditorSettings?: () => void;
  /**
   * True when the loaded repository is a local directory.
   *
   * Local mode is a PRIVACY promise, so it is stated on screen rather
   * than buried in a settings page: nothing from this repository has
   * left the machine. A user who is about to paste a private codebase
   * into a chat needs to see that at a glance.
   */
  isLocal?: boolean;
  /**
   * The name of a folder the browser parsed. A preview has no backend
   * index, so the server-backed modes and Student Mode are unavailable.
   */
  previewName?: string | null;
}

const MODES: { id: Mode; label: string }[] = [
  { id: "understanding", label: "Understand" },
  { id: "tracking",      label: "Track"       },
  { id: "incident",      label: "Incident"    },
];

export default function TopBar({
  repo, mode, onModeChange, viewMode = "graph", onViewModeChange, debugMode, onDebugToggle, studentMode, onStudentModeToggle,
  onShowShortcuts, loader, onClearRepo, onToggleSidebar, isLocal, onOpenEditorSettings,
  previewName = null,
}: Props) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chipEditing, setChipEditing]   = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);

  // Close settings popover on outside click
  useEffect(() => {
    if (!settingsOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!settingsRef.current?.contains(e.target as Node)) setSettingsOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [settingsOpen]);

  const showInput = !repo || chipEditing;

  return (
    <header
      className="
        relative z-50 flex items-center justify-between gap-1 sm:gap-2.5 px-2 sm:px-4
        h-12 sm:h-14 shrink-0
        bg-bg-panel border-b-[1.5px] border-border-subtle
      "
    >
      {/* ── Left: logo mark + wordmark + subtitle ── */}
      <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            aria-label="Toggle sidebar"
            title="Toggle sidebar"
            className="btn-ghost w-7 h-7 sm:w-8 sm:h-8 !p-0 items-center justify-center lg:hidden flex shrink-0"
          >
            <Menu size={16} />
          </button>
        )}
        <img
          src="/icon.png"
          alt="RepoScope logo"
          className="w-5 h-5 sm:w-6 sm:h-6 shrink-0 object-cover border-[1.5px] border-border-subtle rounded-md"
        />
        <div className="flex flex-col leading-none">
          <span className="hidden min-[540px]:block text-[13px] sm:text-[15px] font-extrabold text-text-primary tracking-[-0.02em]">
            RepoScope
          </span>
          <span className="hidden md:block text-[10px] font-semibold tracking-[0.15em] text-text-muted uppercase mt-0.5">
            Repo Intelligence
          </span>
        </div>
      </div>

      {/* ── Center: Load Repo input ⇄ repo chip ──
          Deliberately wider than the old 340px cap: a repository URL is
          long, and the loading button must never eat into it. */}
      <div className="flex-1 flex justify-center min-w-0 max-w-md lg:max-w-xl px-1">
        {showInput ? (
          <div className="relative w-full max-w-[480px] min-w-0">
            <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
              <div className="relative flex-1 min-w-[90px]">
                <Link2
                  size={13}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none"
                />
                <input
                  id="repo-url-input"
                  value={loader.url}
                  onChange={(e) => { loader.setUrl(e.target.value); loader.setUrlError(null); }}
                  onKeyDown={(e) => e.key === "Enter" && !loader.loading && void loader.submit()}
                  placeholder="github.com/owner/repo"
                  disabled={loader.loading}
                  aria-label="GitHub repository URL"
                  className="input !py-1.5 pl-8 pr-7 font-mono !text-xs w-full"
                />
                {loader.url && !loader.loading && (
                  <button
                    onClick={() => { loader.setUrl(""); loader.setUrlError(null); }}
                    aria-label="Clear URL"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
              <button
                id="load-repo-btn"
                onClick={() => void loader.submit()}
                disabled={loader.loading || !loader.url.trim()}
                className="btn-primary !py-1.5 !px-2.5 sm:!px-3 !text-xs shrink-0 justify-center min-w-[74px]"
              >
                {loader.loading ? <span className="btn-spinner" /> : null}
                {loader.loading ? "Loading" : "Load"}
              </button>
            </div>

            {/* Staged loading progress, anchored under the input. The
                header must stay overflow-visible for this to escape the
                bar; clipping it here is what made the URL and the button
                appear to overlap. */}
            {loader.loading && loader.stepIdx >= 0 && loader.stepIdx < 4 && (
              <div className="pop-in absolute left-0 right-0 top-full mt-2 z-50 card p-3 shadow-lg">
                <LoadingStepper steps={loader.steps} />
              </div>
            )}

            {/* Inline error */}
            {loader.urlError && !loader.loading && (
              <p className="mt-1.5 text-2xs text-accent-rose leading-relaxed px-1" role="alert">
                {loader.urlError}
              </p>
            )}
          </div>
        ) : (
          <button
            onClick={() => setChipEditing(true)}
            title={`Loaded: ${repo} (click to change)`}
            className="
              flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1.5 rounded-full max-w-full min-w-0
              bg-bg-panel-alt border-[1.5px] border-border-subtle
              text-xs font-mono text-text-primary
              hover:bg-bg-panel-hover transition-colors cursor-text
            "
          >
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 pulse-dot shrink-0" />
            <span className="truncate max-w-[130px] sm:max-w-[200px] md:max-w-xs">{repo}</span>
          </button>
        )}
      </div>

      {/* ── LOCAL MODE badge ──
          The privacy promise, stated where the user can see it before
          they paste anything private into a chat. */}
      {isLocal && (
        <div className="shrink-0">
          <span
            data-testid="local-mode-badge"
            title="Local mode — this repository is analysed on your machine. Nothing from it has been uploaded, and no GitHub request is made."
            className="
              flex items-center gap-1 px-2 py-1 rounded-full
              bg-accent-emerald/10 border-[1.5px] border-accent-emerald/40
              text-[10px] font-bold uppercase tracking-wider text-accent-emerald
              whitespace-nowrap
            "
          >
            <ShieldCheck size={11} />
            <span className="hidden sm:inline">Local mode</span>
          </span>
        </div>
      )}

      {/* ── Right: mode pills + icon buttons ── */}
      <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
        {/* ── View Mode switch: Graph ⇄ Mind Map ── */}
        {onViewModeChange && (
          <div
            role="group"
            aria-label="View mode"
            className="flex items-center rounded-lg border-[1.5px] border-border-subtle p-0.5 bg-bg-panel-alt mr-1"
          >
            <button
              type="button"
              role="tab"
              data-testid="view-mode-graph"
              aria-selected={viewMode === "graph"}
              aria-label="Graph view"
              onClick={() => onViewModeChange("graph")}
              className={clsx(
                "flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-md text-[11px] sm:text-xs font-bold transition-all duration-150",
                viewMode === "graph"
                  ? "bg-text-primary text-white shadow-sm"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-panel"
              )}
            >
              <Network size={13} />
              <span>Graph</span>
            </button>
            <button
              type="button"
              role="tab"
              data-testid="view-mode-mindmap"
              aria-selected={viewMode === "mindmap"}
              aria-label="Mind Map view"
              onClick={() => onViewModeChange("mindmap")}
              className={clsx(
                "flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-md text-[11px] sm:text-xs font-bold transition-all duration-150",
                viewMode === "mindmap"
                  ? "bg-accent-cyan text-white shadow-sm"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-panel"
              )}
            >
              <Boxes size={13} />
              <span>Mind Map</span>
            </button>
          </div>
        )}

        {/* A browser preview has no server-side index, so Track/Incident and
            Student Mode would either do nothing or answer about the server's
            loaded repository. Hide them rather than let the labels lie. */}
        {!previewName && (
          <>
            <nav role="tablist" className="flex items-center gap-0.5 sm:gap-1">
              {MODES.map(({ id, label }) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={mode === id}
                  onClick={() => onModeChange(id)}
                  className={clsx(
                    "px-2 sm:px-2.5 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-semibold whitespace-nowrap border-[1.5px] border-border-subtle transition-all duration-150",
                    mode === id
                      ? "bg-accent-cyan text-white shadow-sm"
                      : "bg-bg-panel text-text-primary hover:bg-bg-panel-alt"
                  )}
                >
                  {id === "understanding" ? (
                    <>
                      <span className="hidden min-[480px]:inline">Understand</span>
                      <span className="min-[480px]:hidden">Map</span>
                    </>
                  ) : label}
                </button>
              ))}
            </nav>

            {/* Student Mode toggle — learning path + quizzes (Feature: Student Onboarding) */}
            <button
              onClick={onStudentModeToggle}
              title={studentMode ? "Student Mode is ON — click to exit" : "Student Mode: guided learning path + quizzes"}
              aria-pressed={studentMode}
              className={clsx(
                "flex items-center gap-1.5 px-2 sm:px-2.5 py-1 sm:py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap border-[1.5px] transition-all duration-150",
                studentMode
                  ? "bg-accent-emerald text-white border-accent-emerald shadow-sm"
                  : "bg-bg-panel text-text-primary border-border-subtle hover:bg-bg-panel-alt"
              )}
            >
              <GraduationCap size={13} />
              <span className="hidden md:inline">Student</span>
            </button>
          </>
        )}

        {/* Shortcuts — settings popover covers these on small screens */}
        <button
          onClick={() => onShowShortcuts?.()}
          title="Keyboard shortcuts (?)"
          aria-label="Keyboard shortcuts"
          className="btn-ghost w-8 h-8 !p-0 items-center justify-center hidden md:flex"
        >
          <Keyboard size={15} />
        </button>

        {/* Settings gear + popover */}
        <div className="relative" ref={settingsRef}>
          <button
            onClick={() => setSettingsOpen((v) => !v)}
            title="Settings"
            aria-label="Settings"
            aria-expanded={settingsOpen}
            className={clsx(
              "btn-ghost w-8 h-8 !p-0 items-center justify-center",
              settingsOpen && "bg-bg-panel-alt text-text-primary"
            )}
          >
            <Settings size={15} />
          </button>

          {settingsOpen && (
            <div className="
              drawer-slide-in absolute right-0 top-full mt-2 w-56 z-[60]
              card p-2 shadow-lg
            ">
              <button
                onClick={() => { onShowShortcuts?.(); setSettingsOpen(false); }}
                className="w-full flex items-center gap-2 px-2.5 py-2 text-xs text-text-secondary
                  hover:bg-bg-panel-alt rounded-md transition-colors text-left"
              >
                <Keyboard size={13} className="text-text-muted" />
                Keyboard shortcuts
                <span className="ml-auto font-mono text-[10px] text-text-muted">?</span>
              </button>
              <button
                onClick={() => { onOpenEditorSettings?.(); setSettingsOpen(false); }}
                className="w-full flex items-center gap-2 px-2.5 py-2 text-xs text-text-secondary
                  hover:bg-bg-panel-alt rounded-md transition-colors text-left"
              >
                <ExternalLink size={13} className="text-text-muted" />
                Editor settings
                <span className="ml-auto font-mono text-[10px] text-text-muted">IDE</span>
              </button>
              <button
                onClick={() => { onDebugToggle(); setSettingsOpen(false); }}
                className="w-full flex items-center gap-2 px-2.5 py-2 text-xs text-text-secondary
                  hover:bg-bg-panel-alt rounded-md transition-colors text-left"
              >
                <Bug size={13} className="text-text-muted" />
                Debug panel
                <span className={clsx(
                  "ml-auto text-[10px] font-semibold",
                  debugMode ? "text-green-700" : "text-text-muted"
                )}>
                  {debugMode ? "ON" : "OFF"}
                </span>
              </button>
              <div className="mt-1 pt-2 border-t border-border-hairline px-2.5 py-1.5">
                <span className="text-[10px] text-text-muted">
                  Theme — Editorial (light)
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Debug toggle */}
        <button
          onClick={onDebugToggle}
          title="Toggle debug panel"
          aria-label="Toggle debug panel"
          className={clsx(
            "btn-ghost w-8 h-8 !p-0 items-center justify-center hidden md:flex",
            debugMode && "bg-bg-panel-alt text-text-primary"
          )}
        >
          <Bug size={15} />
        </button>

        {/* Clear repo — only when one is loaded */}
        {repo && (
          <button
            onClick={() => { setChipEditing(false); onClearRepo(); }}
            title="Clear loaded repository"
            aria-label="Clear loaded repository"
            className="btn-ghost w-8 h-8 !p-0 items-center justify-center"
          >
            <X size={15} />
          </button>
        )}
      </div>
    </header>
  );
}
