/**
 * client.ts
 * Typed API client with 30s timeouts on JSON endpoints, external abort
 * support for SSE streams, and response-shape guards.
 */

/** Stable session ID for the lifetime of this browser tab. */
export const SESSION_ID = crypto.randomUUID();

const BASE = "";  // relative — proxied by Vite to http://localhost:8000

const JSON_TIMEOUT_MS = 30_000;

async function _json(res: Response) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = err.detail ?? apiErrorHint(res);
    const error = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    (error as any).status = res.status;
    throw error;
  }
  return res.json();
}

/**
 * A human-readable reason for a failed API call.
 *
 * `res.statusText` for a 500 is the bare string "Internal Server Error",
 * which tells the user nothing. When the backend is unreachable — the
 * most common cause — say so, and say what to check.
 */
export function apiErrorHint(res: Response): string {
  if (res.status >= 500) {
    return `The backend returned ${res.status}. Is it running? (npm run dev / uvicorn on :8000)`;
  }
  if (res.status === 404) {
    return "The backend has no such endpoint.";
  }
  return res.statusText || "Request failed";
}

/**
 * A human-readable reason for a request that never reached the backend.
 *
 * `fetch` rejects with "Failed to fetch" for a connection error, which
 * reads like an application bug rather than "the server is not running".
 */
export function networkErrorHint(err: unknown): string {
  if (err instanceof Error && /failed to fetch|networkerror|load failed/i.test(err.message)) {
    return "Cannot reach the backend. Is it running on :8000?";
  }
  return err instanceof Error ? err.message : String(err);
}

/**
 * fetch with a 30s timeout. On abort, throws a friendly Error that
 * callers can show directly.
 */
async function _fetchWithTimeout(path: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), JSON_TIMEOUT_MS);
  try {
    return await fetch(path, { ...init, signal: controller.signal });
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    // A connection error is almost always "the backend is not running".
    throw new Error(networkErrorHint(e));
  } finally {
    clearTimeout(timer);
  }
}

// ── Repo ──────────────────────────────────────────────────────────────────

export interface RepoLoadResult {
  local_path?: string;
  owner: string;
  repo: string;
  file_count?: number;
  node_count?: number;
  edge_count?: number;
  readme_length?: number;
  ok?: boolean;
}

function isRepoLoadResult(d: unknown): d is RepoLoadResult {
  return (
    typeof d === "object" && d !== null &&
    typeof (d as RepoLoadResult).owner === "string" &&
    typeof (d as RepoLoadResult).repo === "string"
  );
}

export async function loadRepo(url: string): Promise<RepoLoadResult> {
  const data = await _json(await _fetchWithTimeout(`${BASE}/api/repo/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-Id": SESSION_ID },
    body: JSON.stringify({ url }),
  }));
  if (!isRepoLoadResult(data)) {
    throw new Error("Unexpected response from server");
  }
  return data;
}

export async function checkRepo() {
  return _json(await _fetchWithTimeout(`${BASE}/api/repo/check`, {
    headers: { "X-Session-Id": SESSION_ID },
  }));
}

export async function getStatus() {
  return _json(await _fetchWithTimeout(`${BASE}/api/repo/status`));
}

export async function getHealth() {
  return _json(await _fetchWithTimeout(`${BASE}/api/health`));
}

export async function getGraph() {
  return _json(await _fetchWithTimeout(`${BASE}/api/repo/graph`));
}

// ── Mind Map ──────────────────────────────────────────────────────────────

export type {
  MindmapPayload,
  MindmapNode,
  MindmapPillarId,
  MindmapNodeKind,
  MindmapPillarDescriptor,
  MindmapStats,
  MindmapSource,
  MindmapMetrics,
  MindmapRoute,
} from "../lib/mindmapTypes";

import type { MindmapPayload } from "../lib/mindmapTypes";

export async function getMindmap(params?: {
  includeSymbols?: boolean;
  maxNodes?: number;
}): Promise<MindmapPayload> {
  const query = new URLSearchParams();
  if (params?.includeSymbols !== undefined) {
    query.set("include_symbols", String(params.includeSymbols));
  }
  if (params?.maxNodes !== undefined) {
    query.set("max_nodes", String(params.maxNodes));
  }
  const qStr = query.toString();
  const url = `${BASE}/api/mindmap${qStr ? `?${qStr}` : ""}`;
  return _json(await _fetchWithTimeout(url));
}

// ── BYOK ──────────────────────────────────────────────────────────────────

export async function setBYOK(token: string) {
  return _json(await _fetchWithTimeout(`${BASE}/api/byok/set`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-Id": SESSION_ID },
    body: JSON.stringify({ token }),
  }));
}

// ── Commit ────────────────────────────────────────────────────────────────

export async function commit(message: string) {
  return _json(await _fetchWithTimeout(`${BASE}/api/repo/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-Id": SESSION_ID },
    body: JSON.stringify({ message }),
  }));
}

// ── SSE Chat ──────────────────────────────────────────────────────────────

export interface CitationItem {
  raw: string;
  path: string;
  start_line: number | null;
  end_line: number | null;
  symbol: string | null;
  node_id: string | null;
  verified: boolean;
  confidence: number;
  reason: string;
  preview: string;
}

export interface SSECallbacks {
  onContext:   (d: ContextPayload) => void;
  onToken:     (t: string) => void;
  onTracking:  (d: unknown) => void;
  onCitations?: (citations: CitationItem[]) => void;
  onDone:      () => void;
  onError?:    (msg: string) => void;
}

export interface ContextPayload {
  nodes: unknown[];
  edges: unknown[];
  graph_summary: string;
  file_count: number;
  node_count: number;
  edge_count: number;
  readme_length: number;
}

export interface StreamOptions {
  /** AbortSignal to cancel the stream (component unmount / new query). */
  signal?: AbortSignal;
}

import { aiHeaders } from "../utils/aiHeaders";

export async function streamChat(
  mode: string,
  message: string,
  repo: string | null,
  cb: SSECallbacks,
  options: StreamOptions = {},
) {
  const resp = await fetch(`${BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": SESSION_ID,
      ...aiHeaders(),
    },
    body: JSON.stringify({ mode, message, repo }),
    signal: options.signal,
  });

  if (!resp.ok || !resp.body) {
    const err = await resp.json().catch(() => ({ detail: "Stream failed" }));
    cb.onError?.(err.detail ?? "Stream request failed");
    cb.onDone();
    return;
  }

  const { parseSSE } = await import("./sse");
  const reader = resp.body.getReader();

  try {
    for await (const { event, data } of parseSSE(reader)) {
      try {
        if (event === "context")       cb.onContext(JSON.parse(data));
        else if (event === "token")    cb.onToken(JSON.parse(data).t ?? "");
        else if (event === "tracking") cb.onTracking(JSON.parse(data));
        else if (event === "citations") {
          const parsed = JSON.parse(data);
          cb.onCitations?.(parsed.citations ?? []);
        }
        else if (event === "done")     cb.onDone();
        else if (event === "error")    cb.onError?.(JSON.parse(data).message ?? "Unknown error");
      } catch (e) {
        // Genuine parse failure — keep as error log
        console.error("SSE parse error", event, data, e);
      }
    }
  } catch (e: unknown) {
    // Aborted streams are expected on unmount / new query — not errors
    if (!(e instanceof DOMException && e.name === "AbortError")) {
      cb.onError?.(e instanceof Error ? e.message : "Stream interrupted");
    }
  }
}

// ── Harness Configurator (Phase 3) ──────────────────────────────────────────

export type HarnessTransport = "stdio" | "http";

export interface HarnessAgent {
  id: string;
  label: string;
  config_paths: string[];
  transport: HarnessTransport[];
  default_transport: HarnessTransport;
  global_preview_paths: string[];
  docs_url: string;
  verified_at: string;
  notes: string[];
}

export interface HarnessFilePreview {
  path: string;
  format: "json" | "toml" | "markdown";
  content: string;
  exists: boolean;
  diff: string | null;
  will_write: boolean;
}

export interface HarnessPreview {
  ok: boolean;
  agent: string;
  label: string;
  transport: HarnessTransport;
  root: string;
  command: string;
  command_kind: "install" | "server" | "deeplink";
  command_note: string;
  apply_enabled: boolean;
  requires_force: boolean;
  files: HarnessFilePreview[];
  warnings: string[];
}

export interface HarnessApplyResult extends HarnessPreview {
  apply: boolean;
  applied: string[];
  unchanged: string[];
}

export interface HarnessSkill {
  id: string;
  label: string;
  description: string;
  targets: string[];
  files: string[];
  content_available: boolean;
  content: string;
}

export interface HarnessSkills {
  skills: HarnessSkill[];
  content_available: boolean;
}

export async function getHarnessAgents(): Promise<{ agents: HarnessAgent[]; apply_enabled: boolean }> {
  return _json(await _fetchWithTimeout(`${BASE}/api/harness/agents`));
}

export async function getHarnessConfig(params: {
  agent: string;
  transport: HarnessTransport;
  root: string;
}): Promise<HarnessPreview> {
  const q = new URLSearchParams({
    agent: params.agent,
    transport: params.transport,
    root: params.root,
  });
  return _json(await _fetchWithTimeout(`${BASE}/api/harness/config?${q.toString()}`));
}

export async function applyHarnessConfig(body: {
  agent: string;
  transport: HarnessTransport;
  root: string;
  apply: boolean;
  force: boolean;
}): Promise<HarnessApplyResult> {
  return _json(await _fetchWithTimeout(`${BASE}/api/harness/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
}

export async function getHarnessSkills(): Promise<HarnessSkills> {
  return _json(await _fetchWithTimeout(`${BASE}/api/harness/skills`));
}

export async function verifyCitation(
  path: string,
  line?: number | null,
  endLine?: number | null,
  raw?: string,
): Promise<CitationItem> {
  const params = new URLSearchParams({ path });
  if (line != null) params.set("line", String(line));
  if (endLine != null) params.set("end_line", String(endLine));
  if (raw != null) params.set("raw", raw);
  const resp = await fetch(`${BASE}/api/citation/verify?${params.toString()}`);
  if (!resp.ok) {
    throw new Error(`Failed to verify citation: ${resp.statusText}`);
  }
  return resp.json();
}
