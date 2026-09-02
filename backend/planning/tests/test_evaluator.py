from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from types import MappingProxyType
from unittest.mock import Mock

from planning import (
    Evaluation,
    EvaluationTrace,
    TruthValue,
    evaluate,
    validate_rule_v1,
    validate_submitted_facts,
)
from planning.facts import FactValue
from planning.rules import Predicate


def predicate(raw: object) -> Predicate:
    result = validate_rule_v1(raw)
    if result.diagnostics or result.predicate is None:
        raise AssertionError(result.diagnostics)
    return result.predicate


def run(raw_rule: object, raw_facts: dict[str, object]) -> Evaluation:
    fact_result = validate_submitted_facts(raw_facts)
    rule_result = validate_rule_v1(raw_rule)
    if fact_result.diagnostics or rule_result.diagnostics:
        raise AssertionError((fact_result.diagnostics, rule_result.diagnostics))
    assert fact_result.facts is not None and rule_result.predicate is not None
    return evaluate(
        rule_result.predicate,
        fact_result.facts,
        submitted_keys=frozenset(fact_result.facts),
    )


def truth_rule(value: TruthValue) -> dict[str, object]:
    if value is TruthValue.UNKNOWN:
        return {"op": "eq", "fact": "is_student", "value": True}
    return {
        "op": "eq",
        "fact": "citizenship",
        "value": "egyptian" if value is TruthValue.TRUE else "other",
    }


TRUTHS = (TruthValue.TRUE, TruthValue.FALSE, TruthValue.UNKNOWN)


class StrongKleeneTests(unittest.TestCase):
    def _binary(self, op: str, left: TruthValue, right: TruthValue) -> Evaluation:
        raw = {"op": op, "children": [truth_rule(left), truth_rule(right)]}
        return run(raw, {"citizenship": "egyptian"})

    def test_all_exhaustive_ordered_truth_table(self) -> None:
        expected = {
            (left, right): (
                TruthValue.FALSE
                if TruthValue.FALSE in (left, right)
                else TruthValue.TRUE
                if left is right is TruthValue.TRUE
                else TruthValue.UNKNOWN
            )
            for left in TRUTHS
            for right in TRUTHS
        }
        for pair, value in expected.items():
            with self.subTest(pair=pair):
                evaluation = self._binary("all", *pair)
                self.assertIs(evaluation.value, value)
                self.assertEqual(len(evaluation.trace.children), 2)

    def test_any_exhaustive_ordered_truth_table(self) -> None:
        expected = {
            (left, right): (
                TruthValue.TRUE
                if TruthValue.TRUE in (left, right)
                else TruthValue.FALSE
                if left is right is TruthValue.FALSE
                else TruthValue.UNKNOWN
            )
            for left in TRUTHS
            for right in TRUTHS
        }
        for pair, value in expected.items():
            with self.subTest(pair=pair):
                evaluation = self._binary("any", *pair)
                self.assertIs(evaluation.value, value)
                self.assertEqual(len(evaluation.trace.children), 2)

    def test_not_all_three_values(self) -> None:
        expected = {
            TruthValue.TRUE: TruthValue.FALSE,
            TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN,
        }
        for source, result in expected.items():
            with self.subTest(source=source):
                evaluation = run(
                    {"op": "not", "children": [truth_rule(source)]},
                    {"citizenship": "egyptian"},
                )
                self.assertIs(evaluation.value, result)
                self.assertTrue(evaluation.trace.children[0].affected_result)

    def test_nary_nested_and_duplicate_missing_union(self) -> None:
        raw = {
            "op": "all",
            "children": [
                truth_rule(TruthValue.TRUE),
                {"op": "not", "children": [truth_rule(TruthValue.UNKNOWN)]},
                truth_rule(TruthValue.UNKNOWN),
            ],
        }
        evaluation = run(raw, {"citizenship": "egyptian"})
        self.assertIs(evaluation.value, TruthValue.UNKNOWN)
        self.assertEqual(evaluation.missing_facts, frozenset({"is_student"}))
        self.assertEqual([child.op for child in evaluation.trace.children], ["eq", "not", "eq"])


class LeafEvaluationTests(unittest.TestCase):
    def test_eq_and_in_every_fact_kind(self) -> None:
        cases = (
            ("is_student", True, [False, True]),
            ("citizenship", "egyptian", ["other", "egyptian"]),
            ("other_living_sons_of_father_count", 2, [1, 2]),
            ("birth_date", date(2020, 2, 29), [{"$date": "2020-01-01"}, {"$date": "2020-02-29"}]),
            ("residence_district", "Dokki", ["Cairo", "Dokki"]),
        )
        for fact, actual, operands in cases:
            encoded = {"$date": actual.isoformat()} if type(actual) is date else actual
            for op, value in (("eq", encoded), ("in", operands)):
                with self.subTest(fact=fact, op=op):
                    evaluation = run({"op": op, "fact": fact, "value": value}, {fact: actual})
                    self.assertIs(evaluation.value, TruthValue.TRUE)
                    self.assertEqual(evaluation.trace.actual_value, actual)
                    self.assertTrue(evaluation.trace.fact_present)
                    self.assertTrue(evaluation.trace.submitted)

    def test_every_ordering_operator_for_integer_and_calendar_date_boundaries(self) -> None:
        cases = (
            ("other_living_sons_of_father_count", 2, 2),
            ("birth_date", date(2024, 1, 2), {"$date": "2024-01-02"}),
        )
        expected = {"lt": False, "lte": True, "gt": False, "gte": True}
        for fact, actual, operand in cases:
            for op, matched in expected.items():
                with self.subTest(fact=fact, op=op):
                    evaluation = run({"op": op, "fact": fact, "value": operand}, {fact: actual})
                    self.assertIs(
                        evaluation.value, TruthValue.TRUE if matched else TruthValue.FALSE
                    )
                    if fact == "birth_date":
                        self.assertIs(type(evaluation.trace.actual_value), date)
                        self.assertIs(type(evaluation.trace.expected_value), date)

    def test_missing_fact_for_every_comparison_operator(self) -> None:
        values: dict[str, object] = {
            "eq": 1,
            "in": [1, 2],
            "lt": 1,
            "lte": 1,
            "gt": 1,
            "gte": 1,
        }
        fact = "other_living_sons_of_father_count"
        for op, value in values.items():
            with self.subTest(op=op):
                evaluation = run({"op": op, "fact": fact, "value": value}, {})
                self.assertIs(evaluation.value, TruthValue.UNKNOWN)
                self.assertEqual(evaluation.missing_facts, frozenset({fact}))
                self.assertEqual(evaluation.trace.fact_key, fact)
                self.assertFalse(evaluation.trace.fact_present)
                self.assertFalse(evaluation.trace.submitted)
                self.assertIsNone(evaluation.trace.actual_value)

    def test_exists_uses_submission_not_truthiness_or_evaluation_mapping(self) -> None:
        for submitted_value in (False,):
            evaluation = run(
                {"op": "exists", "fact": "is_student"}, {"is_student": submitted_value}
            )
            self.assertIs(evaluation.value, TruthValue.TRUE)
        falsey_cases: tuple[tuple[str, object], ...] = (
            ("other_living_sons_of_father_count", 0),
            ("residence_district", ""),
        )
        for fact, falsey_value in falsey_cases:
            evaluation = run({"op": "exists", "fact": fact}, {fact: falsey_value})
            self.assertIs(evaluation.value, TruthValue.TRUE)

        rule = predicate({"op": "exists", "fact": "is_student"})
        evaluation_facts: dict[str, FactValue] = {
            "is_student": False,
            "card_expired_before_evaluation_date": True,
        }
        evaluation = evaluate(rule, MappingProxyType(evaluation_facts), submitted_keys=frozenset())
        self.assertIs(evaluation.value, TruthValue.FALSE)
        self.assertTrue(evaluation.trace.fact_present)
        self.assertFalse(evaluation.trace.submitted)
        self.assertEqual(evaluation.missing_facts, frozenset())

        unrelated = predicate({"op": "exists", "fact": "birth_date"})
        evaluation = evaluate(
            unrelated, MappingProxyType(evaluation_facts), submitted_keys=frozenset()
        )
        self.assertIs(evaluation.value, TruthValue.FALSE)
        self.assertFalse(evaluation.trace.fact_present)

    def test_derived_comparison_records_not_submitted(self) -> None:
        rule = predicate({"op": "eq", "fact": "age_years_on_evaluation_date", "value": 18})
        facts: dict[str, FactValue] = {"age_years_on_evaluation_date": 18}
        evaluation = evaluate(rule, MappingProxyType(facts), submitted_keys=frozenset())
        self.assertIs(evaluation.value, TruthValue.TRUE)
        self.assertTrue(evaluation.trace.fact_present)
        self.assertFalse(evaluation.trace.submitted)

    def test_exists_for_derived_fact_is_rejected_before_evaluation(self) -> None:
        result = validate_rule_v1({"op": "exists", "fact": "age_years_on_evaluation_date"})
        self.assertIsNone(result.predicate)
        self.assertTrue(result.diagnostics)


class TraceTests(unittest.TestCase):
    def test_all_dominance_in_both_orders_and_complete_evaluation(self) -> None:
        for values in (
            (TruthValue.FALSE, TruthValue.UNKNOWN),
            (TruthValue.UNKNOWN, TruthValue.FALSE),
        ):
            evaluation = StrongKleeneTests()._binary("all", *values)
            self.assertIs(evaluation.value, TruthValue.FALSE)
            self.assertEqual(evaluation.missing_facts, frozenset())
            self.assertEqual(len(evaluation.trace.children), 2)
            unknown = next(c for c in evaluation.trace.children if c.result is TruthValue.UNKNOWN)
            self.assertFalse(unknown.affected_result)
            self.assertEqual(unknown.missing_facts, frozenset({"is_student"}))

    def test_any_dominance_in_both_orders(self) -> None:
        for values in (
            (TruthValue.TRUE, TruthValue.UNKNOWN),
            (TruthValue.UNKNOWN, TruthValue.TRUE),
        ):
            evaluation = StrongKleeneTests()._binary("any", *values)
            self.assertIs(evaluation.value, TruthValue.TRUE)
            self.assertEqual(evaluation.missing_facts, frozenset())
            unknown = next(c for c in evaluation.trace.children if c.result is TruthValue.UNKNOWN)
            self.assertFalse(unknown.affected_result)

    def test_nested_dominated_subtree_recursively_clears_every_node(self) -> None:
        raw = {
            "op": "all",
            "children": [
                truth_rule(TruthValue.FALSE),
                {
                    "op": "any",
                    "children": [
                        truth_rule(TruthValue.UNKNOWN),
                        {
                            "op": "not",
                            "children": [
                                {
                                    "op": "eq",
                                    "fact": "birth_date",
                                    "value": {"$date": "2000-01-01"},
                                }
                            ],
                        },
                    ],
                },
            ],
        }
        evaluation = run(raw, {"citizenship": "egyptian"})
        subtree = evaluation.trace.children[1]
        nodes = [subtree, *subtree.children, *subtree.children[1].children]
        self.assertTrue(all(not node.affected_result for node in nodes))
        self.assertEqual(subtree.result, TruthValue.UNKNOWN)
        self.assertEqual(subtree.missing_facts, frozenset({"is_student", "birth_date"}))
        self.assertEqual(subtree.children[0].missing_facts, frozenset({"is_student"}))
        self.assertEqual(subtree.children[1].children[0].expected_value, date(2000, 1, 1))

    def test_consequential_unknown_reaches_root_and_authored_order_is_stable(self) -> None:
        raw = {
            "op": "all",
            "children": [
                truth_rule(TruthValue.TRUE),
                {
                    "op": "any",
                    "children": [
                        truth_rule(TruthValue.FALSE),
                        truth_rule(TruthValue.UNKNOWN),
                    ],
                },
            ],
        }
        first = run(raw, {"citizenship": "egyptian"})
        second = run(raw, {"citizenship": "egyptian"})
        self.assertEqual(first, second)
        self.assertEqual(first.missing_facts, frozenset({"is_student"}))
        nested = first.trace.children[1]
        self.assertTrue(nested.affected_result)
        self.assertTrue(nested.children[1].affected_result)
        self.assertEqual(
            [c.result for c in nested.children],
            [TruthValue.FALSE, TruthValue.UNKNOWN],
        )

    def test_domain_objects_and_collections_are_immutable(self) -> None:
        evaluation = run(truth_rule(TruthValue.UNKNOWN), {})
        with self.assertRaises(FrozenInstanceError):
            evaluation.value = TruthValue.TRUE  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            evaluation.trace.result = TruthValue.TRUE  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            evaluation.missing_facts.add("x")  # type: ignore[attr-defined]
        with self.assertRaises(TypeError):
            evaluation.trace.children[0] = evaluation.trace  # type: ignore[index]
        self.assertIsInstance(evaluation.trace, EvaluationTrace)


class ValidationBoundaryTests(unittest.TestCase):
    @staticmethod
    def gated(raw_rule: object, raw_facts: dict[str, object], evaluator: Mock) -> object:
        facts = validate_submitted_facts(raw_facts)
        rule = validate_rule_v1(raw_rule)
        if facts.diagnostics or rule.diagnostics:
            return facts.diagnostics + rule.diagnostics
        assert facts.facts is not None and rule.predicate is not None
        return evaluator(rule.predicate, facts.facts, submitted_keys=frozenset(facts.facts))

    def test_malformed_rules_never_reach_evaluation_or_truth_domain(self) -> None:
        invalid = (
            None,
            {"op": "unsupported"},
            {"op": "all", "children": [None]},
            {"op": "eq", "fact": "is_student", "value": 1},
        )
        for raw in invalid:
            with self.subTest(raw=raw):
                evaluator = Mock()
                diagnostics = self.gated(raw, {}, evaluator)
                self.assertTrue(diagnostics)
                evaluator.assert_not_called()
                result = validate_rule_v1(raw)
                self.assertIsNone(result.predicate)
                self.assertIsInstance(diagnostics, tuple)
                assert isinstance(diagnostics, tuple)
                self.assertFalse(
                    any(isinstance(item, (Evaluation, TruthValue)) for item in diagnostics)
                )

    def test_invalid_facts_never_reach_evaluation(self) -> None:
        invalid: tuple[dict[str, object], ...] = (
            {"is_student": None},
            {"other_living_sons_of_father_count": True},
            {"other_living_sons_of_father_count": "1"},
            {"birth_date": "2020-01-01"},
            {"citizenship": "Egyptian"},
            {"birth_date": datetime(2020, 1, 1)},
            {"unsupported": 1},
            {"age_years_on_evaluation_date": 1},
        )
        for facts in invalid:
            with self.subTest(facts=facts):
                evaluator = Mock()
                diagnostics = self.gated(truth_rule(TruthValue.TRUE), facts, evaluator)
                self.assertTrue(diagnostics)
                evaluator.assert_not_called()
                self.assertIsNone(validate_submitted_facts(facts).facts)

    def test_successful_validated_path_calls_evaluator(self) -> None:
        sentinel = object()
        evaluator = Mock(return_value=sentinel)
        result = self.gated(truth_rule(TruthValue.TRUE), {"citizenship": "egyptian"}, evaluator)
        self.assertIs(result, sentinel)
        evaluator.assert_called_once()
