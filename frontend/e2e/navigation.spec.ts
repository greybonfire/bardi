import { test, expect, ui, isPlanning } from "./browser";
import { passportId, services } from "./fixtures.mjs";

const origin = "http://localhost:3010";

test("root defaults to Arabic, with an accessible English language switch", async ({ page, planningCalls }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL(`${origin}/ar`);
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { level: 1, name: ui.ar.home })).toBeVisible();
  const language = page.getByRole("link", { name: "English", exact: true });
  await expect(language).toHaveAttribute("lang", "en");
  await expect(language).toHaveAttribute("hreflang", "en");
  await expect(language).toHaveAttribute("dir", "ltr");
  await language.click();
  await expect(page).toHaveURL(`${origin}/en`);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { level: 1, name: ui.en.home })).toBeVisible();
  expect(planningCalls).toHaveLength(0);
});

for (const locale of ["ar", "en"] as const) {
  test(`${locale}: Service navigation is server-rendered without JavaScript`, async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    let posts = 0;
    page.on("request", (request) => { if (isPlanning(request)) posts += 1; });
    try {
      await page.goto(`${origin}/${locale}`);
      for (const service of services) {
        await expect(page.getByRole("link", { name: service.title[locale], exact: true }))
          .toHaveAttribute("href", `/${locale}/services/${service.id}`);
      }
      await page.getByRole("link", { name: ui[locale].service, exact: true }).click();
      await expect(page.getByRole("heading", { level: 1, name: ui[locale].service })).toBeVisible();
      await page.getByRole("link", { name: ui[locale].start, exact: true }).click();
      await expect(page.getByText(locale === "ar" ? "الأسئلة محتاجة JavaScript." : "The questionnaire needs JavaScript.", { exact: false })).toBeVisible();
      expect(posts).toBe(0);
    } finally { await context.close(); }
  });

  for (const path of ["", "/privacy", `/services/${passportId}`]) {
    test(`${locale}${path || "/"}: public bilingual SEO and canonical links`, async ({ page }) => {
      const response = await page.goto(`/${locale}${path}`);
      expect(response?.status()).toBe(200);
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expect(page.locator("html")).toHaveAttribute("dir", locale === "ar" ? "rtl" : "ltr");
      await expect(page).toHaveTitle(locale === "ar" ? /بردي/ : /Bardi/);
      // Next streams dynamic Service metadata into <body> for JS-capable
      // browsers; HTML-limited crawlers receive it in <head> (tested below).
      await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", locale === "ar" ? /دليل مستقل/ : /independent guide/);
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `${origin}/${locale}${path}`);
      for (const [language, target] of [["ar", "ar"], ["en", "en"], ["x-default", "ar"]]) {
        await expect(page.locator(`link[rel="alternate"][hreflang="${language}"]`)).toHaveAttribute("href", `${origin}/${target}${path}`);
      }
      expect(await page.locator('meta[name="robots"]').evaluateAll((nodes) => nodes.some((node) => /noindex/.test(node.getAttribute("content") ?? "")))).toBe(false);
      expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
      await expect(page.locator('meta[name="referrer"]')).toHaveAttribute("content", "no-referrer");
    });
  }

  test(`${locale}: HTML-limited crawlers receive Service metadata in the initial head`, async ({ request }) => {
    const response = await request.get(`/${locale}/services/${passportId}`, { headers: { "User-Agent": "facebookexternalhit/1.1" } });
    expect(response.status()).toBe(200);
    const head = (await response.text()).split("</head>")[0];
    expect(head).toContain('name="description"');
    expect(head).toContain(`rel="canonical" href="${origin}/${locale}/services/${passportId}"`);
    expect(head).toContain('hrefLang="ar"');
    expect(head).toContain('hrefLang="en"');
    expect(head).toContain('hrefLang="x-default"');
  });

  test(`${locale}: plan route is private, noindex and not a canonical personalized URL`, async ({ page }) => {
    await page.goto(`/${locale}/services/${passportId}/plan`);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /nofollow/);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noarchive/);
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(0);
    await expect(page.locator('meta[name="description"]')).not.toHaveAttribute("content", /TEST-ONLY|synthetic_note|inside_egypt/);
  });
}

test("same-origin service proxy strips credentials/referrer and does not cache navigation", async ({ request }) => {
  // The stand-in rejects these if Next forwards them upstream. These are fixed
  // test sentinels, not an auth token or real cookie.
  const response = await request.get("/v1/services", { headers: {
    Cookie: "e2e=TEST-ONLY", Authorization: "Bearer TEST-ONLY", Referer: `${origin}/en`,
    "X-Forwarded-For": "192.0.2.1",
  } });
  expect(response.status()).toBe(200);
  expect(response.headers()["cache-control"]).toBe("no-store");
  expect((await response.json()).services).toEqual(services);
});

for (const path of ["/fr", "/en/not-a-page", "/ar/services/e2e.unknown", "/en/services/e2e.unknown/plan"]) {
  test(`unknown route returns HTTP 404: ${path}`, async ({ page }) => {
    const response = await page.goto(path);
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await expect(page.locator('meta[name="robots"]').first()).toHaveAttribute("content", /noindex/);
    await expect(page.getByRole("link", { name: /كل الخدمات|All services|Browse services/ }).first()).toBeVisible();
  });
}

test("sitemap exposes bilingual public pages but no questionnaire or API URLs", async ({ request }) => {
  const response = await request.get("/sitemap.xml");
  expect(response.status()).toBe(200);
  const sitemap = await response.text();
  for (const locale of ["ar", "en"]) {
    expect(sitemap).toContain(`<loc>${origin}/${locale}</loc>`);
    expect(sitemap).toContain(`<loc>${origin}/${locale}/privacy</loc>`);
    for (const service of services) expect(sitemap).toContain(`<loc>${origin}/${locale}/services/${service.id}</loc>`);
  }
  expect(sitemap).not.toMatch(/\/plan(?:<|\")|\/v1\/|TEST-ONLY|synthetic_note/);
});
