import { test, expect } from "@playwright/test";

test.describe("Synthia Full Workflow", () => {
  test("navigates through all major pages", async ({ page }) => {
    // Dashboard
    await page.goto("/");
    await expect(page.getByText(/Synthia\s*·\s*AI-Powered Test Data Management/i)).toBeVisible();
    // Phase 48 UX refactor: links live in the global <nav>, not an <aside>.
    await expect(page.locator('nav[aria-label="Global navigation"] a[href="/projects"]')).toBeVisible();

    // Navigate to Projects
    await page.click('a[href="/projects"]');
    await expect(page.locator("h1")).toContainText("Projects");

    // Create project button visible
    const newProjectBtn = page.locator("button:has-text('New Project')");
    await expect(newProjectBtn).toBeVisible();

    // Open create dialog
    await newProjectBtn.click();
    await expect(page.locator("text=New Project").nth(1)).toBeVisible();

    // Fill and submit (will fail without backend, but verifies UI renders)
    await page.fill('input[placeholder="My TDM Project"]', "E2E Test Project");
    await page.fill('textarea[placeholder="Optional description..."]', "Created by Playwright");

    // Close dialog (don't submit — no backend in E2E)
    await page.click("text=Cancel");

    // Navigate to a mock project URL to verify layout
    await page.goto("/projects/00000000-0000-0000-0000-000000000001");

    // Verify project layout renders with workspace tab bar (Phase 48 refactor:
    // per-project navigation moved from <aside> sidebar to top tabs).
    await page.waitForTimeout(1000);
    const tabs = page.locator('[role="tablist"][aria-label="Workspace sections"]');
    await expect(tabs.locator('[role="tab"]:has-text("Connections")')).toBeVisible();
    await expect(tabs.locator('[role="tab"]:has-text("Discovery")')).toBeVisible();

    // Navigate to connections
    await tabs.locator('[role="tab"]:has-text("Connections")').click();
    await page.waitForURL("**/connections");
    await expect(page.locator("h1")).toContainText("Connections");
    await expect(page.locator("text=Add Connection")).toBeVisible();

    // Open connection drawer
    await page.click("text=Add Connection");
    await expect(page.locator("text=Connector Type")).toBeVisible();
    await expect(page.locator("text=PostgreSQL")).toBeVisible();
    await expect(page.locator("text=MySQL")).toBeVisible();
    await expect(page.locator("text=MongoDB")).toBeVisible();
    await expect(page.locator("text=Snowflake")).toBeVisible();

    // Select Snowflake — verify dynamic fields. Scope to label so the
    // "Data warehouses" category header in the tile-grid picker doesn't
    // double-match "Warehouse".
    await page.click("button:has-text('Snowflake')");
    await expect(page.locator('label:has-text("Account")')).toBeVisible();
    await expect(page.locator('label:has-text("Warehouse")')).toBeVisible();

    // Close drawer
    await page.keyboard.press("Escape");

    // Navigate to discovery
    await page.click('a:has-text("Discovery")');
    await page.waitForURL("**/discovery");
    await expect(page.locator("h1")).toContainText("Discovery");
    await expect(page.locator("text=Schema Explorer")).toBeVisible();
    await expect(page.locator("text=PII Results")).toBeVisible();

    // Navigate to synthetic
    await page.click('a:has-text("Synthetic")');
    await page.waitForURL("**/synthetic");
    await expect(page.locator("h1")).toContainText("Synthetic Data Generation");
    await expect(page.locator("text=Faker")).toBeVisible();

    // Navigate to masking
    await page.click('a:has-text("Masking")');
    await page.waitForURL("**/masking");
    await expect(page.locator("h1")).toContainText("Data Masking");

    // Navigate to subsetting
    await page.click('a:has-text("Subsetting")');
    await page.waitForURL("**/subsetting");
    await expect(page.locator("h1")).toContainText("Data Subsetting");

    // Navigate to workflows
    await page.click('a:has-text("Workflows")');
    await page.waitForURL("**/workflows");
    await expect(page.locator("h1")).toContainText("Workflows");

    // Navigate to jobs
    await page.click('a:has-text("Jobs")');
    await page.waitForURL("**/jobs");
    await expect(page.locator("h1")).toContainText("Jobs");

    // Navigate to compliance
    await page.click('a:has-text("Compliance")');
    await page.waitForURL("**/compliance");
    await expect(page.locator("h1")).toContainText("Compliance");

    // Navigate to admin
    await page.goto("/admin");
    await expect(page.locator("h1")).toContainText("Admin");
    await expect(page.locator("text=Audit Log")).toBeVisible();

    // Verify 404 page
    await page.goto("/this-page-does-not-exist");
    await expect(page.locator("text=404")).toBeVisible();
    await expect(page.locator("text=Page not found")).toBeVisible();
    await expect(page.locator("text=Go to Dashboard")).toBeVisible();
  });

  test("theme toggle switches modes", async ({ page }) => {
    await page.goto("/");

    // Find theme toggle area (3 buttons in the toggle group)
    const html = page.locator("html");

    // Default is system — check no explicit class or dark class based on OS
    // Click dark mode button (Moon icon)
    const darkBtn = page.locator('button[title="Dark"]');
    if (await darkBtn.isVisible()) {
      await darkBtn.click();
      await expect(html).toHaveClass(/dark/);
    }

    // Click light mode button (Sun icon)
    const lightBtn = page.locator('button[title="Light"]');
    if (await lightBtn.isVisible()) {
      await lightBtn.click();
      await expect(html).not.toHaveClass(/dark/);
    }
  });

  test("global nav is sticky and brand link is visible", async ({ page }) => {
    // Phase 48 UX refactor: the collapsible <aside> sidebar was replaced by
    // a fixed two-bar shell (global + workspace tabs). The old collapse test
    // no longer maps to any UI; this is the replacement smoke test.
    await page.goto("/");

    const nav = page.locator('nav[aria-label="Global navigation"]');
    await expect(nav).toBeVisible();
    await expect(nav.locator('a[href="/"]')).toBeVisible();
    // Scroll and confirm nav stays in view (sticky positioning).
    await page.evaluate(() => window.scrollTo(0, 600));
    await expect(nav).toBeInViewport();
  });
});
