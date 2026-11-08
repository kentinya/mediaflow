import { defineConfig } from "@playwright/test";

// Real Python/API/SQLite/Worker proof for the OpenList metadata-only journey.
// The harness serves the built V2 artifact and one real OpenListStorage over a
// loopback OpenList v4 server whose /api/fs/get always answers HTTP 405.
// Run after `npm run build`:
//
//   npm run test:e2e -- --config=playwright.openlist-metadata.python.config.ts \
//     tests/e2e/openlist-metadata.python.spec.ts
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4190",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "../.venv/bin/python ../scripts/openlist_metadata_browser_harness.py --port 4190",
    port: 4190,
    timeout: 180_000,
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  expect: { timeout: 15_000 },
});
