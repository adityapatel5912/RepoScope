/**
 * journeys.spec.ts
 * RepoScope browser-QA journeys.
 *
 * Part III of docs/ROADMAP_V2.md, Section 18.4 (the smoke matrix).
 *
 * Sprint 0 implements the foundation journeys:
 *   J00  health            — the backend and the UI both come up
 *   J01  graph renders     — a repo loads and the canvas is NOT blank
 *   J02  node drawer       — clicking a node opens its details
 *   J03  no console errors — the gate that did not exist before
 *
 * Every journey asserts ZERO un-whitelisted console/network errors and
 * commits a screenshot to docs/screenshots/v2/.
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

/** Load a fixture repository into backend state, without touching the network. */
async function loadFixture(name = "multilang"): Promise<void> {
  const response = await fetch(
    `${BACKEND_URL}/api/qa/load-fixture?name=${encodeURIComponent(name)}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to load fixture '${name}': HTTP ${response.status} ` +
        `${await response.text()}`,
    );
  }
}

test.describe("RepoScope QA journeys", () => {
  test("J00 — backend is healthy and the UI mounts", async ({ page }) => {
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();

    // The root route redirects to the health page; the app shell must exist.
    await expect(
      page.getByText(/RepoScope|Health|Architecture/i).first(),
    ).toBeVisible({ timeout: 20_000 });

    assertNoErrors(errors, "J00");
    await captureJourney(page, "j00-health", "loaded");
  });

  test("J01 — a loaded repo renders a populated graph", async ({ page }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    const nodeCount = await expectGraphHasNodes(page);

    expect(nodeCount).toBeGreaterThan(1);

    assertNoErrors(errors, "J01");
    await captureJourney(page, "j01-graph", "graph-rendered");
  });

  test("J02 — clicking a file node opens the detail drawer", async ({ page }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expectGraphHasNodes(page);

    // Click a FILE node — that is what a user actually clicks. The root
    // ("repo:root") node is also covered, by the geometry assertion in J05.
    const fileNode = page.locator('.react-flow__node[data-id^="file:"]').first();
    await fileNode.click();

    const drawer = page.locator(".node-drawer");
    await expect(drawer).toBeVisible({ timeout: 15_000 });

    assertNoErrors(errors, "J02");
    await captureJourney(page, "j02-drawer", "node-drawer-open");
  });

  test("J05 — no graph node is painted under the sticky header", async ({ page }) => {
    // Regression guard for a real defect the QA harness found:
    // fitView clamped its zoom at 0.3, could not fit a tall pyramid, and
    // centred the overflow — the top of which was painted under the
    // TopBar (z-50). The root node was clipped by 24px and unclickable.
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expectGraphHasNodes(page);
    await page.waitForTimeout(800); // let fitView settle

    const overlap = await page.evaluate(`(() => {
      const header = document.querySelector("header");
      if (!header) return null;
      const headerBottom = header.getBoundingClientRect().bottom;
      const nodes = Array.from(document.querySelectorAll(".react-flow__node"));
      const offenders = nodes
        .map(n => ({ id: n.getAttribute("data-id"), r: n.getBoundingClientRect() }))
        .filter(n => n.r.top < headerBottom && n.r.height > 0)
        .map(n => ({ id: n.id, top: Math.round(n.r.top), bottom: Math.round(n.r.bottom) }));
      return { headerBottom: Math.round(headerBottom), offenders };
    })()`);

    expect(overlap, "the header element was not found").not.toBeNull();
    expect(
      overlap!.offenders,
      `these nodes are painted under the sticky header (bottom ${overlap!.headerBottom}px): ` +
        JSON.stringify(overlap!.offenders),
    ).toEqual([]);

    assertNoErrors(errors, "J05");
    await captureJourney(page, "j05-header-clearance", "nodes-clear-header");
  });

  test("J03 — the architecture rules endpoint is served", async ({ page }) => {
    const errors = attachErrorCollector(page);

    const response = await page.request.get(`${BACKEND_URL}/api/arch/rules`);
    expect(response.status()).toBe(200);

    const payload = await response.json();
    expect(payload.layers).toHaveLength(5);
    expect(payload.layers.map((l: { id: string }) => l.id)).toEqual([
      "client",
      "backend",
      "storage",
      "external",
      "compute",
    ]);
    expect(payload.default_layer).toBe("backend");

    assertNoErrors(errors, "J03");
  });

  test("J04 — the graph survives a page reload with no console errors", async ({
    page,
  }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expectGraphHasNodes(page);
    await page.reload();
    await expectGraphHasNodes(page);

    assertNoErrors(errors, "J04");
    await captureJourney(page, "j04-reload", "after-reload");
  });
});
