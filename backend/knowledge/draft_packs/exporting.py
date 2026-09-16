"""Authoring export and deliberately non-importable read-only context."""

from __future__ import annotations

from typing import Any

from knowledge import models as m
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.service_point_routing import ServicePointVersion

from .mapping import CANDIDATE, CATALOG, CONTRADICTION, EVIDENCE, OWNED, QUESTION, VERSION, authored
from .state import evidence_for, fail, revision


def setup_for(service: Any) -> dict[str, Any]:
    questions = []
    for row in service.questions.order_by("semantic_id"):
        questions.append(
            {
                **authored(row, QUESTION),
                "resolves_facts": list(
                    row.resolved_fact_links.order_by("position").values_list("fact__key", flat=True)
                ),
            }
        )
    contradictions = []
    for row in service.contradictions.order_by("semantic_id"):
        contradictions.append({**authored(row, CONTRADICTION), "facts": list(row.fact_keys)})
    return {
        "service": service.semantic_id,
        "questions": questions,
        "candidates": [
            authored(row, CANDIDATE)
            for row in service.procedure_candidates.order_by("procedure__semantic_id")
        ],
        "contradictions": contradictions,
    }


def snapshot(version: Any) -> dict[str, Any]:
    service = version.procedure.primary_service
    setup = setup_for(service)
    result: dict[str, Any] = {
        "format": "bardi.draft-pack",
        "format_version": 1,
        "base_revision": revision(version),
        "version": authored(version, VERSION),
        "service_setup": setup,
    }
    policy = ProcedureVersionReviewPolicy.objects.filter(procedure_version=version).first()
    result["risks"] = {
        name: bool(policy and getattr(policy, f"{name}_risk"))
        for name in ("legal", "military", "custody_guardianship", "contested_identity")
    }
    for key, spec in OWNED.items():
        result[key] = [
            authored(row, spec)
            for row in spec.model.objects.filter(procedure_version=version).order_by(spec.identity)
        ]
    result["evidence_links"] = []
    for link in evidence_for(version):
        if not link.semantic_id.strip():
            fail(
                "legacy_evidence_identity",
                ("evidence_links",),
                "Assign stable IDs to legacy evidence in Admin before exporting.",
            )
        kind = next(
            spec.owner_kind
            for spec in OWNED.values()
            if spec.owner_kind and getattr(link, f"{spec.owner_kind}_id")
        )
        result["evidence_links"].append(
            {
                **authored(link, EVIDENCE),
                "owner": {"kind": kind, "semantic_id": link.owner.semantic_id},
                "sources": list(
                    link.source_links.order_by("position").values_list(
                        "source__semantic_id", flat=True
                    )
                ),
            }
        )
    result["evidence_links"].sort(
        key=lambda row: (row["owner"]["kind"], row["owner"]["semantic_id"], row["semantic_id"])
    )
    procedures = {
        version.procedure.semantic_id,
        *(row["procedure"] for row in setup["candidates"]),
        *(row["target_procedure"] for row in result["dependencies"]),
    }
    procedure_rows = m.Procedure.objects.filter(semantic_id__in=procedures)
    sources = m.Source.objects.filter(
        semantic_id__in={key for row in result["evidence_links"] for key in row["sources"]}
    )
    rows = {
        "procedures": procedure_rows,
        "services": m.Service.objects.filter(pk__in=procedure_rows.values("primary_service_id")),
        # Full source registry also covers pinned Derived Fact source dependencies.
        "facts": m.FactDefinition.objects.filter(derived=False),
        "sources": sources,
        "authorities": m.Authority.objects.filter(pk__in=sources.values("authority_id")),
        "document_types": m.DocumentType.objects.filter(
            semantic_id__in={
                row["document_type"] for row in result["checklist_items"] if row["document_type"]
            }
        ),
    }
    result["catalog"] = {
        key: [authored(row, CATALOG[key]) for row in queryset.order_by(CATALOG[key].identity)]
        for key, queryset in rows.items()
    }
    return result


def context(service_id: str | None) -> dict[str, Any]:
    services = m.Service.objects.all()
    if service_id is not None:
        services = services.filter(semantic_id=service_id)
        if not services.exists():
            fail("not_found", ("service",), "Service does not exist.")
    return {
        "format": "bardi.draft-context",
        "format_version": 1,
        "status": "read_only",
        "catalog": {
            key: [authored(row, spec) for row in spec.model.objects.order_by(spec.identity)]
            for key, spec in CATALOG.items()
            if key != "facts"
        },
        "facts": [
            {
                **authored(row, CATALOG["facts"]),
                "derived": row.derived,
                "is_published": row.is_published,
            }
            for row in m.FactDefinition.objects.order_by("key")
        ],
        "service_setup": [setup_for(row) for row in services.order_by("semantic_id")],
        "service_point_versions": [
            {
                "semantic_id": row.semantic_id,
                "effective_from": row.effective_from.isoformat() if row.effective_from else None,
                "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            }
            for row in ServicePointVersion.objects.order_by("semantic_id")
        ],
    }
