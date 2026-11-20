import { expect, test } from "@playwright/test";

test("dashboard renders KPIs, charts and queue from the live API", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/app/");
  await expect(page.getByText("Approval rate").first()).toBeVisible();
  await expect(page.getByText("95.07%")).toBeVisible();
  await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
  expect(await page.locator("svg.recharts-surface").count()).toBeGreaterThanOrEqual(2);
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.screenshot({ path: "e2e/dashboard.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("scoring form returns decline and fraud probabilities", async ({ page }) => {
  await page.goto("/app/");
  await page.getByLabel("Amount (USD)").fill("2000");
  await page.getByLabel("Hour").fill("2");
  await page.getByLabel("Channel").selectOption("E-commerce");
  await page.getByRole("button", { name: "Score" }).click();
  await expect(page.getByTestId("score-out")).toContainText("Decline probability");
  await expect(page.getByTestId("score-out")).toContainText("Fraud probability");
});

test("card-based scoring computes server-side features", async ({ page }) => {
  await page.goto("/app/");
  await page.getByLabel("Card ID (optional)").fill("CARD-001602");
  await page.getByLabel("Timestamp (with card)").fill("2025-06-01T03:00");
  await page.getByRole("button", { name: "Score" }).click();
  await expect(page.getByTestId("score-out")).toContainText("prior payments");
});

test("layout has no horizontal overflow at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto("/app/");
  await expect(page.getByText("Approval rate").first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});
