"""Semantic integrity verification for the researched passport-renewal import."""

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
    DocumentType,
    EvidenceLink,
    ProcedureVersion,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scenarios import PlanningScenario, planning_behavior_signature
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePointVersion,
)

VERSION_ID = "ordinary_domestic_passport_renewal.research-2026-08-25"

_EXPECTED = {
    "authorities": "7c1a974234b6d3bba73247af9070129e029609ce7e3b7d0a7fea0c89f30a0de5",
    "documents": "515fb6b1ef9e6f450d39ca0f24bb6f3f08bb139c7f33394d9629462baeb2be93",
    "evidence": "0b1768a1be95fa9a081a17bb4f511cd17b5de0c57ec47508572b2130fcee6ba9",
    "policy": "a606df3d811909414097f400cf393f94eac503607f718f5aecc066a25bba2605",
    "scenarios": "e5f2c2f2fa59c63876324eec0610b548455fa5e1c14a506da119c00c479041f4",
    "sources": "87efb46c6eb3b57883936c927517d6c011577e2504e846ea0d4ebaf41e33ff54",
    "trust": "f409b172c9565fa0bb6a6a7a1a1a463278cd2f8d63804cd12d9bb14e6944a009",
}

_AUTHORITY_IDS = ("authority.mfa.egypt", "authority.moi.gapin")
_DOCUMENT_IDS = (
    "birth_certificate",
    "military_status_document",
    "national_id",
    "passport_photo",
    "previous_passport",
    "student_enrollment_certificate",
    "supporting_documents",
)
_SOURCE_IDS = (
    "SRC-HISTORIC-GOV-PASSPORT",
    "SRC-MFA-CONSULAR-PASSPORT",
    "SRC-MOI-ACCELERATED",
    "SRC-MOI-OFFICE-DIRECTORY",
    "SRC-MOI-PASSPORT-REQ",
    "SRC-PSM-RENEWAL-SERVICE",
)
_OWNER_FIELDS = (
    "checklist_item",
    "step",
    "warning",
    "fee",
    "eligibility_basis",
    "procedure_dependency",
    "service_point_version",
    "procedure_service_point_association",
)


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


def _verify_shared_research_records() -> None:
    authorities = list(
        Authority.objects.filter(semantic_id__in=_AUTHORITY_IDS)
        .order_by("semantic_id")
        .values("semantic_id", "name_ar", "name_en")
    )
    _require_digest("authorities", authorities)

    documents = list(
        DocumentType.objects.filter(semantic_id__in=_DOCUMENT_IDS)
        .order_by("semantic_id")
        .values("semantic_id", "name_ar", "name_en")
    )
    _require_digest("documents", documents)

    sources = [
        {
            "semantic_id": source.semantic_id,
            "authority_id": source.authority.semantic_id,
            "title": source.title,
            "locator": source.locator,
            "classification": source.classification,
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
        ("procedure_service_point_association", ProcedureServicePointAssociation),
    ):
        rows.extend(
            _trust_row(model_name, row)
            for row in model.objects.filter(procedure_version=version).order_by("semantic_id")
        )
    rows.extend(
        _trust_row("service_point_version", row)
        for row in ServicePointVersion.objects.filter(associations__procedure_version=version)
        .distinct()
        .order_by("semantic_id")
    )
    rows.sort(key=lambda row: (str(row["model"]), str(row["semantic_id"])))
    _require_digest("trust", rows)


def _evidence_owner(link: EvidenceLink) -> tuple[str, str]:
    for field in _OWNER_FIELDS:
        if getattr(link, f"{field}_id", None) is not None:
            return field, str(getattr(link, field).semantic_id)
    raise ValidationError(f"{VERSION_ID}: imported Evidence Link has no owner.")


def _verify_evidence(version: ProcedureVersion) -> None:
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
    rows = list(
        ProcedureVersionReviewPolicy.objects.filter(procedure_version=version).values(
            "legal_risk",
            "military_risk",
            "custody_guardianship_risk",
            "contested_identity_risk",
        )
    )
    _require_digest("policy", rows)


def verify_passport_renewal_import(version: ProcedureVersion) -> None:
    """Reject drift from the semantic state created by the deterministic importer."""

    if version.semantic_id != VERSION_ID:
        raise ValidationError(
            f"Unexpected passport-renewal version identity: {version.semantic_id}."
        )
    _verify_planning_signature(version)
    _verify_scenarios(version)
    _verify_shared_research_records()
    _verify_trust_metadata(version)
    _verify_evidence(version)
    _verify_review_policy(version)


__all__ = ("verify_passport_renewal_import",)
