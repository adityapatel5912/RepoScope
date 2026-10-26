/**
 * ReversePromptModal.tsx
 * Displays the agent-ready "Reverse Build Prompt" generated from the
 * loaded repo. Read-only mono textarea + copy + save-as-.md.
 * Modal styling per FILE 1: white card, black border, hard offset shadow.
 */
import { useEffect, useState } from "react";
import { Copy, Check, Save, X } from "lucide-react";

interface Props {
  open: boolean;
  prompt: string;
  onClose: () => void;
}

export default function ReversePromptModal({ open, prompt, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const copy = () => {
    navigator.clipboard.writeText(prompt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const saveMd = () => {
    const blob = new Blob([prompt], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "reposcope-build-prompt.md";
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
      onClick={onClose}
    >
      <div
        className="card w-full max-w-4xl h-[85vh] flex flex-col p-5 !shadow-lg pop-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-3 shrink-0">
          <div>
            <h2 className="h3">Build Prompt</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Agent-ready prompt reverse-engineered from this repository
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={copy} className="btn-primary !py-1.5 !px-3 !text-xs">
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button onClick={saveMd} className="btn-secondary !py-1.5 !px-3 !text-xs">
              <Save size={12} />
              Save as .md
            </button>
            <button
              onClick={onClose}
              aria-label="Close"
              className="btn-ghost w-8 h-8 !p-0 items-center justify-center"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Prompt body — read-only mono, generous height */}
        <textarea
          readOnly
          value={prompt}
          aria-label="Generated build prompt"
          className="
            input flex-1 min-h-0 !resize-none font-mono !text-[13px] leading-relaxed
            whitespace-pre-wrap
          "
          onFocus={(e) => e.currentTarget.select()}
        />

        <p className="text-[11px] text-text-muted mt-3 shrink-0">
          Paste this into Bob or any coding agent to rebuild.
        </p>
      </div>
    </div>
  );
}
