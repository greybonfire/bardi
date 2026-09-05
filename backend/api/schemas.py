"""Strict request and explicit whitelist response schemas for API v1."""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from ninja import Field, Schema
from pydantic import ConfigDict, StrictBool, StrictInt, StrictStr, field_validator


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvaluationContext(StrictSchema):
    evaluation_date: date

    @field_validator("evaluation_date", mode="before")
    @classmethod
    def canonical_date(cls, value: object) -> date:
        if type(value) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("invalid_date")
        return date.fromisoformat(value)


type TransportValue = StrictBool | StrictInt | StrictStr | None


class PlanningRequest(StrictSchema):
    service_id: Annotated[str, Field(min_length=1, max_length=128, pattern=r".*\S.*")]
    facts: dict[str, TransportValue]
    locale: Literal["ar", "en"]
    evaluation_context: EvaluationContext


class LocalizedTitleResponse(StrictSchema):
    ar: str
    en: str


class ServiceNavigationItem(StrictSchema):
    id: str
    title: LocalizedTitleResponse


class NavigationResponse(StrictSchema):
    services: list[ServiceNavigationItem]


class AnswerDefinitionResponse(StrictSchema):
    key: str
    kind: Literal["enum", "integer", "boolean", "date", "string"]
    enum_options: list[str]
    minimum: int | None


class QuestionResponse(StrictSchema):
    id: str
    text: str
    answers: list[AnswerDefinitionResponse]


class NextQuestionResponse(StrictSchema):
    type: Literal["next_question"]
    service_id: str
    question: QuestionResponse


class FreshnessResponse(StrictSchema):
    state: Literal["current", "needs_reverification", "stale", "disputed", "unknown"]
    verified_on: date | None
    reverify_on: date | None


class GuidanceSourceResponse(StrictSchema):
    id: str
    authority_id: str
    title: str
    locator: str
    classification: Literal["official", "field_report", "secondary"]
    retrieved_on: date


class EligibilityBasisResponse(StrictSchema):
    id: str
    text: str
    checklist_item_ids: list[str]
    step_ids: list[str]
    sources: list[GuidanceSourceResponse]
    freshness: FreshnessResponse


class ChecklistItemResponse(StrictSchema):
    id: str
    text: str
    classification: Literal["official_requirement", "practical_preparation"]
    classification_label: str
    quantity: int
    original_quantity: int
    copy_quantity: int
    document_type_id: str | None
    scope: Literal["procedure", "eligibility_basis"]
    eligibility_basis_id: str | None
    sources: list[GuidanceSourceResponse]
    freshness: FreshnessResponse


class StepResponse(StrictSchema):
    id: str
    text: str
    phase: str
    scope: Literal["procedure", "eligibility_basis"]
    eligibility_basis_id: str | None
    sources: list[GuidanceSourceResponse]
    freshness: FreshnessResponse


class FeeResponse(StrictSchema):
    id: str
    text: str
    value_state: Literal["known", "range", "unknown", "unverified"]
    amount: int | None
    minimum_amount: int | None
    maximum_amount: int | None
    currency: str
    fee_type: str
    current_value_unknown: bool
    sources: list[GuidanceSourceResponse]
    freshness: FreshnessResponse


class WarningResponse(StrictSchema):
    id: str
    text: str
    severity: Literal["info", "important"]
    kind: Literal["administrative", "product"]
    role: Literal["general", "regeneration", "limitation"]
    sources: list[GuidanceSourceResponse]
    freshness: FreshnessResponse


class PlanResponse(StrictSchema):
    type: Literal["plan"]
    service_id: str
    procedure_id: str
    procedure_version_id: str
    title: str
    eligibility_bases: list[EligibilityBasisResponse]
    inconclusive_basis_ids: list[str]
    checklist_items: list[ChecklistItemResponse]
    steps: list[StepResponse]
    fees: list[FeeResponse]
    warnings: list[WarningResponse]


class InconclusiveResponse(StrictSchema):
    type: Literal["inconclusive"]
    reason: str
    message: str


class DiagnosticResponse(StrictSchema):
    code: str
    path: list[str | int]


class InvalidResponse(StrictSchema):
    type: Literal["invalid"]
    diagnostics: list[DiagnosticResponse]


type PlanningResponse = Annotated[
    NextQuestionResponse | PlanResponse | InconclusiveResponse | InvalidResponse,
    Field(discriminator="type"),
]
