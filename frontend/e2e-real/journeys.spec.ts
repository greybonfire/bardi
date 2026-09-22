import { test, expect, type Page, type Response } from "@playwright/test";
import { planningResultSchema, type Facts, type Locale, type PlanningRequest, type PlanningResult } from "../src/api/contract";

const service = "get_egyptian_national_id";
const date = "2026-08-26";
const keys = ["application_location", "national_id_possession_state", "national_id_data_change_kind", "national_id_expiry_date"];
const ids = ["application_location", "possession_state", "data_change_kind", "expiry_date"];
const values = ["inside_egypt", "held", "none", "2026-05-01"];
const copy = {
  en: { service: "Get an Egyptian National ID", start: "Start the questions", next: "Continue", choices: ["Inside Egypt", "Card held", "No data changes"], fee: "Current amount unknown — check before paying.", routing: "Destination unresolved", blocked: "Current/previous card" },
  ar: { service: "الحصول على بطاقة رقم قومي مصرية", start: "ابدأ الأسئلة", next: "كمّل", choices: ["داخل مصر", "البطاقة موجودة معايا", "مفيش بيانات محتاجة تغيير"], fee: "القيمة الحالية مش معروفة — اتأكد منها قبل الدفع.", routing: "جهة التقديم لسه مش محسومة", blocked: "البطاقة الحالية/القديمة" },
};

function planning(response: Response) {
  return new URL(response.url()).pathname === "/v1/planning" && response.request().method() === "POST";
}
async function exchange(page: Page, locale: Locale, facts: Facts, action: () => Promise<unknown>): Promise<PlanningResult> {
  const pending = page.waitForResponse(planning);
  await action();
  const response = await pending;
  const request = response.request().postDataJSON() as PlanningRequest;
  // Assert only booleans: failures must never serialize source Facts or bodies.
  expect(response.ok()).toBe(true);
  expect(request.service_id === service && request.locale === locale && request.evaluation_context.evaluation_date === date).toBe(true);
  expect(JSON.stringify(Object.entries(request.facts).sort()) === JSON.stringify(Object.entries(facts).sort())).toBe(true);
  const parsed = planningResultSchema.safeParse(await response.json());
  expect(parsed.success).toBe(true);
  if (!parsed.success) throw new Error("REAL_E2E_RESPONSE_SCHEMA");
  return parsed.data;
}
function question(result: PlanningResult, index: number) {
  expect(result.type === "next_question" && result.service_id === service && result.question.id === `q.nid.${ids[index]}`
    && result.question.answers.length === 1 && result.question.answers[0].key === keys[index]
    && result.question.answers[0].kind === (index === 3 ? "date" : "enum")).toBe(true);
}
async function answer(page: Page, locale: Locale, result: PlanningResult, index: number, facts: Facts, lost = false) {
  question(result, index);
  if (result.type !== "next_question") throw new Error("REAL_E2E_QUESTION");
  const form = page.getByRole("form", { name: result.question.text, exact: true });
  await expect(form).toBeVisible();
  if (index === 3) await form.getByLabel(result.question.text, { exact: true }).fill(values[index]);
  else await form.getByRole("radio", { name: lost ? "Lost" : copy[locale].choices[index], exact: true }).check();
  facts[keys[index]] = lost ? "lost" : values[index];
  return exchange(page, locale, facts, () => form.getByRole("button", { name: copy[locale].next, exact: true }).click());
}
async function assertPlan(page: Page, locale: Locale, result: PlanningResult) {
  expect(result.type === "plan" && result.service_id === service
    && result.procedure_id === "ordinary_domestic_national_id_renewal"
    && result.procedure_version_id === "ordinary_domestic_national_id_renewal.research-2026-08-26"
    && result.routing.status === "unresolved" && result.routing.destinations.length === 0
    && result.fees.some((fee) => fee.id === "nid.fee.ordinary" && fee.value_state === "unknown" && fee.current_value_unknown && fee.amount === null)
    && !result.checklist_items.some((item) => item.id === "nid.requirement.previous_card")
    && result.checklist_items.some((item) => item.sources.length > 0)).toBe(true);
  const article = page.getByRole("article", { name: locale === "ar" ? "خطة التحضير" : "Preparation plan", exact: true });
  await expect(article).toBeVisible();
  await expect(article).toHaveAttribute("dir", locale === "ar" ? "rtl" : "ltr");
  await expect(article.getByText(copy[locale].fee, { exact: true })).toBeVisible();
  await expect(article.getByText(copy[locale].routing, { exact: true })).toBeVisible();
  await expect(article.getByText(copy[locale].blocked, { exact: true })).toHaveCount(0);
}
async function complete(page: Page, locale: Locale) {
  await page.goto(`/${locale}`);
  await expect(page.locator("html")).toHaveAttribute("dir", locale === "ar" ? "rtl" : "ltr");
  await page.getByRole("link", { name: copy[locale].service, exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: copy[locale].service, exact: true })).toBeVisible();
  const facts: Facts = {};
  let result = await exchange(page, locale, facts, () => page.getByRole("link", { name: copy[locale].start, exact: true }).click());
  for (let index = 0; index < 4; index++) result = await answer(page, locale, result, index, facts);
  await assertPlan(page, locale, result);
}

test.beforeEach(async ({ page, context, baseURL }) => {
  await context.route("**/*", (route) => new URL(route.request().url()).origin === baseURL ? route.continue() : route.abort());
  await context.routeWebSocket(/.*/, (socket) => {
    const url = new URL(socket.url());
    url.protocol = url.protocol === "wss:" ? "https:" : "http:";
    if (url.origin === baseURL) socket.connectToServer(); else socket.close();
  });
  await page.clock.install({ time: new Date(`${date}T09:00:00Z`) });
});
for (const locale of ["ar", "en"] as const) {
  test(`${locale}: real National ID renewal`, async ({ page }) => { await complete(page, locale); });
}
test("en: possession correction and recovery", async ({ page }) => {
  await complete(page, "en");
  const change = async () => {
    const button = page.getByRole("button", { name: "Change answer: Current National ID status", exact: true });
    if (!await button.isVisible()) await page.getByText("Review or change answers", { exact: true }).click();
    const result = await exchange(page, "en", { application_location: "inside_egypt" }, () => button.click());
    await expect(page.getByRole("article")).toHaveCount(0);
    return result;
  };
  let result = await change();
  result = await answer(page, "en", result, 1, { application_location: "inside_egypt" }, true);
  expect(result.type === "inconclusive" && result.reason === "no_matching_researched_procedure").toBe(true);
  await expect(page.getByRole("heading", { name: "We can’t prepare reliable guidance yet", exact: true })).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
  result = await change();
  const facts: Facts = { application_location: "inside_egypt" };
  for (let index = 1; index < 4; index++) result = await answer(page, "en", result, index, facts);
  await assertPlan(page, "en", result);
});
