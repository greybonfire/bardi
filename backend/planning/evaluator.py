"""Pure deterministic evaluation of validated v1 predicates over typed Facts.

Validation is a mandatory, separate boundary.  This module accepts only a non-optional
``Predicate`` returned by successful ``validate_rule_v1`` validation, an immutable typed
Fact mapping produced by successful Fact validation (and, later, derivation), and the
original source-key set captured before derivation.  It does not decode or validate raw
input.

Traces are transient editor/test diagnostics.  An UNKNOWN trace with
``affected_result=True`` is consequential; one with ``affected_result=False`` was fully
evaluated but dominated by the enclosing boolean result.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum

from .facts import FactValue
from .rules import Predicate


class TruthValue(str, Enum):  # noqa: UP042 - public contract explicitly requires str, Enum
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EvaluationTrace:
    op: str
    result: TruthValue
    fact_key: str | None = None
    fact_present: bool | None = None
    submitted: bool | None = None
    actual_value: object | None = None
    expected_value: object | None = None
    missing_facts: frozenset[str] = frozenset()
    affected_result: bool = True
    children: tuple[EvaluationTrace, ...] = ()


@dataclass(frozen=True, slots=True)
class Evaluation:
    value: TruthValue
    missing_facts: frozenset[str]
    trace: EvaluationTrace


def _dominated(trace: EvaluationTrace) -> EvaluationTrace:
    """Copy an entire trace subtree while marking every node non-consequential."""

    return replace(
        trace,
        affected_result=False,
        children=tuple(_dominated(child) for child in trace.children),
    )


def _compose(op: str, children: tuple[EvaluationTrace, ...]) -> EvaluationTrace:
    values = tuple(child.result for child in children)
    if op == "all":
        if TruthValue.FALSE in values:
            result = TruthValue.FALSE
            influential = TruthValue.FALSE
        elif all(value is TruthValue.TRUE for value in values):
            result = TruthValue.TRUE
            influential = TruthValue.TRUE
        else:
            result = TruthValue.UNKNOWN
            influential = TruthValue.UNKNOWN
    else:
        if TruthValue.TRUE in values:
            result = TruthValue.TRUE
            influential = TruthValue.TRUE
        elif all(value is TruthValue.FALSE for value in values):
            result = TruthValue.FALSE
            influential = TruthValue.FALSE
        else:
            result = TruthValue.UNKNOWN
            influential = TruthValue.UNKNOWN

    composed_children = tuple(
        child if child.result is influential else _dominated(child) for child in children
    )
    missing = (
        frozenset().union(
            *(child.missing_facts for child in children if child.result is TruthValue.UNKNOWN)
        )
        if result is TruthValue.UNKNOWN
        else frozenset()
    )
    return EvaluationTrace(op, result, missing_facts=missing, children=composed_children)


def _evaluate_trace(
    predicate: Predicate, facts: Mapping[str, FactValue], submitted_keys: frozenset[str]
) -> EvaluationTrace:
    op = predicate.op
    if op in {"all", "any"}:
        # Deliberately exhaustive and in authored order: never short-circuit.
        children = tuple(
            _evaluate_trace(child, facts, submitted_keys) for child in predicate.children
        )
        return _compose(op, children)
    if op == "not":
        child = _evaluate_trace(predicate.children[0], facts, submitted_keys)
        result = {
            TruthValue.TRUE: TruthValue.FALSE,
            TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN,
        }[child.result]
        missing = child.missing_facts if result is TruthValue.UNKNOWN else frozenset()
        return EvaluationTrace(op, result, missing_facts=missing, children=(child,))

    # These attributes are guaranteed by successful rule validation.
    assert predicate.fact is not None
    fact = predicate.fact
    present = fact in facts
    submitted = fact in submitted_keys
    if op == "exists":
        result = TruthValue.TRUE if submitted else TruthValue.FALSE
        return EvaluationTrace(
            op,
            result,
            fact_key=fact,
            fact_present=present,
            submitted=submitted,
        )

    expected = predicate.value
    if not present:
        missing = frozenset({fact})
        return EvaluationTrace(
            op,
            TruthValue.UNKNOWN,
            fact_key=fact,
            fact_present=False,
            submitted=submitted,
            expected_value=expected,
            missing_facts=missing,
        )

    actual = facts[fact]
    if op == "eq":
        matched = actual == expected
    elif op == "in":
        assert isinstance(expected, tuple)
        matched = actual in expected
    elif op == "lt":
        matched = actual < expected  # type: ignore[operator]
    elif op == "lte":
        matched = actual <= expected  # type: ignore[operator]
    elif op == "gt":
        matched = actual > expected  # type: ignore[operator]
    else:
        assert op == "gte"
        matched = actual >= expected  # type: ignore[operator]
    return EvaluationTrace(
        op,
        TruthValue.TRUE if matched else TruthValue.FALSE,
        fact_key=fact,
        fact_present=True,
        submitted=submitted,
        actual_value=actual,
        expected_value=expected,
    )


def evaluate(
    predicate: Predicate,
    facts: Mapping[str, FactValue],
    *,
    submitted_keys: frozenset[str],
) -> Evaluation:
    """Evaluate validated typed input using exhaustive Strong Kleene semantics.

    ``submitted_keys`` is mandatory and must be captured from validated source Facts
    before derived Facts are added to the evaluation mapping.  Invalid Facts and malformed
    rules must be reported by their validators and must never be passed here or represented
    as truth values.
    """

    trace = _evaluate_trace(predicate, facts, submitted_keys)
    return Evaluation(trace.result, trace.missing_facts, trace)
