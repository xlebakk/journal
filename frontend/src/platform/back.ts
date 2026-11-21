import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

/**
 * The Android system «Назад»: an open dialog closes itself (Radix listens for Escape), then
 * the history goes back, and on the first screen the app closes. No-op in a browser.
 */
export function onBackButton(goBack: () => void, canGoBack: () => boolean): () => void {
  if (!Capacitor.isNativePlatform()) return () => {};
  const listener = App.addListener("backButton", () => {
    const dialog = document.querySelector('[role="dialog"]');
    if (dialog) {
      dialog.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return;
    }
    if (canGoBack()) goBack();
    else void App.exitApp();
  });
  return () => {
    void listener.then((handle) => handle.remove());
  };
}
