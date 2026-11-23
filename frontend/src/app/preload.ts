/**
 * Stage 19: every lazy screen registers its loader here; after sign-in the shell fetches them
 * all in idle time, so the first visit to any section opens at once. Only code is fetched —
 * no data (the API answers are never stored on the device).
 */
const loaders: (() => Promise<unknown>)[] = [];
let started = false;

export function remember<T>(load: () => Promise<T>): () => Promise<T> {
  loaders.push(load);
  return load;
}

export function preloadScreens(): void {
  if (started) return;
  started = true;
  const run = () => {
    for (const load of loaders) void load().catch(() => undefined);
  };
  if ("requestIdleCallback" in window) window.requestIdleCallback(run, { timeout: 3000 });
  else setTimeout(run, 1500);
}
