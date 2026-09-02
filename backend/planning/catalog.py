"""Immutable, framework-free snapshots of the persisted planning catalog.

Snapshots contain decoded planning-domain values only; loading and all ORM access belong
in the knowledge adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType

from .facts import FactDefinition
from .rules import Predicate


@dataclass(frozen=True, slots=True)
class LocalizedText:
    ar: str
    en: str


@dataclass(frozen=True, slots=True)
class ProcedureCandidateSnapshot:
    procedure_semantic_id: str
    text: LocalizedText
    selection_predicate: Predicate


@dataclass(frozen=True, slots=True)
class QuestionSnapshot:
    semantic_id: str
    text: LocalizedText
    priority: int
    primary_fact_key: str
    resolved_fact_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolved_fact_keys", tuple(self.resolved_fact_keys))


@dataclass(frozen=True, slots=True)
class ContradictionSnapshot:
    semantic_id: str
    condition: Predicate
    fact_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_keys", tuple(self.fact_keys))


@dataclass(frozen=True, slots=True)
class ServiceSnapshot:
    semantic_id: str
    text: LocalizedText
    candidates: tuple[ProcedureCandidateSnapshot, ...]
    questions: tuple[QuestionSnapshot, ...]
    contradictions: tuple[ContradictionSnapshot, ...]
    is_active: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "questions", tuple(self.questions))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))


@dataclass(frozen=True, slots=True)
class ProcedureVersionSnapshot:
    semantic_id: str
    procedure_semantic_id: str
    text: LocalizedText
    applicability: Predicate
    rules_contract_version: str
    state: str
    effective_from: date | None
    effective_to: date | None
    published_at: datetime | None = None
    published_by_id: int | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    fact_definitions: Mapping[str, FactDefinition]
    services: tuple[ServiceSnapshot, ...]
    procedure_versions: tuple[ProcedureVersionSnapshot, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_definitions", MappingProxyType(dict(self.fact_definitions)))
        object.__setattr__(self, "services", tuple(self.services))
        object.__setattr__(self, "procedure_versions", tuple(self.procedure_versions))
