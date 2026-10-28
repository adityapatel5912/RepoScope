/**
 * OnboardingPath.tsx
 * Student Mode panel — Topological Curriculum (V2.7) derived from Tarjan SCC
 * condensation and DAG ordering, with graph-graded challenges and progress tracking,
 * plus backward-compatible classic 3-level pyramid and Good First Issues.
 */
import { useEffect, useState } from "react";
import {
  generateOnboarding,
  getOnboardCurriculum,
  verifyChallenge,
  type Onboarding,
  type OnboardLevel,
  type OnboardCurriculum,
  type OnboardTier,
} from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";
import {
  GraduationCap,
  RefreshCw,
  ChevronDown,
  CheckCircle2,
  Circle,
  HelpCircle,
  Wrench,
  Lock,
  Unlock,
  Layers,
  Sparkles,
} from "lucide-react";

interface Props {
  /** owner/repo of the loaded repository. */
  repo: string | null;
}

const TIER_ACCENT: Record<number, string> = {
  1: "text-accent-cyan border-accent-cyan/30 bg-accent-cyan/10",
  2: "text-accent-amber border-accent-amber/30 bg-accent-amber/10",
  3: "text-accent-emerald border-accent-emerald/30 bg-accent-emerald/10",
  4: "text-accent-purple border-accent-purple/30 bg-accent-purple/10",
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

// ── Tier Challenge Solver ───────────────────────────────────────────────────
function TierChallengeCard({
  tier,
  challenge,
  onSolved,
}: {
  tier: number;
  challenge: OnboardTier["challenges"][0];
  onSolved: () => void;
}) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ correct: boolean; message: string } | null>(null);

  const handleVerify = async () => {
    if (selectedIdx === null || submitting) return;
    setSubmitting(true);
    try {
      const res = await verifyChallenge(tier, challenge.id, String(selectedIdx));
      setFeedback({ correct: res.correct, message: res.feedback });
      if (res.correct) {
        toast.success(`Tier ${tier} challenge passed!`);
        onSolved();
      } else {
        toast.error("Incorrect. Try again!");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Verification failed";
      setFeedback({ correct: false, message: msg });
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-lg border border-border-hairline bg-bg-panel-alt p-3 min-w-0 flex flex-col gap-2">
      <div className="flex items-start gap-1.5 min-w-0">
        <HelpCircle size={13} className="text-accent-cyan shrink-0 mt-0.5" />
        <span className="text-xs font-semibold text-text-primary break-words leading-snug">
          {challenge.prompt}
        </span>
      </div>

      <div className="flex flex-col gap-1.5 mt-1">
        {challenge.options.map((opt, oi) => {
          const isSelected = selectedIdx === oi;
          let btnCls = "border-border-subtle hover:bg-bg-panel-hover text-text-secondary";
          if (isSelected) {
            btnCls = "border-accent-cyan bg-accent-cyan/15 text-accent-cyan font-semibold";
          }
          return (
            <button
              key={oi}
              disabled={submitting}
              onClick={() => {
                setSelectedIdx(oi);
                setFeedback(null);
              }}
              className={`text-left text-2xs px-2.5 py-1.5 rounded-md border transition-all duration-150 break-words ${btnCls}`}
            >
              <span className="font-mono mr-1.5 opacity-80">{String.fromCharCode(65 + oi)}.</span>
              {opt}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2 mt-1">
        <button
          onClick={handleVerify}
          disabled={selectedIdx === null || submitting}
          className="btn-primary !py-1 !px-3 !text-2xs font-semibold"
        >
          {submitting ? "Verifying..." : "Verify with AST Graph"}
        </button>
      </div>

      {feedback && (
        <div
          className={`p-2 rounded text-2xs leading-relaxed border mt-1 ${
            feedback.correct
              ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald"
              : "bg-accent-rose/10 border-accent-rose/30 text-accent-rose"
          }`}
        >
          <span className="font-bold mr-1">{feedback.correct ? "✓ Correct:" : "✗ Hint:"}</span>
          {feedback.message}
        </div>
      )}
    </div>
  );
}

// ── Tier Card ───────────────────────────────────────────────────────────────
function TierCard({
  tier,
  unlocked,
  completed,
  onComplete,
}: {
  tier: OnboardTier;
  unlocked: boolean;
  completed: boolean;
  onComplete: () => void;
}) {
  const [open, setOpen] = useState(unlocked && (tier.tier === 1 || !completed));
  const accent = TIER_ACCENT[tier.tier] ?? TIER_ACCENT[1];

  return (
    <div
      className={`rounded-xl border overflow-hidden transition-all duration-200 ${
        unlocked
          ? "border-border-subtle bg-bg-panel"
          : "border-border-hairline bg-bg-panel/40 opacity-75"
      }`}
    >
      <button
        onClick={() => unlocked && setOpen((v) => !v)}
        disabled={!unlocked}
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-bg-panel-alt transition-colors text-left"
      >
        <span className={`text-2xs font-bold px-2 py-0.5 rounded border ${accent}`}>
          {tier.badge || `L${tier.tier}`}
        </span>
        <span className="text-xs font-semibold text-text-primary flex-1 min-w-0 truncate">
          {tier.name}
        </span>
        {completed ? (
          <CheckCircle2 size={13} className="text-accent-emerald shrink-0" />
        ) : unlocked ? (
          <Unlock size={12} className="text-accent-cyan shrink-0" />
        ) : (
          <Lock size={12} className="text-text-muted shrink-0" />
        )}
        {unlocked && (
          <ChevronDown
            size={13}
            className={`text-text-muted shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
          />
        )}
      </button>

      {open && unlocked && (
        <div className="px-3 pb-3 pt-0.5 flex flex-col gap-2.5 border-t border-border-hairline">
          <p className="m-0 mt-2 text-2xs text-text-muted leading-relaxed">{tier.description}</p>

          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
              Curated Modules ({tier.files.length})
            </span>
            {tier.files.map((f) => (
              <div
                key={f.path}
                className="rounded-lg bg-bg-panel-alt border border-border-hairline px-2.5 py-1.5 min-w-0"
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="font-mono text-[11px] text-accent-cyan break-all" title={f.path}>
                    {f.path}
                  </span>
                  {f.in_degree !== undefined && (
                    <span className="text-[10px] text-text-muted shrink-0">
                      in: {f.in_degree} / out: {f.out_degree}
                    </span>
                  )}
                </div>
                {f.why && (
                  <p className="m-0 mt-0.5 text-2xs text-text-muted leading-relaxed break-words">
                    {f.why}
                  </p>
                )}
              </div>
            ))}
          </div>

          {tier.challenges && tier.challenges.length > 0 && (
            <div className="flex flex-col gap-2 mt-1">
              <span className="text-[10px] font-mono uppercase tracking-wider text-accent-cyan flex items-center gap-1">
                <Sparkles size={11} /> Graph-Graded Checkpoint
              </span>
              {tier.challenges.map((ch) => (
                <TierChallengeCard key={ch.id} tier={tier.tier} challenge={ch} onSolved={onComplete} />
              ))}
            </div>
          )}

          {!completed && (!tier.challenges || tier.challenges.length === 0) && (
            <button onClick={onComplete} className="btn-secondary !py-1.5 !text-2xs self-start">
              <Circle size={11} /> Mark Tier Complete
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Classic Quiz block ──────────────────────────────────────────────────────
function Quiz({ quiz, onPassed }: { quiz: OnboardLevel["quiz"]; onPassed: () => void }) {
  const [picked, setPicked] = useState<Record<number, number>>({});
  useEffect(() => setPicked({}), [quiz]);

  const allCorrect = quiz.length > 0 && quiz.every((q, i) => picked[i] === q.answer_index);
  useEffect(() => {
    if (allCorrect) onPassed();
  }, [allCorrect, onPassed]);

  if (quiz.length === 0) {
    return <p className="text-2xs text-text-muted m-0">No quiz for this level.</p>;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {quiz.map((q, qi) => {
        const choice = picked[qi];
        const answered = choice != null;
        return (
          <div key={qi} className="rounded-lg border border-border-hairline bg-bg-panel-alt p-2.5 min-w-0">
            <p className="m-0 mb-1.5 text-xs font-semibold text-text-primary flex items-start gap-1.5 min-w-0">
              <HelpCircle size={12} className="text-accent-cyan shrink-0 mt-0.5" />
              <span className="min-w-0 break-words">{q.question}</span>
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
                    className={`text-left text-2xs px-2 py-1.5 rounded-md border transition-all duration-150 break-words ${cls}`}
                  >
                    <span className="font-mono mr-1.5">{String.fromCharCode(65 + oi)}.</span>
                    {opt}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Panel ──────────────────────────────────────────────────────────────
export default function OnboardingPath({ repo }: Props) {
  const [mode, setMode] = useState<"curriculum" | "classic">("curriculum");
  const [curriculum, setCurriculum] = useState<OnboardCurriculum | null>(null);
  const [data, setData] = useState<Onboarding | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completedTiers, setCompletedTiers] = useState<number[]>([]);

  const loadData = async () => {
    if (loading || !repo) return;
    setLoading(true);
    setError(null);
    try {
      const [curr, onboard] = await Promise.all([
        getOnboardCurriculum().catch(() => null),
        generateOnboarding().catch(() => null),
      ]);
      if (curr) setCurriculum(curr);
      if (onboard) setData(onboard);
      setCompletedTiers(loadProgress(repo));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load onboarding";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setCurriculum(null);
    setData(null);
    setError(null);
    setCompletedTiers([]);
    if (repo) void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo]);

  const markTierComplete = (tierNum: number) => {
    if (!repo) return;
    setCompletedTiers((prev) => {
      if (prev.includes(tierNum)) return prev;
      const next = [...prev, tierNum];
      try {
        localStorage.setItem(progressKey(repo), JSON.stringify(next));
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  };

  const isTierUnlocked = (t: OnboardTier) => {
    if (t.tier === 1) return true;
    return t.prerequisites.every((pr) => completedTiers.includes(pr));
  };

  const totalItems = curriculum?.tiers.length || 4;
  const pct = Math.round((completedTiers.length / Math.max(1, totalItems)) * 100);

  if (!repo) return null;

  return (
    <div className="card p-4 flex flex-col gap-3 overflow-hidden min-w-0">
      <div className="flex items-center gap-1.5 justify-between">
        <div className="flex items-center gap-1.5 min-w-0">
          <GraduationCap size={14} className="text-accent-cyan shrink-0" />
          <h3 className="label-caps truncate">Student Onboarding</h3>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <div className="flex bg-bg-panel-alt rounded-md p-0.5 border border-border-hairline text-[10px]">
            <button
              onClick={() => setMode("curriculum")}
              className={`px-2 py-0.5 rounded transition-colors ${
                mode === "curriculum"
                  ? "bg-accent-cyan/20 text-accent-cyan font-bold"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              Curriculum (V2.7)
            </button>
            <button
              onClick={() => setMode("classic")}
              className={`px-2 py-0.5 rounded transition-colors ${
                mode === "classic"
                  ? "bg-accent-cyan/20 text-accent-cyan font-bold"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              Classic
            </button>
          </div>

          <button
            onClick={() => void loadData()}
            disabled={loading}
            title="Refresh curriculum"
            aria-label="Refresh curriculum"
            className="w-6 h-6 flex items-center justify-center rounded-md text-text-muted hover:text-text-primary hover:bg-bg-panel-hover transition-all"
          >
            <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-2xs text-text-muted mb-1">
          <span>Topological Curriculum Progress</span>
          <span className="font-mono text-accent-emerald font-semibold">{pct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-bg-panel-alt border border-border-hairline overflow-hidden">
          <div
            className="h-full bg-accent-emerald transition-all duration-500"
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 rounded-lg text-xs bg-accent-rose/10 border border-accent-rose/25 text-accent-rose">
          {error}
        </div>
      )}

      {loading && !curriculum && !data && (
        <>
          <SkeletonCard lines={2} />
          <SkeletonCard lines={3} />
        </>
      )}

      {/* Mode 1: Topological Curriculum (V2.7) */}
      {mode === "curriculum" && curriculum && (
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center gap-1.5 text-2xs text-text-muted">
            <Layers size={11} className="text-accent-cyan" />
            <span>
              Tarjan SCC condensation: {curriculum.scc_count} components, {curriculum.dag_edges} DAG edges
            </span>
          </div>

          <div className="flex flex-col gap-2">
            {curriculum.tiers.map((t) => (
              <TierCard
                key={t.tier}
                tier={t}
                unlocked={isTierUnlocked(t)}
                completed={completedTiers.includes(t.tier)}
                onComplete={() => markTierComplete(t.tier)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Mode 2: Classic Levels */}
      {mode === "classic" && data && (
        <div className="flex flex-col gap-2">
          {data.levels.map((lv) => (
            <div key={lv.level} className="rounded-xl border border-border-subtle bg-bg-panel p-3">
              <span className="text-2xs font-bold text-accent-amber">Level {lv.level}: {lv.title}</span>
              <p className="text-2xs text-text-muted mt-1">{lv.description}</p>
              {lv.quiz.length > 0 && <Quiz quiz={lv.quiz} onPassed={() => markTierComplete(lv.level)} />}
            </div>
          ))}

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
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
