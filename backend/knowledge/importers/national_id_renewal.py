"""Deterministic production import for researched ordinary domestic National ID renewal.

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
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceContradiction,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scenarios import PlanningScenario, planning_behavior_signature
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.services import (
    save_candidate,
    set_contradiction_facts,
    set_evidence_link_sources,
    set_question_resolved_facts,
    validate_core_catalog,
)

VERSION_ID = "ordinary_domestic_national_id_renewal.research-2026-08-26"
RESEARCH_DATE = date(2026, 8, 26)
SHORT_REVERIFY = RESEARCH_DATE + timedelta(days=30)


def _eq(fact: str, value: object) -> dict[str, object]:
    return {"op": "eq", "fact": fact, "value": value}


def _all(*children: dict[str, object]) -> dict[str, object]:
    return {"op": "all", "children": list(children)}


def _exists(fact: str) -> dict[str, object]:
    return {"op": "exists", "fact": fact}


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
    _expected(
        row,
        {
            "kind": expected.kind,
            "enum_values": list(expected.enum_values),
            "minimum": expected.minimum,
            "derived": expected.derived,
        },
        key,
    )
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
    location: str,
    context: str,
    sources: tuple[Source, ...],
    *,
    state: str = "current",
    support: str = "supports",
) -> EvidenceLink:
    link = EvidenceLink(
        semantic_id=semantic_id,
        **{owner_field: owner},
        passage=passage,
        location=location,
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


def _verify_existing(version: ProcedureVersion) -> None:
    expected_ids = {
        ChecklistItem: {
            "nid.requirement.renew_after_expiry",
            "nid.requirement.previous_card",
        },
        Step: {
            "nid.step.apply_for_renewal",
            "nid.step.resolve_service_location",
        },
        Warning: {
            "nid.warning.deadline",
            "nid.warning.changed_data",
            "nid.warning.recheck",
        },
        Fee: {"nid.fee.ordinary"},
    }
    for model, semantic_ids in expected_ids.items():
        actual = set(
            cast(Any, model)
            .objects.filter(procedure_version=version)
            .values_list("semantic_id", flat=True)
        )
        if actual != semantic_ids:
            raise ValidationError(
                f"{VERSION_ID}: semantic aggregate conflict for {model.__name__}."
            )
    if version.eligibility_bases.exists() or version.dependencies.exists():
        raise ValidationError(f"{VERSION_ID}: unexpected Eligibility Basis or dependency.")
    if version.service_point_associations.exists():
        raise ValidationError(f"{VERSION_ID}: exact routing must remain unresolved.")

    current_signature = planning_behavior_signature(version)
    scenario_signatures = set(
        PlanningScenario.objects.filter(procedure_version=version).values_list(
            "behavior_signature", flat=True
        )
    )
    if scenario_signatures != {current_signature}:
        raise ValidationError(f"{VERSION_ID}: semantic conflict in planning behavior.")

    fee = Fee.objects.get(procedure_version=version, semantic_id="nid.fee.ordinary")
    _expected(
        fee,
        {
            "value_state": Fee.ValueState.UNKNOWN,
            "amount": None,
            "minimum_amount": None,
            "maximum_amount": None,
            "currency": "EGP",
            "verification_state": "unknown",
        },
        fee.semantic_id,
    )
    previous = ChecklistItem.objects.get(
        procedure_version=version, semantic_id="nid.requirement.previous_card"
    )
    _expected(
        previous,
        {
            "classification": ChecklistItem.Classification.CANDIDATE,
            "verification_state": "needs_reverification",
        },
        previous.semantic_id,
    )


@transaction.atomic
def import_national_id_renewal(*, author: models.Model) -> ProcedureVersion:
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
        existing_procedure = Procedure.objects.get(
            semantic_id="ordinary_domestic_national_id_renewal"
        )
        _expected(
            existing,
            {
                "procedure_id": existing_procedure.pk,
                "text_ar": "تجديد بطاقة الرقم القومي المنتهية داخل مصر دون تغيير البيانات",
                "text_en": (
                    "Renew an expired Egyptian National ID inside Egypt without changing its "
                    "recorded data"
                ),
            },
            VERSION_ID,
        )
        _verify_existing(existing)
        validate_core_catalog()
        return existing

    service = _shared(
        Service,
        {"semantic_id": "get_egyptian_national_id"},
        {
            "text_ar": "الحصول على بطاقة رقم قومي مصرية",
            "text_en": "Get an Egyptian National ID",
            "is_active": True,
        },
    )
    assert isinstance(service, Service)
    procedure = _shared(
        Procedure,
        {"semantic_id": "ordinary_domestic_national_id_renewal"},
        {
            "text_ar": "تجديد بطاقة الرقم القومي المنتهية داخل مصر دون تغيير البيانات",
            "text_en": (
                "Renew an expired Egyptian National ID inside Egypt without changing its "
                "recorded data"
            ),
            "primary_service_id": service.pk,
        },
    )
    assert isinstance(procedure, Procedure)

    boundary = _all(
        _eq("application_location", "inside_egypt"),
        _eq("national_id_possession_state", "held"),
        _eq("national_id_data_change_kind", "none"),
        _eq("card_expired_before_evaluation_date", True),
    )
    candidate = ServiceProcedureCandidate.objects.filter(
        service=service, procedure=procedure
    ).first()
    if candidate is None:
        save_candidate(
            ServiceProcedureCandidate(
                service=service,
                procedure=procedure,
                selection_predicate=boundary,
            )
        )
    else:
        _expected(candidate, {"selection_predicate": boundary}, str(candidate))

    question_specs = (
        (
            10,
            "q.nid.application_location",
            "application_location",
            "هل ستجري معاملة بطاقة الرقم القومي من داخل مصر أم من خارجها؟",
            "Will you handle the National ID transaction from inside or outside Egypt?",
        ),
        (
            20,
            "q.nid.possession_state",
            "national_id_possession_state",
            "ما حالة بطاقة الرقم القومي الحالية لديك؟",
            "What is the status of your current National ID card?",
        ),
        (
            30,
            "q.nid.data_change_kind",
            "national_id_data_change_kind",
            "هل تحتاج إلى تغيير أي بيانات مسجلة على البطاقة أو في حالتك المدنية؟",
            "Do you need to change any data recorded on the card or in your civil-status record?",
        ),
        (
            40,
            "q.nid.expiry_date",
            "national_id_expiry_date",
            "ما تاريخ انتهاء بطاقة الرقم القومي الحالية؟",
            "What is the expiry date printed on your current National ID?",
        ),
        (
            50,
            "q.nid.residence_governorate",
            "residence_governorate",
            "ما محافظة محل إقامتك؟",
            "What is your governorate of residence?",
        ),
        (
            60,
            "q.nid.residence_district",
            "residence_district",
            "ما المركز أو القسم التابع له محل إقامتك؟",
            "Which district or centre covers your residence?",
        ),
    )
    facts: dict[str, FactDefinition] = {}
    for priority, semantic_id, fact_key, ar, en in question_specs:
        fact = _published_fact(fact_key)
        facts[fact_key] = fact
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
        if not question.resolved_fact_links.exists():
            set_question_resolved_facts(question, (fact,))
        elif question.resolved_fact_keys != (fact.key,):
            raise ValidationError(f"{semantic_id}: semantic conflict in resolved Facts.")

    _published_fact("card_expired_before_evaluation_date")
    _published_fact("renewal_deadline_date")
    _published_fact("renewal_deadline_passed")

    contradiction_condition = _all(
        _eq("national_id_possession_state", "none"),
        _exists("national_id_expiry_date"),
    )
    contradiction = ServiceContradiction.objects.filter(
        semantic_id="nid.no_current_card_with_expiry_date"
    ).first()
    if contradiction is None:
        contradiction = ServiceContradiction.objects.create(
            semantic_id="nid.no_current_card_with_expiry_date",
            service=service,
            condition=contradiction_condition,
        )
        set_contradiction_facts(
            contradiction,
            (facts["national_id_possession_state"], facts["national_id_expiry_date"]),
        )
    else:
        _expected(
            contradiction,
            {"service_id": service.pk, "condition": contradiction_condition},
            contradiction.semantic_id,
        )
        if contradiction.fact_keys != (
            "national_id_possession_state",
            "national_id_expiry_date",
        ):
            raise ValidationError(
                f"{contradiction.semantic_id}: semantic conflict in declared Facts."
            )

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

    official_gazette = _shared(
        Authority,
        {"semantic_id": "authority.official_gazette.egypt"},
        {
            "name_ar": "الجريدة الرسمية المصرية",
            "name_en": "Egyptian Official Gazette",
        },
    )
    civil_status = _shared(
        Authority,
        {"semantic_id": "authority.moi.civil_status"},
        {
            "name_ar": "وزارة الداخلية — قطاع الأحوال المدنية",
            "name_en": "Egyptian Ministry of Interior — Civil Status Sector",
        },
    )
    lawyer_egypt = _shared(
        Authority,
        {"semantic_id": "authority.lawyer_egypt"},
        {"name_ar": "موقع محامي مصر", "name_en": "Lawyer Egypt"},
    )
    sis = _shared(
        Authority,
        {"semantic_id": "authority.sis.egypt"},
        {"name_ar": "الهيئة العامة للاستعلامات", "name_en": "State Information Service"},
    )
    assert isinstance(official_gazette, Authority)
    assert isinstance(civil_status, Authority)
    assert isinstance(lawyer_egypt, Authority)
    assert isinstance(sis, Authority)

    source_specs: tuple[tuple[Any, ...], ...] = (
        (
            "SRC-CIVIL-LAW-143-GAZETTE",
            official_gazette,
            "Civil Status Law No. 143 of 1994",
            "https://manshurat.org/node/31633",
            "official",
            date(1994, 6, 9),
            date(1994, 6, 10),
        ),
        (
            "SRC-CIVIL-LAW-CONSOLIDATED-2022",
            lawyer_egypt,
            "Civil Status Law No. 143 of 1994 consolidated through 2022",
            "https://lawyeregypt.net/قانون-الاحوال-المدنية-المصري-رقم-143-لسن/",
            "secondary",
            None,
            None,
        ),
        (
            "SRC-PSM-CIVIL-STATUS-SERVICES",
            civil_status,
            "Civil Status services directory",
            "https://psm.gov.eg/providers/1/services",
            "official",
            None,
            None,
        ),
        (
            "SRC-SIS-CONSULAR-NID-2026",
            sis,
            "Consular National ID transactions guide",
            "https://sis.gov.eg/ar/بوابة-معلومات-للمصريين-بالخارج/الخدمات-الحكومية/دليل-المعاملات-القنصلية/",
            "official",
            date(2026, 6, 1),
            None,
        ),
    )
    sources: dict[str, Source] = {}
    for (
        sid,
        authority,
        title,
        locator,
        classification,
        published_on,
        effective_from,
    ) in source_specs:
        source = _shared(
            Source,
            {"semantic_id": sid},
            {
                "authority_id": authority.pk,
                "title": title,
                "locator": locator,
                "classification": classification,
                "published_on": published_on,
                "effective_from": effective_from,
                "retrieved_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
            },
        )
        assert isinstance(source, Source)
        sources[sid] = source

    deadline_requirement = _claim(
        ChecklistItem,
        version,
        {
            "semantic_id": "nid.requirement.renew_after_expiry",
            "text_ar": "يجب التقدم لتجديد البطاقة خلال ثلاثة أشهر من انتهاء مدة سريانها",
            "text_en": "Apply to renew within three months from expiry",
            "classification": ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            "display_order": 10,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "checklist_item",
        deadline_requirement,
        "EL-CIVIL-LAW-52",
        "خلال ثلاثة أشهر من تاريخ انتهاء مدة سريانها",
        "Civil Status Law, Article 52; Official Gazette scan page 18",
        "National ID cardholder renewal; original Article 52 wording.",
        (
            sources["SRC-CIVIL-LAW-143-GAZETTE"],
            sources["SRC-CIVIL-LAW-CONSOLIDATED-2022"],
        ),
    )

    previous_card = _claim(
        ChecklistItem,
        version,
        {
            "semantic_id": "nid.requirement.previous_card",
            "text_ar": "البطاقة الحالية/القديمة",
            "text_en": "Current/previous card",
            "classification": ChecklistItem.Classification.CANDIDATE,
            "display_order": 20,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "needs_reverification",
        },
    )
    _evidence(
        "checklist_item",
        previous_card,
        "EL-SIS-CONSULAR-PREVIOUS-CARD",
        "أصل وصورة البطاقة القديمة",
        "State Information Service consular transactions guide",
        "Consular/overseas National ID renewal; research lead only, not domestic proof.",
        (sources["SRC-SIS-CONSULAR-NID-2026"],),
        support="context",
    )

    apply_step = _claim(
        Step,
        version,
        {
            "semantic_id": "nid.step.apply_for_renewal",
            "text_ar": "التقدم بطلب تجديد البطاقة خلال المدة القانونية بعد انتهاء سريانها",
            "text_en": "Apply for renewal within the legal period after expiry",
            "phase": "submit",
            "phase_order": 10,
            "slot": 10,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "step",
        apply_step,
        "EL-CIVIL-LAW-52",
        "خلال ثلاثة أشهر من تاريخ انتهاء مدة سريانها",
        "Civil Status Law, Article 52; Official Gazette scan page 18",
        "National ID cardholder renewal application deadline.",
        (
            sources["SRC-CIVIL-LAW-143-GAZETTE"],
            sources["SRC-CIVIL-LAW-CONSOLIDATED-2022"],
        ),
    )

    route_step = _claim(
        Step,
        version,
        {
            "semantic_id": "nid.step.resolve_service_location",
            "text_ar": "تحديد جهة الخدمة وفق المحافظة والمنطقة أو قناة خدمة حالية موثقة",
            "text_en": (
                "Resolve the service location from governorate/district or another currently "
                "evidenced channel"
            ),
            "phase": "route",
            "phase_order": 20,
            "slot": 20,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "step",
        route_step,
        "EL-PSM-NID-SERVICE",
        "Ordinary National ID service requires governorate and area selection",
        "Public Services Guide ordinary National ID service listing",
        (
            "Current directory behavior; governorate/area input is exposed, but no nationwide "
            "office mapping is asserted."
        ),
        (sources["SRC-PSM-CIVIL-STATUS-SERVICES"],),
    )

    deadline_warning = _claim(
        Warning,
        version,
        {
            "semantic_id": "nid.warning.deadline",
            "text_ar": "يجب تقديم طلب التجديد خلال ثلاثة أشهر من تاريخ انتهاء مدة سريان البطاقة.",
            "text_en": "Apply for renewal within three months from the card's expiry date.",
            "severity": "important",
            "kind": "administrative",
            "role": "general",
            "display_order": 1,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "warning",
        deadline_warning,
        "EL-CIVIL-LAW-52",
        "خلال ثلاثة أشهر من تاريخ انتهاء مدة سريانها",
        "Civil Status Law, Article 52; Official Gazette scan page 18",
        "National ID cardholder renewal deadline.",
        (
            sources["SRC-CIVIL-LAW-143-GAZETTE"],
            sources["SRC-CIVIL-LAW-CONSOLIDATED-2022"],
        ),
    )

    changed_data_warning = _claim(
        Warning,
        version,
        {
            "semantic_id": "nid.warning.changed_data",
            "text_ar": (
                "إذا تغيرت بيانات البطاقة أو الحالة المدنية فقد تحتاج إلى مسار تحديث بيانات "
                "مختلف عن التجديد العادي."
            ),
            "text_en": (
                "If card or civil-status data changed, you may need a data-update Procedure "
                "rather than ordinary renewal."
            ),
            "severity": "important",
            "kind": "administrative",
            "role": "limitation",
            "display_order": 2,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "warning",
        changed_data_warning,
        "EL-CIVIL-LAW-53",
        "خلال ثلاثة أشهر من تاريخ التغيير",
        "Civil Status Law, Article 53; Official Gazette scan page 18",
        "Changed card/civil-status data uses a distinct update route.",
        (
            sources["SRC-CIVIL-LAW-143-GAZETTE"],
            sources["SRC-CIVIL-LAW-CONSOLIDATED-2022"],
        ),
    )
    _evidence(
        "warning",
        changed_data_warning,
        "EL-PSM-DATA-CHANGE-SERVICES",
        "تغيير بيانات محل الإقامة",
        "Public Services Guide Civil Status service directory",
        "Residence, profession and marital-status changes are exposed as distinct services.",
        (sources["SRC-PSM-CIVIL-STATUS-SERVICES"],),
    )

    _claim(
        Warning,
        version,
        {
            "semantic_id": "nid.warning.recheck",
            "text_ar": (
                "أعد التحقق من الخطة قبل التوجه لأن الرسوم ومنافذ الخدمة والتعليمات التشغيلية "
                "قد تتغير."
            ),
            "text_en": (
                "Re-check the plan before acting because fees, service channels and operational "
                "instructions can change."
            ),
            "severity": "important",
            "kind": "product",
            "role": "regeneration",
            "display_order": 3,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )

    _claim(
        Fee,
        version,
        {
            "semantic_id": "nid.fee.ordinary",
            "text_ar": "رسم التجديد العادي",
            "text_en": "Ordinary renewal fee",
            "value_state": Fee.ValueState.UNKNOWN,
            "currency": "EGP",
            "fee_type": "government_fee",
            "display_order": 1,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "unknown",
        },
    )

    ProcedureVersionReviewPolicy.objects.create(procedure_version=version, author=author)

    common = {
        "application_location": "inside_egypt",
        "national_id_possession_state": "held",
        "national_id_data_change_kind": "none",
        "national_id_expiry_date": "2026-05-01",
        "residence_governorate": "giza",
        "residence_district": "dokki",
    }
    plan = {
        "procedure_version_id": VERSION_ID,
        "checklist_item_ids": ["nid.requirement.renew_after_expiry"],
        "step_ids": ["nid.step.apply_for_renewal", "nid.step.resolve_service_location"],
        "warning_ids": [
            "nid.warning.deadline",
            "nid.warning.changed_data",
            "nid.warning.recheck",
        ],
        "fee_ids": ["nid.fee.ordinary"],
        "routing_status": "unresolved",
        "routing_association_ids": [],
    }
    unsupported = {"reason": "no_matching_researched_procedure"}
    scenarios: tuple[tuple[Any, ...], ...] = (
        ("nid.positive.expired_held_no_changes", "positive", common, "plan", plan, []),
        (
            "nid.negative.first_issuance",
            "negative",
            {
                "application_location": "inside_egypt",
                "national_id_possession_state": "none",
            },
            "inconclusive",
            unsupported,
            [],
        ),
        (
            "nid.negative.lost_card",
            "negative",
            {**common, "national_id_possession_state": "lost"},
            "inconclusive",
            unsupported,
            [],
        ),
        (
            "nid.negative.damaged_card",
            "negative",
            {**common, "national_id_possession_state": "damaged"},
            "inconclusive",
            unsupported,
            [],
        ),
        (
            "nid.negative.data_change",
            "negative",
            {**common, "national_id_data_change_kind": "residence"},
            "inconclusive",
            unsupported,
            [],
        ),
        (
            "nid.negative.outside_egypt",
            "negative",
            {**common, "application_location": "outside_egypt"},
            "inconclusive",
            unsupported,
            [],
        ),
        (
            "nid.unknown.possession_state",
            "unknown",
            {"application_location": "inside_egypt"},
            "next_question",
            {"question_id": "q.nid.possession_state"},
            [],
        ),
        (
            "nid.unknown.data_change",
            "unknown",
            {
                "application_location": "inside_egypt",
                "national_id_possession_state": "held",
            },
            "next_question",
            {"question_id": "q.nid.data_change_kind"},
            [],
        ),
        (
            "nid.unknown.expiry_date",
            "unknown",
            {
                "application_location": "inside_egypt",
                "national_id_possession_state": "held",
                "national_id_data_change_kind": "none",
            },
            "next_question",
            {"question_id": "q.nid.expiry_date"},
            [],
        ),
        (
            "nid.contradictory.no_card_with_expiry",
            "contradictory",
            {
                "application_location": "inside_egypt",
                "national_id_possession_state": "none",
                "national_id_expiry_date": "2026-05-01",
            },
            "invalid",
            {},
            ["contradictory_facts", "contradictory_facts"],
        ),
        (
            "nid.edge.not_yet_expired",
            "negative",
            {**common, "national_id_expiry_date": "2026-09-10"},
            "inconclusive",
            unsupported,
            [],
        ),
        (
            "nid.edge.deadline_exact_three_calendar_months",
            "supported_edge",
            {**common, "national_id_expiry_date": "2026-05-26"},
            "plan",
            plan,
            [],
        ),
        (
            "nid.edge.deadline_month_end_clamping",
            "supported_edge",
            {**common, "national_id_expiry_date": "2026-05-31"},
            "plan",
            plan,
            [],
            "2026-08-31",
        ),
        ("nid.locale.ar", "positive", common, "plan", plan, []),
    )
    for raw in scenarios:
        name, kind, source_facts, family, identifiers, diagnostics, *date_override = raw
        row = PlanningScenario(
            procedure_version=version,
            name=name,
            kind=kind,
            evaluation_context={
                "evaluation_date": date_override[0] if date_override else "2026-08-26",
                "locale": "ar" if name == "nid.locale.ar" else "en",
            },
            source_facts=source_facts,
            expected_result_family=family,
            expected_identifiers=identifiers,
            expected_diagnostics=diagnostics,
        )
        row.save()

    _verify_existing(version)
    validate_core_catalog()
    return version


__all__ = ("RESEARCH_DATE", "VERSION_ID", "import_national_id_renewal")
