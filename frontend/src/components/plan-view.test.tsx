import { readFileSync } from "node:fs";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { planSchema, type Freshness, type Locale, type Plan } from "@/api/contract";
import { createPartialPlanFixture, createPlanFixture, createPlanSources, planEvaluationDate } from "../../tests/plan-fixture";
import { PlanView } from "./plan-view";

const labels = {
  ar: {
    article: "خطة التحضير",
    index: "في الخطة دي",
    sections: ["خلي بالك", "إجراءات لازم تسبق ده", "الورق والتحضير", "تمشي إزاي", "الرسوم", "أسس الاستحقاق", "تروح فين"],
    identity: "عن الخطة دي",
    evidence: "المصادر وتفاصيل المرجع",
    quantities: ["العدد", "الأصول", "الصور"],
    amount: "المبلغ حسب التقييم",
    range: "النطاق حسب التقييم",
    unknownMoney: "القيمة الحالية مش معروفة — اتأكد منها قبل الدفع.",
    feeStates: { known: "قيمة محددة", range: "نطاق قيم", unknown: "غير معروفة", unverified: "غير متحقق منها" },
    candidate: "أساس محتمل غير محسوم — مش تأكيد للاستحقاق",
    matched: "أساس مطابق حسب التقييم، مش قرار من الجهة المختصة",
    basisIntro: "دي أسس استحقاق بديلة، من غير ترتيب أفضلية أو ترشيح. ظهور أساس هنا مش قرار رسمي بالاستحقاق.",
    statuses: ["المتطلب السابق متحقق حسب التقييم", "لازم تخلص المتطلب السابق قبل ما تكمل", "الإجراء السابق مش مدعوم هنا؛ بردي مش هيقدر يطلع خطته", "حالة المتطلب السابق مش محسومة؛ راجعها قبل ما تكمل"],
    resolved: "جهات التقديم اتحسمت للخطة دي",
    partial: "في جهات معروفة، وجزء من التوجيه لسه مش محسوم",
    unresolved: "جهة التقديم لسه مش محسومة",
    localRouting: "عدم اليقين هنا يخص جهة التقديم بس؛ ما يلغيش باقي المعلومات الموثوقة في الخطة.",
    localAvailability: "مش معروفة في الجهة دي — اتأكد منها مباشرة قبل ما تروح",
    manual: "مصادر للمراجعة اليدوية",
    manualNotice: "دي مراجع محفوظة من البحث، وممكن تعكس معلومات تاريخية. استخدمها للمراجعة اليدوية؛ مش تأكيد إن بيانات الجهة أو اختصاصها ساريين دلوقتي.",
    reminder: "طلّع الخطة من جديد قبل ما تتصرف على أساسها مباشرة.",
    checklistLimit: "قائمة الورق مش محسومة بالكامل.",
    stepLimit: "الخطوات مش محسومة بالكامل.",
    sourceClasses: ["مصدر رسمي", "تقرير ميداني", "مصدر ثانوي"],
    freshness: ["سارية حسب التقييم", "محتاجة مراجعة جديدة", "قديمة — مش تأكيد حالي", "محل خلاف", "غير معروفة"],
    empty: [
      "الخطة ما رجّعتش تنبيهات إضافية.",
      "الخطة ما رجّعتش إجراءات سابقة.",
      "الخطة ما رجّعتش بنود تحضير.",
      "الخطة ما رجّعتش خطوات.",
      "الخطة ما رجّعتش معلومات عن الرسوم. ده مش معناه إن الإجراء مجاني.",
      "الخطة ما رجّعتش أسس استحقاق. ده مش حكم بالقبول أو الرفض.",
      "الخطة ما رجّعتش جهة تقديم موثوقة.",
    ],
  },
  en: {
    article: "Preparation plan",
    index: "In this plan",
    sections: ["Things to keep in mind", "Prerequisites", "Documents and preparation", "What to do", "Fees", "Eligibility bases", "Where to go"],
    identity: "About this plan",
    evidence: "Sources and reference details",
    quantities: ["Quantity", "Originals", "Copies"],
    amount: "Amount for this evaluation",
    range: "Range for this evaluation",
    unknownMoney: "Current amount unknown — check before paying.",
    feeStates: { known: "Specified amount", range: "Range", unknown: "Unknown", unverified: "Unverified" },
    candidate: "Inconclusive candidate — not confirmation of eligibility",
    matched: "Matched for this evaluation, not an authority’s decision",
    basisIntro: "These are alternative eligibility bases, without ranking or recommendation. A basis appearing here is not an official eligibility decision.",
    statuses: ["Prerequisite satisfied for this evaluation", "Blocking — complete this prerequisite before proceeding", "Prerequisite not supported here — Bardi cannot provide its plan", "Prerequisite unresolved — check before proceeding"],
    resolved: "Routing resolved for this plan",
    partial: "Some destinations resolved; other routing is still uncertain",
    unresolved: "Destination unresolved",
    localRouting: "This uncertainty is local to routing; it does not invalidate unrelated reliable guidance in the plan.",
    localAvailability: "Unknown at this destination — check directly before visiting",
    manual: "Sources for manual verification",
    manualNotice: "These are preserved research references and may reflect historical information. Use them for manual verification, not as confirmation of current destination details or jurisdiction.",
    reminder: "Regenerate this plan immediately before acting on it.",
    checklistLimit: "The document list is not fully resolved.",
    stepLimit: "The steps are not fully resolved.",
    sourceClasses: ["Official source", "Field report", "Secondary source"],
    freshness: ["Current for this evaluation", "Needs re-verification", "Stale — not current confirmation", "Disputed", "Unknown"],
    empty: [
      "No additional warnings were returned.",
      "No prerequisites were returned.",
      "No preparation items were returned.",
      "No steps were returned.",
      "No fee information was returned. This does not mean the procedure is free.",
      "No eligibility bases were returned. This is not a decision to accept or reject eligibility.",
      "No trusted destination was returned.",
    ],
  },
} as const;

function show(plan: Plan, locale: Locale) {
  return render(<PlanView plan={plan} locale={locale} evaluationDate={planEvaluationDate} />);
}

function region(name: string) {
  return screen.getByRole("region", { name });
}

function itemIn(section: HTMLElement, text: string) {
  return within(section).getByRole("listitem", {
    name: (name) => name.replace(/\s+/g, " ").trim() === text.replace(/\s+/g, " ").trim(),
  });
}

function disclosureIn(item: HTMLElement) {
  const disclosure = item.querySelector("details");
  if (!disclosure) throw new Error("Expected a native source disclosure");
  return disclosure;
}

function linkedElement(link: HTMLAnchorElement) {
  return document.getElementById(decodeURIComponent(link.hash.slice(1)));
}

describe.each(["ar", "en"] as const)("PlanView (%s)", (locale) => {
  const t = labels[locale];
  const number = new Intl.NumberFormat(locale);

  it("has typed complete and partial fixtures conforming to the exact public schema", () => {
    expect(planSchema.parse(createPlanFixture(locale))).toEqual(createPlanFixture(locale));
    expect(planSchema.parse(createPartialPlanFixture(locale))).toEqual(createPartialPlanFixture(locale));
  });

  it("renders every indexed section below the parent's h1 and preserves authored text and order", () => {
    const plan = createPlanFixture(locale);
    const { container } = show(plan, locale);
    const article = screen.getByRole("article", { name: t.article });
    expect(article).toHaveAttribute("lang", locale);
    expect(article).toHaveAttribute("dir", locale === "ar" ? "rtl" : "ltr");
    expect(within(article).queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
    expect(within(article).getAllByRole("heading", { level: 2 }).map((node) => node.textContent)).toEqual([t.index, ...t.sections]);
    expect(container.querySelector(".plan-title")?.textContent).toBe(plan.title);

    const nav = screen.getByRole("navigation", { name: t.index });
    const links = within(nav).getAllByRole<HTMLAnchorElement>("link");
    expect(links.map((link) => link.textContent)).toEqual(t.sections);
    for (const link of links) expect(linkedElement(link)?.tagName).toBe("H2");

    for (const [sectionName, rows] of [
      [t.sections[0], plan.warnings], [t.sections[1], plan.dependencies],
      [t.sections[2], plan.checklist_items], [t.sections[3], plan.steps],
      [t.sections[4], plan.fees], [t.sections[5], plan.eligibility_bases],
    ] as const) {
      for (const row of rows) {
        const node = itemIn(region(sectionName), row.text);
        expect(node.querySelector(":scope > .plan-authored")?.textContent).toBe(row.text);
      }
    }
    const steps = region(t.sections[3]).querySelector("ol");
    expect(steps).not.toBeNull();
    expect(Array.from(steps!.children).map((li) => li.querySelector(".plan-authored")?.textContent)).toEqual(plan.steps.map((step) => step.text));
    for (const step of plan.steps) expect(itemIn(region(t.sections[3]), step.text)).toHaveTextContent(step.phase);
  });

  it("keeps official requirements separate from preparation and renders all quantities, including zero", () => {
    const plan = createPlanFixture(locale);
    show(plan, locale);
    const checklist = region(t.sections[2]);
    expect(within(checklist).getAllByRole("heading", { level: 3 })).toHaveLength(2);
    for (const item of plan.checklist_items) {
      const row = itemIn(checklist, item.text);
      expect(within(row).getByText(item.classification_label)).toBeInTheDocument();
      [item.quantity, item.original_quantity, item.copy_quantity].forEach((value, index) => {
        const dt = within(row).getByText(t.quantities[index], { selector: "dt" });
        expect(dt.nextElementSibling?.textContent).toBe(number.format(value));
      });
      const evidence = disclosureIn(row);
      expect(evidence).toHaveTextContent(item.id);
      if (item.document_type_id) expect(evidence).toHaveTextContent(item.document_type_id);
    }
    expect(itemIn(checklist, plan.checklist_items[0].text)).toHaveTextContent(locale === "ar" ? "للإجراء كله" : "Whole procedure");
    const basisRow = itemIn(checklist, plan.checklist_items[1].text);
    expect(basisRow).toHaveTextContent(locale === "ar" ? "مرتبط بأساس استحقاق" : "Linked to an eligibility basis");
    expect(basisRow.querySelectorAll('a[href^="#"]')).toHaveLength(2);
  });

  it("shows known zero, known positive and range fees without inventing a total", () => {
    const plan = createPlanFixture(locale);
    show(plan, locale);
    const fees = region(t.sections[4]);
    const zero = itemIn(fees, plan.fees[0].text);
    expect(zero.querySelector(".plan-money")).toHaveTextContent(`${t.amount}: ${number.format(0)} EGP`);
    expect(within(zero).queryByText(t.unknownMoney)).not.toBeInTheDocument();
    expect(itemIn(fees, plan.fees[1].text).querySelector(".plan-money")).toHaveTextContent(`${number.format(120)} EGP`);
    const range = itemIn(fees, plan.fees[2].text);
    expect(range.querySelector(".plan-money")).toHaveTextContent(t.range);
    expect(range.querySelector(".plan-money")).toHaveTextContent(number.format(125));
    expect(range.querySelector(".plan-money")).toHaveTextContent(`${number.format(175)} EGP`);
    expect(fees.querySelectorAll(".plan-money")).toHaveLength(3);
    for (const fee of plan.fees) {
      const row = itemIn(fees, fee.text);
      expect(row).toHaveTextContent(fee.currency);
      expect(row).toHaveTextContent(fee.fee_type);
      expect(row.querySelector(":scope > .plan-meta")).toHaveTextContent(t.feeStates[fee.value_state]);
      expect(disclosureIn(row)).toHaveTextContent(fee.id);
      if (fee.current_value_unknown) {
        expect(within(row).getByText(t.unknownMoney)).toBeInTheDocument();
        expect(row.querySelector(".plan-money")).toBeNull();
      }
    }
  });

  it.each([
    { value_state: "known", current_value_unknown: true },
    { value_state: "range", current_value_unknown: true },
    { value_state: "unknown", current_value_unknown: true },
    { value_state: "unknown", current_value_unknown: false },
    { value_state: "unverified", current_value_unknown: true },
    { value_state: "unverified", current_value_unknown: false },
  ] as const)("withholds retained monetary fields for $value_state / unknown=$current_value_unknown", (state) => {
    const plan = createPlanFixture(locale);
    const fee = { ...plan.fees[0], ...state, amount: 876543, minimum_amount: 654321, maximum_amount: 987654 };
    plan.fees = [fee];
    show(plan, locale);
    const row = itemIn(region(t.sections[4]), fee.text);
    expect(within(row).getByText(t.unknownMoney)).toBeInTheDocument();
    expect(row.querySelector(".plan-money")).toBeNull();
    for (const amount of [876543, 654321, 987654]) {
      expect(row).not.toHaveTextContent(number.format(amount));
      expect(row).not.toHaveTextContent(String(amount));
    }
  });

  it.each(["needs_reverification", "stale", "disputed", "unknown"] as const)("does not promote %s money even if a retained value is marked known", (state) => {
    const plan = createPlanFixture(locale);
    plan.fees = [{ ...plan.fees[0], amount: 876543, freshness: { ...plan.fees[0].freshness, state } }];
    show(plan, locale);
    const row = itemIn(region(t.sections[4]), plan.fees[0].text);
    expect(row).toHaveTextContent(t.unknownMoney);
    expect(row).not.toHaveTextContent(number.format(876543));
  });

  it("keeps bases non-ranked, explains candidates and resolves claim-ID mappings both ways", () => {
    const plan = createPartialPlanFixture(locale);
    show(plan, locale);
    const bases = region(t.sections[5]);
    expect(within(bases).getByText(t.basisIntro)).toBeInTheDocument();
    const basisList = bases.querySelector(".plan-bases");
    expect(basisList?.tagName).toBe("UL");
    expect(Array.from(basisList!.children).map((li) => li.querySelector("h3")?.textContent)).toEqual(plan.eligibility_bases.map((basis) => basis.text));
    expect(within(bases).queryByRole("radio")).not.toBeInTheDocument();
    for (const basis of plan.eligibility_bases) {
      const row = itemIn(bases, basis.text);
      expect(row).toHaveTextContent(basis.id);
      expect(row).toHaveTextContent(basis.id === "demo.basis.candidate" ? t.candidate : t.matched);
      const links = row.querySelectorAll<HTMLAnchorElement>('a[href^="#"]');
      expect(links).toHaveLength(basis.checklist_item_ids.length + basis.step_ids.length);
      for (const link of links) expect(linkedElement(link)?.textContent).toBe(link.textContent);
      for (const id of [...basis.checklist_item_ids, ...basis.step_ids]) expect(row).toHaveTextContent(id);
    }
    const candidate = itemIn(bases, plan.eligibility_bases[2].text);
    expect(within(candidate).queryByText(t.matched)).not.toBeInTheDocument();
    const idOnly = within(bases).getByText("demo.basis.id-only");
    expect(idOnly.closest("a")).toBeNull();
    expect(idOnly.closest(".plan-unresolved-bases")).not.toBeNull();

    const mappedDocument = itemIn(region(t.sections[2]), plan.checklist_items[1].text);
    for (const link of mappedDocument.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) {
      expect(linkedElement(link)?.textContent).toBe(link.textContent);
    }
  });

  it("presents every direct dependency status, target and version without recursively planning", () => {
    const plan = createPlanFixture(locale);
    show(plan, locale);
    const prerequisites = region(t.sections[1]);
    plan.dependencies.forEach((dependency, index) => {
      const row = itemIn(prerequisites, dependency.text);
      expect(row).toHaveTextContent(t.statuses[index]);
      expect(row).toHaveTextContent(dependency.target_procedure);
      expect(disclosureIn(row)).toHaveTextContent(dependency.target_procedure_id);
      if (dependency.target_procedure_version_id) expect(disclosureIn(row)).toHaveTextContent(dependency.target_procedure_version_id);
      expect(disclosureIn(row)).toHaveTextContent(dependency.id);
    });
    expect(prerequisites.querySelector(".plan-view")).toBeNull();
    expect(within(prerequisites).queryByRole("button")).not.toBeInTheDocument();
    expect(prerequisites.querySelector('a:not([target="_blank"])')).toBeNull();
  });

  it("keeps availability uncertainty local even with resolved routing and preserves association-distinct offices", () => {
    const plan = createPlanFixture(locale);
    show(plan, locale);
    const routing = region(t.sections[6]);
    expect(within(routing).getByText(t.resolved)).toBeInTheDocument();
    expect(routing).toHaveTextContent(t.localAvailability);
    expect(routing.querySelector(".plan-destinations")?.tagName).toBe("UL");
    const rows = routing.querySelectorAll(".plan-destinations > li");
    expect(rows).toHaveLength(3);
    plan.routing.destinations.forEach((destination, index) => {
      const row = rows[index] as HTMLElement;
      expect(row.querySelector("h3")?.textContent).toBe(destination.name);
      expect(row.querySelector("p.plan-authored")?.textContent).toBe(destination.address);
      const sources = disclosureIn(row);
      for (const id of [destination.service_point_id, destination.service_point_version_id, destination.association_id]) expect(sources).toHaveTextContent(id);
      if (destination.effective_from) expect(row.querySelector(`time[datetime="${destination.effective_from}"]`)).not.toBeNull();
      if (destination.effective_to) expect(row.querySelector(`time[datetime="${destination.effective_to}"]`)).not.toBeNull();
    });
    expect(routing).toHaveTextContent(locale === "ar" ? "مش دليل على تغطية كل مصر" : "They do not establish nationwide coverage");
  });

  it.each(["partially_resolved", "unresolved"] as const)("keeps reliable rows under %s routing and marks manual sources as provenance only", (status) => {
    const plan = createPartialPlanFixture(locale);
    plan.routing.status = status;
    if (status === "unresolved") plan.routing.destinations = [];
    show(plan, locale);
    const routing = region(t.sections[6]);
    expect(routing).toHaveTextContent(status === "unresolved" ? t.unresolved : t.partial);
    expect(routing).toHaveTextContent(t.localRouting);
    expect(within(routing).getByRole("heading", { name: t.manual })).toBeInTheDocument();
    expect(within(routing).getByText(t.manualNotice).closest("details")).toBeNull();
    expect(routing).toHaveTextContent(plan.routing.verification_sources[0].title);
    expect(routing).toHaveTextContent(plan.routing.verification_sources[0].retrieved_on);
    expect(region(t.sections[2])).toHaveTextContent(t.checklistLimit);
    expect(region(t.sections[3])).toHaveTextContent(t.stepLimit);
    expect(itemIn(region(t.sections[2]), plan.checklist_items[0].text)).toBeInTheDocument();
    expect(itemIn(region(t.sections[3]), plan.steps[0].text)).toBeInTheDocument();
    expect(itemIn(region(t.sections[4]), plan.fees[1].text)).toHaveTextContent(number.format(120));
    expect(itemIn(region(t.sections[0]), plan.warnings[0].text)).toBeInTheDocument();
    expect(itemIn(region(t.sections[5]), plan.eligibility_bases[0].text)).toHaveTextContent(t.matched);
    expect(itemIn(region(t.sections[1]), plan.dependencies[0].text)).toBeInTheDocument();
  });

  it("renders all warning severity/kind/role labels and all five freshness states and dates", async () => {
    const plan = createPlanFixture(locale);
    show(plan, locale);
    const warnings = region(t.sections[0]);
    const expected = locale === "ar"
      ? ["للعلم · تنبيه إداري · تنبيه عام", "مهم · تنبيه من بردي · حدود الإرشادات", "مهم · تنبيه من بردي · تجديد الخطة قبل التصرف"]
      : ["Information · Administrative warning · General notice", "Important · Bardi safety note · Guidance limitation", "Important · Bardi safety note · Regenerate before acting"];
    plan.warnings.forEach((warning, index) => {
      const row = itemIn(warnings, warning.text);
      expect(row).toHaveTextContent(expected[index]);
      expect(row.querySelector(".plan-authored")?.closest("details")).toBeNull();
      if (warning.kind === "product") expect(row.querySelector(".plan-sources")).toBeNull();
    });
    const states: Freshness["state"][] = ["current", "needs_reverification", "stale", "disputed", "unknown"];
    states.forEach((state, index) => {
      const fee = plan.fees.find((fee) => fee.freshness.state === state)!;
      const row = itemIn(region(t.sections[4]), fee.text);
      expect(row.querySelector(".plan-freshness")).toHaveTextContent(t.freshness[index]);
      const details = disclosureIn(row);
      for (const date of [fee.freshness.verified_on, fee.freshness.reverify_on]) {
        if (date) expect(details.querySelector(`time[datetime="${date}"]`)?.textContent).toBe(date);
      }
    });
    const user = userEvent.setup();
    const details = disclosureIn(itemIn(region(t.sections[2]), plan.checklist_items[0].text));
    expect(details).not.toHaveAttribute("open");
    await user.click(within(details).getByText(t.evidence, { selector: "summary" }));
    expect(details).toHaveAttribute("open");
    const source = plan.checklist_items[0].sources[0];
    const link = within(details).getByRole("link");
    expect(link).toHaveAttribute("href", source.locator);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAccessibleName(expect.stringContaining(locale === "ar" ? "يفتح في تبويب جديد" : "opens in a new tab"));
    for (const value of [source.id, source.authority_id, source.title, source.retrieved_on, t.sourceClasses[0]]) expect(details).toHaveTextContent(value);
    const fieldDetails = disclosureIn(itemIn(region(t.sections[2]), plan.checklist_items[3].text));
    const archiveDetails = disclosureIn(itemIn(region(t.sections[4]), plan.fees[4].text));
    expect(fieldDetails).toHaveTextContent(t.sourceClasses[1]);
    expect(archiveDetails).toHaveTextContent(t.sourceClasses[2]);
    expect(archiveDetails).toHaveTextContent(locale === "ar" ? "مش مذكور في الخطة" : "Not supplied in this plan");
  });

  it("localizes recognized public phase/fee codes and preserves unfamiliar codes without guessing", () => {
    const plan = createPlanFixture(locale);
    const phases = ["prepare-at-office", "submit", "route", "adjudicate", "future.phase", "constructor"];
    const feeTypes = ["government_fee", "optional_service_fee", "service_fee", "certificate", "future.fee", "constructor"];
    const phaseLabels = locale === "ar"
      ? ["التحضير في نقطة الخدمة", "تقديم الطلب", "تحديد جهة التقديم", "البت في الطلب", "future.phase", "constructor"]
      : ["Prepare at the service point", "Submit", "Routing", "Adjudication", "future.phase", "constructor"];
    const feeLabels = locale === "ar"
      ? ["رسم حكومي", "رسم خدمة اختيارية", "رسم خدمة", "رسم شهادة", "future.fee", "constructor"]
      : ["Government fee", "Optional service fee", "Service fee", "Certificate fee", "future.fee", "constructor"];
    const step = plan.steps[0];
    const fee = plan.fees[0];
    plan.steps = phases.map((phase, index) => ({ ...step, id: `${step.id}.${index}`, text: `${step.text} (${index})`, phase }));
    plan.fees = feeTypes.map((fee_type, index) => ({ ...fee, id: `${fee.id}.${index}`, text: `${fee.text} (${index})`, fee_type }));
    show(plan, locale);
    plan.steps.forEach((step, index) => {
      const row = itemIn(region(t.sections[3]), step.text);
      expect(row.querySelector(":scope > .plan-small")).toHaveTextContent(phaseLabels[index]);
      expect(disclosureIn(row)).toHaveTextContent(step.phase);
    });
    plan.fees.forEach((fee, index) => {
      const row = itemIn(region(t.sections[4]), fee.text);
      expect(row.querySelector(":scope > .plan-meta")).toHaveTextContent(feeLabels[index]);
      expect(disclosureIn(row)).toHaveTextContent(fee.fee_type);
    });
  });

  it("uses honest empty sections and always-visible regeneration copy, even without an API warning", () => {
    const plan = createPlanFixture(locale);
    Object.assign(plan, {
      warnings: [], dependencies: [], checklist_items: [], steps: [], fees: [], eligibility_bases: [],
      routing: { status: "unresolved", destinations: [], verification_sources: [] },
    });
    const { container } = show(plan, locale);
    t.sections.forEach((name, index) => expect(region(name)).toHaveTextContent(t.empty[index]));
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent(t.reminder);
    expect(note.closest("details")).toBeNull();
    expect(note.closest(".plan-print-only")).toBeNull();
    expect(container.querySelector("ul:empty, ol:empty, dl:empty")).toBeNull();
  });
});

it("discloses procedure identity and exact calendar dates without adding raw Facts or DTOs", async () => {
  const plan = Object.assign(createPlanFixture("en"), {
    facts: { private_key: "PRIVATE_FACT_SENTINEL" },
    applicability: { op: "eq", fact: "INTERNAL_RULE_SENTINEL" },
  });
  const { container } = render(<PlanView plan={plan} locale="en" evaluationDate="2024-02-29" />);
  const summary = screen.getByText("About this plan", { selector: "summary" });
  const identity = summary.closest("details")!;
  expect(identity).not.toHaveAttribute("open");
  await userEvent.setup().click(summary);
  for (const value of [plan.service_id, plan.procedure_id, plan.procedure_version_id]) expect(identity).toHaveTextContent(value);
  expect(identity.querySelector("time")?.dateTime).toBe("2024-02-29");
  expect(identity.querySelector("time")?.textContent).toBe("2024-02-29");
  expect(container).not.toHaveTextContent("PRIVATE_FACT_SENTINEL");
  expect(container).not.toHaveTextContent("INTERNAL_RULE_SENTINEL");
  expect(container.querySelector("pre, code, textarea")).toBeNull();
});

it("shows missing claim references without fabricating guidance, and links safely with non-ASCII IDs", () => {
  const plan = createPlanFixture("en");
  plan.checklist_items[1].id = "demo.مستند/أصل?نسخة=1%";
  plan.eligibility_bases[0].id = "demo.أساس/بديل";
  plan.eligibility_bases[0].checklist_item_ids = [plan.checklist_items[1].id, "demo.missing.claim"];
  plan.eligibility_bases[0].step_ids = ["demo.missing.step"];
  const { container } = show(plan, "en");
  const basis = itemIn(region("Eligibility bases"), plan.eligibility_bases[0].text);
  expect(within(basis).getAllByText("Item details were not returned in this plan")).toHaveLength(2);
  expect(basis).toHaveTextContent("demo.missing.claim");
  expect(basis).toHaveTextContent("demo.missing.step");
  for (const link of container.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) expect(linkedElement(link)).not.toBeNull();
});

it("treats an explicitly inconclusive ID as a candidate even when its freshness says current", () => {
  const plan = createPlanFixture("en");
  plan.inconclusive_basis_ids = [plan.eligibility_bases[0].id];
  show(plan, "en");
  const basis = itemIn(region("Eligibility bases"), plan.eligibility_bases[0].text);
  expect(basis).toHaveTextContent(labels.en.candidate);
  expect(within(basis).queryByText(labels.en.matched)).not.toBeInTheDocument();
});

it("does not manufacture an eligibility link for an unmapped basis-scoped requirement", () => {
  const plan = createPlanFixture("en");
  plan.eligibility_bases = [];
  show(plan, "en");
  const item = itemIn(region("Documents and preparation"), plan.checklist_items[1].text);
  expect(item).toHaveTextContent("The related eligibility basis was not identified in this plan.");
  expect(item.querySelector('a[href^="#"]')).toBeNull();
});

it.each([
  { value_state: "known", amount: null, minimum_amount: null, maximum_amount: null },
  { value_state: "range", amount: null, minimum_amount: null, maximum_amount: 100 },
  { value_state: "range", amount: null, minimum_amount: 0, maximum_amount: null },
] as const)("withholds incomplete $value_state monetary data", (values) => {
  const plan = createPlanFixture("en");
  plan.fees = [{ ...plan.fees[0], ...values }];
  show(plan, "en");
  expect(itemIn(region("Fees"), plan.fees[0].text)).toHaveTextContent(labels.en.unknownMoney);
  expect(region("Fees").querySelector(".plan-money")).toBeNull();
});

it("renders a zero-to-zero range rather than treating either boundary as absent", () => {
  const plan = createPlanFixture("en");
  plan.fees = [{ ...plan.fees[2], minimum_amount: 0, maximum_amount: 0 }];
  show(plan, "en");
  expect(region("Fees").querySelector(".plan-money")).toHaveTextContent("Range for this evaluation: 0 to 0 EGP");
});

it.each([
  "javascript:alert(1)", "JaVaScRiPt:alert(1)", "java\nscript:alert(1)",
  "data:text/html,<script>alert(1)</script>", "vbscript:msgbox(1)",
  "file:///etc/passwd", "ftp://example.org/file", "blob:https://example.org/id",
  "mailto:test@example.org", "//example.org/relative", "/v1/planning", "https://", "plain archive locator",
])("renders a non-http(s) or invalid locator as escaped plain text: %s", (locator) => {
  const plan = createPlanFixture("en");
  plan.checklist_items[0].sources = [{ ...plan.checklist_items[0].sources[0], locator }];
  show(plan, "en");
  const row = itemIn(region("Documents and preparation"), plan.checklist_items[0].text);
  expect(row.querySelectorAll("a")).toHaveLength(0);
  expect(row.querySelector("script, iframe")).toBeNull();
  expect(Array.from(row.querySelectorAll("bdi")).some((node) => node.textContent === locator)).toBe(true);
});

it.each(["https://example.org/path?a=1&b=2", "http://example.org/path"])("enables safe external locators in screen and print sources: %s", (locator) => {
  const plan = createPlanFixture("en");
  plan.checklist_items[0].sources = [{ ...plan.checklist_items[0].sources[0], locator }];
  show(plan, "en");
  const row = itemIn(region("Documents and preparation"), plan.checklist_items[0].text);
  const links = row.querySelectorAll("a");
  expect(links).toHaveLength(2);
  for (const link of links) {
    expect(link).toHaveAttribute("href", locator);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  }
});

it("keeps manual-verification provenance explicitly non-current even with resolved routing", () => {
  const plan = createPlanFixture("en");
  plan.routing.verification_sources = createPlanSources("en");
  show(plan, "en");
  const routing = region("Where to go");
  expect(routing).toHaveTextContent(labels.en.resolved);
  expect(routing).toHaveTextContent(labels.en.manualNotice);
});

it("provides non-collapsible, complete print evidence and visible warnings without duplicate IDs", () => {
  const plan = createPartialPlanFixture("en");
  const { container } = show(plan, "en");
  const evidence = container.querySelectorAll(".plan-evidence");
  expect(evidence.length).toBeGreaterThan(20);
  for (const group of evidence) {
    const screenDetails = group.querySelector("details.plan-screen-only")!;
    expect(screenDetails).not.toHaveAttribute("open");
    const print = group.querySelector(".plan-print-only")!;
    expect(print).not.toBeNull();
    expect(print.querySelector("details, summary")).toBeNull();
    expect(print.textContent).toBe(screenDetails.textContent);
  }
  for (const source of createPlanSources("en")) {
    const printSources = container.querySelectorAll(".plan-print-only .plan-sources > li");
    const sourceRow = Array.from(printSources).find((node) => node.textContent?.includes(source.id));
    expect(sourceRow).toBeDefined();
    for (const value of [source.title, source.locator, source.authority_id, source.retrieved_on, labels.en.sourceClasses[["official", "field_report", "secondary"].indexOf(source.classification)]]) expect(sourceRow).toHaveTextContent(value);
  }
  for (const warning of plan.warnings) {
    const row = itemIn(region("Things to keep in mind"), warning.text);
    expect(row.closest("details, .plan-screen-only, .plan-print-only")).toBeNull();
  }
  const ids = Array.from(container.querySelectorAll("[id]")).map((node) => node.id);
  expect(new Set(ids).size).toBe(ids.length);

  // This guards the print contract structurally; real pagination belongs to the
  // parent browser/print review, not jsdom's non-existent print layout engine.
  const css = readFileSync("src/components/plan-view.css", "utf8");
  const printCss = css.slice(css.indexOf("@media print"));
  expect(printCss).toMatch(/\.plan-screen-only[^{}]*\{\s*display: none !important;/);
  expect(printCss).toMatch(/\.plan-print-only\s*\{\s*display: block !important;/);
  expect(css).toContain("max-inline-size: 75ch");
  expect(css).not.toMatch(/(?:margin|padding|border)-(?:left|right)\s*:/);
});

it("keeps in-page targets distinct if two plans are mounted together", () => {
  const plan = createPlanFixture("en");
  const { container } = render(<>
    <PlanView plan={plan} locale="en" evaluationDate={planEvaluationDate} />
    <PlanView plan={plan} locale="ar" evaluationDate={planEvaluationDate} />
  </>);
  const ids = Array.from(container.querySelectorAll("[id]")).map((node) => node.id);
  expect(new Set(ids).size).toBe(ids.length);
  for (const link of container.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) expect(linkedElement(link)?.closest("article")).toBe(link.closest("article"));
});
