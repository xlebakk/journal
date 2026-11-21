import "@/shared/ui/global.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/app/App";
import { isNativeApp } from "@/platform";
import { applyTheme, readThemePreference } from "@/shared/lib/theme";

applyTheme(readThemePreference());

// PWA on the site only: the app ships its files inside the APK (SPEC §13).
if (import.meta.env.PROD && !isNativeApp && "serviceWorker" in navigator) {
  void import("virtual:pwa-register").then(({ registerSW }) => registerSW({ immediate: true }));
}

const root = document.getElementById("root");
if (!root) throw new Error("#root not found");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
