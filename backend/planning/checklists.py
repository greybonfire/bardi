"""Pure applicability, scope, and shared-trust selection for checklist claims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .catalog import LocalizedText, ProcedureVersionSnapshot, SourceSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .public import PublicChecklistItem, PublicSource
from .trust import assess_trust


@dataclass(frozen=True, slots=True)
class ChecklistSelection:
    items: tuple[PublicChecklistItem, ...]
    missing_facts: frozenset[str] = frozenset()
    trust_inconclusive: bool = False


def select_checklist_items(
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
) -> ChecklistSelection:
    selected: list[PublicChecklistItem] = []
    consequential_missing: set[str] = set()
    trust_inconclusive = False
    for item in sorted(
        version.checklist_items, key=lambda value: (value.display_order, value.semantic_id)
    ):
        if item.classification not in {"official_requirement", "practical_preparation"}:
            continue
        if item.scope != "procedure":
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
        sources: dict[str, PublicSource] = {}
        has_current_contradiction = False
        for link in item.evidence_links:
            link_assessment = assess_trust(
                link.verification_state,
                evaluation_date=evaluation_date,
                effective_from=link.effective_from,
                effective_to=link.effective_to,
                retrieved_on=link.retrieved_on,
                verified_on=link.verified_on,
                reverify_on=link.reverify_on,
            )
            if link_assessment.disposition != "assert_current":
                continue
            if not link.sources or not all(
                _source_is_current(source, evaluation_date) for source in link.sources
            ):
                continue
            if link.support_status == "contradicts":
                has_current_contradiction = True
                continue
            if link.support_status != "supports":
                continue
            if item.classification == "official_requirement" and not all(
                source.classification == "official" for source in link.sources
            ):
                continue
            for source in link.sources:
                sources.setdefault(
                    source.semantic_id,
                    PublicSource(
                        source.semantic_id,
                        source.authority.semantic_id,
                        source.title,
                        source.locator,
                        source.classification,
                        source.retrieved_on,
                    ),
                )
        if has_current_contradiction:
            if item.classification == "official_requirement":
                trust_inconclusive = True
            continue
        if not sources:
            if item.classification == "official_requirement":
                trust_inconclusive = True
            continue
        if item.classification == "official_requirement" and not any(
            source.classification == "official" for source in sources.values()
        ):
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
                tuple(sources.values()),
                assessment.freshness,
            )
        )
    return ChecklistSelection(tuple(selected), frozenset(consequential_missing), trust_inconclusive)


def _source_is_current(source: SourceSnapshot, evaluation_date: date) -> bool:
    return (
        assess_trust(
            "current",
            evaluation_date=evaluation_date,
            effective_from=source.effective_from,
            effective_to=source.effective_to,
            retrieved_on=source.retrieved_on,
            reverify_on=source.reverify_on,
        ).disposition
        == "assert_current"
    )


class LocalizedLabel:
    @staticmethod
    def for_classification(classification: str) -> LocalizedText:

        if classification == "official_requirement":
            return LocalizedText("متطلب رسمي", "Official Requirement")
        return LocalizedText("تحضير عملي", "Practical Preparation")
