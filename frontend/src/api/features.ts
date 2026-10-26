/**
 * features.ts
 * API client for Code Tours and What-If Impact Analysis, with
 * response-shape guards. Reuses the stable tab SESSION_ID from client.ts.
 */
import { SESSION_ID } from "./client";

// ── Shared types ──────────────────────────────────────────────────────────

export interface TourStep {
  step: number;
  node_id: string;
  label: string;
  type: string;
  file: string;
  line: number;
  explanation: string;
}

export interface Tour {
  topic: string;
  total_steps: number;
  steps: TourStep[];
}

export interface ImpactNode {
  id: string;
  label: string;
  type: string;
  file: string;
}

export interface Impact {
  target: ImpactNode;
  direct_impacts: ImpactNode[];
  transitive_impacts: ImpactNode[];
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  suggested_tests: string[];
  total_impacted: number;
  narrative: string;
}

// ── Shape guards ──────────────────────────────────────────────────────────

function isTour(d: unknown): d is Tour {
  return (
    typeof d === "object" && d !== null &&
    typeof (d as Tour).topic === "string" &&
    Array.isArray((d as Tour).steps)
  );
}

function isImpact(d: unknown): d is Impact {
  const imp = d as Impact;
  return (
    typeof d === "object" && d !== null &&
    typeof imp.target === "object" && imp.target !== null &&
    Array.isArray(imp.direct_impacts) &&
    Array.isArray(imp.transitive_impacts) &&
    typeof imp.risk_score === "number"
  );
}

// ── Requests ──────────────────────────────────────────────────────────────

const JSON_TIMEOUT_MS = 30_000;
// LLM-backed endpoints (tour/impact/reverse-prompt) can legitimately take
// over a minute — give them a generous budget.
const LLM_TIMEOUT_MS = 120_000;

import { aiHeaders } from "../utils/aiHeaders";

async function postJson<T>(
  path: string,
  body: object,
  validate: (d: unknown) => boolean,
  timeoutMs = JSON_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let r: Response;
  try {
    r = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Id": SESSION_ID,
        ...aiHeaders(),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  const data: unknown = await r.json();
  if (!validate(data)) {
    throw new Error("Unexpected response from server");
  }
  return data as T;
}

export function generateTour(topic: string): Promise<Tour> {
  return postJson("/api/tour/generate", { topic }, isTour, LLM_TIMEOUT_MS);
}

export function analyzeImpact(target: string, maxDepth = 3): Promise<Impact> {
  return postJson("/api/impact/analyze", { target, max_depth: maxDepth }, isImpact, LLM_TIMEOUT_MS);
}

// ── PR Bot (impact report as a GitHub comment) ────────────────────────────

export interface PRImpactFile {
  file: string;
  status: string;
  additions: number;
  deletions: number;
  in_graph: boolean;
  direct: number;
  transitive: number;
}

export interface PRImpact {
  ok?: boolean;
  pr_number: number;
  pr_title: string;
  risk_score: number;
  risk_level: Impact["risk_level"];
  affected_files: PRImpactFile[];
  files_analyzed: number;
  impacted_total: number;
  direct_total: number;
  transitive_total: number;
  suggested_tests: string[];
  comment: string;
  comment_posted?: boolean;
}

function isPRImpact(d: unknown): d is PRImpact {
  const p = d as PRImpact;
  return (
    typeof d === "object" && d !== null &&
    typeof p.risk_score === "number" &&
    typeof p.comment === "string" && p.comment.length > 0 &&
    Array.isArray(p.affected_files)
  );
}

export function generatePRImpact(repoUrl: string, prNumber: number): Promise<PRImpact> {
  return postJson(
    "/api/impact/pr",
    { repo_url: repoUrl, pr_number: prNumber },
    isPRImpact,
    LLM_TIMEOUT_MS, // clone + graph build can take a while on cold starts
  );
}

// ── Reverse Build Prompt (GitReverse) ─────────────────────────────────────

export interface ReversePrompt {
  prompt: string;
}

function isReversePrompt(d: unknown): d is ReversePrompt {
  return (
    typeof d === "object" && d !== null &&
    typeof (d as ReversePrompt).prompt === "string" &&
    (d as ReversePrompt).prompt.length > 0
  );
}

export function generateReversePrompt(): Promise<ReversePrompt> {
  return postJson("/api/repo/reverse-prompt", {}, isReversePrompt, LLM_TIMEOUT_MS);
}

// ── Scaffold (CodeCrafters-style starter from the loaded repo) ────────────

export interface ScaffoldFile {
  path: string;
  content: string;
  purpose: string;
}

export interface Scaffold {
  ok?: boolean;
  project_type: string;
  file_tree: string[];
  files: ScaffoldFile[];
  entry_files?: string[];
  top_nodes?: string[];
}

function isScaffold(d: unknown): d is Scaffold {
  const s = d as Scaffold;
  return (
    typeof d === "object" && d !== null &&
    typeof s.project_type === "string" &&
    Array.isArray(s.files) && s.files.length > 0 &&
    s.files.every((f) => typeof f?.path === "string" && typeof f?.content === "string")
  );
}

export function generateScaffold(): Promise<Scaffold> {
  return postJson("/api/scaffold", {}, isScaffold, LLM_TIMEOUT_MS);
}

// ── Student Onboarding Mode (learning path + quizzes + Good First Issues) ──

export interface OnboardQuiz {
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
}

export interface OnboardFile {
  path: string;
  why: string;
}

export interface OnboardLevel {
  level: number;
  title: string;
  description: string;
  files: OnboardFile[];
  quiz: OnboardQuiz[];
}

export interface GoodFirstIssue {
  title: string;
  file: string;
  description: string;
  hint: string;
}

export interface Onboarding {
  ok?: boolean;
  repo?: string | null;
  levels: OnboardLevel[];
  good_first_issues: GoodFirstIssue[];
}

function isOnboarding(d: unknown): d is Onboarding {
  const o = d as Onboarding;
  return (
    typeof d === "object" && d !== null &&
    Array.isArray(o.levels) && o.levels.length > 0 &&
    o.levels.every((l) => Array.isArray(l.files)) &&
    Array.isArray(o.good_first_issues)
  );
}

export function generateOnboarding(): Promise<Onboarding> {
  return postJson("/api/onboard", {}, isOnboarding, LLM_TIMEOUT_MS);
}

// ── Security Scan (Breaking Change + Secret + CVE) ────────────────────────

export interface SecurityFlag {
  type: "SECRET" | "BREAKING" | "CVE";
  severity: "critical" | "high" | "medium" | "low";
  file: string;
  line: number;
  detail: string;
  suggestion: string;
}

export interface SecurityScan {
  ok?: boolean;
  repo: string | null;
  scanned: { repo_files: boolean; pr: number | null; commits: number };
  flags: SecurityFlag[];
  total_flags: number;
  summary: {
    SECRET: number;
    BREAKING: number;
    CVE: number;
    critical: number;
    high: number;
  };
}

function isSecurityScan(d: unknown): d is SecurityScan {
  const s = d as SecurityScan;
  return (
    typeof d === "object" && d !== null &&
    Array.isArray(s.flags) &&
    typeof s.summary === "object" && s.summary !== null &&
    typeof s.summary.SECRET === "number"
  );
}

export function securityScan(): Promise<SecurityScan> {
  return postJson("/api/security/scan", {}, isSecurityScan, 120_000);
}

// ── Voice Code Tours (server TTS via OpenRouter audio models) ─────────────

export interface SpeechAudio {
  ok?: boolean;
  audio_base64: string;
  format: string; // "mp3" | "wav" | "ogg"
  model: string;
}

function isSpeechAudio(d: unknown): d is SpeechAudio {
  const s = d as SpeechAudio;
  return (
    typeof d === "object" && d !== null &&
    typeof s.audio_base64 === "string" && s.audio_base64.length > 0 &&
    typeof s.format === "string"
  );
}

/**
 * Synthesize narration through the backend (OpenRouter TTS with key
 * rotation). Throws when no server voice is available — callers should fall
 * back to browser speechSynthesis.
 */
export async function synthesizeSpeech(text: string): Promise<SpeechAudio> {
  return postJson("/api/tts", { text }, isSpeechAudio, 90_000);
}

let currentAudio: HTMLAudioElement | null = null;

/** Stop any in-flight narration (server audio + browser speech). */
export function stopSpeechAudio(): void {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

/** Play base64 audio and resolve when playback finishes (or errors). */
export function playSpeechAudio(audio: SpeechAudio): Promise<void> {
  stopSpeechAudio();
  return new Promise((resolve, reject) => {
    const mime = audio.format === "wav" ? "audio/wav" : audio.format === "ogg" ? "audio/ogg" : "audio/mpeg";
    const el = new Audio(`data:${mime};base64,${audio.audio_base64}`);
    currentAudio = el;
    el.onended = () => {
      if (currentAudio === el) currentAudio = null;
      resolve();
    };
    el.onerror = () => {
      if (currentAudio === el) currentAudio = null;
      reject(new Error("Audio playback failed"));
    };
    void el.play().catch((e) => {
      if (currentAudio === el) currentAudio = null;
      reject(e instanceof Error ? e : new Error("Audio playback failed"));
    });
  });
}

/**
 * Browser speechSynthesis fallback — used when the server TTS route is
 * unavailable (no key, offline, model down). Keeps the accessibility story
 * working everywhere.
 */
export function speakBrowser(text: string): Promise<void> {
  stopSpeechAudio();
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      reject(new Error("speechSynthesis unavailable in this browser"));
      return;
    }
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.02;
    u.onend = () => resolve();
    u.onerror = (e) => reject(new Error(e.error || "browser speech failed"));
    window.speechSynthesis.speak(u);
  });
}

// ── Demo repositories (one-click examples) ─────────────────────────────────

export interface DemoRepo {
  name: string;
  url: string;
  description: string;
}

export function listDemos(): Promise<Record<string, DemoRepo>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), JSON_TIMEOUT_MS);
  return fetch("/api/repo/demos", { signal: controller.signal })
    .finally(() => clearTimeout(timer))
    .then(async (r) => {
      if (!r.ok) throw new Error("Failed to list demo repos");
      return r.json();
    });
}

export async function loadDemo(id: string): Promise<{ owner: string; repo: string; file_count?: number }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120_000);
  try {
    const r = await fetch(`/api/repo/load-demo/${encodeURIComponent(id)}`, {
      method: "POST",
      headers: { "X-Session-Id": SESSION_ID },
      signal: controller.signal,
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail ?? "Failed to load demo");
    }
    return r.json();
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Demo load timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// ── Repo file download (FileTree) ──────────────────────────────────────────

/**
 * Download a single file from the loaded repo. Reads the filename from
 * Content-Disposition when the backend provides it.
 */
export async function downloadRepoFile(path: string): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000); // large files
  let r: Response;
  try {
    r = await fetch(`/api/repo/file?path=${encodeURIComponent(path)}`, {
      headers: { "X-Session-Id": SESSION_ID },
      signal: controller.signal,
    });
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Download timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail ?? "Download failed");
  }
  // Preferred filename from Content-Disposition, falling back to basename
  const cd = r.headers.get("Content-Disposition") ?? "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
  const fallback = path.split("/").pop() ?? "file";
  const filename = match?.[1] ?? fallback;

  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
