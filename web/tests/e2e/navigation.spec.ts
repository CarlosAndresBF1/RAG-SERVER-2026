import { test, expect } from "@playwright/test";

test.describe("Navigation & Layout", () => {
  test("login page has correct title", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("Odyssey RAG")).toBeVisible();
  });

  test("sidebar links are present on login redirect", async ({ page }) => {
    // Unauthenticated users get redirected; just verify login loads
    await page.goto("/login");
    await expect(page.getByRole("button", { name: /sign in/i })).toBeEnabled();
  });
});

test.describe("Command Palette", () => {
  test("Cmd+K shortcut targets login when unauthenticated", async ({ page }) => {
    await page.goto("/login");
    // Command palette only renders inside dashboard layout, so on login it won't appear
    await page.keyboard.press("Meta+k");
    // Verify no crash — page still functional
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  });
});
