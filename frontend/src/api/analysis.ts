/**
 * analysis.ts
 * Typed client for the graph-intelligence endpoints (Milestones 7.1-7.3, 1.3).
 *
 * These are the four things the graph could not previously show:
 *   hotspots   git churn blended with centrality
 *   cycles     dependency cycles, at file and symbol level
 *   unreachable symbols no entry point can reach
 *   hubs       the most central nodes, by PageRank
 *
 * Every endpoint degrades to an `available: false` payload rather than an
 * error, so the UI can simply not render the panel.
 */

const BASE = "";
const JSON_TIMEOUT_MS = 30_000;

async function _json(res: Response) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

async function _fetchWithTimeout(path: string): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), JSON_TIMEOUT_MS);
  try {
    return await fetch(path, { signal: controller.signal });
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// ── Hotspots ────────────────────────────────────────────────────────────────

export interface HotspotEntry {
  path: string;
  commits: number;
  lines_added: number;
  lines_deleted: number;
  churn_score: number;
  primary_author: string;
  last_modified: string;
  /** Churn blended with centrality, 0..1. */
  hotspot_score: number;
  co_changes: Array<[string, number]>;
}

export interface HotspotsResponse {
  available: boolean;
  reason: string;
  window_days: number;
  files: HotspotEntry[];
  total_files: number;
}

export async function getHotspots(windowDays = 90): Promise<HotspotsResponse> {
  return _json(
    await _fetchWithTimeout(`${BASE}/api/analysis/hotspots?window_days=${windowDays}`),
  );
}

// ── Cycles ──────────────────────────────────────────────────────────────────

export interface CycleDetail {
  length: number;
  members: string[];
  layers: string[];
  crosses_layers: boolean;
  severity: "error" | "warning";
}

export interface CyclesResponse {
  available: boolean;
  reason: string;
  cycles: CycleDetail[];
  file_cycles: number;
  symbol_cycles: number;
  total: number;
  cross_layer_count: number;
}

export async function getCycles(): Promise<CyclesResponse> {
  return _json(await _fetchWithTimeout(`${BASE}/api/analysis/cycles`));
}

// ── Unreachable ─────────────────────────────────────────────────────────────

export interface UnreachableEntry {
  id: string;
  label: string;
  file: string;
  type: string;
}

export interface UnreachableResponse {
  available: boolean;
  reason: string;
  /** Always true — this is a static estimate, not proof of dead code. */
  estimate: boolean;
  entry_points: string[];
  entry_point_count: number;
  unreachable: UnreachableEntry[];
  total: number;
}

export async function getUnreachable(): Promise<UnreachableResponse> {
  return _json(await _fetchWithTimeout(`${BASE}/api/analysis/unreachable`));
}

// ── Hubs ────────────────────────────────────────────────────────────────────

export interface HubEntry {
  id: string;
  label: string;
  type: string;
  file: string;
  pagerank: number;
}

export interface HubsResponse {
  available: boolean;
  reason: string;
  hubs: HubEntry[];
  total_nodes: number;
}

export async function getHubs(limit = 15): Promise<HubsResponse> {
  return _json(await _fetchWithTimeout(`${BASE}/api/analysis/hubs?limit=${limit}`));
}

// ── Heatmap scale ───────────────────────────────────────────────────────────

/**
 * The churn spectrum: emerald for stable, amber for warm, crimson for a
 * hotspot. Mirrors the spec — emerald green (stable / rarely touched)
 * through amber to crimson red (high-frequency hotspot with a high blast
 * radius).
 */
export const CHURN_COLORS = {
  stable: "#10B981",   // emerald
  warm: "#F59E0B",     // amber
  hot: "#DC2626",      // crimson
} as const;

/**
 * Map a hotspot score (0..1) to its colour.
 *
 * The thresholds are deliberately not linear: most files in a healthy
 * repository are cold, so a linear ramp would paint everything amber and
 * the genuinely hot files would not stand out.
 */
export function churnColor(score: number): string {
  if (score <= 0) return "transparent";
  if (score < 0.25) return CHURN_COLORS.stable;
  if (score < 0.55) return CHURN_COLORS.warm;
  return CHURN_COLORS.hot;
}

/** A short human label for a hotspot score. */
export function churnLabel(score: number): string {
  if (score <= 0) return "no churn data";
  if (score < 0.25) return "stable";
  if (score < 0.55) return "churn";
  return "hotspot";
}
