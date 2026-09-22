import { describe, expect, it, vi } from "vitest";
import type { FullResult, Suite, TestCase, TestResult } from "@playwright/test/reporter";
import { disposableOrigin } from "./options";
import PrivateReporter, { titles } from "./reporter";

describe("disposable browser boundary", () => {
  it.each([undefined, "", "https://example.org", "http://127.0.0.1:4000/path", "http://user:secret@localhost:4000", "http://localhost:4000?secret=1", "http://localhost:4000/#x", "http://127.1:4000", "http://localhost:4000/"])("rejects noncanonical or nonloopback origins (%s)", (origin) => {
    expect(() => disposableOrigin({ BARDI_REAL_E2E_ORIGIN: origin, BARDI_REAL_E2E_DISPOSABLE: "1" })).toThrow("REAL_E2E_DISPOSABLE_ORIGIN_REQUIRED");
  });
  it("disables artifacts, retries, focused tests and server startup", async () => {
    vi.stubEnv("BARDI_REAL_E2E_ORIGIN", "http://127.0.0.1:4000");
    vi.stubEnv("BARDI_REAL_E2E_DISPOSABLE", "1");
    try {
      const { default: config } = await import("../playwright.real.config");
      expect(config.forbidOnly).toBe(true);
      expect(config.retries).toBe(0);
      expect(config.preserveOutput).toBe("never");
      expect(config.webServer).toBeUndefined();
      expect(config.use).toMatchObject({ timezoneId: "Africa/Cairo", trace: "off", screenshot: "off", video: "off", serviceWorkers: "block" });
      expect(config.testMatch).toBe("journeys.spec.ts");
    } finally { vi.unstubAllEnvs(); }
  });
  it("requires explicit disposable ownership", () => {
    expect(() => disposableOrigin({ BARDI_REAL_E2E_ORIGIN: "http://localhost:4000" })).toThrow();
    expect(disposableOrigin({ BARDI_REAL_E2E_ORIGIN: "http://127.0.0.1:4000", BARDI_REAL_E2E_DISPOSABLE: "1" })).toBe("http://127.0.0.1:4000");
  });
  it.each(["passed", "skipped", "failed", "missing", "error"])("fails closed except three actual passes: %s", async (mode) => {
    const output = vi.spyOn(console, "log").mockImplementation(() => {});
    try {
      const reporter = new PrivateReporter();
      const tests = titles.map((title) => ({ title, expectedStatus: "passed" }) as TestCase);
      reporter.onBegin({}, { allTests: () => mode === "missing" ? tests.slice(1) : tests } as Suite);
      for (const test of tests) reporter.onTestEnd(test, { status: mode === "skipped" ? "skipped" : mode === "failed" ? "failed" : "passed", retry: 0 } as TestResult);
      if (mode === "error") reporter.onError();
      expect((await reporter.onEnd({ status: "passed" } as FullResult)).status).toBe(mode === "passed" ? "passed" : "failed");
      expect(Object.keys(JSON.parse(output.mock.calls[0][0]))).toEqual(["suite", "passed", "failed", "errors", "failingIds", "status"]);
    } finally { output.mockRestore(); }
  });
});
