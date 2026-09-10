"""Named executable planning scenarios used as an atomic publication gate.

Scenarios are editorial acceptance records owned by one Procedure Version. They execute the
actual production snapshot adapters and pure planner; the retired research prototype is not
an import or runtime dependency.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any, cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from django.utils import timezone
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
from planning.facts import FactDefinition as DomainFactDefinition
from planning.public import Locale

from .domain import decode_stored_rule, referenced_fact_keys
from .models import (
    NONBLANK_PATTERN,
    ChecklistItem,
    EligibilityBasis,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    ServiceContradiction,
    ServiceContradictionFact,
    ServiceProcedureCandidate,
    ServiceQuestion,
    ServiceQuestionResolvedFact,
    Step,
    Warning,
)
from .publication import PublicationContext, PublicationDiagnostic

_RESULT_IDENTIFIER_KEYS: Mapping[str, frozenset[str]] = {
    "plan": frozenset(
        {
            "service_id",
            "procedure_id",
            "procedure_version_id",
            "eligibility_basis_ids",
            "inconclusive_basis_ids",
            "dependency_ids",
            "dependency_statuses",
            "checklist_item_ids",
            "step_ids",
            "warning_ids",
            "fee_ids",
            "routing_status",
            "routing_association_ids",
            "inconclusive_sections",
        }
    ),
    "next_question": frozenset({"service_id", "question_id"}),
    "inconclusive": frozenset({"reason"}),
    "invalid": frozenset(),
}
_RULE_FIELD_NAMES = frozenset(
    {
        "selection_predicate",
        "applicability",
        "reachability",
        "qualification",
        "satisfied_when",
    }
)
_SEMANTIC_HASH_EXCLUDED_FIELDS = frozenset(
    {
        "id",
        "state",
        "published_at",
        "published_by",
        "withdrawn_at",
        "withdrawn_by",
        "verified_on",
        "reverify_on",
        "verification_state",
    }
)


class PlanningScenario(models.Model):
    class Kind(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEGATIVE = "negative", "Negative"
        UNKNOWN = "unknown", "Unknown"
        CONTRADICTORY = "contradictory", "Contradictory"
        SUPPORTED_EDGE = "supported_edge", "Supported edge"

    class ResultFamily(models.TextChoices):
        PLAN = "plan", "Plan"
        NEXT_QUESTION = "next_question", "Next question"
        INCONCLUSIVE = "inconclusive", "Inconclusive"
        INVALID = "invalid", "Invalid"

    procedure_version = models.ForeignKey(
        ProcedureVersion,
        on_delete=models.CASCADE,
        related_name="planning_scenarios",
    )
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    evaluation_context = models.JSONField(default=dict)
    source_facts = models.JSONField(default=dict, blank=True)
    expected_result_family = models.CharField(max_length=24, choices=ResultFamily.choices)
    expected_identifiers = models.JSONField(default=dict, blank=True)
    expected_diagnostics = models.JSONField(default=list, blank=True)
    behavior_signature = models.CharField(max_length=64, editable=False)

    class Meta:
        app_label = "knowledge"
        ordering = ("procedure_version_id", "kind", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "name"),
                name="unique_planning_scenario_name_per_version",
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=NONBLANK_PATTERN),
                name="planning_scenario_name_nonblank",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=[
                        "positive",
                        "negative",
                        "unknown",
                        "contradictory",
                        "supported_edge",
                    ]
                ),
                name="planning_scenario_kind_supported",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    expected_result_family__in=[
                        "plan",
                        "next_question",
                        "inconclusive",
                        "invalid",
                    ]
                ),
                name="planning_scenario_result_supported",
            ),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if not self.name.strip():
            errors["name"] = "Scenario name is required."
        if self.kind not in self.Kind.values:
            errors["kind"] = "Unsupported scenario kind."
        if self.expected_result_family not in self.ResultFamily.values:
            errors["expected_result_family"] = "Unsupported public result family."

        context = self.evaluation_context
        if type(context) is not dict or set(context) != {"evaluation_date", "locale"}:
            errors["evaluation_context"] = (
                "Evaluation context must contain exactly evaluation_date and locale."
            )
        else:
            raw_date = context.get("evaluation_date")
            locale = context.get("locale")
            try:
                evaluation_date = date.fromisoformat(raw_date) if type(raw_date) is str else None
            except ValueError:
                evaluation_date = None
            if evaluation_date is None or evaluation_date.isoformat() != raw_date:
                errors["evaluation_context"] = "evaluation_date must be an ISO calendar date."
            elif self.procedure_version_id:
                version = self.procedure_version
                if version.effective_from and evaluation_date < version.effective_from:
                    errors["evaluation_context"] = "Scenario date precedes the version interval."
                if version.effective_to and evaluation_date > version.effective_to:
                    errors["evaluation_context"] = "Scenario date follows the version interval."
            if locale not in {"ar", "en"}:
                errors["evaluation_context"] = "locale must be exactly ar or en."

        if type(self.source_facts) is not dict or any(
            type(key) is not str or not key.strip() for key in self.source_facts
        ):
            errors["source_facts"] = "Submitted source Facts must be a JSON object with named keys."
        elif self.source_facts:
            definitions = FactDefinition.objects.in_bulk(self.source_facts, field_name="key")
            if len(definitions) != len(self.source_facts) or any(
                definition.derived for definition in definitions.values()
            ):
                errors["source_facts"] = "Scenarios may submit defined source Facts only."

        identifiers = self.expected_identifiers
        if type(identifiers) is not dict or any(type(key) is not str for key in identifiers):
            errors["expected_identifiers"] = "Expected identifiers must be a JSON object."
        elif self.expected_result_family in _RESULT_IDENTIFIER_KEYS:
            unsupported = set(identifiers) - _RESULT_IDENTIFIER_KEYS[self.expected_result_family]
            if unsupported:
                errors["expected_identifiers"] = "Expected identifiers contain unsupported keys."

        diagnostics = self.expected_diagnostics
        if type(diagnostics) is not list or any(
            type(item) is not str or not item.strip() for item in diagnostics
        ):
            errors["expected_diagnostics"] = "Expected diagnostics must be a list of codes."

        family = self.expected_result_family
        if self.kind in {self.Kind.POSITIVE, self.Kind.SUPPORTED_EDGE} and family != "plan":
            errors["expected_result_family"] = "Positive and supported-edge scenarios must plan."
        elif self.kind == self.Kind.NEGATIVE and family not in {"plan", "inconclusive"}:
            errors["expected_result_family"] = (
                "Negative scenarios must plan with a local exclusion or remain inconclusive."
            )
        elif self.kind == self.Kind.UNKNOWN and family not in {
            "plan",
            "next_question",
            "inconclusive",
        }:
            errors["expected_result_family"] = (
                "UNKNOWN scenarios must plan with local uncertainty, ask a question, or remain "
                "inconclusive."
            )
        elif self.kind == self.Kind.CONTRADICTORY and family != "invalid":
            errors["expected_result_family"] = "Contradictory scenarios must be invalid."

        if family == "plan":
            expected_version = (
                identifiers.get("procedure_version_id") if type(identifiers) is dict else None
            )
            if expected_version != getattr(self.procedure_version, "semantic_id", None):
                errors["expected_identifiers"] = (
                    "Plan scenarios must name this Procedure Version as procedure_version_id."
                )
        elif family == "next_question":
            question_id = identifiers.get("question_id")
            if not isinstance(question_id, str) or not question_id.strip():
                errors["expected_identifiers"] = "Question scenarios must name question_id."
        elif family == "inconclusive":
            reason = identifiers.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                errors["expected_identifiers"] = "Inconclusive scenarios must name reason."
        elif family == "invalid" and not diagnostics:
            errors["expected_diagnostics"] = "Invalid scenarios must name expected diagnostics."

        if family != "invalid" and diagnostics:
            errors["expected_diagnostics"] = "Only invalid scenarios may expect diagnostics."
        if errors:
            raise ValidationError(errors)

    def _editable_owner(self) -> ProcedureVersion:
        if self.procedure_version_id is None:
            raise ValidationError("Scenario ownership is required.")
        try:
            owner = ProcedureVersion.objects.get(pk=self.procedure_version_id)
        except ProcedureVersion.DoesNotExist as exc:
            raise ValidationError("Scenario ownership is required.") from exc
        if owner.state != ProcedureVersion.State.DRAFT:
            raise ValidationError(
                "Planning scenarios are editable only while their version is draft."
            )
        return owner

    def save(self, *args: Any, **kwargs: Any) -> None:
        owner = self._editable_owner()
        stored = type(self).objects.filter(pk=self.pk).only("procedure_version_id").first()
        if stored is not None and stored.procedure_version_id != self.procedure_version_id:
            raise ValidationError("Scenario ownership cannot be reassigned.")
        self.behavior_signature = planning_behavior_signature(owner)
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        self._editable_owner()
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.name}"


def _jsonable(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _semantic_row(instance: models.Model) -> dict[str, object]:
    payload: dict[str, object] = {"model": instance._meta.label_lower}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in _SEMANTIC_HASH_EXCLUDED_FIELDS:
            continue
        payload[field.name] = _jsonable(getattr(instance, field.attname))
    return payload


def _ordered_rows(queryset: models.QuerySet[Any]) -> list[dict[str, object]]:
    return [_semantic_row(row) for row in queryset.order_by("pk")]


def planning_behavior_signature(version: ProcedureVersion) -> str:
    """Hash consequential authored semantics, excluding trust/review freshness metadata."""

    from .fees import Fee
    from .procedure_dependencies import ProcedureDependency
    from .service_point_routing import (
        ProcedureServicePointAssociation,
        ServicePoint,
        ServicePointVersion,
    )

    association_rows = ProcedureServicePointAssociation.objects.filter(procedure_version=version)
    material_ids = tuple(
        association_rows.order_by("pk").values_list("service_point_version_id", flat=True)
    )
    point_ids = tuple(
        ServicePointVersion.objects.filter(pk__in=material_ids)
        .order_by("pk")
        .values_list("service_point_id", flat=True)
    )
    target_ids = tuple(
        ProcedureDependency.objects.filter(procedure_version=version)
        .order_by("pk")
        .values_list("target_procedure_id", flat=True)
    )
    service = version.procedure.primary_service
    payload: dict[str, object] = {
        "version": _semantic_row(version),
        "procedure": _semantic_row(version.procedure),
        "candidates": _ordered_rows(
            ServiceProcedureCandidate.objects.filter(procedure=version.procedure)
        ),
        "questions": _ordered_rows(ServiceQuestion.objects.filter(service=service)),
        "question_facts": _ordered_rows(
            ServiceQuestionResolvedFact.objects.filter(question__service=service)
        ),
        "contradictions": _ordered_rows(ServiceContradiction.objects.filter(service=service)),
        "contradiction_facts": _ordered_rows(
            ServiceContradictionFact.objects.filter(contradiction__service=service)
        ),
        "checklist": _ordered_rows(ChecklistItem.objects.filter(procedure_version=version)),
        "bases": _ordered_rows(EligibilityBasis.objects.filter(procedure_version=version)),
        "steps": _ordered_rows(Step.objects.filter(procedure_version=version)),
        "warnings": _ordered_rows(Warning.objects.filter(procedure_version=version)),
        "fees": _ordered_rows(Fee.objects.filter(procedure_version=version)),
        "dependencies": _ordered_rows(
            ProcedureDependency.objects.filter(procedure_version=version)
        ),
        "dependency_targets": _ordered_rows(Procedure.objects.filter(pk__in=target_ids)),
        "routing_associations": _ordered_rows(association_rows),
        "routing_material": _ordered_rows(ServicePointVersion.objects.filter(pk__in=material_ids)),
        "routing_points": _ordered_rows(ServicePoint.objects.filter(pk__in=point_ids)),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _iter_authored_rules(version: ProcedureVersion) -> Iterable[object]:
    from .fees import Fee
    from .procedure_dependencies import ProcedureDependency
    from .service_point_routing import ProcedureServicePointAssociation

    if version.applicability != {}:
        yield version.applicability
    rows: tuple[models.Model, ...] = (
        tuple(ServiceProcedureCandidate.objects.filter(procedure=version.procedure).order_by("pk"))
        + tuple(ChecklistItem.objects.filter(procedure_version=version).order_by("pk"))
        + tuple(EligibilityBasis.objects.filter(procedure_version=version).order_by("pk"))
        + tuple(Step.objects.filter(procedure_version=version).order_by("pk"))
        + tuple(Warning.objects.filter(procedure_version=version).order_by("pk"))
        + tuple(Fee.objects.filter(procedure_version=version).order_by("pk"))
        + tuple(ProcedureDependency.objects.filter(procedure_version=version).order_by("pk"))
        + tuple(
            ProcedureServicePointAssociation.objects.filter(procedure_version=version).order_by(
                "pk"
            )
        )
    )
    for row in rows:
        for field in row._meta.concrete_fields:
            if field.name not in _RULE_FIELD_NAMES or not isinstance(field, models.JSONField):
                continue
            value = getattr(row, field.name)
            if value not in ({}, None):
                yield value


def _rule_can_depend_on_facts(
    raw: object,
    definitions: Mapping[str, DomainFactDefinition],
) -> bool:
    decoded = decode_stored_rule(raw, definitions)
    return bool(decoded.predicate and referenced_fact_keys(decoded.predicate))


def required_scenario_kinds(
    version: ProcedureVersion,
    definitions: Mapping[str, DomainFactDefinition],
) -> frozenset[str]:
    """Derive scenario purposes from the Procedure Version's authored capabilities."""

    from .fees import Fee
    from .procedure_dependencies import ProcedureDependency
    from .service_point_routing import ProcedureServicePointAssociation

    required = {PlanningScenario.Kind.POSITIVE}
    if any(_rule_can_depend_on_facts(raw, definitions) for raw in _iter_authored_rules(version)):
        required.update({PlanningScenario.Kind.NEGATIVE, PlanningScenario.Kind.UNKNOWN})
    if ServiceContradiction.objects.filter(service=version.procedure.primary_service).exists():
        required.add(PlanningScenario.Kind.CONTRADICTORY)

    temporal_edge = bool(version.effective_from or version.effective_to)
    if not temporal_edge:
        for model in (ChecklistItem, EligibilityBasis, Step, Warning, Fee):
            if (
                model.objects.filter(procedure_version=version)
                .filter(
                    models.Q(effective_from__isnull=False) | models.Q(effective_to__isnull=False)
                )
                .exists()
            ):
                temporal_edge = True
                break
    feature_edge = (
        EligibilityBasis.objects.filter(procedure_version=version).exists()
        or Fee.objects.filter(procedure_version=version).exists()
        or ProcedureDependency.objects.filter(procedure_version=version).exists()
        or ProcedureServicePointAssociation.objects.filter(procedure_version=version).exists()
    )
    if temporal_edge or feature_edge:
        required.add(PlanningScenario.Kind.SUPPORTED_EDGE)
    return frozenset(required)


def _decode_date_facts(
    facts: Mapping[str, object], definitions: Mapping[str, DomainFactDefinition]
) -> dict[str, object]:
    decoded = dict(facts)
    for key, value in facts.items():
        definition = definitions.get(key)
        if definition is None or definition.kind != "date" or type(value) is not str:
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            continue
        if parsed.isoformat() == value:
            decoded[key] = parsed
    return decoded


def _observed_result(result: PlanningResult) -> tuple[str, dict[str, object], list[str]]:
    if isinstance(result, PlanResult):
        identifiers: dict[str, object] = {
            "service_id": result.service_id,
            "procedure_id": result.procedure_id,
            "procedure_version_id": result.procedure_version_id,
            "eligibility_basis_ids": [item.id for item in result.eligibility_bases],
            "inconclusive_basis_ids": list(result.inconclusive_basis_ids),
            "dependency_ids": [item.id for item in result.dependencies],
            "dependency_statuses": {item.id: item.status for item in result.dependencies},
            "checklist_item_ids": [item.id for item in result.checklist_items],
            "step_ids": [item.id for item in result.steps],
            "warning_ids": [item.id for item in result.warnings],
            "fee_ids": [item.id for item in result.fees],
            "routing_status": result.routing.status,
            "routing_association_ids": [
                item.association_id for item in result.routing.destinations
            ],
            "inconclusive_sections": list(result.inconclusive_sections),
        }
        return result.type, identifiers, []
    if isinstance(result, NextQuestionResult):
        return (
            result.type,
            {
                "service_id": result.service_id,
                "question_id": result.question.id,
            },
            [],
        )
    if isinstance(result, InconclusiveResult):
        return result.type, {"reason": result.reason}, []
    assert isinstance(result, InvalidResult)
    return result.type, {}, [item.code for item in result.diagnostics]


def _scenario_matches(scenario: PlanningScenario, result: PlanningResult) -> bool:
    family, identifiers, diagnostics = _observed_result(result)
    if family != scenario.expected_result_family:
        return False
    if any(identifiers.get(key) != value for key, value in scenario.expected_identifiers.items()):
        return False
    return bool(diagnostics == scenario.expected_diagnostics)


def _set_lifecycle_transition(value: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('bardi.procedure_version_lifecycle', %s, true)", [value])


def _execute_scenarios(
    context: PublicationContext,
    scenarios: tuple[PlanningScenario, ...],
) -> tuple[PublicationDiagnostic, ...]:
    """Expose the draft in a rollback-only savepoint and run production planning."""

    if context.version.pk is None or context.actor.pk is None:
        return ()
    # The structural temporal gate already owns the overlap diagnostic. Avoid turning that
    # independent defect into a generic scenario execution failure as well.
    overlaps = ProcedureVersion.objects.filter(
        procedure_id=context.version.procedure_id,
        state=ProcedureVersion.State.PUBLISHED,
    ).exclude(pk=context.version.pk)
    if context.version.effective_to is not None:
        overlaps = overlaps.filter(
            models.Q(effective_from__isnull=True)
            | models.Q(effective_from__lte=context.version.effective_to)
        )
    if context.version.effective_from is not None:
        overlaps = overlaps.filter(
            models.Q(effective_to__isnull=True)
            | models.Q(effective_to__gte=context.version.effective_from)
        )
    if overlaps.exists():
        return ()

    sid = transaction.savepoint()
    failures: list[PublicationDiagnostic] = []
    try:
        temporary_time = timezone.now()
        _set_lifecycle_transition("publish")
        updated = ProcedureVersion.objects.filter(
            pk=context.version.pk,
            state=ProcedureVersion.State.DRAFT,
        ).update(
            state=ProcedureVersion.State.PUBLISHED,
            published_at=temporary_time,
            published_by_id=context.actor.pk,
        )
        if updated != 1:
            raise RuntimeError("candidate draft could not be exposed for scenario execution")

        from .evidence_workflow_temporal import load_knowledge_snapshot_as_of

        snapshots: dict[date, KnowledgeSnapshot] = {}
        for scenario in scenarios:
            try:
                raw_date = cast(str, scenario.evaluation_context["evaluation_date"])
                evaluation_date = date.fromisoformat(raw_date)
                snapshot = snapshots.get(evaluation_date)
                if snapshot is None:
                    snapshot = load_knowledge_snapshot_as_of(evaluation_date)
                    snapshots[evaluation_date] = snapshot
                planning_input = PlanningInput(
                    context.version.procedure.primary_service.semantic_id,
                    _decode_date_facts(scenario.source_facts, snapshot.fact_definitions),
                    cast(Locale, scenario.evaluation_context["locale"]),
                    evaluation_date,
                )
                result = plan_stateless(snapshot, planning_input)
            except Exception:
                # Fail closed without serializing exception details or submitted Facts. A database
                # error may leave the transaction unusable until the outer savepoint is rolled back,
                # so stop executing scenarios after recording the named failure.
                failures.append(
                    PublicationDiagnostic(
                        PlanningScenarioPublicationGate.name,
                        "scenario_execution_failed",
                        scenario.name,
                    )
                )
                break
            if not _scenario_matches(scenario, result):
                failures.append(
                    PublicationDiagnostic(
                        PlanningScenarioPublicationGate.name,
                        "scenario_failed",
                        scenario.name,
                    )
                )
    finally:
        transaction.savepoint_rollback(sid)
        _set_lifecycle_transition("")
    return tuple(failures)


class PlanningScenarioPublicationGate:
    name = "core.planning_scenarios"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        if not getattr(settings, "PLANNING_SCENARIOS_REQUIRED", True):
            return ()

        scenarios = tuple(
            PlanningScenario.objects.select_for_update()
            .filter(procedure_version=context.version)
            .order_by("kind", "name", "pk")
        )
        required = required_scenario_kinds(context.version, context.fact_definitions)
        present = {scenario.kind for scenario in scenarios}
        failures: list[PublicationDiagnostic] = [
            PublicationDiagnostic(self.name, "missing_required_scenario", kind)
            for kind in sorted(required - present)
        ]

        current_signature = planning_behavior_signature(context.version)
        valid_for_execution: list[PlanningScenario] = []
        for scenario in scenarios:
            try:
                scenario.full_clean()
            except ValidationError:
                failures.append(PublicationDiagnostic(self.name, "invalid_scenario", scenario.name))
                continue
            if scenario.kind not in required:
                failures.append(
                    PublicationDiagnostic(self.name, "scenario_kind_not_required", scenario.name)
                )
                continue
            if scenario.behavior_signature != current_signature:
                failures.append(
                    PublicationDiagnostic(
                        self.name,
                        "scenario_stale_after_semantic_change",
                        scenario.name,
                    )
                )
                continue
            valid_for_execution.append(scenario)

        if failures:
            return failures
        return _execute_scenarios(context, tuple(valid_for_execution))


__all__ = (
    "PlanningScenario",
    "PlanningScenarioPublicationGate",
    "planning_behavior_signature",
    "required_scenario_kinds",
)
