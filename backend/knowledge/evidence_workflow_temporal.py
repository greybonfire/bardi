"""Temporal projection for internal evidence workflow history.

The persisted semantic snapshot is immutable. Discrepancy transitions and semantic-preserving
re-verification events are applied only when they had been established by the caller's explicit
evaluation date, so later editorial work cannot rewrite an earlier planning result.
"""

from __future__ import annotations

from collections.abc import Iterable
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
from .evidence_trust_projection import (
    DiscrepancyTransition,
    Reverification,
    project_evidence_trust,
)


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


def _owner_related_paths(anchor_path: str) -> tuple[str, ...]:
    """Load exactly the owner relationships consumed by workflow._owner_key."""

    return tuple(
        f"{anchor_path}__{field}"
        if kind == "service_point_version"
        else f"{anchor_path}__{field}__procedure_version"
        for kind, field in workflow._OWNER_FIELDS
    )


def _captured_history_as_of(
    evaluation_date: date,
    *,
    evidence_link_ids: frozenset[int] | None = None,
) -> Iterable[DiscrepancyTransition | Reverification]:
    """Finish both history reads before yielding detached records in replay order."""
    timeline: list[tuple[datetime, int, int, str, object]] = []
    transitions = EvidenceDiscrepancyTransition.objects.filter(
        occurred_at__date__lte=evaluation_date
    )
    reverifications = workflow.EvidenceReverificationEvent.objects.filter(
        meaning_changed=False,
        occurred_at__date__lte=evaluation_date,
    )
    if evidence_link_ids is not None:
        transitions = transitions.filter(discrepancy__anchor_evidence_link_id__in=evidence_link_ids)
        reverifications = reverifications.filter(anchor_evidence_link_id__in=evidence_link_ids)
    for transition in transitions.select_related(
        *_owner_related_paths("discrepancy__anchor_evidence_link")
    ).order_by("occurred_at", "pk"):
        timeline.append((transition.occurred_at, 0, transition.pk, "discrepancy", transition))
    for review in reverifications.select_related(
        *_owner_related_paths("anchor_evidence_link")
    ).order_by("occurred_at", "pk"):
        timeline.append((review.occurred_at, 1, review.pk, "reverification", review))

    # Resolve one preloaded owner, then let projection replay its record before the
    # next owner is resolved. Eagerly converting this iterator to a list would move
    # later owner failures ahead of earlier replay failures.
    def records() -> Iterable[DiscrepancyTransition | Reverification]:
        for occurred, _, _, kind, raw in sorted(timeline, key=lambda item: item[:3]):
            if kind == "discrepancy":
                transition = cast(EvidenceDiscrepancyTransition, raw)
                yield DiscrepancyTransition(
                    owner=workflow._owner_key(transition.discrepancy.anchor_evidence_link),
                    occurred_at=occurred,
                    discrepancy_id=transition.discrepancy_id,
                    event_type=transition.event_type,
                    verification_state=cast(VerificationState, transition.verification_state),
                )
            else:
                review = cast(workflow.EvidenceReverificationEvent, raw)
                yield Reverification(
                    owner=workflow._owner_key(review.anchor_evidence_link),
                    occurred_at=occurred,
                    verification_state=cast(VerificationState, review.verification_state),
                    verified_on=review.verified_on,
                    reverify_on=review.reverify_on,
                )

    return records()


def apply_evidence_workflow_as_of(
    snapshot: KnowledgeSnapshot,
    evaluation_date: date,
    *,
    evidence_link_ids: frozenset[int] | None = None,
) -> KnowledgeSnapshot:
    """Apply only workflow history established on or before ``evaluation_date``."""

    history = _captured_history_as_of(evaluation_date, evidence_link_ids=evidence_link_ids)
    return project_evidence_trust(snapshot, history)


def load_knowledge_snapshot_as_of(evaluation_date: date) -> KnowledgeSnapshot:
    """Load one detached snapshot and project workflow history at an explicit date."""

    return apply_evidence_workflow_as_of(
        knowledge_domain._materialize_knowledge_snapshot(), evaluation_date
    )


def load_consistent_knowledge_snapshot_as_of(evaluation_date: date) -> KnowledgeSnapshot:
    """Load semantic and workflow state in one repeatable-read transaction."""

    if connection.in_atomic_block:
        raise RuntimeError("a consistent knowledge snapshot requires an outermost transaction")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return apply_evidence_workflow_as_of(
            knowledge_domain._materialize_knowledge_snapshot(), evaluation_date
        )


def load_consistent_service_knowledge_snapshot_as_of(
    service_id: str, evaluation_date: date
) -> KnowledgeSnapshot:
    """Load one requested Service graph and its coherent historical workflow state."""

    if connection.in_atomic_block:
        raise RuntimeError("a consistent knowledge snapshot requires an outermost transaction")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        from .planning_scope import discover_planning_scope

        scope = discover_planning_scope(service_id)
        snapshot = knowledge_domain._materialize_knowledge_snapshot(
            scope, evaluation_date=evaluation_date
        )
        return apply_evidence_workflow_as_of(
            snapshot,
            evaluation_date,
            evidence_link_ids=scope.evidence_link_ids,
        )


__all__ = (
    "EvidenceDiscrepancyTransition",
    "apply_evidence_workflow_as_of",
    "load_consistent_knowledge_snapshot_as_of",
    "load_consistent_service_knowledge_snapshot_as_of",
    "load_knowledge_snapshot_as_of",
)
