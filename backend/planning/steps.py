"""Pure deterministic Step selection."""

from __future__ import annotations

from collections.abc import Set
from datetime import date

from .catalog import ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import supporting_sources
from .public import PublicStep
from .trust import assess_trust


def select_steps(
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
    *,
    matched_basis_ids: Set[str] | None = None,
) -> tuple[PublicStep, ...]:
    matched = frozenset() if matched_basis_ids is None else frozenset(matched_basis_ids)
    result: list[PublicStep] = []
    for item in sorted(version.steps, key=lambda row: (row.phase_order, row.slot, row.semantic_id)):
        if item.scope == "eligibility_basis" and item.eligibility_basis_id not in matched:
            continue
        if item.scope not in {"procedure", "eligibility_basis"}:
            continue
        if (
            item.effective_from
            and evaluation_date < item.effective_from
            or item.effective_to
            and evaluation_date > item.effective_to
        ):
            continue
        if (
            item.applicability is not None
            and evaluate(
                item.applicability, facts.values, submitted_keys=facts.submitted_keys
            ).value
            is not TruthValue.TRUE
        ):
            continue
        trust = assess_trust(
            item.verification_state,
            evaluation_date=evaluation_date,
            verified_on=item.verified_on,
            reverify_on=item.reverify_on,
        )
        if trust.disposition != "assert_current":
            continue
        sources = supporting_sources(item.evidence_links, evaluation_date)
        if sources is None:
            continue
        result.append(PublicStep(item.semantic_id, item.text, item.phase, sources, trust.freshness))
    return tuple(result)
