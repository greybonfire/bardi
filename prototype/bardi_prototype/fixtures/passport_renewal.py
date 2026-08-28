from __future__ import annotations

from datetime import date

from ..contracts import (
    ClaimDefinition,
    EvidenceLink,
    FeeDefinition,
    GoalDefinition,
    KnowledgeBundle,
    LocalizedText,
    ProcedureVersionDefinition,
    ServicePointDefinition,
    Source,
    StepDefinition,
    UnknownDefinition,
    WarningDefinition,
)
from ..evaluator import all_of, eq, gte, lt, one_of

VERIFIED_ON = date(2026, 8, 25)


def t(ar: str, en: str) -> LocalizedText:
    return LocalizedText(ar=ar, en=en)


def load_passport_renewal_fixture() -> KnowledgeBundle:
    sources = {
        "SRC-MOI-PASSPORT-REQ": Source("SRC-MOI-PASSPORT-REQ", "Egyptian Ministry of Interior — General Administration of Passports, Immigration and Nationality", "Passport requirements and instructions", VERIFIED_ON),
        "SRC-MOI-ACCELERATED": Source("SRC-MOI-ACCELERATED", "Egyptian Ministry of Interior", "Urgent and premium passport service announcements", VERIFIED_ON),
        "SRC-MOI-OFFICE-DIRECTORY": Source("SRC-MOI-OFFICE-DIRECTORY", "Egyptian Ministry of Interior", "Passport office and police directory entries", VERIFIED_ON),
        "SRC-PSM-RENEWAL-SERVICE": Source("SRC-PSM-RENEWAL-SERVICE", "Egyptian Public Services directory", "Expired or page-full passport replacement service", VERIFIED_ON),
    }
    evidence_links = {
        "EL-MOI-REQ-01": EvidenceLink("EL-MOI-REQ-01", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-REQ-02": EvidenceLink("EL-MOI-REQ-02", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-REQ-03": EvidenceLink("EL-MOI-REQ-03", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-REQ-04": EvidenceLink("EL-MOI-REQ-04", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-REQ-05": EvidenceLink("EL-MOI-REQ-05", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-REQ-06": EvidenceLink("EL-MOI-REQ-06", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-PSM-SERVICE-01": EvidenceLink("EL-PSM-SERVICE-01", ("SRC-PSM-RENEWAL-SERVICE",)),
        "EL-MOI-PROCESS-01": EvidenceLink("EL-MOI-PROCESS-01", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-PROCESS-02": EvidenceLink("EL-MOI-PROCESS-02", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-FEE-01": EvidenceLink("EL-MOI-FEE-01", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-URGENT-01": EvidenceLink("EL-MOI-URGENT-01", ("SRC-MOI-ACCELERATED",)),
        "EL-MOI-PREMIUM-01": EvidenceLink("EL-MOI-PREMIUM-01", ("SRC-MOI-ACCELERATED",)),
        "EL-MOI-ROUTING-01": EvidenceLink("EL-MOI-ROUTING-01", ("SRC-MOI-OFFICE-DIRECTORY", "SRC-MOI-ACCELERATED")),
        "EL-MOI-GIZA-01": EvidenceLink("EL-MOI-GIZA-01", ("SRC-MOI-OFFICE-DIRECTORY",)),
        "EL-MOI-PASSPORT-NATURE-01": EvidenceLink("EL-MOI-PASSPORT-NATURE-01", ("SRC-MOI-PASSPORT-REQ",)),
        "EL-MOI-VALIDITY-01": EvidenceLink("EL-MOI-VALIDITY-01", ("SRC-MOI-PASSPORT-REQ",)),
    }

    goal = GoalDefinition("get_egyptian_passport", t("الحصول على جواز سفر مصري", "Get an Egyptian passport"), ("ordinary_domestic_passport_renewal",))
    procedure = ProcedureVersionDefinition(
        procedure_id="ordinary_domestic_passport_renewal",
        version_id="ordinary_domestic_passport_renewal.research-2026-08-25",
        text=t("استخراج جواز سفر عادي بدل جواز سفر منتهي أو ممتلئ الصفحات داخل مصر", "Obtain an ordinary passport in place of an expired or page-full passport inside Egypt"),
        applicability=all_of(eq("citizenship", "egyptian"), eq("application_location", "inside_egypt"), eq("passport_class", "ordinary"), one_of("existing_passport_state", ("expired", "pages_full"))),
        verified_on=VERIFIED_ON,
    )

    claims = (
        ClaimDefinition("passport.requirement.national_id", t("بطاقة رقم قومي سارية وبياناتها الحالية محدثة", "Valid National ID with current recorded data"), "official_requirement", gte("age_years_on_evaluation_date", 15), ("EL-MOI-REQ-01",), "current", 10, document_type_id="national_id"),
        ClaimDefinition("passport.requirement.birth_certificate", t("شهادة ميلاد مميكنة تحمل الرقم القومي", "Machine-readable birth certificate carrying the national number"), "official_requirement", lt("age_years_on_evaluation_date", 15), ("EL-MOI-REQ-02",), "current", 20, document_type_id="birth_certificate"),
        ClaimDefinition("passport.requirement.student_enrollment", t("شهادة قيد دراسي عن العام الدراسي الحالي", "Enrollment certificate for the current academic year"), "official_requirement", eq("is_student", True), ("EL-MOI-REQ-03",), "current", 30, document_type_id="student_enrollment_certificate"),
        ClaimDefinition("passport.requirement.military_status", t("مستند يثبت الموقف من التجنيد", "Military-status document"), "official_requirement", all_of(eq("sex", "male"), gte("birth_date", date(1941, 3, 18)), gte("age_years_on_evaluation_date", 19)), ("EL-MOI-REQ-04",), "current", 40, document_type_id="military_status_document"),
        ClaimDefinition("passport.requirement.photos", t("3 صور شخصية ملونة حديثة بخلفية بيضاء مقاس 4×6", "Three recent colour 4×6 photos with a white background"), "official_requirement", None, ("EL-MOI-REQ-05",), "current", 50, quantity=3, document_type_id="passport_photo"),
        ClaimDefinition("passport.requirement.originals_and_copy", t("أصول المستندات وصورة منها للمطابقة", "Originals plus a copy for verification"), "official_requirement", None, ("EL-MOI-REQ-06",), "current", 60, document_type_id="supporting_documents", original_quantity=1, copy_quantity=1),
        ClaimDefinition("passport.requirement.previous_passport", t("جواز السفر السابق المنتهي أو ممتلئ الصفحات", "Previous expired or page-full passport"), "official_requirement_candidate", one_of("existing_passport_state", ("expired", "pages_full")), ("EL-PSM-SERVICE-01",), "needs_reverification", 70, document_type_id="previous_passport"),
    )

    steps = (
        StepDefinition("passport.step.obtain_form_29", t("الحصول على نموذج 29 جوازات مميكن مجانًا", "Obtain machine-readable Passport Form 29 free of charge"), "prepare-at-office", 10, None, ("EL-MOI-PROCESS-01",), "current", phase_order=10),
        StepDefinition("passport.step.complete_form", t("استيفاء بيانات الصفحة الأولى من النموذج بمعرفة صاحب الشأن", "Complete the first page of the form with the applicant's information"), "prepare-at-office", 20, None, ("EL-MOI-PROCESS-02",), "current", phase_order=10),
        StepDefinition("passport.step.submit_and_pay", t("تقديم الطلب والمستندات وسداد الرسم في نقطة الخدمة المختصة", "Submit the application and documents and pay the applicable fee at the resolved Service Point"), "submit", 30, None, ("EL-MOI-ROUTING-01", "EL-MOI-FEE-01"), "current", phase_order=20),
    )

    fees = (
        FeeDefinition("passport.fee.base", t("رسم جواز السفر الأساسي", "Base passport fee"), 705, "EGP", None, ("EL-MOI-FEE-01",), "current", value_state="known", fee_type="base"),
        FeeDefinition("passport.fee.urgent_service", t("رسم إضافي للخدمة العاجلة", "Additional urgent-service fee"), 100, "EGP", eq("service_level", "urgent"), ("EL-MOI-URGENT-01",), "current", value_state="known", fee_type="additional_service"),
        FeeDefinition("passport.fee.premium_service", t("رسم إضافي للخدمة المميزة", "Additional premium-service fee"), 500, "EGP", eq("service_level", "premium"), ("EL-MOI-PREMIUM-01",), "current", value_state="known", fee_type="additional_service"),
    )

    service_points = (
        ServicePointDefinition(
            id="sp.giza_passport_office",
            text=t("قسم جوازات الجيزة", "Giza Passport Office"),
            address=t("مبنى قسم شرطة الجيزة، شارع البحر الأعظم، الجيزة", "Giza Police Department building, Bahr El-Azam Street, Giza"),
            applicability=all_of(eq("service_level", "standard"), one_of("residence_police_jurisdiction", ("giza", "boulak_el_dakrour", "haram", "talbia", "abu_el_nomros", "omrania"))),
            evidence_link_ids=("EL-MOI-GIZA-01", "EL-MOI-ROUTING-01"),
            verification_state="current",
        ),
    )

    warnings = (
        WarningDefinition("passport.warning.personal_document", t("جواز السفر المقروء آليًا شخصي ولا تُضاف إليه الزوجة أو الأبناء.", "The machine-readable passport is personal; a spouse or children are not added to it."), "info", ("EL-MOI-PASSPORT-NATURE-01",), kind="administrative"),
        WarningDefinition("passport.warning.validity", t("مدة الصلاحية القياسية المنشورة حاليًا سبع سنوات.", "The currently published standard validity is seven years."), "info", ("EL-MOI-VALIDITY-01",), kind="administrative"),
        WarningDefinition("passport.warning.regenerate", t("أعد التحقق من الخطة قبل التوجه مباشرة لأن الرسوم ونقاط الخدمة والتعليمات قد تتغير.", "Re-check the plan immediately before acting because fees, Service Points and instructions can change."), "important", kind="product", role="regeneration"),
        WarningDefinition("passport.warning.guidance_not_decision", t("هذه إرشادات مبنية على مصادر منشورة وليست قرارًا ملزمًا من الجهة الحكومية.", "This is source-backed guidance, not a binding decision by the government authority."), "important", kind="product", role="limitation"),
    )

    unknowns = (
        UnknownDefinition("passport.turnaround.standard", t("مدة إنجاز الخدمة العادية غير مثبتة حاليًا في هذه الحزمة البحثية.", "The standard-service turnaround is not currently established by this research fixture."), eq("service_level", "standard")),
    )

    return KnowledgeBundle("passport-renewal.research-2026-08-25", goal, procedure, sources, evidence_links, claims, steps, fees, service_points, warnings, unknowns)
