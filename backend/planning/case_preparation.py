"""Pure, pinned v1 source-Fact validation, derivation, and contradiction checking."""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from .catalog import ServiceSnapshot
from .diagnostics import ValidationDiagnostic
from .evaluator import EvaluationTrace, TruthValue, evaluate
from .facts import (
    FACT_DEFINITIONS,
    FactDefinition,
    FactValue,
    PreparedFacts,
    validate_submitted_facts,
)
from .rules import Predicate

# This is production-owned contract metadata. It must never be populated from catalog data.
DERIVED_FACT_DEPENDENCIES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "age_years_on_evaluation_date": frozenset({"birth_date"}),
        "card_expired_before_evaluation_date": frozenset({"national_id_expiry_date"}),
        "renewal_deadline_date": frozenset({"national_id_expiry_date"}),
        "renewal_deadline_passed": frozenset({"national_id_expiry_date"}),
        "only_son_candidate": frozenset({"father_alive", "other_living_sons_of_father_count"}),
    }
)


@dataclass(frozen=True, slots=True)
class CasePreparationSuccess:
    prepared_facts: PreparedFacts


@dataclass(frozen=True, slots=True)
class CasePreparationInvalid:
    """Invalid caller input or a TRUE authored contradiction."""

    diagnostics: tuple[ValidationDiagnostic, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True, slots=True)
class CasePreparationConfigurationDefect:
    """A redacted internal indication that trusted knowledge is malformed."""

    diagnostic_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostic_codes", tuple(self.diagnostic_codes))


type CasePreparationOutcome = (
    CasePreparationSuccess | CasePreparationInvalid | CasePreparationConfigurationDefect
)


def derived_definition_is_compatible(definition: FactDefinition) -> bool:
    """Return whether a derived definition exactly names a pinned v1 implementation."""

    expected = FACT_DEFINITIONS.get(definition.key)
    return (
        definition.derived
        and expected is not None
        and expected.derived
        and definition == expected
        and definition.key in DERIVED_FACT_DEPENDENCIES
    )


def _completed_years(birth_date: date, evaluation_date: date) -> int:
    years = evaluation_date.year - birth_date.year
    if (evaluation_date.month, evaluation_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def _add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    if not 1 <= year <= date.max.year:
        raise OverflowError("calendar date is outside the supported representation")
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _referenced_fact_keys(predicate: Predicate) -> frozenset[str]:
    result: set[str] = set()
    stack = [predicate]
    while stack:
        current = stack.pop()
        if current.fact is not None:
            result.add(current.fact)
        stack.extend(current.children)
    return frozenset(result)


def _influential_submitted_fact_keys(trace: EvaluationTrace) -> frozenset[str]:
    """Collect submitted Fact leaves that actually influenced this evaluation result."""

    result: set[str] = set()
    stack = [trace]
    while stack:
        current = stack.pop()
        if not current.affected_result:
            continue
        if current.fact_key is not None and current.submitted is True:
            result.add(current.fact_key)
        stack.extend(current.children)
    return frozenset(result)


def prepare_case(
    definitions: Mapping[str, FactDefinition],
    service: ServiceSnapshot,
    submitted_facts: Mapping[str, object],
    evaluation_date: date,
) -> CasePreparationOutcome:
    """Validate and prepare one case before any Procedure predicate is evaluated.

    Only the five implementations registered in this module can produce derived values.
    Catalog definitions merely opt a compatible derived key into the prepared snapshot.
    """

    incompatible = tuple(
        sorted(
            key
            for key, definition in definitions.items()
            if definition.derived and not derived_definition_is_compatible(definition)
        )
    )
    if incompatible:
        return CasePreparationConfigurationDefect(
            tuple(f"unsupported_derived_fact:{key}" for key in incompatible)
        )

    validation = validate_submitted_facts(submitted_facts, definitions)
    if validation.facts is None:
        return CasePreparationInvalid(validation.diagnostics)
    if type(evaluation_date) is not date:
        return CasePreparationInvalid(
            (
                ValidationDiagnostic(
                    "invalid_evaluation_date", ("evaluation_context", "evaluation_date")
                ),
            )
        )

    source_values = validation.facts
    values: dict[str, FactValue] = dict(source_values)
    missing: dict[str, frozenset[str]] = {}

    for key in sorted(DERIVED_FACT_DEPENDENCIES):
        definition = definitions.get(key)
        if definition is None:
            continue
        # Compatibility was checked above; this assertion cannot authorize behavior.
        assert derived_definition_is_compatible(definition)
        omitted = DERIVED_FACT_DEPENDENCIES[key] - source_values.keys()
        if omitted:
            missing[key] = frozenset(omitted)
            continue

        if key == "age_years_on_evaluation_date":
            birth = source_values["birth_date"]
            if type(birth) is not date or birth > evaluation_date:
                return CasePreparationInvalid(
                    (
                        ValidationDiagnostic(
                            "invalid_fact_value:birth_date", ("facts", "birth_date")
                        ),
                    )
                )
            values[key] = _completed_years(birth, evaluation_date)
        elif key in {
            "card_expired_before_evaluation_date",
            "renewal_deadline_date",
            "renewal_deadline_passed",
        }:
            expiry = source_values["national_id_expiry_date"]
            if type(expiry) is not date:
                return CasePreparationInvalid(
                    (
                        ValidationDiagnostic(
                            "invalid_fact_value:national_id_expiry_date",
                            ("facts", "national_id_expiry_date"),
                        ),
                    )
                )
            if key == "card_expired_before_evaluation_date":
                values[key] = evaluation_date > expiry
            else:
                try:
                    deadline = _add_calendar_months(expiry, 3)
                except OverflowError, ValueError:
                    return CasePreparationInvalid(
                        (
                            ValidationDiagnostic(
                                "invalid_fact_value:national_id_expiry_date",
                                ("facts", "national_id_expiry_date"),
                            ),
                        )
                    )
                values[key] = (
                    deadline if key == "renewal_deadline_date" else evaluation_date > deadline
                )
        else:
            father_alive = source_values["father_alive"]
            other_sons = source_values["other_living_sons_of_father_count"]
            # Source validation guarantees exact bool/int types and the nonnegative minimum.
            values[key] = father_alive is True and other_sons == 0

    prepared = PreparedFacts(values, frozenset(source_values), missing)

    contradictory_keys: set[str] = set()
    for contradiction in service.contradictions:
        declared = contradiction.fact_keys
        referenced = _referenced_fact_keys(contradiction.condition)
        if (
            len(declared) < 2
            or len(set(declared)) != len(declared)
            or set(declared) != set(referenced)
            or any(
                (definition := definitions.get(key)) is None or definition.derived
                for key in declared
            )
        ):
            return CasePreparationConfigurationDefect(("invalid_contradiction_definition",))
        result = evaluate(
            contradiction.condition,
            prepared.values,
            submitted_keys=prepared.submitted_keys,
        )
        if result.value is TruthValue.TRUE:
            contradictory_keys.update(_influential_submitted_fact_keys(result.trace))

    if contradictory_keys:
        return CasePreparationInvalid(
            tuple(
                ValidationDiagnostic("contradictory_facts", ("facts", key))
                for key in sorted(contradictory_keys)
            )
        )
    return CasePreparationSuccess(prepared)
