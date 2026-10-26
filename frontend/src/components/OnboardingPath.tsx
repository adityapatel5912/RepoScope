/**
 * OnboardingPath.tsx
 * Student Mode panel — a 3-level learning path ranked by the graph's
 * connectivity pyramid (Row 1 entry points → Rows 2-3 core → Rows 4-5
 * utils), with per-file "why it matters" notes, a 3-question quiz per
 * level, and Good First Issues mined from the low-traffic bottom rows.
 * Progress persists per-repo in localStorage.
 */
import { useEffect, useMemo, useState } from "react";
import { generateOnboarding, type Onboarding, type OnboardLevel } from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";
import {
  GraduationCap, RefreshCw, ChevronDown, CheckCircle2, Circle,
  HelpCircle, Wrench,
} from "lucide-react";

interface Props {
  /** owner/repo of the loaded repository. */
  repo: string | null;
}

const LEVEL_ACCENT: Record<number, string> = {
  1: "text-accent-cyan border-accent-cyan/30 bg-accent-cyan/10",
  2: "text-accent-amber border-accent-amber/30 bg-accent-amber/10",
  3: "text-accent-emerald border-accent-emerald/30 bg-accent-emerald/10",
};

function progressKey(repo: string) {
  return `reposcope-onboard-progress-${repo}`;
}

function loadProgress(repo: string): number[] {
  try {
    const raw = localStorage.getItem(progressKey(repo));
    return raw ? (JSON.parse(raw) as number[]) : [];
  } catch {
    return [];
  }
}

// ── Quiz block ───────────────────────────────────────────────────────────────
function Quiz({ quiz, onPassed }: { quiz: OnboardLevel["quiz"]; onPassed: () => void }) {
  const [picked, setPicked] = useState<Record<number, number>>({});
  useEffect(() => setPicked({}), [quiz]);

  const allCorrect = quiz.length > 0 && quiz.every((q, i) => picked[i] === q.answer_index);
  useEffect(() => {
    if (allCorrect) onPassed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allCorrect]);

  if (quiz.length === 0) {
    return <p className="text-2xs text-text-muted m-0">No quiz for this level.</p>;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {quiz.map((q, qi) => {
        const choice = picked[qi];
        const answered = choice != null;
        return (
          <div key={qi} className="rounded-lg border border-border-hairline bg-bg-panel-alt p-2.5">
            <p className="m-0 mb-1.5 text-xs font-semibold text-text-primary flex items-start gap-1.5">
              <HelpCircle size={12} className="text-accent-cyan shrink-0 mt-0.5" />
              {q.question}
            </p>
            <div className="flex flex-col gap-1">
              {q.options.map((opt, oi) => {
                const isPicked = choice === oi;
                const isAnswer = oi === q.answer_index;
                let cls = "border-border-subtle hover:bg-bg-panel-hover text-text-secondary";
                if (answered && isAnswer) cls = "border-accent-emerald/50 bg-accent-emerald/10 text-accent-emerald";
                else if (answered && isPicked && !isAnswer) cls = "border-accent-rose/50 bg-accent-rose/10 text-accent-rose";
                else if (answered) cls = "border-border-hairline text-text-muted opacity-60";
                return (
                  <button
                    key={oi}
                    disabled={answered}
                    onClick={() => setPicked((p) => ({ ...p, [qi]: oi }))}
                    className={`text-left text-2xs px-2 py-1.5 rounded-md border transition-all duration-150 ${cls}`}
                  >
                    <span className="font-mono mr-1.5">{String.fromCharCode(65 + oi)}.</span>
                    {opt}
                  </button>
                );
              })}
            </div>
            {answered && q.explanation && (
              <p className="m-0 mt-1.5 text-2xs text-text-muted leading-relaxed">
                {choice === q.answer_index ? "✓ " : "✗ "}{q.explanation}
              </p>
            )}
          </div>
        );
      })}
      {allCorrect && (
        <p className="m-0 text-2xs font-semibold text-accent-emerald">
          Perfect score — level complete! 🎓
        </p>
      )}
    </div>
  );
}

// ── Level accordion ──────────────────────────────────────────────────────────
function LevelCard({
  level, completed, onComplete,
}: { level: OnboardLevel; completed: boolean; onComplete: () => void }) {
  const [open, setOpen] = useState(level.level === 1);
  const accent = LEVEL_ACCENT[level.level] ?? LEVEL_ACCENT[1];

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-bg-panel-alt transition-colors text-left"
      >
        <span className={`text-2xs font-bold px-2 py-0.5 rounded border ${accent}`}>
          L{level.level}
        </span>
        <span className="text-xs font-semibold text-text-primary flex-1 min-w-0 truncate">
          {level.title}
        </span>
        {completed && <CheckCircle2 size={13} className="text-accent-emerald shrink-0" />}
        <ChevronDown size={13} className={`text-text-muted shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="px-3 pb-3 pt-0.5 flex flex-col gap-2.5 border-t border-border-hairline">
          <p className="m-0 mt-2 text-2xs text-text-muted leading-relaxed">{level.description}</p>

          <div className="flex flex-col gap-1.5">
            {level.files.map((f) => (
              <div key={f.path} className="rounded-lg bg-bg-panel-alt border border-border-hairline px-2.5 py-1.5">
                <div className="font-mono text-[11px] text-accent-cyan break-all">{f.path}</div>
                <p className="m-0 mt-0.5 text-2xs text-text-muted leading-relaxed">{f.why}</p>
              </div>
            ))}
          </div>

          {level.quiz.length > 0 && (
            <div>
              <p className="label-caps !text-[10px] mb-1.5">Checkpoint quiz</p>
              <Quiz quiz={level.quiz} onPassed={onComplete} />
            </div>
          )}

          {!completed && level.quiz.length === 0 && (
            <button onClick={onComplete} className="btn-secondary !py-1.5 !text-2xs self-start">
              <Circle size={11} />
              Mark level complete
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────
export default function OnboardingPath({ repo }: Props) {
  const [data, setData]       = useState<Onboarding | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [completed, setCompleted] = useState<number[]>([]);

  const generate = async () => {
    if (loading || !repo) return;
    setLoading(true);
    setError(null);
    try {
      const d = await generateOnboarding();
      setData(d);
      setCompleted(loadProgress(repo));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Onboarding failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  // Auto-generate when a repo is loaded
  useEffect(() => {
    setData(null);
    setError(null);
    setCompleted([]);
    if (repo) void generate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo]);

  const markComplete = (level: number) => {
    if (!repo) return;
    setCompleted((prev) => {
      if (prev.includes(level)) return prev;
      const next = [...prev, level];
      try {
        localStorage.setItem(progressKey(repo), JSON.stringify(next));
      } catch { /* storage unavailable */ }
      return next;
    });
  };

  const pct = useMemo(
    () => (data && data.levels.length > 0
      ? Math.round((completed.filter((l) => data.levels.some((lv) => lv.level === l)).length / data.levels.length) * 100)
      : 0),
    [completed, data],
  );

  if (!repo) return null;

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-1.5">
        <GraduationCap size={12} className="text-accent-cyan" />
        <h3 className="label-caps">Student Path</h3>
        <button
          onClick={() => void generate()}
          disabled={loading}
          title="Regenerate learning path"
          aria-label="Regenerate learning path"
          className="ml-auto w-6 h-6 flex items-center justify-center rounded-md
            text-text-muted hover:text-text-primary hover:bg-bg-panel-hover transition-all"
        >
          <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-2xs text-text-muted mb-1">
          <span>Progress</span>
          <span className="font-mono">{pct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-bg-panel-alt border border-border-hairline overflow-hidden">
          <div
            className="h-full bg-accent-emerald transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 rounded-lg text-xs bg-accent-rose/10 border border-accent-rose/25 text-accent-rose">
          {error}
        </div>
      )}

      {loading && !data && (
        <>
          <SkeletonCard lines={2} />
          <SkeletonCard lines={3} />
        </>
      )}

      {data && (
        <>
          <div className="flex flex-col gap-2">
            {data.levels.map((lv) => (
              <LevelCard
                key={lv.level}
                level={lv}
                completed={completed.includes(lv.level)}
                onComplete={() => markComplete(lv.level)}
              />
            ))}
          </div>

          {data.good_first_issues.length > 0 && (
            <div className="pt-2 border-t border-border-subtle">
              <p className="label-caps !text-[10px] mb-1.5 flex items-center gap-1.5">
                <Wrench size={10} className="text-accent-emerald" />
                Good First Issues
              </p>
              <div className="flex flex-col gap-2">
                {data.good_first_issues.map((gfi, i) => (
                  <div key={i} className="rounded-lg bg-accent-emerald/5 border border-accent-emerald/20 px-2.5 py-2">
                    <div className="text-xs font-semibold text-text-primary leading-snug">{gfi.title}</div>
                    <div className="font-mono text-2xs text-accent-cyan mt-0.5 break-all">{gfi.file}</div>
                    <p className="m-0 mt-1 text-2xs text-text-muted leading-relaxed">{gfi.description}</p>
                    {gfi.hint && (
                      <p className="m-0 mt-1 text-2xs text-text-muted leading-relaxed">
                        <span className="font-semibold text-accent-emerald">Start:</span> {gfi.hint}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
