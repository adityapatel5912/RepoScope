import { Network } from "lucide-react";

interface Props {
  onTryDemo?: () => void;
}

export default function EmptyState({ onTryDemo }: Props) {
  return (
    <div className="
      w-full h-full flex flex-col items-center justify-center
      px-8 text-center gap-5
    ">
      {/* Ghost icon */}
      <div className="relative">
        <div className="
          w-20 h-20 rounded-2xl
          flex items-center justify-center
          bg-bg-panel-alt border border-border-subtle
        ">
          <Network size={36} className="text-border-strong" />
        </div>
      </div>

      <div className="flex flex-col gap-2 max-w-xs">
        <h2 className="text-base font-semibold text-text-primary">
          No graph loaded
        </h2>
        <p className="text-sm text-text-muted leading-relaxed">
          Paste a GitHub repository URL in the top bar to visualize its code graph.
        </p>
      </div>

      <div className="
        text-left w-full max-w-xs
        bg-bg-panel-alt border border-border-subtle
        rounded-xl px-4 py-3
        flex flex-col gap-2
      ">
        {[
          "Ask questions in natural language",
          "Graph shows imports, calls & structure",
          "Switch to Track mode for recent changes",
          "Use BYOK for private repositories",
        ].map((tip) => (
          <div key={tip} className="flex items-start gap-2 text-xs text-text-muted">
            <span className="text-accent-cyan shrink-0 mt-0.5">→</span>
            {tip}
          </div>
        ))}
      </div>

      {onTryDemo && (
        <button
          onClick={onTryDemo}
          className="
            flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
            bg-accent-cyan/10 border border-accent-cyan/25 text-accent-cyan
            hover:bg-accent-cyan/20 transition-all duration-200
          "
        >
          Try demo repo
        </button>
      )}
    </div>
  );
}
