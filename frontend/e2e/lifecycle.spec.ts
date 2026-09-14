import type { Page } from "@playwright/test";
import {
  test, expect, ui, openQuestionnaire, answerLocation, answerPhotos, submitNote,
  hasFacts, storedCase, planPath, deferred, evaluationDate, isPlanning, expectNoOverflow,
} from "./browser";
import { identityId, notes, passportId, questions, richPlan } from "./fixtures.mjs";

// These exercise the actual SiteHeader Next Link, not a prop rerender or a full
// page.goto/reload. All inputs and delayed responses are synthetic test fixtures.
async function languageLink(page: Page, locale: "ar" | "en", serviceId = passportId) {
  await page.getByRole("banner").getByRole("link", { name: locale === "ar" ? "العربية" : "English", exact: true }).click();
  await expect(page).toHaveURL(`http://localhost:3010${planPath(locale, serviceId)}`);
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
}

async function blockStorage(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(window, "sessionStorage", {
      configurable: true,
      get() { throw new DOMException("TEST-ONLY storage blocked", "SecurityError"); },
    });
  });
}

async function clear(page: Page, locale: "ar" | "en") {
  await page.getByRole("button", { name: ui[locale].clear, exact: true }).click();
  await page.getByRole("button", { name: ui[locale].confirmClear, exact: true }).click();
  await expect(page.getByRole("heading", { name: ui[locale].cleared, exact: true })).toBeVisible();
}

test("blocked sessionStorage retains submitted source answers through real language-link remounts", async ({ page, planningCalls }) => {
  await blockStorage(page);
  await openQuestionnaire(page, "ar");
  await answerLocation(page, "ar");
  const document = await page.evaluateHandle(() => window.document);
  await languageLink(page, "en");
  await expect(page.getByRole("heading", { name: questions.en[1], exact: true })).toBeVisible();
  expect(await document.evaluate((previous) => previous === window.document)).toBe(true);
  await document.dispose();
  expect(planningCalls).toHaveLength(3);
  expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt" })).toBe(true);
  await expect(page.getByText(/Tab storage isn’t available/)).toBeVisible();
  await page.locator("summary").filter({ hasText: ui.en.review }).click();
  await expect(page.getByRole("button", { name: ui.en.changeLocation, exact: true })).toBeVisible();
  await expect(page.locator(".planning-review").getByText(ui.en.inside, { exact: true })).toBeVisible();
  await expect(page.getByText(questions.ar[1], { exact: true })).toHaveCount(0);
  await answerPhotos(page, "en", false);
  await languageLink(page, "ar");
  await expect(page.getByRole("heading", { name: questions.ar[2], exact: true })).toBeVisible();
  expect(planningCalls).toHaveLength(5);
  expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt", has_required_photos: false })).toBe(true);
  expect(planningCalls.at(-1)?.locale).toBe("ar");
  await expect(page.getByText(/تخزين التبويب مش متاح/)).toBeVisible();
});

test("an active 429 keeps its original deadline and manual-retry marker across language links, even after expiry", async ({ page, planningCalls }) => {
  await openQuestionnaire(page, "ar");
  await answerLocation(page, "ar");
  await answerPhotos(page, "ar");
  await page.clock.pauseAt(new Date(`${evaluationDate}T10:00:00Z`));
  const response = page.waitForResponse((response) => response.url().endsWith("/v1/planning") && response.status() === 429);
  await submitNote(page, "ar", notes.rateLimited);
  expect((await response).headers()["retry-after"]).toBe("2");
  await expect(page.getByRole("heading", { name: ui.ar.failure, exact: true })).toBeVisible();
  const count = planningCalls.length;
  await page.clock.runFor(750);
  await languageLink(page, "en");
  const retry = page.getByRole("button", { name: ui.en.retry, exact: true });
  await expect(retry).toBeDisabled();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("There have been too many requests.");
  const cooldown = page.getByText(/You can try again in/);
  await expect(cooldown).toBeVisible();
  expect(await cooldown.evaluate((element) => element.closest("details") === null)).toBe(true);
  expect(planningCalls).toHaveLength(count);
  await page.clock.runFor(1_249);
  await expect(retry).toBeDisabled();
  expect(planningCalls).toHaveLength(count);
  await page.clock.runFor(1);
  await expect(retry).toBeEnabled(); // Original deadline, not a new two seconds.
  expect(planningCalls).toHaveLength(count);
  await languageLink(page, "ar");
  await expect(page.getByRole("button", { name: ui.ar.retry, exact: true })).toBeEnabled();
  await page.clock.runFor(10_000);
  expect(planningCalls).toHaveLength(count);
  await page.getByRole("button", { name: ui.ar.retry, exact: true }).click();
  await expect(page.getByRole("button", { name: ui.ar.retry, exact: true })).toBeDisabled();
  expect(planningCalls).toHaveLength(count + 1);
  expect(hasFacts(planningCalls.at(-1), {
    application_location: "inside_egypt", has_required_photos: true, synthetic_note: notes.rateLimited,
  })).toBe(true);
});

for (const blocked of [false, true]) {
  test(`clear stays idle across language links without POST or a saved case (storage blocked: ${blocked})`, async ({ page, planningCalls }) => {
    if (blocked) await blockStorage(page);
    await openQuestionnaire(page, "ar");
    await answerLocation(page, "ar");
    await clear(page, "ar");
    const count = planningCalls.length;
    await languageLink(page, "en");
    await expect(page.getByRole("heading", { name: ui.en.cleared, exact: true })).toBeVisible();
    if (blocked) await expect(page.getByText(/browser storage could not be cleared/)).toBeVisible();
    else expect(await storedCase(page)).toBeNull();
    await expect(page.locator(".planning-review")).toHaveCount(0);
    await page.clock.fastForward(60_000);
    expect(planningCalls).toHaveLength(count);
    await languageLink(page, "ar");
    await expect(page.getByRole("heading", { name: ui.ar.cleared, exact: true })).toBeVisible();
    expect(planningCalls).toHaveLength(count);
    if (!blocked) expect(await storedCase(page)).toBeNull();
    await page.getByRole("button", { name: ui.ar.restart, exact: true }).click();
    await expect(page.getByRole("heading", { name: questions.ar[0], exact: true })).toBeVisible();
    expect(planningCalls).toHaveLength(count + 1);
    expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
  });

  test(`Service links replace the one current case rather than archiving it (storage blocked: ${blocked})`, async ({ page, planningCalls }) => {
    if (blocked) await blockStorage(page);
    await openQuestionnaire(page);
    await answerLocation(page);
    await answerPhotos(page, "en", false);
    await page.getByRole("banner").locator(".wordmark").click();
    await page.getByRole("link", { name: "National ID renewal", exact: true }).click();
    await page.getByRole("link", { name: ui.en.start, exact: true }).click();
    await expect(page.getByRole("heading", { name: questions.en[0], exact: true })).toBeVisible();
    expect(planningCalls.at(-1)?.service_id).toBe(identityId);
    expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
    await answerLocation(page);
    await languageLink(page, "ar", identityId);
    await expect(page.getByRole("heading", { name: questions.ar[1], exact: true })).toBeVisible();
    expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt" })).toBe(true);
    await page.getByRole("banner").locator(".wordmark").click();
    await page.getByRole("link", { name: ui.ar.service, exact: true }).click();
    await page.getByRole("link", { name: ui.ar.start, exact: true }).click();
    await expect(page.getByRole("heading", { name: questions.ar[0], exact: true })).toBeVisible();
    expect(planningCalls.at(-1)?.service_id).toBe(passportId);
    expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
    if (!blocked) {
      expect((await storedCase(page))?.serviceId).toBe(passportId);
      expect(await page.evaluate(() => sessionStorage.length)).toBe(1);
    }
  });
}

test("clearing a pending request then navigating language cannot revive an old response or send a new POST", async ({ page, planningCalls }) => {
  await openQuestionnaire(page, "ar");
  await answerLocation(page, "ar");
  await answerPhotos(page, "ar");
  const entered = deferred();
  const gate = deferred();
  const finished = deferred();
  await page.route("**/v1/planning", async (route) => {
    entered.release();
    await gate.promise;
    try { await route.fulfill({ json: richPlan("ar") }); }
    finally { finished.release(); }
  }, { times: 1 });
  try {
    await submitNote(page, "ar");
    await entered.promise;
    await clear(page, "ar");
    await languageLink(page, "en");
    await expect(page.getByRole("heading", { name: ui.en.cleared, exact: true })).toBeVisible();
  } finally { gate.release(); }
  await finished.promise;
  await page.clock.fastForward(30_000);
  expect(planningCalls).toHaveLength(4);
  expect(await storedCase(page)).toBeNull();
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: ui.en.cleared, exact: true })).toBeVisible();
});

for (const locale of ["ar", "en"] as const) {
  test(`${locale}: compact mobile disclosures are keyboard operable, and date correction opens before focusing`, async ({ page, planningCalls }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openQuestionnaire(page, locale);
    const privacy = page.locator("summary").filter({ hasText: locale === "ar" ? "إجاباتك وخصوصيتك" : "Your answers and privacy" });
    const dateSummary = page.locator("summary").filter({ hasText: locale === "ar" ? "تاريخ الإرشادات:" : "Guidance date:" });
    const date = page.getByLabel(locale === "ar" ? "تاريخ الإرشادات" : "Guidance date", { exact: true });
    const dateDetails = page.locator("details").filter({ has: date });
    await expect(privacy.locator("..")).not.toHaveAttribute("open");
    await expect(dateDetails).not.toHaveAttribute("open");
    await expect(date).toBeHidden();
    await expect(dateSummary).toContainText(evaluationDate);
    await expectNoOverflow(page);
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.getByRole("heading", { name: questions[locale][0], exact: true })).toBeInViewport({ ratio: 1 });
    // Result focus starts on the stage, after these two closed disclosures.
    await page.keyboard.press("Shift+Tab");
    await expect(dateSummary).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(privacy).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(privacy.locator("..")).toHaveAttribute("open");
    await expect(privacy.locator("..").locator("p")).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(privacy.locator("..").locator("p")).toBeHidden();
    await page.keyboard.press("Tab");
    await expect(dateSummary).toBeFocused();
    await page.keyboard.press("Space");
    await expect(date).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(date).toBeFocused();
    await date.fill("2024-02-29");
    await expect(dateSummary).toContainText(evaluationDate); // Unapplied draft.
    expect(planningCalls).toHaveLength(1);
    await page.route("**/v1/planning", (route) => route.fulfill({ json: {
      type: "invalid", diagnostics: [{ code: "invalid_request", path: ["evaluation_context", "evaluation_date"] }],
    } }), { times: 1 });
    const apply = page.getByRole("button", { name: locale === "ar" ? "استخدم التاريخ ده" : "Use this date", exact: true });
    await apply.click();
    await expect(page.getByRole("heading", { name: ui[locale].invalid, exact: true })).toBeVisible();
    await expect(dateSummary).toContainText("2024-02-29");
    await dateSummary.click();
    await expect(date).toBeHidden();
    await page.getByRole("button", { name: locale === "ar" ? "صحّح التاريخ" : "Correct the date", exact: true }).click();
    await expect(dateDetails).toHaveAttribute("open");
    await expect(date).toBeVisible();
    await expect(date).toBeFocused();
    await date.fill("2024-03-01");
    await apply.click();
    await expect(page.getByRole("heading", { name: questions[locale][0], exact: true })).toBeVisible();
    await expect(dateSummary).toContainText("2024-03-01");
    expect(planningCalls.at(-1)?.evaluation_context.evaluation_date).toBe("2024-03-01");
    expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
    await expectNoOverflow(page);
    await expect(page.getByText(locale === "ar" ? "الأسئلة محتاجة JavaScript." : "The questionnaire needs JavaScript.", { exact: true })).toHaveCount(0);
  });

  test(`${locale}: JavaScript-disabled questionnaire has plain visible SSR recovery and no POST`, async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    let posts = 0;
    page.on("request", (request) => { if (isPlanning(request)) posts += 1; });
    try {
      const response = await page.goto(`http://localhost:3010${planPath(locale)}`);
      expect(response?.status()).toBe(200);
      const planning = page.locator(".planning");
      await expect(planning.getByText(locale === "ar" ? "الأسئلة محتاجة JavaScript." : "The questionnaire needs JavaScript.", { exact: true })).toBeVisible();
      await expect(planning.getByText(locale === "ar" ? "فعّل JavaScript وحدّث الصفحة عشان تكمّل." : "Enable JavaScript and reload this page to continue.", { exact: true })).toBeVisible();
      await expect(planning.locator("noscript, form")).toHaveCount(0);
      const recovery = planning.getByRole("link", { name: locale === "ar" ? "ارجع لتعريف الخدمة" : "Back to the service introduction", exact: true });
      await expect(recovery).toHaveAttribute("href", `/${locale}/services/${passportId}`);
      await recovery.click();
      await expect(page.getByRole("heading", { level: 1, name: ui[locale].service, exact: true })).toBeVisible();
      expect(posts).toBe(0);
    } finally { await context.close(); }
  });
}
