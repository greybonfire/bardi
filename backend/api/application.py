"""Application boundary between Django knowledge loading and pure planning."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import cast

from knowledge.evidence_workflow_temporal import (
    load_consistent_service_knowledge_snapshot_as_of,
)
from knowledge.navigation import ServiceNavigationEntry, load_active_service_navigation
from planning import (
    InconclusiveResult,
    InvalidResult,
    KnowledgeSnapshot,
    NextQuestionResult,
    PlanningInput,
    PlanningResult,
    PlanResult,
    plan_stateless,
)
from planning.public import Locale, PublicSource
from planning.trust import Freshness

SnapshotLoader = Callable[[], KnowledgeSnapshot]
NavigationLoader = Callable[[], tuple[ServiceNavigationEntry, ...]]
Planner = Callable[[KnowledgeSnapshot, PlanningInput], PlanningResult]

_MESSAGES: Mapping[str, Mapping[str, str]] = {
    "unknown_service": {"ar": "الخدمة غير متاحة.", "en": "The service is unavailable."},
    "inactive_service": {"ar": "الخدمة غير نشطة.", "en": "The service is inactive."},
    "knowledge_unavailable": {"ar": "المعرفة غير متاحة حالياً.", "en": "Knowledge is unavailable."},
}
_DEFAULT_MESSAGE = {"ar": "لا توجد نتيجة حاسمة.", "en": "No conclusive result is available."}


def _localized(text: object, locale: Locale) -> str:
    return cast(str, getattr(text, locale))


def _decode_date_facts(
    facts: Mapping[str, object], snapshot: KnowledgeSnapshot
) -> dict[str, object]:
    decoded = dict(facts)
    for key, value in facts.items():
        definition = snapshot.fact_definitions.get(key)
        if definition is None or definition.kind != "date" or type(value) is not str:
            continue
        try:
            if len(value) == 10 and date.fromisoformat(value).isoformat() == value:
                decoded[key] = date.fromisoformat(value)
        except ValueError:
            pass
    return decoded


def _project_source(source: PublicSource) -> dict[str, object]:
    return {
        "id": source.id,
        "authority_id": source.authority_id,
        "title": source.title,
        "locator": source.locator,
        "classification": source.classification,
        "retrieved_on": source.retrieved_on,
    }


def _project_freshness(freshness: Freshness) -> dict[str, object]:
    return {
        "state": freshness.state,
        "verified_on": freshness.verified_on,
        "reverify_on": freshness.reverify_on,
    }


def project_result(result: PlanningResult, locale: Locale) -> dict[str, object]:
    """Whitelist public fields; never serialize domain objects directly."""

    if isinstance(result, NextQuestionResult):
        return {
            "type": "next_question",
            "service_id": result.service_id,
            "question": {
                "id": result.question.id,
                "text": _localized(result.question.text, locale),
                "answers": [
                    {
                        "key": answer.key,
                        "kind": answer.kind,
                        "enum_options": list(answer.enum_options),
                        "minimum": answer.minimum,
                    }
                    for answer in result.question.answers
                ],
            },
        }
    if isinstance(result, PlanResult):
        return {
            "type": "plan",
            "service_id": result.service_id,
            "procedure_id": result.procedure_id,
            "procedure_version_id": result.procedure_version_id,
            "title": _localized(result.title, locale),
            "eligibility_bases": [
                {
                    "id": item.id,
                    "text": _localized(item.text, locale),
                    "checklist_item_ids": list(item.checklist_item_ids),
                    "step_ids": list(item.step_ids),
                    "sources": [_project_source(source) for source in item.sources],
                    "freshness": _project_freshness(item.freshness),
                }
                for item in result.eligibility_bases
            ],
            "inconclusive_basis_ids": list(result.inconclusive_basis_ids),
            "inconclusive_sections": list(result.inconclusive_sections),
            "dependencies": [
                {
                    "id": item.id,
                    "text": _localized(item.text, locale),
                    "relation": item.relation,
                    "status": item.status,
                    "target_procedure_id": item.target_procedure_id,
                    "target_procedure": _localized(item.target_procedure, locale),
                    "target_procedure_version_id": item.target_procedure_version_id,
                    "sources": [_project_source(source) for source in item.sources],
                    "freshness": _project_freshness(item.freshness),
                }
                for item in result.dependencies
            ],
            "steps": [
                {
                    "id": item.id,
                    "text": _localized(item.text, locale),
                    "phase": item.phase,
                    "sources": [_project_source(source) for source in item.sources],
                    "freshness": _project_freshness(item.freshness),
                }
                for item in result.steps
            ],
            "fees": [
                {
                    "id": item.id,
                    "text": _localized(item.text, locale),
                    "value_state": item.value_state,
                    "amount": item.amount,
                    "minimum_amount": item.minimum_amount,
                    "maximum_amount": item.maximum_amount,
                    "currency": item.currency,
                    "fee_type": item.fee_type,
                    "current_value_unknown": item.current_value_unknown,
                    "sources": [_project_source(source) for source in item.sources],
                    "freshness": _project_freshness(item.freshness),
                }
                for item in result.fees
            ],
            "warnings": [
                {
                    "id": item.id,
                    "text": _localized(item.text, locale),
                    "severity": item.severity,
                    "kind": item.kind,
                    "role": item.role,
                    "sources": [_project_source(source) for source in item.sources],
                    "freshness": _project_freshness(item.freshness),
                }
                for item in result.warnings
            ],
            "routing": {
                "status": result.routing.status,
                "destinations": [
                    {
                        "service_point_id": item.service_point_id,
                        "service_point_version_id": item.service_point_version_id,
                        "association_id": item.association_id,
                        "name": _localized(item.name, locale),
                        "address": _localized(item.address, locale),
                        "availability": item.availability,
                        "effective_from": item.effective_from,
                        "effective_to": item.effective_to,
                        "sources": [_project_source(source) for source in item.sources],
                    }
                    for item in result.routing.destinations
                ],
                "verification_sources": [
                    _project_source(source) for source in result.routing.verification_sources
                ],
            },
            "checklist_items": [
                {
                    "id": item.id,
                    "text": _localized(item.text, locale),
                    "classification": item.classification,
                    "classification_label": _localized(item.classification_label, locale),
                    "quantity": item.quantity,
                    "original_quantity": item.original_quantity,
                    "copy_quantity": item.copy_quantity,
                    "document_type_id": item.document_type_id,
                    "scope": item.scope,
                    "sources": [_project_source(source) for source in item.sources],
                    "freshness": _project_freshness(item.freshness),
                }
                for item in result.checklist_items
            ],
        }
    if isinstance(result, InvalidResult):
        return {
            "type": "invalid",
            "diagnostics": [
                {"code": item.code, "path": list(item.path)} for item in result.diagnostics
            ],
        }
    assert isinstance(result, InconclusiveResult)
    message = _MESSAGES.get(result.reason, _DEFAULT_MESSAGE)[locale]
    return {"type": "inconclusive", "reason": result.reason, "message": message}


def execute_planning(
    planning_input: PlanningInput,
    *,
    snapshot_loader: SnapshotLoader | None = None,
    planner: Planner = plan_stateless,
) -> dict[str, object]:
    snapshot = (
        load_consistent_service_knowledge_snapshot_as_of(
            planning_input.service_id, planning_input.evaluation_date
        )
        if snapshot_loader is None
        else snapshot_loader()
    )
    detached_input = PlanningInput(
        planning_input.service_id,
        _decode_date_facts(planning_input.facts, snapshot),
        planning_input.locale,
        planning_input.evaluation_date,
    )
    return project_result(planner(snapshot, detached_input), detached_input.locale)


def list_active_services(
    *,
    navigation_loader: NavigationLoader = load_active_service_navigation,
    snapshot_loader: SnapshotLoader | None = None,
) -> dict[str, object]:
    if snapshot_loader is not None:
        snapshot = snapshot_loader()
        services = (
            {
                "id": service.semantic_id,
                "title": {"ar": service.text.ar, "en": service.text.en},
            }
            for service in sorted(snapshot.services, key=lambda item: item.semantic_id)
            if service.is_active
        )
    else:
        entries = sorted(navigation_loader(), key=lambda item: item.semantic_id)
        services = (
            {
                "id": entry.semantic_id,
                "title": {"ar": entry.text_ar, "en": entry.text_en},
            }
            for entry in entries
        )
    return {"services": list(services)}
