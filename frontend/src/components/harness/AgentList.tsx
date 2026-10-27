import { ExternalLink, Check } from "lucide-react";
import type { HarnessAgent } from "../../api/client";

interface Props {
  agents: HarnessAgent[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export default function AgentList({ agents, selectedId, onSelect }: Props) {
  return (
    <div
      role="tablist"
      aria-label="Supported AI Agents"
      className="flex flex-col gap-1.5"
      data-testid="harness-agent-list"
    >
      {agents.map((agent) => {
        const isSelected = agent.id === selectedId;
        return (
          <div
            key={agent.id}
            role="tab"
            tabIndex={0}
            data-testid={`harness-agent-${agent.id}`}
            aria-selected={isSelected}
            aria-controls="harness-preview-panel"
            onClick={() => onSelect(agent.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(agent.id);
              }
            }}
            className={`
              p-2.5 rounded-xl border text-left cursor-pointer transition-all duration-150 outline-none
              focus-visible:ring-2 focus-visible:ring-accent-cyan focus-visible:ring-offset-1
              flex flex-col gap-1.5
              ${
                isSelected
                  ? "border-accent-cyan bg-accent-cyan/10 shadow-sm ring-1 ring-accent-cyan/40"
                  : "border-border-subtle bg-bg-panel hover:bg-bg-panel-alt hover:border-border"
              }
            `}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-2 h-2 rounded-full shrink-0 ${isSelected ? "bg-accent-cyan" : "bg-text-muted/40"}`} />
                <span className="text-xs font-bold text-text-primary truncate">{agent.label}</span>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <a
                  href={agent.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  title={`Official documentation for ${agent.label}`}
                  aria-label={`Official documentation for ${agent.label}`}
                  className="p-1 rounded text-text-muted hover:text-accent-cyan hover:bg-bg-panel transition-colors"
                >
                  <ExternalLink size={12} />
                </a>
                {isSelected && <Check size={14} className="text-accent-cyan" />}
              </div>
            </div>

            <div className="flex items-center gap-1.5 flex-wrap">
              {agent.config_paths.map((p) => (
                <span
                  key={p}
                  className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-bg-panel-alt border border-border-subtle text-text-secondary"
                >
                  {p}
                </span>
              ))}
              <span className="text-[10px] text-text-muted font-mono ml-auto">
                {agent.transport.join(" / ")}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
