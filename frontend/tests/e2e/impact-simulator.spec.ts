/**
 * impact-simulator.spec.ts
 * E2E tests for Phase 12: Explainable Impact Simulator (V2.7)
 * 3-hop downstream dependency tree, mathematical score breakdown,
 * API boundaries, test gaps, and canvas integration.
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 12 — Explainable Impact Simulator", () => {
  test("IS01 — renders 3-hop dependency tree, score breakdown, and API boundaries", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    // Mock impact analyze endpoint with full 3-hop simulation data
    await page.route("**/api/impact/analyze", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          target: { id: "file:backend/main.py", label: "main.py", file: "backend/main.py", type: "file" },
          max_depth: 3,
          direct_impacts: [
            { id: "file:backend/routes/auth.py", label: "auth.py", file: "backend/routes/auth.py", type: "file" },
            { id: "file:backend/routes/user.py", label: "user.py", file: "backend/routes/user.py", type: "file" },
          ],
          transitive_impacts: [
            { id: "file:backend/services/billing.py", label: "billing.py", file: "backend/services/billing.py", type: "file" },
            { id: "file:frontend/src/api/client.ts", label: "client.ts", file: "frontend/src/api/client.ts", type: "file" },
          ],
          hops: [
            {
              hop: 1,
              label: "Direct Impacts (Hop 1)",
              nodes: [
                { id: "file:backend/routes/auth.py", label: "auth.py", file: "backend/routes/auth.py", type: "file" },
                { id: "file:backend/routes/user.py", label: "user.py", file: "backend/routes/user.py", type: "file" },
              ],
              edges: [
                { source: "file:backend/routes/auth.py", target: "file:backend/main.py", type: "imports" },
              ],
            },
            {
              hop: 2,
              label: "Secondary Dependents (Hop 2)",
              nodes: [
                { id: "file:backend/services/billing.py", label: "billing.py", file: "backend/services/billing.py", type: "file" },
              ],
              edges: [
                { source: "file:backend/services/billing.py", target: "file:backend/routes/user.py", type: "imports" },
              ],
            },
            {
              hop: 3,
              label: "Deep Transitive (Hop 3)",
              nodes: [
                { id: "file:frontend/src/api/client.ts", label: "client.ts", file: "frontend/src/api/client.ts", type: "file" },
              ],
              edges: [
                { source: "file:frontend/src/api/client.ts", target: "file:backend/services/billing.py", type: "api_calls" },
              ],
            },
          ],
          score_breakdown: {
            direct_callers: 2,
            transitive_callers: 2,
            api_boundaries: 1,
            test_gaps: 1,
            raw_score: 15.0,
            normalized_score: 7,
          },
          api_boundaries: [
            { id: "file:backend/routes/auth.py", label: "POST /api/v1/auth/login", file: "backend/routes/auth.py", type: "api_boundary" },
          ],
          test_gaps: [
            { id: "file:backend/services/billing.py", label: "billing.py", file: "backend/services/billing.py", detail: "Downstream dependency billing.py lacks direct test coverage." },
          ],
          explanation_paths: [
            {
              target: "client.ts",
              hop: 3,
              path: ["main.py", "routes/user.py", "services/billing.py", "client.ts"],
              reason: "Transitively imported via billing.py -> client.ts",
            },
          ],
          risk_score: 7,
          risk_level: "high",
          suggested_tests: ["tests/test_auth.py", "tests/test_main.py"],
          total_impacted: 4,
          narrative: "Modifying main.py triggers a high risk blast radius (7/10) with 2 direct routes and 2 transitive dependents spanning 3 hops.",
        }),
      });
    });

    // Navigate to local test repo view
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    // Locate target input inside What-If Impact panel
    const targetInput = page.getByPlaceholder(/process_payment/i).first();
    await expect(targetInput).toBeVisible({ timeout: 15000 });
    await targetInput.fill("main.py");

    // Click "Analyze"
    const analyzeBtn = page.getByRole("button", { name: /^analyze$/i }).first();
    await expect(analyzeBtn).toBeVisible();
    await analyzeBtn.click();

    // Verify Score Breakdown is visible
    await expect(page.getByText(/score breakdown/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/15 pts/i)).toBeVisible();
    await expect(page.getByText(/Direct \(×3\)/i)).toBeVisible();

    // Verify 3-Hop Blast Radius Tree
    await expect(page.getByText(/3-hop blast radius tree/i)).toBeVisible();
    await expect(page.getByText(/Direct Impacts \(Hop 1\)/i)).toBeVisible();
    await expect(page.getByText(/Secondary Dependents \(Hop 2\)/i)).toBeVisible();
    await expect(page.getByText(/Deep Transitive \(Hop 3\)/i)).toBeVisible();

    // Verify node item in tree and click to focus
    const authNode = page.getByText(/auth\.py/).first();
    await expect(authNode).toBeVisible();
    await authNode.click();

    // Verify API Boundaries section
    await expect(page.getByText(/API Boundaries Exposed/i)).toBeVisible();
    await expect(page.getByText(/POST \/api\/v1\/auth\/login/i)).toBeVisible();

    // Verify Test Gaps alert
    await expect(page.getByText(/Downstream Test Gaps/i)).toBeVisible();

    // Capture visual shot of the Explainable Impact Simulator
    await page.screenshot({
      path: "C:/Users/Admin/.gemini/antigravity/brain/a8e957cc-cfc4-4969-9c83-938efc95b952/impact_simulator_panel.png",
      fullPage: false,
    });

    assertNoErrors(errorCollector);
  });
});
