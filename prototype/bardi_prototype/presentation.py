from __future__ import annotations

from .contracts import (
    EvidenceSummary,
    Freshness,
    Locale,
    PersonalizedPlan,
    RenderedChecklistGroup,
    RenderedChecklistItem,
    RenderedFee,
    RenderedServicePoint,
    RenderedStep,
    RenderedWarning,
)
from .planner import SemanticPlan


CLASSIFICATION_LABELS = {
    "official_requirement": {"ar": "متطلب رسمي", "en": "Official requirement"},
    "practical_preparation": {"ar": "استعداد عملي", "en": "Practical preparation"},
}


def _source_summaries(plan: SemanticPlan, evidence_link_ids: tuple[str, ...]) -> tuple[EvidenceSummary, ...]:
    source_ids: list[str] = []
    for evidence_link_id in evidence_link_ids:
        link = plan.knowledge.evidence_links[evidence_link_id]
        for source_id in link.source_ids:
            if source_id not in source_ids:
                source_ids.append(source_id)
    return tuple(
        EvidenceSummary(
            source_id=source_id,
            authority=plan.knowledge.sources[source_id].authority,
            title=plan.knowledge.sources[source_id].title,
            verified_on=plan.knowledge.sources[source_id].retrieved_on,
        )
        for source_id in source_ids
    )


def _classification_label(classification: str, locale: Locale) -> str:
    labels = CLASSIFICATION_LABELS.get(classification)
    return labels[locale] if labels else classification


def _group_checklist(items: tuple[RenderedChecklistItem, ...]) -> tuple[RenderedChecklistGroup, ...]:
    order: list[str] = []
    grouped: dict[str, list[RenderedChecklistItem]] = {}
    document_ids: dict[str, str | None] = {}
    for item in items:
        group_id = item.document_type_id or f"claim:{item.id}"
        if group_id not in grouped:
            grouped[group_id] = []
            order.append(group_id)
            document_ids[group_id] = item.document_type_id
        grouped[group_id].append(item)
    return tuple(
        RenderedChecklistGroup(
            id=group_id,
            document_type_id=document_ids[group_id],
            items=tuple(grouped[group_id]),
        )
        for group_id in order
    )


def project_plan(plan: SemanticPlan, locale: Locale) -> PersonalizedPlan:
    knowledge = plan.knowledge
    checklist = tuple(
        RenderedChecklistItem(
            id=item.id,
            text=item.text.render(locale),
            classification=item.classification,
            classification_label=_classification_label(item.classification, locale),
            quantity=item.quantity,
            original_quantity=item.original_quantity,
            copy_quantity=item.copy_quantity,
            document_type_id=item.document_type_id,
            scope=item.scope,
            eligibility_basis_id=item.eligibility_basis_id,
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.claims
    )
    steps = tuple(
        RenderedStep(
            id=item.id,
            text=item.text.render(locale),
            phase=item.phase,
            phase_order=item.phase_order,
            slot=item.slot,
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.steps
    )
    fees = tuple(
        RenderedFee(
            id=item.id,
            text=item.text.render(locale),
            value_state=item.value_state,
            amount=item.amount,
            minimum_amount=item.minimum_amount,
            maximum_amount=item.maximum_amount,
            currency=item.currency,
            fee_type=item.fee_type,
            verification_state=item.verification_state,
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.fees
    )
    service_points = tuple(
        RenderedServicePoint(
            id=item.id,
            text=item.text.render(locale),
            address=item.address.render(locale),
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.service_points
    )
    warnings = tuple(
        RenderedWarning(
            id=item.id,
            text=item.text.render(locale),
            severity=item.severity,
            kind=item.kind,
            role=item.role,
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.warnings
    )
    regeneration_warning = next(warning for warning in warnings if warning.role == "regeneration")
    return PersonalizedPlan(
        goal_id=knowledge.goal.id,
        goal=knowledge.goal.text.render(locale),
        procedure_id=knowledge.procedure.procedure_id,
        procedure=knowledge.procedure.text.render(locale),
        procedure_version_id=knowledge.procedure.version_id,
        locale=locale,
        checklist=checklist,
        checklist_groups=_group_checklist(checklist),
        steps=steps,
        fees=fees,
        service_points=service_points,
        warnings=warnings,
        regeneration_warning=regeneration_warning,
        unknowns=tuple(item.text.render(locale) for item in plan.unknowns),
        freshness=Freshness(
            procedure_version_id=knowledge.procedure.version_id,
            last_verified_on=knowledge.procedure.verified_on,
            evaluation_date=plan.evaluation_date,
            generated_on=plan.generated_on,
        ),
    )
