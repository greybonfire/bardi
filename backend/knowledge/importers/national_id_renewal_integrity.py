"""Semantic integrity verification for the researched National ID-renewal import."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Q

from knowledge.fees import Fee
from knowledge.models import (
    Authority,
    ChecklistItem,
    EvidenceLink,
    Procedure,
    ProcedureVersion,
    Service,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scenarios import PlanningScenario, planning_behavior_signature
from knowledge.review_workflow import ProcedureVersionReviewPolicy

VERSION_ID = "ordinary_domestic_national_id_renewal.research-2026-08-26"

_EXPECTED = {
    "authorities": "7f4f40fc74e504de67ec65b2b40e6cbac225a41860c68d1823597d65e9187f9d",
    "evidence": "61ed7eb45313add5653866aa42ae0b1131b5771146aafc07bf43b4c664aa8cb5",
    "policy": "06f588d7c3a5511c67ccfa0bd077a4619b2878d6e41b554a1ec0a225d2872aa3",
    "scenarios": "b418ef50987dba3f5069554862e1345ad54e39bb59d6ce3642259cc8ebe350b3",
    "sources": "fef7253023d2fffbe9f6c8577cb31b570664b28f45a4e61b260a69acb4eb6335",
    "trust": "274a52d224ded6a6de890a31a02d42776ceaf11dcfb9cd5d073362d57590a7e3",
}

_AUTHORITY_IDS = (
    "authority.lawyer_egypt",
    "authority.moi.civil_status",
    "authority.official_gazette.egypt",
    "authority.sis.egypt",
)
_SOURCE_IDS = (
    "SRC-CIVIL-LAW-143-GAZETTE",
    "SRC-CIVIL-LAW-CONSOLIDATED-2022",
    "SRC-PSM-CIVIL-STATUS-SERVICES",
    "SRC-SIS-CONSULAR-NID-2026",
)
_OWNER_FIELDS = ("checklist_item", "step", "warning", "fee")


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Unsupported integrity value: {type(value).__name__}")


def _digest(rows: object) -> str:
    payload = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_digest(label: str, rows: object) -> None:
    if _digest(rows) != _EXPECTED[label]:
        raise ValidationError(f"{VERSION_ID}: semantic conflict in {label}.")


def _verify_planning_signature(version: ProcedureVersion) -> None:
    current = planning_behavior_signature(version)
    stored = set(
        PlanningScenario.objects.filter(procedure_version=version).values_list(
            "behavior_signature", flat=True
        )
    )
    if stored != {current}:
        raise ValidationError(f"{VERSION_ID}: semantic conflict in planning behavior.")


def _verify_scenarios(version: ProcedureVersion) -> None:
    rows = list(
        PlanningScenario.objects.filter(procedure_version=version)
        .order_by("name")
        .values(
            "name",
            "kind",
            "evaluation_context",
            "source_facts",
            "expected_result_family",
            "expected_identifiers",
            "expected_diagnostics",
        )
    )
    _require_digest("scenarios", rows)


def _verify_shared_research_records(version: ProcedureVersion) -> None:
    service = Service.objects.get(semantic_id="get_egyptian_national_id")
    if (
        service.text_ar != "الحصول على بطاقة رقم قومي مصرية"
        or service.text_en != "Get an Egyptian National ID"
        or not service.is_active
    ):
        raise ValidationError(f"{VERSION_ID}: semantic conflict in service.")

    procedure = Procedure.objects.get(semantic_id="ordinary_domestic_national_id_renewal")
    if (
        procedure.primary_service_id != service.pk
        or procedure.text_ar != "تجديد بطاقة الرقم القومي المنتهية داخل مصر دون تغيير البيانات"
        or procedure.text_en
        != "Renew an expired Egyptian National ID inside Egypt without changing its recorded data"
        or version.procedure_id != procedure.pk
    ):
        raise ValidationError(f"{VERSION_ID}: semantic conflict in procedure.")

    authorities = list(
        Authority.objects.filter(semantic_id__in=_AUTHORITY_IDS)
        .order_by("semantic_id")
        .values("semantic_id", "name_ar", "name_en")
    )
    _require_digest("authorities", authorities)

    sources = [
        {
            "semantic_id": source.semantic_id,
            "authority_id": source.authority.semantic_id,
            "title": source.title,
            "locator": source.locator,
            "classification": source.classification,
            "published_on": source.published_on,
            "effective_from": source.effective_from,
            "retrieved_on": source.retrieved_on,
            "reverify_on": source.reverify_on,
        }
        for source in Source.objects.filter(semantic_id__in=_SOURCE_IDS)
        .select_related("authority")
        .order_by("semantic_id")
    ]
    _require_digest("sources", sources)


def _trust_row(model: str, row: Any) -> dict[str, object]:
    return {
        "model": model,
        "semantic_id": row.semantic_id,
        "verified_on": row.verified_on,
        "reverify_on": row.reverify_on,
        "verification_state": row.verification_state,
    }


def _verify_trust_metadata(version: ProcedureVersion) -> None:
    rows: list[dict[str, object]] = []
    for model_name, model in (
        ("checklist_item", ChecklistItem),
        ("step", Step),
        ("warning", Warning),
        ("fee", Fee),
    ):
        rows.extend(
            _trust_row(model_name, row)
            for row in model.objects.filter(procedure_version=version).order_by("semantic_id")
        )
    rows.sort(key=lambda row: (str(row["model"]), str(row["semantic_id"])))
    _require_digest("trust", rows)


def _evidence_owner(link: EvidenceLink) -> tuple[str, str]:
    for field in _OWNER_FIELDS:
        if getattr(link, f"{field}_id", None) is not None:
            return field, str(getattr(link, field).semantic_id)
    raise ValidationError(f"{VERSION_ID}: imported Evidence Link has no supported owner.")


def _verify_evidence(version: ProcedureVersion) -> None:
    links = (
        EvidenceLink.objects.filter(
            Q(checklist_item__procedure_version=version)
            | Q(step__procedure_version=version)
            | Q(warning__procedure_version=version)
            | Q(fee__procedure_version=version)
        )
        .distinct()
        .prefetch_related("source_links__source")
    )
    rows: list[dict[str, object]] = []
    for link in links:
        owner_kind, owner_id = _evidence_owner(link)
        rows.append(
            {
                "owner_kind": owner_kind,
                "owner_id": owner_id,
                "semantic_id": link.semantic_id,
                "passage": link.passage,
                "location": link.location,
                "applicability_context": link.applicability_context,
                "retrieved_on": link.retrieved_on,
                "verified_on": link.verified_on,
                "reverify_on": link.reverify_on,
                "verification_state": link.verification_state,
                "support_status": link.support_status,
                "source_ids": [
                    source_link.source.semantic_id
                    for source_link in link.source_links.select_related("source").order_by(
                        "position", "pk"
                    )
                ],
            }
        )
    rows.sort(
        key=lambda row: (
            str(row["owner_kind"]),
            str(row["owner_id"]),
            str(row["semantic_id"]),
        )
    )
    _require_digest("evidence", rows)


def _verify_review_policy(version: ProcedureVersion) -> None:
    policies = list(
        ProcedureVersionReviewPolicy.objects.filter(procedure_version=version).select_related(
            "author"
        )
    )
    rows = [
        {
            "legal_risk": policy.legal_risk,
            "military_risk": policy.military_risk,
            "custody_guardianship_risk": policy.custody_guardianship_risk,
            "contested_identity_risk": policy.contested_identity_risk,
        }
        for policy in policies
    ]
    _require_digest("policy", rows)
    if len(policies) != 1 or not policies[0].author.is_staff:
        raise ValidationError(f"{VERSION_ID}: semantic conflict in review policy author.")


def verify_national_id_renewal_import(version: ProcedureVersion) -> None:
    """Reject drift from the semantic state created by the deterministic importer."""

    if version.semantic_id != VERSION_ID:
        raise ValidationError(
            f"Unexpected National ID-renewal version identity: {version.semantic_id}."
        )
    _verify_planning_signature(version)
    _verify_scenarios(version)
    _verify_shared_research_records(version)
    _verify_trust_metadata(version)
    _verify_evidence(version)
    _verify_review_policy(version)


__all__ = ("verify_national_id_renewal_import",)
