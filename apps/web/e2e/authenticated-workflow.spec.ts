import { expect, test } from "@playwright/test";

const email = process.env.JL_E2E_EMAIL;
const password = process.env.JL_E2E_PASSWORD;
const slug = process.env.JL_E2E_ORG_SLUG;

async function login(page: import("@playwright/test").Page) {
  test.skip(!email || !password, "Set JL_E2E_EMAIL and JL_E2E_PASSWORD for authenticated staging E2E.");
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  if (slug) await page.getByLabel(/Organization slug/).fill(slug);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await page.waitForURL(/\/(matters|onboarding|$)/);
}

test("authenticated shell opens command palette with keyboard", async ({ page }) => {
  await login(page);
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await expect(page.getByRole("dialog", { name: /Universal search|यूनिवर्सल खोज/ })).toBeVisible();
  await page.keyboard.press("Escape");
});

test("display preferences expose Hindi and reduced-motion controls", async ({ page }) => {
  await login(page);
  await page.evaluate(() => window.dispatchEvent(new Event("jl:open-preferences")));
  await expect(page.getByRole("dialog", { name: "Display & accessibility" })).toBeVisible();
  await expect(page.getByRole("button", { name: "हिन्दी" })).toBeVisible();
  await expect(page.getByText("Reduce motion")).toBeVisible();
});
