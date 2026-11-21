// After `npm run build`: the PWA caches the shell only, never the API (SPEC §3, §11, §13).
import { existsSync, readFileSync } from "node:fs";

const fail = (message) => {
  console.error(`✗ ${message}`);
  process.exitCode = 1;
};

const sw = readFileSync("dist/sw.js", "utf8");
const routes = sw.match(/registerRoute\(/g) ?? [];
if (routes.length !== 1) fail(`expected one route (navigation), found ${routes.length}`);
if (!sw.includes("NavigationRoute")) fail("the navigation fallback is missing");
if (!/denylist:\[\/\^\\\/api\\\/\/\]/.test(sw)) fail("/api/ must be excluded from the fallback");
if (/runtimeCaching|NetworkFirst|StaleWhileRevalidate|CacheFirst/.test(sw)) {
  fail("no runtime caching is allowed: API answers must never be cached");
}

const manifest = JSON.parse(readFileSync("dist/manifest.webmanifest", "utf8"));
if (manifest.theme_color !== "#f4f1e8") fail("theme_color must be --paper");
for (const icon of manifest.icons) {
  if (!existsSync(`dist${icon.src}`)) fail(`missing icon ${icon.src}`);
}
if (!manifest.icons.some((icon) => icon.purpose === "maskable")) fail("no maskable icon");
if (!readFileSync("dist/index.html", "utf8").includes('rel="manifest"')) fail("no manifest link");

if (!process.exitCode)
  console.log("✓ PWA: shell only, API never cached, manifest and icons in place");
