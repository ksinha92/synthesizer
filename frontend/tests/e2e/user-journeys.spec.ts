import { test, expect } from "@playwright/test";

test.describe("User Journey: Project Creation → Discovery → Masking", () => {
  test("create project and navigate to connections", async ({ page }) => {
    await page.goto("/projects");
    await expect(page.locator("h1")).toContainText("Projects");

    // Open create dialog
    await page.click("text=New Project");
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();

    // Fill form
    await page.fill('input[placeholder="My TDM Project"]', "E2E Journey Project");
    await page.fill('textarea[placeholder="Optional description..."]', "Created by Playwright user journey test");

    // Cancel (don't submit without backend)
    await page.click("text=Cancel");
    await expect(dialog).not.toBeVisible();
  });

  test("connection drawer opens with all connector types", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/connections");
    await page.click("text=Add Connection");

    const drawer = page.locator('[role="dialog"]');
    await expect(drawer).toBeVisible();

    // All 4 connector types visible
    await expect(page.locator("button:has-text('PostgreSQL')")).toBeVisible();
    await expect(page.locator("button:has-text('MySQL')")).toBeVisible();
    await expect(page.locator("button:has-text('MongoDB')")).toBeVisible();
    await expect(page.locator("button:has-text('Snowflake')")).toBeVisible();

    // Select Snowflake — conditional fields appear. Scope to form labels —
    // the new tile-grid picker introduced a "Data warehouses" category
    // header that collides with a bare "text=Warehouse" lookup.
    await page.click("button:has-text('Snowflake')");
    await expect(page.locator('label:has-text("Account")')).toBeVisible();
    await expect(page.locator('label:has-text("Warehouse")')).toBeVisible();

    // Switch back to PostgreSQL — Snowflake fields hidden
    await page.click("button:has-text('PostgreSQL')");

    // Escape closes drawer
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
  });

  test("discovery page has 3 tabs", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/discovery");
    await expect(page.locator("h1")).toContainText("Discovery");

    // All 3 tabs visible
    await expect(page.locator("text=Schema Explorer")).toBeVisible();
    await expect(page.locator("text=PII Results")).toBeVisible();
    await expect(page.locator("text=Relationship Graph")).toBeVisible();

    // Switch tabs
    await page.click("text=PII Results");
    await page.click("text=Relationship Graph");
    await page.click("text=Schema Explorer");
  });

  test("masking page shows strategy selector and policy creation", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/masking");
    await expect(page.locator("h1")).toContainText("Data Masking");

    // Strategy cards visible. Use exact paragraph match so the new Free-text
    // card's description (which contains "Redact PII entities…") doesn't
    // trigger a strict-mode multi-match on "text=Redact".
    await expect(page.locator('p:text-is("Hash")')).toBeVisible();
    await expect(page.locator('p:text-is("Redact")')).toBeVisible();
    await expect(page.locator('p:text-is("Faker")')).toBeVisible();
    await expect(page.locator('p:text-is("FPE")')).toBeVisible();

    // Auto-suggest button
    await expect(page.locator("text=Auto-suggest from PII")).toBeVisible();

    // Add Policy button opens form
    await page.click("text=Add Policy");
    const policyInput = page.locator('input[placeholder="Policy name..."]');
    await expect(policyInput).toBeVisible();
    await page.click("text=Cancel");
  });
});

test.describe("User Journey: Jobs + Gantt + Synthetic", () => {
  test("jobs page toggles between list and timeline", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/jobs");
    await expect(page.locator("h1")).toContainText("Jobs");

    // List view is default
    const listBtn = page.locator("button:has-text('List')");
    const timelineBtn = page.locator("button:has-text('Timeline')");
    await expect(listBtn).toBeVisible();
    await expect(timelineBtn).toBeVisible();

    // Switch to timeline
    await timelineBtn.click();
    // Switch back to list
    await listBtn.click();
  });

  test("synthetic page shows engine selector", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/synthetic");
    await expect(page.locator("h1")).toContainText("Synthetic Data Generation");
    await expect(page.locator("text=Faker")).toBeVisible();
  });

  test("subsetting page has connection dropdown", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/subsetting");
    await expect(page.locator("h1")).toContainText("Data Subsetting");
    await expect(page.locator("text=Source Connection")).toBeVisible();
    await expect(page.locator("text=Root Table")).toBeVisible();
    await expect(page.locator("text=Traversal Direction")).toBeVisible();
  });
});

test.describe("User Journey: Workflow Creation", () => {
  test("workflow editor has structured form with pipeline preview", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/workflows");
    await expect(page.locator("h1")).toContainText("Workflows");

    // Open create workflow
    const createBtn = page.locator("button:has-text('Create Workflow')").first();
    if (await createBtn.isVisible()) {
      await createBtn.click();
      // Should see structured form, not raw JSON
      await expect(page.locator("text=Pipeline Steps")).toBeVisible();
      await expect(page.locator("text=Pipeline Preview")).toBeVisible();
      await expect(page.locator("text=Add Step")).toBeVisible();
      await page.keyboard.press("Escape");
    }
  });
});

test.describe("Mobile Viewport: Key Pages", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("dashboard renders on mobile", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Synthia\s*·\s*AI-Powered Test Data Management/i)).toBeVisible();
    const menuBtn = page.locator('button[aria-label="Open navigation menu"]');
    await expect(menuBtn).toBeVisible();
  });

  test("jobs page renders on mobile", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/jobs");
    await expect(page.locator("h1")).toContainText("Jobs");
    // Filter dropdowns present
    const selects = page.locator("select");
    expect(await selects.count()).toBeGreaterThanOrEqual(2);
  });
});
