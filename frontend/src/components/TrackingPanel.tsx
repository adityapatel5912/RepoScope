import { Radio } from "lucide-react";

interface Commit {
  sha: string;
  _type: string;
  commit?: { message?: string };
}

interface PR {
  id: number;
  number: number;
  title: string;
  state: string;
}

interface TrackingData {
  new_commits?: Commit[];
  pulls?: PR[];
  issues?: unknown[];
  releases?: unknown[];
}

interface Props {
  data: TrackingData | null;
}

const TYPE_COLOR: Record<string, string> = {
  breaking: "text-accent-rose  bg-accent-rose/10  border-accent-rose/20",
  feat:     "text-accent-emerald bg-accent-emerald/10 border-accent-emerald/20",
  fix:      "text-accent-amber  bg-accent-amber/10  border-accent-amber/20",
  chore:    "text-text-muted    bg-bg-panel-alt           border-border-strong",
  docs:     "text-accent-cyan   bg-accent-cyan/10    border-accent-cyan/20",
  refactor: "text-accent-violet bg-accent-violet/10  border-accent-violet/20",
  deps:     "text-orange-400    bg-orange-400/10     border-orange-400/20",
  other:    "text-text-muted    bg-bg-panel-alt           border-border-strong",
};

const PR_STATE: Record<string, string> = {
  open:   "text-accent-emerald bg-accent-emerald/10 border-accent-emerald/20",
  closed: "text-accent-rose    bg-accent-rose/10    border-accent-rose/20",
  merged: "text-accent-violet  bg-accent-violet/10  border-accent-violet/20",
};

export default function TrackingPanel({ data }: Props) {
  if (!data) return null;

  const commits = data.new_commits ?? [];

  return (
    <div className="px-4 py-4 border-b border-border-subtle">
      <div className="flex items-center gap-2 mb-3">
        <Radio size={12} className="text-accent-cyan" />
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">
          Tracking Results
        </h3>
      </div>

      {commits.length === 0 ? (
        <p className="text-xs text-text-muted">No new commits since last check.</p>
      ) : (
        <>
          <p className="text-[10px] uppercase tracking-wider text-text-muted mb-2">
            Commits ({commits.length})
          </p>
          <ul className="flex flex-col gap-1.5">
            {commits.map((c) => {
              const typeClass = TYPE_COLOR[c._type] ?? TYPE_COLOR.other;
              return (
                <li key={c.sha} className="flex items-start gap-2 min-w-0">
                  <code className="
                    shrink-0 font-mono text-[10px] text-text-muted
                    bg-bg-panel-alt border border-border-subtle
                    px-1.5 py-0.5 rounded
                  ">
                    {c.sha.slice(0, 7)}
                  </code>
                  <span className={`
                    shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5
                    rounded border ${typeClass}
                  `}>
                    {c._type}
                  </span>
                  <span
                    className="text-xs text-text-muted leading-tight truncate min-w-0 flex-1"
                    title={c.commit?.message?.split("\n")[0]}
                  >
                    {c.commit?.message?.split("\n")[0]}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {(data.pulls?.length ?? 0) > 0 && (
        <div className="mt-3">
          <p className="text-[10px] uppercase tracking-wider text-text-muted mb-2">
            Pull Requests
          </p>
          <ul className="flex flex-col gap-1.5">
            {data.pulls!.slice(0, 5).map((p) => {
              const stateClass = PR_STATE[p.state] ?? PR_STATE.closed;
              return (
                <li key={p.id} className="flex items-center gap-2 min-w-0">
                  <span className="text-xs font-mono text-text-muted shrink-0">
                    #{p.number}
                  </span>
                  <span
                    className="text-xs text-text-primary truncate min-w-0 flex-1"
                    title={p.title}
                  >
                    {p.title}
                  </span>
                  <span className={`
                    shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5
                    rounded border ${stateClass}
                  `}>
                    {p.state}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
