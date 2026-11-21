import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests run against a running frontend (default http://localhost:3000) and backend.
 * Locally: `npx playwright install chromium` once, then `npm run test:e2e`.
 * Set PW_CHANNEL=chrome to use an installed Google Chrome instead.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    channel: process.env.PW_CHANNEL || undefined,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: process.env.PW_CHANNEL || undefined }, testIgnore: /mobile\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: process.env.PW_CHANNEL || undefined }, testMatch: /mobile\.spec\.ts/ },
  ],
});
