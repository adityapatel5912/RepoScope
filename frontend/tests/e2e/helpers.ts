/**
 * helpers.ts
 * Shared helpers for RepoScope's browser-QA journeys.
 *
 * Part III of docs/ROADMAP_V2.md, Section 18.3.
 *
 * The important piece is `attachErrorCollector`. A journey that renders
 * correctly while the console fills with React key warnings, unhandled
 * rejections, 404 assets, and CORS failures is NOT a passing journey —
 * that is exactly the class of defect the gitignored manual audit found
 * (SVG NaN attributes, /api/tour/generate 404s).
 */
import { expect, type Page, type Request } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

// The frontend is an ES module package ("type": "module"), so __dirname is
// not defined. Derive it from the module URL instead.
const HERE = path.dirname(fileURLToPath(import.meta.url));

/** Where committed journey screenshots live. */
export const SCREENSHOT_ROOT = path.resolve(HERE, "../../../docs/screenshots/v2");

export interface CollectedError {
  kind: "console" | "pageerror" | "request" | "response";
  text: string;
  url?: string;
}

/**
 * Reviewed allow-list of benign console output.
 *
 * Rule R-QA5: every entry MUST carry a reason. An unexplained console
 * error fails the build — that is the whole point of the gate.
 */
export const WHITELIST: Array<{ pattern: RegExp; reason: string }> = [
  {
    // React DevTools nag — emitted by React itself in development.
    pattern: /Download the React DevTools/i,
    reason: "React DevTools informational message emitted by React in dev mode.",
  },
  {
    // React 18 StrictMode double-render advisory.
    pattern: /ReactDOMTestUtils\.act|deprecated.*act\(/i,
    reason: "React 18 act() deprecation notice from the test renderer.",
  },
  {
    // Vite HMR websocket chatter during dev.
    pattern: /\[vite\] (connect|connected)/i,
    reason: "Vite dev-server HMR websocket messages.",
  },
];

/**
 * Attach console / page-error / failed-request collectors to a page.
 *
 * Call BEFORE navigating so nothing is missed during the first paint.
 */
export function attachErrorCollector(page: Page): CollectedError[] {
  const errors: CollectedError[] = [];

  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (isWhitelisted(text)) return;
    errors.push({ kind: "console", text });
  });

  page.on("pageerror", (error) => {
    const text = error?.message ?? String(error);
    if (isWhitelisted(text)) return;
    errors.push({ kind: "pageerror", text });
  });

  page.on("requestfailed", (request: Request) => {
    const failure = request.failure();
    errors.push({
      kind: "request",
      text: `${request.method()} ${request.url()} — ${failure?.errorText ?? "failed"}`,
      url: request.url(),
    });
  });

  page.on("response", (response) => {
    const status = response.status();
    if (status < 400) return;
    const url = response.url();
    // The backend intentionally 404s a deliberately-missing repository.
    if (isWhitelistedUrl(url)) return;
    errors.push({
      kind: "response",
      text: `HTTP ${status} ${response.request().method()} ${url}`,
      url,
    });
  });

  return errors;
}

function isWhitelisted(text: string): boolean {
  return WHITELIST.some((entry) => entry.pattern.test(text));
}

function isWhitelistedUrl(url: string): boolean {
  // The backend returns 404 for "repository not found" — that is a
  // deliberate, handled condition, not a defect.
  if (url.includes("/api/repo/load") || url.includes("/api/repo/file")) {
    return true;
  }
  return false;
}

/**
 * Assert that no un-whitelisted error was collected.
 *
 * Rule R-QA1: zero console errors. Rule R-QA2: zero unexpected HTTP
 * failures.
 */
export function assertNoErrors(errors: CollectedError[], context = ""): void {
  if (errors.length === 0) return;
  const detail = errors
    .map((e) => `  [${e.kind}] ${e.text}${e.url ? ` (${e.url})` : ""}`)
    .join("\n");
  throw new Error(
    `Expected zero console/network errors${context ? ` in ${context}` : ""}, ` +
      `but found ${errors.length}:\n${detail}`,
  );
}

/**
 * Capture a journey screenshot into the committed evidence directory.
 *
 * Rule R-QA3: docs/screenshots/v2/ is deliberately NOT gitignored — the
 * whole point is that the evidence survives. (The old .playwright-mcp/
 * scratch directory is ignored, and its evidence was lost.)
 */
export async function captureJourney(
  page: Page,
  journeyId: string,
  name: string,
): Promise<string> {
  const dir = path.join(SCREENSHOT_ROOT, journeyId);
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  return file;
}

/**
 * Assert the graph canvas rendered actual nodes rather than staying blank.
 *
 * Rule R-QA1 in practice: a blank canvas is the classic P0 demo-killer,
 * and it produces no console error, so it needs its own assertion.
 */
export async function expectGraphHasNodes(page: Page): Promise<number> {
  const nodes = page.locator(".react-flow__node");
  await expect(nodes.first()).toBeVisible({ timeout: 30_000 });
  const count = await nodes.count();
  expect(count, "the graph rendered zero nodes").toBeGreaterThan(0);
  return count;
}

/** Wait for the backend to be reachable. */
export async function waitForBackend(baseUrl: string): Promise<void> {
  const response = await fetch(`${baseUrl}/api/health`);
  if (!response.ok) {
    throw new Error(`Backend health check failed: HTTP ${response.status}`);
  }
}
