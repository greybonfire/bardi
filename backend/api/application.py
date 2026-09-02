"""Application boundary between Django knowledge loading and pure planning."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import cast

from knowledge.domain import load_consistent_knowledge_snapshot
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
from planning.public import Locale

SnapshotLoader = Callable[[], KnowledgeSnapshot]
Planner = Callable[[KnowledgeSnapshot, PlanningInput], PlanningResult]

_MESSAGES: Mapping[str, Mapping[str, str]] = {
    "unknown_service": {"ar": "الخدمة غير متاحة.", "en": "The service is unavailable."},
    "inactive_service": {"ar": "الخدمة غير نشطة.", "en": "The service is inactive."},
    "knowledge_unavailable": {"ar": "المعرفة غير متاحة حالياً.", "en": "Knowledge is unavailable."},
    "case_preparation_unavailable": {
        "ar": "لا يمكن إكمال التخطيط حالياً.",
        "en": "Planning cannot currently be completed.",
    },
    "plan_assembly_unavailable": {
        "ar": "لا يمكن إعداد الخطة حالياً.",
        "en": "Plan assembly is not yet available.",
    },
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
    snapshot_loader: SnapshotLoader = load_consistent_knowledge_snapshot,
    planner: Planner = plan_stateless,
) -> dict[str, object]:
    snapshot = snapshot_loader()
    detached_input = PlanningInput(
        planning_input.service_id,
        _decode_date_facts(planning_input.facts, snapshot),
        planning_input.locale,
        planning_input.evaluation_date,
    )
    return project_result(planner(snapshot, detached_input), detached_input.locale)


def list_active_services(
    *, snapshot_loader: SnapshotLoader = load_consistent_knowledge_snapshot
) -> dict[str, object]:
    snapshot = snapshot_loader()
    return {
        "services": [
            {
                "id": service.semantic_id,
                "title": {"ar": service.text.ar, "en": service.text.en},
            }
            for service in sorted(snapshot.services, key=lambda item: item.semantic_id)
            if service.is_active
        ]
    }
