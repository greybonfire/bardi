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
    RenderedHistoricalClaim,
    UpcomingProcedureVersion,
    VerificationPathDefinition,
)
from .trust import assess_bundle, trust_state, verification_date
from .versions import upcoming_projection
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
            classification=plan.knowledge.sources[source_id].classification,
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


def _historical_claim(
    plan: SemanticPlan,
    item,
    kind: str,
    state: str,
    locale: Locale,
) -> RenderedHistoricalClaim:
    return RenderedHistoricalClaim(
        id=item.id,
        text=item.text.render(locale),
        kind=kind,
        verification_state=state,
        verified_on=verification_date(item, plan.knowledge),
        effective_from=getattr(item, "effective_from", None),
        effective_to=getattr(item, "effective_to", None),
        current_value_unknown=True,
        sources=_source_summaries(plan, item.evidence_link_ids),
        previous_amount=getattr(item, "amount", None) if kind == "fee" else None,
        previous_minimum_amount=(
            getattr(item, "minimum_amount", None) if kind == "fee" else None
        ),
        previous_maximum_amount=(
            getattr(item, "maximum_amount", None) if kind == "fee" else None
        ),
        previous_value_state=(
            getattr(item, "value_state", None) if kind == "fee" else None
        ),
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
            value_state=(
                item.value_state
                if trust_state(knowledge, item, plan.evaluation_date) == "current"
                or item.value_state == "unknown"
                else "unverified"
            ),
            amount=(item.amount if trust_state(knowledge, item, plan.evaluation_date) == "current" else None),
            minimum_amount=(
                item.minimum_amount if trust_state(knowledge, item, plan.evaluation_date) == "current" else None
            ),
            maximum_amount=(
                item.maximum_amount if trust_state(knowledge, item, plan.evaluation_date) == "current" else None
            ),
            currency=item.currency,
            fee_type=item.fee_type,
            verification_state=trust_state(knowledge, item, plan.evaluation_date),
            sources=_source_summaries(plan, item.evidence_link_ids),
            current_value_unknown=(
                trust_state(knowledge, item, plan.evaluation_date) != "current"
                or item.value_state == "unknown"
            ),
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
            verification_state=trust_state(
                knowledge, basis, plan.evaluation_date
            ),
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
            publication_state=knowledge.procedure.publication_state,
            historical=plan.historical,
            trust_state=assess_bundle(knowledge, plan.evaluation_date).state,
        ),
        eligibility_bases=eligibility_bases,
        basis_verification_path=_verification_path(
            plan,
            knowledge.basis_verification_path,
            locale,
        ),
        dependencies=dependencies,
        routing=routing,
        historical_claims=tuple(
            _historical_claim(
                plan, entry.item, entry.kind, entry.verification_state, locale
            )
            for entry in plan.historical_items
        ),
        upcoming_versions=upcoming_projection(plan.upcoming_versions, locale),
        inconclusive_claim_ids=plan.inconclusive_claim_ids,
        inconclusive_basis_ids=plan.inconclusive_basis_ids,
    )
