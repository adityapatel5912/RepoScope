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
      flex items-center gap-2 sm:gap-3 px-3 sm:px-4
      h-8
      bg-bg-panel border-t border-border-subtle shadow-sm
      text-[11px] text-text-muted
      whitespace-nowrap overflow-x-hidden min-w-0
    ">
      {/* Health indicator */}
      <span className="flex items-center gap-1.5 shrink-0">
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

      <span className="text-border-strong shrink-0">·</span>

      {/* Repo info */}
      {repo ? (
        <span className="flex items-center gap-1 min-w-0" title={`${repo}${repoInfo?.file_count != null ? ` · ${repoInfo.file_count} files` : ""}`}>
          <span className="w-1.5 h-1.5 rounded-full bg-gold-500 shrink-0" aria-hidden />
          <span className="text-text-muted hidden sm:inline">Repo:</span>
          <span className="font-mono text-text-primary truncate max-w-[120px] sm:max-w-[220px]">{repo}</span>
          {repoInfo?.file_count != null && (
            <span className="text-text-muted hidden md:inline">· {repoInfo.file_count} files</span>
          )}
        </span>
      ) : (
        <span className="text-border-strong text-2xs sm:text-[11px] shrink-0">No repo loaded</span>
      )}

      <span className="text-border-strong hidden sm:inline shrink-0">·</span>

      {/* Last event */}
      <span className="hidden sm:inline shrink-0">Last: <span className="text-text-primary">{lastEvent || "—"}</span></span>

      <span className="text-border-strong shrink-0">·</span>

      {/* Token count */}
      <span className="shrink-0" title={`Tokens: ${tokenCount}`}>Tokens: <span className="text-accent-cyan font-mono">{tokenCount}</span></span>

      {/* Right-aligned: last event timestamp */}
      <span className="ml-auto" />
      {eventTime && (
        <span className="text-border-strong hidden md:inline shrink-0">·</span>
      )}
      {eventTime && (
        <span className="hidden md:inline shrink-0">Last event: <span className="text-text-primary font-mono">{eventTime}</span></span>
      )}
    </div>
  );
}
