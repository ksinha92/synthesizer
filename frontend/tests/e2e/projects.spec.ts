import { test, expect } from "@playwright/test";

test.describe("Projects Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/projects");
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Projects");
  });

  test("New Project button visible", async ({ page }) => {
    await expect(page.locator("button:has-text('New Project')")).toBeVisible();
  });

  test("create dialog opens and has proper ARIA", async ({ page }) => {
    await page.click("text=New Project");
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  test("step 1 has name + description fields and Skip toggle", async ({ page }) => {
    await page.click("text=New Project");
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog.locator('input[placeholder="My TDM Project"]')).toBeVisible();
    await expect(dialog.locator('textarea[placeholder="Optional description..."]')).toBeVisible();
    // Step 1 footer shows Cancel + Next, *not* Create Project (last step only).
    await expect(dialog.locator("button:has-text('Cancel')")).toBeVisible();
    await expect(dialog.locator("button:has-text('Next')")).toBeVisible();
    // The "Skip connection setup" checkbox lets users bypass steps 2-4.
    await expect(dialog.locator("text=Skip connection setup")).toBeVisible();
  });

  test("cancel closes wizard with no overlay remaining", async ({ page }) => {
    await page.click("text=New Project");
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await page.click("button:has-text('Cancel')");
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
    // No backdrop left behind that would intercept clicks (Codex P1 regression).
    await expect(page.locator(".bg-black\\/40")).not.toBeVisible();
    await expect(page.locator(".bg-black\\/50")).not.toBeVisible();
  });

  test("Escape closes wizard", async ({ page }) => {
    await page.click("text=New Project");
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
  });

  test("empty name keeps wizard on step 1", async ({ page }) => {
    await page.click("text=New Project");
    const dialog = page.locator('[role="dialog"]');
    // Clicking Next with an empty name fires zod validation and the
    // wizard's title stays on "Project details" rather than advancing.
    await dialog.locator("button:has-text('Next')").click();
    await expect(page.locator("text=Project name is required")).toBeVisible();
    await expect(dialog.locator("h2")).toContainText("Project details");
  });

  test("view toggle switches between table and card", async ({ page }) => {
    const tableBtn = page.locator('button[title="Table view"]');
    const cardBtn = page.locator('button[title="Card view"]');
    if (await tableBtn.isVisible()) {
      await tableBtn.click();
      await cardBtn.click();
    }
  });
});

test.describe("New Project Wizard (5 steps)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/projects");
    await page.click("text=New Project");
  });

  test("step indicator and titles advance with Next", async ({ page }) => {
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog.locator("h2")).toContainText("Project details");

    await dialog.locator('input[placeholder="My TDM Project"]').fill("E2E Wizard Test");
    await dialog.locator("button:has-text('Next')").click();
    await expect(dialog.locator("h2")).toContainText("Pick a source");

    await dialog.locator("button:has-text('Next')").click();
    await expect(dialog.locator("h2")).toContainText("Connect your data");

    // Fill the required connection fields before Next on step 3 validates.
    await dialog.locator('input[placeholder="Production Replica"]').fill("primary");
    await dialog.locator('input[placeholder="localhost"]').fill("db.example.com");
    await dialog.locator('input[placeholder="mydb"]').fill("prod");
    await dialog.locator('input[placeholder="postgres"]').fill("u");
    await dialog.locator("button:has-text('Next')").click();
    await expect(dialog.locator("h2")).toContainText("Run discovery");

    await dialog.locator("button:has-text('Next')").click();
    await expect(dialog.locator("h2")).toContainText("Confirm");
    // Confirm step swaps Next for Create Project.
    await expect(dialog.locator("button:has-text('Create Project')")).toBeVisible();
  });

  test("Back returns to the previous step", async ({ page }) => {
    const dialog = page.locator('[role="dialog"]');
    await dialog.locator('input[placeholder="My TDM Project"]').fill("Back Test");
    await dialog.locator("button:has-text('Next')").click();
    await expect(dialog.locator("h2")).toContainText("Pick a source");
    await dialog.locator("button:has-text('Back')").click();
    await expect(dialog.locator("h2")).toContainText("Project details");
    // Name persists when navigating back.
    await expect(dialog.locator('input[placeholder="My TDM Project"]')).toHaveValue("Back Test");
  });

  test("Skip connection jumps from Details straight to Confirm", async ({ page }) => {
    const dialog = page.locator('[role="dialog"]');
    await dialog.locator('input[placeholder="My TDM Project"]').fill("Skip Test");
    await dialog.locator("text=Skip connection setup").click();
    await dialog.locator("button:has-text('Next')").click();
    await expect(dialog.locator("h2")).toContainText("Confirm");
    await expect(dialog.locator("text=Skipped — add one later")).toBeVisible();
  });

  test("Snowflake tile reveals account/warehouse fields on step 3", async ({ page }) => {
    const dialog = page.locator('[role="dialog"]');
    await dialog.locator('input[placeholder="My TDM Project"]').fill("Snow Test");
    await dialog.locator("button:has-text('Next')").click();

    // Step 2: pick Snowflake.
    await dialog.locator("button:has-text('Snowflake')").click();
    await dialog.locator("button:has-text('Next')").click();

    // Step 3: Snowflake-only labels appear (scope to label so the Tier-2
    // Data warehouses category header doesn't collide on "Warehouse").
    await expect(dialog.locator('label:has-text("Account")')).toBeVisible();
    await expect(dialog.locator('label:has-text("Warehouse")')).toBeVisible();
  });

  test("Confirm step surfaces the values the user entered", async ({ page }) => {
    const dialog = page.locator('[role="dialog"]');
    await dialog.locator('input[placeholder="My TDM Project"]').fill("Acme TDM");
    await dialog
      .locator('textarea[placeholder="Optional description..."]')
      .fill("Project description for confirm");
    await dialog.locator("text=Skip connection setup").click();
    await dialog.locator("button:has-text('Next')").click();
    await expect(dialog.locator("h2")).toContainText("Confirm");
    await expect(dialog.locator("text=Acme TDM")).toBeVisible();
    await expect(dialog.locator("text=Project description for confirm")).toBeVisible();
  });
});

test.describe("Project Detail Page", () => {
  test("loads with Privacy Hub + workspace tabs", async ({ page }) => {
    // Phase 49 UX refactor: the project landing page now renders the Privacy
    // Hub instead of stat cards. Workspace navigation is the tab bar, and
    // section names appear there as tabs (one of which is "Connections").
    await page.goto("/projects/00000000-0000-0000-0000-000000000001");
    const tabs = page.locator('[role="tablist"][aria-label="Workspace sections"]');
    await expect(tabs.locator('[role="tab"]:has-text("Privacy Hub")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Connections")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Masking")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Synthetic")')).toBeVisible();
  });

  test("recent activity section visible", async ({ page }) => {
    // Section header text is "Recent activity" (Phase 49 wording, lower-case 'a').
    await page.goto("/projects/00000000-0000-0000-0000-000000000001");
    await expect(page.locator('h2:has-text("Recent activity")')).toBeVisible();
  });

  test("project workspace tabs show all sections", async ({ page }) => {
    // Phase 48 UX refactor: per-project <aside> sidebar replaced by a top
    // tab bar (WorkspaceTabBar) with role="tablist".
    await page.goto("/projects/00000000-0000-0000-0000-000000000001");
    const tabs = page.locator('[role="tablist"][aria-label="Workspace sections"]');
    await expect(tabs.locator('[role="tab"]:has-text("Connections")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Discovery")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Masking")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Synthetic")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Subsetting")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Workflows")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Jobs")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Compliance")')).toBeVisible();
  });
});
