import {
  test, expect, ui, openQuestionnaire, answerLocation, answerPhotos, submitNote,
  planPath, storedCase, storageKey, deferred,
} from "./browser";
import { passportId, richPlan } from "./fixtures.mjs";

for (const locale of ["ar", "en"] as const) {
  test(`${locale}: a retired Service case can be cleared from its 404 via the privacy page`, async ({ page, planningCalls }) => {
    await page.goto(`/${locale}/privacy`);
    await page.evaluate((key) => {
      sessionStorage.setItem(key, JSON.stringify({
        version: 1, serviceId: "e2e.retired", date: "2026-09-12",
        facts: { synthetic_note: "TEST-ONLY-NOTE" },
        history: [{ questionId: "e2e.retired.q", keys: ["synthetic_note"] }],
      }));
    }, storageKey);
    const response = await page.goto(planPath(locale, "e2e.retired"));
    expect(response?.status()).toBe(404);
    await page.getByRole("contentinfo").getByRole("link").click();
    await expect(page).toHaveURL(`http://localhost:3010/${locale}/privacy`);
    await page.getByRole("button", { name: ui[locale].clear, exact: true }).click();
    await page.getByRole("button", { name: ui[locale].confirmClear, exact: true }).click();
    await expect(page.getByRole("status")).toContainText(ui[locale].cleared);
    expect(await storedCase(page)).toBeNull();
    expect(planningCalls).toHaveLength(0);
    await page.getByRole("banner").getByRole("link", { name: locale === "ar" ? "English" : "العربية", exact: true }).click();
    expect(await storedCase(page)).toBeNull();
    expect(planningCalls).toHaveLength(0);
  });
}

test("privacy-page clearing cancels a pending case and cannot be undone by late work or returning to it", async ({ page, planningCalls }) => {
  await openQuestionnaire(page);
  await answerLocation(page);
  await answerPhotos(page);
  const entered = deferred();
  const gate = deferred();
  const finished = deferred();
  await page.route("**/v1/planning", async (route) => {
    entered.release();
    await gate.promise;
    try { await route.fulfill({ json: richPlan("en") }); }
    finally { finished.release(); }
  }, { times: 1 });
  try {
    await submitNote(page);
    await entered.promise;
    await page.getByRole("contentinfo").getByRole("link").click();
    await page.getByRole("button", { name: ui.en.clear, exact: true }).click();
    await page.getByRole("button", { name: ui.en.confirmClear, exact: true }).click();
    await expect(page.getByRole("status")).toContainText(ui.en.cleared);
  } finally { gate.release(); }
  await finished.promise;
  const count = planningCalls.length;
  await page.getByRole("banner").locator(".wordmark").click();
  await page.getByRole("link", { name: ui.en.service, exact: true }).click();
  await page.getByRole("link", { name: ui.en.start, exact: true }).click();
  await expect(page).toHaveURL(`http://localhost:3010${planPath("en", passportId)}`);
  await expect(page.getByRole("heading", { name: ui.en.cleared, exact: true })).toBeVisible();
  await page.clock.fastForward(60_000);
  expect(planningCalls).toHaveLength(count);
  expect(await storedCase(page)).toBeNull();
  await expect(page.getByRole("article")).toHaveCount(0);
  await page.getByRole("button", { name: ui.en.restart, exact: true }).click();
  await expect(page.getByRole("form")).toBeVisible();
  expect(planningCalls.at(-1)?.facts).toEqual({});
});

test("a browser timeout leaves loading, preserves answers, ignores a late plan, and permits only manual retry", async ({ page, planningCalls }) => {
  await openQuestionnaire(page);
  await answerLocation(page);
  await answerPhotos(page);
  const entered = deferred();
  const gate = deferred();
  const finished = deferred();
  await page.route("**/v1/planning", async (route) => {
    entered.release();
    await gate.promise;
    try { await route.fulfill({ json: richPlan("en") }); }
    finally { finished.release(); }
  }, { times: 1 });
  try {
    await submitNote(page);
    await entered.promise;
    const saved = await storedCase(page);
    const count = planningCalls.length;
    await page.clock.fastForward(20_001);
    await expect(page.getByRole("main").getByRole("alert")).toContainText("We couldn’t connect.");
    await expect(page.getByRole("button", { name: ui.en.retry, exact: true })).toBeEnabled();
    expect((await storedCase(page))?.facts).toEqual(saved?.facts);
    await page.clock.fastForward(60_000);
    expect(planningCalls).toHaveLength(count);
  } finally { gate.release(); }
  await finished.promise;
  await expect(page.getByRole("article")).toHaveCount(0);
  const count = planningCalls.length;
  await page.getByRole("button", { name: ui.en.retry, exact: true }).click();
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toBeVisible();
  expect(planningCalls).toHaveLength(count + 1);
  expect(planningCalls.at(-1)?.facts).toEqual((await storedCase(page))?.facts);
});
