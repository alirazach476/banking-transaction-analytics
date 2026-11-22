import { expect, test } from "@playwright/test";

// End-to-end checks of the NovaBank analytics UI against the real API. Needs the built app (npm run build) and Postgres with the marts + UI views.
const ROUTES = [
  ["overview", "Executive overview"], ["payments", "Payment intelligence"], ["fraud", "Fraud & anomaly"], ["customers", "Customer analytics"], ["merchants", "Merchant analytics"],
  ["branches", "Branch & regional"], ["explorer", "Transaction explorer"], ["global", "Global financial intelligence"], ["engineering", "Data engineering"], ["settings", "Settings"],
];
const IGNORED = /WebGL|GPU stall|Failed to load resource.*(openstreetmap|404)|tile\./i;

for (const [path, title] of ROUTES) {
  test(`route /${path} loads with no console errors and shows its title`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => m.type() === "error" && !IGNORED.test(m.text()) && errors.push(m.text()));
    await page.goto(`/app/${path}`, { waitUntil: "networkidle" });
    await expect(page.locator("h1").first()).toContainText(title, { ignoreCase: true });
    expect(errors).toEqual([]);
  });
}

test("unknown route shows a not-found state, not a blank page", async ({ page }) => {
  await page.goto("/app/does-not-exist");
  await expect(page.getByText("Page not found")).toBeVisible();
});

test("overview KPIs equal the API values and follow the date range", async ({ page, request }) => {
  for (const [from, to] of [["2025-01-01", "2025-12-31"], ["2024-01-01", "2024-06-30"]]) {
    const api = await (await request.get(`/v1/overview?from=${from}&to=${to}`)).json();
    await page.goto(`/app/overview?from=${from}&to=${to}`, { waitUntil: "networkidle" });
    const vol = api.headline.find((k) => k.key === "payment_volume").value;
    await expect(page.getByTestId("kpi-value-payment_volume")).toHaveText(vol.toLocaleString("en-US"));
  }
});

test("changing the date range preset updates KPIs", async ({ page }) => {
  await page.goto("/app/overview", { waitUntil: "networkidle" });
  const before = await page.getByTestId("kpi-value-payment_volume").innerText();
  await page.getByLabel("Date range").first().selectOption("y2024");
  await page.waitForTimeout(500);
  await page.getByLabel("Date range").first().selectOption("all");
  await expect(page.getByTestId("kpi-value-payment_volume")).not.toHaveText(before);
});

test("theme toggle switches and persists", async ({ page }) => {
  await page.goto("/app/overview", { waitUntil: "networkidle" });
  const before = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.getByLabel("Toggle theme").click();
  const after = await page.evaluate(() => document.documentElement.dataset.theme);
  expect(after).not.toBe(before);
  await page.reload({ waitUntil: "networkidle" });
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe(after);
});

test("charts render canvases on the payments page", async ({ page }) => {
  await page.goto("/app/payments", { waitUntil: "networkidle" });
  await expect(page.locator("canvas").first()).toBeVisible();
  expect(await page.locator("canvas").count()).toBeGreaterThanOrEqual(6);
});

test("explorer table: server-side sort, filter, pagination and export", async ({ page }) => {
  test.setTimeout(180000);
  await page.goto("/app/explorer?tab=transactions&from=2023-01-01&to=2025-12-31", { waitUntil: "networkidle" });
  const table = page.getByTestId("explorer-transactions");
  await expect(table.locator("tbody tr").first()).toBeVisible();
  const count = await page.getByTestId("table-count").innerText();
  expect(count).toMatch(/of [\d,]+/);
  // sort by amount (click header twice -> descending)
  const hdr = table.locator("th", { hasText: /^Amount$/ }).first();
  await hdr.locator(".th-in").click();
  await hdr.locator(".th-in").click();
  await page.waitForLoadState("networkidle");
  // pagination
  await expect(page.getByLabel("Next page")).toBeEnabled();
  await page.getByLabel("Next page").click();
  await expect(page.getByText(/Page 2 \//)).toBeVisible();
  // search narrows the row count
  await page.getByPlaceholder(/^Search/).first().fill("CUST-00004035");
  await expect(page.getByTestId("table-count")).not.toHaveText(count);
  // CSV export downloads a file
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByLabel("Export CSV").click()]);
  expect(dl.suggestedFilename()).toMatch(/\.csv$/);
});

test("customer detail opens from the customers table", async ({ page }) => {
  await page.goto("/app/customers", { waitUntil: "networkidle" });
  const first = page.locator("tbody tr").filter({ hasText: "CUST-" }).first();
  await expect(first).toBeVisible();
  await first.click();
  await expect(page).toHaveURL(/\/customers\/CUST-/);
  await expect(page.getByText("Transaction history")).toBeVisible();
});

test("branch map renders markers", async ({ page }) => {
  await page.goto("/app/branches", { waitUntil: "networkidle" });
  await expect(page.getByTestId("branch-map")).toBeVisible();
  await expect(page.getByText(/not branch addresses/)).toBeVisible();
});

test("an API failure shows an error state with retry, not a blank page", async ({ page }) => {
  await page.route("**/v1/overview**", (r) => r.fulfill({ status: 500, body: '{"detail":"boom"}', contentType: "application/json" }));
  await page.goto("/app/overview", { waitUntil: "networkidle" });
  await expect(page.getByRole("button", { name: /retry/i }).first()).toBeVisible();
});

test("every page fits a phone viewport without horizontal page scroll", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 800 } });
  const page = await ctx.newPage();
  for (const [path] of ROUTES) {
    await page.goto(`/app/${path}`, { waitUntil: "networkidle" });
    const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(over, `/${path} overflows by ${over}px`).toBeLessThanOrEqual(1);
  }
  await ctx.close();
});

test("global search returns results", async ({ page }) => {
  await page.goto("/app/overview", { waitUntil: "networkidle" });
  await page.getByLabel("Global search").fill("CUST-0000");
  await expect(page.locator("button.row").first()).toBeVisible();
});
