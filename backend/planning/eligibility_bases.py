"""Reachability-first Eligibility Basis evaluation for the pure planning domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .catalog import EligibilityBasisSnapshot, ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import claim_sources, supporting_sources
from .public import PublicEligibilityBasis
from .trust import assess_trust


@dataclass(frozen=True, slots=True)
class EligibilityBasisSelection:
    """Exhaustive Basis outcome without ranking or hidden recommendation."""

    bases: tuple[PublicEligibilityBasis, ...]
    trusted_matched_basis_ids: frozenset[str]
    missing_facts: frozenset[str] = frozenset()
    inconclusive_basis_ids: tuple[str, ...] = ()
    no_applicable_basis: bool = False
    configuration_invalid: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "bases", tuple(self.bases))
        object.__setattr__(
            self, "trusted_matched_basis_ids", frozenset(self.trusted_matched_basis_ids)
        )
        object.__setattr__(self, "missing_facts", frozenset(self.missing_facts))
        object.__setattr__(self, "inconclusive_basis_ids", tuple(self.inconclusive_basis_ids))


def _inside_effective_interval(basis: EligibilityBasisSnapshot, evaluation_date: date) -> bool:
    return not (
        basis.effective_from is not None
        and evaluation_date < basis.effective_from
        or basis.effective_to is not None
        and evaluation_date > basis.effective_to
    )


def select_eligibility_bases(
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
) -> EligibilityBasisSelection:
    """Evaluate every Basis reachability gate before its qualification rule.

    A FALSE gate never evaluates qualification. An UNKNOWN gate contributes only its own
    consequential missing Facts. Qualification is evaluated only after reachability is TRUE.
    Matched Bases are retained as non-ranked alternatives even when their trust is
    inconclusive, but only currently trusted matches are returned as guidance-unlocking IDs.
    """

    selected: list[PublicEligibilityBasis] = []
    trusted: set[str] = set()
    missing: set[str] = set()
    inconclusive: set[str] = set()
    configuration_invalid = False

    authored = tuple(
        sorted(version.eligibility_bases, key=lambda item: (item.display_order, item.semantic_id))
    )
    for basis in authored:
        if not _inside_effective_interval(basis, evaluation_date):
            continue
        if basis.qualification is None:
            configuration_invalid = True
            continue

        trust = assess_trust(
            basis.verification_state,
            evaluation_date=evaluation_date,
            verified_on=basis.verified_on,
            reverify_on=basis.reverify_on,
            effective_from=basis.effective_from,
            effective_to=basis.effective_to,
        )
        reachability = (
            None
            if basis.reachability is None
            else evaluate(
                basis.reachability,
                facts.values,
                submitted_keys=facts.submitted_keys,
            )
        )
        if reachability is not None:
            if reachability.value is TruthValue.FALSE:
                continue
            if reachability.value is TruthValue.UNKNOWN:
                if trust.freshness.state in {"stale", "disputed", "unknown"}:
                    inconclusive.add(basis.semantic_id)
                else:
                    missing.update(reachability.missing_facts)
                continue

        qualification = evaluate(
            basis.qualification,
            facts.values,
            submitted_keys=facts.submitted_keys,
        )
        if qualification.value is TruthValue.FALSE:
            continue
        if qualification.value is TruthValue.UNKNOWN:
            if trust.freshness.state in {"stale", "disputed", "unknown"}:
                inconclusive.add(basis.semantic_id)
            else:
                missing.update(qualification.missing_facts)
            continue

        if trust.disposition == "assert_current":
            sources = supporting_sources(basis.evidence_links, evaluation_date)
            if sources is None:
                configuration_invalid = True
                continue
            trusted.add(basis.semantic_id)
        else:
            sources = claim_sources(basis.evidence_links)
            inconclusive.add(basis.semantic_id)

        selected.append(
            PublicEligibilityBasis(
                basis.semantic_id,
                basis.text,
                sources,
                trust.freshness,
            )
        )

    return EligibilityBasisSelection(
        tuple(selected),
        frozenset(trusted),
        frozenset(missing),
        tuple(sorted(inconclusive)),
        bool(authored) and not selected and not inconclusive and not missing,
        configuration_invalid,
    )
