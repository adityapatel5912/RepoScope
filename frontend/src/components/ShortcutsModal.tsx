/**
 * ShortcutsModal.tsx
 * Keyboard-shortcuts cheat sheet, opened via the "?" key or header button.
 */
import { Keyboard, X } from "lucide-react";

interface Props {
  onClose: () => void;
}

const SHORTCUTS: { keys: string[]; desc: string }[] = [
  { keys: ["Ctrl", "K"],        desc: "Focus repository URL input" },
  { keys: ["Ctrl", "1"],        desc: "Understand mode" },
  { keys: ["Ctrl", "2"],        desc: "Track mode" },
  { keys: ["Ctrl", "3"],        desc: "Incident mode" },
  { keys: ["Ctrl", "B"],        desc: "Toggle left panel" },
  { keys: ["Ctrl", "J"],        desc: "Toggle chat panel" },
  { keys: ["Ctrl", "\\"],        desc: "Collapse / restore both panels" },
  { keys: ["Enter"],            desc: "Send chat message" },
  { keys: ["Shift", "Enter"],   desc: "New line in chat" },
  { keys: ["Escape"],           desc: "Clear highlights / close dialogs" },
  { keys: ["?"],                desc: "Show this cheat sheet" },
];

export default function ShortcutsModal({ onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div
        className="
          w-[380px] max-w-[90vw] max-h-[80vh] overflow-y-auto
          rounded-2xl border border-border-strong shadow-2xl shadow-black/10
          bg-bg-panel shadow-2xl
        "
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Keyboard size={15} className="text-accent-cyan" />
            Keyboard Shortcuts
          </h2>
          <button
            onClick={onClose}
            aria-label="Close shortcuts"
            className="w-7 h-7 flex items-center justify-center rounded-lg
              text-text-muted hover:text-text-primary hover:bg-bg-panel-hover
              transition-all duration-150"
          >
            <X size={14} />
          </button>
        </div>

        {/* Rows */}
        <div className="px-5 py-3">
          {SHORTCUTS.map(({ keys, desc }) => (
            <div
              key={desc}
              className="flex items-center justify-between py-2.5 border-b border-border-subtle last:border-0"
            >
              <span className="text-xs text-text-muted">{desc}</span>
              <span className="flex items-center gap-1">
                {keys.map((k) => (
                  <kbd
                    key={k}
                    className="
                      px-1.5 py-0.5 rounded-md text-2xs font-mono font-semibold
                      bg-bg-panel-hover border border-border-strong text-text-primary
                      shadow-sm
                    "
                  >
                    {k}
                  </kbd>
                ))}
              </span>
            </div>
          ))}
        </div>

        <div className="px-5 py-3 border-t border-border-subtle">
          <p className="text-2xs text-text-muted text-center">
            On macOS use ⌘ instead of Ctrl
          </p>
        </div>
      </div>
    </div>
  );
}
