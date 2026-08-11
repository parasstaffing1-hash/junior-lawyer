import { expect, test } from "@playwright/test";

test("login surface is keyboard reachable and labelled", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});

test("login page does not expose internal workspace data", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Secret Acquisition Client XYZ")).toHaveCount(0);
  await expect(page.locator("main")).toHaveCount(1);
});
