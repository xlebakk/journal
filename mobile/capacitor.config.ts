import type { CapacitorConfig } from "@capacitor/cli";

// `JOURNAL_DEV_SERVER=1` only for a debug APK against a local http:// server (scripts/build.mjs);
// a release build is synced without it: no mixed content, no WebView debugging (SPEC §13).
const dev = process.env.JOURNAL_DEV_SERVER === "1";

const config: CapacitorConfig = {
  // The Play listing is tied to this id: change it only before the first distribution.
  appId: "uz.journal.center",
  appName: "Daftar",
  // The frontend built with `--mode mobile`: the app loads its own files, not a remote URL.
  webDir: "../frontend/dist-mobile",
  server: {
    // Origin https://localhost — the one APP_ORIGINS on the server allows for CORS.
    androidScheme: "https",
  },
  android: {
    allowMixedContent: dev,
    webContentsDebuggingEnabled: dev,
    captureInput: false,
  },
};

export default config;
