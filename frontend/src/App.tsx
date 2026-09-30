import { useState, useCallback, useRef } from "react";
import TopBar from "./components/TopBar";
import LeftPanel from "./components/LeftPanel";
import GraphCanvas from "./components/GraphView";
import ChatPanel from "./components/ChatPanel";
import StatusBar from "./components/StatusBar";
import Toasts from "./components/Toasts";
import ShortcutsModal from "./components/ShortcutsModal";
import { useKeyboard } from "./hooks/useKeyboard";
import { useRepoLoader } from "./hooks/useRepoLoader";
import type { TourGraphState } from "./components/GraphView";
import { FolderTree, MessageSquare, ChevronDown } from "lucide-react";
import { getGraph } from "./api/client";
import type { ContextPayload } from "./api/client";

type Mode = "understanding" | "tracking" | "incident";

interface RepoInfo {
  owner: string;
  repo: string;
  file_count?: number;
  node_count?: number;
  edge_count?: number;
  readme_length?: number;
}

const LAYOUT_KEY = "reposcope-layout";
const STUDENT_MODE_KEY = "reposcope-student-mode";

interface PersistedLayout {
  sidebarCollapsed?: boolean;
  chatCollapsed?: boolean;
  chatHeightPct?: number;   // chat height as % of main column
}

function loadSavedLayout(): PersistedLayout {
  try {
    const raw = localStorage.getItem(LAYOUT_KEY);
    return raw ? (JSON.parse(raw) as PersistedLayout) : {};
  } catch {
    return {};
  }
}

function loadStudentMode(): boolean {
  try {
    return localStorage.getItem(STUDENT_MODE_KEY) === "1";
  } catch {
    return false;
  }
}

function persistLayout(patch: PersistedLayout) {
  try {
    const next = { ...loadSavedLayout(), ...patch };
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable — layout just won't persist */
  }
}

// ── Collapsed sidebar rail (click to re-expand) ─────────────────────────────
function PanelRail({ onExpand }: { onExpand: () => void }) {
  return (
    <button
      onClick={onExpand}
      aria-label="Expand sidebar"
      title="Expand sidebar (Ctrl+B)"
      className="
        w-full h-full flex flex-col items-center gap-3 pt-3 cursor-pointer
        bg-bg-panel hover:bg-bg-panel-alt transition-colors duration-150
        border-r-[1.5px] border-border-subtle
      "
    >
      <span className="text-accent-cyan"><FolderTree size={16} /></span>
      <span className="rail-vertical-label text-text-muted">Explorer</span>
    </button>
  );
}

export default function App() {
  const [repo,        setRepo]        = useState<string | null>(null);
  const [repoInfo,    setRepoInfo]    = useState<RepoInfo | null>(null);
  const [mode,        setMode]        = useState<Mode>("understanding");
  const [rawNodes,    setRawNodes]    = useState<unknown[]>([]);
  const [rawEdges,    setRawEdges]    = useState<unknown[]>([]);
  const [tracking,    setTracking]    = useState<unknown>(null);
  const [contextInfo, setContextInfo] = useState<ContextPayload | null>(null);
  const [tokenCount,  setTokenCount]  = useState(0);
  const [lastEvent,   setLastEvent]   = useState("");
  const [debugMode,   setDebugMode]   = useState(false);
  const [prefill,     setPrefill]     = useState<string | undefined>(undefined);
  const [studentMode, setStudentMode] = useState(loadStudentMode);

  // Tour + impact graph highlighting
  const [highlightNode, setHighlightNode]       = useState<string | null>(null);
  const [tourState, setTourState]               = useState<TourGraphState | null>(null);
  const [impactTarget, setImpactTarget]         = useState<string | null>(null);
  const [impactDirect, setImpactDirect]         = useState<string[]>([]);
  const [impactTransitive, setImpactTransitive] = useState<string[]>([]);
  const [showShortcuts, setShowShortcuts]       = useState(false);

  // Drawer-triggered feature requests ("Analyze impact" / "Start tour from here")
  const [tourRequest, setTourRequest]           = useState<{ topic: string; ts: number } | null>(null);
  const [impactRequest, setImpactRequest]       = useState<{ target: string; ts: number } | null>(null);

  // ── Shell layout state (persisted) ──
  const saved = useRef<PersistedLayout>(loadSavedLayout());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    saved.current.sidebarCollapsed ?? (typeof window !== "undefined" ? window.innerWidth < 1024 : false)
  );
  const [chatCollapsed, setChatCollapsed]       = useState(saved.current.chatCollapsed ?? false);
  const [chatHeightPct, setChatHeightPct]       = useState(saved.current.chatHeightPct ?? 40);
  const mainRef = useRef<HTMLElement>(null);

  // ── Repo loading (TopBar input) ──
  const handleLoaded = useCallback((info: RepoInfo) => {
    setRepo(`${info.owner}/${info.repo}`);
    setRepoInfo(info);
    setRawNodes([]);
    setRawEdges([]);
    setTracking(null);
    setContextInfo(null);
    setTokenCount(0);
    setTourState(null);
    setHighlightNode(null);
    setImpactTarget(null);
    setImpactDirect([]);
    setImpactTransitive([]);
    // Eagerly fetch the graph so it renders immediately without needing a chat query
    getGraph().then((g) => {
      if (g?.nodes?.length) {
        setRawNodes(g.nodes);
        setRawEdges(g.edges ?? []);
      }
    }).catch(() => { /* graph fetch failed — will populate on first chat query instead */ });
  }, []);

  const loader = useRepoLoader(handleLoaded);

  const clearRepo = useCallback(() => {
    setRepo(null);
    setRepoInfo(null);
    setRawNodes([]);
    setRawEdges([]);
    setTracking(null);
    setContextInfo(null);
    setTokenCount(0);
    loader.setUrl("");
    loader.setUrlError(null);
    clearHighlights();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loader]);

  const clearHighlights = useCallback(() => {
    setHighlightNode(null);
    setImpactTarget(null);
    setImpactDirect([]);
    setImpactTransitive([]);
  }, []);

  // ── Chat height drag (graph ⇅ chat divider) ──
  const startChatResize = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    const mainEl = mainRef.current;
    if (!mainEl) return;
    const rect = mainEl.getBoundingClientRect();
    const onMove = (ev: PointerEvent) => {
      const fromBottom = rect.bottom - ev.clientY;
      const pct = Math.min(70, Math.max(18, (fromBottom / rect.height) * 100));
      setChatHeightPct(pct);
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setChatHeightPct((p) => {
        persistLayout({ chatHeightPct: p });
        return p;
      });
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }, []);

  // ── Global keyboard shortcuts ─────────────────────────────────────────────
  useKeyboard({
    "Mod+k": () => document.getElementById("repo-url-input")?.focus(),
    "Mod+1": () => setMode("understanding"),
    "Mod+2": () => setMode("tracking"),
    "Mod+3": () => setMode("incident"),
    "Mod+b": () => setSidebarCollapsed((v) => { persistLayout({ sidebarCollapsed: !v }); return !v; }),
    "Mod+j": () => setChatCollapsed((v) => { persistLayout({ chatCollapsed: !v }); return !v; }),
    "Escape": () => {
      setShowShortcuts(false);
      clearHighlights();
    },
    "?": () => setShowShortcuts((v) => !v),
  });

  const handleContext = useCallback((ctx: ContextPayload) => {
    setRawNodes(ctx.nodes ?? []);
    setRawEdges(ctx.edges ?? []);
    setContextInfo(ctx);
  }, []);

  return (
    <div className="relative flex flex-col h-screen overflow-hidden bg-bg-base">
      <Toasts />

      {/* Top bar — logo · load input/chip · modes · settings */}
      <TopBar
        repo={repo}
        mode={mode}
        onModeChange={setMode}
        debugMode={debugMode}
        onDebugToggle={() => setDebugMode((v) => !v)}
        studentMode={studentMode}
        onStudentModeToggle={() => setStudentMode((v) => {
          try { localStorage.setItem(STUDENT_MODE_KEY, v ? "0" : "1"); } catch { /* ignore */ }
          return !v;
        })}
        onShowShortcuts={() => setShowShortcuts(true)}
        loader={loader}
        onClearRepo={clearRepo}
        onToggleSidebar={() => {
          setSidebarCollapsed((v) => {
            const next = !v;
            persistLayout({ sidebarCollapsed: next });
            return next;
          });
        }}
      />

      {/* ── Body: two-column grid — fixed sidebar + main stack ── */}
      <div className="relative flex flex-1 min-h-0 z-10">
        {/* Mobile backdrop — tap to close the overlay sidebar */}
        {!sidebarCollapsed && (
          <div
            className="lg:hidden absolute inset-0 z-[35] bg-black/20"
            onClick={() => { setSidebarCollapsed(true); persistLayout({ sidebarCollapsed: true }); }}
            aria-hidden="true"
          />
        )}
        {/* Left sidebar */}
        {sidebarCollapsed ? (
          <div className="w-10 shrink-0">
            <PanelRail onExpand={() => { setSidebarCollapsed(false); persistLayout({ sidebarCollapsed: false }); }} />
          </div>
        ) : (
          <aside
            className="
              w-[300px] max-w-[85vw] shrink-0 overflow-y-auto overflow-x-hidden
              bg-bg-panel border-r-[1.5px] border-border-subtle
              max-lg:absolute max-lg:inset-y-0 max-lg:left-0 max-lg:z-40 max-lg:shadow-lg
            "
          >
            <LeftPanel
              onLoaded={handleLoaded}
              repoInfo={repoInfo}
              trackingData={tracking}
              contextInfo={contextInfo}
              rawNodes={rawNodes}
              loader={loader}
              studentMode={studentMode}
              onHighlightNode={setHighlightNode}
              onHighlightImpact={(t, d, tr) => {
                setImpactTarget(t);
                setImpactDirect(d);
                setImpactTransitive(tr);
              }}
              tourRequest={tourRequest}
              impactRequest={impactRequest}
              onTourState={setTourState}
              onShowShortcuts={() => setShowShortcuts(true)}
              onToggleDebug={() => setDebugMode((v) => !v)}
              onClose={() => { setSidebarCollapsed(true); persistLayout({ sidebarCollapsed: true }); }}
            />
          </aside>
        )}

        {/* Main area — graph on top, chat below (24px rhythm via paddings) */}
        <main ref={mainRef} className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {/* Graph canvas panel */}
          <section className={`w-full min-h-0 ${chatCollapsed ? "flex-1" : "flex-[0_0_auto]"}`} style={chatCollapsed ? undefined : { height: `${100 - chatHeightPct}%` }}>
            <GraphCanvas
              rawNodes={rawNodes}
              rawEdges={rawEdges}
              onAskAbout={(msg) => { setPrefill(msg); setChatCollapsed(false); }}
              onAnalyzeImpact={(label) => setImpactRequest({ target: label, ts: Date.now() })}
              onStartTour={(label) => setTourRequest({ topic: label, ts: Date.now() })}
              repoTitle={repo ?? "Repository"}
              highlightNode={highlightNode}
              impactTarget={impactTarget}
              impactDirect={impactDirect}
              impactTransitive={impactTransitive}
              tourState={tourState}
            />
          </section>

          {/* Divider — drag to resize */}
          {!chatCollapsed && (
            <div
              role="separator"
              aria-orientation="horizontal"
              aria-label="Resize chat panel"
              onPointerDown={startChatResize}
              className="resize-handle-h shrink-0"
            />
          )}

          {/* Chat panel */}
          {!chatCollapsed && (
            <section
              className="w-full min-h-0 flex-[0_0_auto] flex flex-col bg-bg-panel border-t-[1.5px] border-border-subtle"
              style={{ height: `${chatHeightPct}%` }}
            >
              <div className="px-4 py-2 border-b border-border-hairline shrink-0 flex items-center justify-between gap-2 bg-bg-panel">
                <div className="min-w-0 flex items-baseline gap-2">
                  <h2 className="label-caps !text-text-primary">AI Assistant</h2>
                  <p className="text-[11px] text-text-muted truncate hidden sm:block">
                    {mode === "tracking"  ? "Track changes & PRs in real time" :
                     mode === "incident"  ? "Incident response & root-cause analysis" :
                                            "Understand your codebase with natural language"}
                  </p>
                </div>
                <button
                  onClick={() => { setChatCollapsed(true); persistLayout({ chatCollapsed: true }); }}
                  title="Collapse chat panel (Ctrl+J)"
                  aria-label="Collapse chat panel"
                  className="btn-ghost w-6 h-6 !p-0 items-center justify-center shrink-0"
                >
                  <ChevronDown size={14} />
                </button>
              </div>
              <div className="flex-1 min-h-0 overflow-hidden">
                <ChatPanel
                  mode={mode}
                  repo={repo}
                  disabled={!repo}
                  onContext={handleContext}
                  onTracking={setTracking}
                  onToken={() => setTokenCount((c) => c + 1)}
                  onEvent={setLastEvent}
                  debugMode={debugMode}
                  prefillMessage={prefill}
                  onPrefillConsumed={() => setPrefill(undefined)}
                />
              </div>
            </section>
          )}

          {/* Collapsed chat rail — reopen from the bottom edge */}
          {chatCollapsed && (
            <button
              onClick={() => { setChatCollapsed(false); persistLayout({ chatCollapsed: false }); }}
              className="
                shrink-0 h-9 flex items-center justify-center gap-2
                bg-bg-panel border-t-[1.5px] border-border-subtle
                text-xs font-semibold text-text-secondary hover:bg-bg-panel-alt
                transition-colors
              "
              title="Expand chat panel (Ctrl+J)"
            >
              <MessageSquare size={13} className="text-accent-cyan" />
              AI Assistant
            </button>
          )}
        </main>
      </div>

      {/* Status bar */}
      <StatusBar
        repo={repo}
        repoInfo={repoInfo}
        lastEvent={lastEvent}
        tokenCount={tokenCount}
      />

      {/* Keyboard shortcuts cheat sheet */}
      {showShortcuts && <ShortcutsModal onClose={() => setShowShortcuts(false)} />}
    </div>
  );
}
