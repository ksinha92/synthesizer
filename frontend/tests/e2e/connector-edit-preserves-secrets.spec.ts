import { test, expect, type Page } from "@playwright/test";

/**
 * Regression test for the edit-save-wipes-secrets bug Codex flagged.
 *
 * Setup: intercept the connection list + single-connection GET to return
 * a Snowflake key-pair connection whose ``safe_extras`` carries a redacted
 * ``private_key_pem`` (empty string, key present). When the edit drawer
 * opens, parseConnectionPayload should set ``snowflakePrivateKeyPemHasStored``
 * so the user can change only the connection name and click Save without
 * the "Private key PEM is required" validation triggering.
 */

const PROJECT_ID = "00000000-0000-0000-0000-000000000001";
const CONN_ID = "11111111-1111-1111-1111-111111111111";

const STORED_SNOWFLAKE_KEY_PAIR = {
  id: CONN_ID,
  project_id: PROJECT_ID,
  name: "prod-snowflake",
  connector_type: "snowflake",
  host: "xy12345.us-east-1.snowflakecomputing.com",
  port: 443,
  database_name: "ANALYTICS",
  username: "SVC_USER",
  status: "connected",
  last_tested_at: null,
  created_at: "2026-05-17T00:00:00Z",
  updated_at: "2026-05-17T00:00:00Z",
  safe_extras: {
    account: "xy12345.us-east-1",
    warehouse: "COMPUTE_WH",
    role: "SYSADMIN",
    auth_mode: "key_pair",
    // Secret: returned as empty string with the KEY present.
    private_key_pem: "",
    private_key_passphrase: "",
  },
};

const STORED_DATABRICKS_M2M = {
  id: CONN_ID,
  project_id: PROJECT_ID,
  name: "prod-databricks",
  connector_type: "databricks",
  host: "adb-1.azuredatabricks.net",
  port: 443,
  database_name: "main",
  username: "",
  status: "connected",
  last_tested_at: null,
  created_at: "2026-05-17T00:00:00Z",
  updated_at: "2026-05-17T00:00:00Z",
  safe_extras: {
    http_path: "/sql/1.0/warehouses/abc",
    auth_mode: "oauth_m2m",
    databricks_client_id: "svc-client",
    databricks_client_secret: "",  // redacted
  },
};

async function mockConnectionApi(page: Page, stored: object) {
  await page.route(/\/api\/v1\/projects\/.+\/connections(\?|\/|$)/, async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const isSingleByConnId = url.includes(`/connections/${CONN_ID}`);

    if (method === "GET" && isSingleByConnId) {
      await route.fulfill({ status: 200, body: JSON.stringify(stored) });
      return;
    }
    if (method === "GET" && !isSingleByConnId) {
      await route.fulfill({
        status: 200,
        body: JSON.stringify({
          items: [stored],
          total_count: 1,
          page: 1,
          page_size: 50,
          has_more: false,
        }),
      });
      return;
    }
    if (method === "PUT" && isSingleByConnId) {
      const body = JSON.parse(route.request().postData() || "{}");
      (page as unknown as { _lastPutBody: unknown })._lastPutBody = body;
      await route.fulfill({ status: 200, body: JSON.stringify({ ...stored, name: body.name }) });
      return;
    }
    await route.continue();
  });
}

test.describe("Edit-save preserves redacted secrets", () => {
  test("Snowflake key-pair: rename only, save succeeds, PEM not sent as wipe", async ({ page }) => {
    await mockConnectionApi(page, STORED_SNOWFLAKE_KEY_PAIR);

    await page.goto(`/projects/${PROJECT_ID}/connections`);
    await page.waitForSelector("text=prod-snowflake");
    await page.click('button[aria-label="Edit connection"], button:has-text("Edit")');
    await page.waitForSelector('input[name="name"]');

    // Form should have hydrated to key_pair mode without complaining
    await expect(page.locator('select').first()).toBeVisible();

    // Change only the name
    await page.fill('input[name="name"]', "renamed-snowflake");
    await page.click('button:has-text("Update"), button:has-text("Save")');
    await page.waitForTimeout(500);

    // Validation must not block — the PEM error must NOT appear
    await expect(page.locator("#snowflakePrivateKeyPem-error")).toHaveCount(0);

    // PUT body should have private_key_pem as empty string (signalling "preserve")
    const body = (page as any)._lastPutBody;
    expect(body).toBeTruthy();
    expect(body.extra_params.auth_mode).toBe("key_pair");
    // The redacted-blank PEM is sent through; the backend merge preserves
    // the stored value when it sees an empty secret.
    expect(body.extra_params.private_key_pem).toBe("");
  });

  test("Databricks M2M: redacted client_secret does not block validation", async ({ page }) => {
    await mockConnectionApi(page, STORED_DATABRICKS_M2M);

    await page.goto(`/projects/${PROJECT_ID}/connections`);
    await page.waitForSelector("text=prod-databricks");
    await page.click('button[aria-label="Edit connection"], button:has-text("Edit")');
    await page.waitForSelector('input[name="name"]');
    // useEffect refetch settles
    await page.waitForTimeout(200);

    await page.fill('input[name="name"]', "renamed-databricks");
    await page.click('button:has-text("Update"), button:has-text("Save")');
    await page.waitForTimeout(300);

    // The whole point: redacted Client Secret must NOT produce a validation error.
    await expect(page.locator("#databricksClientSecret-error")).toHaveCount(0);
    // Form should have moved past validation — Save button no longer rendering an error.
    await expect(page.locator('text="Client Secret is required for M2M OAuth"')).toHaveCount(0);
  });
});
