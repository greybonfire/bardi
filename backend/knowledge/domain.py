"""Adapters between persisted catalog rows and the ORM-free planning domain."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from planning.facts import FACT_DEFINITIONS, FactKind
from planning.facts import FactDefinition as DomainFactDefinition
from planning.rules import Predicate, RuleValidationResult, validate_rule_v1

if TYPE_CHECKING:
    from .models import FactDefinition


def to_domain_fact(row: FactDefinition) -> DomainFactDefinition:
    return DomainFactDefinition(
        key=row.key,
        kind=cast(FactKind, row.kind),
        enum_values=tuple(row.enum_values),
        minimum=row.minimum,
        derived=row.derived,
    )


def load_fact_definitions() -> Mapping[str, DomainFactDefinition]:
    from .models import FactDefinition

    values = {row.key: to_domain_fact(row) for row in FactDefinition.objects.order_by("key")}
    return MappingProxyType(values)


def compatibility_errors(
    rows: Iterable[FactDefinition],
    registry: Mapping[str, DomainFactDefinition] = FACT_DEFINITIONS,
) -> tuple[str, ...]:
    errors: list[str] = []
    for row in sorted(rows, key=lambda item: item.key):
        expected = registry.get(row.key)
        if expected is None:
            errors.append(f"{row.key}:key")
            continue
        actual = to_domain_fact(row)
        for field in ("kind", "enum_values", "minimum", "derived"):
            if getattr(actual, field) != getattr(expected, field):
                errors.append(f"{row.key}:{field}")
    return tuple(errors)


def decode_stored_rule(
    raw: object,
    definitions: Mapping[str, DomainFactDefinition] | None = None,
) -> RuleValidationResult:
    """Decode using persisted definitions, never the planning default implicitly."""
    mapping = load_fact_definitions() if definitions is None else definitions
    return validate_rule_v1(raw, definitions=mapping)


def referenced_fact_keys(predicate: Predicate) -> frozenset[str]:
    keys: set[str] = set()
    stack = [predicate]
    while stack:
        current = stack.pop()
        if current.fact is not None:
            keys.add(current.fact)
        stack.extend(current.children)
    return frozenset(keys)


def diagnostic_messages(result: RuleValidationResult) -> list[str]:
    return [
        f"{diagnostic.code} at {'.'.join(str(part) for part in diagnostic.path)}"
        for diagnostic in result.diagnostics
    ]
