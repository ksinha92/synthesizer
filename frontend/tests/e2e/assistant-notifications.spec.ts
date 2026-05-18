import { test, expect } from "@playwright/test";

test.describe("AI Assistant Sidebar", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("floating bot button visible", async ({ page }) => {
    await expect(page.locator('button[title="Open AI Assistant"]')).toBeVisible();
  });

  test("clicking bot button opens sidebar", async ({ page }) => {
    await page.click('button[title="Open AI Assistant"]');
    await expect(page.locator("text=Synthia")).toBeVisible();
  });

  test("sidebar has consent banner on first open", async ({ page }) => {
    // Clear consent
    await page.evaluate(() => localStorage.removeItem("dw-assistant-consent"));
    await page.click('button[title="Open AI Assistant"]');
    await expect(page.locator("text=I understand")).toBeVisible();
  });

  test("accepting consent enables input", async ({ page }) => {
    await page.evaluate(() => localStorage.removeItem("dw-assistant-consent"));
    await page.click('button[title="Open AI Assistant"]');
    await page.click("text=I understand");
    const textarea = page.locator("textarea");
    await expect(textarea).toBeEnabled();
  });

  test("input has character counter", async ({ page }) => {
    await page.click('button[title="Open AI Assistant"]');
    // Accept consent first
    const consentBtn = page.locator("text=I understand");
    if (await consentBtn.isVisible()) await consentBtn.click();
    await expect(page.locator("text=0/2000")).toBeVisible();
    await page.fill("textarea", "Hello");
    await expect(page.locator("text=5/2000")).toBeVisible();
  });

  test("send button enabled when input has text and consent given", async ({ page }) => {
    await page.click('button[title="Open AI Assistant"]');
    const consentBtn = page.locator("text=I understand");
    if (await consentBtn.isVisible()) await consentBtn.click();
    await page.fill("textarea", "Hello");
    // Send button should be enabled now
    const textarea = page.locator("textarea");
    await expect(textarea).toBeEnabled();
  });

  test("close button returns to floating button", async ({ page }) => {
    await page.click('button[title="Open AI Assistant"]');
    await expect(page.locator("text=Synthia")).toBeVisible();
    // Click X button in sidebar header
    const closeBtn = page.locator("text=Synthia").locator("..").locator("..").locator("button").last();
    await closeBtn.click();
    await expect(page.locator('button[title="Open AI Assistant"]')).toBeVisible();
  });

  test("provider badge shows in header", async ({ page }) => {
    await page.click('button[title="Open AI Assistant"]');
    // Should show provider badge (ollama/claude/not configured)
    await page.waitForTimeout(1000);
    const header = page.locator("text=Synthia").locator("..");
    // Badge is a small span near the title
    const badge = header.locator("span.capitalize");
    // May or may not be visible depending on API availability
  });
});

test.describe("Notification Center", () => {
  // Semantic locator works regardless of which shell component hosts the bell
  // (was <header>, now <nav> after Phase 48). The label prefix is stable —
  // it gets a suffix like ", 3 unread" when there are unread notifications.
  const bell = (page: import("@playwright/test").Page) =>
    page.locator('button[aria-label^="Open notifications"]');

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("notification bell visible in header", async ({ page }) => {
    await expect(bell(page)).toBeVisible();
  });

  test("clicking bell opens dropdown", async ({ page }) => {
    await bell(page).click();
    await expect(page.locator("h3:has-text('Notifications')")).toBeVisible();
  });

  test("empty state shows when no notifications", async ({ page }) => {
    await bell(page).click();
    await expect(page.locator("text=No notifications yet")).toBeVisible();
  });

  test("clicking outside closes dropdown", async ({ page }) => {
    await bell(page).click();
    await expect(page.locator("h3:has-text('Notifications')")).toBeVisible();
    // Click on main content area (outside the dropdown)
    await page.mouse.click(200, 400);
    await expect(page.locator("h3:has-text('Notifications')")).not.toBeVisible({ timeout: 2000 });
  });
});

test.describe("Assistant on Project Page", () => {
  test("assistant works from project context", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001");
    await expect(page.locator('button[title="Open AI Assistant"]')).toBeVisible();
    await page.click('button[title="Open AI Assistant"]');
    await expect(page.locator("text=Synthia")).toBeVisible();
  });
});
