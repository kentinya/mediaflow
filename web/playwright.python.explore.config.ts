import { defineConfig } from "@playwright/test";

// The isolated real-Python Explore browser path (Task 51.1). One Python
// process serves the built V2 artifact and the real MediaFlowApi explore
// boundary over one temporary SQLite runtime database, with the production
// TMDB adapter driven by an injected in-process fake transport; fixture
// posters answer `https://image.tmdb.org` through interception only. Run
// after `npm run build`:
//
//   npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
export default defineConfig({
  testDir: "./tests/e2e",
  // The file filter on the command line scopes this run to the Python-owned
  // spec; the Node fake-path config in turn ignores it in its own testIgnore
  // list so the ordinary suite never collects it.
  fullyParallel: false,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4187",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "../.venv/bin/python ../scripts/explore_harness.py --port 4187",
    port: 4187,
    timeout: 60_000,
    reuseExistingServer: false,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  expect: { timeout: 10_000 },
});
