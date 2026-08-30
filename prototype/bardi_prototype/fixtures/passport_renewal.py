from __future__ import annotations

from dataclasses import replace
from datetime import date

from ..contracts import (
    ClaimDefinition,
    EvidenceLink,
    FeeDefinition,
    GoalDefinition,
    KnowledgeBundle,
    LocalizedText,
    ProcedureServicePointAssociationDefinition,
    ProcedureVersionDefinition,
    ServicePointDefinition,
    ServicePointVersionDefinition,
    Source,
    StepDefinition,
    UnknownDefinition,
    VerificationPathDefinition,
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
            "EL-MOI-PASSPORT-NATURE-01",
            ("SRC-MOI-PASSPORT-REQ",),
        ),
        "EL-MOI-VALIDITY-01": EvidenceLink("EL-MOI-VALIDITY-01", ("SRC-MOI-PASSPORT-REQ",)),
    }
    exact_passages = {
        "EL-MOI-REQ-01": "بطاقة الرقم القومي لمن بلغت أعمارهم 15 سنة",
        "EL-MOI-REQ-02": "شهادة الميلاد المميكنة لمن هم دون 15 سنة",
        "EL-MOI-REQ-03": "شهادة القيد الدراسي للعام الحالي",
        "EL-MOI-REQ-04": "مستند التجنيد",
        "EL-MOI-REQ-05": "ثلاث صور شخصية ملونة حديثة خلفية بيضاء مقاس 4×6",
        "EL-MOI-REQ-06": "أصول المستندات وصورة منها",
        "EL-MOI-PROCESS-01": "نموذج 29 جوازات مميكن مجاناً",
        "EL-MOI-FEE-01": "705 جنيه",
        "EL-MOI-VALIDITY-01": "سبع سنوات",
    }
    locations = {
        key: "Ministry passport requirements/instructions page"
        for key in (
            "EL-MOI-REQ-01",
            "EL-MOI-REQ-02",
            "EL-MOI-REQ-03",
            "EL-MOI-REQ-04",
            "EL-MOI-REQ-05",
            "EL-MOI-REQ-06",
            "EL-MOI-PROCESS-01",
            "EL-MOI-PROCESS-02",
            "EL-MOI-FEE-01",
            "EL-MOI-PASSPORT-NATURE-01",
            "EL-MOI-VALIDITY-01",
        )
    }
    locations.update(
        {
            "EL-PSM-SERVICE-01": "Public Services directory service listing",
            "EL-MOI-URGENT-01": "Ministry accelerated-service announcement",
            "EL-MOI-PREMIUM-01": "Ministry accelerated-service announcement",
            "EL-MOI-ROUTING-01": "Ministry directory and accelerated-service announcements",
            "EL-MOI-GIZA-01": "Ministry passport-office directory entry",
        }
    )
    applicability_contexts = {
        "EL-MOI-REQ-01": "Current Ministry requirements page; domestic ordinary passport applicants aged 15 or older.",
        "EL-MOI-REQ-02": "Current Ministry requirements page; domestic ordinary passport applicants under age 15.",
        "EL-MOI-REQ-03": "Current Ministry requirements page; students on the ordinary domestic passport path.",
        "EL-MOI-REQ-04": "Current Ministry requirements page; applicable male ordinary domestic passport branch.",
        "EL-MOI-REQ-05": "Current Ministry requirements page; ordinary domestic passport renewal.",
        "EL-MOI-REQ-06": "Current Ministry requirements page; supporting documents on the ordinary domestic passport path.",
        "EL-MOI-PROCESS-01": "Current Ministry instructions; Form 29 for the ordinary domestic passport path.",
        "EL-MOI-PROCESS-02": "Current Ministry instructions; form-completion step on the ordinary domestic passport path.",
        "EL-MOI-FEE-01": "Current Ministry-published base fee at retrieval; effective-from date not exposed.",
        "EL-MOI-URGENT-01": "Current Ministry accelerated-service announcement; effective-from date not exposed.",
        "EL-MOI-PREMIUM-01": "Current Ministry accelerated-service announcement; effective-from date not exposed.",
        "EL-MOI-ROUTING-01": "Domestic ordinary territorial routing and identified accelerated-service locations.",
        "EL-MOI-GIZA-01": "Current Giza passport-office directory entry and listed police-jurisdiction coverage.",
        "EL-MOI-PASSPORT-NATURE-01": "Current Ministry requirements page; personal machine-readable passport nature.",
        "EL-MOI-VALIDITY-01": "Current Ministry-published standard validity at retrieval.",
        "EL-PSM-SERVICE-01": "Government service-directory identity for expired/page-full replacement; not proof of a current domestic previous-passport requirement.",
    }
    evidence_links = {
        key: replace(
            link,
            exact_passage=exact_passages.get(key),
            location=locations.get(key),
            applicability_context=applicability_contexts.get(key),
            retrieved_on=VERIFIED_ON,
        )
        for key, link in evidence_links.items()
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
        publication_state="published",
        published_on=VERIFIED_ON,
        trust_state="current",
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
            document_type_id="national_id",
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
            document_type_id="birth_certificate",
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
            document_type_id="student_enrollment_certificate",
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
            document_type_id="military_status_document",
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
            document_type_id="passport_photo",
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
            document_type_id="supporting_documents",
            original_quantity=1,
            copy_quantity=1,
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
            document_type_id="previous_passport",
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
            phase_order=10,
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
            phase_order=10,
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
            phase_order=20,
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
            value_state="known",
            fee_type="base",
        ),
        FeeDefinition(
            id="passport.fee.urgent_service",
            text=t("رسم إضافي للخدمة العاجلة", "Additional urgent-service fee"),
            amount=100,
            currency="EGP",
            applicability=eq("service_level", "urgent"),
            evidence_link_ids=("EL-MOI-URGENT-01",),
            verification_state="current",
            value_state="known",
            fee_type="additional_service",
        ),
        FeeDefinition(
            id="passport.fee.premium_service",
            text=t("رسم إضافي للخدمة المميزة", "Additional premium-service fee"),
            amount=500,
            currency="EGP",
            applicability=eq("service_level", "premium"),
            evidence_link_ids=("EL-MOI-PREMIUM-01",),
            verification_state="current",
            value_state="known",
            fee_type="additional_service",
        ),
    )

    service_points = (
        ServicePointDefinition(
            id="sp.giza_passport_office",
            text=t("قسم جوازات الجيزة", "Giza Passport Office"),
        ),
    )
    service_point_versions = (
        ServicePointVersionDefinition(
            id="spv.giza_passport_office.research-2026-08-25",
            service_point_id="sp.giza_passport_office",
            address=t(
                "مبنى قسم شرطة الجيزة، شارع البحر الأعظم، الجيزة",
                "Giza Police Department building, Bahr El-Azam Street, Giza",
            ),
            availability="available",
            effective_from=None,
            effective_to=None,
            evidence_link_ids=("EL-MOI-GIZA-01",),
            verification_state="current",
        ),
    )
    service_point_associations = (
        ProcedureServicePointAssociationDefinition(
            id="spa.passport_renewal.giza_standard",
            service_point_version_id="spv.giza_passport_office.research-2026-08-25",
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
            effective_from=None,
            effective_to=None,
            evidence_link_ids=("EL-MOI-ROUTING-01",),
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
            kind="administrative",
        ),
        WarningDefinition(
            id="passport.warning.validity",
            text=t(
                "مدة الصلاحية القياسية المنشورة حاليًا سبع سنوات.",
                "The currently published standard validity is seven years.",
            ),
            severity="info",
            evidence_link_ids=("EL-MOI-VALIDITY-01",),
            kind="administrative",
        ),
        WarningDefinition(
            id="passport.warning.regenerate",
            text=t(
                "أعد التحقق من الخطة قبل التوجه مباشرة لأن الرسوم ونقاط الخدمة والتعليمات قد تتغير.",
                "Re-check the plan immediately before acting because fees, Service Points and instructions can change.",
            ),
            severity="important",
            kind="product",
            role="regeneration",
        ),
        WarningDefinition(
            id="passport.warning.guidance_not_decision",
            text=t(
                "هذه إرشادات مبنية على مصادر منشورة وليست قرارًا ملزمًا من الجهة الحكومية.",
                "This is source-backed guidance, not a binding decision by the government authority.",
            ),
            severity="important",
            kind="product",
            role="limitation",
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
        service_point_versions=service_point_versions,
        service_point_associations=service_point_associations,
        routing_verification_path=VerificationPathDefinition(
            id="passport.routing.verify",
            text=t(
                "تحقق من قسم الجوازات المختص وقواعد الاختصاص قبل التوجه.",
                "Verify the competent passport office and jurisdiction rules before acting.",
            ),
            evidence_link_ids=("EL-MOI-ROUTING-01",),
        ),
    )
