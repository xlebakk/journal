import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Same origin in dev as in prod: the API is proxied, so cookies work without CORS.
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
  },
  build: {
    sourcemap: false,
    // Keeps CSP strict: no inline <script>/<style> and no data: fonts in the bundle.
    assetsInlineLimit: 0,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
