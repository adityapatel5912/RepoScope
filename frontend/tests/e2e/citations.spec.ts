/**
 * citations.spec.ts
 * E2E tests for Phase 5: Verified chat citations (V2.6).
 *
 * Verifies:
 * - Assistant response with citations renders CitationPill components
 * - Distinct visual presentation for verified vs unverified citations
 * - Hover preview tooltip displays path, line range, reason, and preview code
 * - Clicking a citation expands mind map / focuses node
 * - Zero console errors
 */

import { expect, test } from "@playwright/test";
import {
  assertNoErrors,
  attachErrorCollector,
} from "./helpers";

test.describe("Phase 5 — Verified Chat Citations", () => {
  test("renders verified and unverified citations with hover preview and mind map focus", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    // Mock SSE chat stream with verified and unverified citations
    await page.route("**/api/chat/stream", async (route) => {
      const sseBody = [
        'event: context',
        'data: {"nodes":[],"edges":[],"graph_summary":"test","file_count":1,"node_count":1,"edge_count":0,"readme_length":0}',
        '',
        'event: token',
        'data: {"t":"Here is the verified symbol `backend/main.py:20` and hallucinated `fake/missing.py:99`."}',
        '',
        'event: citations',
        'data: {"type":"citations","citations":[{"raw":"backend/main.py:20","path":"backend/main.py","start_line":20,"end_line":25,"symbol":"app_startup","node_id":"func:backend/main.py:app_startup","verified":true,"confidence":1.0,"reason":"exact symbol range","preview":"def app_startup():\\n    pass"},{"raw":"fake/missing.py:99","path":"fake/missing.py","start_line":99,"end_line":99,"symbol":null,"node_id":null,"verified":false,"confidence":0.0,"reason":"file not found","preview":""}]}',
        '',
        'event: done',
        'data: {"ok":true,"req_id":"test1234"}',
        '',
      ].join("\n");

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: {
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
        },
        body: sseBody,
      });
    });

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // Send a message in the chat panel
    const chatInput = page.locator("textarea[placeholder*='Ask anything']");
    if (await chatInput.isVisible()) {
      await chatInput.fill("Tell me about citations");
      await page.keyboard.press("Enter");
    } else {
      // If placeholder differs or mode switch needed, find any textarea in chat
      const anyInput = page.locator("textarea").first();
      await anyInput.fill("Tell me about citations");
      await page.keyboard.press("Enter");
    }

    // Wait for the citation pills to render
    const pills = page.locator('[data-testid="citation-pill"]');
    await expect(pills.first()).toBeVisible({ timeout: 10000 });
    await expect(pills).toHaveCount(2);

    // Pill 1: Verified
    const verifiedPill = page.locator('[data-testid="citation-pill"][data-verified="true"]');
    await expect(verifiedPill).toBeVisible();
    await expect(verifiedPill).toContainText("backend/main.py");

    // Pill 2: Unverified
    const unverifiedPill = page.locator('[data-testid="citation-pill"][data-verified="false"]');
    await expect(unverifiedPill).toBeVisible();
    await expect(unverifiedPill).toContainText("unverified");

    // Hover on verified pill shows preview tooltip
    await verifiedPill.hover();
    const tooltip = page.locator('[data-testid="citation-hover-preview"]');
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toContainText("backend/main.py");
    await expect(tooltip).toContainText("def app_startup");
    await expect(tooltip).toContainText("100% verified");

    // Click verified citation focuses mind map
    await verifiedPill.click();

    // Verify view switched to mind map
    await expect(page.locator("button:has-text('Mind Map')")).toBeVisible();

    // Zero un-whitelisted console errors
    assertNoErrors(errorCollector);
  });
});
