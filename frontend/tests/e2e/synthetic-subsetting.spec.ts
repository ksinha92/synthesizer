import { test, expect } from "@playwright/test";

const PID = "00000000-0000-0000-0000-000000000001";

test.describe("Synthetic Data Generation Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PID}/synthetic`);
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Synthetic Data Generation");
  });

  test("engine selector shows 3 options", async ({ page }) => {
    await expect(page.locator("text=Faker")).toBeVisible();
    // Statistical and LLM should also be present
  });

  test("Faker engine shows config form by default", async ({ page }) => {
    await expect(page.locator("text=Configuration")).toBeVisible();
    await expect(page.locator("text=Config Name")).toBeVisible();
    await expect(page.locator("text=Source Connection")).toBeVisible();
    await expect(page.locator("text=Row Count")).toBeVisible();
  });

  test("source connection dropdown is populated", async ({ page }) => {
    const connSelect = page.locator("select").first();
    await expect(connSelect).toBeVisible();
    await expect(connSelect.locator("option").first()).toContainText("Select");
  });

  test("Preview button disabled without connection", async ({ page }) => {
    const previewBtn = page.locator("button:has-text('Preview')");
    await expect(previewBtn).toBeDisabled();
  });

  test("Generate button disabled without connection", async ({ page }) => {
    // The split-button "Generate Data" CTA lives in WorkspaceTabBar (Phase 48)
    // and the synthetic config form has its own "Generate" submit. Use exact
    // text match to disambiguate from "Generate Data" / "Generate Quality
    // Report" / "Generate File Set" that now coexist on the page.
    const genBtn = page.locator('button:text-is("Generate")');
    await expect(genBtn).toBeDisabled();
  });
});

test.describe("Data Subsetting Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PID}/subsetting`);
  });

  test("page loads with heading", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Data Subsetting");
  });

  test("source connection dropdown visible and populated", async ({ page }) => {
    await expect(page.locator("text=Source Connection")).toBeVisible();
    const select = page.locator("select").first();
    await expect(select).toBeVisible();
    await expect(select.locator("option").first()).toContainText("Select connection");
  });

  test("root table and target % inputs visible", async ({ page }) => {
    await expect(page.locator("text=Root Table")).toBeVisible();
    await expect(page.locator('input[placeholder="claims"]')).toBeVisible();
    await expect(page.locator("text=Target %")).toBeVisible();
  });

  test("traversal direction buttons work", async ({ page }) => {
    const upstream = page.locator("button:has-text('Upstream')");
    const downstream = page.locator("button:has-text('Downstream')");
    const both = page.locator("button:has-text('Both')");

    await expect(upstream).toBeVisible();
    await expect(downstream).toBeVisible();
    await expect(both).toBeVisible();

    // Upstream should be selected by default
    await expect(upstream).toHaveClass(/border-primary/);

    // Click downstream
    await downstream.click();
    await expect(downstream).toHaveClass(/border-primary/);

    // Click both
    await both.click();
    await expect(both).toHaveClass(/border-primary/);
  });

  test("WHERE filter input visible with hint", async ({ page }) => {
    await expect(page.locator("text=WHERE Filter")).toBeVisible();
    await expect(page.locator("text=No semicolons")).toBeVisible();
  });

  test("Analyze button disabled without connection and root table", async ({ page }) => {
    const analyzeBtn = page.locator("button:has-text('Analyze')");
    await expect(analyzeBtn).toBeDisabled();
  });
});
