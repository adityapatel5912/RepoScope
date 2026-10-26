import { useEffect, useRef, useState } from "react";
import { Bug, Keyboard, Settings, Link2, X, Menu, GraduationCap } from "lucide-react";
import { clsx } from "clsx";
import type { RepoLoader } from "../hooks/useRepoLoader";
import LoadingStepper from "./LoadingStepper";

type Mode = "understanding" | "tracking" | "incident";

interface Props {
  repo: string | null;
  mode: Mode;
  onModeChange: (m: Mode) => void;
  debugMode: boolean;
  onDebugToggle: () => void;
  studentMode: boolean;
  onStudentModeToggle: () => void;
  onShowShortcuts?: () => void;
  loader: RepoLoader;
  onClearRepo: () => void;
  onToggleSidebar?: () => void;
}

const MODES: { id: Mode; label: string }[] = [
  { id: "understanding", label: "Understand" },
  { id: "tracking",      label: "Track"       },
  { id: "incident",      label: "Incident"    },
];

export default function TopBar({
  repo, mode, onModeChange, debugMode, onDebugToggle, studentMode, onStudentModeToggle,
  onShowShortcuts, loader, onClearRepo, onToggleSidebar,
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
        relative z-50 flex items-center justify-between gap-1.5 sm:gap-3 px-2 sm:px-4
        h-12 sm:h-14 shrink-0
        bg-bg-panel border-b-[1.5px] border-border-subtle overflow-x-hidden
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
          <span className="hidden min-[480px]:block text-[13px] sm:text-[15px] font-extrabold text-text-primary tracking-[-0.02em]">
            RepoScope
          </span>
          <span className="hidden md:block text-[10px] font-semibold tracking-[0.15em] text-text-muted uppercase mt-0.5">
            Repo Intelligence
          </span>
        </div>
      </div>

      {/* ── Center: Load Repo input ⇄ repo chip ── */}
      <div className="flex-1 flex justify-center min-w-0 max-w-xs sm:max-w-sm px-1">
        {showInput ? (
          <div className="relative w-full max-w-[340px]">
            <div className="flex items-center gap-1.5">
              <div className="relative flex-1 min-w-0">
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
                  className="input !py-1.5 pl-8 pr-8 font-mono !text-xs"
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
                className="btn-primary !py-1.5 !px-3 !text-xs shrink-0"
              >
                {loader.loading ? <span className="btn-spinner" /> : null}
                {loader.loading ? "Loading" : "Load"}
              </button>
            </div>

            {/* Staged loading progress, anchored under the input */}
            {loader.loading && loader.stepIdx >= 0 && loader.stepIdx < 4 && (
              <div className="pop-in absolute left-0 right-0 top-10 z-50 card p-3">
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
            title="Click to load a different repository"
            className="
              flex items-center gap-2 px-3 py-1.5 rounded-full max-w-full min-w-0
              bg-bg-panel-alt border-[1.5px] border-border-subtle
              text-xs font-mono text-text-primary
              hover:bg-bg-panel-hover transition-colors cursor-text
            "
          >
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 pulse-dot shrink-0" />
            <span className="truncate">{repo}</span>
          </button>
        )}
      </div>

      {/* ── Right: mode pills + icon buttons ── */}
      <div className="flex items-center gap-2 shrink-0">
        <nav role="tablist" className="flex items-center gap-1 sm:gap-1.5">
          {MODES.map(({ id, label }) => (
            <button
              key={id}
              role="tab"
              aria-selected={mode === id}
              onClick={() => onModeChange(id)}
              className={clsx(
                "px-1.5 sm:px-3 py-1 sm:py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap border-[1.5px] border-border-subtle transition-all duration-150",
                mode === id
                  ? "bg-accent-cyan text-white shadow-sm"
                  : "bg-bg-panel text-text-primary hover:bg-bg-panel-alt"
              )}
            >
              {label}
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
          <span className="hidden sm:inline">Student</span>
        </button>

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
              drawer-slide-in absolute right-0 top-10 w-56 z-[60]
              card p-2
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
