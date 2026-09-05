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
from .trust import Freshness

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
class PublicSource:
    id: str
    authority_id: str
    title: str
    locator: str
    classification: str
    retrieved_on: date


@dataclass(frozen=True, slots=True)
class PublicChecklistItem:
    id: str
    text: LocalizedText
    classification: str
    classification_label: LocalizedText
    quantity: int
    original_quantity: int
    copy_quantity: int
    document_type_id: str | None
    scope: str
    sources: tuple[PublicSource, ...]
    freshness: Freshness

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True, slots=True)
class PublicStep:
    id: str
    text: LocalizedText
    phase: str
    sources: tuple[PublicSource, ...]
    freshness: Freshness

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True, slots=True)
class PublicWarning:
    id: str
    text: LocalizedText
    severity: str
    kind: str
    role: str
    sources: tuple[PublicSource, ...]
    freshness: Freshness

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True, slots=True)
class PlanResult:
    service_id: str
    procedure_id: str
    procedure_version_id: str
    title: LocalizedText
    checklist_items: tuple[PublicChecklistItem, ...] = ()
    steps: tuple[PublicStep, ...] = ()
    warnings: tuple[PublicWarning, ...] = ()
    type: Literal["plan"] = "plan"

    def __post_init__(self) -> None:
        object.__setattr__(self, "checklist_items", tuple(self.checklist_items))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "warnings", tuple(self.warnings))


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
