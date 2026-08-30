"""Centralized evidence and local trust assessment.

Rule evaluation remains a pure TRUE/FALSE/UNKNOWN operation. This module
answers a different question: whether a material definition may be presented
as current guidance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .contracts import EvidenceDiscrepancy, KnowledgeBundle, VerificationState


@dataclass(frozen=True)
class TrustAssessment:
    """Calculated trust summary; publication state is deliberately separate."""

    state: VerificationState
    needs_reverification_ids: tuple[str, ...] = ()
    disputed_ids: tuple[str, ...] = ()


_UNTRUSTED = {"needs_reverification", "stale", "disputed", "unknown"}


def verification_date(item: Any, bundle: KnowledgeBundle | None = None) -> date | None:
    """Return only an item-level verification date.

    A Procedure Version verification date must never be used as evidence that a
    particular claim/step/fee was itself previously verified. ``bundle`` is
    retained as an ignored compatibility argument for existing callers.
    """
    del bundle
    return getattr(item, "reverified_on", None) or getattr(item, "verified_on", None)


def _date_is_current(
    value: date | None,
    start: date | None,
    end: date | None,
) -> bool:
    return (start is None or value is None or value >= start) and (
        end is None or value is None or value <= end
    )


def evidence_trust_state(
    bundle: KnowledgeBundle,
    evidence_link_ids: tuple[str, ...],
    evaluation_date: date | None = None,
) -> VerificationState:
    """Calculate the weakest state of evidence links and their source windows."""
    states: list[str] = []
    for link_id in evidence_link_ids:
        link = bundle.evidence_links.get(link_id)
        if link is None:
            states.append("unknown")
            continue
        if not link.supports_claim:
            states.append("disputed")
            continue
        if evaluation_date is not None and (
            not _date_is_current(
                evaluation_date, link.effective_from, link.effective_to
            )
            or (
                link.retrieved_on is not None
                and link.retrieved_on > evaluation_date
            )
        ):
            states.append("needs_reverification")
            continue
        source_states: list[str] = []
        for source_id in link.source_ids:
            source = bundle.sources.get(source_id)
            if source is None:
                source_states.append("unknown")
            elif evaluation_date is not None and (
                not _date_is_current(
                    evaluation_date, source.effective_from, source.effective_to
                )
                or (
                    source.retrieved_on is not None
                    and source.retrieved_on > evaluation_date
                )
                or (
                    source.reverification_due_on is not None
                    and evaluation_date > source.reverification_due_on
                )
            ):
                source_states.append("needs_reverification")
            else:
                source_states.append("current")
        if link.verification_state in _UNTRUSTED:
            states.append(link.verification_state)
        elif (
            evaluation_date is not None
            and link.reverification_due_on is not None
            and evaluation_date > link.reverification_due_on
        ):
            states.append("needs_reverification")
        elif not source_states or "disputed" in source_states:
            states.append("disputed")
        elif "needs_reverification" in source_states:
            states.append("needs_reverification")
        elif "unknown" in source_states:
            states.append("unknown")
        else:
            states.append("current")
    if not states:
        return "current"
    if "disputed" in states:
        return "disputed"
    if "needs_reverification" in states or "stale" in states:
        return "needs_reverification"
    if "unknown" in states:
        return "unknown"
    return "current"


def discrepancy_for_claims(
    bundle: KnowledgeBundle,
    claim_ids: set[str],
) -> tuple[EvidenceDiscrepancy, ...]:
    return tuple(
        discrepancy
        for discrepancy in bundle.discrepancies
        if discrepancy.claim_id in claim_ids
        and discrepancy.status not in {"resolved", "resolved_for_current_version"}
    )


def _trust_state(
    bundle: KnowledgeBundle,
    item: Any,
    evaluation_date: date | None,
    seen: frozenset[str],
) -> VerificationState:
    item_id = getattr(item, "id", "")
    if item_id in seen:
        return "disputed"
    explicit = getattr(
        item,
        "verification_state",
        getattr(item, "trust_state", "current"),
    )
    if explicit == "disputed":
        return "disputed"
    if explicit in {"needs_reverification", "stale", "unknown"}:
        return explicit
    if (
        evaluation_date is not None
        and getattr(item, "reverification_due_on", None) is not None
        and evaluation_date > item.reverification_due_on
    ):
        return "needs_reverification"
    evidence_ids = tuple(getattr(item, "evidence_link_ids", ()))
    requires_official_source = (
        getattr(item, "classification", None) == "official_requirement"
        or hasattr(item, "amount")
    )

    # Assess every link before applying source-authority rules. A non-official
    # link that challenges an official link is still a material conflict and
    # must not disappear merely because an official link is also present.
    evidence = evidence_trust_state(bundle, evidence_ids, evaluation_date)
    if evidence != "current":
        return evidence

    # A requirement or fee is authoritative only when at least one complete
    # Evidence Link is made entirely of official sources. A mixed link (for
    # example, official Gazette metadata plus a secondary text mirror) cannot
    # promote the secondary text to official evidence.
    if requires_official_source:
        has_authoritative_link = any(
            link_id in bundle.evidence_links
            and bool(bundle.evidence_links[link_id].source_ids)
            and all(
                source_id in bundle.sources
                and bundle.sources[source_id].classification == "official"
                for source_id in bundle.evidence_links[link_id].source_ids
            )
            for link_id in evidence_ids
        )
        if not has_authoritative_link:
            return "needs_reverification"

    dependencies = set(getattr(item, "claim_dependencies", ()))
    if dependencies:
        claim_by_id = {claim.id: claim for claim in bundle.claims}
        dependency_states = {
            _trust_state(
                bundle,
                claim_by_id[dependency_id],
                evaluation_date,
                seen | {item_id},
            )
            for dependency_id in dependencies
            if dependency_id in claim_by_id
        }
        if "disputed" in dependency_states:
            return "disputed"
        if any(
            state in {"needs_reverification", "stale"}
            for state in dependency_states
        ):
            return "needs_reverification"
        if "unknown" in dependency_states:
            return "unknown"

    discrepancies = discrepancy_for_claims(bundle, {item_id})
    if discrepancies:
        consequences = {discrepancy.consequence for discrepancy in discrepancies}
        if "disputed" in consequences:
            return "disputed"
        if "needs_reverification" in consequences:
            return "needs_reverification"
    return "current"


def trust_state(
    bundle: KnowledgeBundle,
    item: Any,
    evaluation_date: date | None = None,
) -> VerificationState:
    return _trust_state(bundle, item, evaluation_date, frozenset())


def is_currently_trusted(
    bundle: KnowledgeBundle,
    item: Any,
    evaluation_date: date | None = None,
) -> bool:
    return trust_state(bundle, item, evaluation_date) == "current"


def is_historical_context_candidate(
    bundle: KnowledgeBundle,
    item: Any,
    evaluation_date: date,
) -> bool:
    """Return whether an item represents an established past value.

    ``needs_reverification``, ``disputed`` and ``unknown`` are current trust
    problems, not proof of a historical value. Historical context is reserved
    for explicitly stale material or a previously verified item whose authored
    effective interval has ended.
    """
    explicit = getattr(
        item,
        "verification_state",
        getattr(item, "trust_state", "current"),
    )
    if explicit == "stale":
        return verification_date(item) is not None or getattr(item, "effective_to", None) is not None
    if explicit != "current":
        return False
    effective_to = getattr(item, "effective_to", None)
    if type(effective_to) is date and evaluation_date > effective_to:
        return verification_date(item) is not None or effective_to is not None
    return False


def assess_bundle(
    bundle: KnowledgeBundle,
    evaluation_date: date | None = None,
) -> TrustAssessment:
    items = (
        *bundle.claims,
        *bundle.steps,
        *bundle.fees,
        *bundle.eligibility_bases,
        *bundle.dependencies,
        *bundle.warnings,
        *bundle.service_point_versions,
        *bundle.service_point_associations,
    )
    states: dict[str, VerificationState] = {}
    for item in items:
        state = trust_state(bundle, item, evaluation_date)
        if (
            state == "current"
            and evaluation_date is not None
            and getattr(item, "effective_to", None) is not None
            and evaluation_date > item.effective_to
        ):
            state = "stale"
        states[item.id] = state
    states[f"procedure_version:{bundle.procedure.version_id}"] = trust_state(
        bundle, bundle.procedure, evaluation_date
    )
    needs = tuple(
        sorted(
            item_id
            for item_id, state in states.items()
            if state in {"needs_reverification", "stale"}
        )
    )
    disputed = tuple(
        sorted(item_id for item_id, state in states.items() if state == "disputed")
    )
    if disputed:
        state: VerificationState = "disputed"
    elif needs:
        state = "needs_reverification"
    elif any(value == "unknown" for value in states.values()):
        state = "unknown"
    else:
        state = "current"
    return TrustAssessment(state, needs, disputed)


def is_untrusted_state(state: str) -> bool:
    return state in _UNTRUSTED
