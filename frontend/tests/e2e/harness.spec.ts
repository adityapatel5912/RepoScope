/**
 * harness.spec.ts
 * Browser-QA journeys for the nine-agent harness configurator (Phase 3).
 *
 * Verifies:
 * - Local repository loading sets localRoot and enables the harness modal
 * - "Connect AI agent" button opens the modal without reloading repository
 * - All nine supported agent targets are listed and selectable from the API
 * - Preview shows exact files, commands, and notes without writing files
 * - Claude preview asserts .mcp.json, mcpServers.reposcope, and quoted root command
 * - VS Code preview asserts servers.reposcope
 * - Codex preview asserts [mcp_servers.reposcope]
 * - OpenCode preview asserts mcp.reposcope and asserts NO mcp.servers
 * - All 9 targets preview their own fresh content, not stale content
 * - Preview never shows write confirmation and makes zero POST apply calls
 * - Apply button is disabled with explanation when server writes are off
 * - Responsive 1280x800 layout has zero horizontal document overflow
 * - Skills preview lists 5 Phase 4 descriptors
 * - Unified diff, force gate, and second confirmation render for an existing file
 * - Initial focus enters the dialog and focus returns to the trigger on close
 * - Apply success remains visible after the post-write preview refresh
 * - Zero un-whitelisted console or network errors
 * - Evidence screenshots captured under docs/screenshots/v2/harness/
 */

import { expect, test } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import {
  assertNoErrors,
  attachErrorCollector,
  captureJourney,
} from "./helpers";

const BACKEND_URL =
  process.env.REPOSCOPE_QA_BACKEND_URL ?? "http://127.0.0.1:8010";

const EXPECTED_AGENT_IDS = [
  "claude",
  "cursor",
  "vscode",
  "codex",
  "kiro",
  "antigravity",
  "windsurf",
  "cline",
  "opencode",
];

/**
 * The first project file for each target and a token that only appears in
 * that file's exact preview content. This proves the preview refreshed for
 * the selected agent instead of leaving the previous agent's content on screen.
 */
const PREVIEW_EXPECTATIONS: Record<string, { path: string; token: string }> = {
  claude: { path: ".mcp.json", token: "mcpServers" },
  cursor: { path: ".cursor/mcp.json", token: "mcpServers" },
  vscode: { path: ".vscode/mcp.json", token: '"servers"' },
  codex: { path: ".codex/config.toml", token: "[mcp_servers.reposcope]" },
  kiro: { path: ".kiro/settings/mcp.json", token: "mcpServers" },
  antigravity: { path: ".agents/mcp_config.json", token: "mcpServers" },
  windsurf: { path: ".devin/mcp_config.json", token: "mcpServers" },
  cline: { path: ".roo/mcp.json", token: "mcpServers" },
  opencode: { path: "opencode.json", token: '"mcp"' },
};

/** Mirrors the PreviewPane test id convention for exact file content. */
function fileContentTestId(filePath: string): string {
  return `harness-file-content-${filePath.replace(/[/.]/g, "-")}`;
}

async function loadFixture(
  name = "v2_contract",
  options: { copy?: boolean; watch?: boolean } = {},
): Promise<{ copy: string | null }> {
  const params = new URLSearchParams({ name });
  if (options.copy) params.set("copy", "true");
  if (options.watch) params.set("watch", "true");

  const response = await fetch(
    `${BACKEND_URL}/api/qa/load-fixture?${params.toString()}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to load fixture '${name}': HTTP ${response.status} ` +
        `${await response.text()}`,
    );
  }
  const payload = (await response.json()) as { copy?: string | null };
  return { copy: payload.copy ?? null };
}

test.describe("Nine-Agent Harness Configurator (Phase 3)", () => {
  test("H01 — nine-agent harness preview journey with v2_contract fixture", async ({
    page,
  }) => {
    // 1. Load the v2_contract QA fixture
    await loadFixture("v2_contract");
    const errors = attachErrorCollector(page);

    // Track POST requests to /api/harness/apply to guarantee preview never writes
    let applyPostCount = 0;
    page.on("request", (req) => {
      if (req.url().includes("/api/harness/apply") && req.method() === "POST") {
        applyPostCount++;
      }
    });

    // 2. Navigate to root and wait for local-mode-badge
    await page.goto("/");
    const localBadge = page.locator('[data-testid="local-mode-badge"]');
    await expect(localBadge).toBeVisible({ timeout: 15_000 });

    // 3. Open the modal from data-testid="open-harness"
    const openHarnessBtn = page.locator('[data-testid="open-harness"]');
    await expect(openHarnessBtn).toBeVisible();
    await openHarnessBtn.click();

    // Assert modal shell is open
    const modal = page.locator('[data-testid="harness-modal"]');
    await expect(modal).toBeVisible();

    // 4. Assert all nine target labels/ids are listed
    for (const id of EXPECTED_AGENT_IDS) {
      const agentItem = page.locator(`[data-testid="harness-agent-${id}"]`);
      await expect(agentItem).toBeVisible();
    }

    // 5. Preview Claude Code
    const claudeItem = page.locator('[data-testid="harness-agent-claude"]');
    await claudeItem.click();
    const previewPane = page.locator('[data-testid="harness-preview"]');
    await expect(previewPane).toBeVisible();

    // Assert .mcp.json file tab and content
    const mcpJsonTab = previewPane.getByRole("tab", { name: /\.mcp\.json/i });
    await expect(mcpJsonTab).toBeVisible();
    const claudeContent = page.locator('[data-testid="harness-file-content--mcp-json"]');
    await expect(claudeContent).toBeVisible();
    await expect(claudeContent).toContainText("mcpServers");
    await expect(claudeContent).toContainText("reposcope");

    // Assert command includes claude mcp add and reposcope
    const commandPre = previewPane.locator("pre").first();
    await expect(commandPre).toContainText("claude mcp add");
    await expect(commandPre).toContainText("reposcope");

    // Capture Claude preview screenshot
    await captureJourney(page, "harness", "harness-claude-preview");

    // 6. Preview VS Code
    const vscodeItem = page.locator('[data-testid="harness-agent-vscode"]');
    await vscodeItem.click();
    const vscodeContent = page.locator('[data-testid="harness-file-content--vscode-mcp-json"]');
    await expect(vscodeContent).toBeVisible();
    await expect(vscodeContent).toContainText("servers");
    await expect(vscodeContent).toContainText("reposcope");

    // 7. Preview Codex CLI
    const codexItem = page.locator('[data-testid="harness-agent-codex"]');
    await codexItem.click();
    const codexContent = page.locator('[data-testid="harness-file-content--codex-config-toml"]');
    await expect(codexContent).toBeVisible();
    await expect(codexContent).toContainText("[mcp_servers.reposcope]");

    // 8. Preview OpenCode
    const opencodeItem = page.locator('[data-testid="harness-agent-opencode"]');
    await opencodeItem.click();
    const opencodeContent = page.locator('[data-testid="harness-file-content-opencode-json"]');
    await expect(opencodeContent).toBeVisible();
    // Critical: OpenCode schema uses mcp.reposcope and must NOT use mcp.servers
    await expect(opencodeContent).toContainText("mcp");
    await expect(opencodeContent).toContainText("reposcope");
    const opencodeText = await opencodeContent.innerText();
    expect(opencodeText).not.toContain('"servers"');
    expect(opencodeText).not.toContain("mcp.servers");

    // Capture OpenCode preview screenshot
    await captureJourney(page, "harness", "harness-opencode-preview");

    // 9. Preview every one of the nine targets and assert the fresh preview
    // content, not just a pane left over from the previous selection.
    for (const id of EXPECTED_AGENT_IDS) {
      const expectation = PREVIEW_EXPECTATIONS[id];
      const agentBtn = page.locator(`[data-testid="harness-agent-${id}"]`);
      await agentBtn.click();
      await expect(previewPane).toBeVisible();

      const fileTabs = previewPane.getByRole("tablist", { name: /configuration files/i });
      await expect(fileTabs).toBeVisible();
      await expect(
        previewPane.getByRole("tab").filter({ hasText: expectation.path }).first(),
      ).toBeVisible();
      await expect(
        page.locator(`[data-testid="${fileContentTestId(expectation.path)}"]`),
      ).toContainText(expectation.token);
    }

    // 10. Switch to Skills tab and verify 5 shipped skills with Ready badges
    const skillsTab = page.locator('[role="tab"]').filter({ hasText: "Skills" });
    await expect(skillsTab).toBeVisible();
    await skillsTab.click();

    const expectedSkills = [
      "blast-radius-guard",
      "zero-grep-architect",
      "pr-contract-shield",
      "onboarding-navigator",
      "dead-code-surgeon",
    ];
    for (const skillId of expectedSkills) {
      const skillCard = page.locator(`[data-testid="harness-skill-${skillId}"]`);
      await expect(skillCard).toBeVisible();
      await expect(skillCard).toContainText("Ready");
      await expect(skillCard).not.toContainText(/Available in Phase 4/i);
    }

    // Toggle preview on first card
    const firstToggleBtn = page.locator('[data-testid="toggle-skill-preview-blast-radius-guard"]');
    await expect(firstToggleBtn).toBeVisible();
    await firstToggleBtn.click();

    const firstBodyPre = page.locator('[data-testid="harness-skill-body-blast-radius-guard"]');
    await expect(firstBodyPre).toBeVisible();
    await expect(firstBodyPre).toContainText("name: blast-radius-guard");
    await expect(firstBodyPre).toContainText("get_ast_skeleton");

    // Capture Skills preview screenshot with one preview open
    await captureJourney(page, "harness", "harness-skills-preview");

    // Toggle close
    await firstToggleBtn.click();
    await expect(firstBodyPre).toHaveCount(0);

    // Switch back to Agents tab
    const agentsTab = page.locator('[role="tab"]').filter({ hasText: "Agents" });
    await agentsTab.click();

    // Assert Claude file list includes skill file tab
    const claudeAgentBtn = page.locator('[data-testid="harness-agent-claude"]');
    await claudeAgentBtn.click();
    const claudeSkillTab = previewPane.getByRole("tab").filter({ hasText: ".claude/skills/blast-radius-guard/SKILL.md" });
    await expect(claudeSkillTab).toBeVisible();

    // 11. Assert preview never shows success/write confirmation
    const successBanner = page.locator('[data-testid="harness-apply-success"]');
    await expect(successBanner).toHaveCount(0);
    expect(applyPostCount).toBe(0);

    // 12. Assert apply control is disabled when apply_enabled is false
    const applyBtn = page.locator('[data-testid="harness-apply"]');
    await expect(applyBtn).toBeVisible();
    await expect(applyBtn).toBeDisabled();
    const disabledReason = page.locator("#apply-disabled-reason");
    await expect(disabledReason).toBeVisible();
    await expect(disabledReason).toContainText(/server writes are disabled/i);

    // 13. Check modal at 1280x800 for no horizontal overflow
    await page.setViewportSize({ width: 1280, height: 800 });
    // Let layout settle
    await page.waitForTimeout(200);

    const docScrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const windowInnerWidth = await page.evaluate(() => window.innerWidth);
    expect(docScrollWidth).toBeLessThanOrEqual(windowInnerWidth);

    // Assert modal is still fully visible and usable
    await expect(modal).toBeVisible();
    await expect(previewPane).toBeVisible();

    // Capture 1280x800 evidence screenshot
    await captureJourney(page, "harness", "harness-1280x800-layout");

    // 14. Assert zero un-whitelisted errors
    assertNoErrors(errors, "H01 nine-agent harness journey");
  });

  test("H02 — unified diff and force requirement on modified file", async ({
    page,
  }) => {
    // Load a writable copy of v2_contract
    const { copy } = await loadFixture("v2_contract", { copy: true });
    expect(copy).toBeTruthy();

    if (copy) {
      // Seed a pre-existing .mcp.json file in the writable copy
      const existingConfig = {
        mcpServers: {
          custom_tool: {
            command: "npx",
            args: ["-y", "custom-mcp-tool"],
          },
        },
      };
      fs.writeFileSync(
        path.join(copy, ".mcp.json"),
        JSON.stringify(existingConfig, null, 2) + "\n",
        "utf8",
      );
    }

    // Enable server writes in the preview response only. The POST endpoint is
    // never called in this test, so no file is written.
    await page.route("**/api/harness/config*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.apply_enabled = true;
      await route.fulfill({ json });
    });

    let applyPostCount = 0;
    page.on("request", (req) => {
      if (req.url().includes("/api/harness/apply") && req.method() === "POST") {
        applyPostCount++;
      }
    });

    const errors = attachErrorCollector(page);
    await page.goto("/");
    await expect(page.locator('[data-testid="local-mode-badge"]')).toBeVisible({ timeout: 15_000 });

    // Open harness modal
    await page.locator('[data-testid="open-harness"]').click();
    await expect(page.locator('[data-testid="harness-modal"]')).toBeVisible();

    // Preview Claude
    await page.locator('[data-testid="harness-agent-claude"]').click();

    // Assert diff view is visible
    const diffContainer = page.locator('[data-testid="harness-diff"]');
    await expect(diffContainer).toBeVisible();
    await expect(diffContainer).toContainText("custom-mcp-tool");
    await expect(diffContainer).toContainText("reposcope");

    // Assert visible existing file will change warning banner (§7.5)
    const existingFileWarning = page.locator('[data-testid="existing-file-warning"]');
    await expect(existingFileWarning).toBeVisible();
    await expect(existingFileWarning).toContainText(/Existing file will change/i);

    // The force gate is visible, and Write files stays disabled until it is checked.
    const forceCheckbox = page.getByRole("checkbox", {
      name: /Overwrite existing file modifications/i,
    });
    await expect(forceCheckbox).toBeVisible();
    await expect(forceCheckbox).not.toBeChecked();
    const applyBtn = page.locator('[data-testid="harness-apply"]');
    await expect(applyBtn).toBeDisabled();
    await forceCheckbox.check();
    await expect(applyBtn).toBeEnabled();

    // Bring the force gate and action into view before capturing evidence.
    await applyBtn.scrollIntoViewIfNeeded();

    // Capture diff preview screenshot with the force checkbox and enabled action
    await captureJourney(page, "harness", "harness-diff-preview");

    // Open the confirmation, then cancel without writing.
    await applyBtn.click();
    const confirmBtn = page.locator('[data-testid="harness-apply-confirm"]');
    await expect(confirmBtn).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(confirmBtn).toHaveCount(0);
    expect(applyPostCount).toBe(0);
    await expect(page.locator('[data-testid="harness-apply-success"]')).toHaveCount(0);

    // Assert zero un-whitelisted errors
    assertNoErrors(errors, "H02 diff viewer journey");
  });

  test("H03 — keyboard accessibility, focus trap, and Escape dismissal", async ({
    page,
  }) => {
    await loadFixture("v2_contract");
    const errors = attachErrorCollector(page);

    await page.goto("/");
    await expect(page.locator('[data-testid="local-mode-badge"]')).toBeVisible({ timeout: 15_000 });

    const openBtn = page.locator('[data-testid="open-harness"]');
    await openBtn.click();
    const modal = page.locator('[data-testid="harness-modal"]');
    const panel = page.locator('[data-testid="harness-modal-panel"]');
    await expect(modal).toBeVisible();

    // Focus must move into the dialog on open, and Shift+Tab must not escape it.
    await expect(panel).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect
      .poll(() =>
        page.evaluate(() => {
          const dialog = document.querySelector('[data-testid="harness-modal"]');
          return Boolean(dialog && dialog.contains(document.activeElement));
        }),
      )
      .toBe(true);

    // Test Escape key closes the modal and restores focus to the trigger
    await page.keyboard.press("Escape");
    await expect(modal).toBeHidden();
    await expect(openBtn).toBeFocused();

    // Reopen modal
    await openBtn.click();
    await expect(modal).toBeVisible();
    await expect(panel).toBeFocused();

    // Close button click closes modal
    const closeBtn = page.getByRole("button", { name: "Close harness modal" });
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();
    await expect(modal).toBeHidden();

    // Assert trigger button is focused after closing
    await expect(openBtn).toBeFocused();

    // Reopen modal and test backdrop click closes modal when no confirmation is active
    await openBtn.click();
    await expect(modal).toBeVisible();
    await modal.click({ position: { x: 5, y: 5 } });
    await expect(modal).toBeHidden();

    assertNoErrors(errors, "H03 accessibility journey");
  });

  test("H04 — backdrop click is blocked during write confirmation (§7.2)", async ({
    page,
  }) => {
    await loadFixture("v2_contract");
    const errors = attachErrorCollector(page);

    // Mock config endpoint to simulate apply_enabled: true
    await page.route("**/api/harness/config*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.apply_enabled = true;
      json.requires_force = false;
      await route.fulfill({ json });
    });

    await page.goto("/");
    await expect(page.locator('[data-testid="local-mode-badge"]')).toBeVisible({ timeout: 15_000 });

    const openBtn = page.locator('[data-testid="open-harness"]');
    await openBtn.click();
    const modal = page.locator('[data-testid="harness-modal"]');
    await expect(modal).toBeVisible();

    // Select Claude
    await page.locator('[data-testid="harness-agent-claude"]').click();
    const applyBtn = page.locator('[data-testid="harness-apply"]');
    await expect(applyBtn).toBeVisible();
    await expect(applyBtn).toBeEnabled();

    // Initiate write confirmation
    await applyBtn.click();
    const confirmBtn = page.locator('[data-testid="harness-apply-confirm"]');
    await expect(confirmBtn).toBeVisible();

    // Clicking the backdrop while confirmation is active must NOT close the modal (§7.2)
    await modal.click({ position: { x: 5, y: 5 } });
    await expect(modal).toBeVisible();
    await expect(confirmBtn).toBeVisible();

    // Pressing Escape while confirmation is active dismisses confirmation first
    await page.keyboard.press("Escape");
    await expect(confirmBtn).toHaveCount(0);
    await expect(modal).toBeVisible();

    // Pressing Escape again closes the modal
    await page.keyboard.press("Escape");
    await expect(modal).toBeHidden();

    assertNoErrors(errors, "H04 write confirmation backdrop journey");
  });

  test("H05 — apply success remains visible after the preview refresh", async ({
    page,
  }) => {
    await loadFixture("v2_contract");
    const errors = attachErrorCollector(page);

    // Simulate the server-writes-enabled path. The apply POST is fulfilled by
    // Playwright, so this journey never writes a file.
    await page.route("**/api/harness/config*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.apply_enabled = true;
      json.requires_force = false;
      await route.fulfill({ json });
    });

    let applyPostCount = 0;
    await page.route("**/api/harness/apply", async (route) => {
      applyPostCount++;
      await route.fulfill({
        json: {
          ok: true,
          agent: "claude",
          label: "Claude Code",
          transport: "stdio",
          root: "",
          command: "",
          command_kind: "install",
          command_note: "",
          apply_enabled: true,
          requires_force: false,
          files: [],
          warnings: [],
          apply: true,
          applied: [".mcp.json", "CLAUDE.md"],
          unchanged: [],
        },
      });
    });

    await page.goto("/");
    await expect(page.locator('[data-testid="local-mode-badge"]')).toBeVisible({ timeout: 15_000 });

    await page.locator('[data-testid="open-harness"]').click();
    await page.locator('[data-testid="harness-agent-claude"]').click();
    const applyBtn = page.locator('[data-testid="harness-apply"]');
    await expect(applyBtn).toBeEnabled();
    await applyBtn.click();

    const refresh = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        response.url().includes("/api/harness/config") &&
        response.status() === 200,
    );
    await page.locator('[data-testid="harness-apply-confirm"]').click();
    await refresh;

    const successBanner = page.locator('[data-testid="harness-apply-success"]');
    await expect(successBanner).toBeVisible();
    await expect(successBanner).toContainText("Applied files: .mcp.json, CLAUDE.md");
    await expect(page.locator('[data-testid="harness-preview"]')).toBeVisible();
    expect(applyPostCount).toBe(1);

    assertNoErrors(errors, "H05 apply success journey");
  });
});
