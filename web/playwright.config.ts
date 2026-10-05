import { defineConfig } from "@playwright/test";

// Smoke tests run against the real API in postgres mode (Supabase), so DATABASE_URL
// must be in the project's .env. Both servers are started automatically, or reused
// if they're already running.
// Relative to the project root, where the API command runs (cwd: "..").
const python = process.platform === "win32" ? ".venv\\Scripts\\python" : ".venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000, // the first API request opens the database connection
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "phone", use: { viewport: { width: 375, height: 740 }, isMobile: true, hasTouch: true } },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn src.api.main:app --port 8000`,
      cwd: "..",
      env: { DATA_BACKEND: "postgres", ALLOWED_ORIGINS: "http://localhost:3000" },
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
