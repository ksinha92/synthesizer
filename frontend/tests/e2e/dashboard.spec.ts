import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("page loads with hero + Synthia brand", async ({ page }) => {
    // Hero h1 is dynamic (greeting / compliance message), but the brand subtitle is stable.
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.getByText(/Synthia\s*·\s*AI-Powered Test Data Management/i)).toBeVisible();
  });

  test("executive KPI row renders four cards with stable labels", async ({ page }) => {
    // Wait for the initial aggregate fetch + render
    await page.waitForTimeout(3000);
    await expect(page.locator("p:has-text('Compliance score')")).toBeVisible();
    await expect(page.locator("p:has-text('Data at risk')")).toBeVisible();
    await expect(page.locator("p:has-text('Data velocity')")).toBeVisible();
    await expect(page.locator("p:has-text('Pipeline activity')")).toBeVisible();
  });

  test("Insights heading and Coverage section render", async ({ page }) => {
    await expect(page.locator("h2:has-text('What needs your attention')")).toBeVisible();
    await expect(page.locator("h2:has-text('Coverage by table')")).toBeVisible();
  });

  test("PII heatmap and Pipeline health sections visible", async ({ page }) => {
    await expect(page.locator("h2:has-text('PII density heatmap')")).toBeVisible();
    await expect(page.locator("h2:has-text('Pipeline health')")).toBeVisible();
  });

  test("Recent activity section visible", async ({ page }) => {
    await expect(page.locator("h2:has-text('Recent activity')")).toBeVisible();
  });

  test("Refresh button is present and clickable", async ({ page }) => {
    const refresh = page.locator('button[aria-label="Refresh dashboard data"]');
    await expect(refresh).toBeVisible();
    await refresh.click();
  });

  test("global nav has brand + Projects + Admin links", async ({ page }) => {
    const nav = page.locator('nav[aria-label="Global navigation"]');
    await expect(nav.locator('a[href="/"]')).toBeVisible();
    await expect(nav.locator('a[href="/projects"]')).toBeVisible();
    await expect(nav.locator('a[href="/admin"]')).toBeVisible();
  });

  test("clicking Projects in nav navigates", async ({ page }) => {
    await page.locator('nav[aria-label="Global navigation"] a[href="/projects"]').click();
    await expect(page.locator("h1")).toContainText("Projects");
  });

  test("header has search, assistant, notification, and user buttons", async ({ page }) => {
    const nav = page.locator('nav[aria-label="Global navigation"]');
    await expect(nav.locator('button[aria-label="Open command palette"]')).toBeVisible();
    await expect(nav.locator('button[aria-label="Open AI assistant"]')).toBeVisible();
    await expect(nav.locator('button[aria-label="User menu"]')).toBeVisible();
    await expect(nav.locator('button[aria-label^="Open notifications"]')).toBeVisible();
  });

  test("theme toggle: light → dark → light", async ({ page }) => {
    const html = page.locator("html");
    await page.locator('button[title="Dark"]').click();
    await expect(html).toHaveClass(/dark/);
    await page.locator('button[title="Light"]').click();
    await expect(html).not.toHaveClass(/dark/);
  });

  test("command palette opens via toolbar button and closes on Escape", async ({ page }) => {
    await page.locator('button[aria-label="Open command palette"]').click();
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 2000 });
    await page.keyboard.press("Escape");
    await expect(searchInput).not.toBeVisible();
  });
});

test.describe("Dashboard Mobile", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("no horizontal overflow on mobile", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Synthia\s*·\s*AI-Powered Test Data Management/i)).toBeVisible();
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
    const windowWidth = await page.evaluate(() => window.innerWidth);
    expect(bodyScrollWidth).toBeLessThanOrEqual(windowWidth + 1);
  });

  test("mobile menu button visible and toggles drawer", async ({ page }) => {
    await page.goto("/");
    const menuBtn = page.locator('button[aria-label="Open navigation menu"]');
    await expect(menuBtn).toBeVisible();
    await menuBtn.click();
    const mobileDrawer = page.locator("#global-mobile-menu");
    await expect(mobileDrawer).toBeVisible();
    await menuBtn.click();
    await expect(mobileDrawer).not.toBeVisible();
  });
});
