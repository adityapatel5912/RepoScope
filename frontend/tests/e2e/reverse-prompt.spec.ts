/**
 * reverse-prompt.spec.ts
 * E2E tests for Phase 6: Four-mode reverse-prompt compiler (V2.6).
 *
 * Verifies:
 * - Opening the Reverse-Prompt modal from Graph Controls
 * - Four blueprint modes: Context Pack, Rebuild Blueprint, Feature Slice, Spec Bundle
 * - Dynamic mode switching and deterministic token / file badges
 * - Spec mode multi-file tabs and file switching
 * - Copy to clipboard functionality
 * - Download / save as .md functionality
 * - Zero un-whitelisted console errors
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 6 — Four-Mode Reverse-Prompt Compiler", () => {
  test("RP01 — opens modal, switches between all 4 modes, verifies badges, copy, and download", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    try {
      await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
    } catch {
      // Ignore if permissions not supported
    }

    // Mock reverse-prompt endpoint with deterministic 4-mode payloads
    await page.route("**/api/repo/reverse-prompt", async (route) => {
      const postData = route.request().postDataJSON() || {};
      const mode = postData.mode || "context";

      if (mode === "rebuild") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            mode: "rebuild",
            content: "# System Rebuild Blueprint: RepoScope\n\n## 1. Stack & Architecture\n- Languages: Python, TypeScript\n\n## 2. Topological Build Order\n1. `backend/token_metrics.py`\n2. `backend/reverse_prompt_compiler.py`",
            prompt: "# System Rebuild Blueprint: RepoScope\n\n## 1. Stack & Architecture\n- Languages: Python, TypeScript\n\n## 2. Topological Build Order\n1. `backend/token_metrics.py`\n2. `backend/reverse_prompt_compiler.py`",
            tokens: 2450,
            files: [{ path: "BLUEPRINT.md", content: "# System Rebuild Blueprint: RepoScope" }],
            warnings: [],
          }),
        });
      } else if (mode === "feature") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            mode: "feature",
            content: "# Feature Slice: `reverse_prompt_compiler`\n\n## 1. Target Details\n- ID: `backend/reverse_prompt_compiler.py`\n\n## 2. 2-Hop Interface Closure (12 nodes, 18 edges)",
            prompt: "# Feature Slice: `reverse_prompt_compiler`\n\n## 1. Target Details\n- ID: `backend/reverse_prompt_compiler.py`\n\n## 2. 2-Hop Interface Closure (12 nodes, 18 edges)",
            tokens: 1120,
            files: [{ path: "FEATURE_reverse_prompt_compiler.md", content: "# Feature Slice: `reverse_prompt_compiler`" }],
            warnings: [],
          }),
        });
      } else if (mode === "spec") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            mode: "spec",
            content: "# CLAUDE.md\nBuild & test commands\n\n---\n\n# AGENTS.md\nAutonomous agent work agreement",
            prompt: "# CLAUDE.md\nBuild & test commands\n\n---\n\n# AGENTS.md\nAutonomous agent work agreement",
            tokens: 3200,
            files: [
              { path: "CLAUDE.md", content: "# CLAUDE.md guidelines for RepoScope" },
              { path: "AGENTS.md", content: "# AGENTS.md agent rules" },
              { path: "llms.txt", content: "# llms.txt repo manifest" },
              { path: ".kiro/specs/architecture.md", content: "# Architecture specification" },
            ],
            warnings: [],
          }),
        });
      } else {
        // default: context
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            mode: "context",
            content: "# Repository Context Pack: RepoScope\nDetail: skeleton | Budget: 8000 tokens | Files: 12",
            prompt: "# Repository Context Pack: RepoScope\nDetail: skeleton | Budget: 8000 tokens | Files: 12",
            tokens: 1400,
            files: [],
            warnings: [],
          }),
        });
      }
    });

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // Click "Build Prompt" button in GraphControls
    const buildPromptBtn = page.locator("button[aria-label='Generate Build Prompt']");
    await expect(buildPromptBtn).toBeVisible({ timeout: 10000 });
    await buildPromptBtn.click();

    // Verify modal is open
    const modal = page.locator("[data-testid='reverse-prompt-modal']");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Verify initial Context Pack content and token badge
    const textarea = page.locator("[data-testid='reverse-prompt-textarea']");
    await expect(textarea).toBeVisible();
    await expect(textarea).toHaveValue(/Repository Context Pack/i);

    const tokenBadge = page.locator("[data-testid='token-count-badge']");
    await expect(tokenBadge).toBeVisible();
    await expect(tokenBadge).toContainText("tokens");

    // Switch to Rebuild Blueprint mode
    const rebuildTab = page.locator("[data-testid='mode-tab-rebuild']");
    await rebuildTab.click();
    await expect(textarea).toHaveValue(/Topological Build Order/i, { timeout: 5000 });
    await expect(tokenBadge).toContainText("2,450");

    // Switch to Feature Slice mode
    const featureTab = page.locator("[data-testid='mode-tab-feature']");
    await featureTab.click();
    await expect(textarea).toHaveValue(/Feature Slice/i, { timeout: 5000 });
    await expect(tokenBadge).toContainText("1,120");

    // Switch to Spec Bundle mode
    const specTab = page.locator("[data-testid='mode-tab-spec']");
    await specTab.click();
    await expect(tokenBadge).toContainText("3,200", { timeout: 5000 });

    // Verify Spec mode sub-tabs are displayed
    const fileBadge = page.locator("[data-testid='file-count-badge']");
    await expect(fileBadge).toBeVisible();
    await expect(fileBadge).toContainText("4 files");

    const claudeTab = page.locator("[data-testid='file-tab-0']");
    await expect(claudeTab).toBeVisible();
    await expect(claudeTab).toHaveText("CLAUDE.md");
    await claudeTab.click();
    await expect(textarea).toHaveValue(/CLAUDE\.md guidelines for RepoScope/);

    const agentsTab = page.locator("[data-testid='file-tab-1']");
    await agentsTab.click();
    await expect(textarea).toHaveValue(/AGENTS\.md agent rules/);

    // Switch back to Unified Bundle
    const unifiedTab = page.locator("[data-testid='file-tab-all']");
    await unifiedTab.click();
    await expect(textarea).toHaveValue(/CLAUDE\.md[\s\S]*AGENTS\.md/);

    // Test Copy button
    const copyBtn = page.locator("[data-testid='copy-prompt-btn']");
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();
    await expect(copyBtn).toContainText("Copied", { timeout: 3000 });

    // Test Download button
    const downloadPromise = page.waitForEvent("download");
    const downloadBtn = page.locator("[data-testid='download-prompt-btn']");
    await downloadBtn.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain(".md");

    // Close the modal
    const closeBtn = page.locator("[data-testid='close-modal-btn']");
    await closeBtn.click();
    await expect(modal).not.toBeVisible();

    // Verify no console errors
    assertNoErrors(errorCollector);
  });
});
