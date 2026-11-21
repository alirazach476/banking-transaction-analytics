import { expect, test } from "@playwright/test";

const SECTIONS = ["overview", "macro", "banking", "payments", "global", "crossborder", "inclusion", "ml", "quality"];

test("analysis tab renders every section, charts and tables from analysis.json", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("/app/#analysis");
  await expect(page.getByTestId("analysis")).toBeVisible();
  for (const s of SECTIONS) await expect(page.getByTestId("sec-" + s)).toBeAttached();
  // charts and tables are all present
  const cards = await page.locator("figure.chart").count();
  expect(cards).toBeGreaterThanOrEqual(45);
  expect(await page.locator("figure.chart svg.recharts-surface").count()).toBeGreaterThanOrEqual(38);
  await expect(page.getByText("Chart data problem")).toHaveCount(0);
  // KPI and a table value computed from the real data
  await expect(page.getByText("Gross NPL ratio").first()).toBeVisible();
  await expect(page.getByTestId("chart-scoreboard").locator("tbody tr").first()).toBeVisible();
  // no chart contains NaN/undefined text
  const bad = await page.locator("figure.chart").evaluateAll((els) => els.filter((e) => /NaN|undefined|null/.test(e.textContent)).map((e) => e.getAttribute("data-testid")));
  expect(bad).toEqual([]);
  await page.screenshot({ path: "e2e/analysis.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("each section has at least one chart", async ({ page }) => {
  await page.goto("/app/#analysis");
  for (const s of SECTIONS.filter((x) => x !== "overview")) {
    expect(await page.getByTestId("sec-" + s).locator("figure.chart").count()).toBeGreaterThan(0);
  }
});

test("analysis tab has no horizontal overflow at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto("/app/#analysis");
  await expect(page.getByTestId("analysis")).toBeVisible();
  await expect(page.locator("figure.chart svg.recharts-surface").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
});

test("switching tabs works both ways", async ({ page }) => {
  await page.goto("/app/");
  await expect(page.getByText("Approval rate").first()).toBeVisible();
  await page.getByRole("tab", { name: /Pakistan analysis/ }).click();
  await expect(page.getByTestId("analysis")).toBeVisible();
  await page.getByRole("tab", { name: /Payments/ }).click();
  await expect(page.getByText("Approval rate").first()).toBeVisible();
});
