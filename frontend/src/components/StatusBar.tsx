import { useEffect, useState } from "react";
import { getHealth } from "../api/client";

interface Props {
  repo: string | null;
  repoInfo: { file_count?: number; loaded_at?: string } | null;
  lastEvent: string;
  tokenCount: number;
}

export default function StatusBar({ repo, repoInfo, lastEvent, tokenCount }: Props) {
  const [health, setHealth] = useState<"ok" | "down" | "checking">("checking");

  useEffect(() => {
    const check = async () => {
      try {
        await getHealth();
        setHealth("ok");
      } catch {
        setHealth("down");
      }
    };
    check();
    const id = setInterval(check, 10_000);
    return () => clearInterval(id);
  }, []);

  // Timestamp of the last SSE event ("done at HH:MM:SS")
  const [eventTime, setEventTime] = useState<string | null>(null);
  useEffect(() => {
    if (lastEvent) setEventTime(new Date().toLocaleTimeString());
  }, [lastEvent]);

  return (
    <div className="
      shrink-0 z-40
      flex items-center gap-3 px-4
      h-8
      bg-bg-panel border-t border-border-subtle shadow-sm
      text-[11px] text-text-muted
    ">
      {/* Health indicator */}
      <span className="flex items-center gap-1.5">
        <span className={`
          w-1.5 h-1.5 rounded-full shrink-0
          ${health === "ok"       ? "bg-accent-emerald pulse-dot" :
            health === "down"     ? "bg-accent-rose" :
                                    "bg-accent-amber pulse-dot"}
        `} />
        <span>
          Backend:{" "}
          <span className={
            health === "ok"   ? "text-accent-emerald" :
            health === "down" ? "text-accent-rose" :
                                "text-accent-amber"
          }>
            {health === "checking" ? "…" : health}
          </span>
        </span>
      </span>

      <span className="text-border-strong">·</span>

      {/* Repo info */}
      {repo ? (
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-gold-500 shrink-0" aria-hidden />
          <span className="text-text-muted">Repo:</span>
          <span className="font-mono text-text-primary">{repo}</span>
          {repoInfo?.file_count != null && (
            <span className="text-text-muted">· {repoInfo.file_count} files</span>
          )}
        </span>
      ) : (
        <span className="text-border-strong">No repo loaded</span>
      )}

      <span className="text-border-strong">·</span>

      {/* Last event */}
      <span>Last: <span className="text-text-primary">{lastEvent || "—"}</span></span>

      <span className="text-border-strong">·</span>

      {/* Token count */}
      <span>Tokens: <span className="text-accent-cyan font-mono">{tokenCount}</span></span>

      {/* Right-aligned: last event timestamp */}
      <span className="ml-auto" />
      {eventTime && (
        <span className="text-border-strong">·</span>
      )}
      {eventTime && (
        <span>Last event: <span className="text-text-primary font-mono">{eventTime}</span></span>
      )}
    </div>
  );
}
