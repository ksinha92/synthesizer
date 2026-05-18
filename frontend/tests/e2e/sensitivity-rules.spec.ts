import { test, expect } from "@playwright/test";

test.describe("Sensitivity Rules", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/sensitivity-rules");
  });

  test("page loads with heading and New Rule button", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Sensitivity Rules");
    await expect(page.locator("button:has-text('New Rule')")).toBeVisible();
  });

  test("New Rule drawer opens with form + Test Results pane (Tonic 11.27.06)", async ({ page }) => {
    await page.click("button:has-text('New Rule')");

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();

    // Form column
    await expect(dialog.locator('label:has-text("Name")').first()).toBeVisible();
    await expect(dialog.locator('label:has-text("Pattern")').first()).toBeVisible();

    // Test Results pane is the differentiator from the old drawer.
    await expect(dialog.locator('h3:has-text("Test results")')).toBeVisible();
    await expect(
      dialog.locator('label:has-text("Candidate columns")')
    ).toBeVisible();
  });

  test("typing a column_name_contains pattern flags matching candidates live", async ({ page }) => {
    await page.click("button:has-text('New Rule')");
    const dialog = page.locator('[role="dialog"]');

    // Default match type is "column_name_contains"; default test corpus
    // includes "ssn" so a pattern of "ssn" should produce ≥1 match.
    const patternInput = dialog.locator('input.font-mono');
    await patternInput.fill("ssn");

    await expect(dialog.locator('text=/[1-9]\\d* of \\d+ match/')).toBeVisible();
  });

  test("invalid regex shows error inline (no crash)", async ({ page }) => {
    await page.click("button:has-text('New Rule')");
    const dialog = page.locator('[role="dialog"]');

    // Switch to regex match type via the first select inside the drawer.
    await dialog.locator('select').first().selectOption("column_name_regex");
    const patternInput = dialog.locator('input.font-mono');
    await patternInput.fill("[unterminated");

    await expect(dialog.locator("text=Invalid regex")).toBeVisible();
  });

  test("Cancel button closes the drawer", async ({ page }) => {
    await page.click("button:has-text('New Rule')");
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await dialog.locator('button:has-text("Cancel")').click();
    await expect(dialog).not.toBeVisible({ timeout: 2000 });
  });
});
