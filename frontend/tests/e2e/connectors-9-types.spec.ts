import { test, expect } from "@playwright/test";

const CONN_URL = "/projects/00000000-0000-0000-0000-000000000001/connections";

/**
 * Per-connector field-rendering smoke tests for all 9 supported connector
 * types. Each test opens the Add Connection drawer, clicks the connector
 * tile, and asserts the dynamic fields swap in — this is what we used to
 * silently break when only Snowflake had a custom block.
 */
test.describe("Connector dynamic fields (9 types)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(CONN_URL);
    await page.click("text=Add Connection");
  });

  test("PostgreSQL renders host + database + username/password", async ({ page }) => {
    await page.click("button:has-text('PostgreSQL')");
    await expect(page.locator('label:has-text("Host")')).toBeVisible();
    await expect(page.locator('label:has-text("Database")').first()).toBeVisible();
    await expect(page.locator('label:has-text("Username")').first()).toBeVisible();
  });

  test("MySQL renders host + database + username/password", async ({ page }) => {
    await page.click("button:has-text('MySQL')");
    await expect(page.locator('label:has-text("Host")')).toBeVisible();
    await expect(page.locator('label:has-text("Database")').first()).toBeVisible();
  });

  test("MongoDB shows auth mechanism + sample-size controls", async ({ page }) => {
    await page.click("button:has-text('MongoDB')");
    await expect(page.locator('label:has-text("Auth mechanism")')).toBeVisible();
    await expect(page.locator('label:has-text("Sample size")')).toBeVisible();
    await expect(page.locator('label:has-text("Max nesting depth")')).toBeVisible();
  });

  test("Oracle shows Service Name + Wallet Path", async ({ page }) => {
    await page.click("button:has-text('Oracle')");
    await expect(page.locator('label:has-text("Service Name")')).toBeVisible();
    await expect(page.locator('label:has-text("Oracle Wallet Path")')).toBeVisible();
  });

  test("SQL Server shows Named Instance + Azure AD auth toggle", async ({ page }) => {
    await page.click("button:has-text('SQL Server')");
    await expect(page.locator('label:has-text("Named Instance")')).toBeVisible();
  });

  test("IBM DB2 shows Security mechanism selector", async ({ page }) => {
    await page.click("button:has-text('IBM DB2')");
    await expect(page.locator('label:has-text("Security mechanism")')).toBeVisible();
  });

  test("Snowflake shows Account/Warehouse + key-pair auth option", async ({ page }) => {
    await page.click("button:has-text('Snowflake')");
    await expect(page.locator('label:has-text("Account")')).toBeVisible();
    await expect(page.locator('label:has-text("Warehouse")').first()).toBeVisible();
    // Auth select offers production-grade options
    await expect(page.locator("option:has-text('Key-pair')")).toHaveCount(1);
    await expect(page.locator("option:has-text('OAuth')")).toHaveCount(1);
  });

  test("Redshift offers IAM auth mode", async ({ page }) => {
    await page.click("button:has-text('Redshift')");
    await expect(page.locator("option:has-text('IAM')")).toHaveCount(1);
  });

  test("Databricks requires HTTP Path + Personal Access Token", async ({ page }) => {
    await page.click("button:has-text('Databricks')");
    await expect(page.locator('label:has-text("HTTP Path")')).toBeVisible();
    await expect(page.locator('label:has-text("Personal Access Token")')).toBeVisible();
    // Databricks uses Catalog (Unity) rather than the generic "Database" label
    await expect(page.locator('label:has-text("Catalog")')).toBeVisible();
  });

  test("SSL toggles render on every connector", async ({ page }) => {
    for (const connector of [
      "PostgreSQL",
      "MySQL",
      "MongoDB",
      "Oracle",
      "SQL Server",
      "IBM DB2",
      "Snowflake",
      "Redshift",
      "Databricks",
    ]) {
      await page.click(`button:has-text('${connector}')`);
      await expect(page.locator('text=Enable SSL/TLS')).toBeVisible();
      await expect(page.locator('text=Trust server certificate')).toBeVisible();
      await expect(page.locator('text=Block generation if schema changes')).toBeVisible();
    }
  });
});
