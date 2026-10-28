/**
 * capture-gallery-v3.spec.ts
 */

import { test, expect } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GALLERY_DIR = path.resolve(HERE, "../../../docs/screenshots/v2/gallery");
const BRAIN_DIR = "C:/Users/Admin/.gemini/antigravity/brain/a8e957cc-cfc4-4969-9c83-938efc95b952";

async function saveShot(locator: any, filename: string) {
  fs.mkdirSync(GALLERY_DIR, { recursive: true });
  fs.mkdirSync(BRAIN_DIR, { recursive: true });
  const repoPath = path.join(GALLERY_DIR, filename);
  const brainPath = path.join(BRAIN_DIR, filename);

  await locator.screenshot({ path: repoPath });
  fs.copyFileSync(repoPath, brainPath);
  console.log(`[Captured] ${filename} -> ${repoPath}`);
}

test.use({
  deviceScaleFactor: 2,
  viewport: { width: 1600, height: 1000 },
});

test.describe("RepoScope High-DPI Gallery Capture", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/repo/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          repo: "adityapatel5912/Verdict",
          owner: "adityapatel5912",
          name: "Verdict",
          node_count: 553,
          edge_count: 868,
          file_count: 154,
          readme_length: 14500,
          ready: true,
        }),
      });
    });

    await page.route("**/api/onboard", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            levels: [{ level: 1, title: "Entry Points", description: "Start here", files: [{ path: "main.py", why: "Entry point" }], quiz: [] }],
            good_first_issues: [],
          }),
        });
      } else {
        await route.continue();
      }
    });
  });

  test("03 - capture six-engine security suite focused vertical sidebar", async ({ page }) => {
    await page.route("**/api/security/scan", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          repo: "adityapatel5912/Verdict",
          scanned: { repo_files: true, pr: null, commits: 12, taint_flows: 1 },
          flags: [
            {
              type: "TAINT",
              engine: "cross_file_taint",
              cwe: "CWE-20",
              severity: "critical",
              file: "backend/main.py",
              line: 88,
              detail: "request.args in backend/main.py:88 propagates cross-file into sink subprocess.run() in backend/executor.py:14 via run_command()",
              suggestion: "Pass value through strict validation or shlex.quote() before passing to sink.",
              source: "request.args",
              source_line: 88,
              source_file: "backend/main.py",
              sink: "subprocess.run",
              sink_line: 14,
              sink_file: "backend/executor.py",
              patch_available: true,
              trace: {
                source_file: "backend/main.py",
                source_line: 88,
                source_label: "request.args",
                propagators: [
                  { file: "backend/main.py", line: 90, symbol: "run_command", via: "cmd" },
                  { file: "backend/executor.py", line: 12, symbol: "run_command", via: "command" },
                ],
                sink_file: "backend/executor.py",
                sink_line: 14,
                sink_label: "subprocess.run",
              },
            },
            {
              type: "SECRET",
              engine: "secrets_entropy",
              cwe: "CWE-798",
              severity: "high",
              file: "backend/config.py",
              line: 24,
              detail: "Hardcoded secret detected (Shannon entropy H >= 4.2). Key value is masked: <redacted>.",
              suggestion: "Store secrets in environment variables.",
              patch_available: false,
            },
            {
              type: "CVE",
              engine: "dependency_cve",
              cwe: "CWE-1395",
              severity: "high",
              file: "requirements.txt",
              line: 12,
              detail: "urllib3==1.26.4 is vulnerable to CVE-2021-33503 (ReDoS in URL authority parsing).",
              suggestion: "Upgrade urllib3 >= 1.26.5.",
              patch_available: false,
            },
            {
              type: "INJECTION",
              engine: "injection_sinks",
              cwe: "CWE-89",
              severity: "high",
              file: "backend/db.py",
              line: 45,
              detail: "Raw SQL query string interpolation into cursor.execute().",
              suggestion: "Use parameterized queries with prepared statements.",
              patch_available: true,
            },
            {
              type: "CONFIG",
              engine: "insecure_config",
              cwe: "CWE-942",
              severity: "medium",
              file: "backend/server.py",
              line: 18,
              detail: "CORS middleware configured with wildcard allow_origins=['*'].",
              suggestion: "Explicitly allow trusted origins.",
              patch_available: false,
            },
            {
              type: "AUTH_BYPASS",
              engine: "auth_bypass",
              cwe: "CWE-306",
              severity: "low",
              file: "backend/routes/export.py",
              line: 32,
              detail: "State-mutating POST route lacking authentication guard dependency.",
              suggestion: "Add Depends(get_current_user) to endpoint parameters.",
              patch_available: false,
            },
          ],
          total_flags: 6,
          summary: {
            SECRET: 1,
            BREAKING: 0,
            CVE: 1,
            TAINT: 1,
            INJECTION: 1,
            CONFIG: 1,
            AUTH_BYPASS: 1,
            critical: 1,
            high: 3,
            medium: 1,
            low: 1,
            by_engine: {
              cross_file_taint: 1,
              secrets_entropy: 1,
              dependency_cve: 1,
              injection_sinks: 1,
              insecure_config: 1,
              auth_bypass: 1,
            },
          },
        }),
      });
    });

    await page.route("**/api/security/patch", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          diff: "--- a/backend/main.py\n+++ b/backend/main.py\n@@ -88,1 +88,2 @@\n-    cmd = request.args.get('cmd')\n+    import shlex\n+    cmd = shlex.quote(request.args.get('cmd', ''))",
          verified: true,
          syntax_valid: true,
        }),
      });
    });

    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    const trackTab = page.getByRole("tab", { name: /^track$/i });
    if (await trackTab.isVisible()) {
      await trackTab.click();
    }

    const secTab = page.getByRole("tab", { name: /security suite/i });
    await expect(secTab).toBeVisible({ timeout: 15000 });
    await secTab.click();

    const scanBtn = page.getByRole("button", { name: /run 6-engine audit|re-scan/i }).first();
    await expect(scanBtn).toBeVisible({ timeout: 5000 });
    await scanBtn.click();

    await expect(page.getByText(/request\.args in backend\/main\.py:88/i)).toBeVisible({ timeout: 10000 });

    const patchBtn = page.getByRole("button", { name: /view suggested patch/i }).first();
    if (await patchBtn.isVisible()) {
      await patchBtn.click();
    }

    await expect(page.getByText(/ast syntax verified/i)).toBeVisible({ timeout: 5000 });

    const sidebar = page.locator("aside, div.card:has-text('Security Suite')").first();
    await expect(sidebar).toBeVisible();
    await saveShot(sidebar, "security_suite_panel.png");
  });

  test("09 - capture reverse prompt modal feature slice card", async ({ page }) => {
    await page.route("**/api/repo/reverse-prompt", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          mode: "feature",
          prompt: "# Feature Slice: `main.py`\n\n## 1. Target Details\n- **ID**: `file:backend/main.py`\n- **Kind**: `file`\n- **Role**: `entrypoint`\n\n## 2. 2-Hop Interface Closure (3 nodes, 2 edges)\nOnly dependencies and dependents within 2 hops of the target feature are included:\n\n### Files (3)\n- `backend/main.py` (entrypoint)\n- `backend/routes/auth.py` (router)\n- `backend/services/billing.py` (service)\n\n## 3. Interface Edges & Contracts\n| Source | Target | Edge Type |\n|---|---|---|\n| `auth.py` | `main.py` | imports |\n| `billing.py` | `auth.py` | calls |\n\n## 4. Implementation Guidelines\n1. Implement or modify `main.py` satisfying all interfaces above.\n2. Maintain deterministic compatibility with direct callers and callees.\n3. Do not modify files outside the 2-hop closure.",
          tokens: 450,
          files: [{ path: "prompt.md", content: "", tokens: 450 }],
        }),
      });
    });

    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    const promptBtn = page.getByRole("button", { name: /build prompt/i }).first();
    await expect(promptBtn).toBeVisible({ timeout: 25000 });
    await promptBtn.click();

    const modalCard = page.locator("[data-testid='reverse-prompt-modal'] > div.card").first();
    await expect(modalCard).toBeVisible({ timeout: 10000 });

    const featureTab = modalCard.locator("[data-testid='mode-tab-feature'], button:has-text('Feature Slice')").first();
    if (await featureTab.isVisible()) {
      await featureTab.click();
    }

    const textarea = modalCard.locator("[data-testid='reverse-prompt-textarea']").first();
    await expect(textarea).toBeVisible({ timeout: 10000 });
    await saveShot(modalCard, "rp_feature_mode.png");
  });

  test("10 - capture scaffold modal starter kit card", async ({ page }) => {
    await page.route("**/api/scaffold", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          project_type: "clean-architecture-python",
          file_tree: [
            "src/core/entities.py",
            "src/core/use_cases.py",
            "src/adapters/api.py",
            "src/adapters/db.py",
            "main.py",
            "README.md",
          ],
          files: [
            {
              path: "main.py",
              content: "from fastapi import FastAPI\nfrom src.adapters.api import router\n\napp = FastAPI(title='Verdict Clean Arch API')\napp.include_router(router)\n\n@app.get('/health')\ndef health():\n    return {'status': 'healthy', 'arch': 'clean'}\n",
              purpose: "Clean architecture composition root and entry point",
              language: "python",
            },
            {
              path: "README.md",
              content: "# Clean Architecture Python Starter\nGenerated by RepoScope Scaffolder.",
              purpose: "Project documentation",
              language: "markdown",
            },
          ],
          entry_files: ["main.py"],
          top_nodes: ["main.py", "src/core/entities.py"],
          warnings: [],
          token_estimate: 2450,
          bootstrap_command: "npx reposcope-mcp scaffold --from adityapatel5912/Verdict --out ./scaffold-app",
        }),
      });
    });

    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    const scaffoldBtn = page.getByRole("button", { name: /generate scaffold/i });
    await expect(scaffoldBtn).toBeVisible({ timeout: 10000 });
    await scaffoldBtn.click();

    const modalCard = page.locator("div[role='dialog'][aria-label='Starter scaffold'] > div.card").first();
    await expect(modalCard).toBeVisible({ timeout: 5000 });
    await expect(modalCard.getByText("clean-architecture-python")).toBeVisible();
    await saveShot(modalCard, "scaffold_modal_code.png");
  });

  test("11 - capture graph interactive view", async ({ page }) => {
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    const graphTab = page.getByRole("tab", { name: /graph/i }).first();
    await expect(graphTab).toBeVisible({ timeout: 15000 });
    await graphTab.click();

    await expect(page.getByRole("heading", { name: /architecture/i })).toBeVisible({ timeout: 15000 });

    const collapseChatBtn = page.locator("button[aria-label='Collapse chat'], button[title='Collapse chat']").first();
    if (await collapseChatBtn.isVisible()) {
      await collapseChatBtn.click();
    }

    await page.waitForTimeout(3000);

    const graphSection = page.locator("main section").first();
    await expect(graphSection).toBeVisible();
    await saveShot(graphSection, "graph_interactive_view.png");
  });

  test("12 - capture student mode active view", async ({ page }) => {
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    const studentBtn = page.locator("button:has-text('Student')").first();
    await expect(studentBtn).toBeVisible({ timeout: 15000 });
    await studentBtn.click();

    await expect(studentBtn).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText(/student onboarding/i)).toBeVisible({ timeout: 10000 });

    await page.waitForTimeout(1500);

    await page.screenshot({ path: path.join(GALLERY_DIR, "student_mode_active.png") });
    fs.copyFileSync(
      path.join(GALLERY_DIR, "student_mode_active.png"),
      path.join(BRAIN_DIR, "student_mode_active.png")
    );
    console.log("[Captured] student_mode_active.png");
  });

  test("13 - capture chat verified citations hover view", async ({ page }) => {
    await page.route("**/api/chat/stream", async (route) => {
      const sseBody = [
        'event: context',
        'data: {"nodes":[],"edges":[],"graph_summary":"test","file_count":1,"node_count":1,"edge_count":0,"readme_length":0}',
        '',
        'event: token',
        'data: {"t":"Architecture verified via AST analysis: Entry point initializes routes in `backend/main.py:20`. Note that `fake/missing.py:99` was not found in graph."}',
        '',
        'event: citations',
        'data: {"type":"citations","citations":[{"raw":"backend/main.py:20","path":"backend/main.py","start_line":20,"end_line":25,"symbol":"app_startup","node_id":"func:backend/main.py:app_startup","verified":true,"confidence":1.0,"reason":"exact AST symbol definition","preview":"@app.on_event(\\"startup\\")\\ndef app_startup():\\n    init_db()\\n    register_routes()"},{"raw":"fake/missing.py:99","path":"fake/missing.py","start_line":99,"end_line":99,"symbol":null,"node_id":null,"verified":false,"confidence":0.0,"reason":"file not found in repository graph","preview":""}]}',
        '',
        'event: done',
        'data: {"ok":true,"req_id":"test1234"}',
        '',
      ].join("\n");

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: { "Cache-Control": "no-cache", "Connection": "keep-alive" },
        body: sseBody,
      });
    });

    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    const chatInput = page.locator("textarea[placeholder*='Ask anything'], textarea").first();
    await expect(chatInput).toBeVisible({ timeout: 15000 });
    await chatInput.fill("Verify the backend entrypoint");
    await page.keyboard.press("Enter");

    const verifiedPill = page.locator('[data-testid="citation-pill"][data-verified="true"]').first();
    await expect(verifiedPill).toBeVisible({ timeout: 15000 });
    await verifiedPill.hover();

    const tooltip = page.locator('[data-testid="citation-hover-preview"]');
    await expect(tooltip).toBeVisible({ timeout: 5000 });

    const chatSection = page.locator("section:has([data-testid='citation-pill'])").first();
    await expect(chatSection).toBeVisible();
    await saveShot(chatSection, "chat_verified_citations.png");
  });

  test("14 - capture agent harness configurator modal card", async ({ page }) => {
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    const harnessBtn = page.locator("button[data-testid='open-harness'], button:has-text('Connect AI agent')").first();
    await expect(harnessBtn).toBeVisible({ timeout: 15000 });
    await harnessBtn.click();

    const modalCard = page.locator("[data-testid='harness-modal-panel']").first();
    await expect(modalCard).toBeVisible({ timeout: 10000 });

    const claudeItem = modalCard.locator("[data-testid='harness-agent-claude']").first();
    if (await claudeItem.isVisible()) {
      await claudeItem.click();
    }

    await page.waitForTimeout(1000);
    await saveShot(modalCard, "agent_harness_modal.png");
  });
});
