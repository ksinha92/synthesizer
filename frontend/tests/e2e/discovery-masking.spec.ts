import { test, expect } from "@playwright/test";

const PID = "00000000-0000-0000-0000-000000000001";

test.describe("Discovery Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PID}/discovery`);
  });

  test("page loads with heading and 3 tabs", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Discovery");
    await expect(page.locator("text=Schema Explorer")).toBeVisible();
    await expect(page.locator("text=PII Results")).toBeVisible();
    await expect(page.locator("text=Relationship Graph")).toBeVisible();
  });

  test("tab switching works", async ({ page }) => {
    await page.click("text=PII Results");
    await page.click("text=Relationship Graph");
    // Graph tab should load without crash
    await page.waitForTimeout(1000);
    await page.click("text=Schema Explorer");
  });

  test("Run Discovery button and connection dropdown visible", async ({ page }) => {
    await expect(page.locator("button:has-text('Run Discovery')")).toBeVisible();
    const select = page.locator("select").first();
    await expect(select).toBeVisible();
  });

  test("Run Discovery disabled without connection selected", async ({ page }) => {
    const runBtn = page.locator("button:has-text('Run Discovery')");
    await expect(runBtn).toBeDisabled();
  });
});

test.describe("Masking Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PID}/masking`);
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Data Masking");
  });

  test("Auto-suggest button visible", async ({ page }) => {
    await expect(page.locator("text=Auto-suggest from PII")).toBeVisible();
  });

  test("Add Policy button opens form", async ({ page }) => {
    const addBtn = page.locator("button:has-text('Add Policy')");
    await addBtn.click();
    await expect(page.locator('input[placeholder="Policy name..."]')).toBeVisible();
  });

  test("Cancel hides policy form", async ({ page }) => {
    await page.click("text=Add Policy");
    await expect(page.locator('input[placeholder="Policy name..."]')).toBeVisible();
    // Find the Cancel button near the Create button
    const cancelBtn = page.locator("button:has-text('Cancel')").last();
    await cancelBtn.click();
    await expect(page.locator('input[placeholder="Policy name..."]')).not.toBeVisible();
  });

  test("masking strategy cards visible", async ({ page }) => {
    // Use exact text matches scoped to the strategy-card paragraph nodes —
    // a substring "text=Redact" now also catches the "Free-text" card's
    // description ("Redact PII entities in narrative text…").
    await expect(page.locator('p:text-is("Hash")')).toBeVisible();
    await expect(page.locator('p:text-is("Redact")')).toBeVisible();
    await expect(page.locator('p:text-is("Faker")')).toBeVisible();
    await expect(page.locator('p:text-is("Shuffle")')).toBeVisible();
    await expect(page.locator('p:text-is("Nullify")')).toBeVisible();
    await expect(page.locator('p:text-is("FPE")')).toBeVisible();
    await expect(page.locator('p:text-is("Partial")')).toBeVisible();
    await expect(page.locator('p:text-is("Free-text")')).toBeVisible();
  });

  test("strategy cards are clickable and change selection", async ({ page }) => {
    // Pinpoint the card by the exact label paragraph, then walk up to the
    // button so we don't conflict with the Free-text card's "Redact PII…"
    // description text.
    const hashCard = page.locator('button:has(p:text-is("Hash"))');
    await hashCard.click();
    await expect(hashCard).toHaveClass(/border-primary/);

    const redactCard = page.locator('button:has(p:text-is("Redact"))');
    await redactCard.click();
    await expect(redactCard).toHaveClass(/border-primary/);
  });
});
