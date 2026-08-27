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
        "SRC-MOI-PASSPORT-REQ": Source(
            id="SRC-MOI-PASSPORT-REQ",
            authority="Egyptian Ministry of Interior — General Administration of Passports, Immigration and Nationality",
            title="Passport requirements and instructions",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-MOI-ACCELERATED": Source(
            id="SRC-MOI-ACCELERATED",
            authority="Egyptian Ministry of Interior",
            title="Urgent and premium passport service announcements",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-MOI-OFFICE-DIRECTORY": Source(
            id="SRC-MOI-OFFICE-DIRECTORY",
            authority="Egyptian Ministry of Interior",
            title="Passport office and police directory entries",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-PSM-RENEWAL-SERVICE": Source(
            id="SRC-PSM-RENEWAL-SERVICE",
            authority="Egyptian Public Services directory",
            title="Expired or page-full passport replacement service",
            retrieved_on=VERIFIED_ON,
        ),
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
        "EL-MOI-ROUTING-01": EvidenceLink(
            "EL-MOI-ROUTING-01",
            ("SRC-MOI-OFFICE-DIRECTORY", "SRC-MOI-ACCELERATED"),
        ),
        "EL-MOI-GIZA-01": EvidenceLink("EL-MOI-GIZA-01", ("SRC-MOI-OFFICE-DIRECTORY",)),
        "EL-MOI-PASSPORT-NATURE-01": EvidenceLink(
            "EL-MOI-PASSPORT-NATURE-01", ("SRC-MOI-PASSPORT-REQ",)
        ),
        "EL-MOI-VALIDITY-01": EvidenceLink("EL-MOI-VALIDITY-01", ("SRC-MOI-PASSPORT-REQ",)),
    }

    goal = GoalDefinition(
        id="get_egyptian_passport",
        text=t("الحصول على جواز سفر مصري", "Get an Egyptian passport"),
        procedure_ids=("ordinary_domestic_passport_renewal",),
    )
    procedure = ProcedureVersionDefinition(
        procedure_id="ordinary_domestic_passport_renewal",
        version_id="ordinary_domestic_passport_renewal.research-2026-08-25",
        text=t(
            "استخراج جواز سفر عادي بدل جواز سفر منتهي أو ممتلئ الصفحات داخل مصر",
            "Obtain an ordinary passport in place of an expired or page-full passport inside Egypt",
        ),
        applicability=all_of(
            eq("citizenship", "egyptian"),
            eq("application_location", "inside_egypt"),
            eq("passport_class", "ordinary"),
            one_of("existing_passport_state", ("expired", "pages_full")),
        ),
        verified_on=VERIFIED_ON,
    )

    claims = (
        ClaimDefinition(
            id="passport.requirement.national_id",
            text=t(
                "بطاقة رقم قومي سارية وبياناتها الحالية محدثة",
                "Valid National ID with current recorded data",
            ),
            classification="official_requirement",
            applicability=gte("age_years_on_evaluation_date", 15),
            evidence_link_ids=("EL-MOI-REQ-01",),
            verification_state="current",
            display_order=10,
        ),
        ClaimDefinition(
            id="passport.requirement.birth_certificate",
            text=t(
                "شهادة ميلاد مميكنة تحمل الرقم القومي",
                "Machine-readable birth certificate carrying the national number",
            ),
            classification="official_requirement",
            applicability=lt("age_years_on_evaluation_date", 15),
            evidence_link_ids=("EL-MOI-REQ-02",),
            verification_state="current",
            display_order=20,
        ),
        ClaimDefinition(
            id="passport.requirement.student_enrollment",
            text=t(
                "شهادة قيد دراسي عن العام الدراسي الحالي",
                "Enrollment certificate for the current academic year",
            ),
            classification="official_requirement",
            applicability=eq("is_student", True),
            evidence_link_ids=("EL-MOI-REQ-03",),
            verification_state="current",
            display_order=30,
        ),
        ClaimDefinition(
            id="passport.requirement.military_status",
            text=t("مستند يثبت الموقف من التجنيد", "Military-status document"),
            classification="official_requirement",
            applicability=all_of(
                eq("sex", "male"),
                gte("birth_date", date(1941, 3, 18)),
                gte("age_years_on_evaluation_date", 19),
            ),
            evidence_link_ids=("EL-MOI-REQ-04",),
            verification_state="current",
            display_order=40,
        ),
        ClaimDefinition(
            id="passport.requirement.photos",
            text=t(
                "3 صور شخصية ملونة حديثة بخلفية بيضاء مقاس 4×6",
                "Three recent colour 4×6 photos with a white background",
            ),
            classification="official_requirement",
            applicability=None,
            evidence_link_ids=("EL-MOI-REQ-05",),
            verification_state="current",
            display_order=50,
            quantity=3,
        ),
        ClaimDefinition(
            id="passport.requirement.originals_and_copy",
            text=t(
                "أصول المستندات وصورة منها للمطابقة",
                "Originals plus a copy for verification",
            ),
            classification="official_requirement",
            applicability=None,
            evidence_link_ids=("EL-MOI-REQ-06",),
            verification_state="current",
            display_order=60,
        ),
        ClaimDefinition(
            id="passport.requirement.previous_passport",
            text=t(
                "جواز السفر السابق المنتهي أو ممتلئ الصفحات",
                "Previous expired or page-full passport",
            ),
            classification="official_requirement_candidate",
            applicability=one_of("existing_passport_state", ("expired", "pages_full")),
            evidence_link_ids=("EL-PSM-SERVICE-01",),
            verification_state="needs_reverification",
            display_order=70,
        ),
    )

    steps = (
        StepDefinition(
            id="passport.step.obtain_form_29",
            text=t(
                "الحصول على نموذج 29 جوازات مميكن مجانًا",
                "Obtain machine-readable Passport Form 29 free of charge",
            ),
            phase="prepare-at-office",
            slot=10,
            applicability=None,
            evidence_link_ids=("EL-MOI-PROCESS-01",),
            verification_state="current",
        ),
        StepDefinition(
            id="passport.step.complete_form",
            text=t(
                "استيفاء بيانات الصفحة الأولى من النموذج بمعرفة صاحب الشأن",
                "Complete the first page of the form with the applicant's information",
            ),
            phase="prepare-at-office",
            slot=20,
            applicability=None,
            evidence_link_ids=("EL-MOI-PROCESS-02",),
            verification_state="current",
        ),
        StepDefinition(
            id="passport.step.submit_and_pay",
            text=t(
                "تقديم الطلب والمستندات وسداد الرسم في نقطة الخدمة المختصة",
                "Submit the application and documents and pay the applicable fee at the resolved Service Point",
            ),
            phase="submit",
            slot=30,
            applicability=None,
            evidence_link_ids=("EL-MOI-ROUTING-01", "EL-MOI-FEE-01"),
            verification_state="current",
        ),
    )

    fees = (
        FeeDefinition(
            id="passport.fee.base",
            text=t("رسم جواز السفر الأساسي", "Base passport fee"),
            amount=705,
            currency="EGP",
            applicability=None,
            evidence_link_ids=("EL-MOI-FEE-01",),
            verification_state="current",
        ),
        FeeDefinition(
            id="passport.fee.urgent_service",
            text=t("رسم إضافي للخدمة العاجلة", "Additional urgent-service fee"),
            amount=100,
            currency="EGP",
            applicability=eq("service_level", "urgent"),
            evidence_link_ids=("EL-MOI-URGENT-01",),
            verification_state="current",
        ),
        FeeDefinition(
            id="passport.fee.premium_service",
            text=t("رسم إضافي للخدمة المميزة", "Additional premium-service fee"),
            amount=500,
            currency="EGP",
            applicability=eq("service_level", "premium"),
            evidence_link_ids=("EL-MOI-PREMIUM-01",),
            verification_state="current",
        ),
    )

    service_points = (
        ServicePointDefinition(
            id="sp.giza_passport_office",
            text=t("قسم جوازات الجيزة", "Giza Passport Office"),
            address=t(
                "مبنى قسم شرطة الجيزة، شارع البحر الأعظم، الجيزة",
                "Giza Police Department building, Bahr El-Azam Street, Giza",
            ),
            applicability=all_of(
                eq("service_level", "standard"),
                one_of(
                    "residence_police_jurisdiction",
                    (
                        "giza",
                        "boulak_el_dakrour",
                        "haram",
                        "talbia",
                        "abu_el_nomros",
                        "omrania",
                    ),
                ),
            ),
            evidence_link_ids=("EL-MOI-GIZA-01", "EL-MOI-ROUTING-01"),
            verification_state="current",
        ),
    )

    warnings = (
        WarningDefinition(
            id="passport.warning.personal_document",
            text=t(
                "جواز السفر المقروء آليًا شخصي ولا تُضاف إليه الزوجة أو الأبناء.",
                "The machine-readable passport is personal; a spouse or children are not added to it.",
            ),
            severity="info",
            evidence_link_ids=("EL-MOI-PASSPORT-NATURE-01",),
        ),
        WarningDefinition(
            id="passport.warning.validity",
            text=t(
                "مدة الصلاحية القياسية المنشورة حاليًا سبع سنوات.",
                "The currently published standard validity is seven years.",
            ),
            severity="info",
            evidence_link_ids=("EL-MOI-VALIDITY-01",),
        ),
        WarningDefinition(
            id="passport.warning.regenerate",
            text=t(
                "أعد التحقق من الخطة قبل التوجه مباشرة لأن الرسوم ونقاط الخدمة والتعليمات قد تتغير.",
                "Re-check the plan immediately before acting because fees, Service Points and instructions can change.",
            ),
            severity="important",
        ),
        WarningDefinition(
            id="passport.warning.guidance_not_decision",
            text=t(
                "هذه إرشادات مبنية على مصادر منشورة وليست قرارًا ملزمًا من الجهة الحكومية.",
                "This is source-backed guidance, not a binding decision by the government authority.",
            ),
            severity="important",
        ),
    )

    unknowns = (
        UnknownDefinition(
            id="passport.turnaround.standard",
            text=t(
                "مدة إنجاز الخدمة العادية غير مثبتة حاليًا في هذه الحزمة البحثية.",
                "The standard-service turnaround is not currently established by this research fixture.",
            ),
            applicability=eq("service_level", "standard"),
        ),
    )

    return KnowledgeBundle(
        id="passport-renewal.research-2026-08-25",
        goal=goal,
        procedure=procedure,
        sources=sources,
        evidence_links=evidence_links,
        claims=claims,
        steps=steps,
        fees=fees,
        service_points=service_points,
        warnings=warnings,
        unknowns=unknowns,
    )
