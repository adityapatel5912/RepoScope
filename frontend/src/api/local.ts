/**
 * local.ts — the local-mode client.
 *
 * Milestone 2.2. Local mode is the promise that a private, uncommitted
 * repository can be analysed without a GitHub account, without a token,
 * and without anything leaving the machine.
 *
 * Two things live here:
 *
 *   1. The status of the live session — is it watching? what did the last
 *      re-index change?
 *   2. The live-graph stream. The backend pushes a `context` event every
 *      time the watcher re-indexes, and the frontend renders it with the
 *      SAME handler the chat stream uses. There is no second rendering
 *      path for the live graph, which is why it needed no new code in the
 *      graph components.
 *
 * The stream is read with `fetch` rather than `EventSource`. The chat
 * stream already reads SSE that way, so the parser is shared — and
 * `EventSource` logs a browser console error when a connection drops,
 * which would trip the QA console gate for something that is not a
 * product fault.
 */

import { apiErrorHint, networkErrorHint } from "./client";

const BASE = "";

export interface LocalStatus {
  attached: boolean;
  root: string | null;
  watching: boolean;
  watchdog_available: boolean;
  graph_summary: string;
  node_count: number;
  edge_count: number;
  change_count: number;
  last_update: Record<string, unknown>;
  subscribers: number;
  /** True when the loaded repository is a local directory. */
  is_local: boolean;
}

export interface LocalLoadResult {
  ok: boolean;
  local_path: string;
  repo: string;
  file_count: number;
  graph_summary: string;
  node_count: number;
  edge_count: number;
  watching: boolean;
  is_local: boolean;
}

/** The payload of a live `context` event. */
export interface LiveContext {
  nodes: unknown[];
  edges: unknown[];
  graph_summary: string;
  node_count: number;
  edge_count: number;
  changed: string[];
  removed: string[];
  duration_ms: number;
  timestamp: number;
}

export interface LocalEventHandlers {
  /** A fresh graph, pushed after a re-index. */
  onContext: (context: LiveContext) => void;
  /** The stream is open. */
  onReady?: () => void;
  /** The stream failed. */
  onError?: (message: string) => void;
}

async function _json(res: Response) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: apiErrorHint(res) }));
    throw new Error(err.detail ?? apiErrorHint(res));
  }
  return res.json();
}

export async function getLocalStatus(): Promise<LocalStatus> {
  return _json(await fetch(`${BASE}/api/local/status`));
}

export async function loadLocalRepo(path: string): Promise<LocalLoadResult> {
  return _json(
    await fetch(`${BASE}/api/local/load`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, watch: true }),
    }),
  );
}

/**
 * Read the live-graph stream until it ends or the signal aborts.
 *
 * Resolves when the stream closes. Errors are reported through
 * `onError` rather than thrown, because a dropped stream is a state the
 * UI has to survive, not an exception it has to handle.
 */
export async function streamLocalEvents(
  handlers: LocalEventHandlers,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${BASE}/api/local/events`, {
      headers: { Accept: "text/event-stream" },
      signal,
    });

    if (!response.ok || !response.body) {
      handlers.onError?.(
        response.status === 404
          ? "Live updates need the local-mode backend."
          : `The live update stream failed (HTTP ${response.status}).`,
      );
      return;
    }

    const { parseSSE } = await import("./sse");
    const reader = response.body.getReader();

    for await (const { event, data } of parseSSE(reader)) {
      try {
        if (event === "context") {
          handlers.onContext(JSON.parse(data) as LiveContext);
        } else if (event === "ready") {
          handlers.onReady?.();
        }
      } catch (e: unknown) {
        // A malformed frame is a backend bug, but it must not kill the
        // stream — the next frame may be perfectly good.
        handlers.onError?.("A live update could not be read.");
      }
    }
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      return;  // the component unmounted; expected, not an error
    }
    handlers.onError?.(networkErrorHint(e));
  }
}
