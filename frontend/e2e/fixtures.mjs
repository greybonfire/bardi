import { createPlanFixture, createPartialPlanFixture } from "../tests/plan-fixture.ts";

/**
 * TEST DATA ONLY / بيانات اصطناعية للاختبار فقط.
 * This is a fixed public-transport acceptance matrix, NOT Egyptian administrative
 * rules, researched guidance, a copy of the private engine, or a real Case.
 * Never enter personal details into this fixture. Nothing is persisted or logged.
 * The familiar bilingual Service titles are examples, not claims of coverage.
 * Runtime production validators/copy/storage constants are intentionally not used.
 */
export const passportId = "e2e.passport-renewal";
export const identityId = "e2e.national-id-renewal";
export const familyId = "e2e.family-exemption";
export const services = [
  { id: familyId, title: { ar: "الإعفاء العائلي المؤقت", en: "Temporary family exemption" } },
  { id: identityId, title: { ar: "تجديد بطاقة الرقم القومي", en: "National ID renewal" } },
  { id: passportId, title: { ar: "تجديد جواز السفر", en: "Passport renewal" } },
];
export const noteKey = "synthetic_note";
export const notes = {
  happy: "TEST-ONLY-NOTE",
  invalid: "TEST-ONLY-INVALID",
  inconclusive: "TEST-ONLY-INCONCLUSIVE",
  rateLimited: "TEST-ONLY-RATE-LIMITED",
  unavailable: "TEST-ONLY-UNAVAILABLE",
  malformed: "TEST-ONLY-MALFORMED",
};
export const questions = {
  ar: [
    "مثال اصطناعي فقط: أين سيُقدّم هذا الطلب التجريبي؟",
    "مثال اصطناعي فقط: هل الصور التجريبية جاهزة؟",
    "مثال اصطناعي فقط: اكتب TEST-ONLY-NOTE، وليس أي بيانات شخصية.",
  ],
  en: [
    "Synthetic example only: where will this test request be submitted?",
    "Synthetic example only: are the sample photos ready?",
    "Synthetic example only: enter TEST-ONLY-NOTE, not personal details.",
  ],
};
export const inconclusiveMessages = {
  ar: "هذا المثال الاصطناعي لا يوفّر إرشادات موثوقة لهذه الظروف.\nلا تستخدم بيانات الاختبار لإتمام معاملة حقيقية.",
  en: "This synthetic example cannot provide reliable guidance for these circumstances.\nDo not use test data for a real transaction.",
};

export function nextQuestion(serviceId, locale, index) {
  const definitions = [
    { key: "application_location", kind: "enum", enum_options: ["inside_egypt", "outside_egypt"], minimum: null },
    { key: "has_required_photos", kind: "boolean", enum_options: [], minimum: null },
    { key: noteKey, kind: "string", enum_options: [], minimum: null },
  ];
  return {
    type: "next_question",
    service_id: serviceId,
    question: { id: `e2e.question.${index + 1}`, text: questions[locale][index], answers: [definitions[index]] },
  };
}

export function richPlan(locale = "en", serviceId = passportId, partial = false) {
  const plan = partial ? createPartialPlanFixture(locale) : createPlanFixture(locale);
  return { ...plan, service_id: serviceId };
}

/** Stateless switches use only the fixed, known synthetic Facts above. */
export function planningReply(input) {
  const { service_id: serviceId, locale, facts } = input;
  if (!services.some(({ id }) => id === serviceId)) {
    return { status: 200, data: { type: "inconclusive", reason: "unknown_service", message: inconclusiveMessages[locale] } };
  }
  for (const [index, key] of ["application_location", "has_required_photos", noteKey].entries()) {
    if (!Object.hasOwn(facts, key)) return { status: 200, data: nextQuestion(serviceId, locale, index) };
  }
  switch (facts[noteKey]) {
    case notes.invalid:
      return { status: 200, data: { type: "invalid", diagnostics: [
        { code: "contradictory_facts", path: ["facts", "has_required_photos"] },
        { code: "contradictory_facts", path: ["facts", noteKey] },
      ] } };
    case notes.inconclusive:
      return { status: 200, data: { type: "inconclusive", reason: "unsupported_case", message: inconclusiveMessages[locale] } };
    case notes.rateLimited:
      return { status: 429, retryAfter: "2", data: { type: "invalid", diagnostics: [{ code: "rate_limited", path: [] }] } };
    case notes.unavailable:
      return { status: 503, data: { type: "invalid", diagnostics: [{ code: "knowledge_unavailable", path: [] }] } };
    case notes.malformed:
      return { status: 200, data: { type: "plan", title: "TEST-ONLY incomplete transport; must never render" } };
    default:
      return { status: 200, data: richPlan(locale, serviceId, facts.has_required_photos === false) };
  }
}
