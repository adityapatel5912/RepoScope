/**
 * TourPanel.tsx
 * Conversational onboarding "Code Tours" — type a topic (e.g. "auth"),
 * get an ordered step-by-step reading tour; each step highlights its
 * node on the graph.
 */
import { useEffect, useRef, useState } from "react";
import { generateTour, type Tour } from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";
import { Map, X, ChevronLeft, ChevronRight } from "lucide-react";

export interface TourRequest {
  topic: string;
  ts: number;
}

/** Full tour progress, consumed by the graph for badges + progress bar. */
export interface TourState {
  currentNodeId: string | null;
  pastNodeIds: string[];
  step: number;
  total: number;
}

interface Props {
  onHighlightNode?: (nodeId: string | null) => void;
  onTourState?: (state: TourState | null) => void;
  request?: TourRequest | null;
}

// Node-type badge colors (matches NodeDrawer tokens)
const TYPE_BADGE: Record<string, string> = {
  file:     "text-green-700      border-green-500/30     bg-green-50",
  function: "text-gold-700       border-gold-500/30      bg-gold-50",
  class:    "text-indigo-600     border-indigo-500/30    bg-indigo-50",
  import:   "text-slate-500      border-slate-400/30     bg-slate-100",
};

export default function TourPanel({ onHighlightNode, onTourState, request }: Props) {
  const [topic, setTopic]       = useState("");
  const [tour, setTour]         = useState<Tour | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading]   = useState(false);
  const requestIdRef           = useRef(0);
  const [error, setError]       = useState<string | null>(null);

  const emitState = (t: Tour, i: number) => {
    onHighlightNode?.(t.steps[i].node_id);
    onTourState?.({
      currentNodeId: t.steps[i].node_id,
      pastNodeIds: t.steps.slice(0, i).map((s) => s.node_id),
      step: i,
      total: t.total_steps,
    });
  };

  const generate = async (override?: string) => {
    const t = (override ?? topic).trim();
    if (!t || loading) return;
    if (t.length > 100) {
      setError('Tour topic must be 100 characters or fewer');
      return;
    }
    const reqId = ++requestIdRef.current;
    setTopic(t);
    setLoading(true);
    setError(null);
    try {
      const data = await generateTour(t);
      if (reqId !== requestIdRef.current) return;  // stale
      setTour(data);
      setCurrentStep(0);
      emitState(data, 0);
      toast.success(`Tour ready: ${data.total_steps} steps`);
    } catch (e: unknown) {
      if (reqId !== requestIdRef.current) return;  // stale
      const msg = e instanceof Error ? e.message : "Failed to generate tour";
      setError(msg);
      setTour(null);
      onTourState?.(null);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const goTo = (i: number) => {
    if (!tour || i < 0 || i >= tour.total_steps) return;
    setCurrentStep(i);
    emitState(tour, i);
  };

  const stop = () => {
    setTour(null);
    setError(null);
    onHighlightNode?.(null);
    onTourState?.(null);
  };

  // External request (e.g. "Start tour from here" in the node drawer)
  useEffect(() => {
    if (request?.topic) generate(request.topic);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request?.ts]);

  const step = tour?.steps[currentStep];

  return (
    <div className="card p-4 flex flex-col gap-3">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h3 className="label-caps flex items-center gap-1.5">
          <Map size={12} className="text-accent-cyan" />
          Code Tour
        </h3>
        {tour && (
          <button
            onClick={stop}
            title="Stop tour"
            aria-label="Stop tour"
            className="w-6 h-6 flex items-center justify-center rounded-md
              text-text-muted hover:text-text-primary hover:bg-bg-panel-hover
              transition-all duration-150"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* ── Input row ── */}
      <div className="flex gap-2 items-center">
        <input
          id="tour-topic-input" maxLength={100}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && generate()}
          placeholder="e.g., auth, checkout, payment"
          disabled={loading}
          aria-label="Tour topic"
          className="
            flex-1 min-w-0 px-3 py-2 rounded-lg text-xs
            bg-bg-panel-alt border border-border-subtle
            text-text-primary placeholder:text-text-muted
            focus:outline-none focus:border-accent-cyan/50 focus:ring-1 focus:ring-accent-cyan/20
            disabled:opacity-50 transition-all duration-200
          "
        />
        <button
          onClick={() => generate()}
          disabled={loading || !topic.trim()}
          className="
            flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold
            bg-accent-cyan/15 border border-accent-cyan/30 text-accent-cyan
            hover:bg-accent-cyan/25 disabled:opacity-40 disabled:cursor-not-allowed
            transition-all duration-200 whitespace-nowrap shrink-0
          "
        >
          {loading ? <span className="btn-spinner" /> : null}
          {loading ? "Touring" : "Start"}
        </button>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="
          mt-2.5 px-3 py-2 rounded-lg text-xs
          bg-accent-rose/10 border border-accent-rose/25 text-accent-rose
        ">
          {error}
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loading && !tour && (
        <div className="mt-2.5">
          <SkeletonCard lines={3} />
          <SkeletonCard lines={2} />
        </div>
      )}

      {/* ── Tour body ── */}
      {tour && step && (
        <div className="mt-3">
          <div className="text-center text-2xs text-text-muted mb-2">
            Step <span className="text-accent-cyan font-semibold">{currentStep + 1}</span>
            {" "}of {tour.total_steps} · <span className="italic">{tour.topic}</span>
          </div>

          <div className="rounded-xl bg-bg-panel-alt border border-border-subtle px-3 py-3 mb-2.5">
            <span className={`
              inline-block text-2xs font-semibold uppercase tracking-wider
              px-2 py-0.5 rounded border mb-1.5
              ${TYPE_BADGE[step.type] ?? "text-text-muted border-border-strong bg-bg-panel-alt"}
            `}>
              {step.type}
            </span>
            <div className="text-xs font-semibold text-text-primary leading-snug mb-0.5">
              {step.label}
            </div>
            <div className="font-mono text-2xs text-text-muted break-all mb-1.5">
              {step.file}{step.line > 0 && `:${step.line}`}
            </div>
            <p className="text-xs text-text-muted leading-relaxed m-0">
              {step.explanation}
            </p>
          </div>

          {/* Prev / Next */}
          <div className="flex gap-2 mb-2.5">
            <button
              onClick={() => goTo(currentStep - 1)}
              disabled={currentStep === 0}
              className="
                flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-xs
                bg-bg-panel-alt border border-border-subtle text-text-primary
                hover:bg-bg-panel-hover disabled:opacity-30 disabled:cursor-not-allowed
                transition-all duration-200
              "
            >
              <ChevronLeft size={12} /> Prev
            </button>
            <button
              onClick={() => goTo(currentStep + 1)}
              disabled={currentStep === tour.total_steps - 1}
              className="
                flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-xs
                bg-bg-panel-alt border border-border-subtle text-text-primary
                hover:bg-bg-panel-hover disabled:opacity-30 disabled:cursor-not-allowed
                transition-all duration-200
              "
            >
              Next <ChevronRight size={12} />
            </button>
          </div>

          {/* Step dots */}
          <div className="flex justify-center gap-1.5 flex-wrap">
            {tour.steps.map((s, i) => (
              <button
                key={s.node_id}
                onClick={() => goTo(i)}
                aria-label={`Go to step ${i + 1}`}
                className={`
                  w-2 h-2 rounded-full transition-all duration-150
                  ${i === currentStep
                    ? "bg-accent-cyan scale-125"
                    : "bg-border-strong hover:bg-text-muted"}
                `}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Empty hint ── */}
      {!tour && !loading && !error && (
        <p className="mt-2 text-2xs text-text-muted leading-relaxed">
          Get a guided walk through any part of the codebase.
        </p>
      )}
    </div>
  );
}
