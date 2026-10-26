import { CheckCircle2, Circle, Loader2 } from "lucide-react";

interface Step {
  label: string;
  done: boolean;
  active: boolean;
}

interface Props {
  steps: Step[];
}

export default function LoadingStepper({ steps }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2">
      {steps.map((s, i) => (
        <div
          key={i}
          className="flex items-center gap-2.5"
        >
          <span className="flex-shrink-0">
            {s.done ? (
              <CheckCircle2 size={14} className="text-accent-emerald" />
            ) : s.active ? (
              <Loader2 size={14} className="text-accent-cyan animate-spin" />
            ) : (
              <Circle size={14} className="text-border-strong" />
            )}
          </span>
          <span
            className={
              s.done
                ? "text-xs text-text-primary"
                : s.active
                ? "text-xs text-accent-cyan font-medium"
                : "text-xs text-text-muted"
            }
          >
            {s.label}
          </span>
        </div>
      ))}
    </div>
  );
}
