import { test, expect, preparePlan, openQuestionnaire, answerLocation, answerPhotos, submitNote, ui, isPlanning, planPath } from "./browser";
import { richPlan } from "./fixtures.mjs";

test("Facts stay out of addresses, credentials, persistent storage, metadata and analytics", async ({ page, context, planningCalls }) => {
  const audit = { unexpectedRequest: false, unsafePlanningHeaders: false, consoleLeak: false, pageError: false };
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== "http://localhost:3010" || /TEST-ONLY|synthetic_note|inside_egypt|has_required_photos/.test(decodeURIComponent(url.href))) audit.unexpectedRequest = true;
    if (request.method() === "POST" && !isPlanning(request)) audit.unexpectedRequest = true;
  });
  page.on("console", (message) => {
    // Only a boolean escapes this callback; no logs or console bodies retained.
    if (/TEST-ONLY|synthetic_note|inside_egypt|has_required_photos/.test(message.text())) audit.consoleLeak = true;
  });
  page.on("pageerror", () => { audit.pageError = true; });
  await page.addInitScript(() => {
    const state = { safeFetchOptions: true, planningCount: 0, beacons: 0 };
    Object.defineProperty(window, "__syntheticPrivacyCheck", { value: state });
    const originalFetch = window.fetch;
    window.fetch = function (input, init) {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (new URL(url, location.origin).pathname === "/v1/planning") {
        state.planningCount += 1;
        state.safeFetchOptions &&= init?.method === "POST" && init.credentials === "omit" &&
          init.referrerPolicy === "no-referrer" && init.cache === "no-store" && init.redirect === "error";
      }
      return originalFetch.call(this, input, init);
    };
    navigator.sendBeacon = () => { state.beacons += 1; return false; };
  });
  await context.addCookies([{ name: "e2e_credential", value: "TEST-CREDENTIAL-ONLY", url: "http://localhost:3010" }]);
  const headers: Promise<void>[] = [];
  page.on("request", (request) => {
    if (isPlanning(request)) headers.push(request.allHeaders().then((values) => {
      if (["cookie", "authorization", "referer"].some((name) => Object.hasOwn(values, name))) audit.unsafePlanningHeaders = true;
    }));
  });
  const replies: Promise<void>[] = [];
  page.on("response", (response) => {
    if (isPlanning(response.request())) replies.push(response.allHeaders().then((values) => {
      if (values["cache-control"] !== "no-store" || Object.hasOwn(values, "set-cookie")) audit.unsafePlanningHeaders = true;
    }));
  });
  await preparePlan(page);
  await Promise.all([...headers, ...replies]);
  expect(planningCalls).toHaveLength(4);
  const browser = await page.evaluate(() => {
    const state = (window as unknown as { __syntheticPrivacyCheck: { safeFetchOptions: boolean; planningCount: number; beacons: number } }).__syntheticPrivacyCheck;
    return {
      ...state, localStorageKeys: Object.keys(localStorage), sessionStorageKeys: Object.keys(sessionStorage),
      leakedMetadata: /TEST-ONLY|synthetic_note|inside_egypt|has_required_photos/.test(
        document.head.innerHTML + Array.from(document.querySelectorAll('meta, link[rel="canonical"], link[rel="alternate"]'), (node) => node.outerHTML).join(""),
      ),
      cookieHasFacts: /TEST-ONLY|synthetic_note|inside_egypt|has_required_photos/.test(document.cookie),
      analyticsGlobals: ["dataLayer", "gtag", "ga", "Sentry", "posthog"].some((key) => key in window),
    };
  });
  expect(browser).toEqual({
    safeFetchOptions: true, planningCount: 4, beacons: 0,
    localStorageKeys: [], sessionStorageKeys: ["bardi.active-case.v1"], leakedMetadata: false,
    cookieHasFacts: false, analyticsGlobals: false,
  });
  expect(audit).toEqual({ unexpectedRequest: false, unsafePlanningHeaders: false, consoleLeak: false, pageError: false });
  expect(await context.cookies()).toHaveLength(1); // Only the deliberately seeded test credential.
  expect(await page.evaluate(async () => (await caches.keys()).length)).toBe(0);
  await expect(page).toHaveURL(`http://localhost:3010${planPath()}`);
});

test("external sources use safe rel and open without a referrer or opener", async ({ page, context }) => {
  await preparePlan(page);
  const plan = richPlan("en");
  const source = plan.checklist_items[0].sources[0];
  const row = page.getByRole("region", { name: "Documents and preparation", exact: true })
    .getByRole("listitem", { name: plan.checklist_items[0].text, exact: true });
  await row.locator("summary").click();
  const link = row.getByRole("link", { name: /https:\/\/example.org\/synthetic\/guide/ });
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", /\bnoopener\b/);
  await expect(link).toHaveAttribute("rel", /\bnoreferrer\b/);
  let unsafeHeaders = false;
  await context.route("https://example.org/synthetic/**", async (route) => {
    const headers = await route.request().allHeaders();
    unsafeHeaders = ["referer", "cookie", "authorization"].some((name) => Object.hasOwn(headers, name));
    await route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Synthetic external source</title><p>Test data only; no external network access.</p>" });
  });
  const popupEvent = page.waitForEvent("popup");
  await link.click();
  const popup = await popupEvent;
  try {
    await expect(popup).toHaveURL(source.locator);
    await expect(popup).toHaveTitle("Synthetic external source");
    expect(await popup.evaluate(() => window.opener === null && document.referrer === "")).toBe(true);
    expect(unsafeHeaders).toBe(false);
  } finally { await popup.close(); }
});

test("harmful source locators and HTML-like authored text never become active content", async ({ page }) => {
  await openQuestionnaire(page);
  await answerLocation(page);
  await answerPhotos(page);
  const plan = richPlan("en");
  const locators = [
    "javascript:window.__syntheticUnsafe=true", "data:text/html,<script>window.__syntheticUnsafe=true</script>",
    "file:///synthetic-test", "vbscript:TEST-ONLY", "//example.org/synthetic-relative", "/v1/planning",
  ];
  const authored = '<img src="x" onerror="window.__syntheticUnsafe=true"> TEST-ONLY literal authored text';
  plan.checklist_items[0] = { ...plan.checklist_items[0], text: authored, sources: locators.map((locator, index) => ({
    ...plan.checklist_items[0].sources[0], id: `e2e.source.unsafe.${index}`, title: `TEST-ONLY unsafe locator ${index}`, locator,
  })) };
  await page.route("**/v1/planning", (route) => route.fulfill({ json: plan }), { times: 1 });
  await submitNote(page);
  const row = page.getByRole("region", { name: "Documents and preparation", exact: true })
    .getByRole("listitem", { name: authored, exact: true });
  await expect(row.getByText(authored, { exact: true })).toBeVisible();
  await row.locator("summary").click();
  await expect(row.getByRole("link")).toHaveCount(0);
  await expect(row.locator("img, script, iframe")).toHaveCount(0);
  for (const locator of locators) await expect(row.getByText(locator, { exact: true }).filter({ visible: true })).toBeVisible();
  expect(await page.evaluate(() => "__syntheticUnsafe" in window)).toBe(false);
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toBeVisible();
});
