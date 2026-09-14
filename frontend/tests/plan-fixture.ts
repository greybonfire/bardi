import type { Freshness, Locale, Plan, Source } from "@/api/contract";

/** Synthetic public-contract data only: not researched Egyptian guidance. */
export const planEvaluationDate = "2026-09-12";

function current(): Freshness {
  return { state: "current", verified_on: "2026-09-01", reverify_on: "2026-10-01" };
}

export function createPlanSources(locale: Locale): Source[] {
  const text = (ar: string, en: string) => locale === "ar" ? ar : en;
  return [
    {
      id: "demo.source.official",
      authority_id: "demo.authority.records",
      title: text("دليل المعاملة التجريبي — نص رسمي للاختبار", "Synthetic transaction guide — official test text"),
      locator: "https://example.org/synthetic/guide?edition=1&language=both",
      classification: "official",
      retrieved_on: "2026-09-01",
    },
    {
      id: "demo.source.field",
      authority_id: "demo.authority.research",
      title: text("تقرير ميداني تجريبي عن التحضير", "Synthetic preparation field report"),
      locator: "http://example.org/synthetic/field-report",
      classification: "field_report",
      retrieved_on: "2026-08-25",
    },
    {
      id: "demo.source.archive",
      authority_id: "demo.authority.archive",
      title: text("سجل بحثي محفوظ — ليس تأكيدًا حاليًا", "Preserved research record — not current confirmation"),
      locator: "Synthetic archive register, volume 2, page 7",
      classification: "secondary",
      retrieved_on: "2025-11-04",
    },
  ];
}

/** Every public section, all dependency/fee/freshness states, both source kinds
 * and plain-text provenance. Array order is deliberately not alphabetical. */
export function createPlanFixture(locale: Locale = "ar"): Plan {
  const text = (ar: string, en: string) => locale === "ar" ? ar : en;
  const [official, field, archive] = createPlanSources(locale);
  const baseFee = {
    amount: null,
    minimum_amount: null,
    maximum_amount: null,
    currency: "EGP",
    fee_type: "synthetic_service_fee",
    current_value_unknown: true,
    sources: [official],
    freshness: current(),
  } satisfies Omit<Plan["fees"][number], "id" | "text" | "value_state">;

  return {
    type: "plan",
    service_id: "demo.service.preparation",
    procedure_id: "demo.procedure.renewal",
    procedure_version_id: "demo.procedure.renewal.2026-09",
    title: text("خطة تحضير تجريبية — بيانات اختبار فقط", "Synthetic preparation plan — test data only"),
    eligibility_bases: [
      {
        id: "demo.basis.z",
        text: text("أساس الاستحقاق التجريبي: الحالة المسجلة", "Synthetic eligibility basis: recorded status"),
        checklist_item_ids: ["demo.checklist.shared"],
        step_ids: ["demo.step.z.submit"],
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.basis.a",
        text: text("أساس الاستحقاق التجريبي: مستند بديل", "Synthetic eligibility basis: alternative record"),
        checklist_item_ids: ["demo.checklist.shared", "demo.checklist.basis"],
        step_ids: ["demo.step.a.collect"],
        sources: [official],
        freshness: current(),
      },
    ],
    inconclusive_basis_ids: [],
    inconclusive_sections: [],
    dependencies: [
      {
        id: "demo.dependency.satisfied",
        text: text("سبق التحقق من المتطلب التجريبي الأول.", "The first synthetic prerequisite has been established."),
        relation: "blocking_prerequisite",
        status: "satisfied",
        target_procedure_id: "demo.procedure.registration",
        target_procedure: text("قيد تجريبي", "Synthetic registration"),
        target_procedure_version_id: "demo.registration.2026",
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.dependency.blocking",
        text: text("استكمل السجل التجريبي المطلوب أولًا.", "Complete the required synthetic record first."),
        relation: "blocking_prerequisite",
        status: "blocking",
        target_procedure_id: "demo.procedure.record",
        target_procedure: text("إصدار سجل تجريبي", "Issue a synthetic record"),
        target_procedure_version_id: "demo.record.2026",
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.dependency.unsupported",
        text: text("يرتبط هذا المثال بإجراء لا تدعمه هذه الخدمة.", "This example depends on a procedure this service does not support."),
        relation: "blocking_prerequisite",
        status: "unsupported_target",
        target_procedure_id: "demo.procedure.external",
        target_procedure: text("إجراء تجريبي خارجي", "External synthetic procedure"),
        target_procedure_version_id: null,
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.dependency.inconclusive",
        text: text("يلزم التحقق من حالة المتطلب التجريبي الأخير.", "The last synthetic prerequisite needs verification."),
        relation: "blocking_prerequisite",
        status: "inconclusive",
        target_procedure_id: "demo.procedure.verification",
        target_procedure: text("تحقق تجريبي", "Synthetic verification"),
        target_procedure_version_id: null,
        sources: [archive],
        freshness: { state: "unknown", verified_on: null, reverify_on: null },
      },
    ],
    checklist_items: [
      {
        id: "demo.checklist.identity",
        text: text("قدّم أصل المستند التجريبي للاطلاع.", "Present the original synthetic document for inspection."),
        classification: "official_requirement",
        classification_label: text("متطلب رسمي — تصنيف المصدر", "Official Requirement — source-authored label"),
        quantity: 1,
        original_quantity: 1,
        copy_quantity: 0,
        document_type_id: "demo.document.identity",
        scope: "procedure",
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.checklist.shared",
        text: text("أرفق أصل السجل المشترك وصورتين منه.", "Attach the shared record’s original and two copies."),
        classification: "official_requirement",
        classification_label: text("متطلب رسمي مشترك", "Shared Official Requirement"),
        quantity: 3,
        original_quantity: 1,
        copy_quantity: 2,
        document_type_id: "demo.document.shared",
        scope: "eligibility_basis",
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.checklist.basis",
        text: text("أرفق صورة السجل البديل في هذا المثال.", "Attach a copy of the alternative record in this example."),
        classification: "official_requirement",
        classification_label: text("متطلب رسمي خاص بالأساس", "Basis-specific Official Requirement"),
        quantity: 1,
        original_quantity: 0,
        copy_quantity: 1,
        document_type_id: "demo.document.alternative",
        scope: "eligibility_basis",
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.checklist.practical",
        text: text("احتفظ بالملاحظات التجريبية منفصلة عن المستندات.\nهذه نصيحة تحضيرية وليست متطلبًا رسميًا.", "Keep the synthetic notes separate from documents.\nThis is preparation advice, not an official requirement."),
        classification: "practical_preparation",
        classification_label: text("تحضير عملي — تقرير ميداني", "Practical Preparation — field report"),
        quantity: 0,
        original_quantity: 0,
        copy_quantity: 0,
        document_type_id: null,
        scope: "procedure",
        sources: [field],
        freshness: current(),
      },
    ],
    steps: [
      {
        id: "demo.step.z.submit",
        text: text("قدّم الملف التجريبي في نقطة الخدمة المحددة.", "Submit the synthetic file at the specified service point."),
        phase: "submit",
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.step.a.collect",
        text: text("احتفظ بإيصال المثال بعد تقديم الملف.", "Keep the example receipt after submitting the file."),
        phase: "collect",
        sources: [official],
        freshness: current(),
      },
    ],
    fees: [
      { ...baseFee, id: "demo.fee.zero", text: text("رسم النموذج التجريبي", "Synthetic form fee"), value_state: "known", amount: 0, current_value_unknown: false },
      { ...baseFee, id: "demo.fee.known", text: text("رسم المعاملة التجريبية", "Synthetic transaction fee"), value_state: "known", amount: 120, current_value_unknown: false },
      { ...baseFee, id: "demo.fee.range", text: text("نطاق رسم خدمة تجريبية", "Synthetic service fee range"), value_state: "range", minimum_amount: 125, maximum_amount: 175, current_value_unknown: false },
      { ...baseFee, id: "demo.fee.unknown", text: text("رسم شهادة تجريبية غير محدد", "Unspecified synthetic certificate fee"), value_state: "unknown", sources: [] },
      { ...baseFee, id: "demo.fee.unverified", text: text("رسم تجريبي لم يُتحقق منه", "Unverified synthetic fee"), value_state: "unverified", sources: [archive], freshness: { state: "unknown", verified_on: null, reverify_on: null } },
      { ...baseFee, id: "demo.fee.review", text: text("رسم تجريبي يحتاج مراجعة", "Synthetic fee needing re-verification"), value_state: "unverified", sources: [archive], freshness: { state: "needs_reverification", verified_on: "2025-12-01", reverify_on: "2026-01-01" } },
      { ...baseFee, id: "demo.fee.stale", text: text("رسم تجريبي بمعلومات قديمة", "Synthetic fee with stale information"), value_state: "unverified", sources: [archive], freshness: { state: "stale", verified_on: "2025-11-05", reverify_on: "2026-01-01" } },
      { ...baseFee, id: "demo.fee.disputed", text: text("رسم تجريبي محل خلاف", "Disputed synthetic fee"), value_state: "unverified", sources: [official, archive], freshness: { state: "disputed", verified_on: "2026-08-01", reverify_on: "2026-09-01" } },
    ],
    warnings: [
      {
        id: "demo.warning.admin",
        text: text("هذا المثال لا يغطي تغيير بيانات السجل.", "This example does not cover changes to the record’s details."),
        severity: "info",
        kind: "administrative",
        role: "general",
        sources: [official],
        freshness: current(),
      },
      {
        id: "demo.warning.limitation",
        text: text("البيانات هنا اصطناعية ولا تُستخدم لإتمام معاملة حقيقية.", "These data are synthetic and must not be used for a real transaction."),
        severity: "important",
        kind: "product",
        role: "limitation",
        sources: [],
        freshness: current(),
      },
      {
        id: "demo.warning.regenerate",
        text: text("أعد إنشاء الخطة قبل التصرف بناءً عليها مباشرة.", "Regenerate the plan immediately before acting on it."),
        severity: "important",
        kind: "product",
        role: "regeneration",
        sources: [],
        freshness: current(),
      },
    ],
    routing: {
      status: "resolved",
      destinations: [
        {
          service_point_id: "demo.point.west",
          service_point_version_id: "demo.point.west.2026",
          association_id: "demo.route.west.a",
          name: text("مكتب الاختبار — غرب", "Test office — West"),
          address: text("١ شارع المثال، منطقة الاختبار\nعنوان اصطناعي غير حقيقي", "1 Example Street, Test District\nSynthetic address, not a real destination"),
          availability: "available",
          effective_from: "2026-09-01",
          effective_to: "2026-12-31",
          sources: [official],
        },
        {
          service_point_id: "demo.point.west",
          service_point_version_id: "demo.point.west.2026",
          association_id: "demo.route.west.b",
          name: text("مكتب الاختبار — غرب", "Test office — West"),
          address: text("١ شارع المثال، منطقة الاختبار\nعنوان اصطناعي غير حقيقي", "1 Example Street, Test District\nSynthetic address, not a real destination"),
          availability: "available",
          effective_from: "2026-09-01",
          effective_to: "2026-12-31",
          sources: [official],
        },
        {
          service_point_id: "demo.point.east",
          service_point_version_id: "demo.point.east.2026",
          association_id: "demo.route.east",
          name: text("مكتب الاختبار — شرق", "Test office — East"),
          address: text("عنوان اختبار تجريبي", "Synthetic test address"),
          availability: "unknown",
          effective_from: null,
          effective_to: null,
          sources: [official],
        },
      ],
      verification_sources: [],
    },
  };
}

/** Local research uncertainty must leave all unrelated reliable rows intact. */
export function createPartialPlanFixture(locale: Locale = "ar"): Plan {
  const plan = createPlanFixture(locale);
  const text = (ar: string, en: string) => locale === "ar" ? ar : en;
  const archive = createPlanSources(locale)[2];
  return {
    ...plan,
    eligibility_bases: [
      ...plan.eligibility_bases,
      {
        id: "demo.basis.candidate",
        text: text("أساس تجريبي يحتاج تحققًا إضافيًا", "Synthetic basis needing further verification"),
        checklist_item_ids: [],
        step_ids: [],
        sources: [archive],
        freshness: { state: "needs_reverification", verified_on: "2025-12-01", reverify_on: "2026-01-01" },
      },
    ],
    inconclusive_basis_ids: ["demo.basis.candidate", "demo.basis.id-only"],
    inconclusive_sections: ["checklist_items", "steps"],
    routing: {
      ...plan.routing,
      status: "partially_resolved",
      verification_sources: [archive],
    },
  };
}
