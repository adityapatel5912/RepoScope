/**
 * openInEditor.ts
 * Open a file in the user's editor — or explain why we cannot.
 *
 * Milestone 2.1. The interesting case is the failure case.
 *
 * In **local mode** (`reposcope run .`) the backend knows the absolute
 * path of the checkout, because it is reading it off the disk. So the
 * link works with no configuration at all.
 *
 * In **web mode** the backend has never seen the user's files, so a
 * repo-relative path means nothing on their machine. The workspace root
 * from the settings is what bridges the gap — and when it is missing,
 * the right behaviour is to COPY the path and say why, not to open a
 * wrong file or fail silently.
 */
import { toast } from "../components/Toasts";
import {
  buildEditorUri,
  loadIdePrefs,
  resolveWorkspaceRoot,
  type OpenTarget,
} from "./ideLinks";

export interface OpenResult {
  /** True when the editor was launched. */
  opened: boolean;
  /** Why it was not, when it was not. */
  reason?: "no-root" | "declined";
  /** The URI that was used, for tests and for the "copy link" action. */
  uri?: string;
}

/**
 * Build the URI for a target, using the best available root.
 *
 * `localRoot` is the absolute path the backend reported for the loaded
 * repository. It wins over the user's configured workspace root, because
 * it is the repository the graph actually describes.
 */
export function buildOpenUri(
  target: OpenTarget,
  localRoot?: string | null,
  editorOverride?: string,
): { uri: string | null; reason?: "no-root" } {
  const prefs = loadIdePrefs();
  const editor = (editorOverride ?? prefs.editor) as OpenTarget extends never
    ? never
    : Parameters<typeof buildEditorUri>[0];

  const root = localRoot?.trim() || prefs.workspaceRoot?.trim() || "";
  const absolute = resolveWorkspaceRoot(target.path, root);
  if (!absolute) {
    return { uri: null, reason: "no-root" };
  }

  return {
    uri: buildEditorUri(editor, absolute, target.line ?? 0, target.col ?? 0, {
      project: root.split(/[\\/]/).filter(Boolean).pop() ?? "project",
    }),
  };
}

/**
 * Open a file in the editor.
 *
 * Navigates to the editor's URI. When the path cannot be resolved, the
 * path is copied to the clipboard instead — the user can always paste it
 * into their editor, and they are told why the direct link did not
 * work.
 */
export async function openInEditor(
  target: OpenTarget,
  localRoot?: string | null,
): Promise<OpenResult> {
  const { uri } = buildOpenUri(target, localRoot);

  if (!uri) {
    try {
      await navigator.clipboard.writeText(target.path);
      toast.success(
        `Copied ${target.path} — set a workspace root in Settings to open it directly`,
      );
    } catch {
      toast.error(`Could not copy ${target.path}. Set a workspace root in Settings.`);
    }
    return { opened: false, reason: "no-root" };
  }

  window.location.href = uri;

  // The event fires BEFORE the navigation, so a listener can observe
  // the exact URI that was used. The VS Code extension's webview uses
  // it to open the file itself; the QA journey uses it to assert that
  // the link is correct without needing a registered protocol handler.
  window.dispatchEvent(
    new CustomEvent("reposcope:open-editor", {
      detail: { uri, path: target.path, line: target.line ?? 0 },
    }),
  );

  return { opened: true, uri };
}
