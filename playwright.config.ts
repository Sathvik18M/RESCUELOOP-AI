import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.env.CI ? undefined : "msedge",
      },
    },
  ],
  webServer: [
    {
      command:
        process.platform === "win32"
          ? "services\\backend\\.venv\\Scripts\\python.exe scripts\\e2e_api.py"
          : "services/backend/.venv/bin/python scripts/e2e_api.py",
      url: "http://127.0.0.1:8002/health",
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: "npm run dev --workspace apps/seller-dashboard -- --port 3001",
      url: "http://127.0.0.1:3001",
      reuseExistingServer: false,
      timeout: 60000,
      env: {
        NEXT_PUBLIC_API_URL: "http://127.0.0.1:8002",
        NEXT_PUBLIC_DEMO_MODE: "true",
        NEXT_DIST_DIR: ".next-e2e",
      },
    },
  ],
});
