/**
 * The only place that knows whether the code runs in a browser or in the Android app
 * (SPEC §13). Everything platform-specific goes through here, so the web and a future iOS
 * build are not affected by Android calls.
 */
import { Capacitor } from "@capacitor/core";

export const isNativeApp: boolean = Capacitor.isNativePlatform();

/** The site talks to its own origin; the app — to the server set at build time. */
export function apiRoot(): string {
  if (!isNativeApp) return "/api/v1";
  const server = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
  return `${server}/api/v1`;
}

/** Printing and file downloads work in browsers; the app's WebView has neither. */
export const canPrint = !isNativeApp;
export const canDownload = !isNativeApp;

export { onBackButton } from "./back";
export { tokens, type TokenPair } from "./tokens";
