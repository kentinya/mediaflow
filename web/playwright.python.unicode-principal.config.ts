import { defineConfig } from "@playwright/test";

/** Real Python/API/browser proof using a legal Unicode ID from runtime config. */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4184",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "../.venv/bin/python ../scripts/operations_inventory_harness.py --port 4184 --admin-principal-id '值班管理员'",
    port: 4184,
    timeout: 60_000,
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  expect: { timeout: 10_000 },
});
