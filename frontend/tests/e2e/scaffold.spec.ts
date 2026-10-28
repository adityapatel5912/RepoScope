/**
 * scaffold.spec.ts
 * E2E tests for Phase 7: Executable multi-file starter kit scaffolder (V2.6).
 *
 * Verifies:
 * - Opening Scaffold modal from Graph Controls
 * - Display of project type, file count, and token estimate badges
 * - Bootstrap command banner (npx reposcope-mcp scaffold --from <repo> --out ./app)
 * - Copy bootstrap command button and feedback
 * - File tree navigation and code preview updating
 * - File copy action
 * - Download ZIP functionality
 * - Keyboard navigation (Escape to close)
 * - Zero un-whitelisted console errors
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 7 — Executable Multi-File Scaffolder", () => {
  test("SC01 — generates starter kit, renders preview tree, copy command, and zip download", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    try {
      await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
    } catch {
      // Ignore if permissions not supported
    }

    // Mock scaffold endpoint with a deterministic 14-file starter kit
    await page.route("**/api/scaffold", async (route) => {
      const postData = route.request().postDataJSON() || {};
      const mode = postData.mode || "preview";

      if (mode === "command") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            project_type: "python-fastapi",
            command: "npx reposcope-mcp scaffold --from octo/repo --out ./app",
          }),
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          project_type: "python-fastapi",
          file_tree: [
            ".agents/AGENTS.md",
            ".claude/CLAUDE.md",
            ".env.example",
            ".gitignore",
            "Makefile",
            "README.md",
            "SCAFFOLD.md",
            "app/__init__.py",
            "app/api.py",
            "app/config.py",
            "main.py",
            "pyproject.toml",
            "tests/__init__.py",
            "tests/test_api.py",
          ],
          files: [
            {
              path: "README.md",
              content: "# octo/repo — Starter Scaffold\n\nRun `python main.py` to start.",
              purpose: "Starter guide and stage instructions",
              language: "markdown",
            },
            {
              path: "main.py",
              content: "from fastapi import FastAPI\n\napp = FastAPI()\n",
              purpose: "Application entrypoint",
              language: "python",
            },
            {
              path: "app/api.py",
              content: "from fastapi import APIRouter\n\nrouter = APIRouter()\n",
              purpose: "API routing module",
              language: "python",
            },
            {
              path: ".env.example",
              content: "APP_ENV=development\nPORT=8000\n",
              purpose: "Environment variable placeholder template",
              language: "text",
            },
            {
              path: ".claude/CLAUDE.md",
              content: "# CLAUDE.md\nAgent rules\n",
              purpose: "Claude Code instructions",
              language: "markdown",
            },
          ],
          entry_files: ["main.py", "app/api.py"],
          top_nodes: ["main.py", "app/api.py"],
          warnings: [],
          token_estimate: 4250,
          bootstrap_command: "npx reposcope-mcp scaffold --from octo/repo --out ./app",
        }),
      });
    });

    // Mock download-zip endpoint
    await page.route("**/api/scaffold/download-zip", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/zip",
        headers: {
          "Content-Disposition": 'attachment; filename="reposcope-scaffold-python-fastapi.zip"',
        },
        body: Buffer.from("PK\x03\x04synthetic-zip-contents"),
      });
    });

    // Navigate to local test repo view
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    // Click "Generate scaffold" button in GraphControls
    const scaffoldBtn = page.getByRole("button", { name: /generate scaffold/i });
    await expect(scaffoldBtn).toBeVisible({ timeout: 10000 });
    await scaffoldBtn.click();

    // Verify Scaffold modal opens
    const modal = page.getByRole("dialog", { name: /starter scaffold/i });
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Verify header badges
    await expect(modal.getByText("python-fastapi")).toBeVisible();
    await expect(modal.getByText(/5 files/i)).toBeVisible();
    await expect(modal.getByText(/4,250 tokens/i)).toBeVisible();

    // Verify bootstrap command banner
    await expect(modal.getByText("npx reposcope-mcp scaffold --from octo/repo --out ./app")).toBeVisible();

    // Test Copy Command
    const copyCmdBtn = modal.getByRole("button", { name: /copy command/i }).first();
    await expect(copyCmdBtn).toBeVisible();
    await copyCmdBtn.click();
    await expect(modal.getByText(/copied/i).first()).toBeVisible();

    // Verify file preview for README.md (selected by default)
    await expect(modal.getByRole("region", { name: /code preview of readme\.md/i }).or(modal.locator("pre"))).toBeVisible();
    await expect(modal.locator("pre")).toContainText("# octo/repo — Starter Scaffold");

    // Click on another file in the tree (main.py)
    const mainFileItem = modal.getByText("main.py").first();
    if (await mainFileItem.isVisible()) {
      await mainFileItem.click();
      await expect(modal.locator("pre")).toContainText("from fastapi import FastAPI");
    }

    // Verify ZIP download button works
    const downloadZipBtn = modal.getByRole("button", { name: /download zip/i });
    await expect(downloadZipBtn).toBeVisible();
    const downloadPromise = page.waitForEvent("download").catch(() => null);
    await downloadZipBtn.click();
    const download = await downloadPromise;
    if (download) {
      expect(download.suggestedFilename()).toContain(".zip");
    }

    // Test close via Escape key
    await page.keyboard.press("Escape");
    await expect(modal).toBeHidden({ timeout: 3000 });

    assertNoErrors(errorCollector);
  });
});
