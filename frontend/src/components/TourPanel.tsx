/**
 * TourPanel.tsx
 * Conversational onboarding "Code Tours" — type a topic (e.g. "auth"),
 * get an ordered step-by-step reading tour; each step highlights its
 * node on the graph.
 */
import { useEffect, useRef, useState } from "react";
import {
  generateTour, synthesizeSpeech, playSpeechAudio, speakBrowser, stopSpeechAudio,
  type Tour,
} from "../api/features";
import { toast } from "./Toasts";
import { SkeletonCard } from "./Skeleton";
import { Map, X, ChevronLeft, ChevronRight, Play, Square, Volume2 } from "lucide-react";

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

  // ── Voice engine state ──
  // Server TTS (OpenRouter fish-audio / deepgram flux) with browser
  // speechSynthesis fallback. voiceOn = auto-advance playback running.
  const [voiceOn, setVoiceOn]         = useState(false);
  const [speaking, setSpeaking]       = useState(false);
  const [voiceEngine, setVoiceEngine] = useState<"server" | "browser" | "none">("none");
  const voiceEngineRef = useRef<"server" | "browser" | "none">("none");
  const playTokenRef   = useRef(0);   // increments on stop → stale loops exit

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
    stopPlayback();   // kill any narration from a previous tour
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

  const goTo = (i: number, viaUser = false) => {
    if (!tour || i < 0 || i >= tour.total_steps) return;
    setCurrentStep(i);
    emitState(tour, i);
    // Manual navigation while narrating → restart narration at the new step
    if (viaUser && voiceOn) void playFrom(i);
  };

  const narrationFor = (t: Tour, i: number): string => {
    const s = t.steps[i];
    return `Step ${i + 1} of ${t.total_steps}. Now in ${s.label}. ${s.explanation}`;
  };

  /** Speak one step: server TTS first, browser speechSynthesis as fallback. */
  const speakOnce = async (narration: string, token: number): Promise<void> => {
    if (voiceEngineRef.current !== "browser") {
      try {
        const audio = await synthesizeSpeech(narration);
        voiceEngineRef.current = "server";
        setVoiceEngine("server");
        await playSpeechAudio(audio);
        return;
      } catch {
        if (token !== playTokenRef.current) return;
        voiceEngineRef.current = "browser";
        setVoiceEngine("browser");
      }
    }
    await speakBrowser(narration);
  };

  /** Auto-advance playback: narrate steps in order until stopped or done. */
  const playFrom = async (i: number) => {
    const t = tour;
    if (!t || t.total_steps === 0) return;
    const token = ++playTokenRef.current;
    setVoiceOn(true);
    let idx = Math.max(0, Math.min(i, t.total_steps - 1));
    setCurrentStep(idx);
    emitState(t, idx);   // highlight + camera pan sync with the voice
    while (token === playTokenRef.current && idx < t.total_steps) {
      setSpeaking(true);
      try {
        await speakOnce(narrationFor(t, idx), token);
      } catch {
        break;  // playback failed or was cancelled
      } finally {
        if (token === playTokenRef.current) setSpeaking(false);
      }
      if (token !== playTokenRef.current) break;
      idx += 1;
      if (idx < t.total_steps) {
        setCurrentStep(idx);
        emitState(t, idx);
      }
    }
    if (token === playTokenRef.current) {
      setVoiceOn(false);
      setSpeaking(false);
    }
  };

  const stopPlayback = () => {
    playTokenRef.current += 1;   // invalidate any running narration loop
    stopSpeechAudio();
    setVoiceOn(false);
    setSpeaking(false);
  };

  /** Speak just the current step (no auto-advance). */
  const speakCurrent = async () => {
    const t = tour;
    if (!t) return;
    const token = ++playTokenRef.current;
    setVoiceOn(false);
    setSpeaking(true);
    try {
      await speakOnce(narrationFor(t, currentStep), token);
    } catch {
      toast.error("Voice narration is unavailable in this browser");
    } finally {
      if (token === playTokenRef.current) setSpeaking(false);
    }
  };

  const stop = () => {
    stopPlayback();
    setTour(null);
    setError(null);
    onHighlightNode?.(null);
    onTourState?.(null);
  };

  // Cancel any audio when the panel unmounts
  useEffect(() => () => stopPlayback(), []);

  // External request (e.g. "Start tour from here" in the node drawer)
  useEffect(() => {
    if (request?.topic) generate(request.topic);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request?.ts]);

  const step = tour?.steps[currentStep];

  return (
    <div className="card p-4 flex flex-col gap-3 overflow-hidden min-w-0">
      {/* ── Header ── */}
      <div className="flex items-center justify-between min-w-0">
        <h3 className="label-caps flex items-center gap-1.5 truncate">
          <Map size={12} className="text-accent-cyan shrink-0" />
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
            <div className="flex items-start justify-between gap-2">
              <span className={`
                inline-block text-2xs font-semibold uppercase tracking-wider
                px-2 py-0.5 rounded border mb-1.5
                ${TYPE_BADGE[step.type] ?? "text-text-muted border-border-strong bg-bg-panel-alt"}
              `}>
                {step.type}
              </span>
              <button
                onClick={() => void speakCurrent()}
                disabled={speaking}
                title={speaking ? "Narrating…" : "Speak this step"}
                aria-label="Speak this step"
                className="shrink-0 w-6 h-6 flex items-center justify-center rounded-md
                  text-text-muted hover:text-accent-cyan hover:bg-bg-panel-hover
                  disabled:opacity-40 transition-all duration-150"
              >
                <Volume2 size={12} />
              </button>
            </div>
            <div
              className="text-xs font-semibold text-text-primary leading-snug mb-0.5 break-words line-clamp-2"
              title={step.label}
            >
              {step.label}
            </div>
            <div
              className="font-mono text-2xs text-text-muted break-all mb-1.5"
              title={`${step.file}${step.line > 0 ? `:${step.line}` : ""}`}
            >
              {step.file}{step.line > 0 && `:${step.line}`}
            </div>
            <p className="text-xs text-text-muted leading-relaxed m-0">
              {step.explanation}
            </p>
          </div>

          {/* Prev / Play / Next — voice-synced navigation */}
          <div className="flex gap-2 mb-2">
            <button
              onClick={() => goTo(currentStep - 1, true)}
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
            {voiceOn ? (
              <button
                onClick={stopPlayback}
                title="Stop narration"
                aria-label="Stop narration"
                className="
                  flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold
                  bg-accent-rose/15 border border-accent-rose/35 text-accent-rose
                  hover:bg-accent-rose/25 transition-all duration-200
                "
              >
                <Square size={11} /> {speaking ? "Narrating" : "Stop"}
              </button>
            ) : (
              <button
                onClick={() => void playFrom(currentStep)}
                title="Play tour with voice narration — auto-advances with auto-pan"
                aria-label="Play tour with voice narration"
                className="
                  flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold
                  bg-accent-cyan/15 border border-accent-cyan/30 text-accent-cyan
                  hover:bg-accent-cyan/25 transition-all duration-200
                "
              >
                <Play size={11} /> Play Tour
              </button>
            )}
            <button
              onClick={() => goTo(currentStep + 1, true)}
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

          {/* Voice status line */}
          {voiceOn && (
            <div className="text-center text-2xs text-text-muted mb-2">
              🔊 Narrating ·{" "}
              <span className="font-mono">
                {voiceEngine === "server" ? "OpenRouter voice" : "browser voice"}
              </span>
            </div>
          )}

          {/* Step dots */}
          <div className="flex justify-center gap-1.5 flex-wrap">
            {tour.steps.map((s, i) => (
              <button
                key={s.node_id}
                onClick={() => goTo(i, true)}
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
          Get a guided walk through any part of the codebase — press{" "}
          <span className="font-semibold text-text-secondary">▶ Play Tour</span> to hear it
          narrated (OpenRouter voice, browser speech fallback).
        </p>
      )}
    </div>
  );
}
