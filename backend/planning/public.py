"""Stable, framework-independent contracts for stateless public planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Literal

from .catalog import LocalizedText
from .diagnostics import DiagnosticPath
from .facts import FactKind

type Locale = Literal["ar", "en"]


@dataclass(frozen=True, slots=True)
class PlanningInput:
    service_id: str
    facts: Mapping[str, object]
    locale: Locale
    evaluation_date: date

    def __post_init__(self) -> None:
        if self.locale not in ("ar", "en"):
            raise ValueError("locale must be exactly 'ar' or 'en'")
        if type(self.evaluation_date) is not date:
            raise ValueError("evaluation_date must be a calendar date")
        object.__setattr__(self, "facts", MappingProxyType(dict(self.facts)))


@dataclass(frozen=True, slots=True)
class PublicDiagnostic:
    code: str
    path: DiagnosticPath

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", tuple(self.path))


@dataclass(frozen=True, slots=True)
class AnswerDefinition:
    key: str
    kind: FactKind
    enum_options: tuple[str, ...] = ()
    minimum: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "enum_options", tuple(self.enum_options))


@dataclass(frozen=True, slots=True)
class PublicQuestion:
    id: str
    text: LocalizedText
    answers: tuple[AnswerDefinition, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "answers", tuple(self.answers))


@dataclass(frozen=True, slots=True)
class NextQuestionResult:
    service_id: str
    question: PublicQuestion
    type: Literal["next_question"] = "next_question"


@dataclass(frozen=True, slots=True)
class PlanResult:
    service_id: str
    procedure_id: str
    procedure_version_id: str
    title: LocalizedText
    type: Literal["plan"] = "plan"


@dataclass(frozen=True, slots=True)
class InconclusiveResult:
    reason: str
    type: Literal["inconclusive"] = "inconclusive"


@dataclass(frozen=True, slots=True)
class InvalidResult:
    diagnostics: tuple[PublicDiagnostic, ...]
    type: Literal["invalid"] = "invalid"

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


type PlanningResult = NextQuestionResult | PlanResult | InconclusiveResult | InvalidResult
