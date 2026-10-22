/**
 * model.test.js
 * The extension's pure logic, tested without an extension host.
 *
 *     npm run compile && node --test test/
 *
 * A plain `node --test` - no mocking, no VS Code, no extension host.
 * That is possible because everything that can be decided without an
 * editor lives in `model.ts`, which has no `vscode` import.
 *
 * The CodeLens count is the important one: it MUST match the MCP tool's
 * answer, because both read the same graph. If they ever disagree, an
 * agent and a human are looking at two different codebases.
 */
const test = require("node:test");
const assert = require("node:assert");

const {
  layerOf,
  layoutBands,
  renderSvg,
  candidateSymbols,
  isDefinitionLine,
  callersLensText,
  formatStatusText,
  formatStatusTooltip,
  escapeXml,
  parseOpenUri,
  renderLegend,
  shortenLabel,
} = require("../out/model.js");

const GRAPH = {
  summary: "4 nodes, 2 edges",
  nodes: [
    { id: "file:app.py", type: "file", label: "app.py", pagerank: 0.5 },
    { id: "file:helpers.py", type: "file", label: "helpers.py", pagerank: 0.3 },
    { id: "file:ui.tsx", type: "file", label: "ui.tsx", pagerank: 0.15 },
    { id: "file:README.md", type: "file", label: "README.md", pagerank: 0.05 },
    { id: "func:app.py:greet", type: "function", label: "greet", file: "app.py", line: 19 },
  ],
  edges: [
    { source: "file:app.py", target: "file:helpers.py", type: "imports" },
    { source: "file:ui.tsx", target: "file:helpers.py", type: "imports" },
  ],
};

test("the layer of a file follows its kind", () => {
  assert.equal(layerOf({ id: "file:a.py", type: "file", label: "a.py" }), "backend");
  assert.equal(layerOf({ id: "file:a.tsx", type: "file", label: "a.tsx" }), "client");
  assert.equal(layerOf({ id: "file:a.md", type: "file", label: "a.md" }), "storage");
  assert.equal(layerOf({ id: "file:a.go", type: "file", label: "a.go" }), "compute");
  assert.equal(
    layerOf({ id: "file:tests/a.py", type: "file", label: "tests/a.py" }),
    "external",
  );
});

test("the bands are ordered by the graph's own centrality", () => {
  const bands = layoutBands(GRAPH);
  // The most central file is in the first band.
  assert.equal(bands.get("file:app.py"), 0);
  assert.ok(
    bands.get("file:helpers.py") <= bands.get("file:README.md"),
    "the ranking does not follow PageRank",
  );
});

test("with no file open, the map is the repository at a glance", () => {
  const svg = renderSvg(GRAPH);
  assert.match(svg, /<svg/);
  assert.match(svg, /4 files, 3 layers/);
  assert.match(svg, /MOST CENTRAL/);
  assert.match(svg, /TOP FOLDERS/);
  // Only the top modules are drawn - a sidebar is not a canvas.
  assert.ok((svg.match(/data-id="/g) || []).length <= 6);
  assert.match(svg, /data-id="file:app\.py"/);
});

test("with a file open, the map is that file's neighbourhood", () => {
  const svg = renderSvg(GRAPH, "file:app.py");
  assert.match(svg, /THIS FILE/);
  assert.match(svg, /USES \(1\)/);
  assert.match(svg, /USED BY \(0\)/);
  assert.match(svg, /helpers\.py/);
  // A file two hops away is not the file's neighbourhood.
  assert.doesNotMatch(svg, /README\.md/);
});

test("the focused file is named, not just dotted", () => {
  const svg = renderSvg(GRAPH, "file:app.py");
  assert.match(svg, />app\.py</);
  assert.match(svg, /data-id="file:app\.py"/);
});

test("the dependents are on the other side of the edge", () => {
  // helpers.py is used by app.py and ui.tsx.
  const svg = renderSvg(GRAPH, "file:helpers.py");
  assert.match(svg, /USED BY \(2\)/);
  assert.match(svg, /app\.py/);
  assert.match(svg, /ui\.tsx/);
  assert.match(svg, /USES \(0\)/);
});

test("every node says what it is on hover", () => {
  const svg = renderSvg(GRAPH);
  assert.match(svg, /<title>app\.py · backend<\/title>/);
});

test("the legend lists only the layers the repository uses", () => {
  const legend = renderLegend(GRAPH);
  assert.match(legend, /backend/);
  assert.match(legend, /client/);
  assert.match(legend, /data/);
  // The fixture has no Go/Rust files and no tests.
  assert.doesNotMatch(legend, /compute/);
});

test("a long path is shortened from the head, never from the file name", () => {
  assert.equal(shortenLabel("app.py", 42), "app.py");
  const shortened = shortenLabel("backend/tests/fixtures/real_small/src/tomli/_parser.py", 30);
  assert.ok(shortened.length <= 30, shortened);
  assert.ok(shortened.endsWith("_parser.py"), shortened);
  assert.ok(shortened.startsWith("…"), shortened);
});

test("an empty graph says what to do", () => {
  const svg = renderSvg({ nodes: [], edges: [], summary: "0 nodes" });
  assert.match(svg, /reposcope run \./);
});

test("the XML is escaped, so a path cannot break the SVG", () => {
  assert.equal(escapeXml('a&b<c>"d"'), "a&amp;b&lt;c&gt;&quot;d&quot;");
  const svg = renderSvg({
    nodes: [{ id: "file:<x>.py", type: "file", label: "<script>.py" }],
    edges: [],
    summary: "",
  });
  assert.ok(!svg.includes("<script>"), "the label was not escaped");
});

test("the candidate symbols on a definition line are the names, not the keywords", () => {
  assert.deepEqual(candidateSymbols("def greet(name: str) -> str:"), ["greet", "name", "str"]);
  // "export" and "function" are keywords, so they are filtered out.
  assert.deepEqual(candidateSymbols("export function renderLabel(text: string)"), [
    "renderLabel", "text", "string",
  ]);
  // A string literal must not contribute its contents.
  assert.deepEqual(candidateSymbols('const x = "notASymbol";'), ["x"]);
});

test("definition lines are recognised in every supported language", () => {
  assert.ok(isDefinitionLine("def greet():"));
  assert.ok(isDefinitionLine("export function go() {"));
  assert.ok(isDefinitionLine("func Greet() string {"));
  assert.ok(isDefinitionLine("pub fn main() {"));
  assert.ok(isDefinitionLine("class Foo:"));
  assert.ok(isDefinitionLine("    const x = 1;"));
  assert.ok(!isDefinitionLine("    return 42;"));
  assert.ok(!isDefinitionLine("// a comment"));
});

test("the caller lens reads naturally at every count", () => {
  assert.equal(callersLensText(0), "No callers");
  assert.equal(callersLensText(1), "View Callers (1)");
  assert.equal(callersLensText(8), "View Callers (8)");
});

test("the status bar states the count and the risk", () => {
  assert.equal(
    formatStatusText(12, "medium"),
    "$(git-merge) RepoScope: 12 dependents | Risk: medium",
  );
  assert.equal(
    formatStatusText(1, "low"),
    "$(git-merge) RepoScope: 1 dependent | Risk: low",
  );
  assert.equal(formatStatusText(0, "low"), "RepoScope: no dependents");
  assert.equal(formatStatusText(5, "high", false), "RepoScope: offline");
});

test("the status bar tooltip shows the evidence, not just the conclusion", () => {
  const tooltip = formatStatusTooltip({ direct: 3, transitive: 9, risk_score: 7 });
  assert.match(tooltip, /Direct dependents: 3/);
  assert.match(tooltip, /Transitive dependents: 9/);
  assert.match(tooltip, /Risk score: 7\/10/);
});

test("a reposcope://open link carries the file and the line", () => {
  const target = parseOpenUri("path=backend/graph_builder.py&line=15");
  assert.deepEqual(target, { path: "backend/graph_builder.py", line: 15 });
});

test("a reposcope://open link without a line opens the top of the file", () => {
  const target = parseOpenUri("path=backend/graph_builder.py");
  assert.deepEqual(target, { path: "backend/graph_builder.py", line: 1 });
});

test("a reposcope://open link without a file is not a target", () => {
  assert.equal(parseOpenUri("line=15"), null);
  assert.equal(parseOpenUri(""), null);
});

test("a reposcope://open link with a nonsense line still opens the file", () => {
  const target = parseOpenUri("path=a.py&line=not-a-number");
  assert.deepEqual(target, { path: "a.py", line: 1 });
});
