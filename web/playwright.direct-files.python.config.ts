import { defineConfig } from "@playwright/test";

// Real Python/API/SQLite/Worker coverage for the two native Files pages.
// Run after `npm run build` with:
// npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4185",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "../.venv/bin/python ../scripts/direct_files_browser_harness.py --port 4185",
    port: 4185,
    timeout: 60_000,
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  expect: { timeout: 10_000 },
});
