/**
 * mindmap.spec.ts
 * Browser-QA journeys for the vertical six-pillar mind map (Phase 2).
 *
 * Verifies:
 * - Default view is the dependency network
 * - Switching to Mind Map renders the six pillars and hides the dependency canvas
 * - Hierarchical expand/collapse: pillar → folder → file → symbol
 * - Search for helpers.py auto-focuses the result and mirrors in outline
 * - Layout orientation toggle (TB ⇄ LR) with zero window overflow at 1600x900 and 1280x800
 * - Zero un-whitelisted console errors
 */

import { expect, test } from "@playwright/test";
import {
  assertNoErrors,
  attachErrorCollector,
  captureJourney,
  expectGraphHasNodes,
} from "./helpers";

const BACKEND_URL =
  process.env.REPOSCOPE_QA_BACKEND_URL ?? "http://127.0.0.1:8010";

async function loadFixture(
  name = "multilang",
  options: { copy?: boolean; watch?: boolean } = {},
): Promise<{ copy: string | null }> {
  const params = new URLSearchParams({ name });
  if (options.copy) params.set("copy", "true");
  if (options.watch) params.set("watch", "true");

  const response = await fetch(
    `${BACKEND_URL}/api/qa/load-fixture?${params.toString()}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to load fixture '${name}': HTTP ${response.status} ` +
        `${await response.text()}`,
    );
  }
  const payload = (await response.json()) as { copy?: string | null };
  return { copy: payload.copy ?? null };
}

test.describe("Mind Map QA journeys", () => {
  test("MM01 — vertical six-pillar mind map journey with multilang fixture", async ({
    page,
  }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");

    // 1. Assert default view is the dependency network
    const initialNodes = await expectGraphHasNodes(page);
    expect(initialNodes).toBeGreaterThan(0);

    // 2. Switch to Mind Map view
    const mindmapTab = page.locator('[data-testid="view-mode-mindmap"]');
    await expect(mindmapTab).toBeVisible();
    await mindmapTab.click();

    // 3. Assert the dependency canvas is hidden and mind map is visible
    await expect(page.locator(".react-flow")).toBeHidden();
    await expect(page.locator('[data-testid="mindmap-view"]')).toBeVisible();

    // 4. Assert the six pillars are visible
    const backendPillar = page.locator('[data-node-id="pillar:backend"]');
    const frontendPillar = page.locator('[data-node-id="pillar:frontend"]');
    const dataPillar = page.locator('[data-node-id="pillar:data"]');
    const infraPillar = page.locator('[data-node-id="pillar:infrastructure"]');
    const testsPillar = page.locator('[data-node-id="pillar:tests"]');
    const docsPillar = page.locator('[data-node-id="pillar:docs"]');

    await expect(backendPillar).toBeVisible();
    await expect(frontendPillar).toBeVisible();
    await expect(dataPillar).toBeVisible();
    await expect(infraPillar).toBeVisible();
    await expect(testsPillar).toBeVisible();
    await expect(docsPillar).toBeVisible();

    // 5. Expand backend pillar (collapse then re-expand to test interactive toggle)
    const helpersFile = page.locator('[data-node-id="file:helpers.py"]');
    const collapseBackendBtn = backendPillar.getByRole("button", { name: /collapse/i });
    if (await collapseBackendBtn.isVisible()) {
      await collapseBackendBtn.click();
      await expect(helpersFile).toBeHidden();
      const expandBackendBtn = backendPillar.getByRole("button", { name: /expand/i });
      await expandBackendBtn.click();
    } else {
      const expandBackendBtn = backendPillar.getByRole("button", { name: /expand/i });
      await expandBackendBtn.click();
    }

    // Assert helpers.py file is visible
    await expect(helpersFile).toBeVisible();

    // If any folder is present, expand it
    const folderNodes = page.locator('[data-node-kind="folder"]');
    if ((await folderNodes.count()) > 0) {
      const folderBtn = folderNodes.first().getByRole("button", { name: /expand/i });
      if (await folderBtn.isVisible()) {
        await folderBtn.click();
      }
    }

    // 6. Expand file:helpers.py to reveal its symbol(s)
    const helpersExpandBtn = helpersFile.getByRole("button", {
      name: /expand/i,
    });
    await expect(helpersExpandBtn).toBeVisible();
    await helpersExpandBtn.click();

    // Assert symbol "shout" is visible
    const shoutSymbol = page.locator('[data-node-id="func:helpers.py:shout"]');
    await expect(shoutSymbol).toBeVisible();

    // 7. Search for helpers.py
    const searchInput = page.locator('#mindmap-search-input');
    await expect(searchInput).toBeVisible();
    await searchInput.fill("helpers.py");

    // Allow debounce to process
    await page.waitForTimeout(350);

    // Assert search result count indicator and that the first result is selected/focused
    const matchCount = page.locator('[data-testid="search-match-count"]');
    await expect(matchCount).toBeVisible();
    await expect(matchCount).toHaveText(/^\d+\/\d+$/);
    await expect(helpersFile).toHaveAttribute("data-selected", "true");
    await expect(helpersFile).toBeInViewport();

    // Open outline and assert it mirrors the visible tree
    const outlineToggle = page.locator('[data-testid="toggle-outline-btn"]');
    await outlineToggle.click();

    const outline = page.locator('[data-testid="mindmap-outline"]');
    await expect(outline).toBeVisible();
    await expect(outline.getByRole("tree")).toBeVisible();
    await expect(outline.getByText("helpers.py")).toBeVisible();

    // 8. Toggle orientation: TB -> LR -> TB and assert no window overflow
    const orientationToggle = page.locator('[data-testid="toggle-orientation-btn"]');
    await orientationToggle.click(); // Switch to LR
    await page.waitForTimeout(200);

    let overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow).toBe(false);

    await orientationToggle.click(); // Switch back to TB
    await page.waitForTimeout(200);

    overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow).toBe(false);

    // 9. Assert zero un-whitelisted console errors
    assertNoErrors(errors, "MM01");
    await captureJourney(page, "mindmap", "mindmap-multilang");
  });

  test("MM02 — responsive viewport verification at 1600x900 and 1280x800", async ({
    page,
  }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    // Test at 1600x900
    await page.setViewportSize({ width: 1600, height: 900 });
    await page.goto("/");
    await page.locator('[data-testid="view-mode-mindmap"]').click();

    await expect(page.locator('[data-node-id="pillar:backend"]')).toBeVisible();

    let overflow1600 = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow1600).toBe(false);

    // Test at 1280x800
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(200);

    let overflow1280 = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow1280).toBe(false);

    assertNoErrors(errors, "MM02");
  });

  test("MM03 — hierarchical folder, file, and symbol expansion with v2_contract fixture", async ({
    page,
  }) => {
    await loadFixture("v2_contract");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await page.locator('[data-testid="view-mode-mindmap"]').click();

    // The six pillars are expanded on first paint; open the frontend folder branch.
    const frontendPillar = page.locator('[data-node-id="pillar:frontend"]');
    await expect(frontendPillar).toBeVisible();

    const componentsFolder = page.locator(
      '[data-node-id="folder:frontend:components"]',
    );
    await expect(componentsFolder).toBeVisible();
    await componentsFolder.getByRole("button", { name: /expand/i }).click();

    const buttonFile = page.locator(
      '[data-node-id="file:components/Button.tsx"]',
    );
    await expect(buttonFile).toBeVisible();
    await buttonFile
      .getByRole("button", { name: /expand symbols/i })
      .click();

    const buttonSymbol = page.locator(
      '[data-node-id="func:components/Button.tsx:Button"]',
    );
    await expect(buttonSymbol).toBeVisible();

    // The outline mirrors the same expanded hierarchy.
    await page.locator('[data-testid="toggle-outline-btn"]').click();
    const outline = page.locator('[data-testid="mindmap-outline"]');
    await expect(outline).toBeVisible();
    await expect(
      outline.getByText("components", { exact: true }),
    ).toBeVisible();
    await expect(outline.getByText("Button", { exact: true })).toBeVisible();

    assertNoErrors(errors, "MM03");
  });
});
