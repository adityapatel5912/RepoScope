/**
 * statusBar.ts
 * The blast-radius indicator.
 *
 * `RepoScope: ⚠️ 12 dependents | Risk: Med`
 *
 * The point is that the cost of a change is visible BEFORE you make it.
 * A developer opening a file has not decided to edit it yet — they are
 * deciding whether to. Showing them that 12 files depend on it at that
 * moment is the difference between an informed decision and a surprised
 * one.
 *
 * The item updates when the active editor changes. The roadmap's
 * acceptance is "within 1s of switching tabs", so the update is fired
 * immediately and the previous request is abandoned rather than queued.
 */
import * as vscode from "vscode";
import { GraphClient } from "./graphClient";
import { formatStatusText, formatStatusTooltip } from "./model";

/** The risk levels, in the order they escalate. */
export const RISK_ORDER = ["unknown", "low", "medium", "high", "critical"];

export class StatusBarController {
  private readonly item: vscode.StatusBarItem;
  private readonly client: GraphClient;
  private token = 0;

  constructor(client: GraphClient) {
    this.client = client;
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100,
    );
    this.item.command = "reposcope.showBlastRadius";
    this.item.text = "RepoScope: …";
    this.item.show();
  }

  dispose(): void {
    this.item.dispose();
  }

  /** Refresh for the given file (a repo-relative path), or hide. */
  async update(file: string | null): Promise<void> {
    const current = ++this.token;

    if (!file) {
      this.item.text = "RepoScope: no file";
      this.item.tooltip = "Open a source file to see its blast radius.";
      return;
    }

    try {
      const result = await this.client.getDependents(file);
      // A newer request has already started — this answer is stale.
      if (current !== this.token) return;

      if (!result.available || !result.found) {
        this.item.text = "RepoScope: no index";
        this.item.tooltip =
          "The RepoScope backend has no index for this file. " +
          "Run `reposcope run .` in your repository.";
        return;
      }

      this.item.text = formatStatusText(result.dependents, result.risk);
      this.item.tooltip = formatStatusTooltip(result);
      this.item.backgroundColor =
        RISK_ORDER.indexOf(result.risk) >= RISK_ORDER.indexOf("high")
          ? new vscode.ThemeColor("statusBarItem.warningBackground")
          : undefined;
    } catch {
      if (current !== this.token) return;
      this.item.text = "RepoScope: offline";
      this.item.tooltip =
        "Could not reach the RepoScope backend.\nStart one with: reposcope run .";
    }
  }
}
