"""Internal evidence discrepancy and re-verification workflow.

Published semantic records stay immutable. Editorial workflow records are append-only or
one-way and are projected onto detached planning snapshots as trust/freshness overlays.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from planning.catalog import KnowledgeSnapshot
from planning.trust import VERIFICATION_CHOICES, VerificationState

from . import domain as knowledge_domain
from .models import EvidenceLink, ProcedureVersion, _required
from .publication import PublicationContext, PublicationDiagnostic

_OWNER_FIELDS = (
    ("checklist", "checklist_item"),
    ("step", "step"),
    ("warning", "warning"),
    ("fee", "fee"),
    ("eligibility_basis", "eligibility_basis"),
    ("procedure_dependency", "procedure_dependency"),
    ("procedure_service_point_association", "procedure_service_point_association"),
    ("service_point_version", "service_point_version"),
)
_OPEN_OUTCOMES = frozenset({"needs_reverification", "disputed", "unknown"})
_SHARED_STATES = frozenset(choice[0] for choice in VERIFICATION_CHOICES)


def _owner_key(link: EvidenceLink) -> tuple[str, str, str]:
    for kind, field in _OWNER_FIELDS:
        if getattr(link, f"{field}_id", None) is None:
            continue
        owner = getattr(link, field)
        if kind == "service_point_version":
            return kind, "", cast(str, owner.semantic_id)
        return (
            kind,
            cast(str, owner.procedure_version.semantic_id),
            cast(str, owner.semantic_id),
        )
    raise ValidationError("Evidence must have exactly one supported claim owner.")


def _owning_versions(link: EvidenceLink) -> tuple[ProcedureVersion, ...]:
    multiple = getattr(link, "owning_versions", None)
    if callable(multiple):
        return cast(tuple[ProcedureVersion, ...], multiple())
    return (link.owning_version(),)


def _owner_evidence(link: EvidenceLink) -> tuple[EvidenceLink, ...]:
    owner = link.owner
    manager = getattr(owner, "evidence_links", None)
    if manager is None:
        raise ValidationError("Evidence owner does not expose its evidence set.")
    return tuple(manager.order_by("pk"))


def _validate_actor(actor: models.Model) -> None:
    user_model = get_user_model()
    if (
        not isinstance(actor, user_model)
        or actor.pk is None
        or not user_model._default_manager.filter(pk=actor.pk).exists()
    ):
        raise ValidationError("A saved staff actor is required.")


class EvidenceDiscrepancy(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    anchor_evidence_link = models.ForeignKey(
        EvidenceLink,
        on_delete=models.PROTECT,
        related_name="anchored_discrepancies",
    )
    evidence_links = models.ManyToManyField(
        EvidenceLink,
        through="EvidenceDiscrepancyEvidence",
        related_name="discrepancies",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    outcome_state = models.CharField(
        max_length=24,
        choices=VERIFICATION_CHOICES,
        default="disputed",
    )
    rationale = models.TextField()
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_evidence_discrepancies",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="resolved_evidence_discrepancies",
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("status", "created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["open", "resolved"]),
                name="evidence_discrepancy_status_supported",
            ),
            models.CheckConstraint(
                condition=Q(outcome_state__in=sorted(_SHARED_STATES)),
                name="evidence_discrepancy_outcome_supported",
            ),
            models.CheckConstraint(
                condition=Q(rationale__regex=r".*[^[:space:]].*"),
                name="evidence_discrepancy_rationale_nonblank",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="open", resolved_at__isnull=True, resolved_by__isnull=True)
                    | Q(status="resolved", resolved_at__isnull=False, resolved_by__isnull=False)
                ),
                name="evidence_discrepancy_lifecycle",
            ),
            models.CheckConstraint(
                condition=~Q(status="open") | Q(outcome_state__in=sorted(_OPEN_OUTCOMES)),
                name="open_discrepancy_is_inconclusive",
            ),
        ]

    def clean(self) -> None:
        _required(self.rationale, "rationale")
        if self.outcome_state not in _SHARED_STATES:
            raise ValidationError({"outcome_state": "Unsupported shared verification state."})
        if self.status == self.Status.OPEN:
            if self.outcome_state not in _OPEN_OUTCOMES:
                raise ValidationError(
                    {"outcome_state": "Open discrepancies must remain inconclusive."}
                )
            if self.resolved_at is not None or self.resolved_by_id is not None:
                raise ValidationError("Open discrepancies cannot carry resolution metadata.")
        elif self.status == self.Status.RESOLVED:
            if self.resolved_at is None or self.resolved_by_id is None:
                raise ValidationError("Resolved discrepancies require resolution metadata.")
        else:
            raise ValidationError({"status": "Unsupported discrepancy status."})
        if self.anchor_evidence_link_id is not None:
            _owner_key(self.anchor_evidence_link)

    def save(self, *args: Any, **kwargs: Any) -> None:
        stored = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if stored is None:
            if self.status != self.Status.OPEN:
                raise ValidationError("Discrepancies must be created open.")
        else:
            if stored.status == self.Status.RESOLVED:
                raise ValidationError("Resolved discrepancies are immutable.")
            if stored.anchor_evidence_link_id != self.anchor_evidence_link_id:
                raise ValidationError("Discrepancy ownership cannot be reassigned.")
            if stored.created_by_id != self.created_by_id or stored.created_at != self.created_at:
                raise ValidationError("Discrepancy creation metadata is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Evidence discrepancies are preserved research history.")

    def __str__(self) -> str:
        return f"discrepancy:{self.pk or 'new'}:{_owner_key(self.anchor_evidence_link)}"


class EvidenceDiscrepancyEvidence(models.Model):
    discrepancy = models.ForeignKey(
        EvidenceDiscrepancy,
        on_delete=models.CASCADE,
        related_name="evidence_rows",
    )
    evidence_link = models.ForeignKey(
        EvidenceLink,
        on_delete=models.PROTECT,
        related_name="discrepancy_rows",
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("discrepancy_id", "evidence_link_id")
        constraints = [
            models.UniqueConstraint(
                fields=("discrepancy", "evidence_link"),
                name="unique_discrepancy_evidence_link",
            )
        ]

    def clean(self) -> None:
        if self.discrepancy_id and self.evidence_link_id:
            if _owner_key(self.discrepancy.anchor_evidence_link) != _owner_key(self.evidence_link):
                raise ValidationError("Discrepancy evidence must belong to one affected subject.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValidationError("Discrepancy evidence links cannot be reassigned.")
        if self.discrepancy_id and self.discrepancy.status != EvidenceDiscrepancy.Status.OPEN:
            raise ValidationError("Resolved discrepancy evidence is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if self.discrepancy.status != EvidenceDiscrepancy.Status.OPEN:
            raise ValidationError("Resolved discrepancy evidence is immutable.")
        return super().delete(*args, **kwargs)


class EvidenceReverificationEvent(models.Model):
    anchor_evidence_link = models.ForeignKey(
        EvidenceLink,
        on_delete=models.PROTECT,
        related_name="reverification_events",
    )
    reviewed_evidence_links = models.ManyToManyField(
        EvidenceLink,
        through="EvidenceReverificationEvidence",
        related_name="review_events",
    )
    verification_state = models.CharField(max_length=24, choices=VERIFICATION_CHOICES)
    verified_on = models.DateField()
    reverify_on = models.DateField(null=True, blank=True)
    rationale = models.TextField()
    meaning_changed = models.BooleanField(default=False)
    successor_version = models.ForeignKey(
        ProcedureVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidence_change_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evidence_reverification_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "knowledge"
        ordering = ("occurred_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(verification_state__in=sorted(_SHARED_STATES)),
                name="reverification_state_supported",
            ),
            models.CheckConstraint(
                condition=Q(rationale__regex=r".*[^[:space:]].*"),
                name="reverification_rationale_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(reverify_on__isnull=True) | Q(verified_on__lte=models.F("reverify_on")),
                name="reverification_dates_ordered",
            ),
            models.CheckConstraint(
                condition=(
                    Q(meaning_changed=False, successor_version__isnull=True)
                    | Q(meaning_changed=True, successor_version__isnull=False)
                ),
                name="reverification_successor_policy",
            ),
        ]

    def clean(self) -> None:
        _required(self.rationale, "rationale")
        if self.verification_state not in _SHARED_STATES:
            raise ValidationError({"verification_state": "Unsupported shared verification state."})
        if self.reverify_on is not None and self.verified_on > self.reverify_on:
            raise ValidationError({"reverify_on": "Re-verification interval is not ordered."})
        if self.meaning_changed != (self.successor_version_id is not None):
            raise ValidationError(
                {"successor_version": "Meaning changes require a successor Procedure Version."}
            )
        if self.anchor_evidence_link_id is not None:
            _owner_key(self.anchor_evidence_link)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValidationError("Re-verification events are append-only history.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Re-verification events are append-only history.")

    def __str__(self) -> str:
        return f"reverify:{self.pk or 'new'}:{_owner_key(self.anchor_evidence_link)}"


class EvidenceReverificationEvidence(models.Model):
    event = models.ForeignKey(
        EvidenceReverificationEvent,
        on_delete=models.CASCADE,
        related_name="evidence_rows",
    )
    evidence_link = models.ForeignKey(
        EvidenceLink,
        on_delete=models.PROTECT,
        related_name="reverification_rows",
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("event_id", "evidence_link_id")
        constraints = [
            models.UniqueConstraint(
                fields=("event", "evidence_link"),
                name="unique_reverification_evidence_link",
            )
        ]

    def clean(self) -> None:
        if self.event_id and self.evidence_link_id:
            if _owner_key(self.event.anchor_evidence_link) != _owner_key(self.evidence_link):
                raise ValidationError("Reviewed evidence must belong to one affected subject.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValidationError("Re-verification evidence history is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Re-verification evidence history is immutable.")


def open_evidence_discrepancy(
    *,
    anchor_evidence_link: EvidenceLink,
    evidence_links: Iterable[EvidenceLink],
    rationale: str,
    actor: models.Model,
    outcome_state: VerificationState = "disputed",
) -> EvidenceDiscrepancy:
    """Open one internal concern for a single semantic subject and its evidence."""

    _validate_actor(actor)
    if anchor_evidence_link.pk is None:
        raise ValidationError("Anchor Evidence Link must be saved.")
    values = tuple(evidence_links)
    if not values or any(item.pk is None for item in values):
        raise ValidationError("Discrepancy evidence must be saved.")
    by_id = {cast(int, item.pk): item for item in values}
    by_id[cast(int, anchor_evidence_link.pk)] = anchor_evidence_link
    owner_key = _owner_key(anchor_evidence_link)
    if any(_owner_key(item) != owner_key for item in by_id.values()):
        raise ValidationError("Discrepancy evidence must belong to one affected subject.")
    if outcome_state not in _OPEN_OUTCOMES:
        raise ValidationError("Open discrepancies must use an inconclusive shared trust state.")

    with transaction.atomic():
        locked = tuple(
            EvidenceLink.objects.select_for_update().filter(pk__in=sorted(by_id)).order_by("pk")
        )
        if len(locked) != len(by_id):
            raise ValidationError("Discrepancy evidence could not be locked.")
        version_ids = sorted(
            {
                cast(int, version.pk)
                for item in locked
                for version in _owning_versions(item)
                if version.pk is not None
            }
        )
        tuple(
            ProcedureVersion.objects.select_for_update().filter(pk__in=version_ids).order_by("pk")
        )
        discrepancy = EvidenceDiscrepancy(
            anchor_evidence_link=anchor_evidence_link,
            outcome_state=outcome_state,
            rationale=rationale,
            created_by=actor,
        )
        discrepancy.save()
        EvidenceDiscrepancyEvidence.objects.bulk_create(
            EvidenceDiscrepancyEvidence(discrepancy=discrepancy, evidence_link=item)
            for item in locked
        )
    return discrepancy


def resolve_evidence_discrepancy(
    discrepancy_id: int,
    *,
    outcome_state: VerificationState,
    resolution: str = "",
    actor: models.Model,
) -> EvidenceDiscrepancy:
    """Resolve an open discrepancy once, preserving its original research rationale."""

    _validate_actor(actor)
    if outcome_state not in _SHARED_STATES:
        raise ValidationError("Resolution must map to the shared trust vocabulary.")
    with transaction.atomic():
        discrepancy = EvidenceDiscrepancy.objects.select_for_update().get(pk=discrepancy_id)
        if discrepancy.status != EvidenceDiscrepancy.Status.OPEN:
            raise ValidationError("Only open discrepancies can be resolved.")
        discrepancy.status = EvidenceDiscrepancy.Status.RESOLVED
        discrepancy.outcome_state = outcome_state
        discrepancy.resolution = resolution
        discrepancy.resolved_at = timezone.now()
        discrepancy.resolved_by = actor
        discrepancy.save()
    return discrepancy


def record_evidence_reverification(
    *,
    anchor_evidence_link: EvidenceLink,
    reviewed_evidence_links: Iterable[EvidenceLink],
    verification_state: VerificationState,
    verified_on: date,
    reverify_on: date | None,
    rationale: str,
    actor: models.Model,
    meaning_changed: bool = False,
    successor_version: ProcedureVersion | None = None,
) -> EvidenceReverificationEvent:
    """Record trust/freshness history without rewriting an immutable published subject."""

    _validate_actor(actor)
    if anchor_evidence_link.pk is None:
        raise ValidationError("Anchor Evidence Link must be saved.")
    if verification_state not in _SHARED_STATES:
        raise ValidationError("Re-verification must use the shared trust vocabulary.")
    if reverify_on is not None and verified_on > reverify_on:
        raise ValidationError("Re-verification interval is not ordered.")
    if meaning_changed != (successor_version is not None):
        raise ValidationError("Meaning-changing review requires a successor Procedure Version.")

    reviewed = tuple(reviewed_evidence_links)
    reviewed_by_id = {cast(int, item.pk): item for item in reviewed if item.pk is not None}
    owner_key = _owner_key(anchor_evidence_link)
    if any(_owner_key(item) != owner_key for item in reviewed_by_id.values()):
        raise ValidationError("Reviewed evidence must belong to one affected subject.")

    with transaction.atomic():
        expected = _owner_evidence(anchor_evidence_link)
        expected_ids = {cast(int, item.pk) for item in expected if item.pk is not None}
        if (
            set(reviewed_by_id) != expected_ids
            or cast(int, anchor_evidence_link.pk) not in expected_ids
        ):
            raise ValidationError(
                "Re-verification must review the subject's complete evidence set."
            )
        locked = tuple(
            EvidenceLink.objects.select_for_update()
            .filter(pk__in=sorted(expected_ids))
            .order_by("pk")
        )
        versions = _owning_versions(anchor_evidence_link)
        version_ids = sorted(cast(int, item.pk) for item in versions if item.pk is not None)
        locked_versions = tuple(
            ProcedureVersion.objects.select_for_update().filter(pk__in=version_ids).order_by("pk")
        )
        if not locked_versions or all(
            item.state == ProcedureVersion.State.DRAFT for item in locked_versions
        ):
            raise ValidationError(
                "Draft material should be edited directly instead of re-verified."
            )
        if meaning_changed:
            assert successor_version is not None
            successor_version = ProcedureVersion.objects.select_for_update().get(
                pk=successor_version.pk
            )
            procedures = {item.procedure_id for item in locked_versions}
            if len(procedures) != 1:
                raise ValidationError(
                    "Shared material spanning Procedures requires a distinct successor workflow."
                )
            if (
                successor_version.state != ProcedureVersion.State.DRAFT
                or successor_version.pk in version_ids
                or successor_version.procedure_id != next(iter(procedures))
            ):
                raise ValidationError(
                    "Meaning changes require a distinct draft successor for the same Procedure."
                )

        event = EvidenceReverificationEvent(
            anchor_evidence_link=anchor_evidence_link,
            verification_state=verification_state,
            verified_on=verified_on,
            reverify_on=reverify_on,
            rationale=rationale,
            meaning_changed=meaning_changed,
            successor_version=successor_version,
            actor=actor,
        )
        event.save()
        EvidenceReverificationEvidence.objects.bulk_create(
            EvidenceReverificationEvidence(event=event, evidence_link=item) for item in locked
        )
    return event


class EvidenceWorkflowPublicationGate:
    name = "core.evidence_workflow"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        failures: list[PublicationDiagnostic] = []
        rows = tuple(
            EvidenceDiscrepancy.objects.select_for_update()
            .filter(status=EvidenceDiscrepancy.Status.OPEN)
            .select_related("anchor_evidence_link")
            .order_by("pk")
        )
        for row in rows:
            try:
                versions = _owning_versions(row.anchor_evidence_link)
            except ValidationError:
                continue
            if any(version.pk == context.version.pk for version in versions):
                failures.append(
                    PublicationDiagnostic(self.name, "open_evidence_discrepancy", str(row.pk))
                )
        return failures


@dataclass(slots=True)
class _TrustOverlay:
    state: VerificationState | None = None
    owner_verified_on: date | None = None
    reverify_on: date | None = None
    reverify_seen: bool = False
    evidence_state: VerificationState | None = None
    evidence_verified_on: date | None = None
    evidence_reverify_on: date | None = None


def _max_date(left: date | None, right: date | None) -> date | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _workflow_overlays() -> dict[tuple[str, str, str], _TrustOverlay]:
    timeline: list[tuple[datetime, int, int, str, object]] = []
    for row in EvidenceDiscrepancy.objects.select_related("anchor_evidence_link").order_by("pk"):
        occurred = (
            row.resolved_at if row.status == EvidenceDiscrepancy.Status.RESOLVED else row.created_at
        )
        if occurred is not None:
            timeline.append((occurred, 0, cast(int, row.pk), "discrepancy", row))
    for row in (
        EvidenceReverificationEvent.objects.filter(meaning_changed=False)
        .select_related("anchor_evidence_link")
        .order_by("pk")
    ):
        timeline.append((row.occurred_at, 1, cast(int, row.pk), "reverification", row))

    overlays: dict[tuple[str, str, str], _TrustOverlay] = {}
    for occurred, _, _, kind, raw in sorted(timeline, key=lambda item: item[:3]):
        if kind == "discrepancy":
            row = cast(EvidenceDiscrepancy, raw)
            key = _owner_key(row.anchor_evidence_link)
            overlay = overlays.setdefault(key, _TrustOverlay())
            overlay.state = cast(VerificationState, row.outcome_state)
            overlay.owner_verified_on = _max_date(overlay.owner_verified_on, occurred.date())
        else:
            row = cast(EvidenceReverificationEvent, raw)
            key = _owner_key(row.anchor_evidence_link)
            overlay = overlays.setdefault(key, _TrustOverlay())
            established_on = max(row.verified_on, occurred.date())
            overlay.state = cast(VerificationState, row.verification_state)
            overlay.owner_verified_on = established_on
            overlay.reverify_on = row.reverify_on
            overlay.reverify_seen = True
            overlay.evidence_state = cast(VerificationState, row.verification_state)
            overlay.evidence_verified_on = established_on
            overlay.evidence_reverify_on = row.reverify_on
    return overlays


def _overlay_item(item: Any, overlay: _TrustOverlay) -> Any:
    links = item.evidence_links
    if overlay.evidence_state is not None:
        links = tuple(
            replace(
                link,
                verification_state=overlay.evidence_state,
                verified_on=overlay.evidence_verified_on,
                reverify_on=overlay.evidence_reverify_on,
            )
            for link in links
        )
    return replace(
        item,
        verification_state=overlay.state or item.verification_state,
        verified_on=_max_date(item.verified_on, overlay.owner_verified_on),
        reverify_on=overlay.reverify_on if overlay.reverify_seen else item.reverify_on,
        evidence_links=links,
    )


def _apply_workflow_overlays(snapshot: KnowledgeSnapshot) -> KnowledgeSnapshot:
    overlays = _workflow_overlays()
    if not overlays:
        return snapshot

    def version_items(version: Any, attribute: str, kind: str) -> tuple[Any, ...]:
        return tuple(
            _overlay_item(item, overlays[(kind, version.semantic_id, item.semantic_id)])
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
        _overlay_item(item, overlays[("service_point_version", "", item.semantic_id)])
        if ("service_point_version", "", item.semantic_id) in overlays
        else item
        for item in snapshot.service_point_versions
    )
    return replace(
        snapshot,
        procedure_versions=versions,
        service_point_versions=service_point_versions,
    )


_original_materialize = knowledge_domain._materialize_knowledge_snapshot


def _materialize_with_evidence_workflow() -> KnowledgeSnapshot:
    return _apply_workflow_overlays(_original_materialize())


knowledge_domain._materialize_knowledge_snapshot = _materialize_with_evidence_workflow


__all__ = (
    "EvidenceDiscrepancy",
    "EvidenceDiscrepancyEvidence",
    "EvidenceReverificationEvent",
    "EvidenceReverificationEvidence",
    "EvidenceWorkflowPublicationGate",
    "open_evidence_discrepancy",
    "record_evidence_reverification",
    "resolve_evidence_discrepancy",
)
