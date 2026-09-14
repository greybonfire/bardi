import { afterEach, describe, expect, it, vi } from "vitest";
import { alternatePath, isLocale, pageAlternates, servicePath, siteOrigin } from "./site";

afterEach(() => vi.unstubAllEnvs());

describe("public bilingual paths", () => {
  it("recognizes only the exact supported locale codes", () => {
    expect(["ar", "en"].every(isLocale)).toBe(true);
    expect(["", "AR", "en-GB", "fr", " ar"].some(isLocale)).toBe(false);
  });

  it("encodes a Service ID as one path segment rather than a query or fragment", () => {
    expect(servicePath("ar", "test/service?key=value#part")).toBe("/ar/services/test%2Fservice%3Fkey%3Dvalue%23part");
    expect(servicePath("en", "خدمة اختبار")).toBe(`/en/services/${encodeURIComponent("خدمة اختبار")}`);
  });

  it.each(["", "/privacy", "/services/test%2Fid", "/services/test%2Fid/plan"])("switches locale without changing the public path: %s", (suffix) => {
    expect(alternatePath(`/ar${suffix}`, "ar")).toBe(`/en${suffix}`);
    expect(alternatePath(`/en${suffix}`, "en")).toBe(`/ar${suffix}`);
  });

  it.each(["ar", "en"] as const)("builds a %s canonical and Arabic-first hreflang alternatives", (locale) => {
    expect(pageAlternates("/services/test%2Fid", locale)).toEqual({
      canonical: `/${locale}/services/test%2Fid`,
      languages: { ar: "/ar/services/test%2Fid", en: "/en/services/test%2Fid", "x-default": "/ar/services/test%2Fid" },
    });
  });
});

describe("site origin metadata boundary", () => {
  it.each([
    ["http://localhost:3010", "http://localhost:3010"],
    ["https://example.org/public?not=metadata#fragment", "https://example.org"],
    ["https://example.org:443", "https://example.org"],
  ])("keeps only a public HTTP(S) origin from %s", (configured, expected) => {
    vi.stubEnv("BARDI_SITE_ORIGIN", configured);
    expect(siteOrigin()).toBe(expected);
  });

  it.each([undefined, "", "not a URL", "javascript:alert(1)", "file:///tmp/test", "https://user:password@example.org"])("fails safely for invalid/private configuration: %s", (configured) => {
    vi.stubEnv("BARDI_SITE_ORIGIN", configured);
    expect(siteOrigin()).toBe("http://localhost:3000");
  });
});
