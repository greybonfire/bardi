"""Safe lifecycle helpers used by the Django Admin editorial surface.

Published Procedure Versions are never reopened for editing.  Successor creation copies the
coherent version-owned semantic/evidence/scenario aggregate into new draft rows while preserving
shared stable identities such as Sources, Authorities, Document Types, Procedures and Service
Point material.  Historical workflow records are deliberately not copied.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from .fees import Fee
from .models import (
    ChecklistItem,
    EligibilityBasis,
    EvidenceLink,
    EvidenceLinkSource,
    ProcedureVersion,
    Step,
    Warning,
)
from .planning_scenarios import PlanningScenario
from .procedure_dependencies import ProcedureDependency
from .review_workflow import ProcedureVersionReviewPolicy
from .service_point_routing import ProcedureServicePointAssociation

_LIFECYCLE_FIELDS = frozenset(
    {
        "semantic_id",
        "state",
        "published_at",
        "published_by",
        "withdrawn_at",
        "withdrawn_by",
    }
)
_EVIDENCE_OWNER_FIELDS = (
    "checklist_item",
    "step",
    "warning",
    "fee",
    "eligibility_basis",
    "procedure_dependency",
    "service_point_version",
    "procedure_service_point_association",
)


def _validate_actor(actor: User) -> None:
    user_model = get_user_model()
    if actor.pk is None or not user_model._default_manager.filter(pk=actor.pk).exists():
        raise ValidationError("A saved staff actor is required to create a successor draft.")


def _copy_values(
    instance: models.Model,
    *,
    exclude: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in exclude:
            continue
        values[field.attname] = deepcopy(getattr(instance, field.attname))
    return values


def _clone_row(instance: models.Model, **overrides: Any) -> models.Model:
    values = _copy_values(instance)
    values.update(overrides)
    clone = type(instance)(**values)
    clone.save()
    return clone


def _next_successor_semantic_id(source: ProcedureVersion) -> str:
    stem = f"{source.semantic_id}.successor"
    candidate = stem
    suffix = 2
    while ProcedureVersion.objects.filter(semantic_id=candidate).exists():
        candidate = f"{stem}.{suffix}"
        suffix += 1
    return candidate


def _clone_scenario(
    scenario: PlanningScenario,
    *,
    successor: ProcedureVersion,
    source_semantic_id: str,
) -> PlanningScenario:
    values = _copy_values(scenario, exclude=frozenset({"behavior_signature"}))
    identifiers = deepcopy(values.get("expected_identifiers", {}))
    if (
        isinstance(identifiers, dict)
        and identifiers.get("procedure_version_id") == source_semantic_id
    ):
        identifiers["procedure_version_id"] = successor.semantic_id
    values["expected_identifiers"] = identifiers
    values["procedure_version_id"] = successor.pk
    clone = PlanningScenario(**values)
    clone.save()
    return clone


def clone_published_procedure_version(
    source_version_id: int,
    *,
    actor: User,
    semantic_id: str | None = None,
) -> ProcedureVersion:
    """Clone one published Procedure Version into a fresh editable successor draft.

    Stable shared identities remain shared.  Version-owned semantic material, claim Evidence
    Links/source joins, named planning scenarios, and high-risk review-policy flags are copied.
    Discrepancy history, re-verification events, approvals, and publication audit rows remain
    attached to the historical version and are intentionally not copied.
    """

    _validate_actor(actor)
    with transaction.atomic():
        source = (
            ProcedureVersion.objects.select_for_update()
            .select_related("procedure")
            .get(pk=source_version_id)
        )
        if source.state != ProcedureVersion.State.PUBLISHED:
            raise ValidationError(
                f"{source.semantic_id}: only a published Procedure Version can be cloned."
            )

        successor_id = (semantic_id or _next_successor_semantic_id(source)).strip()
        if not successor_id:
            raise ValidationError(f"{source.semantic_id}: successor semantic_id is required.")
        if ProcedureVersion.objects.filter(semantic_id=successor_id).exists():
            raise ValidationError(f"{source.semantic_id}: successor semantic_id already exists.")

        version_values = _copy_values(source, exclude=_LIFECYCLE_FIELDS)
        successor = ProcedureVersion(
            **version_values,
            semantic_id=successor_id,
            state=ProcedureVersion.State.DRAFT,
            published_at=None,
            published_by=None,
            withdrawn_at=None,
            withdrawn_by=None,
        )
        successor.save()

        basis_map: dict[int, EligibilityBasis] = {}
        for basis_row in EligibilityBasis.objects.filter(procedure_version=source).order_by("pk"):
            basis_clone = cast(
                EligibilityBasis,
                _clone_row(basis_row, procedure_version_id=successor.pk),
            )
            assert basis_row.pk is not None
            basis_map[basis_row.pk] = basis_clone

        checklist_map: dict[int, ChecklistItem] = {}
        for checklist_row in ChecklistItem.objects.filter(procedure_version=source).order_by("pk"):
            checklist_clone = cast(
                ChecklistItem,
                _clone_row(checklist_row, procedure_version_id=successor.pk),
            )
            assert checklist_row.pk is not None
            checklist_map[checklist_row.pk] = checklist_clone

        step_map: dict[int, Step] = {}
        for step_row in Step.objects.filter(procedure_version=source).order_by("pk"):
            basis_id = step_row.eligibility_basis_id
            step_clone = cast(
                Step,
                _clone_row(
                    step_row,
                    procedure_version_id=successor.pk,
                    eligibility_basis_id=(basis_map[basis_id].pk if basis_id is not None else None),
                ),
            )
            assert step_row.pk is not None
            step_map[step_row.pk] = step_clone

        warning_map: dict[int, Warning] = {}
        for warning_row in Warning.objects.filter(procedure_version=source).order_by("pk"):
            warning_clone = cast(
                Warning,
                _clone_row(warning_row, procedure_version_id=successor.pk),
            )
            assert warning_row.pk is not None
            warning_map[warning_row.pk] = warning_clone

        fee_map: dict[int, Fee] = {}
        for fee_row in Fee.objects.filter(procedure_version=source).order_by("pk"):
            basis_id = fee_row.eligibility_basis_id
            fee_clone = cast(
                Fee,
                _clone_row(
                    fee_row,
                    procedure_version_id=successor.pk,
                    eligibility_basis_id=(basis_map[basis_id].pk if basis_id is not None else None),
                ),
            )
            assert fee_row.pk is not None
            fee_map[fee_row.pk] = fee_clone

        dependency_map: dict[int, ProcedureDependency] = {}
        for dependency_row in ProcedureDependency.objects.filter(
            procedure_version=source
        ).order_by("pk"):
            dependency_clone = cast(
                ProcedureDependency,
                _clone_row(dependency_row, procedure_version_id=successor.pk),
            )
            assert dependency_row.pk is not None
            dependency_map[dependency_row.pk] = dependency_clone

        association_map: dict[int, ProcedureServicePointAssociation] = {}
        for association_row in ProcedureServicePointAssociation.objects.filter(
            procedure_version=source
        ).order_by("pk"):
            association_clone = cast(
                ProcedureServicePointAssociation,
                _clone_row(association_row, procedure_version_id=successor.pk),
            )
            assert association_row.pk is not None
            association_map[association_row.pk] = association_clone

        owner_maps: dict[str, dict[int, models.Model]] = {
            "checklist_item": cast(dict[int, models.Model], checklist_map),
            "step": cast(dict[int, models.Model], step_map),
            "warning": cast(dict[int, models.Model], warning_map),
            "fee": cast(dict[int, models.Model], fee_map),
            "eligibility_basis": cast(dict[int, models.Model], basis_map),
            "procedure_dependency": cast(dict[int, models.Model], dependency_map),
            "procedure_service_point_association": cast(dict[int, models.Model], association_map),
        }
        evidence_filter = Q(pk__in=[])
        for field_name, mapping in owner_maps.items():
            evidence_filter |= Q(**{f"{field_name}_id__in": tuple(mapping)})

        evidence_map: dict[int, EvidenceLink] = {}
        for evidence_link in EvidenceLink.objects.filter(evidence_filter).order_by("pk"):
            values = _copy_values(evidence_link, exclude=frozenset(_EVIDENCE_OWNER_FIELDS))
            matched = [
                (field_name, mapping[getattr(evidence_link, f"{field_name}_id")])
                for field_name, mapping in owner_maps.items()
                if getattr(evidence_link, f"{field_name}_id", None) in mapping
            ]
            if len(matched) != 1:
                raise ValidationError(
                    f"{source.semantic_id}: evidence {evidence_link.pk} has incoherent version ownership."
                )
            field_name, new_owner = matched[0]
            values[f"{field_name}_id"] = new_owner.pk
            evidence_clone = EvidenceLink(**values)
            evidence_clone.save()
            assert evidence_link.pk is not None
            evidence_map[evidence_link.pk] = evidence_clone

        for source_link in EvidenceLinkSource.objects.filter(
            evidence_link_id__in=tuple(evidence_map)
        ).order_by("evidence_link_id", "position", "pk"):
            EvidenceLinkSource.objects.create(
                evidence_link=evidence_map[source_link.evidence_link_id],
                source_id=source_link.source_id,
                position=source_link.position,
            )

        for planning_scenario in PlanningScenario.objects.filter(
            procedure_version=source
        ).order_by("pk"):
            _clone_scenario(
                planning_scenario,
                successor=successor,
                source_semantic_id=source.semantic_id,
            )

        source_policy = ProcedureVersionReviewPolicy.objects.filter(
            procedure_version=source
        ).first()
        ProcedureVersionReviewPolicy.objects.create(
            procedure_version=successor,
            author=actor,
            legal_risk=bool(source_policy and source_policy.legal_risk),
            military_risk=bool(source_policy and source_policy.military_risk),
            custody_guardianship_risk=bool(
                source_policy and source_policy.custody_guardianship_risk
            ),
            contested_identity_risk=bool(source_policy and source_policy.contested_identity_risk),
        )

        return successor


__all__ = ("clone_published_procedure_version",)
