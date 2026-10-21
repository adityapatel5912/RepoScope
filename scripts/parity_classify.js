// parity_classify.js
// Parity probe for the RepoScope layer classifier.
//
// Runs the EXACT rules from frontend/src/components/graph/layerClassifier.ts
// over a corpus file and prints one classification per case as JSON.
//
//   node scripts/parity_classify.js backend/tests/fixtures/layer_corpus.json
//
// backend/tests/test_arch_rules.py runs this and asserts that
// backend/arch_rules.py produces identical output. If the frontend rules
// change without the backend changing, that test fails — which is the
// whole point: one rule table, two languages, zero drift.
const fs = require("fs");

const ASSET_MEDIA_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tif", ".tiff",
  ".svg", ".avif", ".heic",
  ".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".ogv",
  ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
  ".ttf", ".otf", ".woff", ".woff2", ".eot",
]);

const ASSET_DATA_EXTENSIONS = new Set([
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf", ".odt",
  ".ods", ".csv", ".tsv", ".parquet", ".avro",
]);

const ASSET_DOC_EXTENSIONS = new Set([
  ".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc", ".log",
]);

const ASSET_CONFIG_EXTENSIONS = new Set([
  ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".toml", ".xml", ".ini",
  ".cfg", ".conf", ".env", ".properties", ".lock",
]);

const ASSET_ARCHIVE_EXTENSIONS = new Set([
  ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".jar", ".war",
]);

const ASSET_DOTFILES = new Set([
  ".gitignore", ".gitattributes", ".gitmodules", ".editorconfig",
  ".dockerignore", ".npmrc", ".nvmrc", ".prettierrc", ".eslintrc",
  ".babelrc", ".stylelintrc", ".gitkeep", ".dockerfile",
]);

const ASSET_PROJECT_DOCUMENTS = new Set([
  "license", "licence", "notice", "authors", "contributors", "changelog",
  "readme", "copying", "codeowners",
]);

const BUILD_FILE_NAMES = new Set([
  "makefile", "dockerfile", "procfile", "rakefile", "gemfile", "justfile",
  "cmakelists.txt", "makefile.am", "makefile.in",
]);

const RULES = [
  { layer: "external", re: /(^|\/)(external|integrations?|sdk|providers?)(\/|$)|(^|[/._-])(api[_-]?client|http[_-]?client|webhooks?|oauth|payments?|stripe|slack|openai|anthropic)([/._-]|$)|(_|-)client\./ },
  { layer: "compute",  re: /(^|\/)(engines?|workers?|schedulers?|queues?|celery|cron|daemons?|consumers?|producers?|tasks?|algorithms?)([/._-]|$)/ },
  { layer: "storage",  re: /(^|\/)(models?|schemas?|migrations?|db|database|datastore|persistence|repositories?|store|storehouse)(\/|$)|\.(sql|db|sqlite)$/ },
  { layer: "backend",  re: /(^|\/)(backend|server|servers|services?|routers?|routes?|handlers?|controllers?|api|apis|middleware|main)(\/|$)|\.(py|go|java|rb|php|rs)$/ },
  { layer: "client",   re: /(^|\/)(frontend|client|src|components?|pages?|views?|screens?|ui|styles?|assets?|public)(\/|$)|\.(tsx|jsx|vue|svelte|css|scss|html|svg|png|jpg)$/ },
];

function extensionOf(path) {
  const name = path.replace(/\\/g, "/").split("/").pop() ?? "";
  if (!name.includes(".")) return "";
  if (name.startsWith(".") && name.split(".").length === 2) return "";
  return "." + name.split(".").pop().toLowerCase();
}

function fileNameOf(path) {
  return path.replace(/\\/g, "/").split("/").pop()?.toLowerCase() ?? "";
}

function assetLayer(path) {
  const extension = extensionOf(path);
  const name = fileNameOf(path);

  if (ASSET_MEDIA_EXTENSIONS.has(extension)) return "client";
  if (ASSET_DATA_EXTENSIONS.has(extension)) return "storage";
  if (ASSET_DOC_EXTENSIONS.has(extension)) return "storage";
  if (ASSET_CONFIG_EXTENSIONS.has(extension)) return "storage";
  if (ASSET_ARCHIVE_EXTENSIONS.has(extension)) return "storage";

  if (ASSET_DOTFILES.has(name)) return "storage";
  if (ASSET_PROJECT_DOCUMENTS.has(name)) return "storage";
  if (BUILD_FILE_NAMES.has(name)) return "backend";

  return null;
}

function classify(id, label) {
  // Non-code files first. Without this a PDF, a CSV, or a JSON manifest
  // falls through every rule and lands in "backend".
  //
  // The id and the label are checked SEPARATELY. They are joined with a
  // space for the path rules below, and a joined string breaks the "last
  // path segment" logic for a root-level file: "file:.gitignore
  // .gitignore" has no path separator, so its last segment is the whole
  // thing rather than ".gitignore".
  for (const candidate of [id, label]) {
    if (!candidate) continue;
    const asset = assetLayer(candidate);
    if (asset !== null) return asset;
  }

  const hay = `${id} ${label}`;
  for (const { layer, re } of RULES) if (re.test(hay)) return layer;
  if (/\.(tsx|jsx|ts|js|css|html|vue|svelte)$/i.test(hay)) return "client";
  return "backend";
}

const corpusPath = process.argv[2];
if (!corpusPath) {
  console.error("usage: node scripts/parity_classify.js <corpus.json>");
  process.exit(2);
}

const corpus = JSON.parse(fs.readFileSync(corpusPath, "utf8"));
const cases = Array.isArray(corpus) ? corpus : corpus.cases || [];
const out = cases.map(([id, label]) => classify(id, label));
process.stdout.write(JSON.stringify(out));
