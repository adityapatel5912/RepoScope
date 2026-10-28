/**
 * metrics-hotspots.spec.ts
 * E2E tests for Phase 10: Churn, Hotspots, Bus Factor, Time Machine & Tracking/Incident Polish (V2.7).
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 10 — Hotspots, Bus Factor & Time Machine", () => {
  test("MH01 — verifies quadrant metrics, bus factor risk, historical compare, and incident triage", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    // Mock hotspots endpoint
    await page.route("**/api/metrics/hotspots*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          total_files: 15,
          quadrant_summary: {
            critical: 2,
            debt: 3,
            active: 4,
            stable: 6,
          },
          bus_factor_warnings: [
            {
              path: "backend/main.py",
              commits: 12,
              primary_author: "Alice",
              author_share: 0.9,
              bus_factor_risk: true,
            },
          ],
          files: [
            {
              path: "backend/main.py",
              commits: 12,
              churn_score: 25,
              complexity: 18,
              hotspot_score: 25.4,
              primary_author: "Alice",
              author_share: 0.9,
              bus_factor_risk: true,
              risk_level: "critical",
              quadrant: "critical",
            },
            {
              path: "backend/scaffolder.py",
              commits: 6,
              churn_score: 14,
              complexity: 9,
              hotspot_score: 10.5,
              primary_author: "Bob",
              author_share: 0.6,
              bus_factor_risk: false,
              risk_level: "medium",
              quadrant: "active",
            },
          ],
        }),
      });
    });

    // Mock compare endpoint
    await page.route("**/api/metrics/compare*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          ref_a: "HEAD~10",
          ref_b: "HEAD",
          summary: "5 files changed, 250 insertions(+), 30 deletions(-)",
          architectural_drift: [
            "2 new file(s) introduced (e.g. backend/chat_actions.py)",
            "Cross-cutting refactor spanning 5 files",
          ],
          modified_files: ["backend/main.py", "backend/onboarding.py", "frontend/src/App.tsx"],
          added_files: ["backend/chat_actions.py"],
          removed_files: [],
        }),
      });
    });

    // Mock incidents endpoint
    await page.route("**/api/tracking/incidents*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          total: 1,
          incidents: [
            {
              id: "inc-1",
              timestamp: new Date().toISOString(),
              event_type: "breaking_contract",
              category: "breaking_change",
              severity: "high",
              triage: "Verify client consumer contracts and run API integration tests.",
              details: { route: "/api/v1/tour" },
            },
          ],
        }),
      });
    });

    // Navigate to local test repo view
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    // Open Tracking tab in LeftPanel/SecurityPanel if not active
    const trackingBtn = page.getByRole("tab", { name: /tracking/i }).first();
    if (await trackingBtn.isVisible()) {
      await trackingBtn.click();
    }

    // Verify Tracking header and Hotspots view
    await expect(page.getByText(/repository tracking & git intelligence/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Critical").first()).toBeVisible();
    await expect(page.getByText("Debt").first()).toBeVisible();
    await expect(page.getByText("backend/main.py").first()).toBeVisible();

    // Verify Bus Factor Warning Pill is displayed
    await expect(page.getByText(/bus factor single-point-of-failure risk/i)).toBeVisible();

    // Switch to Time Machine view
    const timeMachineBtn = page.getByRole("button", { name: /time machine/i });
    await expect(timeMachineBtn).toBeVisible();
    await timeMachineBtn.click();

    // Verify compare summary and architectural drift
    await expect(page.getByText(/5 files changed/i)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/architectural drift/i)).toBeVisible();
    await expect(page.getByText(/new file\(s\) introduced/i)).toBeVisible();

    // Switch to Incidents view
    const incidentsBtn = page.getByRole("button", { name: /incidents/i });
    await expect(incidentsBtn).toBeVisible();
    await incidentsBtn.click();

    // Verify incident triage log
    await expect(page.getByText(/incident triage log/i)).toBeVisible();
    await expect(page.getByText(/breaking_contract/i)).toBeVisible();
    await expect(page.getByText(/verify client consumer contracts/i)).toBeVisible();

    assertNoErrors(errorCollector);
  });
});
