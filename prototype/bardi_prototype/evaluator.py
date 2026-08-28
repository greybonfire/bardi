from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum

from .contracts import FactDefinition, Predicate
from .facts import FACT_DEFINITIONS, value_matches_definition

MAX_RULE_NODES = 128
LEAF_OPERATORS = frozenset(("eq", "in", "lt", "lte", "gt", "gte", "exists"))
BOOLEAN_OPERATORS = frozenset(("all", "any", "not"))
SUPPORTED_OPERATORS = LEAF_OPERATORS | BOOLEAN_OPERATORS


class TruthValue(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EvaluationTrace:
    """Editor-facing trace for one predicate node.

    Trace objects are ephemeral prototype diagnostics. Public planning results do
    not contain them and the prototype does not persist them.
    """

    op: str
    result: TruthValue
    fact_key: str | None = None
    fact_present: bool | None = None
    submitted: bool | None = None
    actual_value: object | None = None
    expected_value: object | None = None
    missing_facts: frozenset[str] = frozenset()
    affected_result: bool = True
    children: tuple["EvaluationTrace", ...] = ()


@dataclass(frozen=True)
class Evaluation:
    value: TruthValue
    missing_facts: frozenset[str] = frozenset()
    trace: EvaluationTrace | None = None


@dataclass(frozen=True)
class RuleEvaluationRecord:
    """One named rule evaluation captured by the scenario inspector."""

    context: str
    value: TruthValue
    missing_facts: frozenset[str]
    consequential_to_planning: bool
    trace: EvaluationTrace


def _literal_valid(definition: FactDefinition, value: object) -> bool:
    return value_matches_definition(definition, value)


def validate_predicate(
    predicate: Predicate | None,
    fact_definitions: Mapping[str, FactDefinition] = FACT_DEFINITIONS,
    *,
    max_nodes: int = MAX_RULE_NODES,
) -> tuple[str, ...]:
    """Validate the fixture-proven rule AST without executing it."""
    if predicate is None:
        return ()

    diagnostics: list[str] = []
    node_count = 0

    def add(code: str) -> None:
        if code not in diagnostics:
            diagnostics.append(code)

    def visit(node: Predicate) -> None:
        nonlocal node_count
        node_count += 1
        if node_count > max_nodes:
            add("rule_too_large")
            return

        op = node.op
        if op not in SUPPORTED_OPERATORS:
            add(f"unsupported_rule_operator:{op}")
            return

        if op in {"all", "any"}:
            if node.fact is not None or node.value is not None:
                add(f"malformed_rule:{op}")
            if not node.children:
                add(f"empty_boolean_composition:{op}")
                return
            for child in node.children:
                visit(child)
            return

        if op == "not":
            if node.fact is not None or node.value is not None or len(node.children) != 1:
                add("malformed_rule:not")
                return
            visit(node.children[0])
            return

        if node.children:
            add(f"malformed_rule:{op}")
        if node.fact is None:
            add(f"missing_rule_fact:{op}")
            return

        definition = fact_definitions.get(node.fact)
        if definition is None:
            add(f"unsupported_rule_fact:{node.fact}")
            return

        if op == "exists":
            if node.value is not None:
                add("malformed_rule:exists")
            if definition.derived:
                add(f"exists_requires_source_fact:{node.fact}")
            return

        if op in {"lt", "lte", "gt", "gte"} and definition.kind not in {"integer", "date"}:
            add(f"ordering_not_supported_for_fact:{node.fact}")

        if op == "in":
            if not isinstance(node.value, (tuple, list)) or not node.value:
                add(f"invalid_rule_operand:{node.fact}")
                return
            if any(not _literal_valid(definition, item) for item in node.value):
                add(f"invalid_rule_operand:{node.fact}")
            return

        if not _literal_valid(definition, node.value):
            add(f"invalid_rule_operand:{node.fact}")

    visit(predicate)
    return tuple(diagnostics)


def _clear_effect(trace: EvaluationTrace) -> EvaluationTrace:
    return replace(
        trace,
        affected_result=False,
        children=tuple(_clear_effect(child) for child in trace.children),
    )


def _compose_trace(
    *,
    op: str,
    value: TruthValue,
    missing_facts: frozenset[str],
    children: tuple[Evaluation, ...],
) -> EvaluationTrace:
    child_traces = tuple(child.trace for child in children)
    assert all(trace is not None for trace in child_traces)

    def affects(child: Evaluation) -> bool:
        if op == "not":
            return True
        if op == "all":
            if value is TruthValue.TRUE:
                return True
            if value is TruthValue.FALSE:
                return child.value is TruthValue.FALSE
            return child.value is TruthValue.UNKNOWN
        if op == "any":
            if value is TruthValue.FALSE:
                return True
            if value is TruthValue.TRUE:
                return child.value is TruthValue.TRUE
            return child.value is TruthValue.UNKNOWN
        return True

    traces = tuple(
        trace if affects(child) else _clear_effect(trace)
        for child, trace in zip(children, child_traces)
        if trace is not None
    )
    return EvaluationTrace(
        op=op,
        result=value,
        missing_facts=missing_facts,
        children=traces,
    )


def evaluate(
    predicate: Predicate | None,
    facts: Mapping[str, object],
    *,
    submitted_keys: frozenset[str] | None = None,
) -> Evaluation:
    """Evaluate a validated predicate with strong-Kleene three-valued logic.

    All pure child predicates are evaluated even when a sibling already
    determines the parent result. The trace then marks dominated branches as
    not affecting that result.
    """
    if predicate is None:
        trace = EvaluationTrace(op="always", result=TruthValue.TRUE)
        return Evaluation(TruthValue.TRUE, trace=trace)

    submitted = frozenset(facts) if submitted_keys is None else submitted_keys
    op = predicate.op

    if op == "exists":
        assert predicate.fact is not None
        fact_present = predicate.fact in facts
        was_submitted = predicate.fact in submitted
        value = TruthValue.TRUE if was_submitted else TruthValue.FALSE
        trace = EvaluationTrace(
            op=op,
            result=value,
            fact_key=predicate.fact,
            fact_present=fact_present,
            submitted=was_submitted,
            actual_value=facts.get(predicate.fact) if fact_present else None,
        )
        return Evaluation(value, trace=trace)

    if op in {"eq", "in", "lt", "lte", "gt", "gte"}:
        assert predicate.fact is not None
        fact_present = predicate.fact in facts
        was_submitted = predicate.fact in submitted
        if not fact_present:
            missing = frozenset((predicate.fact,))
            trace = EvaluationTrace(
                op=op,
                result=TruthValue.UNKNOWN,
                fact_key=predicate.fact,
                fact_present=False,
                submitted=was_submitted,
                expected_value=predicate.value,
                missing_facts=missing,
            )
            return Evaluation(TruthValue.UNKNOWN, missing, trace)

        actual = facts[predicate.fact]
        expected = predicate.value
        if op == "eq":
            matched = actual == expected
        elif op == "in":
            matched = actual in expected  # type: ignore[operator]
        elif op == "lt":
            matched = actual < expected  # type: ignore[operator]
        elif op == "lte":
            matched = actual <= expected  # type: ignore[operator]
        elif op == "gt":
            matched = actual > expected  # type: ignore[operator]
        else:
            matched = actual >= expected  # type: ignore[operator]
        value = TruthValue.TRUE if matched else TruthValue.FALSE
        trace = EvaluationTrace(
            op=op,
            result=value,
            fact_key=predicate.fact,
            fact_present=True,
            submitted=was_submitted,
            actual_value=actual,
            expected_value=expected,
        )
        return Evaluation(value, trace=trace)

    children = tuple(
        evaluate(child, facts, submitted_keys=submitted)
        for child in predicate.children
    )

    if op == "all":
        if any(child.value is TruthValue.FALSE for child in children):
            value = TruthValue.FALSE
            missing = frozenset()
        elif all(child.value is TruthValue.TRUE for child in children):
            value = TruthValue.TRUE
            missing = frozenset()
        else:
            value = TruthValue.UNKNOWN
            missing = frozenset().union(
                *(child.missing_facts for child in children if child.value is TruthValue.UNKNOWN)
            )
        return Evaluation(value, missing, _compose_trace(op=op, value=value, missing_facts=missing, children=children))

    if op == "any":
        if any(child.value is TruthValue.TRUE for child in children):
            value = TruthValue.TRUE
            missing = frozenset()
        elif all(child.value is TruthValue.FALSE for child in children):
            value = TruthValue.FALSE
            missing = frozenset()
        else:
            value = TruthValue.UNKNOWN
            missing = frozenset().union(
                *(child.missing_facts for child in children if child.value is TruthValue.UNKNOWN)
            )
        return Evaluation(value, missing, _compose_trace(op=op, value=value, missing_facts=missing, children=children))

    if op == "not":
        child = children[0]
        if child.value is TruthValue.UNKNOWN:
            value = TruthValue.UNKNOWN
            missing = child.missing_facts
        else:
            value = TruthValue.FALSE if child.value is TruthValue.TRUE else TruthValue.TRUE
            missing = frozenset()
        return Evaluation(value, missing, _compose_trace(op=op, value=value, missing_facts=missing, children=children))

    raise ValueError(f"predicate must be validated before evaluation: {op}")


def record_evaluation(
    context: str,
    evaluation: Evaluation,
    *,
    consequential_to_planning: bool,
) -> RuleEvaluationRecord:
    assert evaluation.trace is not None
    return RuleEvaluationRecord(
        context=context,
        value=evaluation.value,
        missing_facts=evaluation.missing_facts,
        consequential_to_planning=consequential_to_planning,
        trace=evaluation.trace,
    )


def eq(fact: str, value: object) -> Predicate:
    return Predicate("eq", fact=fact, value=value)


def one_of(fact: str, values: tuple[object, ...]) -> Predicate:
    return Predicate("in", fact=fact, value=values)


def lt(fact: str, value: object) -> Predicate:
    return Predicate("lt", fact=fact, value=value)


def lte(fact: str, value: object) -> Predicate:
    return Predicate("lte", fact=fact, value=value)


def gt(fact: str, value: object) -> Predicate:
    return Predicate("gt", fact=fact, value=value)


def gte(fact: str, value: object) -> Predicate:
    return Predicate("gte", fact=fact, value=value)


def exists(fact: str) -> Predicate:
    return Predicate("exists", fact=fact)


def all_of(*children: Predicate) -> Predicate:
    return Predicate("all", children=tuple(children))


def any_of(*children: Predicate) -> Predicate:
    return Predicate("any", children=tuple(children))


def negate(child: Predicate) -> Predicate:
    return Predicate("not", children=(child,))
