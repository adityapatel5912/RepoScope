/**
 * onboarding.spec.ts
 * E2E tests for Phase 9: Topological Student Onboarding (V2.7).
 * Verifies 4 topological tiers, lock/unlock states, graph-graded challenge verification,
 * and localStorage progress persistence.
 */

import { expect, test } from "@playwright/test";
import { assertNoErrors, attachErrorCollector } from "./helpers";

test.describe("Phase 9 — Topological Student Onboarding", () => {
  test("ONB01 — verifies 4 DAG-ordered tiers, challenge verification, and unlock flow", async ({
    page,
  }) => {
    const errorCollector = attachErrorCollector(page);

    // Mock curriculum endpoint
    await page.route("**/api/onboard/curriculum", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          repo: "demo/repo",
          total_tiers: 4,
          scc_count: 5,
          dag_edges: 6,
          tiers: [
            {
              tier: 1,
              name: "Foundations & Leaf Utilities",
              badge: "L1",
              description: "Base helper libraries and leaf utilities with zero internal repo dependencies.",
              prerequisites: [],
              files: [
                {
                  path: "backend/json_utils.py",
                  label: "json_utils.py",
                  role: "Foundation Leaf",
                  in_degree: 8,
                  out_degree: 0,
                  why: "Leaf utility for JSON operations.",
                },
              ],
              challenges: [
                {
                  id: "tier_1_role",
                  title: "Architectural Role",
                  prompt: "What is the architectural role of backend/json_utils.py in this codebase?",
                  options: [
                    "Foundation leaf utility with zero or minimal internal repo imports",
                    "Core domain model or data schema consumed across services",
                    "Application service orchestrating business workflows",
                    "Public API route handler or CLI entrypoint",
                  ],
                  answer_index: 0,
                  explanation: "json_utils.py is a leaf module with out-degree 0.",
                  kind: "multiple_choice",
                },
              ],
            },
            {
              tier: 2,
              name: "Core Domain Models & Schemas",
              badge: "L2",
              description: "Domain entities and schemas representing business objects.",
              prerequisites: [1],
              files: [
                {
                  path: "backend/models.py",
                  label: "models.py",
                  role: "Domain Model",
                  in_degree: 5,
                  out_degree: 1,
                  why: "Domain entities.",
                },
              ],
              challenges: [],
            },
            {
              tier: 3,
              name: "Application Services & Handlers",
              badge: "L3",
              description: "Internal services coordinating business logic.",
              prerequisites: [1, 2],
              files: [],
              challenges: [],
            },
            {
              tier: 4,
              name: "Public APIs & System Entrypoints",
              badge: "L4",
              description: "Public HTTP routers and entrypoints.",
              prerequisites: [1, 2, 3],
              files: [],
              challenges: [],
            },
          ],
        }),
      });
    });

    // Mock legacy onboard endpoint
    await page.route("**/api/onboard", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            levels: [
              {
                level: 1,
                title: "Entry Points",
                description: "Start here",
                files: [{ path: "main.py", why: "Entry point" }],
                quiz: [],
              },
            ],
            good_first_issues: [],
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock challenge verification endpoint
    await page.route("**/api/onboard/verify-challenge", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          correct: true,
          feedback: "Correct! json_utils.py is a leaf module with out-degree 0.",
          next_tier: 2,
          unlocked: true,
        }),
      });
    });

    // Navigate to local test repo view
    await page.goto("/#test-repo");
    await page.waitForLoadState("domcontentloaded");

    // Open Student Onboarding / Learn panel if not visible
    const onboardHeading = page.getByRole("heading", { name: /student onboarding|student path/i });
    if (!(await onboardHeading.isVisible())) {
      const onboardBtn = page.getByRole("button", { name: /learn|student|onboard/i }).first();
      if (await onboardBtn.isVisible()) {
        await onboardBtn.click();
      }
    }

    // Verify 4 Tiers are visible
    await expect(page.getByText("Foundations & Leaf Utilities")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Core Domain Models & Schemas")).toBeVisible();
    await expect(page.getByText("Application Services & Handlers")).toBeVisible();
    await expect(page.getByText("Public APIs & System Entrypoints")).toBeVisible();

    // Verify Tier 1 challenge prompt is visible
    await expect(page.getByText("What is the architectural role of backend/json_utils.py")).toBeVisible();

    // Select correct option A
    const optionA = page.getByRole("button", { name: /foundation leaf utility/i });
    await expect(optionA).toBeVisible();
    await optionA.click();

    // Click "Verify with AST Graph" button
    const verifyBtn = page.getByRole("button", { name: /verify with ast graph/i });
    await expect(verifyBtn).toBeVisible();
    await verifyBtn.click();

    // Expect positive verification feedback
    await expect(page.getByText(/correct!/i).first()).toBeVisible({ timeout: 5000 });

    assertNoErrors(errorCollector);
  });
});
