"""Explicit v1 authoring allowlist. ORM metadata never selects uploaded fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from knowledge import models as m
from knowledge.fees import Fee
from knowledge.planning_scenarios import PlanningScenario
from knowledge.procedure_dependencies import ProcedureDependency
from knowledge.service_point_routing import ProcedureServicePointAssociation, ServicePointVersion


@dataclass(frozen=True)
class Mapping:
    model: Any
    fields: tuple[str, ...]
    references: dict[str, Any] = field(default_factory=dict)
    identity: str = "semantic_id"
    owner_kind: str = ""


TEXT = ("semantic_id", "text_ar", "text_en")
DATES = ("effective_from", "effective_to")
VERSION = Mapping(
    m.ProcedureVersion,
    TEXT + ("procedure", "rules_contract_version", "applicability") + DATES,
    {"procedure": m.Procedure},
)
CATALOG = {
    "services": Mapping(m.Service, TEXT),
    "procedures": Mapping(m.Procedure, TEXT + ("primary_service",), {"primary_service": m.Service}),
    "facts": Mapping(m.FactDefinition, ("key", "kind", "enum_values", "minimum"), identity="key"),
    "authorities": Mapping(m.Authority, ("semantic_id", "name_ar", "name_en")),
    "sources": Mapping(
        m.Source,
        (
            "semantic_id",
            "authority",
            "title",
            "locator",
            "classification",
            "published_on",
            "effective_from",
            "effective_to",
            "retrieved_on",
            "observation_date",
            "observation_context",
        ),
        {"authority": m.Authority},
    ),
    "document_types": Mapping(m.DocumentType, ("semantic_id", "name_ar", "name_en")),
}
OWNED = {
    "bases": Mapping(
        m.EligibilityBasis,
        TEXT + ("reachability", "qualification", "display_order") + DATES,
        owner_kind="eligibility_basis",
    ),
    "checklist_items": Mapping(
        m.ChecklistItem,
        TEXT
        + (
            "classification",
            "document_type",
            "quantity",
            "original_quantity",
            "copy_quantity",
            "display_order",
            "applicability",
            "scope",
            "scope_reference",
        )
        + DATES,
        {"document_type": m.DocumentType},
        owner_kind="checklist_item",
    ),
    "steps": Mapping(
        m.Step,
        TEXT
        + ("phase", "phase_order", "slot", "applicability", "scope", "eligibility_basis")
        + DATES,
        {"eligibility_basis": m.EligibilityBasis},
        owner_kind="step",
    ),
    "warnings": Mapping(
        m.Warning,
        TEXT + ("severity", "kind", "role", "display_order", "applicability") + DATES,
        owner_kind="warning",
    ),
    "fees": Mapping(
        Fee,
        TEXT
        + (
            "value_state",
            "amount",
            "minimum_amount",
            "maximum_amount",
            "currency",
            "fee_type",
            "display_order",
            "applicability",
            "scope",
            "eligibility_basis",
        )
        + DATES,
        {"eligibility_basis": m.EligibilityBasis},
        owner_kind="fee",
    ),
    "dependencies": Mapping(
        ProcedureDependency,
        TEXT
        + ("target_procedure", "relation", "applicability", "satisfied_when", "display_order")
        + DATES,
        {"target_procedure": m.Procedure},
        owner_kind="procedure_dependency",
    ),
    "routing_associations": Mapping(
        ProcedureServicePointAssociation,
        ("semantic_id", "service_point_version", "applicability") + DATES,
        {"service_point_version": ServicePointVersion},
        owner_kind="procedure_service_point_association",
    ),
    "scenarios": Mapping(
        PlanningScenario,
        (
            "name",
            "kind",
            "evaluation_context",
            "source_facts",
            "expected_result_family",
            "expected_identifiers",
            "expected_diagnostics",
        ),
        identity="name",
    ),
}
EVIDENCE = Mapping(
    m.EvidenceLink,
    (
        "semantic_id",
        "passage",
        "location",
        "applicability_context",
        "effective_from",
        "effective_to",
        "retrieved_on",
        "support_status",
    ),
)
QUESTION = Mapping(m.ServiceQuestion, TEXT + ("fact", "priority"), {"fact": m.FactDefinition})
CANDIDATE = Mapping(
    m.ServiceProcedureCandidate,
    ("procedure", "selection_predicate"),
    {"procedure": m.Procedure},
    identity="procedure",
)
CONTRADICTION = Mapping(m.ServiceContradiction, ("semantic_id", "condition"))
RULE_FIELDS = frozenset(
    {
        "applicability",
        "reachability",
        "qualification",
        "satisfied_when",
        "selection_predicate",
        "condition",
    }
)
DATE_FIELDS = frozenset({*DATES, "published_on", "retrieved_on", "observation_date"})


def authored(row: Any, spec: Mapping) -> dict[str, Any]:
    result = {}
    for name in spec.fields:
        value = getattr(row, name)
        if name in spec.references and value is not None:
            value = value.key if spec.references[name] is m.FactDefinition else value.semantic_id
        if isinstance(value, date):
            value = value.isoformat()
        result[name] = value
    return result
