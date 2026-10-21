// ── Layer classification (FILE 3: GitDiagram palette) ────────────────────────
// Classifies a graph node into one of five architecture layers using rules
// over its id + label. Colors sampled from the reference diagram — pastel
// fills with saturated borders. Do not invent new colors here.
//
// The rule table here is MIRRORED by backend/arch_rules.py, and
// backend/tests/test_arch_rules.py runs both over a shared corpus to prove
// they agree. If you change a rule here, change it there too — the parity
// test will fail otherwise.

export type Layer = "client" | "backend" | "storage" | "external" | "compute";

export interface LayerStyle {
  fill: string;
  border: string;
  text: string;
  icon: string;   // lucide icon name key — resolved in LayerNode
  name: string;
}

export const LAYER_STYLE: Record<Layer, LayerStyle> = {
  client:   { fill: "#DBEAFE", border: "#2563EB", text: "#1E3A8A", icon: "monitor",  name: "Client / UI" },
  backend:  { fill: "#FEF3C7", border: "#D97706", text: "#78350F", icon: "server",   name: "Backend / API" },
  storage:  { fill: "#D1FAE5", border: "#059669", text: "#065F46", icon: "database", name: "Storage / Data" },
  external: { fill: "#FEE2E2", border: "#DC2626", text: "#991B1B", icon: "globe",    name: "External / Integrations" },
  compute:  { fill: "#EDE9FE", border: "#7C3AED", text: "#4C1D95", icon: "cpu",      name: "Compute / Workers" },
};

// ── Non-code files ─────────────────────────────────────────────────────────
//
// The rules below were written for SOURCE CODE, but they were applied to
// every file in the repository — so a PDF in a data folder fell through
// every rule and landed in "backend". Measured on a real 154-file
// repository, 53 of 154 files (34%) were misclassified: every PDF,
// spreadsheet, CSV, markdown file, and JSON manifest.
//
// A non-code file is not part of the system's architecture. It is data, a
// document, a config file, or a media asset — and its KIND says which.
// The extension decides, not the directory: a PDF is data wherever it
// lives.

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

// ── Ordered rules — first match wins. Mirrored in arch_rules.py. ───────────
//
// The generic words are anchored to path/word boundaries. The previous
// patterns matched them anywhere in the string, so `myengineer.py` counted
// as "compute" and `notpayment.py` counted as "external".
const RULES: Array<{ layer: Layer; re: RegExp }> = [
  // api clients, sdk, integrations, providers
  { layer: "external", re: /(^|\/)(external|integrations?|sdk|providers?)(\/|$)|(^|[/._-])(api[_-]?client|http[_-]?client|webhooks?|oauth|payments?|stripe|slack|openai|anthropic)([/._-]|$)|(_|-)client\./ },
  // engines, workers, schedulers, queues
  { layer: "compute",  re: /(^|\/)(engines?|workers?|schedulers?|queues?|celery|cron|daemons?|consumers?|producers?|tasks?|algorithms?)([/._-]|$)/ },
  // models, schemas, migrations, db, persistence
  { layer: "storage",  re: /(^|\/)(models?|schemas?|migrations?|db|database|datastore|persistence|repositories?|store|storehouse)(\/|$)|\.(sql|db|sqlite)$/ },
  // backend, server, services, routers, handlers
  { layer: "backend",  re: /(^|\/)(backend|server|servers|services?|routers?|routes?|handlers?|controllers?|api|apis|middleware|main)(\/|$)|\.(py|go|java|rb|php|rs)$/ },
  // frontend, client, src, components, pages, styles
  { layer: "client",   re: /(^|\/)(frontend|client|src|components?|pages?|views?|screens?|ui|styles?|assets?|public)(\/|$)|\.(tsx|jsx|vue|svelte|css|scss|html|svg|png|jpg)$/ },
];

/**
 * The lower-cased extension of a path, including the dot.
 *
 * A dotfile such as `.gitignore` has no extension — the dot is the name,
 * not a separator. A file named `School-Energy-Bills.pdf` has `.pdf`.
 */
function extensionOf(path: string): string {
  const name = path.replace(/\\/g, "/").split("/").pop() ?? "";
  if (!name.includes(".")) return "";
  if (name.startsWith(".") && name.split(".").length === 2) return "";
  return "." + name.split(".").pop()!.toLowerCase();
}

/** The final path segment, lower-cased. */
function fileNameOf(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop()?.toLowerCase() ?? "";
}

/**
 * Classify a non-code file, or return null when the file is code.
 *
 * The extension decides, not the directory: a PDF is data wherever it
 * lives, and an image is a media asset wherever it lives.
 *
 *   media                          -> client  (served to the browser)
 *   data, document, config, archive-> storage (inputs, outputs, manifests)
 */
function assetLayer(path: string): Layer | null {
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

/**
 * Classify a node into its architecture layer from its id + label.
 *
 * Extension-based fallback when no ordered rule matches.
 */
export function classify(id: string, label: string): Layer {
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
  for (const { layer, re } of RULES) {
    if (re.test(hay)) return layer;
  }
  // Extension-based fallback when no ordered rule matches.
  if (/\.(tsx|jsx|ts|js|css|html|vue|svelte)$/i.test(hay)) return "client";
  return "backend";
}
