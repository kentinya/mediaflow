import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    css: false,
    // The Playwright browser path lives in tests/e2e and runs via `npm run
    // test:e2e`, not inside Vitest.
    exclude: [...configDefaults.exclude, "tests/e2e/**"],
  },
});
