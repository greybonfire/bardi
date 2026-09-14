import { test, expect, ui, answerLocation, answerPhotos, submitNote, preparePlan, openQuestionnaire, storedCase, hasFacts, storageKey, planPath, deferred, evaluationDate } from "./browser";
import { identityId, noteKey, notes, passportId, questions, richPlan } from "./fixtures.mjs";

for (const locale of ["ar", "en"] as const) {
  const t = ui[locale];

  test(`${locale}: directory → introduction → questions → complete sourced plan`, async ({ page, planningCalls }) => {
    await page.goto(`/${locale}`);
    await page.getByRole("link", { name: t.service, exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: t.service })).toBeVisible();
    await expect(page.getByRole("heading", { name: locale === "ar" ? "قبل ما تبدأ" : "Before you start", exact: true })).toBeVisible();
    expect(planningCalls).toHaveLength(0);
    await page.getByRole("link", { name: t.start, exact: true }).click();
    await expect(page.getByRole("group", { name: questions[locale][0], exact: true })).toBeVisible();
    expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
    await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
    await answerLocation(page, locale);
    await expect(page.getByRole("group", { name: questions[locale][1], exact: true })).toBeVisible();
    await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
    await answerPhotos(page, locale);
    await submitNote(page, locale);
    const article = page.getByRole("article", { name: t.plan, exact: true });
    await expect(article).toBeVisible();
    expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt", has_required_photos: true, [noteKey]: notes.happy })).toBe(true);
    expect(planningCalls.at(-1)?.locale).toBe(locale);
    expect(planningCalls.at(-1)?.evaluation_context.evaluation_date).toBe(evaluationDate);
    await expect(article).toHaveAttribute("dir", locale === "ar" ? "rtl" : "ltr");
    const plan = richPlan(locale);
    await expect(article.getByText(plan.title, { exact: true })).toBeVisible();
    for (const section of t.sections) await expect(article.getByRole("region", { name: section, exact: true })).toBeVisible();
    // Authored text is not paraphrased, and official/practical guidance is separate.
    for (const [section, rows] of [
      [t.sections[0], plan.warnings], [t.sections[1], plan.dependencies],
      [t.sections[2], plan.checklist_items], [t.sections[3], plan.steps], [t.sections[4], plan.fees],
    ] as const) {
      for (const row of rows) await expect(article.getByRole("region", { name: section, exact: true })
        .getByRole("listitem", { name: row.text.replace(/\s+/g, " "), exact: true })).toBeVisible();
    }
    await expect(article.getByRole("heading", { name: locale === "ar" ? "متطلبات رسمية" : "Official requirements", exact: true })).toBeVisible();
    await expect(article.getByRole("heading", { name: locale === "ar" ? "تحضير عملي — مش متطلبات رسمية" : "Practical preparation — not official requirements", exact: true })).toBeVisible();
    await expect(article.getByText(locale === "ar" ? "القيمة الحالية مش معروفة — اتأكد منها قبل الدفع." : "Current amount unknown — check before paying.", { exact: true })).toHaveCount(5);
    await expect(article.getByRole("heading", { level: 3, name: plan.eligibility_bases[0].text })).toBeVisible();
    await expect(article.getByRole("heading", { level: 3, name: plan.routing.destinations[2].name })).toBeVisible();
    await expect(page).toHaveURL(`http://localhost:3010${planPath(locale)}`);
  });

  test(`${locale}: print includes closed source disclosures and hides review/forms`, async ({ page }) => {
    await preparePlan(page, locale);
    const article = page.getByRole("article", { name: t.plan, exact: true });
    const plan = richPlan(locale);
    const official = article.getByRole("region", { name: t.sections[2], exact: true })
      .getByRole("listitem", { name: plan.checklist_items[0].text, exact: true });
    await expect(article.locator("details[open]")).toHaveCount(0);
    await expect(official.getByText(plan.checklist_items[0].sources[0].title, { exact: true }).filter({ visible: true })).toHaveCount(0);
    // Deliberately leave review OPEN and provenance CLOSED when switching media.
    await page.locator("summary").filter({ hasText: t.review }).click();
    await expect(page.getByRole("button", { name: t.changeLocation, exact: true })).toBeVisible();
    await page.emulateMedia({ media: "print" });
    for (const row of [...plan.checklist_items, ...plan.warnings]) {
      await expect(article.getByRole("listitem", { name: row.text.replace(/\s+/g, " "), exact: true })).toBeVisible();
    }
    const printSource = official.locator(".plan-print-only");
    await expect(printSource).toBeVisible();
    await expect(printSource.getByText(plan.checklist_items[0].sources[0].title, { exact: true })).toBeVisible();
    await expect(printSource.getByText("demo.authority.records", { exact: true })).toBeVisible();
    await expect(printSource.getByText("demo.source.official", { exact: true })).toBeVisible();
    await expect(printSource.locator('time[datetime="2026-09-01"]')).toHaveCount(2);
    await expect(printSource.getByRole("link")).toHaveAttribute("href", plan.checklist_items[0].sources[0].locator);
    await expect(article.locator("header .plan-print-only").getByText(plan.procedure_version_id, { exact: true })).toBeVisible();
    await expect(article.locator("details").filter({ visible: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: t.changeLocation, exact: true })).toBeHidden();
    await expect(page.getByRole("button", { name: t.print, exact: true })).toBeHidden();
    await expect(page.locator("form").filter({ visible: true })).toHaveCount(0);
    await expect(page.getByRole("banner")).toBeHidden();
    await expect(page.getByRole("contentinfo")).toBeHidden();
    await page.emulateMedia({ media: "screen" });
    await expect(page.getByRole("button", { name: t.print, exact: true })).toBeVisible();
  });
}

test("reviewing an earlier answer discards it and every later Fact, including false", async ({ page, planningCalls }) => {
  await preparePlan(page, "en", false);
  expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt", has_required_photos: false, [noteKey]: notes.happy })).toBe(true);
  await expect(page.getByText("Some destinations resolved; other routing is still uncertain", { exact: true })).toBeVisible();
  await page.locator("summary").filter({ hasText: ui.en.review }).click();
  await expect(page.locator("details[open]").getByText("No", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: ui.en.changeLocation, exact: true }).click();
  await expect(page.getByRole("heading", { name: questions.en[0], exact: true })).toBeVisible();
  expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
  expect(Object.keys((await storedCase(page))!.facts)).toHaveLength(0);
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toHaveCount(0);
  await answerLocation(page);
  expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt" })).toBe(true);
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
});

test("refresh restores only the tab case, revalidates instead of restoring a plan, and locale preserves Facts", async ({ page, planningCalls }) => {
  await preparePlan(page);
  const saved = await storedCase(page);
  expect(Object.keys(saved!).sort()).toEqual(["date", "facts", "history", "serviceId", "version"]);
  expect(saved!.history).toHaveLength(3);
  expect(saved!.history.every((entry) => Object.keys(entry).sort().join() === "keys,questionId")).toBe(true);
  expect(JSON.stringify(saved).includes("procedure_version_id")).toBe(false);
  expect(JSON.stringify(saved).includes(richPlan("en").title)).toBe(false);
  const gate = deferred();
  await page.route("**/v1/planning", async (route) => { await gate.promise; await route.continue(); });
  try {
    await page.reload();
    await expect(page.getByText(ui.en.restored, { exact: false })).toBeVisible();
    await expect(page.getByText("Checking your answers…", { exact: true })).toBeVisible();
    await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toHaveCount(0);
    expect(hasFacts(planningCalls.at(-1), saved!.facts)).toBe(true);
  } finally { gate.release(); }
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toBeVisible();
  await page.unroute("**/v1/planning");
  await page.getByRole("link", { name: "العربية", exact: true }).click();
  await expect(page).toHaveURL(`http://localhost:3010${planPath("ar")}`);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("article", { name: ui.ar.plan, exact: true })).toBeVisible();
  expect(hasFacts(planningCalls.at(-1), saved!.facts)).toBe(true);
  expect(planningCalls.at(-1)?.locale).toBe("ar");
  expect(JSON.stringify((await storedCase(page))!.facts) === JSON.stringify(saved!.facts)).toBe(true);
});

test("changing the guidance date hides the old plan until applied and survives refresh without changing Facts", async ({ page, planningCalls }) => {
  await preparePlan(page);
  const saved = await storedCase(page);
  const date = page.getByLabel("Guidance date", { exact: true });
  // The advanced date control may be progressively disclosed. Open its native
  // summary through a visible user action, never force-fill a hidden input.
  if (!await date.isVisible()) await page.locator("details").filter({ has: date }).locator("summary").click();
  const count = planningCalls.length;
  await date.fill("2024-02-29");
  await expect(page.getByRole("heading", { name: "Apply the date to continue", exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toHaveCount(0);
  expect(planningCalls).toHaveLength(count);
  await page.getByRole("button", { name: "Use this date", exact: true }).click();
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toBeVisible();
  expect(planningCalls.at(-1)?.evaluation_context.evaluation_date).toBe("2024-02-29");
  expect(hasFacts(planningCalls.at(-1), saved!.facts)).toBe(true);
  await page.reload();
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toBeVisible();
  expect(planningCalls.at(-1)?.evaluation_context.evaluation_date).toBe("2024-02-29");
  expect(hasFacts(planningCalls.at(-1), saved!.facts)).toBe(true);
});

test("new tabs do not inherit Facts, and a different Service replaces only its tab case",  async ({ page, context, planningCalls }) => {
  await openQuestionnaire(page);
  await answerLocation(page);
  const otherTab = await context.newPage(); // No opener: normal independently opened tab.
  try {
    await openQuestionnaire(otherTab);
    expect(Object.keys((await storedCase(otherTab))!.facts)).toHaveLength(0);
    expect(Object.keys((await storedCase(page))!.facts)).toHaveLength(1);
    await openQuestionnaire(page, "en", identityId);
    expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
    expect((await storedCase(page))!.serviceId).toBe(identityId);
    await expect(page.getByRole("heading", { level: 1, name: "National ID renewal" })).toBeVisible();
    await openQuestionnaire(page);
    expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
    expect((await storedCase(page))!.serviceId).toBe(passportId);
  } finally { await otherTab.close(); }
});

test("reset clears tab storage and guidance, focuses confirmation, and sends nothing until Start again", async ({ page, planningCalls }) => {
  await preparePlan(page);
  await page.getByRole("button", { name: ui.en.clear, exact: true }).click();
  await expect(page.getByRole("heading", { name: "Clear this case?", exact: true }).locator("..")).toBeFocused();
  await page.getByRole("button", { name: "Keep my answers", exact: true }).click();
  await expect(page.getByRole("button", { name: ui.en.clear, exact: true })).toBeFocused();
  await page.getByRole("button", { name: ui.en.clear, exact: true }).click();
  const before = planningCalls.length;
  await page.getByRole("button", { name: ui.en.confirmClear, exact: true }).click();
  await expect(page.getByRole("heading", { name: ui.en.cleared, exact: true })).toBeVisible();
  expect(await page.evaluate((key) => sessionStorage.getItem(key), storageKey)).toBeNull();
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toHaveCount(0);
  await expect(page.locator("summary").filter({ hasText: ui.en.review })).toHaveCount(0);
  await page.clock.fastForward(60_000);
  expect(planningCalls).toHaveLength(before);
  await page.getByRole("button", { name: ui.en.restart, exact: true }).click();
  await expect(page.getByRole("heading", { name: questions.en[0], exact: true })).toBeVisible();
  expect(planningCalls).toHaveLength(before + 1);
  expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
});
