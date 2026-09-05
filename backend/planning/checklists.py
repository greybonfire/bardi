"""Pure applicability, scope, and shared-trust selection for checklist claims."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from datetime import date

from .catalog import LocalizedText, ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import supporting_sources
from .public import PublicChecklistItem
from .trust import assess_trust


@dataclass(frozen=True, slots=True)
class ChecklistSelection:
    items: tuple[PublicChecklistItem, ...]
    missing_facts: frozenset[str] = frozenset()
    trust_inconclusive: bool = False
    basis_resolution_required: bool = False


def select_checklist_items(
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
    *,
    matched_basis_ids: Set[str] | None = None,
) -> ChecklistSelection:
    matched = None if matched_basis_ids is None else frozenset(matched_basis_ids)
    selected: list[PublicChecklistItem] = []
    consequential_missing: set[str] = set()
    trust_inconclusive = False
    basis_resolution_required = False
    for item in sorted(
        version.checklist_items, key=lambda value: (value.display_order, value.semantic_id)
    ):
        if item.classification not in {"official_requirement", "practical_preparation"}:
            continue
        if item.scope not in {"procedure", "eligibility_basis"}:
            continue
        if item.scope == "eligibility_basis":
            if matched is None:
                basis_resolution_required = True
                continue
            if item.scope_reference not in matched:
                continue
        if item.effective_from is not None and evaluation_date < item.effective_from:
            continue
        if item.effective_to is not None and evaluation_date > item.effective_to:
            continue
        if item.applicability is not None:
            result = evaluate(item.applicability, facts.values, submitted_keys=facts.submitted_keys)
            if result.value is TruthValue.UNKNOWN:
                if item.classification == "official_requirement":
                    consequential_missing.update(result.missing_facts)
                continue
            if result.value is not TruthValue.TRUE:
                continue
        assessment = assess_trust(
            item.verification_state,
            evaluation_date=evaluation_date,
            verified_on=item.verified_on,
            reverify_on=item.reverify_on,
        )
        if assessment.disposition != "assert_current":
            if (
                item.classification == "official_requirement"
                and assessment.disposition == "inconclusive"
            ):
                trust_inconclusive = True
            continue
        sources = supporting_sources(
            item.evidence_links,
            evaluation_date,
            official_only=item.classification == "official_requirement",
        )
        if sources is None:
            if item.classification == "official_requirement":
                trust_inconclusive = True
            continue
        selected.append(
            PublicChecklistItem(
                item.semantic_id,
                item.text,
                item.classification,
                LocalizedLabel.for_classification(item.classification),
                item.quantity,
                item.original_quantity,
                item.copy_quantity,
                item.document_type_id,
                item.scope,
                sources,
                assessment.freshness,
                item.scope_reference if item.scope == "eligibility_basis" else None,
            )
        )
    return ChecklistSelection(
        tuple(selected),
        frozenset(consequential_missing),
        trust_inconclusive,
        basis_resolution_required,
    )


class LocalizedLabel:
    @staticmethod
    def for_classification(classification: str) -> LocalizedText:
        if classification == "official_requirement":
            return LocalizedText("متطلب رسمي", "Official Requirement")
        return LocalizedText("تحضير عملي", "Practical Preparation")
