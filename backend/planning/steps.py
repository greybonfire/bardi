"""Pure deterministic Step selection."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from datetime import date

from .catalog import ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import supporting_sources
from .public import PublicStep
from .trust import assess_trust


@dataclass(frozen=True, slots=True)
class StepSelection:
    items: tuple[PublicStep, ...]
    missing_facts: frozenset[str] = frozenset()
    trust_inconclusive: bool = False
    basis_resolution_required: bool = False


def select_steps(
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
    *,
    matched_basis_ids: Set[str] | None = None,
) -> StepSelection:
    matched = None if matched_basis_ids is None else frozenset(matched_basis_ids)
    selected: list[PublicStep] = []
    consequential_missing: set[str] = set()
    trust_inconclusive = False
    basis_resolution_required = False
    for item in sorted(version.steps, key=lambda row: (row.phase_order, row.slot, row.semantic_id)):
        if item.scope not in {"procedure", "eligibility_basis"}:
            continue
        if (
            item.effective_from is not None
            and evaluation_date < item.effective_from
            or item.effective_to is not None
            and evaluation_date > item.effective_to
        ):
            continue
        if item.scope == "eligibility_basis":
            if matched is None:
                basis_resolution_required = True
                continue
            if item.eligibility_basis_id not in matched:
                continue
        if item.applicability is not None:
            applicability = evaluate(
                item.applicability, facts.values, submitted_keys=facts.submitted_keys
            )
            if applicability.value is TruthValue.UNKNOWN:
                consequential_missing.update(applicability.missing_facts)
                continue
            if applicability.value is not TruthValue.TRUE:
                continue
        trust = assess_trust(
            item.verification_state,
            evaluation_date=evaluation_date,
            verified_on=item.verified_on,
            reverify_on=item.reverify_on,
        )
        if trust.disposition != "assert_current":
            trust_inconclusive = True
            continue
        sources = supporting_sources(item.evidence_links, evaluation_date)
        if sources is None:
            trust_inconclusive = True
            continue
        selected.append(
            PublicStep(
                item.semantic_id,
                item.text,
                item.phase,
                sources,
                trust.freshness,
                item.scope,
                item.eligibility_basis_id,
            )
        )
    return StepSelection(
        tuple(selected),
        frozenset(consequential_missing),
        trust_inconclusive,
        basis_resolution_required,
    )
