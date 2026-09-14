// @vitest-environment node
import { expect, it } from "vitest";
import config from "../../next.config";

// These framework controls are part of the privacy boundary, not optional
// performance tuning. Configuration is integrated by the parent worker.
it("disables Next's development HMR cache, which otherwise caches no-store POST fetches", () => {
  expect(config.experimental?.serverComponentsHmrCache).toBe(false);
});

it("disables framework request/fetch logging before handlers can discard queries and sanitize failures", () => {
  expect(config.logging === false || (
    config.logging?.incomingRequests === false && !config.logging.fetches
  )).toBe(true);
  expect(config.experimental?.requestInsights ?? false).toBe(false);
});
