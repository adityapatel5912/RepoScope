/**
 * pr-impact.spec.ts
 * E2E tests for Phase 11: Symbol-Level PR Impact (V2.7)
 * AST symbol-level diffing, API route contract changes, cross-stack callers,
 * test coverage gaps, and SARIF 2.1.0 export.
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 11 — Symbol-Level PR Impact", () => {
  test("PR01 — renders symbol contract breaks, consumers, test gaps, and SARIF export", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    // Mock PR impact endpoint with rich symbol contract breaks and test gaps
    await page.route("**/api/impact/pr", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          pr_number: 42,
          pr_title: "Refactor User Service & Endpoints",
          risk_score: 8,
          risk_level: "critical",
          affected_files: [
            {
              file: "backend/services/user.py",
              status: "modified",
              additions: 14,
              deletions: 5,
              in_graph: true,
              direct: 3,
              transitive: 6,
            },
            {
              file: "backend/routes/auth.py",
              status: "modified",
              additions: 8,
              deletions: 12,
              in_graph: true,
              direct: 2,
              transitive: 4,
            },
          ],
          files_analyzed: 2,
          impacted_total: 9,
          direct_total: 3,
          transitive_total: 6,
          suggested_tests: ["tests/test_user.py", "tests/test_auth.py"],
          symbol_findings: [
            {
              kind: "altered-route",
              symbol: "GET /api/v1/users",
              file: "backend/routes/auth.py",
              line: 45,
              severity: "BREAKING",
              detail: "API Route `GET /api/v1/users` was altered to `GET /api/v2/users`",
              consumers: ["frontend/src/api/client.ts", "cli/user_cmd.py"],
            },
            {
              kind: "retyped-parameter",
              symbol: "update_user",
              file: "backend/services/user.py",
              line: 112,
              severity: "BREAKING",
              detail: "Parameter `user_id` of `update_user` changed type: `int` -> `UUID`",
              consumers: ["backend/routes/auth.py"],
            },
          ],
          test_gaps: [
            {
              symbol: "update_user",
              file: "backend/services/user.py",
              line: 112,
              detail: "Modified symbol `update_user` has 0 incoming test edges in the dependency graph.",
            },
          ],
          sarif_doc: {
            $schema: "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            version: "2.1.0",
            runs: [],
          },
          comment: "## 🔴 RepoScope PR Impact Report — #42\n\n**Risk score: `8/10` (critical)**\n\n### Breaking Changes\n- `GET /api/v1/users` route altered\n- `update_user` parameter retyped",
        }),
      });
    });

    // Navigate to local test repo view
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    // Locate PR number input inside ImpactPanel and fill with "42"
    const prInput = page.getByPlaceholder("PR #");
    await expect(prInput).toBeVisible({ timeout: 15000 });
    await prInput.fill("42");

    // Click "Preview Comment" / analyze button
    const previewBtn = page.getByRole("button", { name: /preview comment/i }).first();
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();

    // Verify Risk badge
    await expect(page.getByText(/pr #42 · critical · 8\/10/i)).toBeVisible({ timeout: 10000 });

    // Verify Contract Breaking Changes section
    await expect(page.getByText(/contract breaking changes/i)).toBeVisible();
    await expect(page.getByText(/GET \/api\/v1\/users/).first()).toBeVisible();
    await expect(page.getByText(/update_user/).first()).toBeVisible();

    // Verify consumers are displayed
    await expect(page.getByText(/client\.ts/).first()).toBeVisible();
    await expect(page.getByText(/auth\.py/).first()).toBeVisible();

    // Verify Test Gaps warning
    await expect(page.getByText(/coverage gaps/i)).toBeVisible();

    // Verify buttons: Copy comment and Export SARIF
    await expect(page.getByRole("button", { name: /copy comment/i })).toBeVisible();
    const sarifBtn = page.getByRole("button", { name: /export sarif/i });
    await expect(sarifBtn).toBeVisible();

    // Capture visual verification screenshot
    await page.screenshot({
      path: "C:/Users/Admin/.gemini/antigravity/brain/a8e957cc-cfc4-4969-9c83-938efc95b952/pr_impact_symbols_panel.png",
      fullPage: false,
    });

    assertNoErrors(errorCollector);
  });
});
