import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ServiceDirectory, ServiceUnavailable } from "./service-directory";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
beforeEach(() => refresh.mockClear());

// Synthetic public navigation only. The SSR directory cannot be intercepted
// using browser.route('/v1/services'); these regressions exercise its actual
// empty/unavailable UI and RetryServices client control without a server toggle.
const services = [
  { id: "test/service?query#part", title: { ar: "تجديد جواز السفر — مثال اختبار", en: "Passport renewal — test example" } },
  { id: "e2e.identity", title: { ar: "تجديد بطاقة الرقم القومي — مثال اختبار", en: "National ID renewal — test example" } },
];
const copy = {
  ar: { empty: "مفيش خدمات متاحة حاليًا", unavailable: "ما قدرناش نحمّل الخدمات", retry: "حمّل الخدمات تاني" },
  en: { empty: "No services are available yet", unavailable: "We couldn’t load the services", retry: "Load services again" },
};

describe.each(["ar", "en"] as const)("Service directory (%s)", (locale) => {
  const t = copy[locale];
  it("renders exact localized titles, safe URLs and decorative arrows", () => {
    const { container } = render(<ServiceDirectory services={services} locale={locale} />);
    expect(screen.getAllByRole("link").map((link) => link.textContent)).toEqual(services.map((service) => service.title[locale]));
    expect(screen.getByRole("link", { name: services[0].title[locale] })).toHaveAttribute("href", `/${locale}/services/test%2Fservice%3Fquery%23part`);
    expect(container.querySelectorAll('svg[aria-hidden="true"]')).toHaveLength(2);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("shows an honest empty catalog, and refreshes only when requested", async () => {
    render(<ServiceDirectory services={[]} locale={locale} />);
    expect(screen.getByRole("heading", { name: t.empty })).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: t.retry }));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("announces directory unavailability and supports a manual keyboard retry", async () => {
    const user = userEvent.setup();
    render(<ServiceUnavailable locale={locale} />);
    expect(screen.getByRole("status")).toHaveTextContent(t.unavailable);
    expect(screen.queryByRole("heading", { name: t.empty })).not.toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
    await user.tab();
    expect(screen.getByRole("button", { name: t.retry })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
