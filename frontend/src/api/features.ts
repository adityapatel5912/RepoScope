/**
 * features.ts
 * API client for Code Tours and What-If Impact Analysis, with
 * response-shape guards. Reuses the stable tab SESSION_ID from client.ts.
 */
import { apiErrorHint } from "./client";
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
  reason?: string;
}

export interface Tour {
  ok?: boolean;
  topic: string;
  track?: string;
  track_label?: string;
  why_this_order?: string;
  available?: boolean;
  total_steps: number;
  steps: TourStep[];
}

export interface TourOptions {
  topic?: string;
  track?: "request_lifecycle" | "data_flow" | "change_impact" | "onboarding" | string;
  target_node_id?: string;
  max_stops?: number;
}

export interface ImpactNode {
  id: string;
  label: string;
  type: string;
  file: string;
}

export interface ImpactHop {
  hop: number;
  label: string;
  nodes: ImpactNode[];
  edges?: Array<{ source: string; target: string; type?: string }>;
}

export interface ImpactScoreBreakdown {
  direct_callers: number;
  transitive_callers: number;
  api_boundaries: number;
  test_gaps: number;
  raw_score?: number;
  normalized_score?: number;
}

export interface ImpactExplanationPath {
  target: string;
  hop: number;
  path: string[];
  reason: string;
}

export interface Impact {
  target: ImpactNode;
  max_depth?: number;
  direct_impacts: ImpactNode[];
  transitive_impacts: ImpactNode[];
  hops?: ImpactHop[];
  score_breakdown?: ImpactScoreBreakdown;
  api_boundaries?: ImpactNode[];
  test_gaps?: Array<{ id?: string; label?: string; file?: string; detail: string }>;
  explanation_paths?: ImpactExplanationPath[];
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
    const err = await r.json().catch(() => ({ detail: apiErrorHint(r) }));
    throw new Error(err.detail ?? apiErrorHint(r));
  }
  const data: unknown = await r.json();
  if (!validate(data)) {
    throw new Error("Unexpected response from server");
  }
  return data as T;
}

async function getJson<T>(
  path: string,
  validate: (d: unknown) => boolean,
  timeoutMs = JSON_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let r: Response;
  try {
    r = await fetch(path, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Id": SESSION_ID,
        ...aiHeaders(),
      },
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
    const err = await r.json().catch(() => ({ detail: apiErrorHint(r) }));
    throw new Error(err.detail ?? apiErrorHint(r));
  }
  const data: unknown = await r.json();
  if (!validate(data)) {
    throw new Error("Unexpected response from server");
  }
  return data as T;
}

export function generateTour(optsOrTopic: string | TourOptions): Promise<Tour> {
  const body = typeof optsOrTopic === "string" ? { topic: optsOrTopic } : optsOrTopic;
  return postJson("/api/tour/generate", body, isTour, LLM_TIMEOUT_MS);
}

export function getCodeTourExportUrl(track = "request_lifecycle"): string {
  return `/api/tour/export?track=${encodeURIComponent(track)}&format=codetour`;
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

export interface ContractFinding {
  kind: string;
  symbol: string;
  file: string;
  line: number;
  severity: "error" | "warning" | "note" | "BREAKING" | "INFO" | string;
  title?: string;
  detail?: string;
  message?: string;
  consumers?: string[];
  guidance?: string;
}

export interface TestGap {
  symbol?: string | null;
  file: string;
  line?: number;
  detail: string;
}

export interface PRImpact {
  ok?: boolean;
  pr_number: number;
  pr_title: string;
  pr_state?: string;
  risk_score: number;
  risk_level: Impact["risk_level"];
  affected_files: PRImpactFile[];
  files_analyzed: number;
  impacted_total: number;
  direct_total: number;
  transitive_total: number;
  suggested_tests: string[];
  test_gaps?: TestGap[];
  symbol_findings?: ContractFinding[];
  architecture_impact?: {
    findings: ContractFinding[];
    cycles: unknown[];
    summary?: { breaking: number; boundary: number; contracts: number };
  };
  sarif_doc?: Record<string, unknown>;
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

export function generatePRImpact(repoUrl: string, prNumber: number, format: "json" | "sarif" = "json"): Promise<PRImpact> {
  return postJson(
    "/api/impact/pr",
    { repo_url: repoUrl, pr_number: prNumber, format },
    isPRImpact,
    LLM_TIMEOUT_MS, // clone + graph build can take a while on cold starts
  );
}

// ── Reverse Build Prompt (GitReverse) ─────────────────────────────────────

export interface ReversePromptFile {
  path: string;
  content: string;
}

export interface ReversePrompt {
  prompt: string;
  ok?: boolean;
  mode?: string;
  content?: string;
  files?: ReversePromptFile[];
  tokens?: number;
  format?: string;
  source?: { nodes: number; edges: number; root: string };
  warnings?: string[];
}

function isReversePrompt(d: unknown): d is ReversePrompt {
  return (
    typeof d === "object" && d !== null &&
    typeof (d as ReversePrompt).prompt === "string" &&
    (d as ReversePrompt).prompt.length > 0
  );
}

export interface ReversePromptOptions {
  mode?: "context" | "rebuild" | "feature" | "spec" | string;
  target_node_id?: string;
  budget?: number;
  format?: string;
}

export function generateReversePrompt(opts?: ReversePromptOptions): Promise<ReversePrompt> {
  return postJson("/api/repo/reverse-prompt", opts ?? {}, isReversePrompt, LLM_TIMEOUT_MS);
}

// ── Scaffold (CodeCrafters-style starter from the loaded repo) ────────────

export interface ScaffoldFile {
  path: string;
  content: string;
  purpose: string;
  language?: string;
}

export interface Scaffold {
  ok?: boolean;
  project_type: string;
  file_tree: string[];
  files: ScaffoldFile[];
  entry_files?: string[];
  top_nodes?: string[];
  warnings?: string[];
  token_estimate?: number;
  bootstrap_command?: string;
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

export function generateScaffold(mode: "preview" | "zip" | "command" = "preview"): Promise<Scaffold> {
  return postJson("/api/scaffold", { mode }, isScaffold, LLM_TIMEOUT_MS);
}

export async function downloadScaffoldZip(): Promise<Blob> {
  const r = await fetch("/api/scaffold/download-zip", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...aiHeaders(),
    },
  });
  if (!r.ok) {
    throw new Error(`Zip download failed: ${r.statusText}`);
  }
  return await r.blob();
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

export interface OnboardChallenge {
  id: string;
  title: string;
  prompt: string;
  options: string[];
  answer_index: number;
  explanation: string;
  kind?: string;
}

export interface OnboardTierFile {
  path: string;
  label?: string;
  role: string;
  in_degree?: number;
  out_degree?: number;
  scc_group?: string[];
  why?: string;
}

export interface OnboardTier {
  tier: number;
  name: string;
  badge: string;
  description: string;
  prerequisites: number[];
  files: OnboardTierFile[];
  challenges: OnboardChallenge[];
}

export interface OnboardCurriculum {
  ok: boolean;
  repo?: string | null;
  total_tiers: number;
  scc_count: number;
  dag_edges: number;
  tiers: OnboardTier[];
}

export interface ChallengeVerifyResult {
  ok: boolean;
  correct: boolean;
  feedback: string;
  next_tier: number;
  unlocked: boolean;
}

export interface Onboarding {
  ok?: boolean;
  repo?: string | null;
  levels: OnboardLevel[];
  good_first_issues: GoodFirstIssue[];
  curriculum?: OnboardCurriculum;
  tiers?: OnboardTier[];
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

export async function getOnboardCurriculum(): Promise<OnboardCurriculum> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), JSON_TIMEOUT_MS);
  return fetch("/api/onboard/curriculum", { signal: controller.signal })
    .finally(() => clearTimeout(timer))
    .then(async (r) => {
      if (!r.ok) throw new Error("Failed to load onboarding curriculum");
      return r.json();
    });
}

export function verifyChallenge(
  tier: number,
  challenge_id: string,
  answer: string,
): Promise<ChallengeVerifyResult> {
  return postJson(
    "/api/onboard/verify-challenge",
    { tier, challenge_id, answer },
    (d): d is ChallengeVerifyResult => {
      return typeof d === "object" && d !== null && "correct" in (d as any);
    },
  );
}

// ── Metrics, Hotspots, Bus Factor & Time Machine ────────────────────────────

export interface HotspotFile {
  path: string;
  commits: number;
  lines_added: number;
  lines_deleted: number;
  churn_score: number;
  complexity: number;
  hotspot_score: number;
  primary_author: string;
  author_share: number;
  bus_factor_risk: boolean;
  risk_level: "critical" | "high" | "medium" | "low";
  quadrant: "critical" | "debt" | "active" | "stable";
}

export interface HotspotsReport {
  ok: boolean;
  total_files: number;
  high_risk_hotspots: HotspotFile[];
  bus_factor_warnings: HotspotFile[];
  quadrant_summary: {
    critical: number;
    debt: number;
    active: number;
    stable: number;
  };
  files: HotspotFile[];
}

export interface CompareResult {
  ok: boolean;
  ref_a: string;
  ref_b: string;
  added_files: string[];
  removed_files: string[];
  modified_files: string[];
  summary: string;
  architectural_drift: string[];
}

export interface IncidentRecord {
  id: string;
  timestamp: string;
  event_type: string;
  category: string;
  severity: "critical" | "high" | "medium" | "low";
  triage: string;
  details: Record<string, unknown>;
}

export interface IncidentTimeline {
  ok: boolean;
  total: number;
  incidents: IncidentRecord[];
}

export async function getHotspots(limit = 100): Promise<HotspotsReport> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), JSON_TIMEOUT_MS);
  return fetch(`/api/metrics/hotspots?limit=${limit}`, { signal: controller.signal })
    .finally(() => clearTimeout(timer))
    .then(async (r) => {
      if (!r.ok) throw new Error("Failed to load hotspots metrics");
      return r.json();
    });
}

export async function compareRefs(refA = "HEAD~10", refB = "HEAD"): Promise<CompareResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), JSON_TIMEOUT_MS);
  return fetch(
    `/api/metrics/compare?ref_a=${encodeURIComponent(refA)}&ref_b=${encodeURIComponent(refB)}`,
    { signal: controller.signal },
  )
    .finally(() => clearTimeout(timer))
    .then(async (r) => {
      if (!r.ok) throw new Error("Failed to compare revisions");
      return r.json();
    });
}

export async function getIncidents(limit = 50): Promise<IncidentTimeline> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), JSON_TIMEOUT_MS);
  return fetch(`/api/tracking/incidents?limit=${limit}`, { signal: controller.signal })
    .finally(() => clearTimeout(timer))
    .then(async (r) => {
      if (!r.ok) throw new Error("Failed to load incident timeline");
      return r.json();
    });
}


// ── Security Scan (Breaking Change + Secret + CVE) ────────────────────────

export interface SecurityTracePropagator {
  file: string;
  line: number;
  symbol: string;
  via: string;
}

export interface SecurityTrace {
  source_file: string;
  source_line: number;
  source_label: string;
  propagators: SecurityTracePropagator[];
  sink_file: string;
  sink_line: number;
  sink_label: string;
}

export interface SecurityFlag {
  type: "SECRET" | "BREAKING" | "CVE" | "TAINT" | "INJECTION" | "CONFIG" | "AUTH_BYPASS" | string;
  severity: "critical" | "high" | "medium" | "low";
  file: string;
  line: number;
  detail: string;
  suggestion: string;
  engine?: "cross_file_taint" | "secrets_entropy" | "dependency_cve" | "injection_sinks" | "insecure_config" | "auth_bypass" | "breaking" | string;
  cwe?: string;
  trace?: SecurityTrace;
  patch_available?: boolean;
}

export interface SecurityScan {
  ok?: boolean;
  repo: string | null;
  scanned: { repo_files: boolean; pr: number | null; commits: number; taint_flows?: number };
  flags: SecurityFlag[];
  total_flags: number;
  summary: {
    by_engine?: Record<string, number>;
    SECRET: number;
    BREAKING: number;
    CVE: number;
    TAINT?: number;
    INJECTION?: number;
    CONFIG?: number;
    AUTH_BYPASS?: number;
    critical: number;
    high: number;
    medium?: number;
    low?: number;
  };
}

export interface SecurityPatch {
  ok: boolean;
  file: string;
  line: number;
  engine: string;
  diff: string;
  syntax_valid: boolean;
  explanation: string;
  error?: string;
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

export function fetchSecurityPatch(req: {
  file: string;
  line: number;
  engine?: string;
  detail: string;
  type?: string;
}): Promise<SecurityPatch> {
  return postJson(
    "/api/security/patch",
    req,
    (d): d is SecurityPatch => typeof d === "object" && d !== null && "ok" in d,
  );
}

export function fetchSecuritySarif(): Promise<Record<string, unknown>> {
  return getJson(
    "/api/security/sarif",
    (d: unknown): d is Record<string, unknown> => typeof d === "object" && d !== null && "$schema" in d,
  );
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
      const err = await r.json().catch(() => ({ detail: apiErrorHint(r) }));
      throw new Error(err.detail ?? apiErrorHint(r));
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
    const err = await r.json().catch(() => ({ detail: apiErrorHint(r) }));
    throw new Error(err.detail ?? apiErrorHint(r));
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
