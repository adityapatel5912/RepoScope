/**
 * codeLens.ts
 * "View Callers (8)" above every exported symbol.
 *
 * The count is the graph's, not a guess. It comes from the same
 * `calls` edges the MCP tool reads, so the number in the editor and the
 * number an agent reports are the same number. An extension that said
 * "8" when the graph said 3 would be worse than no extension.
 *
 * The lens is only offered on symbols the graph knows about — a file
 * that has not been indexed shows nothing, rather than a misleading
 * zero.
 */
import * as vscode from "vscode";
import { GraphClient } from "./graphClient";
import { candidateSymbols, callersLensText, isDefinitionLine } from "./model";

/** The languages RepoScope parses with an AST. */
export const SUPPORTED_LANGUAGES = [
  "python", "typescript", "typescriptreact", "javascript", "javascriptreact",
  "go", "rust",
];

export class CallerCodeLensProvider implements vscode.CodeLensProvider {
  private readonly emitter = new vscode.EventEmitter<void>();
  readonly onDidChangeCodeLenses = this.emitter.event;

  constructor(private readonly client: GraphClient) {}

  refresh(): void {
    this.emitter.fire();
  }

  dispose(): void {
    this.emitter.dispose();
  }

  async provideCodeLenses(
    document: vscode.TextDocument,
    _token: vscode.CancellationToken,
  ): Promise<vscode.CodeLens[]> {
    if (!SUPPORTED_LANGUAGES.includes(document.languageId)) return [];

    const relative = relativePath(document);
    if (!relative) return [];

    const lenses: vscode.CodeLens[] = [];

    for (let lineNumber = 0; lineNumber < document.lineCount; lineNumber++) {
      const line = document.lineAt(lineNumber).text;
      if (!isDefinitionLine(line)) continue;

      const names = candidateSymbols(line);
      if (names.length === 0) continue;

      for (const name of names) {
        let result;
        try {
          result = await this.client.getCallers(relative, name);
        } catch {
          // The backend is down. Showing no lens is the honest answer;
          // showing "0 callers" would be a lie.
          return lenses;
        }
        if (!result.available || !result.found) continue;

        lenses.push(
          new vscode.CodeLens(new vscode.Range(lineNumber, 0, lineNumber, 0), {
            title: callersLensText(result.count),
            command: "reposcope.showCallers",
            arguments: [relative, name, result.count],
          }),
        );
        break;  // one lens per definition line
      }
    }

    return lenses;
  }
}

/** The repo-relative path of a document, using the workspace root. */
export function relativePath(document: vscode.TextDocument): string | null {
  const folder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!folder) return null;
  const relative = vscode.workspace.asRelativePath(document.uri, false);
  return relative.replace(/\\/g, "/");
}
