from __future__ import annotations

from collections.abc import Mapping

from .contracts import Predicate


class MissingFactError(KeyError):
    """Known-case evaluator cannot decide a predicate because a Fact is absent."""


def evaluate(predicate: Predicate | None, facts: Mapping[str, object]) -> bool:
    """Evaluate only the complete-input predicate subset used before issue #7."""
    if predicate is None:
        return True

    op = predicate.op
    if op in {"eq", "in", "lt", "lte", "gt", "gte"}:
        if predicate.fact is None:
            raise ValueError(f"{op} predicate requires a fact")
        if predicate.fact not in facts:
            raise MissingFactError(predicate.fact)
        actual = facts[predicate.fact]
        expected = predicate.value
        if op == "eq":
            return actual == expected
        if op == "in":
            return actual in expected  # type: ignore[operator]
        if op == "lt":
            return actual < expected  # type: ignore[operator]
        if op == "lte":
            return actual <= expected  # type: ignore[operator]
        if op == "gt":
            return actual > expected  # type: ignore[operator]
        return actual >= expected  # type: ignore[operator]

    if op == "all":
        return all(evaluate(child, facts) for child in predicate.children)
    if op == "any":
        return any(evaluate(child, facts) for child in predicate.children)
    if op == "not":
        if len(predicate.children) != 1:
            raise ValueError("not predicate requires exactly one child")
        return not evaluate(predicate.children[0], facts)

    raise ValueError(f"unsupported known-case predicate operator: {op}")


def eq(fact: str, value: object) -> Predicate:
    return Predicate("eq", fact=fact, value=value)


def one_of(fact: str, values: tuple[object, ...]) -> Predicate:
    return Predicate("in", fact=fact, value=values)


def lt(fact: str, value: object) -> Predicate:
    return Predicate("lt", fact=fact, value=value)


def gt(fact: str, value: object) -> Predicate:
    return Predicate("gt", fact=fact, value=value)


def gte(fact: str, value: object) -> Predicate:
    return Predicate("gte", fact=fact, value=value)


def all_of(*children: Predicate) -> Predicate:
    return Predicate("all", children=tuple(children))


def any_of(*children: Predicate) -> Predicate:
    return Predicate("any", children=tuple(children))


def negate(child: Predicate) -> Predicate:
    return Predicate("not", children=(child,))
