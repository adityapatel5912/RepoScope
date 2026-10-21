/**
 * EditorSettings.tsx
 * Where the map meets the editor.
 *
 * Milestone 2.1. Three settings, and every one of them exists because
 * without it the feature is broken for somebody:
 *
 *   **The editor.** Everyone uses a different one. The URI schemes are
 *   different, and opening the wrong one does nothing at all.
 *
 *   **The workspace root.** In web mode RepoScope runs on a server that
 *   has never seen the user's checkout, so a repo-relative path means
 *   nothing on the user's machine. The root is what turns
 *   `backend/auth.py` into `/home/me/project/backend/auth.py`. Without
 *   it, RepoScope cannot open anything — so instead of failing, it
 *   copies the path and says why.
 *
 *   **"Always ask".** Some people want a click to open the editor.
 *   Some people want a click to show them what they clicked. The toggle
 *   is the difference between those two.
 */
import { useEffect, useState } from "react";
import { Check, FolderOpen, Settings2, X } from "lucide-react";
import {
  EDITORS,
  loadIdePrefs,
  saveIdePrefs,
  type EditorId,
  type IdePrefs,
} from "../utils/ideLinks";

interface Props {
  onClose: () => void;
  /** Called when the preferences change, so the app can re-render. */
  onChange?: (prefs: IdePrefs) => void;
}

export default function EditorSettings({ onClose, onChange }: Props) {
  const [prefs, setPrefs] = useState<IdePrefs>(() => loadIdePrefs());
  const [rootDraft, setRootDraft] = useState(prefs.workspaceRoot);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const commit = (next: IdePrefs) => {
    setPrefs(next);
    saveIdePrefs(next);
    onChange?.(next);
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Editor settings"
    >
      <div
        className="
          w-[440px] max-w-[92vw] max-h-[85vh] overflow-y-auto
          rounded-2xl border border-border-strong shadow-2xl
          bg-bg-panel
        "
        onClick={(e) => e.stopPropagation()}
        data-testid="editor-settings"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Settings2 size={15} className="text-accent-cyan" />
            Editor settings
          </h2>
          <button
            onClick={onClose}
            aria-label="Close editor settings"
            className="w-7 h-7 flex items-center justify-center rounded-lg
              text-text-muted hover:text-text-primary hover:bg-bg-panel-hover
              transition-all duration-150"
          >
            <X size={14} />
          </button>
        </div>

        <div className="px-5 py-4 flex flex-col gap-5">
          {/* Editor */}
          <section>
            <p className="label-caps !text-[10px] mb-2">Preferred editor</p>
            <div className="flex flex-col gap-1.5">
              {EDITORS.map((editor) => (
                <button
                  key={editor.id}
                  onClick={() => commit({ ...prefs, editor: editor.id as EditorId })}
                  aria-pressed={prefs.editor === editor.id}
                  className={`
                    flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-left
                    border transition-colors duration-150
                    ${
                      prefs.editor === editor.id
                        ? "border-accent-cyan bg-accent-cyan/10"
                        : "border-border-subtle hover:bg-bg-panel-alt"
                    }
                  `}
                >
                  <span className="min-w-0">
                    <span className="block text-xs font-semibold text-text-primary">
                      {editor.name}
                    </span>
                    <span className="block text-[10px] text-text-muted font-mono truncate">
                      {editor.scheme}://
                    </span>
                  </span>
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] text-text-muted hidden sm:inline">
                      {editor.hint}
                    </span>
                    {prefs.editor === editor.id && (
                      <Check size={13} className="text-accent-cyan" />
                    )}
                  </span>
                </button>
              ))}
            </div>
          </section>

          {/* Workspace root */}
          <section>
            <p className="label-caps !text-[10px] mb-1.5">Workspace root</p>
            <p className="text-[11px] text-text-muted leading-relaxed mb-2">
              The absolute path of this checkout on your machine. RepoScope
              runs on a server that has never seen your files, so without
              this it cannot open anything — it will copy the path instead.
            </p>
            <div className="flex gap-2 items-center">
              <input
                value={rootDraft}
                onChange={(e) => setRootDraft(e.target.value)}
                onBlur={() => commit({ ...prefs, workspaceRoot: rootDraft.trim() })}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    commit({ ...prefs, workspaceRoot: rootDraft.trim() });
                  }
                }}
                placeholder="C:\\Users\\you\\projects\\my-repo"
                aria-label="Workspace root path"
                className="input flex-1 !py-1.5 font-mono !text-xs"
              />
              <button
                onClick={() => commit({ ...prefs, workspaceRoot: rootDraft.trim() })}
                className="btn-secondary !py-1.5 !px-3 !text-xs shrink-0"
                title="Save the workspace root"
              >
                <FolderOpen size={12} /> Save
              </button>
            </div>
          </section>

          {/* Always ask */}
          <section className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="label-caps !text-[10px] mb-1">Always ask first</p>
              <p className="text-[11px] text-text-muted leading-relaxed">
                Off: a click opens the editor. On: a click asks first.
              </p>
            </div>
            <button
              role="switch"
              aria-checked={prefs.alwaysAsk}
              aria-label="Always ask before opening the editor"
              onClick={() => commit({ ...prefs, alwaysAsk: !prefs.alwaysAsk })}
              className={`
                relative w-9 h-5 shrink-0 rounded-full transition-colors duration-150
                ${prefs.alwaysAsk ? "bg-accent-cyan" : "bg-border-strong"}
              `}
            >
              <span
                className={`
                  absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all duration-150
                  ${prefs.alwaysAsk ? "left-4.5" : "left-0.5"}
                `}
              />
            </button>
          </section>
        </div>
      </div>
    </div>
  );
}
