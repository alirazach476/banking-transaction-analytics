import { defineConfig } from "@playwright/test";

// End-to-end test of the built React app served by the real API (needs Postgres with the payment marts + trained models).
// Run: npm run build && npx playwright test
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.pw.js",
  timeout: 60000,
  use: { baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:8792", screenshot: "only-on-failure" },
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: "python -m uvicorn src.api.main:app --port 8792 --log-level warning",
    cwd: "../..",
    url: "http://127.0.0.1:8792/health",
    reuseExistingServer: true,
    timeout: 60000,
    env: { RATE_LIMIT_PER_MIN: "0", PYTHONPATH: "." },
  },
});
