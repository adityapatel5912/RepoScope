/**
 * LocalFolderPanel.tsx
 * The EXPERIMENTAL in-browser path.
 *
 * Milestone 2.3, Correction C8: optional, clearly labelled, and built
 * last.
 *
 * The promise is the strongest privacy claim the product can make —
 * **no source code leaves the browser** — and it is worth having. But
 * the graph built here is SIMPLER than the server's: the same
 * Tree-sitter grammars, a lighter resolution pass, and no cross-file
 * symbol resolution. So the panel says so, right where the button is,
 * because a privacy feature that quietly produces a worse answer is a
 * trap.
 *
 * The button is hidden entirely where the File System Access API does
 * not exist — there is no point offering a Chromium-only feature to
 * someone in Firefox.
 */
import { useEffect, useState } from "react";
import { FolderOpen, Loader2, ShieldCheck, TriangleAlert } from "lucide-react";
import {
  buildGraphInBrowser,
  pickDirectory,
  supportsFileSystemAccess,
  type BrowserGraph,
} from "../api/localBrowser";
import { toast } from "./Toasts";

interface Props {
  /** Called with the graph the browser built. */
  onGraph?: (graph: BrowserGraph) => void;
}

export default function LocalFolderPanel({ onGraph }: Props) {
  const [supported, setSupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BrowserGraph | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSupported(supportsFileSystemAccess());
  }, []);

  if (!supported) return null;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const handle = await pickDirectory();
      if (!handle) {
        // Cancelling keeps the previous preview on screen. Clearing it
        // here made "Cancel" look like the folder had been forgotten.
        return;
      }
      // A real selection replaces the previous result; a failure below
      // must not leave the old counts looking like the new answer.
      setResult(null);
      const graph = await buildGraphInBrowser(handle);
      setResult(graph);
      onGraph?.(graph);
      toast.success(
        `Parsed ${graph.files} file(s) in the browser — nothing was uploaded.`,
      );
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      setError(message);
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="card-flat !border-border-hairline px-3 py-2.5"
      data-testid="local-folder-panel"
    >
      <div className="flex items-center justify-between mb-2">
        <p className="label-caps !text-[10px]">Open a local folder</p>
        <span
          className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border border-accent-amber/40 text-accent-amber"
          title="This path is experimental. The full graph needs the CLI."
        >
          Experimental
        </span>
      </div>

      <p className="text-[11px] text-text-muted leading-relaxed mb-2">
        Parsed <strong>in this browser</strong> with Tree-sitter compiled to
        WebAssembly. No file is uploaded, and the server is never told the
        folder's name.
      </p>

      <button
        onClick={() => void run()}
        disabled={busy}
        className="btn-secondary w-full !text-xs"
        data-testid="pick-local-folder"
      >
        {busy ? (
          <>
            <Loader2 size={12} className="animate-spin" /> Parsing…
          </>
        ) : (
          <>
            <FolderOpen size={12} /> Choose a folder
          </>
        )}
      </button>

      {error && (
        <p className="text-[11px] text-accent-rose leading-relaxed mt-2">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-2.5 pt-2 border-t border-border-hairline">
          <p className="text-[10px] font-mono text-text-secondary">
            {result.summary}
          </p>
          <p className="text-[10px] text-text-muted mt-0.5">
            {result.files} file(s) ·{" "}
            {result.languages.length
              ? result.languages.join(", ")
              : "no grammar loaded"}
          </p>
          <p className="text-[10px] text-text-muted leading-snug mt-1.5 flex items-start gap-1">
            <TriangleAlert size={10} className="shrink-0 mt-0.5 text-accent-amber" />
            <span>
              This graph is lighter than the server's: imports and symbols,
              but no cross-file symbol resolution, so the call graph is
              thinner. Chat, Track, and Student Mode are off while a preview is
              open. For the full picture use{" "}
              <code className="font-mono">reposcope run .</code>
            </span>
          </p>
          <p className="text-[10px] text-text-muted leading-snug mt-1 flex items-start gap-1">
            <ShieldCheck size={10} className="shrink-0 mt-0.5 text-accent-emerald" />
            <span>Nothing from that folder left your machine.</span>
          </p>
        </div>
      )}
    </div>
  );
}
