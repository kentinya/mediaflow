import { defineConfig } from "@playwright/test";

// The isolated real-Python browser path for the Automation definition
// lifecycle (Task 43.1). It runs the same production harness as
// `playwright.python.config.ts` on its own port, because this journey
// deliberately publishes real focused Active configuration successors: each
// publication advances the authoritative Active revision, which by design
// invalidates the fixture snapshot pins other journeys seed once at harness
// build time. Sharing one harness would make those unrelated journeys depend
// on this spec's ordering, so the lifecycle proof owns an isolated instance
// exactly as the Unicode-principal proof owns `playwright.python.unicode-principal.config.ts`.
//
// Run after `npm run build`:
//
//   npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts
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
      "../.venv/bin/python ../scripts/operations_inventory_harness.py --port 4185",
    port: 4185,
    timeout: 60_000,
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  expect: { timeout: 10_000 },
});
