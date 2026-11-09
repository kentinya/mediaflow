import { defineConfig } from "@playwright/test";

// The isolated real-Python browser path (Task 42.1). One Python process
// serves the built V2 artifact and the real MediaFlowApi over one temporary
// SQLite runtime database, so the browser drives the packaged Python stack
// (real admission, real Worker claim/linkage, real reads) instead of a Node
// fake. Run after `npm run build`:
//
//   npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  // One Python process serves one temporary SQLite database and one shared
  // durable fixture set.  File-level parallelism would let two specs admit
  // work, consume the single organizing capacity or move the same source
  // concurrently, so the real-harness run is deliberately serial.
  workers: 1,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4183",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "../.venv/bin/python ../scripts/operations_inventory_harness.py --port 4183",
    port: 4183,
    timeout: 60_000,
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  expect: { timeout: 10_000 },
});
