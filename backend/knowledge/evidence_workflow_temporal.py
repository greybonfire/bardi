"""Temporal projection for internal evidence workflow history.

The persisted semantic snapshot is immutable. Discrepancy transitions and semantic-preserving
re-verification events are applied only when they had been established by the caller's explicit
evaluation date, so later editorial work cannot rewrite an earlier planning result.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from typing import Any, cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from planning.catalog import KnowledgeSnapshot
from planning.trust import VERIFICATION_CHOICES, VerificationState

from . import domain as knowledge_domain
from . import evidence_workflow as workflow


class EvidenceDiscrepancyTransition(models.Model):
    class EventType(models.TextChoices):
        OPENED = "opened", "Opened"
        RESOLVED = "resolved", "Resolved"

    discrepancy = models.ForeignKey(
        workflow.EvidenceDiscrepancy,
        on_delete=models.PROTECT,
        related_name="transitions",
    )
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    verification_state = models.CharField(max_length=24, choices=VERIFICATION_CHOICES)
    occurred_at = models.DateTimeField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evidence_discrepancy_transitions",
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("occurred_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("discrepancy", "event_type"),
                name="unique_evidence_discrepancy_transition",
            ),
            models.CheckConstraint(
                condition=models.Q(event_type__in=["opened", "resolved"]),
                name="evidence_discrepancy_transition_type_supported",
            ),
            models.CheckConstraint(
                condition=models.Q(verification_state__in=sorted(workflow._SHARED_STATES)),
                name="evidence_discrepancy_transition_state_supported",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError("Discrepancy transitions are append-only history.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Discrepancy transitions are append-only history.")


@receiver(
    pre_save,
    sender=workflow.EvidenceDiscrepancy,
    dispatch_uid="knowledge.capture_evidence_discrepancy_transition",
)
def _capture_discrepancy_transition(
    sender: type[workflow.EvidenceDiscrepancy],
    instance: workflow.EvidenceDiscrepancy,
    **_: object,
) -> None:
    if instance._state.adding or instance.pk is None:
        return
    previous = sender.objects.filter(pk=instance.pk).values("status", "outcome_state").first()
    if previous is None:
        return
    previous_status = previous["status"]
    previous_state = previous["outcome_state"]
    if (
        previous_status == workflow.EvidenceDiscrepancy.Status.OPEN
        and instance.status == workflow.EvidenceDiscrepancy.Status.OPEN
        and previous_state != instance.outcome_state
    ):
        raise ValidationError(
            "An open discrepancy's trust outcome is immutable; resolve it to record a new outcome."
        )
    instance._workflow_previous_status = previous_status  # type: ignore[attr-defined]


@receiver(
    post_save,
    sender=workflow.EvidenceDiscrepancy,
    dispatch_uid="knowledge.persist_evidence_discrepancy_transition",
)
def _persist_discrepancy_transition(
    sender: type[workflow.EvidenceDiscrepancy],
    instance: workflow.EvidenceDiscrepancy,
    created: bool,
    **_: object,
) -> None:
    del sender
    if created:
        if instance.created_at is None or instance.created_by_id is None:
            raise ValidationError("Created discrepancies require complete transition metadata.")
        EvidenceDiscrepancyTransition.objects.create(
            discrepancy=instance,
            event_type=EvidenceDiscrepancyTransition.EventType.OPENED,
            verification_state=instance.outcome_state,
            occurred_at=instance.created_at,
            actor_id=instance.created_by_id,
        )
        return

    previous_status = getattr(instance, "_workflow_previous_status", None)
    if (
        previous_status == workflow.EvidenceDiscrepancy.Status.OPEN
        and instance.status == workflow.EvidenceDiscrepancy.Status.RESOLVED
    ):
        if instance.resolved_at is None or instance.resolved_by_id is None:
            raise ValidationError("Resolved discrepancies require complete transition metadata.")
        EvidenceDiscrepancyTransition.objects.create(
            discrepancy=instance,
            event_type=EvidenceDiscrepancyTransition.EventType.RESOLVED,
            verification_state=instance.outcome_state,
            occurred_at=instance.resolved_at,
            actor_id=instance.resolved_by_id,
        )


def _workflow_overlays_as_of(
    evaluation_date: date,
) -> dict[tuple[str, str, str], workflow._TrustOverlay]:
    timeline: list[tuple[datetime, int, int, str, object]] = []
    for transition in (
        EvidenceDiscrepancyTransition.objects.filter(occurred_at__date__lte=evaluation_date)
        .select_related("discrepancy__anchor_evidence_link")
        .order_by("occurred_at", "pk")
    ):
        timeline.append((transition.occurred_at, 0, transition.pk, "discrepancy", transition))
    for review in (
        workflow.EvidenceReverificationEvent.objects.filter(
            meaning_changed=False,
            occurred_at__date__lte=evaluation_date,
        )
        .select_related("anchor_evidence_link")
        .order_by("occurred_at", "pk")
    ):
        timeline.append((review.occurred_at, 1, review.pk, "reverification", review))

    overlays: dict[tuple[str, str, str], workflow._TrustOverlay] = {}
    for occurred, _, _, kind, raw in sorted(timeline, key=lambda item: item[:3]):
        if kind == "discrepancy":
            transition = cast(EvidenceDiscrepancyTransition, raw)
            key = workflow._owner_key(transition.discrepancy.anchor_evidence_link)
            overlay = overlays.setdefault(key, workflow._TrustOverlay())
            overlay.state = cast(VerificationState, transition.verification_state)
            overlay.owner_verified_on = workflow._max_date(
                overlay.owner_verified_on, occurred.date()
            )
            continue

        review = cast(workflow.EvidenceReverificationEvent, raw)
        key = workflow._owner_key(review.anchor_evidence_link)
        overlay = overlays.setdefault(key, workflow._TrustOverlay())
        established_on = max(review.verified_on, occurred.date())
        overlay.state = cast(VerificationState, review.verification_state)
        overlay.owner_verified_on = established_on
        overlay.reverify_on = review.reverify_on
        overlay.reverify_seen = True
        overlay.evidence_state = cast(VerificationState, review.verification_state)
        overlay.evidence_verified_on = established_on
        overlay.evidence_reverify_on = review.reverify_on
    return overlays


def apply_evidence_workflow_as_of(
    snapshot: KnowledgeSnapshot,
    evaluation_date: date,
) -> KnowledgeSnapshot:
    """Apply only workflow history established on or before ``evaluation_date``."""

    overlays = _workflow_overlays_as_of(evaluation_date)
    if not overlays:
        return snapshot

    def version_items(version: Any, attribute: str, kind: str) -> tuple[Any, ...]:
        return tuple(
            workflow._overlay_item(item, overlays[(kind, version.semantic_id, item.semantic_id)])
            if (kind, version.semantic_id, item.semantic_id) in overlays
            else item
            for item in getattr(version, attribute)
        )

    versions = tuple(
        replace(
            version,
            checklist_items=version_items(version, "checklist_items", "checklist"),
            eligibility_bases=version_items(version, "eligibility_bases", "eligibility_basis"),
            steps=version_items(version, "steps", "step"),
            warnings=version_items(version, "warnings", "warning"),
            fees=version_items(version, "fees", "fee"),
            dependencies=version_items(version, "dependencies", "procedure_dependency"),
            service_point_associations=version_items(
                version,
                "service_point_associations",
                "procedure_service_point_association",
            ),
        )
        for version in snapshot.procedure_versions
    )
    service_point_versions = tuple(
        workflow._overlay_item(item, overlays[("service_point_version", "", item.semantic_id)])
        if ("service_point_version", "", item.semantic_id) in overlays
        else item
        for item in snapshot.service_point_versions
    )
    return replace(
        snapshot,
        procedure_versions=versions,
        service_point_versions=service_point_versions,
    )


def load_knowledge_snapshot_as_of(evaluation_date: date) -> KnowledgeSnapshot:
    """Load one detached snapshot and project workflow history at an explicit date."""

    return apply_evidence_workflow_as_of(workflow._original_materialize(), evaluation_date)


def load_consistent_knowledge_snapshot_as_of(evaluation_date: date) -> KnowledgeSnapshot:
    """Load semantic and workflow state in one repeatable-read transaction."""

    if connection.in_atomic_block:
        raise RuntimeError("a consistent knowledge snapshot requires an outermost transaction")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return apply_evidence_workflow_as_of(workflow._original_materialize(), evaluation_date)


# The original issue-46 implementation installed a latest-state projection directly on the
# generic loader. A generic snapshot has no evaluation date, so that hook cannot be temporally
# correct. Restore the pre-workflow materializer; callers that need editorial trust state must
# use one of the explicit ``*_as_of`` loaders above.
knowledge_domain._materialize_knowledge_snapshot = workflow._original_materialize


__all__ = (
    "EvidenceDiscrepancyTransition",
    "apply_evidence_workflow_as_of",
    "load_consistent_knowledge_snapshot_as_of",
    "load_knowledge_snapshot_as_of",
)
