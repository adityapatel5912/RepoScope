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
      headers: { "Content-Type": "application/json", "X-Session-Id": SESSION_ID },
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
