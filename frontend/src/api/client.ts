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
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
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
    throw e;
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

export interface SSECallbacks {
  onContext:  (d: ContextPayload) => void;
  onToken:    (t: string) => void;
  onTracking: (d: unknown) => void;
  onDone:     () => void;
  onError?:   (msg: string) => void;
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
