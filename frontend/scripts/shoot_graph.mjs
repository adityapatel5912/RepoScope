// shoot_graph.mjs
// Screenshot the graph for whatever repository the backend has loaded.
//
//   node scripts/shoot_graph.mjs <output.png> [--zoom 0.2] [--fixture name]
//
// A reusable QA lens: it opens the real app in a real browser, waits for
// the graph to render, and captures the canvas. Used to compare the
// low-zoom density view against the readable view.

import { chromium } from "@playwright/test";
import fs from "fs";

const args = process.argv.slice(2);
const output = args[0] ?? "graph.png";
const zoomArg = args.includes("--zoom") ? args[args.indexOf("--zoom") + 1] : null;
const fixtureArg = args.includes("--fixture") ? args[args.indexOf("--fixture") + 1] : null;

const BACKEND = process.env.REPOSCOPE_QA_BACKEND_URL ?? "http://127.0.0.1:8000";
const FRONTEND = process.env.REPOSCOPE_QA_FRONTEND_URL ?? "http://127.0.0.1:5173";

if (fixtureArg) {
  const res = await fetch(`${BACKEND}/api/qa/load-fixture?name=${encodeURIComponent(fixtureArg)}`, {
    method: "POST",
  });
  if (!res.ok) {
    console.error(`could not load fixture: HTTP ${res.status}`);
    process.exit(1);
  }
  console.log(`loaded fixture: ${fixtureArg}`);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });

const errors = [];
const responses = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
page.on("requestfailed", (r) => {
  errors.push(`REQUEST FAILED ${r.method()} ${r.url()} — ${r.failure()?.errorText}`);
});
page.on("response", (r) => {
  if (r.status() >= 400) {
    responses.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  }
});

await page.goto(FRONTEND, { waitUntil: "networkidle" });

try {
  await page.waitForSelector(".react-flow__node", { timeout: 90000 });
} catch (err) {
  // Report what the page actually looked like — a bare timeout says nothing.
  console.error("the graph never rendered. page diagnostics:");
  console.error(`  title:  ${await page.title()}`);
  console.error(`  body:   ${(await page.locator("body").innerText()).slice(0, 400).replace(/\n/g, " | ")}`);
  console.error(`  html:   ${(await page.content()).length} bytes`);
  console.error(`  console errors (${errors.length}):`);
  for (const e of errors.slice(0, 10)) console.error(`    ${e}`);
  console.error(`  failed responses (${responses.length}):`);
  for (const r of responses.slice(0, 12)) console.error(`    ${r}`);
  await page.screenshot({ path: output.replace(/\.png$/, "-FAILED.png") });
  await browser.close();
  process.exit(1);
}

await page.waitForTimeout(1500);

if (zoomArg) {
  const zoom = Number(zoomArg);
  await page.evaluate((z) => {
    const el = document.querySelector(".react-flow__viewport");
    if (!el) return;
    const m = new DOMMatrixReadOnly(getComputedStyle(el).transform);
    el.style.transform = `matrix(${m.a * z / m.a}, 0, 0, ${m.d * z / m.d}, ${m.e}, ${m.f})`;
  }, zoom);
  await page.waitForTimeout(1200);
}

const canvas = page.locator(".react-flow");
await canvas.screenshot({ path: output });

const stats = await page.evaluate(() => {
  const canvas = document.querySelector(".react-flow");
  const root = document.querySelector('.react-flow__node[data-id="repo:root"]');
  const c = canvas?.getBoundingClientRect();
  const r = root?.getBoundingClientRect();
  const vp = document.querySelector(".react-flow__viewport");
  return {
    nodes: document.querySelectorAll(".react-flow__node").length,
    edges: document.querySelectorAll(".react-flow__edge").length,
    labels: document.querySelectorAll(".rs-node-label").length,
    rankLabels: document.querySelectorAll(".rs-rank-label").length,
    lod: canvas?.className ?? "",
    canvas: c ? { w: Math.round(c.width), h: Math.round(c.height) } : null,
    root: r ? { top: Math.round(r.top - (c?.top ?? 0)), bottom: Math.round(r.bottom - (c?.top ?? 0)) } : null,
    transform: vp ? getComputedStyle(vp).transform : null,
  };
});

console.log(`nodes=${stats.nodes} edges=${stats.edges} labels=${stats.labels} rankLabels=${stats.rankLabels}`);
console.log(`container class: ${stats.lod}`);
console.log(`canvas: ${JSON.stringify(stats.canvas)}  root(top,bottom within canvas): ${JSON.stringify(stats.root)}`);
console.log(`viewport transform: ${stats.transform}`);
console.log(`console errors: ${errors.length}`);
for (const e of errors.slice(0, 5)) console.log(`  ${e}`);
console.log(`saved: ${output} (${fs.statSync(output).size} bytes)`);

await browser.close();
