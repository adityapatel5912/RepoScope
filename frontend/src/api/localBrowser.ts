/**
 * localBrowser.ts
 * The EXPERIMENTAL in-browser path.
 *
 * Milestone 2.3, and Correction C8: "Optional and clearly labelled
 * experimental. Sequence it AFTER the native path is fully working, and
 * mark it experimental in the UI."
 *
 * The promise is the strongest privacy claim the product can make:
 *
 *     **No source code leaves the browser.**
 *
 * The directory is read through the File System Access API, parsed in
 * the browser with Tree-sitter compiled to WebAssembly, and the graph is
 * built here. Nothing is uploaded, and the backend is never told the
 * directory's name.
 *
 * **What it is not.** The graph built here is simpler than the native
 * one: the same Tree-sitter grammars, but a lighter resolution pass —
 * imports are detected, symbols are extracted, and the file-level
 * dependency edges are built. It does NOT do the cross-file symbol
 * resolution the server does, so the call graph is thinner.
 *
 * That is stated in the UI, next to the button, because a privacy
 * feature that quietly produces a worse answer is a trap.
 */
/**
 * The Tree-sitter WASM runtime, loaded ON DEMAND.
 *
 * This is an experimental feature, and its runtime is ~200 KB of
 * JavaScript. Bundling it into the main chunk would make every user pay
 * for a path 99% of them will never take. The dynamic import means it
 * is fetched when — and only when — somebody clicks "Choose a folder".
 */
type TreeSitter = typeof import("web-tree-sitter");

let treeSitter: TreeSitter | null = null;

async function getTreeSitter(): Promise<TreeSitter | null> {
  if (treeSitter) return treeSitter;
  try {
    const module = await import("web-tree-sitter");
    await module.Parser.init({
      // The Emscripten runtime lives in `public/grammars/`, so it is
      // served by Vite rather than bundled.
      locateFile: (path: string) =>
        path.endsWith(".wasm") ? "/grammars/web-tree-sitter.wasm" : path,
    });
    treeSitter = module;
    return module;
  } catch (exc) {
    console.error("RepoScope: the in-browser parser could not be loaded.", exc);
    return null;
  }
}

/** The languages the in-browser path can parse. */
const GRAMMARS: Record<string, string> = {
  ".py": "python",
  ".pyi": "python",
  ".js": "javascript",
  ".jsx": "javascript",
  ".mjs": "javascript",
  ".ts": "typescript",
  ".tsx": "typescript",
  ".go": "go",
  ".rs": "rust",
};

/** The directories never descended into. */
const SKIP_DIRS = new Set([
  "node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv",
  "target", ".next", ".nuxt", "vendor", ".reposcope", ".idea", ".vscode",
]);

/** How many files the in-browser parse will read. */
const MAX_FILES = 3000;

export interface BrowserNode {
  id: string;
  type: "file" | "function" | "class";
  label: string;
  file: string;
  line: number;
  size: number;
}

export interface BrowserEdge {
  source: string;
  target: string;
  type: "contains" | "imports";
}

export interface BrowserGraph {
  nodes: BrowserNode[];
  edges: BrowserEdge[];
  summary: string;
  files: number;
  /** The languages that were actually parsed. */
  languages: string[];
  /** The files that could not be parsed. */
  skipped: number;
}

/** Is the File System Access API available? */
export function supportsFileSystemAccess(): boolean {
  return typeof window !== "undefined" && "showDirectoryPicker" in window;
}

/** The directories the user picked, as a list of {path, handle}. */
export interface PickedFile {
  /** The path relative to the picked directory. */
  path: string;
  file: File;
}

interface FileSystemDirectoryHandle {
  kind: "directory";
  name: string;
  values(): AsyncIterableIterator<FileSystemDirectoryHandle | FileSystemFileHandle>;
}

interface FileSystemFileHandle {
  kind: "file";
  name: string;
  getFile(): Promise<File>;
}

/** Ask the user for a directory. Returns null when they decline. */
export async function pickDirectory(): Promise<FileSystemDirectoryHandle | null> {
  if (!supportsFileSystemAccess()) return null;
  try {
    const handle = await (
      window as unknown as {
        showDirectoryPicker(options?: { mode?: string }): Promise<FileSystemDirectoryHandle>;
      }
    ).showDirectoryPicker({ mode: "read" });
    return handle;
  } catch {
    // The user dismissed the picker. That is not an error.
    return null;
  }
}

/** Walk the picked directory and collect the source files. */
export async function collectFiles(
  root: FileSystemDirectoryHandle,
  maxFiles = MAX_FILES,
): Promise<{ files: PickedFile[]; skipped: number }> {
  const files: PickedFile[] = [];
  let skipped = 0;

  async function walk(
    handle: FileSystemDirectoryHandle,
    prefix: string,
  ): Promise<void> {
    if (files.length >= maxFiles) return;
    for await (const entry of handle.values()) {
      if (files.length >= maxFiles) return;
      if (entry.kind === "directory") {
        if (SKIP_DIRS.has(entry.name)) {
          skipped += 1;
          continue;
        }
        await walk(entry as FileSystemDirectoryHandle, `${prefix}${entry.name}/`);
      } else {
        const file = await (entry as FileSystemFileHandle).getFile();
        files.push({ path: `${prefix}${entry.name}`, file });
      }
    }
  }

  await walk(root, "");
  return { files, skipped };
}

// ── The Tree-sitter extraction ──────────────────────────────────────────────

/** The queries, per language. A query naming a node type the grammar
 * lacks fails to compile, so each language gets its own. */
const SYMBOL_QUERIES: Record<string, string> = {
  python: `
    (function_definition name: (identifier) @name) @def
    (class_definition name: (identifier) @name) @def
  `,
  javascript: `
    (function_declaration name: (identifier) @name) @def
    (class_declaration name: (identifier) @name) @def
  `,
  typescript: `
    (function_declaration name: (identifier) @name) @def
    (class_declaration name: (type_identifier) @name) @def
  `,
  go: `
    (function_declaration name: (identifier) @name) @def
    (type_declaration (type_spec name: (type_identifier) @name)) @def
  `,
  rust: `
    (function_item name: (identifier) @name) @def
    (struct_item name: (type_identifier) @name) @def
  `,
};

const IMPORT_QUERIES: Record<string, string> = {
  python: `
    (import_statement name: (dotted_name) @module)
    (import_from_statement) @imp
  `,
  javascript: `
    (import_statement source: (string) @module)
    (export_statement source: (string) @module)
  `,
  typescript: `
    (import_statement source: (string) @module)
    (export_statement source: (string) @module)
  `,
  go: `
    (import_spec path: (interpreted_string_literal) @module)
  `,
  rust: `
    (use_declaration argument: (_) @module)
  `,
};

const parsers = new Map<string, any>();
const languages = new Set<string>();

async function getParser(language: string): Promise<any | null> {
  const cached = parsers.get(language);
  if (cached) return cached;

  const ts = await getTreeSitter();
  if (!ts) return null;

  try {
    const loaded = await ts.Language.load(`/grammars/tree-sitter-${language}.wasm`);
    const parser = new ts.Parser();
    parser.setLanguage(loaded);
    parsers.set(language, parser);
    languages.add(language);
    return parser;
  } catch (exc) {
    console.warn(`RepoScope: the ${language} grammar could not be loaded.`, exc);
    return null;
  }
}

function textOf(node: { text: string }): string {
  return node.text.replace(/^['"`]|['"`]$/g, "");
}

/** The import specifiers in a file. */
async function extractImports(language: string, tree: any): Promise<string[]> {
  const source = IMPORT_QUERIES[language];
  if (!source) return [];
  const ts = await getTreeSitter();
  if (!ts) return [];
  const out: string[] = [];
  try {
    const query = new ts.Query(tree.language, source);
    // web-tree-sitter 0.25 returns a flat array of captures, each with
    // its capture name — not the dict the Python API returns.
    const captures = query.captures(tree.rootNode);
    for (const capture of captures) {
      if (capture.name === "module") {
        out.push(textOf(capture.node));
      }
    }
    // Python's `from X import Y` — the module is the child before the
    // `import` keyword, and the grammar has no field for it.
    for (const capture of captures) {
      if (capture.name !== "imp") continue;
      const imp = capture.node;
      let module = "";
      for (const child of imp.children) {
        if (!child) continue;
        if (child.type === "import") break;
        if (child.type === "dotted_name" || child.type === "relative_import") {
          module = child.text;
        }
      }
      if (module) out.push(module);
    }
  } catch (exc) {
    console.warn("RepoScope: the import query failed.", exc);
  }
  return out;
}

/** The symbol names in a file. */
async function extractSymbols(
  language: string,
  tree: any,
): Promise<{ name: string; line: number; kind: string }[]> {
  const source = SYMBOL_QUERIES[language];
  if (!source) return [];
  const ts = await getTreeSitter();
  if (!ts) return [];
  const out: { name: string; line: number; kind: string }[] = [];
  try {
    const query = new ts.Query(tree.language, source);
    const captures = query.captures(tree.rootNode);
    const names = captures.filter((c: any) => c.name === "name").map((c: any) => c.node);
    const defs = captures.filter((c: any) => c.name === "def").map((c: any) => c.node);
    for (const def of defs) {
      const name = names.find(
        (n: any) => n.startIndex >= def.startIndex && n.endIndex <= def.endIndex,
      );
      if (!name) continue;
      out.push({
        name: name.text,
        line: name.startPosition.row + 1,
        kind: def.type.includes("class") ? "class" : "function",
      });
    }
  } catch (exc) {
    console.warn("RepoScope: the symbol query failed.", exc);
  }
  return out;
}

/** Resolve an import specifier to a repo-relative path, or null. */
function resolveImport(
  language: string,
  spec: string,
  importerPath: string,
  knownFiles: Set<string>,
): string | null {
  if (language === "python") {
    const candidate = spec
      .replace(/^\./, "")
      .replace(/\./g, "/")
      .replace(/^\//, "");
    if (!candidate) return null;
    for (const suffix of [".py", "/__init__.py"]) {
      const path = candidate + suffix;
      if (knownFiles.has(path)) return path;
    }
    return null;
  }
  if (language === "go" || language === "rust") {
    // Package paths, not repo paths. Not resolvable to a file.
    return null;
  }
  // JavaScript / TypeScript
  if (!spec.startsWith(".")) return null;
  const base = importerPath.split("/").slice(0, -1).join("/");
  const joined = `${base}/${spec}`.replace(/\/\.\//g, "/").replace(/\/\.$/, "");
  const normalised = joined
    .split("/")
    .reduce<string[]>((parts, part) => {
      if (part === "..") parts.pop();
      else if (part !== ".") parts.push(part);
      return parts;
    }, [])
    .join("/");
  for (const suffix of [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]) {
    const path = normalised + suffix;
    if (knownFiles.has(path)) return path;
  }
  return null;
}

/**
 * Parse a directory in the browser and build the graph.
 *
 * Nothing leaves the browser: the files are read through the File
 * System Access handle and parsed here.
 */
export async function buildGraphInBrowser(
  root: FileSystemDirectoryHandle,
): Promise<BrowserGraph> {
  const ts = await getTreeSitter();
  if (!ts) {
    return {
      nodes: [], edges: [], summary: "the in-browser parser could not be loaded",
      files: 0, languages: [], skipped: 0,
    };
  }

  const { files, skipped } = await collectFiles(root);
  const sourceFiles = files.filter((f) => GRAMMARS[f.path.split(".").pop() ? `.${f.path.split(".").pop()}` : ""]);
  const knownFiles = new Set(sourceFiles.map((f) => f.path));

  const nodes: BrowserNode[] = [];
  const edges: BrowserEdge[] = [];
  const parsedLanguages = new Set<string>();

  for (const entry of sourceFiles) {
    const extension = entry.path.slice(entry.path.lastIndexOf("."));
    const language = GRAMMARS[extension];
    if (!language) continue;

    const parser = await getParser(language);
    if (!parser) continue;

    let source: string;
    try {
      source = await entry.file.text();
    } catch {
      continue;
    }

    const fileId = `file:${entry.path}`;
    nodes.push({
      id: fileId,
      type: "file",
      label: entry.path,
      file: entry.path,
      line: 0,
      size: entry.file.size,
    });
    parsedLanguages.add(language);

    let tree: any;
    try {
      tree = parser.parse(source);
    } catch {
      continue;
    }
    if (!tree) continue;

    for (const symbol of await extractSymbols(language, tree)) {
      const symbolId = `${symbol.kind === "class" ? "class" : "func"}:${entry.path}:${symbol.name}`;
      nodes.push({
        id: symbolId,
        type: symbol.kind === "class" ? "class" : "function",
        label: symbol.name,
        file: entry.path,
        line: symbol.line,
        size: 0,
      });
      edges.push({ source: fileId, target: symbolId, type: "contains" });
    }

    for (const spec of await extractImports(language, tree)) {
      const target = resolveImport(language, spec, entry.path, knownFiles);
      if (!target) continue;
      edges.push({ source: fileId, target: `file:${target}`, type: "imports" });
    }
  }

  // Dedupe the edges.
  const seen = new Set<string>();
  const uniqueEdges = edges.filter((edge) => {
    const key = `${edge.source}|${edge.target}|${edge.type}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return {
    nodes,
    edges: uniqueEdges,
    summary: `${nodes.length} nodes, ${uniqueEdges.length} edges`,
    files: sourceFiles.length,
    languages: [...parsedLanguages],
    skipped,
  };
}
