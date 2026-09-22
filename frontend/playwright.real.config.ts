import { defineConfig } from "@playwright/test";
import { disposableOrigin } from "./e2e-real/options";

export default defineConfig({
  testDir: "./e2e-real",
  testMatch: "journeys.spec.ts",
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  preserveOutput: "never",
  reporter: [["./e2e-real/reporter.ts"]],
  use: {
    baseURL: disposableOrigin(process.env),
    browserName: "chromium",
    timezoneId: "Africa/Cairo",
    serviceWorkers: "block",
    trace: "off", screenshot: "off", video: "off",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {},
  },
});
