"""Immutable v1 Fact registry and submitted-Fact validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Literal, TypeGuard, cast

from .diagnostics import ValidationDiagnostic

type FactKind = Literal["enum", "integer", "boolean", "date", "string"]
type FactValue = bool | int | date | str


@dataclass(frozen=True, slots=True)
class FactDefinition:
    key: str
    kind: FactKind
    enum_values: tuple[str, ...] = ()
    minimum: int | None = None
    derived: bool = False


_FACT_DEFINITIONS = {
    "citizenship": FactDefinition("citizenship", "enum", ("egyptian", "other")),
    "application_location": FactDefinition(
        "application_location", "enum", ("inside_egypt", "outside_egypt")
    ),
    "existing_passport_state": FactDefinition(
        "existing_passport_state",
        "enum",
        ("expired", "pages_full", "valid_with_pages", "lost", "damaged", "none"),
    ),
    "passport_class": FactDefinition("passport_class", "enum", ("ordinary", "other")),
    "birth_date": FactDefinition("birth_date", "date"),
    "sex": FactDefinition("sex", "enum", ("male", "female")),
    "national_id_status": FactDefinition(
        "national_id_status", "enum", ("valid_current_data", "invalid_or_expired", "not_held")
    ),
    "is_student": FactDefinition("is_student", "boolean"),
    "has_current_enrollment_certificate": FactDefinition(
        "has_current_enrollment_certificate", "boolean"
    ),
    "has_military_status_document": FactDefinition("has_military_status_document", "boolean"),
    "has_required_photos": FactDefinition("has_required_photos", "boolean"),
    "service_level": FactDefinition("service_level", "enum", ("standard", "urgent", "premium")),
    "residence_police_jurisdiction": FactDefinition("residence_police_jurisdiction", "string"),
    "minor_presenting_adult_role": FactDefinition(
        "minor_presenting_adult_role", "enum", ("parent", "legal_guardian", "other", "unknown")
    ),
    "national_id_possession_state": FactDefinition(
        "national_id_possession_state", "enum", ("held", "lost", "damaged", "none")
    ),
    "national_id_expiry_date": FactDefinition("national_id_expiry_date", "date"),
    "national_id_data_change_kind": FactDefinition(
        "national_id_data_change_kind",
        "enum",
        ("none", "residence", "profession", "marital_status", "other", "multiple"),
    ),
    "residence_governorate": FactDefinition("residence_governorate", "string"),
    "residence_district": FactDefinition("residence_district", "string"),
    "father_alive": FactDefinition("father_alive", "boolean"),
    "other_living_sons_of_father_count": FactDefinition(
        "other_living_sons_of_father_count", "integer", minimum=0
    ),
    "father_unable_to_earn_status": FactDefinition(
        "father_unable_to_earn_status",
        "enum",
        ("authority_documented_unable", "not_documented_unable"),
    ),
    "other_capable_family_support_for_father": FactDefinition(
        "other_capable_family_support_for_father", "enum", ("none_known", "present", "unknown")
    ),
    "mother_family_status": FactDefinition(
        "mother_family_status",
        "enum",
        ("widowed", "irrevocably_divorced", "husband_authority_documented_unable", "other"),
    ),
    "other_capable_family_support_for_mother": FactDefinition(
        "other_capable_family_support_for_mother", "enum", ("none_known", "present", "unknown")
    ),
    "unmarried_sisters_requiring_support_count": FactDefinition(
        "unmarried_sisters_requiring_support_count", "integer", minimum=0
    ),
    "other_capable_family_support_for_sisters": FactDefinition(
        "other_capable_family_support_for_sisters", "enum", ("none_known", "present", "unknown")
    ),
    "missing_relative_category": FactDefinition(
        "missing_relative_category",
        "enum",
        ("officer", "volunteer", "conscript", "citizen", "none"),
    ),
    "missing_relative_cause": FactDefinition(
        "missing_relative_cause", "enum", ("war_operations", "terrorist_operations", "other")
    ),
    "missing_relative_alive_status": FactDefinition(
        "missing_relative_alive_status", "enum", ("missing", "returned_or_proven_alive", "unknown")
    ),
    "applicant_largest_eligible_relative_status": FactDefinition(
        "applicant_largest_eligible_relative_status",
        "enum",
        ("authority_documented_yes", "authority_documented_no"),
    ),
    "sibling_service_status": FactDefinition(
        "sibling_service_status", "enum", ("compulsory_service", "reserve_recall", "none")
    ),
    "applicant_eldest_remaining_brother_status": FactDefinition(
        "applicant_eldest_remaining_brother_status",
        "enum",
        ("authority_documented_yes", "authority_documented_no"),
    ),
    "article7_third_exclusion_status": FactDefinition(
        "article7_third_exclusion_status",
        "enum",
        ("none_documented", "exclusion_present", "unknown"),
    ),
    "age_years_on_evaluation_date": FactDefinition(
        "age_years_on_evaluation_date", "integer", minimum=0, derived=True
    ),
    "card_expired_before_evaluation_date": FactDefinition(
        "card_expired_before_evaluation_date", "boolean", derived=True
    ),
    "renewal_deadline_date": FactDefinition("renewal_deadline_date", "date", derived=True),
    "renewal_deadline_passed": FactDefinition("renewal_deadline_passed", "boolean", derived=True),
    "only_son_candidate": FactDefinition("only_son_candidate", "boolean", derived=True),
}
FACT_DEFINITIONS: Mapping[str, FactDefinition] = MappingProxyType(_FACT_DEFINITIONS)


def value_matches_definition(definition: FactDefinition, value: object) -> TypeGuard[FactValue]:
    if definition.kind == "boolean":
        return type(value) is bool
    if definition.kind == "integer":
        return type(value) is int and (definition.minimum is None or value >= definition.minimum)
    if definition.kind == "date":
        return type(value) is date
    if definition.kind == "string":
        return type(value) is str
    if definition.kind == "enum":
        return type(value) is str and value in definition.enum_values
    return False  # type: ignore[unreachable]


@dataclass(frozen=True, slots=True)
class FactValidationResult:
    facts: Mapping[str, FactValue] | None
    diagnostics: tuple[ValidationDiagnostic, ...]

    @property
    def is_valid(self) -> bool:
        return not self.diagnostics

    @property
    def diagnostic_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.diagnostics)


@dataclass(frozen=True, slots=True)
class PreparedFacts:
    """Strict input seam after validation, derivation, and contradiction rejection.

    This type deliberately does not perform those stages; issue #38 will own their
    orchestration. ``missing_source_dependencies`` only records unresolved source Facts
    for a derived Fact and never authorizes Questions to resolve derived Facts directly.
    """

    values: Mapping[str, FactValue]
    submitted_keys: frozenset[str]
    missing_source_dependencies: Mapping[str, frozenset[str]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "submitted_keys", frozenset(self.submitted_keys))
        dependencies = {
            key: frozenset(source_keys)
            for key, source_keys in self.missing_source_dependencies.items()
        }
        object.__setattr__(self, "missing_source_dependencies", MappingProxyType(dependencies))


def validate_submitted_facts(
    facts: Mapping[str, object], definitions: Mapping[str, FactDefinition] = FACT_DEFINITIONS
) -> FactValidationResult:
    diagnostics: list[ValidationDiagnostic] = []
    copied: dict[str, FactValue] = {}
    for key in sorted(facts):
        definition = definitions.get(key)
        path = ("facts", key)
        if definition is None:
            diagnostics.append(ValidationDiagnostic(f"unsupported_fact_key:{key}", path))
        elif definition.derived:
            diagnostics.append(
                ValidationDiagnostic(f"derived_fact_cannot_be_submitted:{key}", path)
            )
        else:
            value = facts[key]
            if not value_matches_definition(definition, value):
                diagnostics.append(ValidationDiagnostic(f"invalid_fact_value:{key}", path))
            else:
                copied[key] = cast(FactValue, value)
    if diagnostics:
        return FactValidationResult(None, tuple(diagnostics))
    return FactValidationResult(MappingProxyType(copied), ())
