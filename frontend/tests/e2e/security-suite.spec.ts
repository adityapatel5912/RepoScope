/**
 * security-suite.spec.ts
 * E2E tests for Phase 13: Six-Engine Graph-Contextual Security Suite (V2.8)
 *
 * Verifies:
 *   1. Switching to Security Suite tab and executing scan
 *   2. Grouping by 6 deterministic engines (Taint, Secrets, CVEs, Injections, Config, Auth)
 *   3. Interactive Taint Flow Propagation diagram
 *   4. Suggested Unified Diff patch viewer with AST syntax verification & copy
 *   5. Standard OASIS SARIF 2.1.0 export
 *   6. Visual screenshot artifact capture
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 13 — Six-Engine Graph-Contextual Security Suite", () => {
  test("SEC01 — runs 6-engine scan, renders categories, taint traces, and syntax-verified patches", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    // Mock the 6-engine security scan endpoint
    await page.route("**/api/security/scan", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          repo: "adityapatel5912/RepoScope",
          scanned: { repo_files: true, pr: null, commits: 12, taint_flows: 1 },
          flags: [
            {
              type: "TAINT",
              engine: "cross_file_taint",
              cwe: "CWE-20",
              severity: "critical",
              file: "backend/main.py",
              line: 88,
              detail: "request.args in backend/main.py:88 propagates cross-file into sink subprocess.run() in backend/executor.py:14 via run_command()",
              suggestion: "Pass value through strict validation or shlex.quote() before passing to sink.",
              source: "request.args",
              source_line: 88,
              source_file: "backend/main.py",
              sink: "subprocess.run",
              sink_line: 14,
              sink_file: "backend/executor.py",
              patch_available: true,
              trace: {
                source_file: "backend/main.py",
                source_line: 88,
                source_label: "request.args",
                propagators: [
                  { file: "backend/main.py", line: 90, symbol: "run_command", via: "cmd" },
                  { file: "backend/executor.py", line: 12, symbol: "run_command", via: "command" },
                ],
                sink_file: "backend/executor.py",
                sink_line: 14,
                sink_label: "subprocess.run",
              },
            },
            {
              type: "SECRET",
              engine: "secrets_entropy",
              cwe: "CWE-798",
              severity: "high",
              file: "backend/config.py",
              line: 12,
              detail: "High-entropy credential detected (AKIA<redacted>9Z, H=4.38)",
              suggestion: "Store secrets in NordPass or environment variables.",
              patch_available: true,
            },
            {
              type: "INJECTION",
              engine: "injection_sinks",
              cwe: "CWE-89",
              severity: "high",
              file: "backend/database.py",
              line: 45,
              detail: "SQL query constructed with dynamic string interpolation in execute()",
              suggestion: "Use parameterized queries (e.g. cursor.execute(query, (params,)))",
              patch_available: true,
            },
            {
              type: "CVE",
              engine: "dependency_cve",
              cwe: "CWE-1395",
              severity: "medium",
              file: "requirements.txt",
              line: 1,
              detail: "cryptography 39.0.0 is below the fixed version for CVE-2023-49083 null pointer dereference",
              suggestion: "Upgrade cryptography to >=41.0.6",
              patch_available: true,
            },
            {
              type: "CONFIG",
              engine: "insecure_config",
              cwe: "CWE-942",
              severity: "medium",
              file: "backend/main.py",
              line: 162,
              detail: "Wildcard CORS origin '*' allows any external domain to make cross-origin requests",
              suggestion: "Specify explicit allowed origins.",
              patch_available: true,
            },
            {
              type: "AUTH_BYPASS",
              engine: "auth_bypass",
              cwe: "CWE-306",
              severity: "high",
              file: "backend/routes/user.py",
              line: 32,
              detail: "State-mutating endpoint 'delete_account' (POST) lacks authentication dependency or guard",
              suggestion: "Add an authentication dependency like 'user = Depends(get_current_user)'",
              patch_available: true,
            },
          ],
          total_flags: 6,
          summary: {
            by_engine: {
              cross_file_taint: 1,
              secrets_entropy: 1,
              dependency_cve: 1,
              injection_sinks: 1,
              insecure_config: 1,
              auth_bypass: 1,
              breaking: 0,
            },
            SECRET: 1,
            BREAKING: 0,
            CVE: 1,
            TAINT: 1,
            INJECTION: 1,
            CONFIG: 1,
            AUTH_BYPASS: 1,
            critical: 1,
            high: 3,
            medium: 2,
            low: 0,
          },
        }),
      });
    });

    // Mock patch endpoint
    await page.route("**/api/security/patch", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          file: "backend/database.py",
          line: 45,
          engine: "injection_sinks",
          diff: "--- a/backend/database.py\n+++ b/backend/database.py\n@@ -45,1 +45,1 @@\n-cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n+cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
          syntax_valid: true,
          explanation: "Parameterized query placeholders prevent SQL injection by separating SQL commands from untrusted data.",
        }),
      });
    });

    // Mock SARIF export endpoint
    await page.route("**/api/security/sarif", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/sarif+json",
        body: JSON.stringify({
          $schema: "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
          version: "2.1.0",
          runs: [
            {
              tool: {
                driver: {
                  name: "RepoScope",
                  version: "2.1.0",
                  rules: [],
                },
              },
              results: [],
            },
          ],
        }),
      });
    });

    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    // 1. Switch to Security Suite tab
    const secTab = page.getByRole("tab", { name: /security suite/i });
    await expect(secTab).toBeVisible({ timeout: 15000 });
    await secTab.click();

    // 2. Click "Run 6-Engine Audit"
    const auditBtn = page.getByRole("button", { name: /run 6-engine audit|re-scan/i });
    await expect(auditBtn).toBeVisible();
    await auditBtn.click();

    // 3. Verify finding headers and counts
    await expect(page.getByText(/taint flow/i).first()).toBeVisible();
    await expect(page.getByText(/secrets/i).first()).toBeVisible();
    await expect(page.getByText(/cves/i).first()).toBeVisible();
    await expect(page.getByText(/injections/i).first()).toBeVisible();

    // 4. Verify Taint Propagation Trace diagram is rendered
    await expect(page.getByText(/taint propagation trace/i)).toBeVisible();
    await expect(page.getByText(/backend\/executor\.py:14/i).first()).toBeVisible();

    // 5. Expand suggested patch
    const patchBtns = page.getByRole("button", { name: /view suggested patch/i });
    await expect(patchBtns.first()).toBeVisible();
    await patchBtns.first().click();

    // Verify Syntax Valid badge and diff display
    await expect(page.getByText(/ast syntax verified/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /copy patch/i })).toBeVisible();

    // 6. Test SARIF export button
    const sarifBtn = page.getByRole("button", { name: /export sarif/i });
    await expect(sarifBtn).toBeVisible();
    await sarifBtn.click();

    // 7. Capture visual screenshot artifact
    const artifactPath =
      "C:\\Users\\Admin\\.gemini\\antigravity\\brain\\a8e957cc-cfc4-4969-9c83-938efc95b952\\security_suite_panel.png";
    await page.screenshot({ path: artifactPath, fullPage: true });

    assertNoErrors(errorCollector);
  });
});
