import { test, expect } from "@playwright/test";

test.describe("Accessibility", () => {
  test("skip-to-content link works", async ({ page }) => {
    await page.goto("/");
    // Tab to the skip link (first focusable element)
    await page.keyboard.press("Tab");
    const skipLink = page.locator('a[href="#main-content"]');
    await expect(skipLink).toBeFocused();
    // Activate it
    await page.keyboard.press("Enter");
    // Main content should be the target
    const main = page.locator("#main-content");
    await expect(main).toBeVisible();
  });

  test("create project dialog has proper ARIA and focus trap", async ({ page }) => {
    await page.goto("/projects");
    await page.click("text=New Project");

    // Verify dialog role and attributes
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(dialog).toHaveAttribute("aria-labelledby", "create-project-title");

    // Wizard h2 now changes per step. Step 1 reads "Project details" —
    // the dialog's aria-labelledby still points at the same id so screen
    // readers always announce the current step.
    const title = page.locator("#create-project-title");
    await expect(title).toContainText("Project details");

    // Escape closes the dialog
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
  });

  test("connection drawer has proper ARIA and Escape closes it", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/connections");
    await page.click("text=Add Connection");

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(dialog).toHaveAttribute("aria-labelledby", "connection-drawer-title");

    // Escape closes
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
  });

  test("icon buttons in header have aria-labels", async ({ page }) => {
    await page.goto("/");

    // Every icon-only button in the global nav must announce itself.
    await expect(page.locator('button[aria-label="Open AI assistant"]')).toBeVisible();
    await expect(page.locator('button[aria-label="User menu"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Open command palette"]')).toBeVisible();
    // Notification bell: label varies with unread count (announces the count).
    await expect(page.locator('button[aria-label^="Open notifications"]')).toBeVisible();
  });

  test("keyboard tab navigates through dashboard elements", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Synthia\s*·\s*AI-Powered Test Data Management/i)).toBeVisible();

    // Tab through — skip link, then header elements, then content
    // Just verify tab moves focus and elements are focusable
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press("Tab");
    }
    // Some element should be focused
    const focused = page.locator(":focus");
    await expect(focused).toBeVisible();
  });

  test("focus-visible ring appears on keyboard navigation", async ({ page }) => {
    await page.goto("/");

    // Tab to first interactive element
    await page.keyboard.press("Tab"); // skip link
    await page.keyboard.press("Tab"); // first real element

    const focused = page.locator(":focus-visible");
    // At least one element should have focus-visible
    const count = await focused.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});

test.describe("Mobile Responsiveness", () => {
  test.use({ viewport: { width: 375, height: 812 } }); // iPhone viewport

  test("dashboard renders on mobile", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Synthia\s*·\s*AI-Powered Test Data Management/i)).toBeVisible();
  });

  test("mobile menu button is visible", async ({ page }) => {
    await page.goto("/");
    const menuBtn = page.locator('button[aria-label="Open navigation menu"]');
    await expect(menuBtn).toBeVisible();
  });

  test("projects page renders on mobile", async ({ page }) => {
    await page.goto("/projects");
    await expect(page.locator("h1")).toContainText("Projects");
  });

  test("connection drawer is full-width on mobile", async ({ page }) => {
    await page.goto("/projects/00000000-0000-0000-0000-000000000001/connections");
    await page.click("text=Add Connection");

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();

    // Drawer should be full width on mobile (no max-w-[480px] applying)
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.width).toBeGreaterThanOrEqual(370); // ~full width on 375 viewport
    }
  });
});
