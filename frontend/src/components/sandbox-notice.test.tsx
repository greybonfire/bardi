import { readFileSync } from "node:fs";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SandboxNotice } from "./sandbox-notice";

const { connection } = vi.hoisted(() => ({ connection: vi.fn().mockResolvedValue(undefined) }));
vi.mock("next/server", () => ({ connection }));
afterEach(() => {
  vi.unstubAllEnvs();
  connection.mockClear();
});

const labels = { ar: "نسخة تجريبية محلية", en: "Local questionnaire sandbox" };

describe.each(["ar", "en"] as const)("Sandbox notice (%s)", (locale) => {
  it.each([undefined, "false", "0", "", "true"])("adds no markup for flag %s", async (flag) => {
    vi.stubEnv("BARDI_SANDBOX", flag);
    const notice = await SandboxNotice({ locale });
    expect(notice).toBeNull();
    expect(connection).not.toHaveBeenCalled();
    const { container } = render(notice);
    expect(container).toBeEmptyDOMElement();
  });

  it("labels copied test data and distinguishes explicit refresh from page reload", async () => {
    vi.stubEnv("BARDI_SANDBOX", "1");
    render(await SandboxNotice({ locale }));
    expect(connection).toHaveBeenCalledExactlyOnceWith();
    const notice = screen.getByRole("complementary", { name: labels[locale] });
    expect(notice.tagName).toBe("ASIDE");
    expect(notice.querySelector("strong")).toHaveTextContent(labels[locale]);
    expect(notice).toHaveTextContent(locale === "ar" ? "بيانات منسوخة للتجربة المحلية بس" : "Copied data for local testing only");
    expect(notice).toHaveTextContent(locale === "ar" ? "بأمر refresh بيمسح تعديلات النسخة الحالية" : "refresh command replaces the active copy and its changes");
    expect(notice).toHaveTextContent(locale === "ar" ? "إعادة تحميل الصفحة مش بتستبدل البيانات" : "reloading this page does not replace data");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

it("waits for a connection only when the sandbox flag is enabled", async () => {
  vi.stubEnv("BARDI_SANDBOX", "1");
  let connected = false;
  connection.mockImplementationOnce(async () => { connected = true; });
  expect(await SandboxNotice({ locale: "en" })).not.toBeNull();
  expect(connected).toBe(true);
  expect(connection).toHaveBeenCalledExactlyOnceWith();
});

it("keeps the notice outside hidden print navigation and explicitly visible in print", () => {
  const layout = readFileSync("src/app/[locale]/layout.tsx", "utf8");
  expect(layout).toContain('<SiteHeader locale={locale} />\n      <SandboxNotice locale={locale} />\n      <main');
  const css = readFileSync("src/app/globals.css", "utf8");
  expect(css.slice(css.indexOf("@media print"))).toMatch(/\.sandbox-notice\s*\{\s*display: block !important;/);
});
