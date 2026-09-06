"""Deterministic production import for researched ordinary domestic passport renewal.

This module transcribes the evidence pack into production models. It deliberately has no
runtime or import dependency on the frozen prototype and never publishes or records approvals.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
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
from knowledge.planning_scenarios import PlanningScenario
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)
from knowledge.services import (
    save_candidate,
    set_evidence_link_sources,
    set_question_resolved_facts,
    validate_core_catalog,
)

VERSION_ID = "ordinary_domestic_passport_renewal.research-2026-08-25"
RESEARCH_DATE = date(2026, 8, 25)
SHORT_REVERIFY = RESEARCH_DATE + timedelta(days=30)


def _eq(fact: str, value: object) -> dict[str, object]:
    return {"op": "eq", "fact": fact, "value": value}


def _all(*children: dict[str, object]) -> dict[str, object]:
    return {"op": "all", "children": list(children)}


def _expected(instance: models.Model, values: dict[str, Any], identity: str) -> None:
    conflicts = [
        name
        for name, value in values.items()
        if getattr(instance, f"{name}_id", object()) != value
        and getattr(instance, name, object()) != value
    ]
    if conflicts:
        raise ValidationError(f"{identity}: semantic conflict in {', '.join(sorted(conflicts))}.")


def _shared(model: Any, lookup: dict[str, Any], values: dict[str, Any]) -> models.Model:
    row = model.objects.filter(**lookup).first()
    identity = str(next(iter(lookup.values())))
    if row is not None:
        _expected(row, values, identity)
        return cast(models.Model, row)
    row = model(**lookup, **values)
    row.full_clean()
    row.save()
    return cast(models.Model, row)


def _published_fact(key: str) -> FactDefinition:
    expected = FACT_DEFINITIONS[key]
    try:
        row = FactDefinition.objects.get(key=key, is_published=True)
    except FactDefinition.DoesNotExist as exc:
        raise ValidationError(f"{key}: compatible published Fact definition is required.") from exc
    values = {
        "kind": expected.kind,
        "enum_values": list(expected.enum_values),
        "minimum": expected.minimum,
        "derived": expected.derived,
    }
    _expected(row, values, key)
    return row


def _claim(model: Any, version: ProcedureVersion, values: dict[str, Any]) -> models.Model:
    row = model(procedure_version=version, **values)
    row.full_clean()
    row.save()
    return cast(models.Model, row)


def _evidence(
    owner_field: str,
    owner: models.Model,
    semantic_id: str,
    passage: str,
    sources: tuple[Source, ...],
    *,
    state: str = "current",
    support: str = "supports",
    context: str = "Ordinary domestic passport renewal in Egypt; retrieved 2026-08-25.",
) -> EvidenceLink:
    link = EvidenceLink(
        semantic_id=semantic_id,
        **{owner_field: owner},
        passage=passage,
        location="Preserved source page/announcement passage",
        applicability_context=context,
        retrieved_on=RESEARCH_DATE,
        verified_on=RESEARCH_DATE,
        reverify_on=SHORT_REVERIFY,
        verification_state=state,
        support_status=support,
    )
    link.full_clean()
    link.save()
    set_evidence_link_sources(link, sources)
    return link


@transaction.atomic
def import_passport_renewal(*, author: models.Model) -> ProcedureVersion:
    """Create or verify the researched draft, without approvals or publication metadata."""

    user_model = get_user_model()
    if (
        not isinstance(author, user_model)
        or author.pk is None
        or not author.is_staff
        or not user_model._default_manager.filter(pk=author.pk, is_staff=True).exists()
    ):
        raise ValidationError("A saved staff author is required.")

    existing = ProcedureVersion.objects.select_for_update().filter(semantic_id=VERSION_ID).first()
    if existing is not None:
        _expected(
            existing,
            {
                "procedure_id": Procedure.objects.get(
                    semantic_id="ordinary_domestic_passport_renewal"
                ).pk,
                "text_ar": "استخراج جواز سفر عادي بدل جواز سفر منتهي أو ممتلئ الصفحات داخل مصر",
                "text_en": (
                    "Obtain an ordinary passport in place of an expired or page-full "
                    "passport inside Egypt"
                ),
            },
            VERSION_ID,
        )
        if existing.state == ProcedureVersion.State.DRAFT:
            expected_sets = {
                ChecklistItem: {
                    "passport.requirement.national_id",
                    "passport.requirement.birth_certificate",
                    "passport.requirement.student_enrollment",
                    "passport.requirement.military_status",
                    "passport.requirement.photos",
                    "passport.requirement.originals_and_copy",
                    "passport.requirement.previous_passport",
                },
                Step: {
                    "passport.step.obtain_form_29",
                    "passport.step.complete_form",
                    "passport.step.submit_and_pay",
                },
                Warning: {
                    "passport.warning.personal_document",
                    "passport.warning.validity",
                    "passport.warning.regenerate",
                    "passport.warning.guidance_not_decision",
                },
                Fee: {
                    "passport.fee.base",
                    "passport.fee.urgent_service",
                    "passport.fee.premium_service",
                },
                ProcedureServicePointAssociation: {"spa.passport_renewal.giza_standard"},
            }
            for model, ids in expected_sets.items():
                actual = set(
                    cast(Any, model)
                    .objects.filter(procedure_version=existing)
                    .values_list("semantic_id", flat=True)
                )
                if actual != ids:
                    raise ValidationError(
                        f"{VERSION_ID}: semantic aggregate conflict for {model.__name__}."
                    )
        validate_core_catalog()
        return existing

    service = _shared(
        Service,
        {"semantic_id": "get_egyptian_passport"},
        {
            "text_ar": "الحصول على جواز سفر مصري",
            "text_en": "Get an Egyptian passport",
            "is_active": True,
        },
    )
    assert isinstance(service, Service)
    procedure = _shared(
        Procedure,
        {"semantic_id": "ordinary_domestic_passport_renewal"},
        {
            "text_ar": "استخراج جواز سفر عادي بدل جواز سفر منتهي أو ممتلئ الصفحات داخل مصر",
            "text_en": (
                "Obtain an ordinary passport in place of an expired or page-full passport "
                "inside Egypt"
            ),
            "primary_service_id": service.pk,
        },
    )
    assert isinstance(procedure, Procedure)

    boundary = _all(
        _eq("citizenship", "egyptian"),
        _eq("application_location", "inside_egypt"),
        _eq("passport_class", "ordinary"),
        {"op": "in", "fact": "existing_passport_state", "value": ["expired", "pages_full"]},
    )
    candidate = ServiceProcedureCandidate.objects.filter(
        service=service, procedure=procedure
    ).first()
    if candidate is None:
        save_candidate(
            ServiceProcedureCandidate(
                service=service, procedure=procedure, selection_predicate=boundary
            )
        )
    else:
        _expected(candidate, {"selection_predicate": boundary}, str(candidate))

    questions = (
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
    for priority, semantic_id, fact_key, ar, en in questions:
        fact = _published_fact(fact_key)
        question = _shared(
            ServiceQuestion,
            {"semantic_id": semantic_id},
            {
                "service_id": service.pk,
                "fact_id": fact.pk,
                "text_ar": ar,
                "text_en": en,
                "priority": priority,
            },
        )
        assert isinstance(question, ServiceQuestion)
        resolved = question.resolved_fact_keys
        if not question.resolved_fact_links.exists():
            set_question_resolved_facts(question, (fact,))
        elif resolved != (fact.key,):
            raise ValidationError(f"{semantic_id}: semantic conflict in resolved Facts.")

    version = ProcedureVersion(
        semantic_id=VERSION_ID,
        procedure=procedure,
        text_ar=procedure.text_ar,
        text_en=procedure.text_en,
        applicability=boundary,
        effective_from=RESEARCH_DATE,
    )
    version.full_clean()
    version.save()

    authority = _shared(
        Authority,
        {"semantic_id": "authority.moi.gapin"},
        {
            "name_ar": "وزارة الداخلية — الإدارة العامة للجوازات والهجرة والجنسية",
            "name_en": (
                "Egyptian Ministry of Interior — General Administration of Passports, "
                "Immigration and Nationality"
            ),
        },
    )
    assert isinstance(authority, Authority)
    mfa = _shared(
        Authority,
        {"semantic_id": "authority.mfa.egypt"},
        {
            "name_ar": "وزارة الخارجية المصرية",
            "name_en": "Egyptian Ministry of Foreign Affairs",
        },
    )
    assert isinstance(mfa, Authority)
    source_specs = (
        (
            "SRC-MOI-PASSPORT-REQ",
            authority,
            "Passport requirements and instructions",
            "https://moi.gov.eg/content/PPAr.htm",
            "official",
        ),
        (
            "SRC-MOI-ACCELERATED",
            authority,
            "Urgent and premium passport service announcements",
            "https://moi.gov.eg/News/Index?sectionId=1",
            "official",
        ),
        (
            "SRC-MOI-OFFICE-DIRECTORY",
            authority,
            "Passport office and police directory entries",
            "https://moi.gov.eg/home/directorypolice",
            "official",
        ),
        (
            "SRC-PSM-RENEWAL-SERVICE",
            authority,
            "Expired or page-full passport replacement service",
            "https://psm.gov.eg/providers/1/services",
            "official",
        ),
        (
            "SRC-HISTORIC-GOV-PASSPORT",
            authority,
            "Historical government passport requirements",
            "https://moi.gov.eg/content/PPAr.htm",
            "official",
        ),
        (
            "SRC-MFA-CONSULAR-PASSPORT",
            mfa,
            "Consular passport issuance and renewal",
            "https://sis.gov.eg/ar/بوابة-معلومات-للمصريين-بالخارج/الخدمات-الحكومية/دليل-المعاملات-القنصلية/",
            "official",
        ),
    )
    sources: dict[str, Source] = {}
    for sid, owner, title, locator, classification in source_specs:
        row = _shared(
            Source,
            {"semantic_id": sid},
            {
                "authority_id": owner.pk,
                "title": title,
                "locator": locator,
                "classification": classification,
                "retrieved_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
            },
        )
        assert isinstance(row, Source)
        sources[sid] = row

    checklist_specs: tuple[tuple[Any, ...], ...] = (
        (
            "passport.requirement.national_id",
            "بطاقة رقم قومي سارية وبياناتها الحالية محدثة",
            "Valid National ID with current recorded data",
            {"op": "gte", "fact": "age_years_on_evaluation_date", "value": 15},
            "national_id",
            1,
            10,
            "EL-MOI-REQ-01",
            "بطاقة الرقم القومي لمن بلغت أعمارهم 15 سنة",
        ),
        (
            "passport.requirement.birth_certificate",
            "شهادة ميلاد مميكنة تحمل الرقم القومي",
            "Machine-readable birth certificate carrying the national number",
            {"op": "lt", "fact": "age_years_on_evaluation_date", "value": 15},
            "birth_certificate",
            1,
            20,
            "EL-MOI-REQ-02",
            "شهادة الميلاد المميكنة لمن هم دون 15 سنة",
        ),
        (
            "passport.requirement.student_enrollment",
            "شهادة قيد دراسي عن العام الدراسي الحالي",
            "Enrollment certificate for the current academic year",
            _eq("is_student", True),
            "student_enrollment_certificate",
            1,
            30,
            "EL-MOI-REQ-03",
            "شهادة القيد الدراسي للعام الحالي",
        ),
        (
            "passport.requirement.military_status",
            "مستند يثبت الموقف من التجنيد",
            "Military-status document",
            _all(
                _eq("sex", "male"),
                {"op": "gte", "fact": "birth_date", "value": {"$date": "1941-03-18"}},
                {"op": "gte", "fact": "age_years_on_evaluation_date", "value": 19},
            ),
            "military_status_document",
            1,
            40,
            "EL-MOI-REQ-04",
            "مستند التجنيد",
        ),
        (
            "passport.requirement.photos",
            "3 صور شخصية ملونة حديثة بخلفية بيضاء مقاس 4×6",
            "Three recent colour 4×6 photos with a white background",
            {},
            "passport_photo",
            3,
            50,
            "EL-MOI-REQ-05",
            "ثلاث صور شخصية ملونة حديثة خلفية بيضاء مقاس 4×6",
        ),
        (
            "passport.requirement.originals_and_copy",
            "أصول المستندات وصورة منها للمطابقة",
            "Originals plus a copy for verification",
            {},
            "supporting_documents",
            1,
            60,
            "EL-MOI-REQ-06",
            "أصول المستندات وصورة منها",
        ),
    )
    for sid, ar, en, rule, doc_id, qty, order, eid, passage in checklist_specs:
        document = _shared(DocumentType, {"semantic_id": doc_id}, {"name_ar": ar, "name_en": en})
        item = _claim(
            ChecklistItem,
            version,
            {
                "semantic_id": sid,
                "text_ar": ar,
                "text_en": en,
                "classification": "official_requirement",
                "document_type_id": document.pk,
                "quantity": qty,
                "display_order": order,
                "applicability": rule,
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            },
        )
        _evidence("checklist_item", item, eid, passage, (sources["SRC-MOI-PASSPORT-REQ"],))
    previous_doc = _shared(
        DocumentType,
        {"semantic_id": "previous_passport"},
        {"name_ar": "جواز السفر السابق", "name_en": "Previous passport"},
    )
    previous = _claim(
        ChecklistItem,
        version,
        {
            "semantic_id": "passport.requirement.previous_passport",
            "text_ar": "جواز السفر السابق المنتهي أو ممتلئ الصفحات",
            "text_en": "Previous expired or page-full passport",
            "classification": "candidate",
            "document_type_id": previous_doc.pk,
            "display_order": 70,
            "applicability": {
                "op": "in",
                "fact": "existing_passport_state",
                "value": ["expired", "pages_full"],
            },
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "needs_reverification",
        },
    )
    for eid, src, passage, state in (
        (
            "EL-PSM-SERVICE-01",
            "SRC-PSM-RENEWAL-SERVICE",
            "Expired or page-full passport replacement service",
            "current",
        ),
        (
            "EL-HIST-OLDPASS-01",
            "SRC-HISTORIC-GOV-PASSPORT",
            "Old passport is brought for renewal",
            "stale",
        ),
        (
            "EL-MFA-CONSULAR-01",
            "SRC-MFA-CONSULAR-PASSPORT",
            "Previous passport is required for consular renewal",
            "current",
        ),
    ):
        _evidence(
            "checklist_item",
            previous,
            eid,
            passage,
            (sources[src],),
            state=state,
            support="context",
        )

    step_specs = (
        (
            "passport.step.obtain_form_29",
            "الحصول على نموذج 29 جوازات مميكن مجانًا",
            "Obtain machine-readable Passport Form 29 free of charge",
            "prepare-at-office",
            10,
            10,
            "EL-MOI-PROCESS-01",
            "نموذج 29 جوازات مميكن مجاناً",
            ("SRC-MOI-PASSPORT-REQ",),
        ),
        (
            "passport.step.complete_form",
            "استيفاء بيانات الصفحة الأولى من النموذج بمعرفة صاحب الشأن",
            "Complete the first page of the form with the applicant’s information",
            "prepare-at-office",
            10,
            20,
            "EL-MOI-PROCESS-02",
            "Complete the first page of the form",
            ("SRC-MOI-PASSPORT-REQ",),
        ),
        (
            "passport.step.submit_and_pay",
            "تقديم الطلب والمستندات وسداد الرسم في نقطة الخدمة المختصة",
            (
                "Submit the application/documents and pay the applicable fee at the resolved "
                "Service Point"
            ),
            "submit",
            20,
            30,
            "EL-MOI-ROUTING-01",
            "Submit at the competent service point",
            ("SRC-MOI-OFFICE-DIRECTORY", "SRC-MOI-ACCELERATED"),
        ),
    )
    for sid, ar, en, phase, po, slot, eid, passage, source_ids in step_specs:
        step = _claim(
            Step,
            version,
            {
                "semantic_id": sid,
                "text_ar": ar,
                "text_en": en,
                "phase": phase,
                "phase_order": po,
                "slot": slot,
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            },
        )
        _evidence("step", step, eid, passage, tuple(sources[x] for x in source_ids))
        if sid == "passport.step.submit_and_pay":
            _evidence("step", step, "EL-MOI-FEE-01", "705 جنيه", (sources["SRC-MOI-PASSPORT-REQ"],))

    warning_specs = (
        (
            "passport.warning.personal_document",
            "جواز السفر المقروء آليًا شخصي ولا تُضاف إليه الزوجة أو الأبناء.",
            "The machine-readable passport is personal; a spouse or children are not added to it.",
            "info",
            "administrative",
            "general",
            "EL-MOI-PASSPORT-NATURE-01",
            "Machine-readable passport is personal",
        ),
        (
            "passport.warning.validity",
            "مدة الصلاحية القياسية المنشورة حاليًا سبع سنوات.",
            "The currently published standard validity is seven years.",
            "info",
            "administrative",
            "general",
            "EL-MOI-VALIDITY-01",
            "سبع سنوات",
        ),
        (
            "passport.warning.regenerate",
            "أعد التحقق من الخطة قبل التوجه مباشرة لأن الرسوم ونقاط الخدمة والتعليمات قد تتغير.",
            (
                "Re-check the plan immediately before acting because fees, Service Points and "
                "instructions can change."
            ),
            "important",
            "product",
            "regeneration",
            None,
            None,
        ),
        (
            "passport.warning.guidance_not_decision",
            "هذه إرشادات مبنية على مصادر منشورة وليست قرارًا ملزمًا من الجهة الحكومية.",
            "This is source-backed guidance, not a binding decision by the government authority.",
            "important",
            "product",
            "limitation",
            None,
            None,
        ),
    )
    for order, spec in enumerate(warning_specs, 1):
        sid, ar, en, severity, kind, role, warning_eid, passage = spec
        warning = _claim(
            Warning,
            version,
            {
                "semantic_id": sid,
                "text_ar": ar,
                "text_en": en,
                "severity": severity,
                "kind": kind,
                "role": role,
                "display_order": order,
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            },
        )
        if warning_eid:
            _evidence(
                "warning",
                warning,
                warning_eid,
                cast(str, passage),
                (sources["SRC-MOI-PASSPORT-REQ"],),
            )

    fee_specs: tuple[tuple[Any, ...], ...] = (
        (
            "passport.fee.base",
            "رسم إصدار جواز السفر المقروء آليًا",
            "Machine-readable passport base fee",
            705,
            {},
            "EL-MOI-FEE-01",
            "SRC-MOI-PASSPORT-REQ",
            "705 جنيه",
        ),
        (
            "passport.fee.urgent_service",
            "رسم إضافي للخدمة العاجلة",
            "Additional urgent-service fee",
            100,
            _eq("service_level", "urgent"),
            "EL-MOI-URGENT-01",
            "SRC-MOI-ACCELERATED",
            "Additional fee 100 EGP; next working day",
        ),
        (
            "passport.fee.premium_service",
            "رسم إضافي للخدمة المميزة",
            "Additional premium-service fee",
            500,
            _eq("service_level", "premium"),
            "EL-MOI-PREMIUM-01",
            "SRC-MOI-ACCELERATED",
            "Additional fee 500 EGP; same day",
        ),
    )
    for order, (sid, ar, en, amount, rule, eid, src, passage) in enumerate(fee_specs, 1):
        fee = _claim(
            Fee,
            version,
            {
                "semantic_id": sid,
                "text_ar": ar,
                "text_en": en,
                "value_state": "known",
                "amount": amount,
                "currency": "EGP",
                "fee_type": "government_fee" if order == 1 else "optional_service_fee",
                "display_order": order,
                "applicability": rule,
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            },
        )
        _evidence("fee", fee, eid, passage, (sources[src],))

    point = _shared(
        ServicePoint,
        {"semantic_id": "sp.giza_passport_office"},
        {"name_ar": "قسم جوازات الجيزة", "name_en": "Giza Passport Office"},
    )
    material = _shared(
        ServicePointVersion,
        {"semantic_id": "spv.giza_passport_office.research-2026-08-25"},
        {
            "service_point_id": point.pk,
            "address_ar": "مبنى قسم شرطة الجيزة، شارع البحر الأعظم",
            "address_en": "Giza Police Department building, Bahr El-Azam Street",
            "availability": "available",
            "effective_from": RESEARCH_DATE,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    association = _claim(
        ProcedureServicePointAssociation,
        version,
        {
            "semantic_id": "spa.passport_renewal.giza_standard",
            "service_point_version_id": material.pk,
            "applicability": _all(
                _eq("service_level", "standard"), _eq("residence_police_jurisdiction", "giza")
            ),
            "effective_from": RESEARCH_DATE,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "service_point_version",
        material,
        "EL-MOI-GIZA-01",
        "Giza Passport Office at the Giza Police Department building on Bahr El-Azam Street",
        (sources["SRC-MOI-OFFICE-DIRECTORY"],),
    )
    _evidence(
        "procedure_service_point_association",
        association,
        "EL-MOI-ROUTING-01",
        "Published territorial coverage includes Giza",
        (sources["SRC-MOI-OFFICE-DIRECTORY"],),
    )

    ProcedureVersionReviewPolicy.objects.create(
        procedure_version=version, author=author, military_risk=True
    )

    common = {
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
    adult_checklist = [
        "passport.requirement.national_id",
        "passport.requirement.photos",
        "passport.requirement.originals_and_copy",
    ]
    child_checklist = [
        "passport.requirement.birth_certificate",
        "passport.requirement.photos",
        "passport.requirement.originals_and_copy",
    ]
    military_checklist = [
        "passport.requirement.national_id",
        "passport.requirement.military_status",
        "passport.requirement.photos",
        "passport.requirement.originals_and_copy",
    ]
    plan = {
        "procedure_version_id": VERSION_ID,
        "checklist_item_ids": adult_checklist,
        "fee_ids": ["passport.fee.base"],
        "routing_status": "resolved",
        "routing_association_ids": ["spa.passport_renewal.giza_standard"],
    }
    unsupported = {"reason": "no_matching_researched_procedure"}
    scenarios = (
        ("passport.positive.adult_expired_standard", "positive", common, "plan", plan),
        (
            "passport.negative.first_issuance",
            "negative",
            {**common, "existing_passport_state": "none"},
            "inconclusive",
            unsupported,
        ),
        (
            "passport.negative.lost",
            "negative",
            {**common, "existing_passport_state": "lost"},
            "inconclusive",
            unsupported,
        ),
        (
            "passport.negative.damaged",
            "negative",
            {**common, "existing_passport_state": "damaged"},
            "inconclusive",
            unsupported,
        ),
        (
            "passport.negative.outside_egypt",
            "negative",
            {**common, "application_location": "outside_egypt"},
            "inconclusive",
            unsupported,
        ),
        (
            "passport.unknown.citizenship",
            "unknown",
            {k: v for k, v in common.items() if k != "citizenship"},
            "next_question",
            {"question_id": "q.citizenship"},
        ),
        (
            "passport.unknown.application_location",
            "unknown",
            {k: v for k, v in common.items() if k != "application_location"},
            "next_question",
            {"question_id": "q.application_location"},
        ),
        (
            "passport.unknown.passport_state",
            "unknown",
            {k: v for k, v in common.items() if k != "existing_passport_state"},
            "next_question",
            {"question_id": "q.existing_passport_state"},
        ),
        (
            "passport.edge.turns_15",
            "supported_edge",
            {**common, "birth_date": "2011-08-25"},
            "plan",
            {**plan, "checklist_item_ids": adult_checklist},
        ),
        (
            "passport.edge.one_day_under_15",
            "supported_edge",
            {**common, "birth_date": "2011-08-26"},
            "plan",
            {**plan, "checklist_item_ids": child_checklist},
        ),
        (
            "passport.edge.male_turns_19",
            "supported_edge",
            {**common, "birth_date": "2007-08-25", "sex": "male"},
            "plan",
            {**plan, "checklist_item_ids": military_checklist},
        ),
        (
            "passport.edge.male_one_day_under_19",
            "supported_edge",
            {**common, "birth_date": "2007-08-26", "sex": "male"},
            "plan",
            plan,
        ),
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
        (
            "passport.student.unknown",
            "unknown",
            {k: v for k, v in common.items() if k != "is_student"},
            "inconclusive",
            {"reason": "checklist_applicability_unknown"},
        ),
        (
            "passport.fee.urgent",
            "positive",
            {**common, "service_level": "urgent"},
            "plan",
            {
                **plan,
                "fee_ids": ["passport.fee.base", "passport.fee.urgent_service"],
                "routing_status": "resolved",
                "routing_association_ids": [],
            },
        ),
        (
            "passport.fee.premium",
            "positive",
            {**common, "service_level": "premium"},
            "plan",
            {
                **plan,
                "fee_ids": ["passport.fee.base", "passport.fee.premium_service"],
                "routing_status": "resolved",
                "routing_association_ids": [],
            },
        ),
        (
            "passport.routing.omitted_district",
            "unknown",
            {k: v for k, v in common.items() if k != "residence_police_jurisdiction"},
            "plan",
            {**plan, "routing_status": "unresolved", "routing_association_ids": []},
        ),
        (
            "passport.routing.unresearched_district",
            "supported_edge",
            {**common, "residence_police_jurisdiction": "unresearched"},
            "plan",
            {**plan, "routing_status": "resolved", "routing_association_ids": []},
        ),
        ("passport.locale.ar", "positive", common, "plan", plan),
    )
    for name, kind, facts, family, identifiers in scenarios:
        row = PlanningScenario(
            procedure_version=version,
            name=name,
            kind=kind,
            evaluation_context={
                "evaluation_date": "2026-08-25",
                "locale": "ar" if name == "passport.locale.ar" else "en",
            },
            source_facts=facts,
            expected_result_family=family,
            expected_identifiers=identifiers,
        )
        row.save()

    validate_core_catalog()
    return version


__all__ = ("RESEARCH_DATE", "VERSION_ID", "import_passport_renewal")
