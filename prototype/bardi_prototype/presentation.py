from __future__ import annotations

from .contracts import (
    EvidenceSummary,
    Freshness,
    Locale,
    PersonalizedPlan,
    RenderedChecklistItem,
    RenderedFee,
    RenderedServicePoint,
    RenderedStep,
    RenderedWarning,
)
from .planner import SemanticPlan


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


def project_plan(plan: SemanticPlan, locale: Locale) -> PersonalizedPlan:
    knowledge = plan.knowledge
    checklist = tuple(
        RenderedChecklistItem(
            id=item.id,
            text=item.text.render(locale),
            classification=item.classification,
            quantity=item.quantity,
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.claims
    )
    steps = tuple(
        RenderedStep(
            id=item.id,
            text=item.text.render(locale),
            phase=item.phase,
            slot=item.slot,
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.steps
    )
    fees = tuple(
        RenderedFee(
            id=item.id,
            text=item.text.render(locale),
            amount=item.amount,
            currency=item.currency,
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
            sources=_source_summaries(plan, item.evidence_link_ids),
        )
        for item in plan.warnings
    )
    return PersonalizedPlan(
        goal_id=knowledge.goal.id,
        goal=knowledge.goal.text.render(locale),
        procedure_id=knowledge.procedure.procedure_id,
        procedure=knowledge.procedure.text.render(locale),
        procedure_version_id=knowledge.procedure.version_id,
        locale=locale,
        checklist=checklist,
        steps=steps,
        fees=fees,
        service_points=service_points,
        warnings=warnings,
        unknowns=tuple(item.text.render(locale) for item in plan.unknowns),
        freshness=Freshness(
            procedure_version_id=knowledge.procedure.version_id,
            verified_on=knowledge.procedure.verified_on,
            evaluation_date=plan.evaluation_date,
            generated_on=plan.evaluation_date,
        ),
    )
