/**
 * ideLinks.ts
 * Universal IDE protocol handlers.
 *
 * Milestone 2.1. The graph is the map; the editor is where the work
 * happens. Clicking a node should put the cursor on that exact line in
 * the user's editor, in whatever editor they use — and if we do not know
 * where their code is, we should say so and give them the path instead
 * of failing silently.
 *
 * These are PURE functions. No React, no DOM, no browser APIs — so they
 * can be unit-tested directly, and so the same logic can be reused by
 * the VS Code extension.
 *
 * The URI formats:
 *
 *   VS Code             vscode://file/{abs}:{line}:{col}
 *   VS Code Insiders    vscode-insiders://file/{abs}:{line}:{col}
 *   Cursor              cursor://file/{abs}:{line}:{col}
 *   JetBrains           jetbrains://idea/navigate/reference?project={proj}&path={rel}:{line}
 *   Sublime Text        subl://open?url=file://{abs}&line={line}
 */

export type EditorId =
  | "vscode"
  | "vscode-insiders"
  | "cursor"
  | "jetbrains"
  | "sublime";

export interface EditorDescriptor {
  id: EditorId;
  name: string;
  /** The URI scheme the editor registers. */
  scheme: string;
  /** A one-line note about where this editor lives. */
  hint: string;
}

export const EDITORS: EditorDescriptor[] = [
  {
    id: "vscode",
    name: "VS Code",
    scheme: "vscode",
    hint: "code --goto {file}:{line}",
  },
  {
    id: "vscode-insiders",
    name: "VS Code Insiders",
    scheme: "vscode-insiders",
    hint: "code-insiders --goto {file}:{line}",
  },
  {
    id: "cursor",
    name: "Cursor",
    scheme: "cursor",
    hint: "cursor --goto {file}:{line}",
  },
  {
    id: "jetbrains",
    name: "JetBrains IDEs",
    scheme: "jetbrains",
    hint: "IntelliJ · PyCharm · WebStorm · GoLand",
  },
  {
    id: "sublime",
    name: "Sublime Text",
    scheme: "subl",
    hint: "subl {file}:{line}",
  },
];

export const DEFAULT_EDITOR: EditorId = "vscode";

/**
 * The project's own URI scheme — the web app's link INTO an editor.
 *
 * The VS Code extension registers a handler for `reposcope://open`, so a
 * code-tour step in the browser can open the exact file and line in the
 * editor. This is the loop: map → code → agent.
 */
export const REPOSCOPE_SCHEME = "reposcope";

export interface OpenTarget {
  /** The repository-relative path. */
  path: string;
  /** A 1-based line number, or 0 for "no line". */
  line?: number;
  /** A 1-based column, or 0. */
  col?: number;
}

/**
 * Build the URI that opens a file in an editor.
 *
 * The absolute path is required by every protocol except JetBrains,
 * which takes a project-relative path plus a project name.
 */
export function buildEditorUri(
  editor: EditorId,
  absPath: string,
  line = 0,
  col = 0,
  options: { project?: string } = {},
): string {
  const normalised = absPath.replace(/\\/g, "/");
  const safeLine = Math.max(0, Math.floor(line || 0));
  const safeCol = Math.max(0, Math.floor(col || 0));

  switch (editor) {
    case "vscode":
    case "vscode-insiders":
    case "cursor":
      // The scheme IS the editor's id for these three.
      return `${editor}://file/${normalised}:${safeLine}:${safeCol}`;

    case "jetbrains": {
      const project = options.project ?? "project";
      // JetBrains wants the path RELATIVE to the project root.
      const relative = normalised.replace(/^\/+/, "");
      const encoded = encodeURIComponent(`${relative}:${safeLine}`);
      return `jetbrains://idea/navigate/reference?project=${encodeURIComponent(project)}&path=${encoded}`;
    }

    case "sublime":
      return `subl://open?url=file://${normalised}&line=${safeLine}`;

    default:
      return `vscode://file/${normalised}:${safeLine}:${safeCol}`;
  }
}

/**
 * Resolve a repository-relative path against a workspace root.
 *
 * Returns null when there is no root — the caller must then fall back
 * to copying the path rather than opening a wrong file.
 */
export function resolveWorkspaceRoot(
  relPath: string,
  workspaceRoot: string | null | undefined,
): string | null {
  if (!workspaceRoot || !workspaceRoot.trim()) return null;
  if (!relPath) return null;
  const root = workspaceRoot.replace(/[\\/]+$/, "");
  const rel = relPath.replace(/^[\\/]+/, "").replace(/\\/g, "/");
  if (!root) return null;
  // Windows: `C:/src` + `app.py` → `C:/src/app.py`.
  return `${root}/${rel}`;
}

/**
 * Build a `reposcope://open` URI — the web app's link into an editor.
 *
 * The VS Code extension registers a URI handler for this scheme, so a
 * click in the browser lands in the editor on the right line.
 */
export function buildRepoScopeUri(target: OpenTarget): string {
  const params = new URLSearchParams();
  params.set("path", target.path);
  if (target.line) params.set("line", String(target.line));
  if (target.col) params.set("col", String(target.col));
  return `${REPOSCOPE_SCHEME}://open?${params.toString()}`;
}

/** Parse a `reposcope://open` URI back into a target. */
export function parseRepoScopeUri(
  uri: string,
): { path: string; line: number; col: number } | null {
  if (!uri || !uri.toLowerCase().startsWith(`${REPOSCOPE_SCHEME}://`)) return null;
  try {
    const url = new URL(uri);
    const path = url.searchParams.get("path");
    if (!path) return null;
    return {
      path,
      line: Number(url.searchParams.get("line") ?? 0) || 0,
      col: Number(url.searchParams.get("col") ?? 0) || 0,
    };
  } catch {
    return null;
  }
}

/** The label of an editor, for the UI. */
export function editorName(editor: EditorId): string {
  return EDITORS.find((e) => e.id === editor)?.name ?? "VS Code";
}

// ── Persisted preferences ───────────────────────────────────────────────────

export const IDE_PREFS_KEY = "reposcope-ide-prefs";

export interface IdePrefs {
  /** The editor the user prefers. */
  editor: EditorId;
  /** The absolute path of the checkout on this machine. */
  workspaceRoot: string;
  /** Ask before opening, rather than opening straight away. */
  alwaysAsk: boolean;
}

export function loadIdePrefs(): IdePrefs {
  const fallback: IdePrefs = {
    editor: DEFAULT_EDITOR,
    workspaceRoot: "",
    alwaysAsk: false,
  };
  try {
    const raw = localStorage.getItem(IDE_PREFS_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<IdePrefs>;
    return {
      editor: (parsed.editor as EditorId) ?? fallback.editor,
      workspaceRoot: parsed.workspaceRoot ?? fallback.workspaceRoot,
      alwaysAsk: parsed.alwaysAsk ?? fallback.alwaysAsk,
    };
  } catch {
    return fallback;
  }
}

export function saveIdePrefs(prefs: IdePrefs): void {
  try {
    localStorage.setItem(IDE_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable — the preference just will not persist */
  }
}
