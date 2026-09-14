"""Pure trust projection over detached knowledge and already ordered, selected history."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from planning.catalog import KnowledgeSnapshot
from planning.trust import VerificationState

OwnerKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class DiscrepancyTransition:
    owner: OwnerKey
    occurred_at: datetime
    discrepancy_id: int
    event_type: str
    verification_state: VerificationState


@dataclass(frozen=True, slots=True)
class Reverification:
    owner: OwnerKey
    occurred_at: datetime
    verification_state: VerificationState
    verified_on: date
    reverify_on: date | None


_OPEN_DISCREPANCY_PRECEDENCE: tuple[VerificationState, ...] = (
    "disputed",
    "needs_reverification",
    "unknown",
)


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


def project_evidence_trust(
    snapshot: KnowledgeSnapshot,
    ordered_history: Iterable[DiscrepancyTransition | Reverification],
) -> KnowledgeSnapshot:
    """Project trust without changing authored semantics or consulting persistence.

    History must already be selected for the evaluation date and scope, ordered by
    timestamp, discrepancy-before-review, and within-kind primary key. The adapter
    owns that selection, including PostgreSQL's timezone-aware calendar cutoff.
    Consume records once, incrementally: iterator failures propagate at the current
    replay position. Do not pre-consume history or discard owners absent from the
    snapshot. Empty history returns the original snapshot; inputs are never mutated.
    """
    overlays: dict[tuple[str, str, str], _TrustOverlay] = {}
    open_discrepancies: dict[tuple[str, str, str], dict[int, VerificationState]] = {}
    for event in ordered_history:
        occurred = event.occurred_at
        if isinstance(event, DiscrepancyTransition):
            transition = event
            key = transition.owner
            state = transition.verification_state
            if transition.event_type == "opened":
                open_discrepancies.setdefault(key, {})[transition.discrepancy_id] = state
            elif transition.event_type == "resolved":
                owner_open_discrepancies = open_discrepancies.get(key)
                if owner_open_discrepancies is not None:
                    owner_open_discrepancies.pop(transition.discrepancy_id, None)
                    if not owner_open_discrepancies:
                        del open_discrepancies[key]

            overlay = overlays.setdefault(key, _TrustOverlay())
            overlay.state = state
            overlay.owner_verified_on = _max_date(overlay.owner_verified_on, occurred.date())
            continue

        review = event
        key = review.owner
        overlay = overlays.setdefault(key, _TrustOverlay())
        established_on = max(review.verified_on, occurred.date())
        overlay.state = review.verification_state
        overlay.owner_verified_on = established_on
        overlay.reverify_on = review.reverify_on
        overlay.reverify_seen = True
        overlay.evidence_state = review.verification_state
        overlay.evidence_verified_on = established_on
        overlay.evidence_reverify_on = review.reverify_on

    for key, owner_open_discrepancies in open_discrepancies.items():
        open_states = set(owner_open_discrepancies.values())
        overlays[key].state = next(
            state for state in _OPEN_DISCREPANCY_PRECEDENCE if state in open_states
        )
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
