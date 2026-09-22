// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";

// Import after stubbing: Next evaluates this configuration at module load time.
afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

it("allows only the loopback hostname for the explicitly enabled sandbox", async () => {
  vi.stubEnv("BARDI_SANDBOX", "1");
  vi.resetModules();
  const { default: config } = await import("../../next.config");
  expect(config.allowedDevOrigins).toEqual(["127.0.0.1"]);
});

it.each([undefined, "", "0", "true", "01"])(
  "leaves Next's default dev origins unchanged for BARDI_SANDBOX=%s",
  async (value) => {
    vi.stubEnv("BARDI_SANDBOX", value);
    vi.resetModules();
    const { default: config } = await import("../../next.config");
    expect(config).not.toHaveProperty("allowedDevOrigins");
  },
);
