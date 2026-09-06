"""Deterministic production import for researched temporary family exemption knowledge.

The importer transcribes the researched military family-exemption pack into production models.
It deliberately does not import the frozen prototype and never records review approvals or
publication metadata.
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
    EligibilityBasis,
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
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)
from knowledge.services import (
    save_candidate,
    set_contradiction_facts,
    set_evidence_link_sources,
    set_question_resolved_facts,
    validate_core_catalog,
)

HISTORICAL_VERSION_ID = "temporary_family_exemption_from_military_service.research-2026-03-24"
CURRENT_VERSION_ID = "temporary_family_exemption_from_military_service.research-2026-08-26"
VERSION_IDS = (HISTORICAL_VERSION_ID, CURRENT_VERSION_ID)
RESEARCH_DATE = date(2026, 8, 26)
AMENDMENT_PUBLICATION_DATE = date(2026, 3, 24)
AMENDMENT_EFFECTIVE_DATE = date(2026, 3, 25)
SHORT_REVERIFY = RESEARCH_DATE + timedelta(days=30)


def _eq(fact: str, value: object) -> dict[str, object]:
    return {"op": "eq", "fact": fact, "value": value}


def _in(fact: str, values: tuple[str, ...]) -> dict[str, object]:
    return {"op": "in", "fact": fact, "value": list(values)}


def _gt(fact: str, value: int) -> dict[str, object]:
    return {"op": "gt", "fact": fact, "value": value}


def _exists(fact: str) -> dict[str, object]:
    return {"op": "exists", "fact": fact}


def _all(*children: dict[str, object]) -> dict[str, object]:
    return {"op": "all", "children": list(children)}


def _any(*children: dict[str, object]) -> dict[str, object]:
    return {"op": "any", "children": list(children)}


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
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> EvidenceLink:
    link = EvidenceLink(
        semantic_id=semantic_id,
        **{owner_field: owner},
        passage=passage,
        location=location,
        applicability_context=context,
        effective_from=effective_from,
        effective_to=effective_to,
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


def _version_spec(amended: bool) -> tuple[str, date | None, date | None]:
    if amended:
        return CURRENT_VERSION_ID, AMENDMENT_EFFECTIVE_DATE, None
    return HISTORICAL_VERSION_ID, None, AMENDMENT_PUBLICATION_DATE


def _verify_version(version: ProcedureVersion, *, amended: bool) -> None:
    version_id, effective_from, effective_to = _version_spec(amended)
    _expected(
        version,
        {
            "semantic_id": version_id,
            "text_ar": "طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية",
            "text_en": "Apply for temporary exemption from military service on a family ground",
            "applicability": _eq("application_location", "inside_egypt"),
            "effective_from": effective_from,
            "effective_to": effective_to,
        },
        version_id,
    )
    expected_ids = {
        EligibilityBasis: {
            "family.only_son_living_father",
            "family.support_father_or_incapable_brothers",
            "family.support_mother",
            "family.support_unmarried_sisters",
            "family.missing_war_or_terror_relative",
            "family.sibling_current_service",
        },
        ChecklistItem: {
            "mil.shared.supporting_documents",
            "mil.basis.only_son_living_father",
            "mil.basis.support_father_or_brothers",
            "mil.basis.support_mother",
            "mil.basis.support_unmarried_sisters",
            "mil.basis.missing_war_or_terror_relative",
            "mil.basis.sibling_current_service",
        },
        Step: {
            "mil.step.submit_supporting_documents",
            "mil.step.authority_review",
        },
        Warning: {
            "mil.warning.candidate_not_decision",
            "mil.warning.recheck",
        },
        Fee: {"mil.fee.current"},
        ProcedureServicePointAssociation: {
            "spa.mil.giza_region",
            "spa.mil.mansoura_region",
            "spa.mil.zagazig_region",
        },
    }
    for model, semantic_ids in expected_ids.items():
        actual = set(
            cast(Any, model)
            .objects.filter(procedure_version=version)
            .values_list("semantic_id", flat=True)
        )
        if actual != semantic_ids:
            raise ValidationError(
                f"{version_id}: semantic aggregate conflict for {model.__name__}."
            )
    if version.dependencies.exists():
        raise ValidationError(f"{version_id}: unexpected direct Procedure dependency.")

    bases = {
        row.semantic_id: row
        for row in EligibilityBasis.objects.filter(procedure_version=version).order_by("semantic_id")
    }
    for basis in bases.values():
        if cast(Any, basis).verification_state != "needs_reverification":
            raise ValidationError(f"{version_id}: all military Bases must remain untrusted.")
    missing = cast(Any, bases["family.missing_war_or_terror_relative"])
    expected_cause = (
        _any(
            _eq("missing_relative_cause", "war_operations"),
            _eq("missing_relative_cause", "terrorist_operations"),
        )
        if amended
        else _eq("missing_relative_cause", "war_operations")
    )
    expected_missing_qualification = _all(
        _eq("applicant_largest_eligible_relative_status", "authority_documented_yes"),
        _eq("missing_relative_alive_status", "missing"),
        expected_cause,
    )
    _expected(
        missing,
        {"qualification": expected_missing_qualification},
        f"{version_id}:family.missing_war_or_terror_relative",
    )

    policy = ProcedureVersionReviewPolicy.objects.get(procedure_version=version)
    _expected(
        policy,
        {
            "legal_risk": True,
            "military_risk": True,
            "custody_guardianship_risk": False,
            "contested_identity_risk": False,
        },
        f"{version_id}:review-policy",
    )
    signature = planning_behavior_signature(version)
    scenario_signatures = set(
        PlanningScenario.objects.filter(procedure_version=version).values_list(
            "behavior_signature", flat=True
        )
    )
    if scenario_signatures != {signature}:
        raise ValidationError(f"{version_id}: semantic conflict in planning behavior.")


def _create_version(
    *,
    procedure: Procedure,
    amended: bool,
    author: models.Model,
    sources: dict[str, Source],
    supporting_documents_type: DocumentType,
    routing_material: dict[str, ServicePointVersion],
) -> ProcedureVersion:
    version_id, effective_from, effective_to = _version_spec(amended)
    version = ProcedureVersion(
        semantic_id=version_id,
        procedure=procedure,
        text_ar="طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية",
        text_en="Apply for temporary exemption from military service on a family ground",
        applicability=_eq("application_location", "inside_egypt"),
        effective_from=effective_from,
        effective_to=effective_to,
    )
    version.full_clean()
    version.save()

    missing_qualification = _all(
        _eq("applicant_largest_eligible_relative_status", "authority_documented_yes"),
        _eq("missing_relative_alive_status", "missing"),
        (
            _any(
                _eq("missing_relative_cause", "war_operations"),
                _eq("missing_relative_cause", "terrorist_operations"),
            )
            if amended
            else _eq("missing_relative_cause", "war_operations")
        ),
    )
    missing_text_ar = (
        "أساس قريب مفقود بسبب العمليات الحربية أو الإرهابية"
        if amended
        else "أساس قريب مفقود بسبب العمليات الحربية"
    )
    missing_text_en = (
        "Missing-relative ground involving war or terrorist operations"
        if amended
        else "Missing-relative ground involving war operations"
    )
    basis_specs: tuple[tuple[Any, ...], ...] = (
        (
            "family.only_son_living_father",
            "الابن الوحيد لأبيه الحي",
            "Only son of a living father",
            _eq("father_alive", True),
            _eq("other_living_sons_of_father_count", 0),
            10,
            "EL-LAW127-ART7-II-A",
            "الابن الوحيد لأبيه الحي",
            "Official Gazette scan page 14, Article 7/Second(a)",
            "Original Law No. 127 of 1980; current-as-researched family ground.",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        (
            "family.support_father_or_incapable_brothers",
            "أساس إعالة الأب غير القادر على الكسب أو الصياغة المرتبطة بالإخوة غير القادرين",
            "Father/incapable-brother family-support ground",
            _eq("father_alive", True),
            _eq("father_unable_to_earn_status", "authority_documented_unable"),
            20,
            "EL-LAW127-ART7-II-B",
            "غير القادر على الكسب",
            "Official Gazette scan page 14, Article 7/Second(b)",
            "Only the researched father sub-route is modeled; incapable-brother semantics remain unresolved.",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        (
            "family.support_mother",
            "أساس إعالة الأم",
            "Mother family-support ground",
            {},
            _in(
                "mother_family_status",
                (
                    "widowed",
                    "irrevocably_divorced",
                    "husband_authority_documented_unable",
                ),
            ),
            30,
            "EL-LAW127-ART7-II-C",
            "إذا كانت أرملة",
            "Official Gazette scan page 14, Article 7/Second(c)",
            "Complete mother-support condition set remains specialist-sensitive.",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        (
            "family.support_unmarried_sisters",
            "أساس إعالة الأخت أو الأخوات غير المتزوجات",
            "Unmarried-sister family-support ground",
            {},
            _gt("unmarried_sisters_requiring_support_count", 0),
            40,
            "EL-LAW127-ART7-II-D",
            "غير المتزوجات",
            "Official Gazette scan page 14, Article 7/Second(d)",
            "Complete unmarried-sister support conditions remain specialist-sensitive.",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        (
            "family.missing_war_or_terror_relative",
            missing_text_ar,
            missing_text_en,
            _in(
                "missing_relative_category",
                ("officer", "volunteer", "conscript", "citizen"),
            ),
            missing_qualification,
            50,
            "EL-LAW2-2026-ART7-II-E" if amended else "EL-LAW127-ART7-II-E-HISTORIC",
            "بسبب العمليات الحربية أو الإرهابية" if amended else "بسبب العمليات الحربية",
            (
                "Law No. 2 of 2026, Article 7/Second(e) replacement text"
                if amended
                else "Official Gazette scan page 14, original Article 7/Second(e)"
            ),
            (
                "Current replacement clause effective 2026-03-25; specialist review required."
                if amended
                else "Historical pre-amendment wording, superseded from 2026-03-25."
            ),
            (
                (
                    "SRC-LAW2-2026-GAZETTE-METADATA",
                    "SRC-LAW2-2026-TEXT",
                    "SRC-PARLIAMENT-LAW2-2026",
                )
                if amended
                else ("SRC-LAW127-1980-GAZETTE",)
            ),
        ),
        (
            "family.sibling_current_service",
            "أساس وجود أخ في الخدمة الإلزامية أو استدعاء احتياط مؤهل",
            "Sibling currently in compulsory service or qualifying reserve recall",
            _in("sibling_service_status", ("compulsory_service", "reserve_recall")),
            _all(
                _eq(
                    "applicant_eldest_remaining_brother_status",
                    "authority_documented_yes",
                ),
                _eq("article7_third_exclusion_status", "none_documented"),
            ),
            60,
            "EL-LAW127-ART7-III",
            "إذا جند أحد الأخوين أو الاخوة",
            "Official Gazette scan pages 14–15, Article 7/Third",
            "Complete ordering and exclusion conditions remain specialist-sensitive.",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
    )
    bases: dict[str, EligibilityBasis] = {}
    for (
        semantic_id,
        text_ar,
        text_en,
        reachability,
        qualification,
        display_order,
        evidence_id,
        passage,
        location,
        context,
        source_ids,
    ) in basis_specs:
        basis = EligibilityBasis(
            procedure_version=version,
            semantic_id=semantic_id,
            text_ar=text_ar,
            text_en=text_en,
            reachability=reachability,
            qualification=qualification,
            display_order=display_order,
            verified_on=RESEARCH_DATE,
            reverify_on=SHORT_REVERIFY,
            verification_state="needs_reverification",
        )
        basis.full_clean()
        basis.save()
        bases[semantic_id] = basis
        _evidence(
            "eligibility_basis",
            basis,
            evidence_id,
            passage,
            location,
            context,
            tuple(sources[source_id] for source_id in source_ids),
            effective_from=AMENDMENT_EFFECTIVE_DATE if amended and display_order == 50 else None,
            effective_to=AMENDMENT_PUBLICATION_DATE if not amended and display_order == 50 else None,
        )

    shared = _claim(
        ChecklistItem,
        version,
        {
            "semantic_id": "mil.shared.supporting_documents",
            "text_ar": "تقديم المستندات المؤيدة لأحقية الطلب",
            "text_en": "Present documents supporting the claimed entitlement",
            "classification": ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            "document_type": supporting_documents_type,
            "display_order": 10,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "checklist_item",
        shared,
        "EL-MOD-SUPPORTING-DOCS",
        "بالمستندات التى تؤيد أحقيته",
        "Ministry of Defense recruitment operational announcement",
        "Current high-level instruction to support an exemption/postponement/exception claim; not a basis-specific list.",
        (sources["SRC-MOD-RECRUITMENT-OCT-2026"],),
    )

    claim_specs = (
        (
            "mil.basis.only_son_living_father",
            "الابن الوحيد لأبيه الحي",
            "Only son of a living father — candidate statutory ground",
            "family.only_son_living_father",
            "EL-LAW127-ART7-II-A",
        ),
        (
            "mil.basis.support_father_or_brothers",
            "أساس إعالة الأب أو الإخوة وفق المادة 7/ثانياً (ب)",
            "Father/incapable-brother support ground — candidate statutory ground",
            "family.support_father_or_incapable_brothers",
            "EL-LAW127-ART7-II-B",
        ),
        (
            "mil.basis.support_mother",
            "أساس إعالة الأم",
            "Mother support — candidate statutory ground",
            "family.support_mother",
            "EL-LAW127-ART7-II-C",
        ),
        (
            "mil.basis.support_unmarried_sisters",
            "أساس إعالة الأخوات غير المتزوجات",
            "Unmarried-sister support — candidate statutory ground",
            "family.support_unmarried_sisters",
            "EL-LAW127-ART7-II-D",
        ),
        (
            "mil.basis.missing_war_or_terror_relative",
            (
                "أساس القريب المفقود بسبب العمليات الحربية أو الإرهابية"
                if amended
                else "أساس القريب المفقود بسبب العمليات الحربية"
            ),
            (
                "Missing war/terror relative — candidate statutory ground"
                if amended
                else "Missing war-operation relative — candidate statutory ground"
            ),
            "family.missing_war_or_terror_relative",
            "EL-LAW2-2026-ART7-II-E" if amended else "EL-LAW127-ART7-II-E-HISTORIC",
        ),
        (
            "mil.basis.sibling_current_service",
            "أساس وجود أخ في الخدمة الحالية",
            "Sibling-current-service — candidate statutory ground",
            "family.sibling_current_service",
            "EL-LAW127-ART7-III",
        ),
    )
    for order, (semantic_id, text_ar, text_en, basis_id, evidence_id) in enumerate(
        claim_specs, start=2
    ):
        item = _claim(
            ChecklistItem,
            version,
            {
                "semantic_id": semantic_id,
                "text_ar": text_ar,
                "text_en": text_en,
                "classification": ChecklistItem.Classification.CANDIDATE,
                "display_order": order * 10,
                "scope": ChecklistItem.Scope.ELIGIBILITY_BASIS,
                "scope_reference": basis_id,
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "needs_reverification",
            },
        )
        basis_evidence = EvidenceLink.objects.get(eligibility_basis=bases[basis_id], semantic_id=evidence_id)
        _evidence(
            "checklist_item",
            item,
            evidence_id,
            basis_evidence.passage,
            basis_evidence.location,
            basis_evidence.applicability_context,
            tuple(link.source for link in basis_evidence.source_links.select_related("source").order_by("position")),
            effective_from=basis_evidence.effective_from,
            effective_to=basis_evidence.effective_to,
        )

    submit_step = _claim(
        Step,
        version,
        {
            "semantic_id": "mil.step.submit_supporting_documents",
            "text_ar": "تقديم المستندات المؤيدة للحالة إلى جهة التجنيد المختصة",
            "text_en": (
                "Submit supporting documents for the claimed status to the competent "
                "recruitment authority"
            ),
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
        submit_step,
        "EL-MOD-SUPPORTING-DOCS",
        "بالمستندات التى تؤيد أحقيته",
        "Ministry of Defense recruitment operational announcement",
        "Submit evidence supporting the claimed military-status entitlement.",
        (sources["SRC-MOD-RECRUITMENT-OCT-2026"],),
    )
    review_step = _claim(
        Step,
        version,
        {
            "semantic_id": "mil.step.authority_review",
            "text_ar": "تخضع الحالة للدراسة بواسطة المختصين لتحديد الاستحقاق",
            "text_en": "The case is reviewed by authority specialists to determine entitlement",
            "phase": "adjudicate",
            "phase_order": 20,
            "slot": 20,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _evidence(
        "step",
        review_step,
        "EL-TAGNED-CERT-REVIEW",
        "يتم دراسة الطلب المقدم",
        "Recruitment and Mobilization exemption-certificate service instructions",
        "Authority specialists study submitted requests and may require status review.",
        (sources["SRC-TAGNED-CERTIFICATE-SERVICE"],),
    )

    _claim(
        Warning,
        version,
        {
            "semantic_id": "mil.warning.candidate_not_decision",
            "text_ar": (
                "مطابقة ظروفك لمسار بحثي لا تعني صدور قرار إعفاء؛ يلزم تأكيد الجهة المختصة "
                "والمراجعة المتخصصة."
            ),
            "text_en": (
                "Matching a researched route is not an exemption decision; specialist and "
                "authority confirmation are required."
            ),
            "severity": "important",
            "kind": "product",
            "role": "limitation",
            "display_order": 1,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _claim(
        Warning,
        version,
        {
            "semantic_id": "mil.warning.recheck",
            "text_ar": "أعد التحقق من التعليمات قبل التوجه.",
            "text_en": "Re-check current instructions before acting.",
            "severity": "important",
            "kind": "product",
            "role": "regeneration",
            "display_order": 2,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "current",
        },
    )
    _claim(
        Fee,
        version,
        {
            "semantic_id": "mil.fee.current",
            "text_ar": "رسم شهادة الإعفاء",
            "text_en": "Exemption-certificate fee",
            "value_state": Fee.ValueState.UNKNOWN,
            "currency": "EGP",
            "fee_type": "certificate",
            "display_order": 1,
            "verified_on": RESEARCH_DATE,
            "reverify_on": SHORT_REVERIFY,
            "verification_state": "unknown",
        },
    )

    association_specs = (
        (
            "spa.mil.giza_region",
            "spv.recruitment_region_giza.research-2026-08-26",
            ("giza", "fayoum", "6_october"),
        ),
        (
            "spa.mil.mansoura_region",
            "spv.recruitment_region_mansoura.research-2026-08-26",
            ("dakahlia", "damietta", "kafr_el_sheikh"),
        ),
        (
            "spa.mil.zagazig_region",
            "spv.recruitment_region_zagazig.research-2026-08-26",
            ("sharqia", "suez", "ismailia", "port_said", "north_sinai", "south_sinai"),
        ),
    )
    for semantic_id, material_id, governorates in association_specs:
        association = _claim(
            ProcedureServicePointAssociation,
            version,
            {
                "semantic_id": semantic_id,
                "service_point_version": routing_material[material_id],
                "applicability": _in("residence_governorate", governorates),
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            },
        )
        _evidence(
            "procedure_service_point_association",
            association,
            "EL-TAGNED-REGIONS",
            "Recruitment region and governorate coverage",
            "Recruitment and Mobilization Administration regions directory",
            "Only the researched governorate-to-region mapping for this association is asserted.",
            (sources["SRC-TAGNED-REGIONS"],),
        )

    ProcedureVersionReviewPolicy.objects.create(
        procedure_version=version,
        author=author,
        legal_risk=True,
        military_risk=True,
    )

    false_branches = {
        "father_alive": False,
        "mother_family_status": "other",
        "unmarried_sisters_requiring_support_count": 0,
        "missing_relative_category": "none",
        "sibling_service_status": "none",
    }
    only_son = {
        "application_location": "inside_egypt",
        "father_alive": True,
        "other_living_sons_of_father_count": 0,
        "father_unable_to_earn_status": "not_documented_unable",
        "mother_family_status": "other",
        "unmarried_sisters_requiring_support_count": 0,
        "missing_relative_category": "none",
        "sibling_service_status": "none",
        "residence_governorate": "giza",
    }
    father_support = {
        **only_son,
        "other_living_sons_of_father_count": 1,
        "father_unable_to_earn_status": "authority_documented_unable",
    }
    mother_support = {
        "application_location": "inside_egypt",
        **false_branches,
        "mother_family_status": "widowed",
        "residence_governorate": "dakahlia",
    }
    sister_support = {
        "application_location": "inside_egypt",
        **false_branches,
        "unmarried_sisters_requiring_support_count": 1,
        "residence_governorate": "sharqia",
    }
    missing_support = {
        "application_location": "inside_egypt",
        **false_branches,
        "missing_relative_category": "citizen",
        "missing_relative_cause": "war_operations",
        "missing_relative_alive_status": "missing",
        "applicant_largest_eligible_relative_status": "authority_documented_yes",
        "residence_governorate": "giza",
    }
    sibling_support = {
        "application_location": "inside_egypt",
        **false_branches,
        "sibling_service_status": "compulsory_service",
        "applicant_eldest_remaining_brother_status": "authority_documented_yes",
        "article7_third_exclusion_status": "none_documented",
        "residence_governorate": "giza",
    }
    basis_plan = lambda basis_id, route_id=None: {
        "procedure_version_id": version_id,
        "eligibility_basis_ids": [basis_id],
        "inconclusive_basis_ids": [basis_id],
        **(
            {"routing_status": "resolved", "routing_association_ids": [route_id]}
            if route_id
            else {}
        ),
    }
    scenarios: list[tuple[Any, ...]] = [
        (
            "mil.basis.only_son.positive_candidate",
            "positive",
            only_son,
            "plan",
            basis_plan("family.only_son_living_father", "spa.mil.giza_region"),
            [],
        ),
        (
            "mil.basis.father_support.documented_incapacity_candidate",
            "positive",
            father_support,
            "plan",
            basis_plan("family.support_father_or_incapable_brothers", "spa.mil.giza_region"),
            [],
        ),
        (
            "mil.basis.mother_support.widowed_candidate",
            "positive",
            mother_support,
            "plan",
            basis_plan("family.support_mother", "spa.mil.mansoura_region"),
            [],
        ),
        (
            "mil.basis.sisters.positive_candidate",
            "positive",
            sister_support,
            "plan",
            basis_plan("family.support_unmarried_sisters", "spa.mil.zagazig_region"),
            [],
        ),
        (
            "mil.basis.missing.positive_war",
            "positive",
            missing_support,
            "plan",
            basis_plan("family.missing_war_or_terror_relative", "spa.mil.giza_region"),
            [],
        ),
        (
            "mil.basis.sibling_service.compulsory_candidate",
            "positive",
            sibling_support,
            "plan",
            basis_plan("family.sibling_current_service", "spa.mil.giza_region"),
            [],
        ),
        (
            "mil.unknown.reachability_first",
            "unknown",
            {"application_location": "inside_egypt"},
            "next_question",
            {"question_id": "q.mil.father_alive"},
            [],
        ),
        (
            "mil.unknown.only_son_qualification",
            "unknown",
            {"application_location": "inside_egypt", "father_alive": True},
            "next_question",
            {"question_id": "q.mil.other_sons_count"},
            [],
        ),
        (
            "mil.unreachable.father_qualification_suppressed",
            "unknown",
            {"application_location": "inside_egypt", "father_alive": False},
            "next_question",
            {"question_id": "q.mil.mother_status"},
            [],
        ),
        (
            "mil.negative.all_false_no_basis",
            "negative",
            {"application_location": "inside_egypt", **false_branches},
            "inconclusive",
            {"reason": "no_applicable_eligibility_basis"},
            [],
        ),
        (
            "mil.contradictory.no_relative_with_cause",
            "contradictory",
            {
                "application_location": "inside_egypt",
                "missing_relative_category": "none",
                "missing_relative_cause": "war_operations",
            },
            "invalid",
            {},
            ["contradictory_facts", "contradictory_facts"],
        ),
    ]
    multiple = {
        **father_support,
        "unmarried_sisters_requiring_support_count": 1,
    }
    scenarios.append(
        (
            "mil.bases.multiple_support_candidates",
            "positive",
            multiple,
            "plan",
            {
                "procedure_version_id": version_id,
                "eligibility_basis_ids": [
                    "family.support_father_or_incapable_brothers",
                    "family.support_unmarried_sisters",
                ],
                "inconclusive_basis_ids": [
                    "family.support_father_or_incapable_brothers",
                    "family.support_unmarried_sisters",
                ],
            },
            [],
        )
    )
    if amended:
        terrorist = {
            **missing_support,
            "missing_relative_category": "officer",
            "missing_relative_cause": "terrorist_operations",
        }
        scenarios.append(
            (
                "mil.temporal.terrorist_effective_march_25",
                "supported_edge",
                terrorist,
                "plan",
                basis_plan("family.missing_war_or_terror_relative"),
                [],
                "2026-03-25",
            )
        )
    else:
        terrorist_false = {
            **missing_support,
            "missing_relative_category": "officer",
            "missing_relative_cause": "terrorist_operations",
        }
        scenarios.append(
            (
                "mil.temporal.terrorist_not_active_march_24",
                "negative",
                terrorist_false,
                "inconclusive",
                {"reason": "no_applicable_eligibility_basis"},
                [],
                "2026-03-24",
            )
        )

    for raw in scenarios:
        name, kind, source_facts, family, identifiers, diagnostics, *date_override = raw
        scenario = PlanningScenario(
            procedure_version=version,
            name=name,
            kind=kind,
            evaluation_context={
                "evaluation_date": date_override[0] if date_override else (
                    "2026-08-26" if amended else "2026-03-24"
                ),
                "locale": "en",
            },
            source_facts=source_facts,
            expected_result_family=family,
            expected_identifiers=identifiers,
            expected_diagnostics=diagnostics,
        )
        scenario.save()

    _verify_version(version, amended=amended)
    return version


@transaction.atomic
def import_temporary_family_exemption(
    *, author: models.Model
) -> tuple[ProcedureVersion, ProcedureVersion]:
    """Create or verify both researched temporal drafts without approving or publishing them."""

    user_model = get_user_model()
    if (
        not isinstance(author, user_model)
        or author.pk is None
        or not author.is_staff
        or not user_model._default_manager.filter(pk=author.pk, is_staff=True).exists()
    ):
        raise ValidationError("A saved staff author is required.")

    existing = tuple(
        ProcedureVersion.objects.select_for_update()
        .filter(semantic_id__in=VERSION_IDS)
        .order_by("semantic_id")
    )
    if existing:
        if {item.semantic_id for item in existing} != set(VERSION_IDS):
            raise ValidationError("Temporary family-exemption import is only partially present.")
        by_id = {item.semantic_id: item for item in existing}
        _verify_version(by_id[HISTORICAL_VERSION_ID], amended=False)
        _verify_version(by_id[CURRENT_VERSION_ID], amended=True)
        validate_core_catalog()
        return by_id[HISTORICAL_VERSION_ID], by_id[CURRENT_VERSION_ID]

    service = _shared(
        Service,
        {"semantic_id": "handle_military_service_paperwork"},
        {
            "text_ar": "إجراءات التجنيد والخدمة العسكرية",
            "text_en": "Handle military-service paperwork",
            "is_active": True,
        },
    )
    assert isinstance(service, Service)
    procedure = _shared(
        Procedure,
        {"semantic_id": "temporary_family_exemption_from_military_service"},
        {
            "text_ar": "طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية",
            "text_en": "Apply for temporary exemption from military service on a family ground",
            "primary_service_id": service.pk,
        },
    )
    assert isinstance(procedure, Procedure)

    boundary = _eq("application_location", "inside_egypt")
    candidate = ServiceProcedureCandidate.objects.filter(service=service, procedure=procedure).first()
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
        (10, "q.mil.application_location", "application_location", "هل ستتعامل مع موقفك التجنيدي من داخل مصر أم من خارجها؟", "Will you handle your military-service status from inside or outside Egypt?"),
        (20, "q.mil.father_alive", "father_alive", "هل والدك على قيد الحياة؟", "Is your father alive?"),
        (30, "q.mil.other_sons_count", "other_living_sons_of_father_count", "كم عدد الأبناء الذكور الآخرين الأحياء لوالدك؟", "How many other living sons does your father have?"),
        (40, "q.mil.father_capacity", "father_unable_to_earn_status", "هل لديك مستند أو حالة معتمدة تثبت أن والدك غير قادر على الكسب؟", "Do you have an accepted document/status establishing that your father is unable to earn?"),
        (50, "q.mil.mother_status", "mother_family_status", "ما الحالة العائلية ذات الصلة لوالدتك؟", "What is your mother's relevant family status?"),
        (60, "q.mil.unmarried_sisters", "unmarried_sisters_requiring_support_count", "كم عدد أخواتك غير المتزوجات اللاتي تدخل حالتهن في طلب الإعفاء؟", "How many unmarried sisters are relevant to the exemption request?"),
        (65, "q.mil.missing_category", "missing_relative_category", "إذا كان الطلب مرتبطًا بشخص مفقود، فما صفته المسجلة؟", "If the request concerns a missing person, what recorded category applies to that relative?"),
        (70, "q.mil.missing_cause", "missing_relative_cause", "إذا كان الطلب مرتبطًا بشخص مفقود، فما سبب الفقد المسجل؟", "If the request concerns a missing person, what recorded cause of disappearance applies?"),
        (72, "q.mil.missing_alive_status", "missing_relative_alive_status", "ما الحالة المسجلة حاليًا للشخص المفقود؟", "What is the currently recorded status of the missing relative?"),
        (75, "q.mil.largest_eligible_relative", "applicant_largest_eligible_relative_status", "هل لديك حالة معتمدة تثبت أنك القريب الأكبر المستوفي لوصف التجنيد المطلوب لهذا الأساس؟", "Do you have an authority-recorded status establishing that you are the largest eligible conscription relative for this ground?"),
        (80, "q.mil.sibling_service", "sibling_service_status", "هل أحد إخوتك حالياً في الخدمة الإلزامية أو مستدعى للاحتياط؟", "Is one of your brothers currently in compulsory service or called for qualifying reserve service?"),
        (85, "q.mil.eldest_remaining_brother", "applicant_eldest_remaining_brother_status", "هل لديك حالة معتمدة تثبت انطباق ترتيب الأخ الأكبر المتبقي عليك؟", "Do you have an authority-recorded status establishing that the eldest-remaining-brother condition applies to you?"),
        (87, "q.mil.article7_third_exclusion", "article7_third_exclusion_status", "هل توجد حالة معتمدة تُظهر وجود أحد استبعادات المادة 7/ثالثاً؟", "Is there an authority-recorded status showing that an Article 7/Third exclusion applies?"),
        (90, "q.mil.governorate", "residence_governorate", "ما محافظة محل الإقامة المستخدمة في معاملتك التجنيدية؟", "Which governorate of residence is used for your recruitment transaction?"),
    )
    facts: dict[str, FactDefinition] = {}
    for priority, semantic_id, fact_key, text_ar, text_en in question_specs:
        fact = _published_fact(fact_key)
        facts[fact_key] = fact
        question = _shared(
            ServiceQuestion,
            {"semantic_id": semantic_id},
            {
                "service_id": service.pk,
                "fact_id": fact.pk,
                "text_ar": text_ar,
                "text_en": text_en,
                "priority": priority,
            },
        )
        assert isinstance(question, ServiceQuestion)
        if not question.resolved_fact_links.exists():
            set_question_resolved_facts(question, (fact,))
        elif question.resolved_fact_keys != (fact.key,):
            raise ValidationError(f"{semantic_id}: semantic conflict in resolved Facts.")

    contradiction_specs = (
        (
            "mil.no_missing_relative_with_cause",
            "missing_relative_cause",
        ),
        (
            "mil.no_missing_relative_with_alive_status",
            "missing_relative_alive_status",
        ),
        (
            "mil.no_missing_relative_with_relative_order_status",
            "applicant_largest_eligible_relative_status",
        ),
    )
    for semantic_id, dependent_fact_key in contradiction_specs:
        condition = _all(
            _eq("missing_relative_category", "none"),
            _exists(dependent_fact_key),
        )
        contradiction = ServiceContradiction.objects.filter(semantic_id=semantic_id).first()
        declared = (facts["missing_relative_category"], facts[dependent_fact_key])
        if contradiction is None:
            contradiction = ServiceContradiction.objects.create(
                semantic_id=semantic_id,
                service=service,
                condition=condition,
            )
            set_contradiction_facts(contradiction, declared)
        else:
            _expected(
                contradiction,
                {"service_id": service.pk, "condition": condition},
                semantic_id,
            )
            if contradiction.fact_keys != tuple(item.key for item in declared):
                raise ValidationError(f"{semantic_id}: semantic conflict in declared Facts.")

    official_gazette = _shared(
        Authority,
        {"semantic_id": "authority.official_gazette.egypt"},
        {"name_ar": "الجريدة الرسمية المصرية", "name_en": "Egyptian Official Gazette"},
    )
    sis = _shared(
        Authority,
        {"semantic_id": "authority.sis.egypt"},
        {"name_ar": "الهيئة العامة للاستعلامات", "name_en": "State Information Service"},
    )
    parliament = _shared(
        Authority,
        {"semantic_id": "authority.house_of_representatives.egypt"},
        {"name_ar": "مجلس النواب المصري", "name_en": "Egyptian House of Representatives"},
    )
    mod = _shared(
        Authority,
        {"semantic_id": "authority.mod.egypt"},
        {"name_ar": "وزارة الدفاع المصرية", "name_en": "Egyptian Ministry of Defense"},
    )
    recruitment = _shared(
        Authority,
        {"semantic_id": "authority.recruitment_mobilization.egypt"},
        {
            "name_ar": "إدارة التجنيد والتعبئة بالقوات المسلحة",
            "name_en": "Recruitment and Mobilization Administration",
        },
    )
    mks = _shared(
        Authority,
        {"semantic_id": "authority.mks_egypt"},
        {
            "name_ar": "الذاكرة والمعرفة للدراسات",
            "name_en": "Memory and Knowledge for Studies (MKS Egypt)",
        },
    )
    for authority in (official_gazette, sis, parliament, mod, recruitment, mks):
        assert isinstance(authority, Authority)

    source_specs: tuple[tuple[Any, ...], ...] = (
        ("SRC-LAW127-1980-GAZETTE", official_gazette, "Military and National Service Law No. 127 of 1980", "https://manshurat.org/node/12230", "official", date(1980, 7, 10), date(1980, 7, 11)),
        ("SRC-LAW2-2026-GAZETTE-METADATA", sis, "Law No. 2 of 2026 — Official Gazette metadata", "https://mediadr.sis.gov.eg/xmlui/handle/123456789/125126?locale-attribute=en", "official", date(2026, 3, 24), date(2026, 3, 25)),
        ("SRC-LAW2-2026-TEXT", mks, "Law No. 2 of 2026 amending Military and National Service Law", "https://mksegypt.org/ar/laws/24662", "secondary", date(2026, 3, 24), date(2026, 3, 25)),
        ("SRC-PARLIAMENT-LAW2-2026", parliament, "Parliamentary approval of Law No. 2 of 2026 military-service amendment", "https://www.parliament.gov.eg/News_Show.aspx?frm=5692", "official", date(2026, 2, 16), None),
        ("SRC-MOD-RECRUITMENT-OCT-2026", mod, "Recruitment operational announcement", "https://www.mod.gov.eg/modwebsite/NewsDetailsAr.aspx?id=45878", "official", None, None),
        ("SRC-TAGNED-REGIONS", recruitment, "Recruitment regions directory", "https://tagned.mod.gov.eg/tagneedPlaces.aspx", "official", None, None),
        ("SRC-TAGNED-CERTIFICATE-SERVICE", recruitment, "Exemption certificate service", "https://tagned.mod.gov.eg/16militaryServiceExemptionC.aspx", "official", None, None),
    )
    sources: dict[str, Source] = {}
    for semantic_id, authority, title, locator, classification, published_on, source_effective in source_specs:
        source = _shared(
            Source,
            {"semantic_id": semantic_id},
            {
                "authority_id": authority.pk,
                "title": title,
                "locator": locator,
                "classification": classification,
                "published_on": published_on,
                "effective_from": source_effective,
                "retrieved_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
            },
        )
        assert isinstance(source, Source)
        sources[semantic_id] = source

    supporting_documents_type = _shared(
        DocumentType,
        {"semantic_id": "military_supporting_documents"},
        {
            "name_ar": "مستندات مؤيدة للحالة التجنيدية",
            "name_en": "Military supporting documents",
        },
    )
    assert isinstance(supporting_documents_type, DocumentType)

    point_specs = (
        ("sp.recruitment_region_giza", "منطقة تجنيد وتعبئة الجيزة", "Giza Recruitment and Mobilization Region", "spv.recruitment_region_giza.research-2026-08-26", "الهرم، الجيزة", "Haram, Giza"),
        ("sp.recruitment_region_mansoura", "منطقة تجنيد وتعبئة المنصورة", "Mansoura Recruitment and Mobilization Region", "spv.recruitment_region_mansoura.research-2026-08-26", "سندوب، المنصورة", "Sandoub, Mansoura"),
        ("sp.recruitment_region_zagazig", "منطقة تجنيد وتعبئة الزقازيق", "Zagazig Recruitment and Mobilization Region", "spv.recruitment_region_zagazig.research-2026-08-26", "تل بسطا، الزقازيق", "Tel Basta, Zagazig"),
    )
    routing_material: dict[str, ServicePointVersion] = {}
    for point_id, name_ar, name_en, material_id, address_ar, address_en in point_specs:
        point = _shared(
            ServicePoint,
            {"semantic_id": point_id},
            {"name_ar": name_ar, "name_en": name_en},
        )
        assert isinstance(point, ServicePoint)
        material = _shared(
            ServicePointVersion,
            {"semantic_id": material_id},
            {
                "service_point_id": point.pk,
                "address_ar": address_ar,
                "address_en": address_en,
                "availability": ServicePointVersion.Availability.AVAILABLE,
                "verified_on": RESEARCH_DATE,
                "reverify_on": SHORT_REVERIFY,
                "verification_state": "current",
            },
        )
        assert isinstance(material, ServicePointVersion)
        routing_material[material_id] = material

    historical = _create_version(
        procedure=procedure,
        amended=False,
        author=author,
        sources=sources,
        supporting_documents_type=supporting_documents_type,
        routing_material=routing_material,
    )
    current = _create_version(
        procedure=procedure,
        amended=True,
        author=author,
        sources=sources,
        supporting_documents_type=supporting_documents_type,
        routing_material=routing_material,
    )

    for material in routing_material.values():
        if not material.evidence_links.exists():
            _evidence(
                "service_point_version",
                material,
                "EL-TAGNED-REGIONS",
                "Recruitment region identity and location",
                "Recruitment and Mobilization Administration regions directory",
                "Current official material details for the researched recruitment region.",
                (sources["SRC-TAGNED-REGIONS"],),
            )

    _verify_version(historical, amended=False)
    _verify_version(current, amended=True)
    validate_core_catalog()
    return historical, current


__all__ = (
    "CURRENT_VERSION_ID",
    "HISTORICAL_VERSION_ID",
    "RESEARCH_DATE",
    "VERSION_IDS",
    "import_temporary_family_exemption",
)
