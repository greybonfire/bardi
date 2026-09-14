import { test as base, expect, type Page, type Request } from "@playwright/test";
import type { Locale, PlanningRequest } from "../src/api/contract";
import { notes, passportId, questions } from "./fixtures.mjs";

// Pinned independently of runtime storage/copy exports. Synthetic bodies are
// inspected transiently in memory only: never attach, log, or serialize them.
export const storageKey = "bardi.active-case.v1";
export const evaluationDate = "2026-09-12";
export const ui = {
  en: {
    home: "Prepare your paperwork, one question at a time.",
    service: "Passport renewal", start: "Start the questions", continue: "Continue",
    inside: "Inside Egypt", yes: "Yes", no: "No", plan: "Preparation plan",
    review: "Review or change answers", changeLocation: "Change answer: Application location",
    clear: "Clear answers and start again", confirmClear: "Yes, clear answers", cleared: "Your case is cleared",
    restart: "Start again", retry: "Try again with these answers", failure: "We couldn’t continue",
    restored: "Your answers from this tab are back.", evidence: "Sources and reference details",
    print: "Print guidance", invalid: "Some information needs checking", correct: "Correct these answers",
    inconclusive: "We can’t prepare reliable guidance yet",
    sections: ["Things to keep in mind", "Prerequisites", "Documents and preparation", "What to do", "Fees", "Eligibility bases", "Where to go"],
  },
  ar: {
    home: "جهّز ورقك، سؤال بسؤال.",
    service: "تجديد جواز السفر", start: "ابدأ الأسئلة", continue: "كمّل",
    inside: "داخل مصر", yes: "أيوه", no: "لأ", plan: "خطة التحضير",
    review: "راجع أو غيّر إجاباتك", changeLocation: "غيّر الإجابة: مكان تقديم الطلب",
    clear: "امسح الإجابات وابدأ من جديد", confirmClear: "أيوه، امسح الإجابات", cleared: "مسحنا الحالة",
    restart: "ابدأ من جديد", retry: "جرّب تاني بنفس الإجابات", failure: "ما قدرناش نكمّل",
    restored: "رجّعنا إجاباتك من التبويب ده.", evidence: "المصادر وتفاصيل المرجع",
    print: "اطبع الإرشادات", invalid: "في معلومات محتاجة مراجعة", correct: "صحّح الإجابات دي",
    inconclusive: "مش قادرين نجهّز إرشادات موثوقة دلوقتي",
    sections: ["خلي بالك", "إجراءات لازم تسبق ده", "الورق والتحضير", "تمشي إزاي", "الرسوم", "أسس الاستحقاق", "تروح فين"],
  },
} as const;

export function isPlanning(request: Request) {
  return new URL(request.url()).pathname === "/v1/planning" && request.method() === "POST";
}

export const test = base.extend<{ planningCalls: PlanningRequest[] }>({
  page: async ({ page, context }, provide) => {
    // Fonts/assets must be self-hosted. A deliberately tested external source is
    // fulfilled by a more-specific test route; no acceptance test uses the web.
    await context.route(/^https?:\/\/(?!localhost:3010(?:\/|$)|127\.0\.0\.1:3010(?:\/|$))/, (route) => route.abort());
    await page.clock.install({ time: new Date(`${evaluationDate}T09:00:00Z`) });
    await provide(page);
  },
  planningCalls: async ({ page }, provide) => {
    const calls: PlanningRequest[] = [];
    const collect = (request: Request) => { if (isPlanning(request)) calls.push(request.postDataJSON() as PlanningRequest); };
    page.on("request", collect);
    await provide(calls);
    page.off("request", collect);
    calls.length = 0;
  },
});
export { expect };

export function planPath(locale: Locale = "en", serviceId = passportId) {
  return `/${locale}/services/${encodeURIComponent(serviceId)}/plan`;
}

export async function openQuestionnaire(page: Page, locale: Locale = "en", serviceId = passportId) {
  await page.goto(planPath(locale, serviceId));
  await expect(page.getByRole("heading", { name: questions[locale][0], exact: true })).toBeVisible();
}

export async function answerLocation(page: Page, locale: Locale = "en") {
  const form = page.getByRole("form", { name: questions[locale][0], exact: true });
  await form.getByRole("radio", { name: ui[locale].inside, exact: true }).check();
  await form.getByRole("button", { name: ui[locale].continue, exact: true }).click();
  await expect(page.getByRole("heading", { name: questions[locale][1], exact: true })).toBeVisible();
}

export async function answerPhotos(page: Page, locale: Locale = "en", value = true) {
  const form = page.getByRole("form", { name: questions[locale][1], exact: true });
  await form.getByRole("radio", { name: value ? ui[locale].yes : ui[locale].no, exact: true }).check();
  await form.getByRole("button", { name: ui[locale].continue, exact: true }).click();
  await expect(page.getByRole("heading", { name: questions[locale][2], exact: true })).toBeVisible();
}

export async function submitNote(page: Page, locale: Locale = "en", note = notes.happy) {
  const form = page.getByRole("form", { name: questions[locale][2], exact: true });
  await form.getByRole("textbox", { name: questions[locale][2], exact: true }).fill(note);
  await form.getByRole("button", { name: ui[locale].continue, exact: true }).click();
}

export async function preparePlan(page: Page, locale: Locale = "en", photos = true) {
  await openQuestionnaire(page, locale);
  await answerLocation(page, locale);
  await answerPhotos(page, locale, photos);
  await submitNote(page, locale);
  await expect(page.getByRole("article", { name: ui[locale].plan, exact: true })).toBeVisible();
}

export async function storedCase(page: Page) {
  return page.evaluate((key) => {
    const raw = sessionStorage.getItem(key);
    return raw === null ? null : JSON.parse(raw) as {
      version: number; serviceId: string; date: string;
      facts: Record<string, unknown>; history: { questionId: string; keys: string[] }[];
    };
  }, storageKey);
}

export function hasFacts(input: PlanningRequest | undefined, facts: Record<string, unknown>) {
  return !!input && JSON.stringify(Object.entries(input.facts).sort()) === JSON.stringify(Object.entries(facts).sort());
}

export async function expectNoOverflow(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth &&
    document.body.scrollWidth <= document.documentElement.clientWidth,
  )).toBe(true);
}

export function deferred() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => { release = resolve; });
  return { promise, release };
}
