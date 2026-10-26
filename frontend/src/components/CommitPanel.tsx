import { useState } from "react";
import { commit } from "../api/client";
import { toast } from "./Toasts";
import { GitCommit, Lock } from "lucide-react";

interface Props {
  /** Disabled until a BYOK PAT is saved for this session. */
  disabled?: boolean;
}

export default function CommitPanel({ disabled }: Props) {
  const [msg, setMsg]       = useState("");
  const [busy, setBusy]     = useState(false);
  const [status, setStatus] = useState("");

  const doCommit = async () => {
    if (!msg.trim() || disabled) return;
    setBusy(true);
    setStatus("");
    try {
      const d = await commit(msg.trim()) as { ok?: boolean; detail?: string };
      if (d.ok) {
        setStatus("✓ Commit simulated");
        setMsg("");
        toast.success("Commit simulated (BYOK active)");
      } else {
        setStatus(`✗ ${d.detail ?? "Failed"}`);
        toast.error(d.detail ?? "Commit failed");
      }
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : "Network error — is the backend running?";
      setStatus(`✗ ${m}`);
      toast.error(m);
    }
    setBusy(false);
  };

  return (
    <section className="card p-4 flex flex-col gap-3 overflow-hidden min-w-0">
      <div className="flex items-center gap-1.5 min-w-0">
        <GitCommit size={12} className="text-text-muted" />
        <h3 className="label-caps truncate">Commit</h3>
      </div>

      {disabled ? (
        <p className="text-[11px] text-text-muted flex items-start gap-1.5 leading-relaxed">
          <Lock size={12} className="shrink-0 mt-0.5" />
          Save a GitHub PAT above to enable commits.
        </p>
      ) : (
        <>
          <textarea
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && !busy && void doCommit()}
            placeholder="Commit message…"
            rows={2}
            aria-label="Commit message"
            className="input !text-xs"
          />
          <div className="flex items-center justify-between gap-2">
            <span className={`text-[11px] ${status.startsWith("✓") ? "text-accent-emerald" : "text-accent-rose"}`}>
              {status}
            </span>
            <button
              onClick={() => void doCommit()}
              disabled={busy || !msg.trim()}
              className="btn-primary !py-1.5 !px-3 !text-xs shrink-0"
            >
              {busy ? <span className="btn-spinner" /> : <GitCommit size={12} />}
              Commit
            </button>
          </div>
        </>
      )}
    </section>
  );
}
