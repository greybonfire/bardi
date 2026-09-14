import { test, expect, ui, openQuestionnaire, answerLocation, answerPhotos, submitNote, hasFacts, storedCase, deferred } from "./browser";
import { inconclusiveMessages, nextQuestion, noteKey, notes, passportId, questions, richPlan } from "./fixtures.mjs";

for (const locale of ["ar", "en"] as const) {
  test(`${locale}: invalid diagnostics correct the earliest affected answer, not unrelated Facts`, async ({ page, planningCalls }) => {
    await openQuestionnaire(page, locale);
    await answerLocation(page, locale);
    await answerPhotos(page, locale);
    await submitNote(page, locale, notes.invalid);
    await expect(page.getByRole("heading", { name: ui[locale].invalid, exact: true })).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(locale === "ar" ? "في إجابات متعارضة" : "Some answers conflict");
    await expect(page.getByRole("main").getByRole("alert")).not.toContainText("contradictory_facts");
    await page.getByRole("button", { name: ui[locale].correct, exact: true }).click();
    await expect(page.getByRole("heading", { name: questions[locale][1], exact: true })).toBeVisible();
    expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt" })).toBe(true);
    expect(Object.keys((await storedCase(page))!.facts)).toHaveLength(1);
    await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
    await expect(page.getByRole("article")).toHaveCount(0);
  });

  test(`${locale}: inconclusive is authored guidance with limits, never a closest-match plan`, async ({ page, planningCalls }) => {
    await openQuestionnaire(page, locale);
    await answerLocation(page, locale);
    await answerPhotos(page, locale);
    await submitNote(page, locale, notes.inconclusive);
    await expect(page.getByRole("heading", { name: ui[locale].inconclusive, exact: true })).toBeVisible();
    await expect(page.getByText(inconclusiveMessages[locale], { exact: true })).toBeVisible();
    await expect(page.getByRole("article")).toHaveCount(0);
    const before = planningCalls.length;
    await page.getByRole("button", { name: ui[locale].retry, exact: true }).click();
    await expect(page.getByRole("heading", { name: ui[locale].inconclusive, exact: true })).toBeVisible();
    expect(planningCalls).toHaveLength(before + 1);
    expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt", has_required_photos: true, [noteKey]: notes.inconclusive })).toBe(true);
  });
}

test("429 traverses the real proxy, observes Retry-After, and only retries on a manual action", async ({ page, planningCalls }) => {
  await openQuestionnaire(page);
  await answerLocation(page);
  await answerPhotos(page);
  const response = page.waitForResponse((response) => response.url().endsWith("/v1/planning") && response.status() === 429);
  await submitNote(page, "en", notes.rateLimited);
  expect((await response).headers()["retry-after"]).toBe("2");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("There have been too many requests.");
  const retry = page.getByRole("button", { name: ui.en.retry, exact: true });
  await expect(retry).toBeDisabled();
  await expect(page.getByRole("button", { name: "Regenerate for today", exact: true })).toBeDisabled();
  const count = planningCalls.length;
  await page.clock.fastForward(3_000);
  await expect(retry).toBeEnabled();
  expect(planningCalls).toHaveLength(count);
  await retry.click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("There have been too many requests.");
  expect(planningCalls).toHaveLength(count + 1);
  expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt", has_required_photos: true, [noteKey]: notes.rateLimited })).toBe(true);
});

for (const scenario of [
  { name: "network failure", abort: true, message: "We couldn’t connect." },
  { name: "malformed JSON", status: 200, contentType: "application/json", body: "{", message: "We couldn’t safely read the response." },
  { name: "unexpected HTML", status: 200, contentType: "text/html", body: "<h1>TEST-ONLY upstream HTML must not render</h1>", message: "We couldn’t safely read the response." },
  { name: "HTTP 500", status: 500, contentType: "application/json", body: '{"TEST-ONLY":"not public guidance"}', message: "Bardi is temporarily unavailable." },
  { name: "HTTP 503", status: 503, contentType: "application/json", body: "{}", message: "Bardi is temporarily unavailable." },
]) {
  test(`${scenario.name} preserves Facts and a manual retry can recover`, async ({ page, planningCalls }) => {
    await openQuestionnaire(page);
    await answerLocation(page);
    await answerPhotos(page);
    await page.route("**/v1/planning", async (route) => {
      if (scenario.abort) await route.abort("failed");
      else await route.fulfill({ status: scenario.status, contentType: scenario.contentType, body: scenario.body });
    }, { times: 1 });
    await submitNote(page);
    await expect(page.getByRole("main").getByRole("alert")).toContainText(scenario.message);
    const saved = await storedCase(page);
    expect(hasFacts(planningCalls.at(-1), saved!.facts)).toBe(true);
    expect(Object.keys(saved!.facts)).toHaveLength(3);
    await expect(page.getByRole("article")).toHaveCount(0);
    const count = planningCalls.length;
    await page.clock.fastForward(30_000);
    expect(planningCalls).toHaveLength(count);
    await page.getByRole("button", { name: ui.en.retry, exact: true }).click();
    await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toBeVisible();
    expect(hasFacts(planningCalls.at(-1), saved!.facts)).toBe(true);
  });
}

for (const note of [notes.unavailable, notes.malformed]) {
  test(`upstream ${note} is sanitized by Next without losing submitted Facts`, async ({ page, planningCalls }) => {
    await openQuestionnaire(page, "ar");
    await answerLocation(page, "ar");
    await answerPhotos(page, "ar");
    await submitNote(page, "ar", note);
    await expect(page.getByRole("heading", { name: ui.ar.failure, exact: true })).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("بردي مش متاح مؤقتًا.");
    await expect(page.getByRole("main").getByRole("alert")).not.toContainText("TEST-ONLY");
    expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt", has_required_photos: true, [noteKey]: note })).toBe(true);
    expect(Object.keys((await storedCase(page))!.facts)).toHaveLength(3);
  });
}

// All four public discriminators must be validated at the browser boundary, even
// if a broken/misconfigured reverse proxy returns HTTP 200. No runtime validator
// supplies expectations, so weakening the production schema breaks these tests.
for (const [kind, data] of [
  ["next_question", { type: "next_question", service_id: passportId, question: { id: "e2e.broken", text: "TEST-ONLY broken question", answers: [{ key: "test", kind: "invented", enum_options: [], minimum: null }] } }],
  ["plan", { ...richPlan("en"), routing: undefined }],
  ["inconclusive", { type: "inconclusive", reason: "unsupported_case", message: 42 }],
  ["invalid", { type: "invalid", diagnostics: [{ code: "invalid_fact_value", path: ["facts", noteKey], input: "TEST-ONLY must not leak" }] }],
] as const) {
  test(`rejects a malformed ${kind} result rather than rendering unchecked content`, async ({ page }) => {
    await openQuestionnaire(page);
    await answerLocation(page);
    await answerPhotos(page);
    await page.route("**/v1/planning", (route) => route.fulfill({ json: data }), { times: 1 });
    await submitNote(page);
    await expect(page.getByRole("main").getByRole("alert")).toContainText("We couldn’t safely read the response.");
    await expect(page.getByRole("article")).toHaveCount(0);
    expect(Object.keys((await storedCase(page))!.facts)).toHaveLength(3);
  });
}

for (const kind of ["next_question", "plan"] as const) {
  test(`rejects ${kind} belonging to a different Service`, async ({ page }) => {
    await page.route("**/v1/planning", (route) => route.fulfill({ json: kind === "plan"
      ? richPlan("en", "e2e.other-service") : nextQuestion("e2e.other-service", "en", 0) }));
    await page.goto(`/en/services/${passportId}/plan`);
    await expect(page.getByRole("main").getByRole("alert")).toContainText("We couldn’t safely read the response.");
    await expect(page.getByRole("article")).toHaveCount(0);
  });
}

test("an unadvanceable question is an explicit configuration failure, not a guessed next step", async ({ page }) => {
  const question = nextQuestion(passportId, "en", 0);
  question.question.answers = [];
  await page.route("**/v1/planning", (route) => route.fulfill({ json: question }));
  await page.goto(`/en/services/${passportId}/plan`);
  await expect(page.getByRole("heading", { name: "We can’t continue with this question", exact: true })).toBeVisible();
  await expect(page.getByRole("form", { name: questions.en[0], exact: true })).toHaveCount(0);
});

test("a delayed plan cannot reappear after resetting a pending request", async ({ page, planningCalls }) => {
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
    await expect(page.getByText("Checking your answers…", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: ui.en.clear, exact: true }).click();
    await page.getByRole("button", { name: ui.en.confirmClear, exact: true }).click();
    await expect(page.getByRole("heading", { name: ui.en.cleared, exact: true })).toBeVisible();
  } finally { gate.release(); }
  await finished.promise;
  await page.clock.fastForward(10_000);
  await expect(page.getByRole("article")).toHaveCount(0);
  expect(await storedCase(page)).toBeNull();
  expect(planningCalls).toHaveLength(4);
  await page.getByRole("button", { name: ui.en.restart, exact: true }).click();
  await expect(page.getByRole("heading", { name: questions.en[0], exact: true })).toBeVisible();
  expect(hasFacts(planningCalls.at(-1), {})).toBe(true);
});

test("a slow English response cannot replace the current Arabic result after a locale switch", async ({ page, planningCalls }) => {
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
    await page.getByRole("link", { name: "العربية", exact: true }).click();
    await expect(page.getByRole("article", { name: ui.ar.plan, exact: true })).toBeVisible();
    expect(planningCalls.at(-1)?.locale).toBe("ar");
    expect(hasFacts(planningCalls.at(-1), { application_location: "inside_egypt", has_required_photos: true, [noteKey]: notes.happy })).toBe(true);
  } finally { gate.release(); }
  await finished.promise;
  await page.clock.fastForward(10_000);
  await expect(page.getByRole("article", { name: ui.en.plan, exact: true })).toHaveCount(0);
  await expect(page.getByRole("article", { name: ui.ar.plan, exact: true })).toHaveAttribute("lang", "ar");
  await expect(page.getByText(richPlan("en").title, { exact: true })).toHaveCount(0);
});
