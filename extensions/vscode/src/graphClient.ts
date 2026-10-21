/**
 * graphClient.ts
 * The extension's client for the RepoScope backend.
 *
 * The extension does NOT parse code. It asks the backend — the same
 * backend the web canvas draws from — so the numbers it shows and the
 * numbers a human sees are the same numbers. That is the whole point of
 * Correction C11: one index, three front-ends (web, CLI, MCP). The
 * extension is a fourth.
 *
 * Every call is local (127.0.0.1) and read-only.
 */
import * as http from "http";
import * as https from "https";
import { URL } from "url";

export interface Caller {
  id: string;
  label: string;
  file: string;
  line: number;
}

export interface CallersResult {
  available: boolean;
  found: boolean;
  count: number;
  callers: Caller[];
  reason?: string;
}

export interface DependentsResult {
  available: boolean;
  found: boolean;
  file: string;
  dependents: number;
  direct: number;
  transitive: number;
  risk: string;
  risk_score: number;
  top: Caller[];
  reason?: string;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  file?: string;
  line?: number;
  pagerank?: number;
  in_degree?: number;
  out_degree?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: string;
}

export interface GraphClientOptions {
  /** The backend's base URL. */
  baseUrl: string;
  /** How long to wait for a response, in milliseconds. */
  timeoutMs?: number;
}

/** An HTTP GET that parses JSON, with a hard timeout. */
function getJson<T>(url: string, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const parsed = new URL(url);
    const client = parsed.protocol === "https:" ? https : http;

    const request = client.get(
      parsed,
      { headers: { Accept: "application/json" } },
      (response) => {
        if (!response.statusCode || response.statusCode >= 400) {
          response.resume();
          reject(new Error(`HTTP ${response.statusCode} from ${parsed.pathname}`));
          return;
        }
        let body = "";
        response.setEncoding("utf-8");
        response.on("data", (chunk) => { body += chunk; });
        response.on("end", () => {
          try {
            resolve(JSON.parse(body) as T);
          } catch (exc) {
            reject(new Error(`Unreadable response from ${parsed.pathname}`));
          }
        });
      },
    );

    request.setTimeout(timeoutMs, () => {
      request.destroy();
      reject(new Error(`Timed out after ${timeoutMs} ms`));
    });
    request.on("error", (err) => reject(err));
  });
}

export class GraphClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(options: GraphClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? 4000;
  }

  /** Is the backend reachable? */
  async isAlive(): Promise<boolean> {
    try {
      await getJson<{ status: string }>(`${this.baseUrl}/api/health`, this.timeoutMs);
      return true;
    } catch {
      return false;
    }
  }

  /** The whole graph. */
  async getGraph(): Promise<Graph> {
    return getJson<Graph>(`${this.baseUrl}/api/repo/graph`, this.timeoutMs);
  }

  /**
   * Who calls this symbol?
   *
   * The count is what the CodeLens shows, and it MUST match the MCP
   * tool's answer — both read the same graph.
   */
  async getCallers(file: string, symbol: string): Promise<CallersResult> {
    const params = new URLSearchParams({ file, symbol });
    return getJson<CallersResult>(
      `${this.baseUrl}/api/analysis/callers?${params.toString()}`,
      this.timeoutMs,
    );
  }

  /** What depends on this file? */
  async getDependents(file: string): Promise<DependentsResult> {
    const params = new URLSearchParams({ file });
    return getJson<DependentsResult>(
      `${this.baseUrl}/api/analysis/dependents?${params.toString()}`,
      this.timeoutMs,
    );
  }

  /** Is the backend serving this repository? */
  async getRepoRoot(): Promise<string | null> {
    try {
      const status = await getJson<{ local_path?: string }>(
        `${this.baseUrl}/api/repo/status`,
        this.timeoutMs,
      );
      return status.local_path ?? null;
    } catch {
      return null;
    }
  }
}
