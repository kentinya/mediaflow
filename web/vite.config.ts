import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Python application serves the built artifact from the Web root, so Vite
// emits every asset URL relative to "/" and the same bytes work in the
// container, the wheel and the development proxy.
export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
});
