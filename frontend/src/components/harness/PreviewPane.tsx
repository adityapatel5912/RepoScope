import { useState, useEffect } from "react";
import {
  Copy,
  Check,
  Terminal,
  FileText,
  AlertTriangle,
  Info,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import type {
  HarnessAgent,
  HarnessPreview,
  HarnessTransport,
  HarnessApplyResult,
} from "../../api/client";
import DiffViewer from "./DiffViewer";

interface Props {
  preview: HarnessPreview | null;
  selectedAgent: HarnessAgent | null;
  transport: HarnessTransport;
  onTransportChange: (t: HarnessTransport) => void;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onApply: (force: boolean) => Promise<void>;
  applyLoading: boolean;
  applyResult: HarnessApplyResult | null;
  applyError: string | null;
  isConfirmingWrite?: boolean;
  onConfirmingWriteChange?: (confirming: boolean) => void;
}

export default function PreviewPane({
  preview,
  selectedAgent,
  transport,
  onTransportChange,
  loading,
  error,
  onRetry,
  onApply,
  applyLoading,
  applyResult,
  applyError,
  isConfirmingWrite,
  onConfirmingWriteChange,
}: Props) {
  const [activeFileIdx, setActiveFileIdx] = useState(0);
  const [copiedCommand, setCopiedCommand] = useState(false);
  const [copiedContent, setCopiedContent] = useState(false);
  const [force, setForce] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [viewDiff, setViewDiff] = useState(true);

  const handleSetConfirm = (val: boolean) => {
    setShowConfirm(val);
    onConfirmingWriteChange?.(val);
  };

  // Reset file tab and force checkbox when preview changes
  useEffect(() => {
    setActiveFileIdx(0);
    setForce(false);
    setShowConfirm(false);
    onConfirmingWriteChange?.(false);
    setViewDiff(true);
  }, [preview?.agent, preview?.transport, onConfirmingWriteChange]);

  // Synchronize with external cancellation (e.g., Escape)
  useEffect(() => {
    if (isConfirmingWrite === false) {
      setShowConfirm(false);
    }
  }, [isConfirmingWrite]);

  const copyToClipboard = async (text: string, type: "command" | "content") => {
    try {
      await navigator.clipboard.writeText(text);
      if (type === "command") {
        setCopiedCommand(true);
        setTimeout(() => setCopiedCommand(false), 2000);
      } else {
        setCopiedContent(true);
        setTimeout(() => setCopiedContent(false), 2000);
      }
    } catch {
      /* fallback */
    }
  };

  if (loading) {
    return (
      <div
        className="h-full min-h-[360px] flex flex-col items-center justify-center gap-3 text-text-muted"
        data-testid="harness-preview"
      >
        <span className="btn-spinner" />
        <span className="text-xs">Generating agent configuration preview...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="h-full min-h-[360px] flex flex-col items-center justify-center p-6 text-center"
        data-testid="harness-preview"
      >
        <div className="w-10 h-10 rounded-full bg-rose-500/10 text-rose-600 flex items-center justify-center mb-3">
          <AlertTriangle size={20} />
        </div>
        <h4 className="text-sm font-bold text-text-primary mb-1">Configuration Preview Failed</h4>
        <p className="text-xs text-text-muted max-w-sm mb-4 leading-relaxed">{error}</p>
        <button onClick={onRetry} className="btn-secondary !text-xs !py-1.5 !px-3">
          Retry Preview
        </button>
      </div>
    );
  }

  if (!preview || !selectedAgent) {
    return (
      <div
        className="h-full min-h-[360px] flex flex-col items-center justify-center text-text-muted text-xs"
        data-testid="harness-preview"
      >
        Select an agent to preview configuration.
      </div>
    );
  }

  const activeFile = preview.files[activeFileIdx] || preview.files[0];
  const isApplyDisabled = !preview.apply_enabled;
  const canApply = preview.apply_enabled && (!preview.requires_force || force);

  return (
    <div
      className="flex flex-col gap-4 min-w-0"
      data-testid="harness-preview"
      id="harness-preview-panel"
    >
      {/* ── Top controls: Transport selector & agent metadata ── */}
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-border-subtle flex-wrap">
        <div>
          <h3 className="text-sm font-bold text-text-primary flex items-center gap-2">
            <span>{selectedAgent.label}</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-bg-panel-alt border border-border-subtle text-text-muted">
              {preview.files.length} file{preview.files.length === 1 ? "" : "s"}
            </span>
          </h3>
          <p className="text-2xs text-text-muted mt-0.5 font-mono">
            Verified {selectedAgent.verified_at}
          </p>
        </div>

        {/* Transport Switcher */}
        <div className="flex items-center gap-2">
          <span className="text-2xs font-semibold text-text-muted uppercase tracking-wider">
            Transport:
          </span>
          <div className="flex flex-col items-end">
            <div
              role="radiogroup"
              aria-label="Transport Protocol"
              className="flex items-center p-0.5 rounded-lg border border-border-subtle bg-bg-panel-alt"
            >
              {(["stdio", "http"] as HarnessTransport[]).map((t) => {
                const supported = selectedAgent.transport.includes(t);
                const active = transport === t;
                return (
                  <button
                    key={t}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    disabled={!supported}
                    aria-describedby={!supported ? `transport-${t}-unsupported` : undefined}
                    onClick={() => onTransportChange(t)}
                    className={`
                      px-2.5 py-1 rounded-md text-xs font-mono font-semibold transition-all duration-150
                      ${
                        active
                          ? "bg-accent-cyan text-white shadow-sm"
                          : supported
                          ? "text-text-secondary hover:text-text-primary"
                          : "text-text-muted/40 cursor-not-allowed opacity-50"
                      }
                    `}
                  >
                    {t}
                  </button>
                );
              })}
            </div>
            {(["stdio", "http"] as HarnessTransport[]).map((t) => {
              const supported = selectedAgent.transport.includes(t);
              if (supported) return null;
              return (
                <span
                  key={t}
                  id={`transport-${t}-unsupported`}
                  className="text-[10px] text-amber-700 mt-1"
                >
                  {t.toUpperCase()} transport is not supported by {selectedAgent.label}.
                </span>
              );
            })}
          </div>
        </div>
      </div>

      {/* Warnings & Global Path Notices */}
      {preview.warnings.length > 0 && (
        <div className="p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 flex flex-col gap-1 text-xs text-amber-900">
          <div className="flex items-center gap-1.5 font-bold">
            <AlertTriangle size={14} className="text-amber-700" />
            <span>Notices & Warnings</span>
          </div>
          <ul className="list-disc list-inside text-2xs space-y-0.5 text-amber-800">
            {preview.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {selectedAgent.global_preview_paths?.length > 0 && (
        <div className="p-2.5 rounded-lg border border-border-subtle bg-bg-panel-alt flex items-center gap-2 text-2xs text-text-muted">
          <Info size={13} className="shrink-0 text-accent-cyan" />
          <span>
            <strong className="text-text-secondary">Display-only global paths:</strong>{" "}
            {selectedAgent.global_preview_paths.join(", ")} (never written by RepoScope).
          </span>
        </div>
      )}

      {/* ── Command section ── */}
      <div className="card p-3 bg-bg-panel-alt/50 border-border-subtle">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-2">
            {preview.command_kind === "deeplink" ? (
              <ExternalLink size={14} className="text-accent-cyan" />
            ) : (
              <Terminal size={14} className="text-accent-cyan" />
            )}
            <span className="text-xs font-bold text-text-primary">
              {preview.command_kind === "deeplink" ? "Agent Deeplink" : "Agent Command"}
            </span>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-accent-cyan/15 text-accent-cyan font-bold">
              {preview.command_kind}
            </span>
          </div>
          <button
            onClick={() => copyToClipboard(preview.command, "command")}
            aria-label={
              preview.command_kind === "deeplink"
                ? "Copy exact agent deeplink"
                : "Copy exact agent command"
            }
            className="flex items-center gap-1 px-2 py-1 rounded text-2xs font-medium text-text-secondary hover:text-text-primary hover:bg-bg-panel transition-colors border border-border-subtle"
          >
            {copiedCommand ? <Check size={12} className="text-accent-emerald" /> : <Copy size={12} />}
            <span>
              {copiedCommand
                ? "Copied"
                : preview.command_kind === "deeplink"
                ? "Copy link"
                : "Copy command"}
            </span>
          </button>
        </div>
        <p className="text-2xs text-text-muted mb-2 leading-relaxed">{preview.command_note}</p>
        <pre className="p-2.5 rounded-lg bg-bg-panel border border-border-subtle font-mono text-xs overflow-x-auto whitespace-pre-wrap break-all text-text-primary selection:bg-accent-cyan/20">
          {preview.command}
        </pre>
      </div>

      {/* ── Files section ── */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          {/* File tabs */}
          <div role="tablist" aria-label="Configuration files" className="flex items-center gap-1.5 overflow-x-auto py-1">
            {preview.files.map((file, idx) => {
              const isActive = idx === activeFileIdx;
              return (
                <button
                  key={file.path}
                  role="tab"
                  id={`harness-file-tab-${idx}`}
                  aria-controls={`harness-file-panel-${idx}`}
                  aria-selected={isActive}
                  onClick={() => setActiveFileIdx(idx)}
                  className={`
                    flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono transition-all duration-150 border
                    ${
                      isActive
                        ? "bg-text-primary text-white border-text-primary shadow-sm"
                        : "bg-bg-panel text-text-secondary border-border-subtle hover:bg-bg-panel-alt hover:text-text-primary"
                    }
                  `}
                >
                  <FileText size={12} />
                  <span>{file.path}</span>
                  {file.exists && (
                    <span
                      className={`text-[9px] px-1 rounded uppercase font-sans font-bold ${
                        isActive ? "bg-white/20 text-white" : "bg-amber-500/20 text-amber-800"
                      }`}
                    >
                      Exists
                    </span>
                  )}
                  {file.diff && (
                    <span
                      className={`text-[9px] px-1 rounded uppercase font-sans font-bold ${
                        isActive ? "bg-white/20 text-white" : "bg-accent-cyan/20 text-accent-cyan"
                      }`}
                    >
                      Diff
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Copy file button & Diff toggle */}
          {activeFile && (
            <div className="flex items-center gap-1.5 shrink-0">
              {activeFile.diff && (
                <button
                  onClick={() => setViewDiff((v) => !v)}
                  className="px-2 py-1 rounded text-2xs font-semibold border border-border-subtle text-text-secondary hover:bg-bg-panel-alt"
                >
                  {viewDiff ? "Show full content" : "Show diff"}
                </button>
              )}
              <button
                onClick={() => copyToClipboard(activeFile.content, "content")}
                aria-label={`Copy content of ${activeFile.path}`}
                className="flex items-center gap-1 px-2 py-1 rounded text-2xs font-medium text-text-secondary hover:text-text-primary hover:bg-bg-panel-alt transition-colors border border-border-subtle"
              >
                {copiedContent ? <Check size={12} className="text-accent-emerald" /> : <Copy size={12} />}
                <span>{copiedContent ? "Copied" : "Copy file"}</span>
              </button>
            </div>
          )}
        </div>

        {/* File content display */}
        {activeFile && (
          <div
            role="tabpanel"
            id={`harness-file-panel-${activeFileIdx}`}
            aria-labelledby={`harness-file-tab-${activeFileIdx}`}
            className="flex flex-col gap-2"
          >
            {activeFile.diff && (
              <div
                className="p-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 flex items-center gap-2 text-xs text-amber-900 font-medium"
                data-testid="existing-file-warning"
              >
                <AlertTriangle size={15} className="text-amber-700 shrink-0" />
                <span>
                  <strong>Existing file will change:</strong> a configuration already exists on disk. Review the unified diff before writing.
                </span>
              </div>
            )}
            {activeFile.diff && viewDiff ? (
              <DiffViewer diff={activeFile.diff} />
            ) : (
              <pre
                className="p-3 rounded-lg border border-border-subtle bg-bg-panel-alt font-mono text-xs overflow-x-auto whitespace-pre leading-relaxed max-h-72 text-text-primary"
                data-testid={`harness-file-content-${activeFile.path.replace(/[/.]/g, "-")}`}
              >
                {activeFile.content}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* ── Apply Result / Success State ── */}
      {applyResult && (
        <div
          className="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 flex items-start gap-2.5 text-xs text-emerald-900"
          data-testid="harness-apply-success"
        >
          <CheckCircle2 size={16} className="text-emerald-700 shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1">
            <span className="font-bold">Configuration written successfully!</span>
            {applyResult.applied.length > 0 && (
              <span className="text-2xs font-mono">
                Applied files: {applyResult.applied.join(", ")}
              </span>
            )}
            {applyResult.unchanged.length > 0 && (
              <span className="text-2xs font-mono text-emerald-800/80">
                Unchanged files: {applyResult.unchanged.join(", ")}
              </span>
            )}
            <span className="text-2xs text-emerald-800 mt-1">
              Restart your AI agent or reload its workspace to activate RepoScope MCP tools.
            </span>
          </div>
        </div>
      )}

      {/* ── Apply Error ── */}
      {applyError && (
        <div className="p-3 rounded-xl border border-rose-500/30 bg-rose-500/10 flex items-center gap-2 text-xs text-rose-900">
          <AlertTriangle size={15} className="text-rose-700 shrink-0" />
          <span>Apply failed: {applyError}</span>
        </div>
      )}

      {/* ── Apply / Action Section ── */}
      <div className="pt-3 border-t border-border-subtle flex flex-col gap-2.5">
        {preview.requires_force && preview.apply_enabled && (
          <label className="flex items-center gap-2 text-xs text-amber-900 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20 cursor-pointer">
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              className="rounded border-amber-400 text-accent-cyan focus:ring-accent-cyan"
            />
            <span className="font-semibold">
              Overwrite existing file modifications (force apply required for changed files)
            </span>
          </label>
        )}

        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            {isApplyDisabled ? (
              <p
                id="apply-disabled-reason"
                className="text-2xs text-text-muted leading-relaxed"
              >
                Server writes are disabled. Start server with{" "}
                <code className="font-mono bg-bg-panel-alt px-1 py-0.5 rounded border border-border-subtle">
                  REPOSCOPE_HARNESS_APPLY=1
                </code>{" "}
                to enable writing configuration files.
              </p>
            ) : preview.requires_force && !force ? (
              <p className="text-2xs text-amber-700 leading-relaxed">
                Check the confirmation box above to allow updating existing configuration files.
              </p>
            ) : (
              <p className="text-2xs text-text-muted leading-relaxed">
                Atomic write to repository files. Non-RepoScope configuration keys are preserved.
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {showConfirm ? (
              <div className="flex items-center gap-2 bg-amber-500/10 p-1.5 rounded-lg border border-amber-500/30">
                <span className="text-2xs font-semibold text-amber-900 px-1">
                  Write files to disk?
                </span>
                <button
                  type="button"
                  onClick={() => handleSetConfirm(false)}
                  className="btn-secondary !py-1 !px-2 !text-2xs"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  data-testid="harness-apply-confirm"
                  onClick={async () => {
                    handleSetConfirm(false);
                    await onApply(force);
                  }}
                  disabled={applyLoading}
                  className="btn-primary !py-1 !px-2.5 !text-2xs !bg-accent-emerald !border-accent-emerald"
                >
                  {applyLoading ? <span className="btn-spinner" /> : null}
                  Confirm Write
                </button>
              </div>
            ) : (
              <button
                type="button"
                data-testid="harness-apply"
                disabled={!canApply || applyLoading}
                aria-describedby={isApplyDisabled ? "apply-disabled-reason" : undefined}
                onClick={() => handleSetConfirm(true)}
                className="btn-primary !py-1.5 !px-3.5 !text-xs disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {applyLoading ? <span className="btn-spinner" /> : null}
                Write files
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
