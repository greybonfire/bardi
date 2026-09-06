"""Exact integrity verification for the researched passport-renewal import."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from planning.facts import FACT_DEFINITIONS

from knowledge.fees import Fee
from knowledge.models import (
    Authority,
    ChecklistItem,
    DocumentType,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scenarios import PlanningScenario, planning_behavior_signature
from knowledge.procedure_dependencies import ProcedureDependency
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)

VERSION_ID = "ordinary_domestic_passport_renewal.research-2026-08-25"
RESEARCH_DATE = date(2026, 8, 25)
SHORT_REVERIFY = RESEARCH_DATE + timedelta(days=30)
EVIDENCE_CONTEXT = "Ordinary domestic passport renewal in Egypt; retrieved 2026-08-25."
EVIDENCE_LOCATION = "Preserved source page/announcement passage"


def _eq(fact: str, value: object) -> dict[str, object]:
    return {"op": "eq", "fact": fact, "value": value}


def _all(*children: dict[str, object]) -> dict[str, object]:
    return {"op": "all", "children": list(children)}


def _value(instance: object, path: str) -> object:
    value: object = instance
    for part in path.split("."):
        value = getattr(value, part)
    return value


def _expect(instance: models.Model, expected: dict[str, object], identity: str) -> None:
    conflicts = [path for path, value in expected.items() if _value(instance, path) != value]
    if conflicts:
        raise ValidationError(f"{identity}: semantic conflict in {', '.join(sorted(conflicts))}.")


def _expect_ids(
    queryset: models.QuerySet[Any], expected: set[str], aggregate: str
) -> dict[str, Any]:
    rows = {row.semantic_id: row for row in queryset}
    if set(rows) != expected:
        raise ValidationError(f"{VERSION_ID}: semantic aggregate conflict for {aggregate}.")
    return rows


def _expect_names(
    queryset: models.QuerySet[Any], expected: set[str], aggregate: str
) -> dict[str, Any]:
    rows = {row.name: row for row in queryset}
    if set(rows) != expected:
        raise ValidationError(f"{VERSION_ID}: semantic aggregate conflict for {aggregate}.")
    return rows


def _verify_catalog(version: ProcedureVersion) -> tuple[Service, Procedure]:
    service = Service.objects.get(semantic_id="get_egyptian_passport")
    _expect(
        service,
        {
            "text_ar": "الحصول على جواز سفر مصري",
            "text_en": "Get an Egyptian passport",
            "is_active": True,
        },
        service.semantic_id,
    )
    procedure = Procedure.objects.get(semantic_id="ordinary_domestic_passport_renewal")
    _expect(
        procedure,
        {
            "text_ar": "استخراج جواز سفر عادي بدل جواز سفر منتهي أو ممتلئ الصفحات داخل مصر",
            "text_en": (
                "Obtain an ordinary passport in place of an expired or page-full passport "
                "inside Egypt"
            ),
            "primary_service.semantic_id": service.semantic_id,
        },
        procedure.semantic_id,
    )
    boundary = _all(
        _eq("citizenship", "egyptian"),
        _eq("application_location", "inside_egypt"),
        _eq("passport_class", "ordinary"),
        {"op": "in", "fact": "existing_passport_state", "value": ["expired", "pages_full"]},
    )
    _expect(
        version,
        {
            "procedure.semantic_id": procedure.semantic_id,
            "text_ar": procedure.text_ar,
            "text_en": procedure.text_en,
            "applicability": boundary,
            "effective_from": RESEARCH_DATE,
        },
        VERSION_ID,
    )
    candidate = ServiceProcedureCandidate.objects.get(service=service, procedure=procedure)
    _expect(candidate, {"selection_predicate": boundary}, str(candidate))
    return service, procedure


def _verify_facts_and_questions(service: Service) -> None:
    question_specs = (
        (0, "q.citizenship", "citizenship", "هل أنت مواطن مصري؟", "Are you an Egyptian citizen?"),
        (
            10,
            "q.application_location",
            "application_location",
            "هل ستقدّم طلب الجواز من داخل مصر أم من خارجها؟",
            "Will you apply for the passport from inside or outside Egypt?",
        ),
        (
            20,
            "q.existing_passport_state",
            "existing_passport_state",
            "ما حالة جواز سفرك الحالي؟",
            "What is the status of your current passport?",
        ),
        (
            30,
            "q.passport_class",
            "passport_class",
            "هل جواز السفر المطلوب جواز عادي أم من فئة أخرى؟",
            "Is the passport you need an ordinary passport or another class?",
        ),
        (40, "q.birth_date", "birth_date", "ما تاريخ ميلادك؟", "What is your date of birth?"),
        (
            50,
            "q.sex",
            "sex",
            "ما الجنس المثبت في مستنداتك الرسمية؟",
            "What sex is recorded on your official documents?",
        ),
        (
            60,
            "q.is_student",
            "is_student",
            "هل أنت طالب أو طالبة في العام الدراسي الحالي؟",
            "Are you a student in the current academic year?",
        ),
        (
            80,
            "q.service_level",
            "service_level",
            "هل تريد الخدمة العادية أم العاجلة أم المميزة في نفس اليوم؟",
            "Do you want standard, next-working-day urgent, or same-day premium service?",
        ),
        (
            90,
            "q.residence_police_jurisdiction",
            "residence_police_jurisdiction",
            "ما قسم أو مركز الشرطة التابع له محل إقامتك؟",
            "Which police district or centre covers your residence?",
        ),
    )
    for priority, semantic_id, fact_key, text_ar, text_en in question_specs:
        registry = FACT_DEFINITIONS[fact_key]
        fact = FactDefinition.objects.get(key=fact_key)
        _expect(
            fact,
            {
                "kind": registry.kind,
                "enum_values": list(registry.enum_values),
                "minimum": registry.minimum,
                "derived": registry.derived,
                "is_published": True,
            },
            fact_key,
        )
        question = ServiceQuestion.objects.get(semantic_id=semantic_id)
        _expect(
            question,
            {
                "service.semantic_id": service.semantic_id,
                "fact.key": fact_key,
                "text_ar": text_ar,
                "text_en": text_en,
                "priority": priority,
            },
            semantic_id,
        )
        if question.resolved_fact_keys != (fact_key,):
            raise ValidationError(f"{semantic_id}: semantic conflict in resolved Facts.")


def _verify_sources_and_documents() -> dict[str, Source]:
    authority_specs = {
        "authority.moi.gapin": {
            "name_ar": "وزارة الداخلية — الإدارة العامة للجوازات والهجرة والجنسية",
            "name_en": (
                "Egyptian Ministry of Interior — General Administration of Passports, "
                "Immigration and Nationality"
            ),
        },
        "authority.mfa.egypt": {
            "name_ar": "وزارة الخارجية المصرية",
            "name_en": "Egyptian Ministry of Foreign Affairs",
        },
    }
    for semantic_id, expected in authority_specs.items():
        _expect(Authority.objects.get(semantic_id=semantic_id), expected, semantic_id)

    source_specs = {
        "SRC-MOI-PASSPORT-REQ": (
            "authority.moi.gapin",
            "Passport requirements and instructions",
            "https://moi.gov.eg/content/PPAr.htm",
        ),
        "SRC-MOI-ACCELERATED": (
            "authority.moi.gapin",
            "Urgent and premium passport service announcements",
            "https://moi.gov.eg/News/Index?sectionId=1",
        ),
        "SRC-MOI-OFFICE-DIRECTORY": (
            "authority.moi.gapin",
            "Passport office and police directory entries",
            "https://moi.gov.eg/home/directorypolice",
        ),
        "SRC-PSM-RENEWAL-SERVICE": (
            "authority.moi.gapin",
            "Expired or page-full passport replacement service",
            "https://psm.gov.eg/providers/1/services",
        ),
        "SRC-HISTORIC-GOV-PASSPORT": (
            "authority.moi.gapin",
            "Historical government passport requirements",
            "https://moi.gov.eg/content/PPAr.htm",
        ),
        "SRC-MFA-CONSULAR-PASSPORT": (
            "authority.mfa.egypt",
            "Consular passport issuance and renewal",
            "https://sis.gov.eg/ar/بوابة-معلومات-للمصريين-بالخارج/الخدمات-الحكومية/دليل-المعاملات-القنصلية/",
        ),
    }
    sources: dict[str, Source] = {}
    for semantic_id, (authority_id, title, locator) in source_specs.items():
        source = Source.objects.get(semantic_id=semantic_id)
        _expect(
            source,
            {
                "authority.semantic_id": authority_id,
                "title": title,
                "locator": locator,
                "classification": "official",
                "retrieved_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
            },
            semantic_id,
        )
        sources[semantic_id] = source

    document_specs = {
        "national_id": (
            "بطاقة رقم قومي سارية وبياناتها الحالية محدثة",
            "Valid National ID with current recorded data",
        ),
        "birth_certificate": (
            "شهادة ميلاد مميكنة تحمل الرقم القومي",
            "Machine-readable birth certificate carrying the national number",
        ),
        "student_enrollment_certificate": (
            "شهادة قيد دراسي عن العام الدراسي الحالي",
            "Enrollment certificate for the current academic year",
        ),
        "military_status_document": ("مستند يثبت الموقف من التجنيد", "Military-status document"),
        "passport_photo": (
            "3 صور شخصية ملونة حديثة بخلفية بيضاء مقاس 4×6",
            "Three recent colour 4×6 photos with a white background",
        ),
        "supporting_documents": (
            "أصول المستندات وصورة منها للمطابقة",
            "Originals plus a copy for verification",
        ),
        "previous_passport": ("جواز السفر السابق", "Previous passport"),
    }
    for semantic_id, (name_ar, name_en) in document_specs.items():
        _expect(
            DocumentType.objects.get(semantic_id=semantic_id),
            {"name_ar": name_ar, "name_en": name_en},
            semantic_id,
        )
    return sources


def _verify_claims(version: ProcedureVersion) -> None:
    checklist_specs: dict[str, dict[str, object]] = {
        "passport.requirement.national_id": {
            "text_ar": "بطاقة رقم قومي سارية وبياناتها الحالية محدثة",
            "text_en": "Valid National ID with current recorded data",
            "classification": "official_requirement",
            "document_type.semantic_id": "national_id",
            "quantity": 1,
            "display_order": 10,
            "applicability": {"op": "gte", "fact": "age_years_on_evaluation_date", "value": 15},
        },
        "passport.requirement.birth_certificate": {
            "text_ar": "شهادة ميلاد مميكنة تحمل الرقم القومي",
            "text_en": "Machine-readable birth certificate carrying the national number",
            "classification": "official_requirement",
            "document_type.semantic_id": "birth_certificate",
            "quantity": 1,
            "display_order": 20,
            "applicability": {"op": "lt", "fact": "age_years_on_evaluation_date", "value": 15},
        },
        "passport.requirement.student_enrollment": {
            "text_ar": "شهادة قيد دراسي عن العام الدراسي الحالي",
            "text_en": "Enrollment certificate for the current academic year",
            "classification": "official_requirement",
            "document_type.semantic_id": "student_enrollment_certificate",
            "quantity": 1,
            "display_order": 30,
            "applicability": _eq("is_student", True),
        },
        "passport.requirement.military_status": {
            "text_ar": "مستند يثبت الموقف من التجنيد",
            "text_en": "Military-status document",
            "classification": "official_requirement",
            "document_type.semantic_id": "military_status_document",
            "quantity": 1,
            "display_order": 40,
            "applicability": _all(
                _eq("sex", "male"),
                {"op": "gte", "fact": "birth_date", "value": {"$date": "1941-03-18"}},
                {"op": "gte", "fact": "age_years_on_evaluation_date", "value": 19},
            ),
        },
        "passport.requirement.photos": {
            "text_ar": "3 صور شخصية ملونة حديثة بخلفية بيضاء مقاس 4×6",
            "text_en": "Three recent colour 4×6 photos with a white background",
            "classification": "official_requirement",
            "document_type.semantic_id": "passport_photo",
            "quantity": 3,
            "display_order": 50,
            "applicability": {},
        },
        "passport.requirement.originals_and_copy": {
            "text_ar": "أصول المستندات وصورة منها للمطابقة",
            "text_en": "Originals plus a copy for verification",
            "classification": "official_requirement",
            "document_type.semantic_id": "supporting_documents",
            "quantity": 1,
            "display_order": 60,
            "applicability": {},
        },
        "passport.requirement.previous_passport": {
            "text_ar": "جواز السفر السابق المنتهي أو ممتلئ الصفحات",
            "text_en": "Previous expired or page-full passport",
            "classification": "candidate",
            "document_type.semantic_id": "previous_passport",
            "display_order": 70,
            "applicability": {
                "op": "in",
                "fact": "existing_passport_state",
                "value": ["expired", "pages_full"],
            },
            "verification_state": "needs_reverification",
        },
    }
    checklist = _expect_ids(
        ChecklistItem.objects.filter(procedure_version=version).select_related("document_type"),
        set(checklist_specs),
        "ChecklistItem",
    )
    for semantic_id, expected in checklist_specs.items():
        expected.setdefault("verified_on", RESEARCH_DATE)
        expected.setdefault("reverify_on", SHORT_REVERIFY)
        expected.setdefault("verification_state", "current")
        _expect(checklist[semantic_id], expected, semantic_id)

    step_specs = {
        "passport.step.obtain_form_29": {
            "text_ar": "الحصول على نموذج 29 جوازات مميكن مجانًا",
            "text_en": "Obtain machine-readable Passport Form 29 free of charge",
            "phase": "prepare-at-office",
            "phase_order": 10,
            "slot": 10,
        },
        "passport.step.complete_form": {
            "text_ar": "استيفاء بيانات الصفحة الأولى من النموذج بمعرفة صاحب الشأن",
            "text_en": "Complete the first page of the form with the applicant’s information",
            "phase": "prepare-at-office",
            "phase_order": 10,
            "slot": 20,
        },
        "passport.step.submit_and_pay": {
            "text_ar": "تقديم الطلب والمستندات وسداد الرسم في نقطة الخدمة المختصة",
            "text_en": (
                "Submit the application/documents and pay the applicable fee at the resolved "
                "Service Point"
            ),
            "phase": "submit",
            "phase_order": 20,
            "slot": 30,
        },
    }
    steps = _expect_ids(Step.objects.filter(procedure_version=version), set(step_specs), "Step")
    for semantic_id, expected in step_specs.items():
        expected.update(
            {
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            }
        )
        _expect(steps[semantic_id], expected, semantic_id)

    warning_specs = {
        "passport.warning.personal_document": {
            "text_ar": "جواز السفر المقروء آليًا شخصي ولا تُضاف إليه الزوجة أو الأبناء.",
            "text_en": (
                "The machine-readable passport is personal; a spouse or children are not added "
                "to it."
            ),
            "severity": "info",
            "kind": "administrative",
            "role": "general",
            "display_order": 1,
        },
        "passport.warning.validity": {
            "text_ar": "مدة الصلاحية القياسية المنشورة حاليًا سبع سنوات.",
            "text_en": "The currently published standard validity is seven years.",
            "severity": "info",
            "kind": "administrative",
            "role": "general",
            "display_order": 2,
        },
        "passport.warning.regenerate": {
            "text_ar": "أعد التحقق من الخطة قبل التوجه مباشرة لأن الرسوم ونقاط الخدمة والتعليمات قد تتغير.",
            "text_en": (
                "Re-check the plan immediately before acting because fees, Service Points and "
                "instructions can change."
            ),
            "severity": "important",
            "kind": "product",
            "role": "regeneration",
            "display_order": 3,
        },
        "passport.warning.guidance_not_decision": {
            "text_ar": "هذه إرشادات مبنية على مصادر منشورة وليست قرارًا ملزمًا من الجهة الحكومية.",
            "text_en": "This is source-backed guidance, not a binding decision by the government authority.",
            "severity": "important",
            "kind": "product",
            "role": "limitation",
            "display_order": 4,
        },
    }
    warnings = _expect_ids(
        Warning.objects.filter(procedure_version=version), set(warning_specs), "Warning"
    )
    for semantic_id, expected in warning_specs.items():
        expected.update(
            {
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            }
        )
        _expect(warnings[semantic_id], expected, semantic_id)

    fee_specs = {
        "passport.fee.base": {
            "text_ar": "رسم إصدار جواز السفر المقروء آليًا",
            "text_en": "Machine-readable passport base fee",
            "value_state": "known",
            "amount": 705,
            "currency": "EGP",
            "fee_type": "government_fee",
            "display_order": 1,
            "applicability": {},
        },
        "passport.fee.urgent_service": {
            "text_ar": "رسم إضافي للخدمة العاجلة",
            "text_en": "Additional urgent-service fee",
            "value_state": "known",
            "amount": 100,
            "currency": "EGP",
            "fee_type": "optional_service_fee",
            "display_order": 2,
            "applicability": _eq("service_level", "urgent"),
        },
        "passport.fee.premium_service": {
            "text_ar": "رسم إضافي للخدمة المميزة",
            "text_en": "Additional premium-service fee",
            "value_state": "known",
            "amount": 500,
            "currency": "EGP",
            "fee_type": "optional_service_fee",
            "display_order": 3,
            "applicability": _eq("service_level", "premium"),
        },
    }
    fees = _expect_ids(Fee.objects.filter(procedure_version=version), set(fee_specs), "Fee")
    for semantic_id, expected in fee_specs.items():
        expected.update(
            {
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            }
        )
        _expect(fees[semantic_id], expected, semantic_id)

    if version.eligibility_bases.exists() or ProcedureDependency.objects.filter(
        procedure_version=version
    ).exists():
        raise ValidationError(f"{VERSION_ID}: semantic aggregate conflict for optional claims.")


def _verify_routing(version: ProcedureVersion) -> None:
    point = ServicePoint.objects.get(semantic_id="sp.giza_passport_office")
    _expect(point, {"name_ar": "قسم جوازات الجيزة", "name_en": "Giza Passport Office"}, point.semantic_id)
    material = ServicePointVersion.objects.get(
        semantic_id="spv.giza_passport_office.research-2026-08-25"
    )
    _expect(
        material,
        {
            "service_point.semantic_id": point.semantic_id,
            "address_ar": "مبنى قسم شرطة الجيزة، شارع البحر الأعظم",
            "address_en": "Giza Police Department building, Bahr El-Azam Street",
            "availability": "available",
            "effective_from": RESEARCH_DATE,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
        material.semantic_id,
    )
    associations = _expect_ids(
        ProcedureServicePointAssociation.objects.filter(procedure_version=version).select_related(
            "service_point_version"
        ),
        {"spa.passport_renewal.giza_standard"},
        "ProcedureServicePointAssociation",
    )
    association = associations["spa.passport_renewal.giza_standard"]
    _expect(
        association,
        {
            "service_point_version.semantic_id": material.semantic_id,
            "applicability": _all(
                _eq("service_level", "standard"),
                _eq("residence_police_jurisdiction", "giza"),
            ),
            "effective_from": RESEARCH_DATE,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
        association.semantic_id,
    )


def _evidence_owner(link: EvidenceLink) -> tuple[str, str]:
    for field in (
        "checklist_item",
        "step",
        "warning",
        "fee",
        "eligibility_basis",
        "procedure_dependency",
        "service_point_version",
        "procedure_service_point_association",
    ):
        if getattr(link, f"{field}_id", None) is not None:
            owner = getattr(link, field)
            return field, owner.semantic_id
    raise ValidationError("Evidence owner is missing.")


def _verify_evidence(version: ProcedureVersion) -> None:
    expected: dict[tuple[str, str, str], tuple[str, str, tuple[str, ...]]] = {}

    def add(
        owner_kind: str,
        owner_id: str,
        evidence_id: str,
        passage: str,
        source_ids: tuple[str, ...],
        *,
        state: str = "current",
        support: str = "supports",
    ) -> None:
        expected[(owner_kind, owner_id, evidence_id)] = (passage, state + ":" + support, source_ids)

    for owner_id, evidence_id, passage in (
        ("passport.requirement.national_id", "EL-MOI-REQ-01", "بطاقة الرقم القومي لمن بلغت أعمارهم 15 سنة"),
        ("passport.requirement.birth_certificate", "EL-MOI-REQ-02", "شهادة الميلاد المميكنة لمن هم دون 15 سنة"),
        ("passport.requirement.student_enrollment", "EL-MOI-REQ-03", "شهادة القيد الدراسي للعام الحالي"),
        ("passport.requirement.military_status", "EL-MOI-REQ-04", "مستند التجنيد"),
        ("passport.requirement.photos", "EL-MOI-REQ-05", "ثلاث صور شخصية ملونة حديثة خلفية بيضاء مقاس 4×6"),
        ("passport.requirement.originals_and_copy", "EL-MOI-REQ-06", "أصول المستندات وصورة منها"),
    ):
        add("checklist_item", owner_id, evidence_id, passage, ("SRC-MOI-PASSPORT-REQ",))
    add(
        "checklist_item",
        "passport.requirement.previous_passport",
        "EL-PSM-SERVICE-01",
        "Expired or page-full passport replacement service",
        ("SRC-PSM-RENEWAL-SERVICE",),
        support="context",
    )
    add(
        "checklist_item",
        "passport.requirement.previous_passport",
        "EL-HIST-OLDPASS-01",
        "Old passport is brought for renewal",
        ("SRC-HISTORIC-GOV-PASSPORT",),
        state="stale",
        support="context",
    )
    add(
        "checklist_item",
        "passport.requirement.previous_passport",
        "EL-MFA-CONSULAR-01",
        "Previous passport is required for consular renewal",
        ("SRC-MFA-CONSULAR-PASSPORT",),
        support="context",
    )
    add(
        "step",
        "passport.step.obtain_form_29",
        "EL-MOI-PROCESS-01",
        "نموذج 29 جوازات مميكن مجاناً",
        ("SRC-MOI-PASSPORT-REQ",),
    )
    add(
        "step",
        "passport.step.complete_form",
        "EL-MOI-PROCESS-02",
        "Complete the first page of the form",
        ("SRC-MOI-PASSPORT-REQ",),
    )
    add(
        "step",
        "passport.step.submit_and_pay",
        "EL-MOI-ROUTING-01",
        "Submit at the competent service point",
        ("SRC-MOI-OFFICE-DIRECTORY", "SRC-MOI-ACCELERATED"),
    )
    add(
        "step",
        "passport.step.submit_and_pay",
        "EL-MOI-FEE-01",
        "705 جنيه",
        ("SRC-MOI-PASSPORT-REQ",),
    )
    add(
        "warning",
        "passport.warning.personal_document",
        "EL-MOI-PASSPORT-NATURE-01",
        "Machine-readable passport is personal",
        ("SRC-MOI-PASSPORT-REQ",),
    )
    add(
        "warning",
        "passport.warning.validity",
        "EL-MOI-VALIDITY-01",
        "سبع سنوات",
        ("SRC-MOI-PASSPORT-REQ",),
    )
    add("fee", "passport.fee.base", "EL-MOI-FEE-01", "705 جنيه", ("SRC-MOI-PASSPORT-REQ",))
    add(
        "fee",
        "passport.fee.urgent_service",
        "EL-MOI-URGENT-01",
        "Additional fee 100 EGP; next working day",
        ("SRC-MOI-ACCELERATED",),
    )
    add(
        "fee",
        "passport.fee.premium_service",
        "EL-MOI-PREMIUM-01",
        "Additional fee 500 EGP; same day",
        ("SRC-MOI-ACCELERATED",),
    )
    add(
        "service_point_version",
        "spv.giza_passport_office.research-2026-08-25",
        "EL-MOI-GIZA-01",
        "Giza Passport Office at the Giza Police Department building on Bahr El-Azam Street",
        ("SRC-MOI-OFFICE-DIRECTORY",),
    )
    add(
        "procedure_service_point_association",
        "spa.passport_renewal.giza_standard",
        "EL-MOI-ROUTING-01",
        "Published territorial coverage includes Giza",
        ("SRC-MOI-OFFICE-DIRECTORY",),
    )

    links = (
        EvidenceLink.objects.filter(
            Q(checklist_item__procedure_version=version)
            | Q(step__procedure_version=version)
            | Q(warning__procedure_version=version)
            | Q(fee__procedure_version=version)
            | Q(eligibility_basis__procedure_version=version)
            | Q(procedure_dependency__procedure_version=version)
            | Q(service_point_version__associations__procedure_version=version)
            | Q(procedure_service_point_association__procedure_version=version)
        )
        .distinct()
        .prefetch_related("source_links__source")
    )
    actual: dict[tuple[str, str, str], EvidenceLink] = {}
    for link in links:
        owner_kind, owner_id = _evidence_owner(link)
        actual[(owner_kind, owner_id, link.semantic_id)] = link
    if set(actual) != set(expected):
        raise ValidationError(f"{VERSION_ID}: semantic aggregate conflict for EvidenceLink.")

    for key, (passage, state_support, source_ids) in expected.items():
        link = actual[key]
        state, support = state_support.split(":", 1)
        identity = ":".join(key)
        _expect(
            link,
            {
                "passage": passage,
                "location": EVIDENCE_LOCATION,
                "applicability_context": EVIDENCE_CONTEXT,
                "retrieved_on": RESEARCH_DATE,
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": state,
                "support_status": support,
            },
            identity,
        )
        actual_sources = tuple(
            row.source.semantic_id for row in link.source_links.select_related("source").order_by("position")
        )
        if actual_sources != source_ids:
            raise ValidationError(f"{identity}: semantic conflict in sources.")


def _scenario_specs() -> dict[str, tuple[str, dict[str, object], str, dict[str, object], str]]:
    common: dict[str, object] = {
        "citizenship": "egyptian",
        "application_location": "inside_egypt",
        "existing_passport_state": "expired",
        "passport_class": "ordinary",
        "birth_date": "1995-06-10",
        "sex": "female",
        "is_student": False,
        "service_level": "standard",
        "residence_police_jurisdiction": "giza",
    }
    adult = [
        "passport.requirement.national_id",
        "passport.requirement.photos",
        "passport.requirement.originals_and_copy",
    ]
    child = [
        "passport.requirement.birth_certificate",
        "passport.requirement.photos",
        "passport.requirement.originals_and_copy",
    ]
    military = [
        "passport.requirement.national_id",
        "passport.requirement.military_status",
        "passport.requirement.photos",
        "passport.requirement.originals_and_copy",
    ]
    plan: dict[str, object] = {
        "procedure_version_id": VERSION_ID,
        "checklist_item_ids": adult,
        "fee_ids": ["passport.fee.base"],
        "routing_status": "resolved",
        "routing_association_ids": ["spa.passport_renewal.giza_standard"],
    }
    unsupported = {"reason": "no_matching_researched_procedure"}

    raw = (
        ("passport.positive.adult_expired_standard", "positive", common, "plan", plan),
        ("passport.negative.first_issuance", "negative", {**common, "existing_passport_state": "none"}, "inconclusive", unsupported),
        ("passport.negative.lost", "negative", {**common, "existing_passport_state": "lost"}, "inconclusive", unsupported),
        ("passport.negative.damaged", "negative", {**common, "existing_passport_state": "damaged"}, "inconclusive", unsupported),
        ("passport.negative.outside_egypt", "negative", {**common, "application_location": "outside_egypt"}, "inconclusive", unsupported),
        ("passport.unknown.citizenship", "unknown", {k: v for k, v in common.items() if k != "citizenship"}, "next_question", {"question_id": "q.citizenship"}),
        ("passport.unknown.application_location", "unknown", {k: v for k, v in common.items() if k != "application_location"}, "next_question", {"question_id": "q.application_location"}),
        ("passport.unknown.passport_state", "unknown", {k: v for k, v in common.items() if k != "existing_passport_state"}, "next_question", {"question_id": "q.existing_passport_state"}),
        ("passport.edge.turns_15", "supported_edge", {**common, "birth_date": "2011-08-25"}, "plan", {**plan, "checklist_item_ids": adult}),
        ("passport.edge.one_day_under_15", "supported_edge", {**common, "birth_date": "2011-08-26"}, "plan", {**plan, "checklist_item_ids": child}),
        ("passport.edge.male_turns_19", "supported_edge", {**common, "birth_date": "2007-08-25", "sex": "male"}, "plan", {**plan, "checklist_item_ids": military}),
        ("passport.edge.male_one_day_under_19", "supported_edge", {**common, "birth_date": "2007-08-26", "sex": "male"}, "plan", plan),
        (
            "passport.student.true",
            "positive",
            {**common, "is_student": True},
            "plan",
            {
                **plan,
                "checklist_item_ids": [
                    "passport.requirement.national_id",
                    "passport.requirement.student_enrollment",
                    "passport.requirement.photos",
                    "passport.requirement.originals_and_copy",
                ],
            },
        ),
        ("passport.student.false", "positive", common, "plan", plan),
        ("passport.student.unknown", "unknown", {k: v for k, v in common.items() if k != "is_student"}, "inconclusive", {"reason": "checklist_applicability_unknown"}),
        (
            "passport.fee.urgent",
            "positive",
            {**common, "service_level": "urgent"},
            "plan",
            {**plan, "fee_ids": ["passport.fee.base", "passport.fee.urgent_service"], "routing_status": "resolved", "routing_association_ids": []},
        ),
        (
            "passport.fee.premium",
            "positive",
            {**common, "service_level": "premium"},
            "plan",
            {**plan, "fee_ids": ["passport.fee.base", "passport.fee.premium_service"], "routing_status": "resolved", "routing_association_ids": []},
        ),
        ("passport.routing.omitted_district", "unknown", {k: v for k, v in common.items() if k != "residence_police_jurisdiction"}, "plan", {**plan, "routing_status": "unresolved", "routing_association_ids": []}),
        ("passport.routing.unresearched_district", "supported_edge", {**common, "residence_police_jurisdiction": "unresearched"}, "plan", {**plan, "routing_status": "resolved", "routing_association_ids": []}),
        ("passport.locale.ar", "positive", common, "plan", plan),
    )
    return {
        name: (
            kind,
            facts,
            family,
            identifiers,
            "ar" if name == "passport.locale.ar" else "en",
        )
        for name, kind, facts, family, identifiers in raw
    }


def _verify_scenarios_and_review_policy(version: ProcedureVersion) -> None:
    specs = _scenario_specs()
    scenarios = _expect_names(
        PlanningScenario.objects.filter(procedure_version=version), set(specs), "PlanningScenario"
    )
    behavior_signature = planning_behavior_signature(version)
    for name, (kind, facts, family, identifiers, locale) in specs.items():
        _expect(
            scenarios[name],
            {
                "kind": kind,
                "evaluation_context": {"evaluation_date": "2026-08-25", "locale": locale},
                "source_facts": facts,
                "expected_result_family": family,
                "expected_identifiers": identifiers,
                "expected_diagnostics": [],
                "behavior_signature": behavior_signature,
            },
            name,
        )

    try:
        policy = ProcedureVersionReviewPolicy.objects.select_related("author").get(
            procedure_version=version
        )
    except ProcedureVersionReviewPolicy.DoesNotExist as exc:
        raise ValidationError(f"{VERSION_ID}: semantic aggregate conflict for review policy.") from exc
    _expect(
        policy,
        {
            "legal_risk": False,
            "military_risk": True,
            "custody_guardianship_risk": False,
            "contested_identity_risk": False,
            "author.is_staff": True,
        },
        f"{VERSION_ID}:review-policy",
    )


def verify_passport_renewal_import(version: ProcedureVersion) -> None:
    """Reject any semantic drift from the deterministic researched import."""

    if version.semantic_id != VERSION_ID:
        raise ValidationError(f"Unexpected passport-renewal version identity: {version.semantic_id}.")
    service, _procedure = _verify_catalog(version)
    _verify_facts_and_questions(service)
    _verify_sources_and_documents()
    _verify_claims(version)
    _verify_routing(version)
    _verify_evidence(version)
    _verify_scenarios_and_review_policy(version)


__all__ = ("verify_passport_renewal_import",)
