import { useEffect, useRef, useState, useCallback } from "react";
import { X, Bot, Sparkles, FolderX, AlertCircle, RefreshCw } from "lucide-react";
import {
  getHarnessAgents,
  getHarnessConfig,
  applyHarnessConfig,
  getHarnessSkills,
  type HarnessAgent,
  type HarnessPreview,
  type HarnessTransport,
  type HarnessApplyResult,
  type HarnessSkill,
} from "../api/client";
import AgentList from "./harness/AgentList";
import PreviewPane from "./harness/PreviewPane";
import SkillsSection from "./harness/SkillsSection";

interface Props {
  localRoot: string | null;
  onClose: () => void;
}

type ModalTab = "config" | "skills";

export default function HarnessModal({ localRoot, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<ModalTab>("config");

  // Registry state
  const [agents, setAgents] = useState<HarnessAgent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [transport, setTransport] = useState<HarnessTransport>("stdio");
  const [registryLoading, setRegistryLoading] = useState(true);
  const [registryError, setRegistryError] = useState<string | null>(null);

  // Preview state
  const [preview, setPreview] = useState<HarnessPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const requestSeqRef = useRef(0);

  // Skills state
  const [skills, setSkills] = useState<HarnessSkill[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsError, setSkillsError] = useState<string | null>(null);

  // Apply state
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyResult, setApplyResult] = useState<HarnessApplyResult | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [isConfirmingWrite, setIsConfirmingWrite] = useState(false);

  // Focus trap refs
  const modalRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  // Save trigger element on open, move focus into the dialog, and restore on unmount
  useEffect(() => {
    triggerRef.current = document.activeElement as HTMLElement | null;
    modalRef.current?.focus();
    return () => {
      triggerRef.current?.focus();
    };
  }, []);

  // Trap focus and close on Escape (or cancel pending write confirmation first)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (isConfirmingWrite) {
          setIsConfirmingWrite(false);
          return;
        }
        onClose();
        return;
      }

      if (e.key === "Tab" && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement as HTMLElement | null;

        // If focus escaped the panel (for example via Shift+Tab from the
        // container itself), pull it back inside.
        if (!active || !modalRef.current.contains(active)) {
          e.preventDefault();
          (e.shiftKey ? last : first).focus();
          return;
        }

        if (e.shiftKey) {
          if (active === first || active === modalRef.current) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (active === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, isConfirmingWrite]);

  // Load Registry
  const loadRegistry = useCallback(async () => {
    if (!localRoot) return;
    setRegistryLoading(true);
    setRegistryError(null);
    try {
      const data = await getHarnessAgents();
      setAgents(data.agents);
      if (data.agents.length > 0) {
        const first = data.agents[0];
        setSelectedAgentId(first.id);
        setTransport(first.default_transport || "stdio");
      }
    } catch (err: unknown) {
      setRegistryError(err instanceof Error ? err.message : "Failed to load agent registry");
    } finally {
      setRegistryLoading(false);
    }
  }, [localRoot]);

  // Load Skills
  const loadSkills = useCallback(async () => {
    setSkillsLoading(true);
    setSkillsError(null);
    try {
      const data = await getHarnessSkills();
      setSkills(data.skills);
    } catch (err: unknown) {
      setSkillsError(err instanceof Error ? err.message : "Failed to load skills descriptors");
    } finally {
      setSkillsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRegistry();
    void loadSkills();
  }, [loadRegistry, loadSkills]);

  // Fetch Preview whenever selectedAgent, transport, or localRoot changes
  const fetchPreview = useCallback(async (
    agentId: string,
    trans: HarnessTransport,
    root: string,
    options?: { preserveApplyState?: boolean },
  ) => {
    const seq = ++requestSeqRef.current;
    setPreviewLoading(true);
    setPreviewError(null);
    if (!options?.preserveApplyState) {
      setApplyResult(null);
      setApplyError(null);
    }

    try {
      const res = await getHarnessConfig({ agent: agentId, transport: trans, root });
      if (seq === requestSeqRef.current) {
        setPreview(res);
      }
    } catch (err: unknown) {
      if (seq === requestSeqRef.current) {
        setPreviewError(err instanceof Error ? err.message : "Failed to generate configuration preview");
        setPreview(null);
      }
    } finally {
      if (seq === requestSeqRef.current) {
        setPreviewLoading(false);
      }
    }
  }, []);

  const prevRootRef = useRef<string | null>(localRoot);

  useEffect(() => {
    if (prevRootRef.current !== localRoot) {
      setPreview(null);
      prevRootRef.current = localRoot;
    }
    if (localRoot && selectedAgentId) {
      void fetchPreview(selectedAgentId, transport, localRoot);
    } else {
      setPreview(null);
    }
  }, [selectedAgentId, transport, localRoot, fetchPreview]);

  // Handle agent selection
  const handleSelectAgent = (id: string) => {
    if (id === selectedAgentId) return;
    setSelectedAgentId(id);
    const agent = agents.find((a) => a.id === id);
    if (agent) {
      // Pick supported transport, default to agent's default
      if (agent.transport.includes(transport)) {
        // keep current transport if supported
      } else {
        setTransport(agent.default_transport || "stdio");
      }
    }
  };

  // Handle transport change
  const handleTransportChange = (newTransport: HarnessTransport) => {
    setTransport(newTransport);
  };

  // Handle apply
  const handleApply = async (force: boolean) => {
    if (!localRoot || !selectedAgentId) return;
    setApplyLoading(true);
    setApplyResult(null);
    setApplyError(null);
    try {
      const result = await applyHarnessConfig({
        agent: selectedAgentId,
        transport,
        root: localRoot,
        apply: true,
        force,
      });
      setApplyResult(result);
      // Re-fetch preview to refresh file exists and diff status without
      // clearing the success result before the user can read it.
      void fetchPreview(selectedAgentId, transport, localRoot, {
        preserveApplyState: true,
      });
    } catch (err: unknown) {
      setApplyError(err instanceof Error ? err.message : "Apply request failed");
    } finally {
      setApplyLoading(false);
    }
  };

  // Backdrop click handler: close only when no unsaved write confirmation in progress
  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;
    if (isConfirmingWrite) {
      return;
    }
    onClose();
  };

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) || null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-3 sm:p-6"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="harness-modal-title"
      data-testid="harness-modal"
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        data-testid="harness-modal-panel"
        onClick={(e) => e.stopPropagation()}
        className="
          w-[1100px] max-w-[95vw] max-h-[90vh] flex flex-col outline-none
          rounded-2xl border border-border-strong shadow-2xl
          bg-bg-panel overflow-hidden
        "
      >
        {/* ── Modal Header ── */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border-subtle bg-bg-panel shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent-cyan/15 text-accent-cyan flex items-center justify-center shrink-0 border border-accent-cyan/30">
              <Bot size={18} />
            </div>
            <div>
              <h2 id="harness-modal-title" className="text-sm font-bold text-text-primary">
                Connect AI Agent — MCP Harness Configurator
              </h2>
              {localRoot ? (
                <p className="text-2xs text-text-muted font-mono truncate max-w-md sm:max-w-xl">
                  Root: <span className="text-text-secondary">{localRoot}</span>
                </p>
              ) : (
                <p className="text-2xs text-accent-rose font-medium">Local repository required</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Tab navigation */}
            <div
              role="tablist"
              aria-label="Harness sections"
              className="flex items-center p-0.5 rounded-lg border border-border-subtle bg-bg-panel-alt mr-2"
            >
              <button
                type="button"
                role="tab"
                id="harness-tab-config"
                aria-controls="harness-panel-config"
                aria-selected={activeTab === "config"}
                onClick={() => setActiveTab("config")}
                className={`
                  flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-150
                  ${
                    activeTab === "config"
                      ? "bg-text-primary text-white shadow-sm"
                      : "text-text-secondary hover:text-text-primary"
                  }
                `}
              >
                <Bot size={13} />
                <span>Agents</span>
              </button>
              <button
                type="button"
                role="tab"
                id="harness-tab-skills"
                aria-controls="harness-panel-skills"
                aria-selected={activeTab === "skills"}
                onClick={() => setActiveTab("skills")}
                className={`
                  flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-150
                  ${
                    activeTab === "skills"
                      ? "bg-accent-cyan text-white shadow-sm"
                      : "text-text-secondary hover:text-text-primary"
                  }
                `}
              >
                <Sparkles size={13} />
                <span>Skills</span>
                <span className="text-[10px] px-1 rounded bg-white/20 ml-0.5 font-mono">P4</span>
              </button>
            </div>

            <button
              onClick={onClose}
              aria-label="Close harness modal"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-panel-hover transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Modal Body ── */}
        <div className="flex-1 overflow-hidden min-h-0">
          {!localRoot ? (
            /* Empty State: No local root */
            <div className="h-full py-16 px-6 flex flex-col items-center justify-center text-center max-w-md mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-amber-500/15 text-amber-700 flex items-center justify-center mb-4 border border-amber-500/30">
                <FolderX size={24} />
              </div>
              <h3 className="text-base font-bold text-text-primary mb-2">Local Repository Required</h3>
              <p className="text-xs text-text-muted leading-relaxed mb-6">
                The harness configurator generates exact MCP configuration files directly in your repository (such as{" "}
                <code className="font-mono bg-bg-panel-alt px-1 py-0.5 rounded border border-border-subtle">.mcp.json</code>,{" "}
                <code className="font-mono bg-bg-panel-alt px-1 py-0.5 rounded border border-border-subtle">.cursor/mcp.json</code>, etc.).
                Browser-only folder previews have no local path on disk.
              </p>
              <div className="p-3 rounded-xl bg-bg-panel-alt border border-border-subtle text-xs text-text-secondary text-left w-full mb-6 font-mono leading-relaxed">
                <div className="text-2xs text-text-muted uppercase tracking-wider mb-1 font-sans font-bold">To use harness:</div>
                reposcope run /path/to/repository
              </div>
              <button onClick={onClose} className="btn-secondary !text-xs !py-1.5 !px-4">
                Close
              </button>
            </div>
          ) : activeTab === "skills" ? (
            /* Skills Tab */
            <div
              role="tabpanel"
              id="harness-panel-skills"
              aria-labelledby="harness-tab-skills"
              className="p-5 overflow-y-auto max-h-[calc(90vh-80px)]"
            >
              <SkillsSection skills={skills} loading={skillsLoading} error={skillsError} />
            </div>
          ) : registryLoading ? (
            /* Loading Registry */
            <div className="h-full py-20 flex flex-col items-center justify-center gap-3 text-text-muted">
              <span className="btn-spinner" />
              <span className="text-xs">Loading AI agent registry...</span>
            </div>
          ) : registryError ? (
            /* Error Loading Registry */
            <div className="h-full py-16 px-6 flex flex-col items-center justify-center text-center max-w-md mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-rose-500/15 text-rose-700 flex items-center justify-center mb-4 border border-rose-500/30">
                <AlertCircle size={24} />
              </div>
              <h3 className="text-base font-bold text-text-primary mb-2">Failed to Load Agents</h3>
              <p className="text-xs text-text-muted leading-relaxed mb-6">{registryError}</p>
              <button onClick={loadRegistry} className="btn-primary !text-xs !py-1.5 !px-4">
                <RefreshCw size={13} className="mr-1" /> Retry
              </button>
            </div>
          ) : (
            /* Main Configurator: 2-column layout */
            <div
              role="tabpanel"
              id="harness-panel-config"
              aria-labelledby="harness-tab-config"
              className="h-full flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-border-subtle"
            >
              {/* Left Column: Agent List */}
              <div className="w-full md:w-72 lg:w-80 p-4 shrink-0 overflow-y-auto max-h-[220px] md:max-h-[calc(90vh-70px)] bg-bg-panel">
                <div className="flex items-center justify-between mb-2 px-1">
                  <span className="label-caps !text-[10px]">Select Agent ({agents.length})</span>
                  <span className="text-[10px] text-text-muted font-mono">9 supported</span>
                </div>
                <AgentList
                  agents={agents}
                  selectedId={selectedAgentId}
                  onSelect={handleSelectAgent}
                />
              </div>

              {/* Right Column: Preview & Apply Pane */}
              <div className="flex-1 p-5 overflow-y-auto max-h-[calc(90vh-140px)] md:max-h-[calc(90vh-70px)] bg-bg-panel min-w-0">
                <PreviewPane
                  preview={preview}
                  selectedAgent={selectedAgent}
                  transport={transport}
                  onTransportChange={handleTransportChange}
                  loading={previewLoading}
                  error={previewError}
                  onRetry={() => {
                    if (localRoot && selectedAgentId) {
                      void fetchPreview(selectedAgentId, transport, localRoot);
                    }
                  }}
                  onApply={handleApply}
                  applyLoading={applyLoading}
                  applyResult={applyResult}
                  applyError={applyError}
                  isConfirmingWrite={isConfirmingWrite}
                  onConfirmingWriteChange={setIsConfirmingWrite}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
