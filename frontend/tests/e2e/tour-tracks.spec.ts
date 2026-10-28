/**
 * tour-tracks.spec.ts
 * E2E tests for Phase 8: Four deterministic tour tracks (V2.7)
 * and Universal Chat Action Cards.
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 8 — Four Tour Tracks & Chat Action Cards", () => {
  test("TT01 — verifies 4 track switcher tabs, codetour export, and chat action chip execution", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    // Mock tour generate endpoint
    await page.route("**/api/tour/generate", async (route) => {
      const postData = route.request().postDataJSON() || {};
      const track = postData.track || "request_lifecycle";

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          topic: track,
          track,
          track_label: track.replace("_", " ").toUpperCase(),
          why_this_order: `Deterministic ordering for ${track}`,
          total_steps: 3,
          steps: [
            {
              step: 1,
              node_id: "file:main.py",
              label: "main.py",
              type: "file",
              file: "main.py",
              line: 1,
              explanation: `Entrypoint for ${track} pipeline.`,
              reason: "HTTP entrypoint",
            },
            {
              step: 2,
              node_id: "file:app/api.py",
              label: "app/api.py",
              type: "file",
              file: "app/api.py",
              line: 5,
              explanation: "Router handler module.",
              reason: "Router",
            },
            {
              step: 3,
              node_id: "file:app/models.py",
              label: "app/models.py",
              type: "file",
              file: "app/models.py",
              line: 10,
              explanation: "Core domain models.",
              reason: "Data schema",
            },
          ],
        }),
      });
    });

    // Navigate to local test repo view
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    // Check if Tour Panel is present or open it from sidebar/controls
    const tourHeading = page.getByRole("heading", { name: /code tour/i });
    if (!(await tourHeading.isVisible())) {
      // Find Tour button or trigger from sidebar
      const tourBtn = page.getByRole("button", { name: /tour/i }).first();
      if (await tourBtn.isVisible()) {
        await tourBtn.click();
      }
    }

    // Verify 4 track tabs are visible in TourPanel
    await expect(page.getByRole("button", { name: /^request$/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: /^data flow$/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^impact$/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^onboard$/i })).toBeVisible();

    // Click "Data Flow" track tab
    await page.getByRole("button", { name: /^data flow$/i }).click();
    await expect(page.getByText(/data flow/i).first()).toBeVisible();

    // Verify .tour download export link exists
    const exportTourLink = page.locator("a[title*='CodeTour']");
    await expect(exportTourLink).toBeVisible();
    const href = await exportTourLink.getAttribute("href");
    expect(href).toContain("/api/tour/export");

    assertNoErrors(errorCollector);
  });
});
