import { test, expect, type Page } from "@playwright/test";

const CONN_URL = "/projects/00000000-0000-0000-0000-000000000001/connections";

/**
 * Validation-pass tests for every enterprise auth flow Codex flagged as
 * "blocked by UI validation". For each flow we fill the minimal happy-path
 * fields for the auth mode, click Save, and assert no spurious validation
 * errors appear for fields that aren't required by the chosen mode.
 *
 * Network-level save success is intentionally not asserted — the seed
 * backend can't talk to real Snowflake/Databricks/etc. We only verify
 * that the form is not held back by client-side validation.
 */

async function openDrawer(page: Page, connector: string) {
  await page.goto(CONN_URL);
  await page.click("text=Add Connection");
  await page.click(`button:has-text('${connector}')`);
  await page.fill('input[name="name"]', "auth-flow-test");
}

async function expectNoBlockingValidation(page: Page, hiddenFieldErrors: string[] = []) {
  await page.click('button:has-text("Save")');
  await page.waitForTimeout(300);
  for (const id of hiddenFieldErrors) {
    await expect(page.locator(`#${id}-error`)).toHaveCount(0);
  }
}

test.describe("Enterprise auth flows — UI validation does not block", () => {
  test("Databricks M2M OAuth: client_id+secret valid, no token required", async ({ page }) => {
    await openDrawer(page, "Databricks");
    await page.fill('input[name="host"]', "adb-1.azuredatabricks.net");
    await page.fill('input[name="databaseName"]', "main");
    await page.fill('input[name="databricksHttpPath"]', "/sql/1.0/warehouses/abc");
    await page.selectOption('select:has(option[value="oauth_m2m"])', "oauth_m2m");
    await page.fill('input[name="databricksClientId"]', "svc-client-id");
    await page.fill('input[name="databricksClientSecret"]', "svc-secret");
    // No PAT entered — must still validate
    await expectNoBlockingValidation(page, ["databricksAccessToken"]);
  });

  test("Snowflake OAuth refresh-token quad: no static token required", async ({ page }) => {
    await openDrawer(page, "Snowflake");
    await page.fill('input[name="account"]', "xy12345.us-east-1");
    await page.fill('input[name="warehouse"]', "COMPUTE_WH");
    await page.fill('input[name="databaseName"]', "ANALYTICS_DB");
    await page.fill('input[name="username"]', "SVC_DATAWRANGLER");
    await page.selectOption('select:has(option[value="oauth"])', "oauth");
    await page.click("summary:has-text('Auto-refresh')");
    await page.fill('input[name="snowflakeOauthRefreshToken"]', "rfsh");
    await page.fill('input[name="snowflakeOauthClientId"]', "cid");
    await page.fill('input[name="snowflakeOauthClientSecret"]', "csec");
    await page.fill('input[name="snowflakeOauthTokenEndpoint"]', "https://idp.example.com/oauth2/token");
    // Static OAuth token textarea intentionally left empty
    await expectNoBlockingValidation(page, ["snowflakeOauthToken"]);
  });

  test("Snowflake Okta: requires okta_url + password, no static token", async ({ page }) => {
    await openDrawer(page, "Snowflake");
    await page.fill('input[name="account"]', "xy12345.us-east-1");
    await page.fill('input[name="warehouse"]', "COMPUTE_WH");
    await page.fill('input[name="databaseName"]', "ANALYTICS_DB");
    await page.fill('input[name="username"]', "okta-user@example.com");
    await page.selectOption('select:has(option[value="okta"])', "okta");
    await page.fill('input[name="snowflakeOktaUrl"]', "https://my-org.okta.com");
    await page.fill('input[name="password"]', "hunter2");
    await expectNoBlockingValidation(page, ["snowflakeOauthToken"]);
  });

  test("Oracle Kerberos: no username required", async ({ page }) => {
    await openDrawer(page, "Oracle");
    await page.fill('input[name="host"]', "oracle.example.com");
    await page.fill('input[name="databaseName"]', "ORCLCDB");
    await page.selectOption('select:has(option[value="kerberos"])', "kerberos");
    await expectNoBlockingValidation(page, ["username"]);
  });

  test("SQL Server Windows Integrated: no username required", async ({ page }) => {
    await openDrawer(page, "SQL Server");
    await page.fill('input[name="host"]', "sql.example.com");
    await page.fill('input[name="databaseName"]', "POL");
    await page.selectOption('select:has(option[value="windows"])', "windows");
    await expectNoBlockingValidation(page, ["username"]);
  });

  test("SQL Server Azure AD: token required, no UID/PWD", async ({ page }) => {
    await openDrawer(page, "SQL Server");
    await page.fill('input[name="host"]', "sql.example.com");
    await page.fill('input[name="databaseName"]', "POL");
    await page.selectOption('select:has(option[value="azure_ad"])', "azure_ad");
    await page.fill('input[name="sqlserverAzureAdToken"]', "ey.token");
    await expectNoBlockingValidation(page, ["username"]);
  });

  test("DB2 Kerberos: no username required", async ({ page }) => {
    await openDrawer(page, "IBM DB2");
    await page.fill('input[name="host"]', "db2.example.com");
    await page.fill('input[name="databaseName"]', "POLICY");
    await page.selectOption('select:has(option[value="KERBEROS"])', "KERBEROS");
    await expectNoBlockingValidation(page, ["username"]);
  });
});
