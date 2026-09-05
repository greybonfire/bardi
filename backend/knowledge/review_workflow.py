"""Independent and specialist review records for Procedure Version publication.

Every approval is append-only and binds to one coherent draft-state signature. Publication
requires fresh approvals from people independent of both the accountable author and publisher.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from django.db.models import Q
from django.utils import timezone

from .evidence_workflow import EvidenceDiscrepancy, EvidenceDiscrepancyEvidence
from .models import (
    Authority,
    ChecklistItem,
    DocumentType,
    EligibilityBasis,
    EvidenceLink,
    EvidenceLinkSource,
    ProcedureVersion,
    ProcedureVersionAuditEvent,
    Source,
    Step,
    Warning,
)
from .planning_scenarios import PlanningScenario, planning_behavior_signature
from .publication import PublicationContext, PublicationDiagnostic

_REVIEW_DIMENSIONS = (
    "evidence_source",
    "rule_logic",
    "scenario_behavior",
    "bilingual_semantic",
    "discrepancy",
)
_CORE_REVIEW_DIMENSIONS = frozenset(_REVIEW_DIMENSIONS[:-1])
_SPECIALIST_RISKS = (
    "legal",
    "military",
    "custody_guardianship",
    "contested_identity",
)
_SPECIALIST_PERMISSIONS: Mapping[str, str] = {
    "legal": "knowledge.specialist_approve_legal",
    "military": "knowledge.specialist_approve_military",
    "custody_guardianship": "knowledge.specialist_approve_custody_guardianship",
    "contested_identity": "knowledge.specialist_approve_contested_identity",
}
_REVIEW_PERMISSION = "knowledge.review_procedureversion"
_SIGNATURE_SETTING = "bardi.procedure_version_review_signature"


def _validate_actor(actor: User) -> None:
    user_model = get_user_model()
    if actor.pk is None or not user_model._default_manager.filter(pk=actor.pk).exists():
        raise ValidationError("A saved review actor is required.")


def _jsonable(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row_payload(instance: models.Model) -> dict[str, object]:
    payload: dict[str, object] = {"model": instance._meta.label_lower}
    for field in instance._meta.concrete_fields:
        if field.primary_key:
            continue
        payload[field.name] = _jsonable(getattr(instance, field.attname))
    return payload


def _ordered_payload(queryset: models.QuerySet[Any]) -> list[dict[str, object]]:
    return [_row_payload(row) for row in queryset.order_by("pk")]


class ProcedureVersionReviewPolicy(models.Model):
    procedure_version = models.OneToOneField(
        ProcedureVersion,
        on_delete=models.CASCADE,
        related_name="review_policy",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_review_policies",
    )
    legal_risk = models.BooleanField(default=False)
    military_risk = models.BooleanField(default=False)
    custody_guardianship_risk = models.BooleanField(default=False)
    contested_identity_risk = models.BooleanField(default=False)

    class Meta:
        app_label = "knowledge"
        ordering = ("procedure_version__semantic_id",)

    def _editable_owner(self) -> ProcedureVersion:
        if self.procedure_version_id is None:
            raise ValidationError("Review policy ownership is required.")
        owner = ProcedureVersion.objects.filter(pk=self.procedure_version_id).first()
        if owner is None:
            raise ValidationError("Review policy ownership is required.")
        if owner.state != ProcedureVersion.State.DRAFT:
            raise ValidationError("Review policy is editable only while its version is draft.")
        return owner

    @property
    def risk_kinds(self) -> tuple[str, ...]:
        values = (
            ("legal", self.legal_risk),
            ("military", self.military_risk),
            ("custody_guardianship", self.custody_guardianship_risk),
            ("contested_identity", self.contested_identity_risk),
        )
        return tuple(kind for kind, enabled in values if enabled)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self._editable_owner()
        stored = type(self).objects.filter(pk=self.pk).only("procedure_version_id").first()
        if stored is not None and stored.procedure_version_id != self.procedure_version_id:
            raise ValidationError("Review policy ownership cannot be reassigned.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        self._editable_owner()
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"review-policy:{self.procedure_version.semantic_id}"


class ProcedureVersionReviewApproval(models.Model):
    class ApprovalKind(models.TextChoices):
        DIMENSION = "dimension", "Review dimension"
        SPECIALIST = "specialist", "Specialist"

    class Dimension(models.TextChoices):
        EVIDENCE_SOURCE = "evidence_source", "Evidence/source"
        RULE_LOGIC = "rule_logic", "Rule/logic"
        SCENARIO_BEHAVIOR = "scenario_behavior", "Scenario/behavior"
        BILINGUAL_SEMANTIC = "bilingual_semantic", "Arabic/English semantic"
        DISCREPANCY = "discrepancy", "Discrepancy"

    class SpecialistRisk(models.TextChoices):
        LEGAL = "legal", "Legal"
        MILITARY = "military", "Military"
        CUSTODY_GUARDIANSHIP = "custody_guardianship", "Custody/guardianship"
        CONTESTED_IDENTITY = "contested_identity", "Contested identity"

    procedure_version = models.ForeignKey(
        ProcedureVersion,
        on_delete=models.PROTECT,
        related_name="review_approvals",
    )
    approval_kind = models.CharField(max_length=16, choices=ApprovalKind.choices)
    dimension = models.CharField(max_length=32, choices=Dimension.choices, blank=True)
    specialist_risk = models.CharField(
        max_length=32,
        choices=SpecialistRisk.choices,
        blank=True,
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="procedure_version_review_approvals",
    )
    reviewed_signature = models.CharField(max_length=64)
    approved_at = models.DateTimeField()

    class Meta:
        app_label = "knowledge"
        ordering = ("approved_at", "id")
        permissions = [
            ("review_procedureversion", "Can approve Procedure Version review dimensions"),
            ("specialist_approve_legal", "Can approve high-risk legal material"),
            ("specialist_approve_military", "Can approve high-risk military material"),
            (
                "specialist_approve_custody_guardianship",
                "Can approve high-risk custody/guardianship material",
            ),
            (
                "specialist_approve_contested_identity",
                "Can approve high-risk contested-identity material",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(approval_kind__in=["dimension", "specialist"]),
                name="review_approval_kind_supported",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        approval_kind="dimension",
                        dimension__in=list(_REVIEW_DIMENSIONS),
                        specialist_risk="",
                    )
                    | Q(
                        approval_kind="specialist",
                        dimension="",
                        specialist_risk__in=list(_SPECIALIST_RISKS),
                    )
                ),
                name="review_approval_scope_shape",
            ),
            models.CheckConstraint(
                condition=Q(reviewed_signature__regex=r"^[0-9a-f]{64}$"),
                name="review_approval_signature_sha256",
            ),
            models.UniqueConstraint(
                fields=("procedure_version", "dimension", "reviewer", "reviewed_signature"),
                condition=Q(approval_kind="dimension"),
                name="unique_dimension_review_approval",
            ),
            models.UniqueConstraint(
                fields=(
                    "procedure_version",
                    "specialist_risk",
                    "reviewer",
                    "reviewed_signature",
                ),
                condition=Q(approval_kind="specialist"),
                name="unique_specialist_review_approval",
            ),
        ]

    def clean(self) -> None:
        if self.approval_kind == self.ApprovalKind.DIMENSION:
            if self.dimension not in self.Dimension.values or self.specialist_risk:
                raise ValidationError("Dimension approvals require exactly one review dimension.")
        elif self.approval_kind == self.ApprovalKind.SPECIALIST:
            if self.specialist_risk not in self.SpecialistRisk.values or self.dimension:
                raise ValidationError("Specialist approvals require exactly one specialist risk.")
        else:
            raise ValidationError("Unsupported review approval kind.")
        if len(self.reviewed_signature) != 64 or any(
            character not in "0123456789abcdef" for character in self.reviewed_signature
        ):
            raise ValidationError("Review approvals require a SHA-256 reviewed-state signature.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError("Review approvals are immutable.")
        owner = ProcedureVersion.objects.filter(pk=self.procedure_version_id).first()
        if owner is None or owner.state != ProcedureVersion.State.DRAFT:
            raise ValidationError("Review approvals may be recorded only for a draft version.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Review approvals are preserved audit history.")

    def __str__(self) -> str:
        scope = self.dimension or self.specialist_risk
        return f"review:{self.procedure_version.semantic_id}:{self.approval_kind}:{scope}"


class ProcedureVersionAuditApproval(models.Model):
    audit_event = models.ForeignKey(
        ProcedureVersionAuditEvent,
        on_delete=models.PROTECT,
        related_name="approvals",
    )
    approval = models.ForeignKey(
        ProcedureVersionReviewApproval,
        on_delete=models.PROTECT,
        related_name="publication_audit_rows",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="procedure_version_audit_approvals",
    )
    approval_kind = models.CharField(
        max_length=16,
        choices=ProcedureVersionReviewApproval.ApprovalKind.choices,
    )
    dimension = models.CharField(
        max_length=32,
        choices=ProcedureVersionReviewApproval.Dimension.choices,
        blank=True,
    )
    specialist_risk = models.CharField(
        max_length=32,
        choices=ProcedureVersionReviewApproval.SpecialistRisk.choices,
        blank=True,
    )
    approved_at = models.DateTimeField()

    class Meta:
        app_label = "knowledge"
        ordering = (
            "audit_event_id",
            "approval_kind",
            "dimension",
            "specialist_risk",
            "id",
        )
        constraints = [
            models.UniqueConstraint(
                fields=("audit_event", "approval"),
                name="unique_publication_audit_approval",
            )
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        raise ValidationError("Publication approval audit rows are lifecycle-service records.")

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Publication approval audit rows are immutable.")


def _version_evidence_links(version: ProcedureVersion) -> models.QuerySet[EvidenceLink]:
    from .fees import Fee
    from .procedure_dependencies import ProcedureDependency
    from .service_point_routing import ProcedureServicePointAssociation

    checklist_ids = ChecklistItem.objects.filter(procedure_version=version).values_list(
        "pk", flat=True
    )
    basis_ids = EligibilityBasis.objects.filter(procedure_version=version).values_list(
        "pk", flat=True
    )
    step_ids = Step.objects.filter(procedure_version=version).values_list("pk", flat=True)
    warning_ids = Warning.objects.filter(procedure_version=version).values_list("pk", flat=True)
    fee_ids = Fee.objects.filter(procedure_version=version).values_list("pk", flat=True)
    dependency_ids = ProcedureDependency.objects.filter(procedure_version=version).values_list(
        "pk", flat=True
    )
    association_rows = ProcedureServicePointAssociation.objects.filter(procedure_version=version)
    association_ids = association_rows.values_list("pk", flat=True)
    material_ids = association_rows.values_list("service_point_version_id", flat=True)
    return EvidenceLink.objects.filter(
        Q(checklist_item_id__in=checklist_ids)
        | Q(step_id__in=step_ids)
        | Q(warning_id__in=warning_ids)
        | Q(fee_id__in=fee_ids)
        | Q(eligibility_basis_id__in=basis_ids)
        | Q(procedure_dependency_id__in=dependency_ids)
        | Q(procedure_service_point_association_id__in=association_ids)
        | Q(service_point_version_id__in=material_ids)
    ).order_by("pk")


def _discrepancies_for_version(
    version: ProcedureVersion,
) -> models.QuerySet[EvidenceDiscrepancy]:
    link_ids = _version_evidence_links(version).values_list("pk", flat=True)
    return (
        EvidenceDiscrepancy.objects.filter(evidence_links__pk__in=link_ids)
        .distinct()
        .order_by("pk")
    )


def required_review_dimensions(version: ProcedureVersion) -> frozenset[str]:
    dimensions = set(_CORE_REVIEW_DIMENSIONS)
    if _discrepancies_for_version(version).exists():
        dimensions.add(ProcedureVersionReviewApproval.Dimension.DISCREPANCY)
    return frozenset(dimensions)


def review_state_signature(version: ProcedureVersion) -> str:
    """Hash the complete consequential draft state reviewed as one coherent publication unit."""

    link_rows = tuple(_version_evidence_links(version))
    link_ids = [row.pk for row in link_rows if row.pk is not None]
    source_link_rows = tuple(
        EvidenceLinkSource.objects.filter(evidence_link_id__in=link_ids).order_by("pk")
    )
    source_ids = sorted({row.source_id for row in source_link_rows})
    source_rows = tuple(Source.objects.filter(pk__in=source_ids).order_by("pk"))
    authority_ids = sorted({row.authority_id for row in source_rows})
    document_type_ids = sorted(
        {
            value
            for value in ChecklistItem.objects.filter(procedure_version=version).values_list(
                "document_type_id", flat=True
            )
            if value is not None
        }
    )
    discrepancies = tuple(_discrepancies_for_version(version))
    discrepancy_ids = [row.pk for row in discrepancies if row.pk is not None]
    policy = ProcedureVersionReviewPolicy.objects.filter(procedure_version=version).first()
    payload: dict[str, object] = {
        "planning_behavior": planning_behavior_signature(version),
        "review_policy": None if policy is None else _row_payload(policy),
        "scenarios": _ordered_payload(PlanningScenario.objects.filter(procedure_version=version)),
        "evidence_links": [_row_payload(row) for row in link_rows],
        "evidence_sources": [_row_payload(row) for row in source_link_rows],
        "sources": [_row_payload(row) for row in source_rows],
        "authorities": _ordered_payload(Authority.objects.filter(pk__in=authority_ids)),
        "document_types": _ordered_payload(DocumentType.objects.filter(pk__in=document_type_ids)),
        "discrepancies": [
            {
                "status": row.status,
                "outcome_state": row.outcome_state,
                "rationale": row.rationale,
                "resolution": row.resolution,
                "anchor_evidence_link_id": row.anchor_evidence_link_id,
            }
            for row in discrepancies
        ],
        "discrepancy_evidence": _ordered_payload(
            EvidenceDiscrepancyEvidence.objects.filter(discrepancy_id__in=discrepancy_ids)
        ),
    }
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approve_review_dimension(
    version_id: int,
    *,
    dimension: str,
    actor: User,
) -> ProcedureVersionReviewApproval:
    _validate_actor(actor)
    if dimension not in _REVIEW_DIMENSIONS:
        raise ValidationError("Unsupported Procedure Version review dimension.")
    if not actor.has_perm(_REVIEW_PERMISSION):
        raise ValidationError("Reviewer lacks the Procedure Version review permission.")
    with transaction.atomic():
        version = ProcedureVersion.objects.select_for_update().get(pk=version_id)
        if version.state != ProcedureVersion.State.DRAFT:
            raise ValidationError("Only draft Procedure Versions may be approved.")
        try:
            policy = ProcedureVersionReviewPolicy.objects.select_for_update().get(
                procedure_version=version
            )
        except ProcedureVersionReviewPolicy.DoesNotExist as exc:
            raise ValidationError(
                "A review policy with an accountable author is required."
            ) from exc
        if actor.pk == policy.author_id:
            raise ValidationError("The accountable author cannot approve their own draft.")
        if dimension not in required_review_dimensions(version):
            raise ValidationError("That review dimension is not applicable to this draft.")
        return ProcedureVersionReviewApproval.objects.create(
            procedure_version=version,
            approval_kind=ProcedureVersionReviewApproval.ApprovalKind.DIMENSION,
            dimension=dimension,
            specialist_risk="",
            reviewer=actor,
            reviewed_signature=review_state_signature(version),
            approved_at=timezone.now(),
        )


def approve_specialist_risk(
    version_id: int,
    *,
    risk_kind: str,
    actor: User,
) -> ProcedureVersionReviewApproval:
    _validate_actor(actor)
    permission = _SPECIALIST_PERMISSIONS.get(risk_kind)
    if permission is None:
        raise ValidationError("Unsupported specialist review risk.")
    if not actor.has_perm(permission):
        raise ValidationError("Reviewer lacks the required specialist approval permission.")
    with transaction.atomic():
        version = ProcedureVersion.objects.select_for_update().get(pk=version_id)
        if version.state != ProcedureVersion.State.DRAFT:
            raise ValidationError("Only draft Procedure Versions may be approved.")
        try:
            policy = ProcedureVersionReviewPolicy.objects.select_for_update().get(
                procedure_version=version
            )
        except ProcedureVersionReviewPolicy.DoesNotExist as exc:
            raise ValidationError(
                "A review policy with an accountable author is required."
            ) from exc
        if actor.pk == policy.author_id:
            raise ValidationError("The accountable author cannot approve their own draft.")
        if risk_kind not in policy.risk_kinds:
            raise ValidationError("That specialist risk is not configured for this draft.")
        return ProcedureVersionReviewApproval.objects.create(
            procedure_version=version,
            approval_kind=ProcedureVersionReviewApproval.ApprovalKind.SPECIALIST,
            dimension="",
            specialist_risk=risk_kind,
            reviewer=actor,
            reviewed_signature=review_state_signature(version),
            approved_at=timezone.now(),
        )


def _approval_diagnostic(
    approvals: tuple[ProcedureVersionReviewApproval, ...],
    *,
    current_signature: str,
    author_id: int,
    publisher_id: int | None,
    permission: str,
    missing_code: str,
    stale_code: str,
    independence_code: str,
    ineligible_code: str,
    detail: str,
) -> PublicationDiagnostic | None:
    if not approvals:
        return PublicationDiagnostic(
            ProcedureVersionReviewPublicationGate.name,
            missing_code,
            detail,
        )
    fresh = tuple(row for row in approvals if row.reviewed_signature == current_signature)
    if not fresh:
        return PublicationDiagnostic(
            ProcedureVersionReviewPublicationGate.name,
            stale_code,
            detail,
        )
    eligible = tuple(row for row in fresh if row.reviewer.has_perm(permission))
    if not eligible:
        return PublicationDiagnostic(
            ProcedureVersionReviewPublicationGate.name,
            ineligible_code,
            detail,
        )
    independent = tuple(
        row
        for row in eligible
        if row.reviewer_id != author_id
        and (publisher_id is None or row.reviewer_id != publisher_id)
    )
    if not independent:
        return PublicationDiagnostic(
            ProcedureVersionReviewPublicationGate.name,
            independence_code,
            detail,
        )
    return None


def _set_review_signature(signature: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [_SIGNATURE_SETTING, signature])


class ProcedureVersionReviewPublicationGate:
    name = "core.procedure_version_reviews"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        if not getattr(settings, "PROCEDURE_VERSION_REVIEWS_REQUIRED", True):
            return ()
        try:
            policy = ProcedureVersionReviewPolicy.objects.select_for_update().get(
                procedure_version=context.version
            )
        except ProcedureVersionReviewPolicy.DoesNotExist:
            return (PublicationDiagnostic(self.name, "missing_review_policy"),)

        current_signature = review_state_signature(context.version)
        approvals = tuple(
            ProcedureVersionReviewApproval.objects.select_for_update()
            .filter(procedure_version=context.version)
            .select_related("reviewer")
            .order_by("approval_kind", "dimension", "specialist_risk", "approved_at", "pk")
        )
        publisher_id = context.actor.pk
        failures: list[PublicationDiagnostic] = []
        for dimension in sorted(required_review_dimensions(context.version)):
            rows = tuple(
                row
                for row in approvals
                if row.approval_kind == ProcedureVersionReviewApproval.ApprovalKind.DIMENSION
                and row.dimension == dimension
            )
            diagnostic = _approval_diagnostic(
                rows,
                current_signature=current_signature,
                author_id=policy.author_id,
                publisher_id=publisher_id,
                permission=_REVIEW_PERMISSION,
                missing_code="missing_review_approval",
                stale_code="stale_review_approval",
                independence_code="review_not_independent",
                ineligible_code="reviewer_not_eligible",
                detail=dimension,
            )
            if diagnostic is not None:
                failures.append(diagnostic)

        for risk_kind in policy.risk_kinds:
            rows = tuple(
                row
                for row in approvals
                if row.approval_kind == ProcedureVersionReviewApproval.ApprovalKind.SPECIALIST
                and row.specialist_risk == risk_kind
            )
            diagnostic = _approval_diagnostic(
                rows,
                current_signature=current_signature,
                author_id=policy.author_id,
                publisher_id=publisher_id,
                permission=_SPECIALIST_PERMISSIONS[risk_kind],
                missing_code="missing_specialist_approval",
                stale_code="stale_specialist_approval",
                independence_code="specialist_review_not_independent",
                ineligible_code="specialist_reviewer_not_eligible",
                detail=risk_kind,
            )
            if diagnostic is not None:
                failures.append(diagnostic)

        if failures:
            return tuple(failures)
        _set_review_signature(current_signature)
        return ()


__all__ = (
    "ProcedureVersionAuditApproval",
    "ProcedureVersionReviewApproval",
    "ProcedureVersionReviewPolicy",
    "ProcedureVersionReviewPublicationGate",
    "approve_review_dimension",
    "approve_specialist_risk",
    "required_review_dimensions",
    "review_state_signature",
)
