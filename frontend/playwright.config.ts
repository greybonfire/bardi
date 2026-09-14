import { defineConfig, devices } from "@playwright/test";

// Build first: npm run build. Both servers below are test-only, local processes.
// Set BARDI_E2E_API_PORT=8471 only when the default fixture port is occupied.
const apiPort = process.env.BARDI_E2E_API_PORT ?? "8451";
if (!["8451", "8471"].includes(apiPort)) throw new Error("Unsupported acceptance fixture port.");
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const siteOrigin = "http://localhost:3010";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: "list",
  use: {
    baseURL: siteOrigin,
    timezoneId: "Africa/Cairo",
    serviceWorkers: "block",
    // Never record Facts, request bodies, screenshots, videos, or browser traces.
    trace: "off",
    screenshot: "off",
    video: "off",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  projects: [
    {
      name: "desktop-chromium",
      testIgnore: "**/mobile.spec.ts",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
    },
    {
      name: "mobile-rtl-chromium",
      testMatch: "**/mobile.spec.ts",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: [
    {
      command: "node --experimental-strip-types e2e/api-stand-in.mjs",
      url: `${apiOrigin}/v1/services`,
      env: { BARDI_E2E_API_PORT: apiPort },
      reuseExistingServer: false,
      timeout: 15_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: "npm run start -- --port 3010",
      url: siteOrigin,
      env: {
        BARDI_API_ORIGIN: apiOrigin,
        BARDI_SITE_ORIGIN: siteOrigin,
        NEXT_TELEMETRY_DISABLED: "1",
      },
      reuseExistingServer: false,
      timeout: 30_000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
