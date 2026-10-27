import { useMemo } from "react";

interface Props {
  diff: string;
}

export default function DiffViewer({ diff }: Props) {
  const lines = useMemo(() => {
    return diff.split("\n").map((line, index) => {
      let type: "header" | "add" | "del" | "ctx" = "ctx";
      if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("@@")) {
        type = "header";
      } else if (line.startsWith("+")) {
        type = "add";
      } else if (line.startsWith("-")) {
        type = "del";
      }
      return { index, line, type };
    });
  }, [diff]);

  return (
    <div className="rounded-lg border border-border-subtle bg-bg-panel-alt overflow-hidden">
      <div className="px-3 py-2 bg-amber-500/10 border-b border-amber-500/20 text-xs font-semibold text-amber-800 flex items-center justify-between">
        <span>Unified Diff — Existing file will be modified</span>
        <span className="text-2xs font-mono text-amber-700/80">Review before writing</span>
      </div>
      <pre
        className="p-3 text-xs font-mono overflow-x-auto leading-relaxed max-h-72"
        data-testid="harness-diff"
      >
        {lines.map(({ index, line, type }) => (
          <div
            key={index}
            className={`px-1 rounded-sm ${
              type === "add"
                ? "bg-emerald-500/15 text-emerald-800 font-semibold"
                : type === "del"
                ? "bg-rose-500/15 text-rose-800 line-through opacity-85"
                : type === "header"
                ? "text-accent-cyan font-bold"
                : "text-text-secondary"
            }`}
          >
            {line || " "}
          </div>
        ))}
      </pre>
    </div>
  );
}
