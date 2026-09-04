"""Shared, pure trust and freshness semantics for evidence-bearing material."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

VerificationState = Literal["current", "needs_reverification", "stale", "disputed", "unknown"]
TrustDisposition = Literal["assert_current", "context_only", "inconclusive"]

VERIFICATION_CHOICES = (
    ("current", "Current"),
    ("needs_reverification", "Needs reverification"),
    ("stale", "Stale"),
    ("disputed", "Disputed"),
    ("unknown", "Unknown"),
)


@dataclass(frozen=True, slots=True)
class Freshness:
    state: VerificationState
    verified_on: date | None = None
    reverify_on: date | None = None


@dataclass(frozen=True, slots=True)
class TrustAssessment:
    """Planner-facing decision for one item without feature-specific policy."""

    disposition: TrustDisposition
    freshness: Freshness


def assess_trust(
    state: VerificationState,
    *,
    evaluation_date: date,
    verified_on: date | None = None,
    reverify_on: date | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    retrieved_on: date | None = None,
) -> TrustAssessment:
    """Assess trust at an explicit date without consulting the system clock.

    Current material can be asserted only inside its effective interval, before its
    re-verification deadline, and after any verification/retrieval dates. Expired material
    is eligible as dated historical context only when an explicit verification date and
    effective end establish it no later than the period it describes. Explicitly stale,
    previously verified material may also be retained as dated context. Needs-reverification,
    disputed, and unknown states remain inconclusive and are never silently relabeled.
    """
    freshness = Freshness(state, verified_on, reverify_on)
    if (verified_on is not None and verified_on > evaluation_date) or (
        retrieved_on is not None and retrieved_on > evaluation_date
    ):
        return TrustAssessment("inconclusive", Freshness("unknown", verified_on, reverify_on))
    if state == "stale":
        established_past_value = verified_on is not None and (
            effective_from is None or effective_from <= evaluation_date
        )
        return TrustAssessment(
            "context_only" if established_past_value else "inconclusive", freshness
        )
    if state != "current":
        return TrustAssessment("inconclusive", freshness)
    if effective_from is not None and evaluation_date < effective_from:
        return TrustAssessment(
            "inconclusive", Freshness("needs_reverification", verified_on, reverify_on)
        )
    if effective_to is not None and evaluation_date > effective_to:
        established_for_period = (
            verified_on is not None
            and verified_on <= effective_to
            and (retrieved_on is None or retrieved_on <= effective_to)
        )
        if established_for_period:
            return TrustAssessment("context_only", freshness)
        return TrustAssessment(
            "inconclusive", Freshness("needs_reverification", verified_on, reverify_on)
        )
    if reverify_on is not None and reverify_on < evaluation_date:
        return TrustAssessment(
            "inconclusive", Freshness("needs_reverification", verified_on, reverify_on)
        )
    return TrustAssessment("assert_current", freshness)
