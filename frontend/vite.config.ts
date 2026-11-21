import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8000";
// --paper: the browser bar and the splash match the page (SPEC §13).
const PAPER = "#f4f1e8";

export default defineConfig(({ mode }) => {
  // `vite build --mode mobile`: the bundle inside the Android app (stage 6). It has no
  // service worker (the files are already on the phone) and needs the server address.
  const mobile = mode === "mobile";
  if (mobile && !process.env.VITE_API_URL) {
    throw new Error("VITE_API_URL is required for the mobile build (https://…)");
  }
  return {
    plugins: [
      react(),
      VitePWA({
        disable: mobile,
        // Registered by src/main.tsx (CSP: no inline script), only on the site.
        injectRegister: false,
        registerType: "autoUpdate",
        manifest: {
          name: "Электронный журнал",
          short_name: "Журнал",
          description: "Расписание, оценки, посещаемость и пробные тесты учебного центра.",
          lang: "ru",
          start_url: "/",
          scope: "/",
          display: "standalone",
          orientation: "any",
          theme_color: PAPER,
          background_color: PAPER,
          icons: [
            { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
            {
              src: "/icons/maskable-512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "maskable",
            },
          ],
        },
        workbox: {
          // Only the shell: scripts, styles, fonts, icons. API answers are never cached
          // (SPEC §3, §11): there is no runtimeCaching, and /api/ never falls back to the shell.
          globPatterns: ["**/*.{js,css,html,woff2,png,svg,webmanifest}"],
          navigateFallback: "/index.html",
          navigateFallbackDenylist: [/^\/api\//],
          cleanupOutdatedCaches: true,
        },
      }),
    ],
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
      outDir: mobile ? "dist-mobile" : "dist",
      sourcemap: false,
      // Keeps CSP strict: no inline <script>/<style> and no data: fonts in the bundle.
      assetsInlineLimit: 0,
    },
    test: {
      include: ["src/**/*.test.{ts,tsx}"],
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: { modules: { classNameStrategy: "non-scoped" } },
    },
  };
});
