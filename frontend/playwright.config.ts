/**
 * playwright.config.ts
 * Browser-QA configuration for RepoScope.
 *
 * Part III of docs/ROADMAP_V2.md, Section 18.
 *
 * The gate this config exists for: unit tests prove functions work, but
 * only a real browser proves the PRODUCT works. The prior manual Playwright
 * audit (in .playwright-mcp/, gitignored) found bugs no unit test can
 * catch — SVG NaN attributes, /api/* 404s, a password field outside a
 * form — and left no protection against regression.
 *
 * Server wiring:
 *   backend  -> http://127.0.0.1:8010   (uvicorn, REPOSCOPE_QA=1)
 *   frontend -> http://127.0.0.1:5173   (vite dev)
 *
 * REPOSCOPE_QA=1 makes the backend hermetic: no GitHub calls, no LLM
 * provider calls, isolated state, fixed seed. A QA run that depends on the
 * network fails for the wrong reason.
 */
import { defineConfig, devices } from "@playwright/test";

const BACKEND_PORT = process.env.REPOSCOPE_QA_BACKEND_PORT ?? "8010";
// The QA harness uses its own frontend port so it never collides with a
// developer's dev server on :5173.
const FRONTEND_PORT = process.env.REPOSCOPE_QA_FRONTEND_PORT ?? "5183";
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./test-results",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ["list"],
    ["json", { outputFile: "../qa-report/results.json" }],
    ["html", { outputFolder: "../qa-report/html", open: "never" }],
  ],

  use: {
    baseURL: FRONTEND_URL,
    // The repo documents its screenshots at 1600x900 (16:9).
    viewport: { width: 1600, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 900 } },
    },
  ],

  webServer: [
    {
      command: "python -m uvicorn main:app --host 127.0.0.1 --port " + BACKEND_PORT + " --log-level warning",
      cwd: "../backend",
      url: `${BACKEND_URL}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 90_000,
      env: { REPOSCOPE_QA: "1", PYTHONPATH: "../backend" },
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port " + FRONTEND_PORT,
      cwd: ".",
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 90_000,
      // The Vite dev server proxies /api to :8000 by default. Point it at
      // the QA backend so the journey talks to the hermetic instance.
      env: { REPOSCOPE_QA_BACKEND_URL: BACKEND_URL },
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
