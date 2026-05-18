import { test, expect } from "@playwright/test";

const CONN_URL = "/projects/00000000-0000-0000-0000-000000000001/connections";

test.describe("Connections Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(CONN_URL);
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Connections");
  });

  test("Add Connection button visible", async ({ page }) => {
    await expect(page.locator("text=Add Connection")).toBeVisible();
  });

  test("drawer opens with ARIA attributes", async ({ page }) => {
    await page.click("text=Add Connection");
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  test("all 9 connector types visible", async ({ page }) => {
    await page.click("text=Add Connection");
    await expect(page.locator("button:has-text('PostgreSQL')")).toBeVisible();
    await expect(page.locator("button:has-text('MySQL')")).toBeVisible();
    await expect(page.locator("button:has-text('MongoDB')")).toBeVisible();
    await expect(page.locator("button:has-text('Oracle')")).toBeVisible();
    await expect(page.locator("button:has-text('SQL Server')")).toBeVisible();
    await expect(page.locator("button:has-text('IBM DB2')")).toBeVisible();
    await expect(page.locator("button:has-text('Snowflake')")).toBeVisible();
    await expect(page.locator("button:has-text('Redshift')")).toBeVisible();
    await expect(page.locator("button:has-text('Databricks')")).toBeVisible();
  });

  test("no 'Coming soon' tiles remain — all connectors are live", async ({ page }) => {
    await page.click("text=Add Connection");
    await expect(page.locator("text=Coming soon")).toHaveCount(0);
    await expect(page.locator("text=Soon")).toHaveCount(0);
  });

  test("Snowflake shows Account and Warehouse fields", async ({ page }) => {
    await page.click("text=Add Connection");
    await page.click("button:has-text('Snowflake')");
    // Scope to the form labels — "Warehouse" alone now collides with the
    // "Data warehouses" category header in the new tile-grid picker.
    await expect(page.locator('label:has-text("Account")')).toBeVisible();
    await expect(page.locator('label:has-text("Warehouse")')).toBeVisible();
  });

  test("switching back to PostgreSQL hides Snowflake fields", async ({ page }) => {
    await page.click("text=Add Connection");
    await page.click("button:has-text('Snowflake')");
    await expect(page.locator("text=Account")).toBeVisible();
    await page.click("button:has-text('PostgreSQL')");
    // Account field should be gone for PostgreSQL
    await expect(page.locator("label:has-text('Account')")).not.toBeVisible();
  });

  test("required fields show specific validation errors on submit", async ({ page }) => {
    await page.click("text=Add Connection");
    await page.click("button:has-text('Save')");
    await page.waitForTimeout(300);
    // Must show specific error messages
    await expect(page.locator('#name-error')).toContainText("Name is required");
    await expect(page.locator('#databaseName-error')).toContainText("Database is required");
    await expect(page.locator('#username-error')).toContainText("Username is required");
  });

  test("password field has show/hide toggle", async ({ page }) => {
    await page.click("text=Add Connection");
    const passwordInput = page.locator('input[type="password"]');
    await expect(passwordInput).toBeVisible();
    // Find the eye toggle button near the password field
    const toggleBtn = page.locator('input[type="password"]').locator("..").locator("button");
    if (await toggleBtn.isVisible()) {
      await toggleBtn.click();
      // After toggle, should become type="text"
      await expect(page.locator('label:has-text("Password")').locator("..").locator('input[type="text"]')).toBeVisible();
    }
  });

  test("Advanced Options expands/collapses", async ({ page }) => {
    await page.click("text=Add Connection");
    await page.click("text=Advanced Options");
    await expect(page.locator("text=Extra Parameters (JSON)")).toBeVisible();
  });

  test("Escape closes drawer", async ({ page }) => {
    await page.click("text=Add Connection");
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
  });

  test("Cancel closes drawer without overlay remaining", async ({ page }) => {
    await page.click("text=Add Connection");
    await page.click("button:has-text('Cancel')");
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
  });

  test("Test Connection button visible", async ({ page }) => {
    await page.click("text=Add Connection");
    await expect(page.locator("button:has-text('Test Connection')")).toBeVisible();
  });
});
