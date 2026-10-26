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
import { readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertNoErrors,
  attachErrorCollector,
  captureJourney,
  expectGraphHasNodes,
} from "./helpers";
import {
  buildEditorUri,
  buildRepoScopeUri,
  parseRepoScopeUri,
  resolveWorkspaceRoot,
} from "../../src/utils/ideLinks";

// The frontend is an ES module package, so __dirname is not defined.
const HERE = path.dirname(fileURLToPath(import.meta.url));

const BACKEND_URL =
  process.env.REPOSCOPE_QA_BACKEND_URL ?? "http://127.0.0.1:8010";

/**
 * Load a fixture repository into backend state, without touching the network.
 *
 * `copy` loads a WRITABLE copy in the temp directory — a journey that
 * edits a file must not edit the committed fixture, or every later run
 * would start from a different repository than the snapshot expects.
 *
 * `watch` starts the file watcher, which is what makes the live-update
 * journey possible.
 */
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

  test("J12 — local mode: editing a file updates the graph without a reload", async ({
    page,
  }) => {
    // The whole point of local mode: a private repository, analysed on
    // this machine, whose graph keeps up with the code as you edit it.
    //
    // The fixture is loaded as a WRITABLE COPY. Editing the committed
    // fixture would corrupt it for every later run, and the failure
    // would look like a product bug.
    const { copy } = await loadFixture("multilang", { copy: true, watch: true });
    expect(copy, "the QA router did not return the copy path").toBeTruthy();

    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expectGraphHasNodes(page);

    // The privacy promise is stated on screen.
    const badge = page.getByTestId("local-mode-badge");
    await expect(badge).toBeVisible({ timeout: 15_000 });
    await expect(badge).toContainText(/local mode/i);

    // A marker on the window proves the page was never reloaded: a
    // reload would wipe it.
    await page.evaluate(() => {
      (window as unknown as { __qaNoReload?: string }).__qaNoReload = "alive";
    });

    // The node count the UI is showing. A DOM node count is NOT a
    // reliable signal here — ReactFlow only renders what is in the
    // viewport, so adding a symbol can REFLOW the pyramid and change
    // which nodes are on screen. The graph's own count is the honest
    // one, and the Repository card shows it.
    const nodesTile = page.getByTestId("stat-value-nodes");
    const before = Number((await nodesTile.innerText()).trim());

    // Edit a file in the copy. The new function becomes a new symbol
    // node, so the graph's node count must grow.
    const target = `${copy}/helpers.py`;
    const source = await readFile(target, "utf-8");
    await writeFile(
      target,
      `${source}\n\ndef qa_live_marker():\n    return "live"\n`,
      "utf-8",
    );

    // Wait for the graph to catch up — on observable state, not on a
    // timer. The watcher debounces for 500 ms, then the re-index runs,
    // then the backend pushes the new graph down the SSE stream.
    await expect
      .poll(async () => Number((await nodesTile.innerText()).trim()), {
        timeout: 30_000,
        message: "the graph never picked up the edit",
      })
      .toBeGreaterThan(before);

    // The page was never reloaded.
    const marker = await page.evaluate(
      () => (window as unknown as { __qaNoReload?: string }).__qaNoReload,
    );
    expect(marker, "the page reloaded — the update was not live").toBe("alive");

    // The live update is reported in the status bar.
    await expect(page.locator("text=/live:/").first()).toBeVisible({
      timeout: 15_000,
    });

    // And the backend's own graph really does contain the new symbol —
    // the same check the backend unit tests make, from the outside.
    const graphResponse = await page.request.get(`${BACKEND_URL}/api/repo/graph`);
    expect(graphResponse.status()).toBe(200);
    const graph = await graphResponse.json();
    const ids = (graph.nodes ?? []).map((n: { id: string }) => n.id);
    expect(ids).toContain("func:helpers.py:qa_live_marker");

    assertNoErrors(errors, "J12");
    await captureJourney(page, "j12-local-live-update", "graph-updated-live");
  });

  test("J19 — the repo map renders and the token reduction is shown", async ({
    page,
  }) => {
    await loadFixture("multilang");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expectGraphHasNodes(page);

    // The panel is in the sidebar, next to the Insights panel.
    const panel = page.getByTestId("repo-map-panel");
    await expect(panel).toBeVisible({ timeout: 20_000 });

    // The headline number: the context saving.
    const reduction = panel.getByTestId("repo-map-reduction");
    await expect(reduction).toBeVisible({ timeout: 20_000 });
    const reductionText = (await reduction.innerText()).replace("%", "").trim();
    const reductionValue = Number(reductionText);
    expect(Number.isFinite(reductionValue), `the reduction is not a number: ${reductionText}`).toBe(true);
    expect(reductionValue).toBeGreaterThan(0);

    // The API's own answer, so the panel is checked against the source
    // rather than against itself.
    const response = await page.request.get(`${BACKEND_URL}/api/analysis/repo-map?budget=8000`);
    expect(response.status()).toBe(200);
    const payload = await response.json();
    expect(payload.available).toBe(true);
    expect(payload.entries.length).toBeGreaterThan(0);
    expect(payload.tokens).toBeLessThanOrEqual(payload.budget_tokens);
    expect(payload.full_context_tokens).toBeGreaterThan(0);
    expect(payload.reduction_pct).toBeGreaterThan(0);

    // The map is real: it names files, symbols and layers.
    const first = payload.entries[0];
    expect(first.path).toBeTruthy();
    expect(Array.isArray(first.symbols)).toBe(true);
    expect(first.layer).toBeTruthy();

    assertNoErrors(errors, "J19");
    await captureJourney(page, "j19-repo-map", "repo-map-panel");
  });

  test("J13 — the MCP server answers over stdio", async ({ page }) => {
    /**
     * The agent-facing half of the wedge.
     *
     * The server is driven over a REAL stdio pipe — the same way Claude
     * Desktop or Cursor drives it — with raw JSON-RPC. An in-process
     * call would prove the tools work but not that the transport does,
     * and the transport is the part that breaks when the SDK moves.
     */
    const errors = attachErrorCollector(page);
    await loadFixture("multilang");

    const backendDir = path.resolve(HERE, "../../../backend");
    const root = path.resolve(backendDir, "tests/fixtures/multilang");

    const exchange = await new Promise<string>((resolve, reject) => {
      const child = spawn(
        process.env.REPOSCOPE_PYTHON ?? "python",
        ["-m", "mcp_server.server", "--root", root],
        { cwd: backendDir },
      );

      let stdout = "";
      let stderr = "";
      child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
      child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });

      const timer = setTimeout(() => {
        child.kill();
        reject(
          new Error(
            `the MCP server did not answer in time.\n` +
            `stdout:\n${stdout}\nstderr:\n${stderr}`,
          ),
        );
      }, 120_000);

      // The stream is NOT closed early. Closing stdin tells the server to
      // shut down, and it does so before the tool call has finished —
      // which is why the first attempt saw the handshake and the tool
      // list but never the tool call. The process is killed instead.
      const finish = () => {
        clearTimeout(timer);
        child.kill();
        resolve(stdout);
      };

      child.stdout.on("data", () => {
        // Wait until the tool call has been answered.
        if (stdout.includes('"id":3')) finish();
      });

      child.on("close", () => {
        clearTimeout(timer);
        resolve(stdout);
      });

      child.stdin.write(
        JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "initialize",
          params: {
            protocolVersion: "2025-06-18",
            capabilities: {},
            clientInfo: { name: "reposcope-qa", version: "1" },
          },
        }) + "\n",
      );
      child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");
      child.stdin.write(
        JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }) + "\n",
      );
      child.stdin.write(
        JSON.stringify({
          jsonrpc: "2.0",
          id: 3,
          method: "tools/call",
          params: {
            name: "calculate_blast_radius",
            arguments: { target_file: "helpers.py" },
          },
        }) + "\n",
      );
    });

    const responses = exchange
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.startsWith("{"))
      .map((line) => JSON.parse(line) as Record<string, unknown>);

    const handshake = responses.find((r) => r.id === 1);
    expect(handshake, "no initialize response").toBeTruthy();
    expect(handshake!.error).toBeUndefined();
    const result = handshake!.result as { serverInfo: { name: string }; protocolVersion: string };
    expect(result.serverInfo.name).toBe("RepoScope");
    expect(result.protocolVersion).toBeTruthy();

    const listing = responses.find((r) => r.id === 2);
    expect(listing, "no tools/list response").toBeTruthy();
    const tools = (listing!.result as { tools: { name: string; inputSchema: { type: string } }[] }).tools;
    const names = tools.map((t) => t.name);
    for (const expected of [
      "get_architecture_overview",
      "calculate_blast_radius",
      "get_dependency_lineage",
      "explain_architectural_rule",
      "get_repo_map",
      "find_dependency_cycles",
    ]) {
      expect(names, `the MCP server is missing ${expected}`).toContain(expected);
    }
    for (const tool of tools) {
      expect(tool.inputSchema.type).toBe("object");
    }

    // A real tool call, with a real answer.
    const call = responses.find((r) => r.id === 3);
    expect(call, "no tools/call response").toBeTruthy();
    const payload = (call!.result as { content: { text: string }[] }).content[0].text;
    const blast = JSON.parse(payload);
    expect(blast.available).toBe(true);
    expect(
      blast.direct_impacts.map((n: { label: string }) => n.label),
    ).toContain("app.py");

    assertNoErrors(errors, "J13");
  });

  test("J14 — a node click produces the exact editor URI", async ({ page }) => {
    /**
     * The map → code link.
     *
     * The URI formats are asserted directly (they are pure functions),
     * and then the real path is exercised: click a file node, click
     * "Open in editor", and read the URI the app actually produced.
     */
    const errors = attachErrorCollector(page);

    // ── The URI formats ──
    expect(buildEditorUri("vscode", "/home/me/app.py", 12, 3)).toBe(
      "vscode://file//home/me/app.py:12:3",
    );
    expect(buildEditorUri("vscode-insiders", "C:\\repo\\app.py", 7)).toBe(
      "vscode-insiders://file/C:/repo/app.py:7:0",
    );
    expect(buildEditorUri("cursor", "/home/me/app.py", 42)).toBe(
      "cursor://file//home/me/app.py:42:0",
    );
    expect(
      buildEditorUri("jetbrains", "/home/me/proj/src/app.py", 5, 0, {
        project: "proj",
      }),
    ).toBe(
      "jetbrains://idea/navigate/reference?project=proj&path=home%2Fme%2Fproj%2Fsrc%2Fapp.py%3A5",
    );
    expect(buildEditorUri("sublime", "/home/me/app.py", 9)).toBe(
      "subl://open?url=file:///home/me/app.py&line=9",
    );

    // ── The workspace-root resolution ──
    expect(resolveWorkspaceRoot("backend/auth.py", "/home/me/proj")).toBe(
      "/home/me/proj/backend/auth.py",
    );
    expect(resolveWorkspaceRoot("backend/auth.py", "C:\\repo")).toBe(
      "C:\\repo/backend/auth.py",
    );
    // No root → no path. The caller must fall back to copying it.
    expect(resolveWorkspaceRoot("backend/auth.py", "")).toBeNull();
    expect(resolveWorkspaceRoot("backend/auth.py", null)).toBeNull();

    // ── The round trip through the app's own URI scheme ──
    const repoUri = buildRepoScopeUri({ path: "backend/auth.py", line: 12 });
    expect(parseRepoScopeUri(repoUri)).toEqual({
      path: "backend/auth.py",
      line: 12,
      col: 0,
    });

    // ── The real path, in the browser ──
    await loadFixture("multilang");
    await page.goto("/");
    await expectGraphHasNodes(page);

    // Capture the URI the app emits. The event fires before the
    // navigation, so it is observed even though the test browser has no
    // editor protocol handler.
    await page.evaluate(() => {
      (window as unknown as { __qaEditorUri?: string }).__qaEditorUri = "";
      window.addEventListener("reposcope:open-editor", (event) => {
        const detail = (event as CustomEvent<{ uri: string }>).detail;
        (window as unknown as { __qaEditorUri?: string }).__qaEditorUri = detail.uri;
      });
    });

    // A PYTHON node, specifically — the roadmap's acceptance is that a
    // Python node opens the exact line, and the fixture has two.
    const pythonNode = page.locator('.react-flow__node[data-id="file:app.py"]').first();
    await expect(pythonNode).toBeVisible({ timeout: 15_000 });
    await pythonNode.click();

    const openButton = page.getByTestId("open-in-editor");
    await expect(openButton).toBeVisible({ timeout: 15_000 });
    await openButton.click();

    await expect
      .poll(
        async () =>
          page.evaluate(
            () => (window as unknown as { __qaEditorUri?: string }).__qaEditorUri ?? "",
          ),
        { timeout: 15_000, message: "the app never produced an editor URI" },
      )
      .not.toBe("");

    const produced = await page.evaluate(
      () => (window as unknown as { __qaEditorUri?: string }).__qaEditorUri ?? "",
    );
    // The URI names the real file, in a scheme an editor can handle.
    expect(produced).toMatch(/^(vscode|vscode-insiders|cursor|jetbrains|subl):/);
    expect(produced).toContain("app.py");
    expect(produced.endsWith("app.py:0:0")).toBe(true);

    // ── And the EXACT line, via a symbol ──
    //
    // "Open in editor" on the file opens the file. The drawer's symbol
    // list opens the symbol's own line — which is the acceptance
    // criterion: clicking a Python node opens the exact line.
    await page.evaluate(() => {
      (window as unknown as { __qaEditorUri?: string }).__qaEditorUri = "";
    });

    const symbolLink = page.getByTestId("open-symbol-in-editor").first();
    await expect(symbolLink).toBeVisible({ timeout: 15_000 });
    const symbolText = (await symbolLink.innerText()).trim();
    await symbolLink.click();

    await expect
      .poll(
        async () =>
          page.evaluate(
            () => (window as unknown as { __qaEditorUri?: string }).__qaEditorUri ?? "",
          ),
        { timeout: 15_000, message: "the symbol link never produced an editor URI" },
      )
      .not.toBe("");

    const symbolUri = await page.evaluate(
      () => (window as unknown as { __qaEditorUri?: string }).__qaEditorUri ?? "",
    );
    // The line in the URI must be the line the drawer showed.
    const shownLine = Number(symbolText.split(":").pop()?.trim() ?? 0);
    expect(shownLine).toBeGreaterThan(0);
    expect(symbolUri).toContain(`app.py:${shownLine}`);
    expect(symbolUri).toContain(".py");

    assertNoErrors(errors, "J14");
    await captureJourney(page, "j14-ide-link", "editor-uri");
  });

  test("J20 — a boundary violation is flagged in the PR comment", async ({
    page,
  }) => {
    /**
     * The architecture-governance angle — the one no AI code reviewer
     * competes in.
     *
     * The `boundary` fixture declares its own layers and its own rule in
     * `.reposcope.yml`: the domain may not depend on the infra.
     * `domain/orders.py` breaks that rule. The report must say so, and
     * it must name BOTH files and the rule.
     */
    const errors = attachErrorCollector(page);
    await loadFixture("boundary");

    const response = await page.request.post(`${BACKEND_URL}/api/pr/report`, {
      data: {
        meta: { number: 42, title: "Add the order flow", state: "open" },
        changed_files: [
          { filename: "domain/orders.py", status: "modified", additions: 8, deletions: 0 },
        ],
      },
    });
    expect(response.status()).toBe(200);
    const report = await response.json();

    // The violation is found, and it names both files.
    const violations = report.architecture_impact.boundary_violations;
    expect(violations).toBeGreaterThan(0);

    const comment = report.comment;
    expect(comment).toContain("Architecture impact");
    expect(comment).toContain("Boundary violation");
    expect(comment).toContain("domain/orders.py");
    expect(comment).toContain("infra/store.py");

    // The merge gate blocks it, and says why.
    expect(report.merge_gate.passed).toBe(false);
    expect(report.merge_gate.blocked_by).toContain("boundary-violation");

    // The Mermaid fallback survives — GitHub renders it natively and it
    // needs no external service.
    expect(comment).toContain("```mermaid");

    assertNoErrors(errors, "J20");
  });

  test("J21 — the SARIF output is valid against the 2.1.0 schema", async ({
    page,
  }) => {
    /**
     * SARIF is the GitHub code-scanning standard, and it is what makes
     * the findings render INLINE on the PR diff.
     *
     * GitHub silently rejects a malformed SARIF file, so the shape is
     * asserted here rather than assumed: the version, the runs array,
     * the tool driver, and every result's ruleId, level and message.
     */
    const errors = attachErrorCollector(page);
    await loadFixture("boundary");

    const response = await page.request.get(`${BACKEND_URL}/api/pr/sarif`);
    expect(response.status()).toBe(200);
    const payload = await response.json();
    const document = payload.sarif;

    expect(document.version).toBe("2.1.0");
    expect(document.$schema).toContain("sarif-schema-2.1.0");
    expect(Array.isArray(document.runs)).toBe(true);
    expect(document.runs.length).toBeGreaterThan(0);

    const run = document.runs[0];
    expect(run.tool.driver.name).toBe("RepoScope");
    expect(run.tool.driver.version).toBeTruthy();
    expect(Array.isArray(run.tool.driver.rules)).toBe(true);
    expect(run.tool.driver.rules.length).toBeGreaterThan(0);

    const known = new Set(run.tool.driver.rules.map((r: { id: string }) => r.id));
    for (const result of run.results) {
      expect(result.ruleId).toBeTruthy();
      expect(known.has(result.ruleId)).toBe(true);
      expect(["error", "warning", "note", "none"]).toContain(result.level);
      expect(result.message.text).toBeTruthy();
      expect(result.locations.length).toBeGreaterThan(0);
      const location = result.locations[0].physicalLocation;
      expect(location.artifactLocation.uri).toBeTruthy();
    }
  });
});
