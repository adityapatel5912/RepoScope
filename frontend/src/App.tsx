import { useState, useCallback, useRef, useEffect } from "react";
import TopBar from "./components/TopBar";
import LeftPanel from "./components/LeftPanel";
import GraphCanvas from "./components/GraphView";
import ChatPanel from "./components/ChatPanel";
import StatusBar from "./components/StatusBar";
import Toasts from "./components/Toasts";
import ShortcutsModal from "./components/ShortcutsModal";
import EditorSettings from "./components/EditorSettings";
import { useKeyboard } from "./hooks/useKeyboard";
import { useRepoLoader } from "./hooks/useRepoLoader";
import type { TourGraphState } from "./components/GraphView";
import { FolderTree, MessageSquare, ChevronDown } from "lucide-react";
import { getGraph, getStatus } from "./api/client";
import type { ContextPayload } from "./api/client";
import { streamLocalEvents } from "./api/local";
import { openInEditor } from "./utils/openInEditor";
import { loadIdePrefs, type IdePrefs } from "./utils/ideLinks";

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
  /**
   * True when the loaded repository is a local directory.
   *
   * It drives the LOCAL MODE badge and the live-update subscription. Both
   * are local-mode-only: a repository cloned from GitHub is a snapshot in
   * a temp directory, and there is nothing to watch.
   */
  const [isLocal, setIsLocal] = useState(false);
  /** A short label for the last live-graph update, shown in the status bar. */
  const [liveUpdate, setLiveUpdate] = useState<string | null>(null);
  /**
   * The absolute path of the repository on this machine.
   *
   * In local mode the backend knows it — it is reading the files off
   * the disk. That is what lets "Open in editor" work with no
   * configuration at all.
   */
  const [localRoot, setLocalRoot] = useState<string | null>(null);
  /** The editor settings modal. */
  const [showEditorSettings, setShowEditorSettings] = useState(false);
  const [idePrefs, setIdePrefs] = useState<IdePrefs>(() => loadIdePrefs());

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
        // The load response does not carry graph counts — take them from the
        // graph itself so the Repository card is not left showing "—".
        setRepoInfo((prev) =>
          prev
            ? {
                ...prev,
                node_count: g.nodes.length,
                edge_count: (g.edges ?? []).length,
              }
            : prev,
        );
      }
    }).catch(() => { /* graph fetch failed — will populate on first chat query instead */ });
  }, []);

  const loader = useRepoLoader(handleLoaded);

  // ── Pick up a repository that is already loaded on the backend ───────────
  // The CLI loads the repository server-side (`reposcope run .`), so the
  // browser must show it on open instead of waiting for someone to type a
  // GitHub URL. This is also what lets the browser-QA harness render a
  // graph without cloning anything over the network.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [status, graph] = await Promise.all([getStatus(), getGraph()]);
        if (cancelled) return;
        const loadedRepo = status?.repo as string | undefined;
        if (loadedRepo) {
          const owner = (status?.owner as string | undefined) ?? "";
          const readme = (status?.readme as string | undefined) ?? "";
          setRepo(owner ? `${owner}/${loadedRepo}` : loadedRepo);
          setRepoInfo({
            owner,
            repo: loadedRepo,
            file_count: status?.file_count as number | undefined,
            node_count: graph?.nodes?.length ?? undefined,
            edge_count: graph?.edges?.length ?? undefined,
            readme_length: readme.length || undefined,
          });
        }
        // `is_local` is set by `load_local_repo` — the CLI's path. It is
        // what tells the UI to show the privacy badge and to subscribe to
        // the live-graph stream.
        setIsLocal(Boolean(status?.is_local));
        // In local mode the backend knows the absolute path of the
        // repository, which is what makes "Open in editor" work without
        // the user configuring a workspace root.
        const root = (status?.local_path as string | undefined) ?? "";
        setLocalRoot(status?.is_local ? root || null : null);
        if (graph?.nodes?.length) {
          setRawNodes(graph.nodes);
          setRawEdges(graph.edges ?? []);
        }
      } catch {
        // No repository loaded — the empty state is the correct UI.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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

  // ── Open in the editor (Milestone 2.1) ───────────────────────────────────
  //
  // "Always ask" is honoured here rather than inside the helper, so the
  // confirmation is a normal browser dialog the user already knows.
  const handleOpenInEditor = useCallback(
    async (path: string, line: number) => {
      if (idePrefs.alwaysAsk) {
        const target = line ? `${path}:${line}` : path;
        const ok = window.confirm(`Open ${target} in your editor?`);
        if (!ok) return;
      }
      await openInEditor({ path, line }, localRoot);
    },
    [idePrefs.alwaysAsk, localRoot],
  );

  // ── Live graph (local mode) ───────────────────────────────────────────────
  //
  // The backend watches the repository and pushes a fresh `context` event
  // whenever it re-indexes. The payload has the SAME shape as the chat
  // stream's `context` event, so the existing handler renders it — there
  // is no second rendering path, which is why the live graph needed no
  // changes to the graph components.
  //
  // The stream is only opened in local mode. A repository cloned from
  // GitHub is a snapshot; there is nothing to watch.
  useEffect(() => {
    if (!isLocal) return;

    const controller = new AbortController();
    let closed = false;

    void streamLocalEvents(
      {
        onContext: (live) => {
          if (closed) return;
          setRawNodes(live.nodes ?? []);
          setRawEdges(live.edges ?? []);
          // The counts must move with the graph. The Repository card
          // shows the node and edge counts, and a live update that left
          // them stale would tell the user the graph had not changed —
          // while the canvas silently showed a different one.
          setRepoInfo((prev) =>
            prev
              ? {
                  ...prev,
                  node_count: live.node_count ?? prev.node_count,
                  edge_count: live.edge_count ?? prev.edge_count,
                }
              : prev,
          );
          const changed = live.changed?.length ?? 0;
          const removed = live.removed?.length ?? 0;
          setLiveUpdate(
            `live: ${changed} changed${removed ? `, ${removed} removed` : ""}` +
              (live.duration_ms ? ` in ${live.duration_ms.toFixed(0)} ms` : ""),
          );
        },
        onReady: () => {
          if (!closed) setLiveUpdate("watching for changes");
        },
        onError: (message) => {
          if (!closed) setLiveUpdate(message);
        },
      },
      controller.signal,
    ).then(() => {
      if (!closed) setLiveUpdate("live updates stopped");
    });

    return () => {
      closed = true;
      controller.abort();
    };
  }, [isLocal]);

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
        isLocal={isLocal}
        onOpenEditorSettings={() => setShowEditorSettings(true)}
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
              onOpenInEditor={handleOpenInEditor}
              localRoot={localRoot}
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
        liveUpdate={liveUpdate}
      />

      {/* Keyboard shortcuts cheat sheet */}
      {showShortcuts && <ShortcutsModal onClose={() => setShowShortcuts(false)} />}

      {/* Editor settings — which editor, which workspace root, always ask */}
      {showEditorSettings && (
        <EditorSettings
          onClose={() => setShowEditorSettings(false)}
          onChange={setIdePrefs}
        />
      )}
    </div>
  );
}
