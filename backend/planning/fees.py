"""Pure deterministic Fee selection without invented current values."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from datetime import date
from typing import cast

from .catalog import ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import claim_sources, supporting_sources
from .public import FeeValueState, PublicFee
from .trust import assess_trust


@dataclass(frozen=True, slots=True)
class FeeSelection:
    items: tuple[PublicFee, ...]
    missing_facts: frozenset[str] = frozenset()
    basis_resolution_required: bool = False


def select_fees(
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
    *,
    matched_basis_ids: Set[str] | None = None,
) -> FeeSelection:
    """Project applicable fees while keeping fee-specific trust uncertainty local.

    Trusted fee rules may be consequential to question selection. An applicable but
    non-current monetary value is still useful as an explicit current-value unknown, but
    its authored amount/range is never exposed as current. Stale/ended values are omitted
    rather than silently relabeled as current or historical.
    """
    matched = None if matched_basis_ids is None else frozenset(matched_basis_ids)
    known_basis_ids = frozenset(item.semantic_id for item in version.eligibility_bases)
    selected: list[PublicFee] = []
    missing: set[str] = set()
    basis_resolution_required = False

    for item in sorted(version.fees, key=lambda row: (row.display_order, row.semantic_id)):
        if item.scope not in {"procedure", "eligibility_basis"}:
            continue
        if (
            item.effective_from is not None
            and evaluation_date < item.effective_from
            or item.effective_to is not None
            and evaluation_date > item.effective_to
        ):
            continue
        if item.scope == "eligibility_basis" and item.eligibility_basis_id not in known_basis_ids:
            basis_resolution_required = True
            continue

        trust = assess_trust(
            item.verification_state,
            evaluation_date=evaluation_date,
            verified_on=item.verified_on,
            reverify_on=item.reverify_on,
            effective_from=item.effective_from,
            effective_to=item.effective_to,
        )
        if trust.disposition == "context_only":
            continue

        if item.scope == "eligibility_basis":
            if matched is None:
                if trust.disposition == "assert_current":
                    basis_resolution_required = True
                continue
            if item.eligibility_basis_id not in matched:
                continue

        applicability = None
        if item.applicability is not None:
            applicability = evaluate(
                item.applicability, facts.values, submitted_keys=facts.submitted_keys
            )
            if applicability.value is TruthValue.FALSE:
                continue
            if applicability.value is TruthValue.UNKNOWN:
                if trust.disposition == "assert_current":
                    missing.update(applicability.missing_facts)
                continue

        authored_state = cast(FeeValueState, item.value_state)
        if trust.disposition == "assert_current":
            if authored_state in {"known", "range"}:
                sources = supporting_sources(item.evidence_links, evaluation_date)
                if sources is None:
                    # Publication/snapshot validation should make this unreachable. Fail
                    # closed here rather than exposing a value without current support.
                    continue
            else:
                sources = claim_sources(item.evidence_links)
            public_state = authored_state
            amount = item.amount
            minimum_amount = item.minimum_amount
            maximum_amount = item.maximum_amount
            current_value_unknown = authored_state == "unknown"
        else:
            sources = claim_sources(item.evidence_links)
            public_state = "unknown" if authored_state == "unknown" else "unverified"
            amount = None
            minimum_amount = None
            maximum_amount = None
            current_value_unknown = True

        selected.append(
            PublicFee(
                item.semantic_id,
                item.text,
                public_state,
                amount,
                minimum_amount,
                maximum_amount,
                item.currency,
                item.fee_type,
                current_value_unknown,
                sources,
                trust.freshness,
            )
        )

    return FeeSelection(tuple(selected), frozenset(missing), basis_resolution_required)
