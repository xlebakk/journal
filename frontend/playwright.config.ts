import { defineConfig, devices } from "@playwright/test";

// Needs PostgreSQL with a `journal_e2e` database (see README). Redis is not used in e2e.
const backendEnv = {
  DJANGO_SETTINGS_MODULE: "config.settings.e2e",
  DB_HOST: process.env.DB_HOST ?? "127.0.0.1",
  DB_PASSWORD: process.env.DB_PASSWORD ?? "journal",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  // One worker: TOTP codes cannot be reused, and the database is shared.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5174",
    trace: "retain-on-failure",
    locale: "ru-RU",
    timezoneId: "Asia/Tashkent",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "uv run python manage.py seed_e2e && uv run python manage.py runserver 127.0.0.1:8001 --noreload",
      cwd: "../backend",
      url: "http://127.0.0.1:8001/api/v1/health",
      env: backendEnv,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npx vite --port 5174 --strictPort",
      url: "http://localhost:5174",
      env: { VITE_API_PROXY: "http://127.0.0.1:8001" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
