from __future__ import annotations

from .contracts import (
    EvidenceSummary,
    Freshness,
    Locale,
    PersonalizedPlan,
    RenderedChecklistGroup,
    RenderedChecklistItem,
    RenderedDependency,
    RenderedEligibilityBasis,
    RenderedFee,
    RenderedRouting,
    RenderedServicePoint,
    RenderedStep,
    RenderedVerificationPath,
    RenderedWarning,
    VerificationPathDefinition,
)
from .planner import SemanticPlan, SemanticServicePoint


CLASSIFICATION_LABELS = {
    "official_requirement": {"ar": "متطلب رسمي", "en": "Official requirement"},
    "practical_preparation": {"ar": "استعداد عملي", "en": "Practical preparation"},
}


def _source_summaries(
    plan: SemanticPlan,
    evidence_link_ids: tuple[str, ...],
) -> tuple[EvidenceSummary, ...]:
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


def _group_checklist(
    items: tuple[RenderedChecklistItem, ...],
) -> tuple[RenderedChecklistGroup, ...]:
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


def _verification_path(
    plan: SemanticPlan,
    definition: VerificationPathDefinition | None,
    locale: Locale,
) -> RenderedVerificationPath | None:
    if definition is None:
        return None
    return RenderedVerificationPath(
        id=definition.id,
        text=definition.text.render(locale),
        sources=_source_summaries(plan, definition.evidence_link_ids),
    )


def _required_verification_path(
    plan: SemanticPlan,
    definition: VerificationPathDefinition,
    locale: Locale,
) -> RenderedVerificationPath:
    rendered = _verification_path(plan, definition, locale)
    assert rendered is not None
    return rendered


def _service_point(
    plan: SemanticPlan,
    item: SemanticServicePoint,
    locale: Locale,
) -> RenderedServicePoint:
    evidence_ids = tuple(
        dict.fromkeys(
            item.version.evidence_link_ids + item.association.evidence_link_ids
        )
    )
    return RenderedServicePoint(
        id=item.point.id,
        version_id=item.version.id,
        association_id=item.association.id,
        text=item.point.text.render(locale),
        address=item.version.address.render(locale),
        availability=item.version.availability,
        effective_from=item.version.effective_from,
        effective_to=item.version.effective_to,
        sources=_source_summaries(plan, evidence_ids),
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
            scope=item.scope,
            eligibility_basis_id=item.eligibility_basis_id,
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
        _service_point(plan, item, locale)
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
    regeneration_warning = next(
        warning for warning in warnings if warning.role == "regeneration"
    )

    eligibility_bases = tuple(
        RenderedEligibilityBasis(
            id=basis.id,
            text=basis.text.render(locale),
            verification_state=basis.verification_state,
            checklist_item_ids=tuple(
                item.id
                for item in checklist
                if item.eligibility_basis_id == basis.id
            ),
            step_ids=tuple(
                item.id
                for item in steps
                if item.eligibility_basis_id == basis.id
            ),
            sources=_source_summaries(plan, basis.evidence_link_ids),
        )
        for basis in plan.eligibility_bases
    )

    dependencies = tuple(
        RenderedDependency(
            id=item.definition.id,
            text=item.definition.text.render(locale),
            relation=item.definition.relation,
            status=item.status,
            target_procedure_id=item.definition.target_procedure_id,
            target_procedure=(
                item.target_knowledge.procedure.text.render(locale)
                if item.target_knowledge is not None
                else item.definition.text.render(locale)
            ),
            target_procedure_version_id=(
                item.target_knowledge.procedure.version_id
                if item.target_knowledge is not None
                else None
            ),
            sources=_source_summaries(
                plan,
                item.definition.evidence_link_ids,
            ),
            verification_path=_required_verification_path(
                plan,
                item.definition.verification_path,
                locale,
            ),
        )
        for item in plan.dependencies
    )

    routing_path = _verification_path(
        plan,
        plan.routing.verification_path,
        locale,
    )
    routing = RenderedRouting(
        status=plan.routing.status,
        service_points=service_points,
        unresolved_association_ids=plan.routing.unresolved_association_ids,
        unresolved_fact_keys=plan.routing.unresolved_fact_keys,
        verification_path=routing_path,
    )

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
        eligibility_bases=eligibility_bases,
        basis_verification_path=_verification_path(
            plan,
            knowledge.basis_verification_path,
            locale,
        ),
        dependencies=dependencies,
        routing=routing,
    )
