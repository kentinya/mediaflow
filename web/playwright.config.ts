import { defineConfig } from "@playwright/test";

// The minimal browser path runs against the built V2 artifact plus a local
// fake API served by one Node process; it never touches production services.
export default defineConfig({
  testDir: "./tests/e2e",
  // The isolated real-Python browser spec runs only under
  // playwright.python.config.ts, which starts the Python harness instead of
  // the Node fake; the fake-path suite must never pick it up.
  testIgnore: [
    "**/direct-files.python.spec.ts",
    "**/operations-inventory.python.spec.ts",
    "**/operations-principal-identity.python.spec.ts",
    "**/operations-task-center-visual.python.spec.ts",
  ],
  // The Node fake API is one process with shared in-memory state. Keep one
  // worker so another test cannot reset or mutate a journey's fixture while
  // its browser is still reading it.
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "node tests/fake-server.mjs",
    port: 4173,
    timeout: 30_000,
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  expect: { timeout: 10_000 },
});
