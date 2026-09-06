"""Semantic integrity verification for the researched temporary family-exemption import."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from django.core.exceptions import ValidationError

from knowledge.fees import Fee
from knowledge.models import (
    Authority,
    ChecklistItem,
    EligibilityBasis,
    Procedure,
    ProcedureVersion,
    Service,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scenarios import PlanningScenario, planning_behavior_signature
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.service_point_routing import ProcedureServicePointAssociation, ServicePointVersion

from .temporary_family_exemption import (
    AMENDMENT_EFFECTIVE_DATE,
    AMENDMENT_PUBLICATION_DATE,
    CURRENT_VERSION_ID,
    HISTORICAL_VERSION_ID,
    RESEARCH_DATE,
    SHORT_REVERIFY,
)

_VERSION_INTERVALS = {
    HISTORICAL_VERSION_ID: (None, AMENDMENT_PUBLICATION_DATE),
    CURRENT_VERSION_ID: (AMENDMENT_EFFECTIVE_DATE, None),
}

_BASIS_IDS = {
    "family.only_son_living_father",
    "family.support_father_or_incapable_brothers",
    "family.support_mother",
    "family.support_unmarried_sisters",
    "family.missing_war_or_terror_relative",
    "family.sibling_current_service",
}

_CLAIM_IDS = {
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
}

_ASSOCIATIONS = {
    "spa.mil.giza_region": (
        "spv.recruitment_region_giza.research-2026-08-26",
        {"giza", "fayoum", "6_october"},
    ),
    "spa.mil.mansoura_region": (
        "spv.recruitment_region_mansoura.research-2026-08-26",
        {"dakahlia", "damietta", "kafr_el_sheikh"},
    ),
    "spa.mil.zagazig_region": (
        "spv.recruitment_region_zagazig.research-2026-08-26",
        {"sharqia", "suez", "ismailia", "port_said", "north_sinai", "south_sinai"},
    ),
}

_SERVICE_POINT_VERSIONS = {
    "spv.recruitment_region_giza.research-2026-08-26": (
        "sp.recruitment_region_giza",
        "الهرم، الجيزة",
        "Haram, Giza",
    ),
    "spv.recruitment_region_mansoura.research-2026-08-26": (
        "sp.recruitment_region_mansoura",
        "سندوب، المنصورة",
        "Sandoub, Mansoura",
    ),
    "spv.recruitment_region_zagazig.research-2026-08-26": (
        "sp.recruitment_region_zagazig",
        "تل بسطا، الزقازيق",
        "Tel Basta, Zagazig",
    ),
}

_AUTHORITIES = {
    "authority.official_gazette.egypt": ("الجريدة الرسمية المصرية", "Egyptian Official Gazette"),
    "authority.sis.egypt": ("الهيئة العامة للاستعلامات", "State Information Service"),
    "authority.house_of_representatives.egypt": (
        "مجلس النواب المصري",
        "Egyptian House of Representatives",
    ),
    "authority.mod.egypt": ("وزارة الدفاع المصرية", "Egyptian Ministry of Defense"),
    "authority.recruitment_mobilization.egypt": (
        "إدارة التجنيد والتعبئة بالقوات المسلحة",
        "Recruitment and Mobilization Administration",
    ),
    "authority.mks_egypt": (
        "الذاكرة والمعرفة للدراسات",
        "Memory and Knowledge for Studies (MKS Egypt)",
    ),
}

_SOURCES = {
    "SRC-LAW127-1980-GAZETTE": (
        "authority.official_gazette.egypt",
        "Military and National Service Law No. 127 of 1980",
        "https://manshurat.org/node/12230",
        "official",
        date(1980, 7, 10),
        date(1980, 7, 11),
    ),
    "SRC-LAW2-2026-GAZETTE-METADATA": (
        "authority.sis.egypt",
        "Law No. 2 of 2026 — Official Gazette metadata",
        "https://mediadr.sis.gov.eg/xmlui/handle/123456789/125126?locale-attribute=en",
        "official",
        date(2026, 3, 24),
        date(2026, 3, 25),
    ),
    "SRC-LAW2-2026-TEXT": (
        "authority.mks_egypt",
        "Law No. 2 of 2026 amending Military and National Service Law",
        "https://mksegypt.org/ar/laws/24662",
        "secondary",
        date(2026, 3, 24),
        date(2026, 3, 25),
    ),
    "SRC-PARLIAMENT-LAW2-2026": (
        "authority.house_of_representatives.egypt",
        "Parliamentary approval of Law No. 2 of 2026 military-service amendment",
        "https://www.parliament.gov.eg/News_Show.aspx?frm=5692",
        "official",
        date(2026, 2, 16),
        None,
    ),
    "SRC-MOD-RECRUITMENT-OCT-2026": (
        "authority.mod.egypt",
        "Recruitment operational announcement",
        "https://www.mod.gov.eg/modwebsite/NewsDetailsAr.aspx?id=45878",
        "official",
        None,
        None,
    ),
    "SRC-TAGNED-REGIONS": (
        "authority.recruitment_mobilization.egypt",
        "Recruitment regions directory",
        "https://tagned.mod.gov.eg/tagneedPlaces.aspx",
        "official",
        None,
        None,
    ),
    "SRC-TAGNED-CERTIFICATE-SERVICE": (
        "authority.recruitment_mobilization.egypt",
        "Exemption certificate service",
        "https://tagned.mod.gov.eg/16militaryServiceExemptionC.aspx",
        "official",
        None,
        None,
    ),
}


def _conflict(version_id: str, label: str) -> None:
    raise ValidationError(f"{version_id}: semantic conflict in {label}.")


def _rule_fact_values(rule: object, fact: str) -> set[object]:
    if not isinstance(rule, dict):
        return set()
    if rule.get("fact") == fact and rule.get("op") == "eq":
        return {rule.get("value")}
    if rule.get("fact") == fact and rule.get("op") == "in":
        value = rule.get("value")
        return set(value) if isinstance(value, list) else set()
    values: set[object] = set()
    children = rule.get("children")
    if isinstance(children, list):
        for child in children:
            values.update(_rule_fact_values(child, fact))
    return values


def _verify_shared_records(version_id: str) -> None:
    service = Service.objects.get(semantic_id="handle_military_service_paperwork")
    if (
        service.text_ar != "إجراءات التجنيد والخدمة العسكرية"
        or service.text_en != "Handle military-service paperwork"
        or not service.is_active
    ):
        _conflict(version_id, "service")

    procedure = Procedure.objects.get(
        semantic_id="temporary_family_exemption_from_military_service"
    )
    if (
        procedure.primary_service_id != service.pk
        or procedure.text_ar != "طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية"
        or procedure.text_en
        != "Apply for temporary exemption from military service on a family ground"
    ):
        _conflict(version_id, "procedure")

    authorities = {
        authority.semantic_id: (authority.name_ar, authority.name_en)
        for authority in Authority.objects.filter(semantic_id__in=_AUTHORITIES)
    }
    if authorities != _AUTHORITIES:
        _conflict(version_id, "authorities")

    sources = {}
    for source in Source.objects.filter(semantic_id__in=_SOURCES).select_related("authority"):
        sources[source.semantic_id] = (
            source.authority.semantic_id,
            source.title,
            source.locator,
            source.classification,
            source.published_on,
            source.effective_from,
        )
        if source.retrieved_on != RESEARCH_DATE or source.reverify_on != SHORT_REVERIFY:
            _conflict(version_id, "source trust metadata")
    if sources != _SOURCES:
        _conflict(version_id, "sources")


def _verify_version(version: ProcedureVersion) -> None:
    version_id = version.semantic_id
    if version_id not in _VERSION_INTERVALS:
        raise ValidationError(f"Unexpected temporary family-exemption version: {version_id}.")
    effective_from, effective_to = _VERSION_INTERVALS[version_id]
    if (
        version.effective_from != effective_from
        or version.effective_to != effective_to
        or version.applicability
        != {"op": "eq", "fact": "application_location", "value": "inside_egypt"}
        or version.procedure.semantic_id != "temporary_family_exemption_from_military_service"
        or version.dependencies.exists()
    ):
        _conflict(version_id, "version contract")

    basis_rows = {
        row.semantic_id: row for row in EligibilityBasis.objects.filter(procedure_version=version)
    }
    if set(basis_rows) != _BASIS_IDS:
        _conflict(version_id, "Eligibility Bases")
    for basis in basis_rows.values():
        dynamic = cast(Any, basis)
        if (
            dynamic.verification_state != "needs_reverification"
            or dynamic.verified_on != RESEARCH_DATE
            or dynamic.reverify_on != SHORT_REVERIFY
            or not basis.evidence_links.exists()
        ):
            _conflict(version_id, f"Basis trust {basis.semantic_id}")

    only_son = cast(Any, basis_rows["family.only_son_living_father"])
    if only_son.reachability != {"op": "eq", "fact": "father_alive", "value": True}:
        _conflict(version_id, "only-son reachability")
    if only_son.qualification != {
        "op": "eq",
        "fact": "other_living_sons_of_father_count",
        "value": 0,
    }:
        _conflict(version_id, "only-son qualification")

    father = cast(Any, basis_rows["family.support_father_or_incapable_brothers"])
    if father.reachability != {"op": "eq", "fact": "father_alive", "value": True}:
        _conflict(version_id, "father-support reachability")
    if father.qualification != {
        "op": "eq",
        "fact": "father_unable_to_earn_status",
        "value": "authority_documented_unable",
    }:
        _conflict(version_id, "father-support qualification")

    missing = cast(Any, basis_rows["family.missing_war_or_terror_relative"])
    causes = _rule_fact_values(missing.qualification, "missing_relative_cause")
    expected_causes = (
        {"war_operations", "terrorist_operations"}
        if version_id == CURRENT_VERSION_ID
        else {"war_operations"}
    )
    if causes != expected_causes:
        _conflict(version_id, "missing-relative temporal rule")

    for model, expected_ids in _CLAIM_IDS.items():
        actual_ids = set(
            cast(Any, model)
            .objects.filter(procedure_version=version)
            .values_list("semantic_id", flat=True)
        )
        if actual_ids != expected_ids:
            _conflict(version_id, f"{model.__name__} aggregate")

    fee = Fee.objects.get(procedure_version=version, semantic_id="mil.fee.current")
    if (
        fee.value_state != Fee.ValueState.UNKNOWN
        or fee.amount is not None
        or fee.minimum_amount is not None
        or fee.maximum_amount is not None
        or fee.currency != "EGP"
        or fee.verification_state != "unknown"
    ):
        _conflict(version_id, "fee")

    associations = {
        row.semantic_id: row
        for row in ProcedureServicePointAssociation.objects.filter(procedure_version=version)
    }
    if set(associations) != set(_ASSOCIATIONS):
        _conflict(version_id, "routing associations")
    for semantic_id, (material_id, governorates) in _ASSOCIATIONS.items():
        row = associations[semantic_id]
        dynamic = cast(Any, row)
        if (
            row.service_point_version.semantic_id != material_id
            or dynamic.verification_state != "current"
            or dynamic.verified_on != RESEARCH_DATE
            or dynamic.reverify_on != SHORT_REVERIFY
            or not row.evidence_links.exists()
        ):
            _conflict(version_id, f"routing trust {semantic_id}")
        if _rule_fact_values(row.applicability, "residence_governorate") != governorates:
            _conflict(version_id, f"routing applicability {semantic_id}")

    policy = ProcedureVersionReviewPolicy.objects.select_related("author").get(
        procedure_version=version
    )
    if (
        not policy.legal_risk
        or not policy.military_risk
        or policy.custody_guardianship_risk
        or policy.contested_identity_risk
        or not policy.author.is_staff
    ):
        _conflict(version_id, "review policy")

    current_signature = planning_behavior_signature(version)
    stored_signatures = set(
        PlanningScenario.objects.filter(procedure_version=version).values_list(
            "behavior_signature", flat=True
        )
    )
    if stored_signatures != {current_signature}:
        _conflict(version_id, "planning behavior")


def _verify_routing_material(version_id: str) -> None:
    rows = {
        row.semantic_id: row
        for row in ServicePointVersion.objects.filter(
            semantic_id__in=_SERVICE_POINT_VERSIONS
        ).select_related("service_point")
    }
    if set(rows) != set(_SERVICE_POINT_VERSIONS):
        _conflict(version_id, "routing material")
    for semantic_id, (point_id, address_ar, address_en) in _SERVICE_POINT_VERSIONS.items():
        row = rows[semantic_id]
        dynamic = cast(Any, row)
        if (
            row.service_point.semantic_id != point_id
            or row.address_ar != address_ar
            or row.address_en != address_en
            or row.availability != ServicePointVersion.Availability.AVAILABLE
            or dynamic.verification_state != "current"
            or dynamic.verified_on != RESEARCH_DATE
            or dynamic.reverify_on != SHORT_REVERIFY
            or not row.evidence_links.exists()
        ):
            _conflict(version_id, f"routing material {semantic_id}")


def verify_temporary_family_exemption_import(
    versions: tuple[ProcedureVersion, ProcedureVersion],
) -> None:
    """Reject drift from the semantic state created by the deterministic importer."""

    if {version.semantic_id for version in versions} != set(_VERSION_INTERVALS):
        raise ValidationError("Unexpected temporary family-exemption version identities.")
    _verify_shared_records(CURRENT_VERSION_ID)
    _verify_routing_material(CURRENT_VERSION_ID)
    for version in versions:
        _verify_version(version)


__all__ = ("verify_temporary_family_exemption_import",)
