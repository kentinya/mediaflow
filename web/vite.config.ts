import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Python application serves the built artifact under the documented
// /ui-v2/ migration prefix, so every asset URL must be emitted relative to it.
export default defineConfig({
  base: "/ui-v2/",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
});
