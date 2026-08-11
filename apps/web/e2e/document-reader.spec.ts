import { expect, test } from "@playwright/test";

const documentId = process.env.JL_E2E_LARGE_DOCUMENT_ID;

test("large document reader keeps a bounded page window", async ({ page }) => {
  test.skip(!documentId, "Set JL_E2E_LARGE_DOCUMENT_ID to a synthetic/de-identified 1000-page staging document.");
  await page.goto(`/documents/${documentId}`);
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.getByText(/page/i).first()).toBeVisible();
  const pageCards = page.locator("[data-document-page]");
  const count = await pageCards.count();
  expect(count).toBeLessThanOrEqual(30);
});
