import { useId, type ReactNode } from "react";
import type { Freshness, Locale, Plan, Source } from "@/api/contract";
import "./plan-view.css";

const copy = {
  ar: {
    plan: "خطة التحضير",
    identity: "عن الخطة دي",
    serviceId: "مرجع الخدمة",
    procedureId: "مرجع الإجراء",
    versionId: "مرجع نسخة الإجراء",
    evaluationDate: "تاريخ التقييم",
    reference: "مرجع البند",
    notProvided: "مش مذكور في الخطة",
    reminderTitle: "قبل ما تتحرك",
    reminder: "طلّع الخطة من جديد قبل ما تتصرف على أساسها مباشرة. المعلومات ممكن تتغير، والخطة مش قرار من الجهة المختصة ولا ضمان لإتمام الإجراء.",
    index: "في الخطة دي",
    warnings: "خلي بالك",
    dependencies: "إجراءات لازم تسبق ده",
    checklist: "الورق والتحضير",
    steps: "تمشي إزاي",
    fees: "الرسوم",
    bases: "أسس الاستحقاق",
    routing: "تروح فين",
    localLimits: "في أجزاء لسه مش محسومة. هتلاقي حدود كل جزء جنبه؛ باقي المعلومات الموثوقة لسه موجودة.",
    noWarnings: "الخطة ما رجّعتش تنبيهات إضافية. ده مش ضمان إن مفيش قيود؛ راجع التذكير قبل ما تتحرك.",
    severity: { info: "للعلم", important: "مهم" },
    warningKind: { administrative: "تنبيه إداري", product: "تنبيه من بردي" },
    warningRole: { general: "تنبيه عام", regeneration: "تجديد الخطة قبل التصرف", limitation: "حدود الإرشادات" },
    dependencyIntro: "دي إجراءات سابقة مباشرة بس. الخطة دي مش بتعمل خطة منفصلة لكل واحد منها.",
    noDependencies: "الخطة ما رجّعتش إجراءات سابقة. ده مش تأكيد إن مفيش متطلبات تانية.",
    dependencyStatus: {
      satisfied: "المتطلب السابق متحقق حسب التقييم",
      blocking: "لازم تخلص المتطلب السابق قبل ما تكمل",
      unsupported_target: "الإجراء السابق مش مدعوم هنا؛ بردي مش هيقدر يطلع خطته",
      inconclusive: "حالة المتطلب السابق مش محسومة؛ راجعها قبل ما تكمل",
    },
    relation: "نوع الارتباط",
    blockingPrerequisite: "متطلب سابق لازم يتحقق",
    target: "الإجراء السابق",
    targetId: "مرجع الإجراء السابق",
    targetVersion: "مرجع نسخته",
    official: "متطلبات رسمية",
    practical: "تحضير عملي — مش متطلبات رسمية",
    checklistLimit: "قائمة الورق مش محسومة بالكامل. البنود المعروضة تفضل مفيدة، لكن ما تعتبرهاش قائمة كاملة.",
    noChecklist: "الخطة ما رجّعتش بنود تحضير. ده مش معناه إن مفيش ورق أو متطلبات؛ اتأكد من الجهة المختصة.",
    quantity: "العدد",
    originals: "الأصول",
    copies: "الصور",
    documentType: "مرجع نوع المستند",
    scope: "نطاق البند",
    procedureScope: "للإجراء كله",
    basisScope: "مرتبط بأساس استحقاق",
    relatedBases: "أسس الاستحقاق المرتبطة",
    missingBasis: "الخطة ما وضّحتش أساس الاستحقاق المرتبط بالبند ده.",
    stepLimit: "الخطوات مش محسومة بالكامل. اتبع المعلومات الموثوقة المعروضة، من غير ما تعتبرها كل الخطوات المطلوبة.",
    noSteps: "الخطة ما رجّعتش خطوات. ده مش معناه إن مفيش خطوات مطلوبة؛ راجع الجهة المختصة.",
    phase: "المرحلة",
    phaseCode: "مرجع المرحلة",
    phases: { "prepare-at-office": "التحضير في نقطة الخدمة", submit: "تقديم الطلب", route: "تحديد جهة التقديم", adjudicate: "البت في الطلب" },
    feeTypes: { government_fee: "رسم حكومي", optional_service_fee: "رسم خدمة اختيارية", service_fee: "رسم خدمة", certificate: "رسم شهادة" },
    feeTypeCode: "مرجع نوع الرسم",
    feeIntro: "دي قيم بنود منفصلة، مش إجمالي الرسوم. أي قيمة مش معروفة محتاجة مراجعة قبل الدفع.",
    noFees: "الخطة ما رجّعتش معلومات عن الرسوم. ده مش معناه إن الإجراء مجاني.",
    feeType: "نوع الرسم",
    currency: "العملة",
    feeState: "حالة القيمة في السجل",
    feeStates: { known: "قيمة محددة", range: "نطاق قيم", unknown: "غير معروفة", unverified: "غير متحقق منها" },
    amount: "المبلغ حسب التقييم",
    amountRange: "النطاق حسب التقييم",
    rangeTo: "إلى",
    currentAmountUnknown: "القيمة الحالية مش معروفة — اتأكد منها قبل الدفع.",
    feeProvenance: "المصادر دي للرجوع والتحقق، مش تأكيد لقيمة حالية. أي رقم سابق ما تعتمدش عليه للدفع.",
    basisIntro: "دي أسس استحقاق بديلة، من غير ترتيب أفضلية أو ترشيح. ظهور أساس هنا مش قرار رسمي بالاستحقاق.",
    noBases: "الخطة ما رجّعتش أسس استحقاق. ده مش حكم بالقبول أو الرفض.",
    matchedBasis: "أساس مطابق حسب التقييم، مش قرار من الجهة المختصة",
    candidateBasis: "أساس محتمل غير محسوم — مش تأكيد للاستحقاق",
    candidateDetail: "ما تعتمدش على الأساس ده لإثبات الاستحقاق أو متطلباته. مصادره مراجع للتحقق، مش تأكيد حالي.",
    basisChecklist: "بنود الورق المرتبطة",
    basisSteps: "الخطوات المرتبطة",
    noMappedClaims: "الخطة ما رجّعتش بنود مرتبطة هنا؛ ده مش معناه إن مفيش متطلبات.",
    unavailableClaim: "تفاصيل البند مش موجودة في الخطة دي",
    inconclusiveBases: "أسس لسه مش محسومة",
    inconclusiveBasisIntro: "المراجع دي لأسس محتاجة تحقق، مش إثبات إنك مؤهل على أساسها.",
    routingStatus: {
      resolved: "جهات التقديم اتحسمت للخطة دي",
      partially_resolved: "في جهات معروفة، وجزء من التوجيه لسه مش محسوم",
      unresolved: "جهة التقديم لسه مش محسومة",
    },
    routingIntro: "دي جهات الخطة دي بس، من غير ترتيب أفضلية أو اختيار للأقرب. مش دليل على تغطية كل مصر.",
    routingLimit: "عدم اليقين هنا يخص جهة التقديم بس؛ ما يلغيش باقي المعلومات الموثوقة في الخطة.",
    noDestinations: "الخطة ما رجّعتش جهة تقديم موثوقة. راجع الجهة المختصة بدل ما تفترض مكتب مناسب.",
    availability: "إتاحة الخدمة في الجهة دي",
    available: "متاحة حسب التوجيه الوارد في الخطة",
    availabilityUnknown: "مش معروفة في الجهة دي — اتأكد منها مباشرة قبل ما تروح",
    effectiveFrom: "بداية سريان بيانات الجهة",
    effectiveTo: "نهاية سريان بيانات الجهة",
    pointId: "مرجع نقطة الخدمة",
    pointVersionId: "مرجع نسخة بياناتها",
    associationId: "مرجع ارتباطها بالإجراء",
    manualSources: "مصادر للمراجعة اليدوية",
    manualSourceNotice: "دي مراجع محفوظة من البحث، وممكن تعكس معلومات تاريخية. استخدمها للمراجعة اليدوية؛ مش تأكيد إن بيانات الجهة أو اختصاصها ساريين دلوقتي.",
    noManualSources: "الخطة ما رجّعتش مصادر للمراجعة اليدوية.",
    evidence: "المصادر وتفاصيل المرجع",
    freshness: "حالة المراجعة",
    freshnessStates: {
      current: "سارية حسب التقييم",
      needs_reverification: "محتاجة مراجعة جديدة",
      stale: "قديمة — مش تأكيد حالي",
      disputed: "محل خلاف",
      unknown: "غير معروفة",
    },
    verifiedOn: "آخر تحقق",
    reverifyOn: "موعد إعادة التحقق",
    noSources: "مفيش مصادر مرفقة بالبند ده في الخطة.",
    productSources: "ده تنبيه من بردي، مش ادعاء إداري له مصدر خارجي.",
    sourceClassification: "نوع المصدر",
    sourceClasses: { official: "مصدر رسمي", field_report: "تقرير ميداني", secondary: "مصدر ثانوي" },
    retrievedOn: "تاريخ الاطلاع",
    authority: "مرجع الجهة صاحبة المصدر",
    sourceId: "مرجع المصدر",
    locator: "رابط أو مكان المصدر",
    external: "يفتح في تبويب جديد",
  },
  en: {
    plan: "Preparation plan",
    identity: "About this plan",
    serviceId: "Service reference",
    procedureId: "Procedure reference",
    versionId: "Procedure version reference",
    evaluationDate: "Evaluation date",
    reference: "Item reference",
    notProvided: "Not supplied in this plan",
    reminderTitle: "Before you act",
    reminder: "Regenerate this plan immediately before acting on it. Information can change; this plan is not an authority’s decision or a guarantee of completion.",
    index: "In this plan",
    warnings: "Things to keep in mind",
    dependencies: "Prerequisites",
    checklist: "Documents and preparation",
    steps: "What to do",
    fees: "Fees",
    bases: "Eligibility bases",
    routing: "Where to go",
    localLimits: "Some parts are still unresolved. Each section explains its limits; unrelated reliable guidance remains available.",
    noWarnings: "No additional warnings were returned. This does not guarantee there are no restrictions; keep the reminder in mind before acting.",
    severity: { info: "Information", important: "Important" },
    warningKind: { administrative: "Administrative warning", product: "Bardi safety note" },
    warningRole: { general: "General notice", regeneration: "Regenerate before acting", limitation: "Guidance limitation" },
    dependencyIntro: "These are direct prerequisites only. This plan does not create a separate plan for each of them.",
    noDependencies: "No prerequisites were returned. This does not establish that there are no other requirements.",
    dependencyStatus: {
      satisfied: "Prerequisite satisfied for this evaluation",
      blocking: "Blocking — complete this prerequisite before proceeding",
      unsupported_target: "Prerequisite not supported here — Bardi cannot provide its plan",
      inconclusive: "Prerequisite unresolved — check before proceeding",
    },
    relation: "Relationship",
    blockingPrerequisite: "Required beforehand",
    target: "Prerequisite procedure",
    targetId: "Prerequisite procedure reference",
    targetVersion: "Its version reference",
    official: "Official requirements",
    practical: "Practical preparation — not official requirements",
    checklistLimit: "The document list is not fully resolved. The items shown remain useful, but do not treat them as a complete list.",
    noChecklist: "No preparation items were returned. This does not mean no documents or requirements apply; check with the responsible authority.",
    quantity: "Quantity",
    originals: "Originals",
    copies: "Copies",
    documentType: "Document type reference",
    scope: "Item scope",
    procedureScope: "Whole procedure",
    basisScope: "Linked to an eligibility basis",
    relatedBases: "Related eligibility bases",
    missingBasis: "The related eligibility basis was not identified in this plan.",
    stepLimit: "The steps are not fully resolved. Use the reliable guidance shown, but do not treat it as every required step.",
    noSteps: "No steps were returned. This does not mean no steps are required; check with the responsible authority.",
    phase: "Phase",
    phaseCode: "Phase reference",
    phases: { "prepare-at-office": "Prepare at the service point", submit: "Submit", route: "Routing", adjudicate: "Adjudication" },
    feeTypes: { government_fee: "Government fee", optional_service_fee: "Optional service fee", service_fee: "Service fee", certificate: "Certificate fee" },
    feeTypeCode: "Fee type reference",
    feeIntro: "These are individual fee values, not a total. Check any unknown value before paying.",
    noFees: "No fee information was returned. This does not mean the procedure is free.",
    feeType: "Fee type",
    currency: "Currency",
    feeState: "Recorded value state",
    feeStates: { known: "Specified amount", range: "Range", unknown: "Unknown", unverified: "Unverified" },
    amount: "Amount for this evaluation",
    amountRange: "Range for this evaluation",
    rangeTo: "to",
    currentAmountUnknown: "Current amount unknown — check before paying.",
    feeProvenance: "These sources are a verification trail, not confirmation of a current amount. Do not rely on a past figure for payment.",
    basisIntro: "These are alternative eligibility bases, without ranking or recommendation. A basis appearing here is not an official eligibility decision.",
    noBases: "No eligibility bases were returned. This is not a decision to accept or reject eligibility.",
    matchedBasis: "Matched for this evaluation, not an authority’s decision",
    candidateBasis: "Inconclusive candidate — not confirmation of eligibility",
    candidateDetail: "Do not rely on this basis to establish eligibility or its requirements. Its sources are a verification trail, not current confirmation.",
    basisChecklist: "Linked document items",
    basisSteps: "Linked steps",
    noMappedClaims: "No linked items were returned here; this does not establish that there are no requirements.",
    unavailableClaim: "Item details were not returned in this plan",
    inconclusiveBases: "Bases still unresolved",
    inconclusiveBasisIntro: "These references identify bases needing verification, not proof that you qualify under them.",
    routingStatus: {
      resolved: "Routing resolved for this plan",
      partially_resolved: "Some destinations resolved; other routing is still uncertain",
      unresolved: "Destination unresolved",
    },
    routingIntro: "These destinations apply only to this plan, without ranking or a nearest-office choice. They do not establish nationwide coverage.",
    routingLimit: "This uncertainty is local to routing; it does not invalidate unrelated reliable guidance in the plan.",
    noDestinations: "No trusted destination was returned. Check with the responsible authority rather than assuming an office is suitable.",
    availability: "Service availability at this destination",
    available: "Available according to the returned routing",
    availabilityUnknown: "Unknown at this destination — check directly before visiting",
    effectiveFrom: "Destination information effective from",
    effectiveTo: "Destination information effective through",
    pointId: "Service point reference",
    pointVersionId: "Service point version reference",
    associationId: "Procedure association reference",
    manualSources: "Sources for manual verification",
    manualSourceNotice: "These are preserved research references and may reflect historical information. Use them for manual verification, not as confirmation of current destination details or jurisdiction.",
    noManualSources: "No manual-verification sources were returned.",
    evidence: "Sources and reference details",
    freshness: "Verification state",
    freshnessStates: {
      current: "Current for this evaluation",
      needs_reverification: "Needs re-verification",
      stale: "Stale — not current confirmation",
      disputed: "Disputed",
      unknown: "Unknown",
    },
    verifiedOn: "Last verified",
    reverifyOn: "Re-verify on",
    noSources: "No sources were attached to this item in the plan.",
    productSources: "This is a Bardi safety note, not an externally sourced administrative claim.",
    sourceClassification: "Source classification",
    sourceClasses: { official: "Official source", field_report: "Field report", secondary: "Secondary source" },
    retrievedOn: "Retrieved on",
    authority: "Source authority reference",
    sourceId: "Source reference",
    locator: "Source link or location",
    external: "opens in a new tab",
  },
} as const;

type Copy = (typeof copy)[Locale];
type Reference = { label: string; value: ReactNode };
type Fee = Plan["fees"][number];
type Anchor = (section: string, id?: string) => string;

// Presentation labels for the public codes used by the production importers.
// Unrecognized future codes remain verbatim; no phase or fee meaning is inferred.
function publicCodeLabel(code: string, labels: Record<string, string>): string {
  return Object.hasOwn(labels, code) ? labels[code] : code;
}

function CalendarDate({ value, t }: { value: string | null; t: Copy }) {
  // Administrative dates are calendar strings, never timezone-shifted timestamps.
  return value === null ? t.notProvided : <time dateTime={value} dir="ltr">{value}</time>;
}

function Metadata({ fields }: { fields: Reference[] }) {
  if (fields.length === 0) return null;
  return <dl className="plan-meta">{fields.map(({ label, value }) => (
    <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
  ))}</dl>;
}

function Disclosure({ summary, children }: { summary: string; children: ReactNode }) {
  return <>
    <details className="plan-disclosure plan-screen-only">
      <summary>{summary}</summary>
      <div className="plan-disclosure-body">{children}</div>
    </details>
    {/* Closed native details do not print consistently across engines. Keep a
        non-collapsible print copy, with no IDs or interactive disclosure. */}
    <div className="plan-print-only">
      <p><strong>{summary}</strong></p>
      {children}
    </div>
  </>;
}

function safeExternalLocator(locator: string): boolean {
  try {
    // Do not resolve relative locators against the app, or enable other schemes.
    const url = new URL(locator);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

function SourceList({ sources, t, product = false }: { sources: Source[]; t: Copy; product?: boolean }) {
  if (sources.length === 0) return <p>{product ? t.productSources : t.noSources}</p>;
  return <ul className="plan-sources">{sources.map((source) => (
    <li key={source.id}>
      <p className="plan-authored"><strong>{source.title}</strong></p>
      <Metadata fields={[
        { label: t.sourceClassification, value: t.sourceClasses[source.classification] },
        { label: t.retrievedOn, value: <CalendarDate value={source.retrieved_on} t={t} /> },
        { label: t.authority, value: <bdi>{source.authority_id}</bdi> },
        { label: t.sourceId, value: <bdi>{source.id}</bdi> },
        { label: t.locator, value: safeExternalLocator(source.locator)
          ? <a href={source.locator} target="_blank" rel="noopener noreferrer"><bdi>{source.locator}</bdi>{" "}<span className="plan-small">({t.external})</span></a>
          : <bdi>{source.locator}</bdi> },
      ]} />
    </li>
  ))}</ul>;
}

function Evidence({ sources, freshness, references = [], t, product = false }: {
  sources: Source[];
  freshness?: Freshness;
  references?: Reference[];
  t: Copy;
  product?: boolean;
}) {
  return <div className="plan-evidence">
    {freshness && <p className="plan-freshness">{t.freshness}: <strong>{t.freshnessStates[freshness.state]}</strong></p>}
    <Disclosure summary={t.evidence}>
      <Metadata fields={[
        ...references,
        ...(freshness ? [
          { label: t.verifiedOn, value: <CalendarDate value={freshness.verified_on} t={t} /> },
          { label: t.reverifyOn, value: <CalendarDate value={freshness.reverify_on} t={t} /> },
        ] : []),
      ]} />
      <SourceList sources={sources} t={t} product={product} />
    </Disclosure>
  </div>;
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return <section className="plan-section" aria-labelledby={id}>
    <h2 id={id} tabIndex={-1}>{title}</h2>
    {children}
  </section>;
}

function ClaimLinks({ ids, claims, section, anchor, t }: {
  ids: string[];
  claims: { id: string; text: string }[];
  section: string;
  anchor: Anchor;
  t: Copy;
}) {
  if (ids.length === 0) return <p className="plan-small">{t.noMappedClaims}</p>;
  return <ul className="plan-linked-items">{ids.map((id) => {
    const claim = claims.find((item) => item.id === id);
    return <li key={id}>
      {claim ? <a href={`#${encodeURIComponent(anchor(section, id))}`}>{claim.text}</a> : <span>{t.unavailableClaim}</span>}
      {" "}<span className="plan-small">({t.reference}: <bdi>{id}</bdi>)</span>
    </li>;
  })}</ul>;
}

function RelatedBases({ bases, anchor, t }: { bases: Plan["eligibility_bases"]; anchor: Anchor; t: Copy }) {
  return <div className="plan-related">
    <p className="plan-small">{t.relatedBases}</p>
    {bases.length > 0
      ? <ul className="plan-linked-items">{bases.map((basis) => <li key={basis.id}><a href={`#${encodeURIComponent(anchor("basis", basis.id))}`}>{basis.text}</a></li>)}</ul>
      : <p className="plan-small">{t.missingBasis}</p>}
  </div>;
}

function FeeValue({ fee, locale, t }: { fee: Fee; locale: Locale; t: Copy }) {
  const number = new Intl.NumberFormat(locale);
  // Explicit uncertainty always wins, even if a payload retains an old amount.
  // Do not reconstruct historical values: this contract has no monetary effective dates.
  const mayShowValue = !fee.current_value_unknown && fee.freshness.state === "current";
  if (mayShowValue && fee.value_state === "known" && fee.amount !== null) {
    return <p className="plan-money">{t.amount}: <strong><bdi>{number.format(fee.amount)} {fee.currency}</bdi></strong></p>;
  }
  if (mayShowValue && fee.value_state === "range" && fee.minimum_amount !== null && fee.maximum_amount !== null) {
    return <p className="plan-money">{t.amountRange}: <strong><bdi>{number.format(fee.minimum_amount)}</bdi> {t.rangeTo} <bdi>{number.format(fee.maximum_amount)} {fee.currency}</bdi></strong></p>;
  }
  return <>
    <p className="plan-state">{t.currentAmountUnknown}</p>
    <p className="plan-small">{t.feeProvenance}</p>
  </>;
}

export function PlanView({ plan, locale, evaluationDate }: { plan: Plan; locale: Locale; evaluationDate: string }) {
  const t = copy[locale];
  const instanceId = useId();
  const anchor: Anchor = (section, id) => `${instanceId}-plan-${section}${id === undefined ? "" : `-${encodeURIComponent(id)}`}`;
  const number = new Intl.NumberFormat(locale);
  const sections = ["warnings", "dependencies", "checklist", "steps", "fees", "bases", "routing"] as const;
  const hasLocalLimits = plan.inconclusive_sections.length > 0 || plan.inconclusive_basis_ids.length > 0 || plan.routing.status !== "resolved";

  return <article className="plan-view" lang={locale} dir={locale === "ar" ? "rtl" : "ltr"} aria-label={t.plan}>
    <header>
      <p className="plan-title plan-authored">{plan.title}</p>
      <p className="plan-small">{t.evaluationDate}: <CalendarDate value={evaluationDate} t={t} /></p>
      <Disclosure summary={t.identity}>
        <Metadata fields={[
          { label: t.serviceId, value: <bdi>{plan.service_id}</bdi> },
          { label: t.procedureId, value: <bdi>{plan.procedure_id}</bdi> },
          { label: t.versionId, value: <bdi>{plan.procedure_version_id}</bdi> },
          { label: t.evaluationDate, value: <CalendarDate value={evaluationDate} t={t} /> },
        ]} />
      </Disclosure>
      <div className="plan-reminder" role="note">
        <p><strong>{t.reminderTitle}</strong></p>
        <p>{t.reminder}</p>
      </div>
      {hasLocalLimits && <p className="plan-state">{t.localLimits}</p>}
    </header>

    <nav className="plan-index" aria-labelledby={anchor("index")}>
      <h2 id={anchor("index")}>{t.index}</h2>
      <ul>{sections.map((section) => <li key={section}><a href={`#${encodeURIComponent(anchor(section))}`}>{t[section]}</a></li>)}</ul>
    </nav>

    <Section id={anchor("warnings")} title={t.warnings}>
      {plan.warnings.length === 0 ? <p>{t.noWarnings}</p> : <ul className="plan-items plan-warnings" role="list">{plan.warnings.map((warning) => (
        <li key={warning.id} aria-labelledby={anchor("warning", warning.id)}>
          <p className={`plan-state plan-warning-${warning.severity}`}>{t.severity[warning.severity]} · {t.warningKind[warning.kind]} · {t.warningRole[warning.role]}</p>
          <p id={anchor("warning", warning.id)} className="plan-authored">{warning.text}</p>
          <Evidence sources={warning.sources} freshness={warning.freshness} product={warning.kind === "product"} t={t} references={[{ label: t.reference, value: <bdi>{warning.id}</bdi> }]} />
        </li>
      ))}</ul>}
    </Section>

    <Section id={anchor("dependencies")} title={t.dependencies}>
      <p>{t.dependencyIntro}</p>
      {plan.dependencies.length === 0 ? <p>{t.noDependencies}</p> : <ul className="plan-items" role="list">{plan.dependencies.map((dependency) => (
        <li key={dependency.id} aria-labelledby={anchor("dependency", dependency.id)}>
          <p className="plan-state">{t.dependencyStatus[dependency.status]}</p>
          <p id={anchor("dependency", dependency.id)} className="plan-authored">{dependency.text}</p>
          <Metadata fields={[
            { label: t.relation, value: t.blockingPrerequisite },
            { label: t.target, value: <span className="plan-authored">{dependency.target_procedure}</span> },
          ]} />
          <Evidence sources={dependency.sources} freshness={dependency.freshness} t={t} references={[
            { label: t.reference, value: <bdi>{dependency.id}</bdi> },
            { label: t.targetId, value: <bdi>{dependency.target_procedure_id}</bdi> },
            { label: t.targetVersion, value: dependency.target_procedure_version_id === null ? t.notProvided : <bdi>{dependency.target_procedure_version_id}</bdi> },
          ]} />
        </li>
      ))}</ul>}
    </Section>

    <Section id={anchor("checklist")} title={t.checklist}>
      {plan.inconclusive_sections.includes("checklist_items") && <p className="plan-state">{t.checklistLimit}</p>}
      {plan.checklist_items.length === 0 && <p>{t.noChecklist}</p>}
      {(["official_requirement", "practical_preparation"] as const).map((classification) => {
        const items = plan.checklist_items.filter((item) => item.classification === classification);
        if (items.length === 0) return null;
        return <div key={classification} className="plan-checklist-group">
          <h3>{classification === "official_requirement" ? t.official : t.practical}</h3>
          <ul className="plan-items" role="list">{items.map((item) => (
            <li key={item.id} aria-labelledby={anchor("checklist-item", item.id)}>
              <p id={anchor("checklist-item", item.id)} tabIndex={-1} className="plan-authored plan-item-title">{item.text}</p>
              <p className="plan-small">{item.classification_label}</p>
              <dl className="plan-quantities">
                <div><dt>{t.quantity}</dt><dd>{number.format(item.quantity)}</dd></div>
                <div><dt>{t.originals}</dt><dd>{number.format(item.original_quantity)}</dd></div>
                <div><dt>{t.copies}</dt><dd>{number.format(item.copy_quantity)}</dd></div>
              </dl>
              <p className="plan-small">{t.scope}: {item.scope === "procedure" ? t.procedureScope : t.basisScope}</p>
              {item.scope === "eligibility_basis" && <RelatedBases bases={plan.eligibility_bases.filter((basis) => basis.checklist_item_ids.includes(item.id))} anchor={anchor} t={t} />}
              <Evidence sources={item.sources} freshness={item.freshness} t={t} references={[
                { label: t.reference, value: <bdi>{item.id}</bdi> },
                { label: t.documentType, value: item.document_type_id === null ? t.notProvided : <bdi>{item.document_type_id}</bdi> },
              ]} />
            </li>
          ))}</ul>
        </div>;
      })}
    </Section>

    <Section id={anchor("steps")} title={t.steps}>
      {plan.inconclusive_sections.includes("steps") && <p className="plan-state">{t.stepLimit}</p>}
      {plan.steps.length === 0 ? <p>{t.noSteps}</p> : <ol className="plan-steps">{plan.steps.map((step) => {
        const related = plan.eligibility_bases.filter((basis) => basis.step_ids.includes(step.id));
        return <li key={step.id} aria-labelledby={anchor("step", step.id)}>
          <p id={anchor("step", step.id)} tabIndex={-1} className="plan-authored plan-item-title">{step.text}</p>
          <p className="plan-small">{t.phase}: <bdi>{publicCodeLabel(step.phase, t.phases)}</bdi></p>
          {related.length > 0 && <RelatedBases bases={related} anchor={anchor} t={t} />}
          <Evidence sources={step.sources} freshness={step.freshness} t={t} references={[
            { label: t.reference, value: <bdi>{step.id}</bdi> },
            { label: t.phaseCode, value: <bdi>{step.phase}</bdi> },
          ]} />
        </li>;
      })}</ol>}
    </Section>

    <Section id={anchor("fees")} title={t.fees}>
      <p>{t.feeIntro}</p>
      {plan.fees.length === 0 ? <p>{t.noFees}</p> : <ul className="plan-items" role="list">{plan.fees.map((fee) => (
        <li key={fee.id} aria-labelledby={anchor("fee", fee.id)}>
          <p id={anchor("fee", fee.id)} className="plan-authored plan-item-title">{fee.text}</p>
          <FeeValue fee={fee} locale={locale} t={t} />
          <Metadata fields={[
            { label: t.feeType, value: <bdi>{publicCodeLabel(fee.fee_type, t.feeTypes)}</bdi> },
            { label: t.currency, value: <bdi>{fee.currency}</bdi> },
            { label: t.feeState, value: t.feeStates[fee.value_state] },
          ]} />
          <Evidence sources={fee.sources} freshness={fee.freshness} t={t} references={[
            { label: t.reference, value: <bdi>{fee.id}</bdi> },
            { label: t.feeTypeCode, value: <bdi>{fee.fee_type}</bdi> },
          ]} />
        </li>
      ))}</ul>}
    </Section>

    <Section id={anchor("bases")} title={t.bases}>
      <p>{t.basisIntro}</p>
      {plan.eligibility_bases.length === 0 && plan.inconclusive_basis_ids.length === 0 && <p>{t.noBases}</p>}
      {plan.eligibility_bases.length > 0 && <ul className="plan-items plan-bases" role="list">{plan.eligibility_bases.map((basis) => {
        const inconclusive = plan.inconclusive_basis_ids.includes(basis.id) || basis.freshness.state !== "current";
        return <li key={basis.id} aria-labelledby={anchor("basis", basis.id)}>
          <h3 id={anchor("basis", basis.id)} tabIndex={-1} className="plan-authored">{basis.text}</h3>
          <p className="plan-state">{inconclusive ? t.candidateBasis : t.matchedBasis}</p>
          {inconclusive && <p>{t.candidateDetail}</p>}
          <p><strong>{t.basisChecklist}</strong></p>
          <ClaimLinks ids={basis.checklist_item_ids} claims={plan.checklist_items} section="checklist-item" anchor={anchor} t={t} />
          <p><strong>{t.basisSteps}</strong></p>
          <ClaimLinks ids={basis.step_ids} claims={plan.steps} section="step" anchor={anchor} t={t} />
          <Evidence sources={basis.sources} freshness={basis.freshness} t={t} references={[{ label: t.reference, value: <bdi>{basis.id}</bdi> }]} />
        </li>;
      })}</ul>}
      {plan.inconclusive_basis_ids.length > 0 && <div className="plan-unresolved-bases">
        <h3>{t.inconclusiveBases}</h3>
        <p>{t.inconclusiveBasisIntro}</p>
        <ul>{plan.inconclusive_basis_ids.map((id) => {
          const basis = plan.eligibility_bases.find((item) => item.id === id);
          return <li key={id}>{basis && <><a href={`#${encodeURIComponent(anchor("basis", id))}`}>{basis.text}</a>{" "}</>}<bdi>{id}</bdi></li>;
        })}</ul>
      </div>}
    </Section>

    <Section id={anchor("routing")} title={t.routing}>
      <p className="plan-state">{t.routingStatus[plan.routing.status]}</p>
      <p>{t.routingIntro}</p>
      {plan.routing.status !== "resolved" && <p className="plan-state">{t.routingLimit}</p>}
      {plan.routing.destinations.length === 0 ? <p>{t.noDestinations}</p> : <ul className="plan-items plan-destinations" role="list">{plan.routing.destinations.map((destination) => (
        <li key={`${destination.service_point_id}/${destination.service_point_version_id}/${destination.association_id}`}>
          <h3 className="plan-authored">{destination.name}</h3>
          <p className="plan-authored">{destination.address}</p>
          <p className={destination.availability === "unknown" ? "plan-state" : undefined}>{t.availability}: {destination.availability === "available" ? t.available : t.availabilityUnknown}</p>
          <Metadata fields={[
            { label: t.effectiveFrom, value: <CalendarDate value={destination.effective_from} t={t} /> },
            { label: t.effectiveTo, value: <CalendarDate value={destination.effective_to} t={t} /> },
          ]} />
          <Evidence sources={destination.sources} t={t} references={[
            { label: t.pointId, value: <bdi>{destination.service_point_id}</bdi> },
            { label: t.pointVersionId, value: <bdi>{destination.service_point_version_id}</bdi> },
            { label: t.associationId, value: <bdi>{destination.association_id}</bdi> },
          ]} />
        </li>
      ))}</ul>}
      <div className="plan-manual-sources">
        <h3>{t.manualSources}</h3>
        {plan.routing.verification_sources.length === 0 ? <p>{t.noManualSources}</p> : <>
          <p className="plan-state">{t.manualSourceNotice}</p>
          <Evidence sources={plan.routing.verification_sources} t={t} />
        </>}
      </div>
    </Section>
  </article>;
}
