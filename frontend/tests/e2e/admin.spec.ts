import { test, expect } from "@playwright/test";

test.describe("Admin Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/admin");
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Admin");
  });

  test("3 tabs visible", async ({ page }) => {
    await expect(page.locator("button:has-text('Audit Log')")).toBeVisible();
    await expect(page.locator("button:has-text('Access Control')")).toBeVisible();
    await expect(page.locator("button:has-text('AI Settings')")).toBeVisible();
  });

  test("Audit Log tab renders content", async ({ page }) => {
    await page.click("button:has-text('Audit Log')");
    // Should show table or empty state
    await page.waitForTimeout(500);
    const hasTable = await page.locator("table").isVisible();
    const hasEmpty = await page.locator("text=No audit entries").isVisible();
    expect(hasTable || hasEmpty).toBe(true);
  });

  test("Access Control tab shows invite and permissions", async ({ page }) => {
    await page.click("button:has-text('Access Control')");
    await expect(page.locator("text=Invite Member")).toBeVisible();
    await expect(page.locator("text=Role Permissions")).toBeVisible();
  });

  test("Invite Member form opens", async ({ page }) => {
    await page.click("button:has-text('Access Control')");
    await page.click("text=Invite Member");
    await expect(page.locator('input[placeholder="user@ameritas.com"]')).toBeVisible();
    await expect(page.locator("button:has-text('Send')")).toBeVisible();
  });

  test("permission matrix table visible", async ({ page }) => {
    await page.click("button:has-text('Access Control')");
    await expect(page.locator("th:has-text('Admin')")).toBeVisible();
    await expect(page.locator("th:has-text('Editor')")).toBeVisible();
    await expect(page.locator("th:has-text('Viewer')")).toBeVisible();
    await expect(page.locator("td:has-text('View projects')")).toBeVisible();
  });
});

test.describe("AI Settings Tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/admin");
    await page.click("button:has-text('AI Settings')");
  });

  test("provider selector shows Claude and Ollama", async ({ page }) => {
    await expect(page.locator("text=Claude (Anthropic)")).toBeVisible();
    await expect(page.locator("text=Ollama (Self-hosted)")).toBeVisible();
  });

  test("clicking Ollama shows URL and Model inputs", async ({ page }) => {
    await page.click("text=Ollama (Self-hosted)");
    await expect(page.locator("text=Server URL")).toBeVisible();
    await expect(page.locator("text=Model")).toBeVisible();
    await expect(page.locator('input[placeholder="http://localhost:11434"]')).toBeVisible();
  });

  test("clicking Claude shows API Key input", async ({ page }) => {
    await page.click("text=Claude (Anthropic)");
    await expect(page.locator("label:has-text('API Key')")).toBeVisible();
  });

  test("Test Connection button visible", async ({ page }) => {
    await expect(page.locator("button:has-text('Test Connection')")).toBeVisible();
  });

  test("Save Settings button visible", async ({ page }) => {
    await expect(page.locator("button:has-text('Save Settings')")).toBeVisible();
  });
});
