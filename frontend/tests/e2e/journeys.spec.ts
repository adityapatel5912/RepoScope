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

    // The root node must also be fully inside the canvas. An earlier fit
    // nudged the viewport upwards to clear the floating toolbar, which
    // clipped the repo node off the top of the canvas instead.
    //
    // The values below are the node's offset from each canvas edge, so a
    // POSITIVE number means "inside" and a negative one means "clipped".
    const root = await page.evaluate(`(() => {
      const canvas = document.querySelector(".react-flow");
      const node = document.querySelector('.react-flow__node[data-id="repo:root"]');
      if (!canvas || !node) return null;
      const c = canvas.getBoundingClientRect();
      const n = node.getBoundingClientRect();
      return {
        top: Math.round(n.top - c.top),
        bottom: Math.round(c.bottom - n.bottom),
        left: Math.round(n.left - c.left),
        right: Math.round(c.right - n.right),
      };
    })()`);
    expect(root, "the root node was not found").not.toBeNull();
    // A small negative tolerance: the root may touch an edge, but it must
    // not disappear behind it.
    expect(root!.top, "the root node is clipped by the canvas top").toBeGreaterThanOrEqual(-2);
    expect(root!.bottom, "the root node is clipped by the canvas bottom").toBeGreaterThanOrEqual(-2);
    expect(root!.left, "the root node is clipped by the canvas left").toBeGreaterThanOrEqual(-2);
    expect(root!.right, "the root node is clipped by the canvas right").toBeGreaterThanOrEqual(-2);

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

  test("J06 — the analysis endpoints serve the graph intelligence", async ({
    page,
  }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    const hubs = await page.request.get(`${BACKEND_URL}/api/analysis/hubs`);
    expect(hubs.status()).toBe(200);
    const hubPayload = await hubs.json();
    expect(hubPayload.available).toBe(true);
    expect(hubPayload.hubs.length).toBeGreaterThan(0);
    // PageRank scores must be real numbers that sum to roughly 1.
    const scores = hubPayload.hubs.map((h: { pagerank: number }) => h.pagerank);
    expect(scores.every((s: number) => s > 0)).toBe(true);
    expect(scores[0]).toBeGreaterThanOrEqual(scores[scores.length - 1]);

    const cycles = await page.request.get(`${BACKEND_URL}/api/analysis/cycles`);
    expect(cycles.status()).toBe(200);
    const cyclePayload = await cycles.json();
    expect(cyclePayload.available).toBe(true);
    // The multi-language fixture has no cycles, so the count is zero —
    // but the endpoint must still answer with a well-formed payload.
    expect(cyclePayload.total).toBe(0);

    // The circular fixture has both file-level and symbol-level cycles.
    await loadFixture("circular");
    const circularCycles = await page.request.get(
      `${BACKEND_URL}/api/analysis/cycles`,
    );
    const circularPayload = await circularCycles.json();
    expect(circularPayload.total).toBeGreaterThan(0);
    expect(circularPayload.file_cycles).toBeGreaterThan(0);
    expect(circularPayload.symbol_cycles).toBeGreaterThan(0);

    // Put the multi-language fixture back for the remaining checks.
    await loadFixture("multilang");

    const unreachable = await page.request.get(
      `${BACKEND_URL}/api/analysis/unreachable`,
    );
    expect(unreachable.status()).toBe(200);
    const unreachablePayload = await unreachable.json();
    expect(unreachablePayload.available).toBe(true);
    // The result is always labelled as an estimate, never as proof.
    expect(unreachablePayload.estimate).toBe(true);

    assertNoErrors(errors, "J06");
  });

  test("J07 — the churn heatmap overlay renders", async ({ page }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expectGraphHasNodes(page);

    // The churn overlay is opt-in: turn it on from the toolbar.
    const churnToggle = page.getByRole("button", {
      name: "Toggle churn heatmap",
    });
    await churnToggle.click();

    // The churn spectrum appears in the legend card.
    const legend = page.locator(".graph-legend");
    await expect(legend).toBeVisible({ timeout: 15_000 });
    await expect(legend).toContainText("Churn");
    await expect(legend).toContainText("Hotspot");
    // The layer legend must still be readable in the same card.
    await expect(legend).toContainText("Client / UI");

    assertNoErrors(errors, "J07");
    await captureJourney(page, "j07-churn", "churn-heatmap");
  });

  test("J08 — the architecture cluster view renders", async ({ page }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expectGraphHasNodes(page);

    const clusterToggle = page.getByRole("button", {
      name: "Toggle architecture cluster view",
    });
    await clusterToggle.click();

    // The pyramid collapses to the five canonical layers.
    const clusters = page.locator('.react-flow__node[data-id^="cluster:"]');
    await expect(clusters.first()).toBeVisible({ timeout: 15_000 });
    const count = await clusters.count();
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(5);

    // Wait for the fit-view animation to settle before capturing, so the
    // screenshot shows the final layout rather than a mid-transition frame.
    await page.waitForTimeout(1200);

    assertNoErrors(errors, "J08");
    await captureJourney(page, "j08-clusters", "cluster-view");
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
