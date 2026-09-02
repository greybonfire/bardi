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


class PlanResponse(StrictSchema):
    type: Literal["plan"]
    service_id: str
    procedure_id: str
    procedure_version_id: str
    title: str


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
