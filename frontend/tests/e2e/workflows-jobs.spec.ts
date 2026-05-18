import { test, expect } from "@playwright/test";

const PID = "00000000-0000-0000-0000-000000000001";

test.describe("Workflows Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PID}/workflows`);
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Workflows");
  });

  test("Create Workflow button opens editor", async ({ page }) => {
    await page.click("text=Create Workflow");
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  test("editor has structured form with pipeline steps", async ({ page }) => {
    await page.click("text=Create Workflow");
    await expect(page.locator("text=Pipeline Steps")).toBeVisible();
    await expect(page.locator("text=Pipeline Preview")).toBeVisible();
    await expect(page.locator("text=Add Step")).toBeVisible();
  });

  test("default 3 nodes visible", async ({ page }) => {
    await page.click("text=Create Workflow");
    // Should have 3 node type dropdowns
    const selects = page.locator('[role="dialog"] select');
    await expect(selects).toHaveCount(3);
  });

  test("Add Step adds a node", async ({ page }) => {
    await page.click("text=Create Workflow");
    const selectsBefore = await page.locator('[role="dialog"] select').count();
    await page.click("text=Add Step");
    const selectsAfter = await page.locator('[role="dialog"] select').count();
    expect(selectsAfter).toBe(selectsBefore + 1);
  });

  test("node type dropdown has 5 options", async ({ page }) => {
    await page.click("text=Create Workflow");
    const firstSelect = page.locator('[role="dialog"] select').first();
    const options = firstSelect.locator("option");
    await expect(options).toHaveCount(5);
  });

  test("Escape closes editor without overlay", async ({ page }) => {
    await page.click("text=Create Workflow");
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
    await expect(page.locator(".bg-black\\/50")).not.toBeVisible();
  });

  test("workflow name required for save", async ({ page }) => {
    await page.click("text=Create Workflow");
    const saveBtn = page.locator("button:has-text('Create Workflow')").last();
    await expect(saveBtn).toBeDisabled();
  });
});

test.describe("Jobs Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PID}/jobs`);
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Jobs");
  });

  test("List/Timeline toggle visible", async ({ page }) => {
    await expect(page.locator("button:has-text('List')")).toBeVisible();
    await expect(page.locator("button:has-text('Timeline')")).toBeVisible();
  });

  test("toggle between list and timeline view", async ({ page }) => {
    await page.click("button:has-text('Timeline')");
    // Should switch to timeline view
    await page.click("button:has-text('List')");
    // Should switch back to list view
  });

  test("type filter dropdown works", async ({ page }) => {
    const typeSelect = page.locator("select").first();
    await expect(typeSelect).toBeVisible();
    await typeSelect.selectOption("discovery");
    await expect(typeSelect).toHaveValue("discovery");
    await typeSelect.selectOption("");
  });

  test("status filter dropdown works", async ({ page }) => {
    const statusSelect = page.locator("select").nth(1);
    await expect(statusSelect).toBeVisible();
    await statusSelect.selectOption("completed");
    await expect(statusSelect).toHaveValue("completed");
    await statusSelect.selectOption("");
  });
});
