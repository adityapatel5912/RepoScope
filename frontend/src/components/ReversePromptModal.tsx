/**
 * ReversePromptModal.tsx
 * Four-mode reverse-prompt compiler UI (Phase 6, V2.6).
 *
 * Supported modes:
 * - context: compact/skeleton context pack fitting token budget
 * - rebuild: topological build order, cycle warnings, stack, routes, models
 * - feature: target node + 2-hop interface closure
 * - spec: CLAUDE.md, AGENTS.md, llms.txt, .kiro/specs/* templates
 */
import { useEffect, useState, useCallback } from "react";
import { Copy, Check, Save, X, Zap, Layers, Box, Cpu, FileCode2, Loader2 } from "lucide-react";
import { generateReversePrompt, type ReversePrompt, type ReversePromptFile } from "../api/features";

type PromptMode = "context" | "rebuild" | "feature" | "spec";

interface Props {
  open: boolean;
  prompt: string;
  onClose: () => void;
  /** Generates + opens the starter scaffold (CodeCrafters-style). */
  onScaffold?: () => void;
  selectedNodeId?: string | null;
}

export default function ReversePromptModal({
  open,
  prompt: initialPrompt,
  onClose,
  onScaffold,
  selectedNodeId,
}: Props) {
  const [mode, setMode] = useState<PromptMode>("context");
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);
  const [cache, setCache] = useState<Record<string, ReversePrompt>>({});
  const [activeFileIdx, setActiveFileIdx] = useState<number>(-1); // -1 means all files / unified

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Seed cache with initial prompt if provided
  useEffect(() => {
    if (!open) return;
    if (initialPrompt && !cache["context"]) {
      setCache((prev) => ({
        ...prev,
        context: {
          prompt: initialPrompt,
          content: initialPrompt,
          mode: "context",
          ok: true,
          tokens: Math.round(initialPrompt.length / 4),
          files: [],
        },
      }));
    }
  }, [open, initialPrompt, cache]);

  // Fetch mode data when mode changes if not cached
  const loadMode = useCallback(
    async (targetMode: PromptMode) => {
      setMode(targetMode);
      setActiveFileIdx(-1);

      if (cache[targetMode]) {
        return;
      }

      setLoading(true);
      try {
        const data = await generateReversePrompt({
          mode: targetMode,
          target_node_id: selectedNodeId || undefined,
        });
        setCache((prev) => ({
          ...prev,
          [targetMode]: data,
        }));
      } catch (err) {
        console.error("Failed to compile reverse prompt mode:", targetMode, err);
      } finally {
        setLoading(false);
      }
    },
    [cache, selectedNodeId]
  );

  if (!open) return null;

  const currentData = cache[mode] ?? (mode === "context" && initialPrompt ? {
    prompt: initialPrompt,
    content: initialPrompt,
    mode: "context",
    tokens: Math.round(initialPrompt.length / 4),
    files: [],
  } : undefined);

  const files: ReversePromptFile[] = currentData?.files ?? [];
  const activeFile = activeFileIdx >= 0 && activeFileIdx < files.length ? files[activeFileIdx] : null;

  // The displayed text in the textarea
  const displayedContent = activeFile ? activeFile.content : (currentData?.content || currentData?.prompt || initialPrompt || "");
  const tokenCount = currentData?.tokens ?? Math.round(displayedContent.length / 4);

  const copy = () => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard
        .writeText(displayedContent)
        .then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        })
        .catch(() => {
          try {
            const ta = document.createElement("textarea");
            ta.value = displayedContent;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
          } catch {
            // noop
          }
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
    } else {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const saveMd = () => {
    const filename = activeFile ? activeFile.path.replace(/[/\\]/g, "_") : `reposcope-${mode}-blueprint.md`;
    const blob = new Blob([displayedContent], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label="Reverse build prompt"
      data-testid="reverse-prompt-modal"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-5xl h-[88vh] flex flex-col p-5 !shadow-lg pop-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-3 shrink-0 flex-wrap gap-2">
          <div className="min-w-0 flex items-center gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="h3">Reverse-Prompt Compiler</h2>
                <span
                  data-testid="token-count-badge"
                  className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-surface-secondary text-text-muted border border-border"
                >
                  ~{tokenCount.toLocaleString()} tokens
                </span>
                {files.length > 0 && (
                  <span
                    data-testid="file-count-badge"
                    className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-surface-secondary text-text-muted border border-border"
                  >
                    {files.length} {files.length === 1 ? "file" : "files"}
                  </span>
                )}
              </div>
              <p className="text-xs text-text-muted mt-0.5">
                Deterministic blueprint compiled directly from the AST knowledge graph
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap shrink-0">
            <button
              onClick={copy}
              data-testid="copy-prompt-btn"
              className="btn-primary !py-1.5 !px-3 !text-xs flex items-center gap-1.5"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              onClick={saveMd}
              data-testid="download-prompt-btn"
              className="btn-secondary !py-1.5 !px-3 !text-xs flex items-center gap-1.5"
            >
              <Save size={12} />
              Save as .md
            </button>
            {onScaffold && (
              <button onClick={onScaffold} className="btn-secondary !py-1.5 !px-3 !text-xs flex items-center gap-1.5">
                <Zap size={12} className="text-accent-amber" />
                Scaffold
              </button>
            )}
            <button
              onClick={onClose}
              aria-label="Close"
              data-testid="close-modal-btn"
              className="btn-ghost w-8 h-8 !p-0 items-center justify-center shrink-0"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* 4 Mode Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-surface-secondary rounded-lg mb-3 shrink-0 border border-border">
          <button
            onClick={() => void loadMode("context")}
            data-testid="mode-tab-context"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              mode === "context"
                ? "bg-surface-elevated text-text shadow-sm border border-border font-semibold"
                : "text-text-muted hover:text-text hover:bg-surface-elevated/50"
            }`}
          >
            <Layers size={13} />
            Context Pack
          </button>

          <button
            onClick={() => void loadMode("rebuild")}
            data-testid="mode-tab-rebuild"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              mode === "rebuild"
                ? "bg-surface-elevated text-text shadow-sm border border-border font-semibold"
                : "text-text-muted hover:text-text hover:bg-surface-elevated/50"
            }`}
          >
            <Cpu size={13} />
            Rebuild Blueprint
          </button>

          <button
            onClick={() => void loadMode("feature")}
            data-testid="mode-tab-feature"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              mode === "feature"
                ? "bg-surface-elevated text-text shadow-sm border border-border font-semibold"
                : "text-text-muted hover:text-text hover:bg-surface-elevated/50"
            }`}
          >
            <Box size={13} />
            Feature Slice
          </button>

          <button
            onClick={() => void loadMode("spec")}
            data-testid="mode-tab-spec"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              mode === "spec"
                ? "bg-surface-elevated text-text shadow-sm border border-border font-semibold"
                : "text-text-muted hover:text-text hover:bg-surface-elevated/50"
            }`}
          >
            <FileCode2 size={13} />
            Spec Bundle
          </button>
        </div>

        {/* Spec Mode File Sub-tabs (when multiple files exist) */}
        {files.length > 1 && (
          <div className="flex items-center gap-1 overflow-x-auto pb-2 mb-2 shrink-0 border-b border-border/50 text-xs">
            <button
              onClick={() => setActiveFileIdx(-1)}
              data-testid="file-tab-all"
              className={`px-2.5 py-1 rounded text-xs font-mono whitespace-nowrap transition-colors ${
                activeFileIdx === -1
                  ? "bg-surface-elevated font-semibold text-text border border-border"
                  : "text-text-muted hover:text-text"
              }`}
            >
              Unified Bundle ({files.length} files)
            </button>
            {files.map((file, idx) => (
              <button
                key={file.path}
                onClick={() => setActiveFileIdx(idx)}
                data-testid={`file-tab-${idx}`}
                className={`px-2.5 py-1 rounded text-xs font-mono whitespace-nowrap transition-colors ${
                  activeFileIdx === idx
                    ? "bg-surface-elevated font-semibold text-text border border-border"
                    : "text-text-muted hover:text-text"
                }`}
              >
                {file.path}
              </button>
            ))}
          </div>
        )}

        {/* Loading overlay or Prompt body */}
        <div className="relative flex-1 min-h-0 flex flex-col">
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 text-text-muted">
              <Loader2 className="animate-spin text-accent-indigo" size={24} />
              <span className="text-xs">Compiling {mode} blueprint from graph...</span>
            </div>
          ) : (
            <textarea
              readOnly
              value={displayedContent}
              data-testid="reverse-prompt-textarea"
              aria-label="Generated build prompt"
              className="
                input flex-1 min-h-0 !resize-none font-mono !text-[13px] leading-relaxed
                whitespace-pre-wrap select-text
              "
              onFocus={(e) => e.currentTarget.select()}
            />
          )}
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between mt-3 shrink-0 text-[11px] text-text-muted">
          <span>
            {mode === "rebuild" && "Topological build order with cycle detection and API route contracts."}
            {mode === "feature" && "Self-contained 2-hop interface closure with contract signatures."}
            {mode === "spec" && "Deterministic CLAUDE.md, AGENTS.md, llms.txt, and .kiro/specs/* templates."}
            {mode === "context" && "Token-budgeted skeleton context pack."}
          </span>
          <span className="font-mono">100% graph-derived • Deterministic</span>
        </div>
      </div>
    </div>
  );
}
