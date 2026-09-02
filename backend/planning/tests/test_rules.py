from __future__ import annotations

import unittest
from datetime import date, datetime
from typing import Any

from planning import (
    MAX_IN_OPERANDS,
    MAX_RULE_NODES,
    Predicate,
    ValidationDiagnostic,
    validate_rule_v1,
)


def eq(fact: str = "is_student", value: object = True) -> dict[str, object]:
    return {"op": "eq", "fact": fact, "value": value}


class SuccessfulRuleTests(unittest.TestCase):
    def assert_valid(self, raw: object) -> Predicate:
        result = validate_rule_v1(raw)
        self.assertEqual(result.diagnostics, ())
        self.assertTrue(result.is_valid)
        assert result.predicate is not None
        return result.predicate

    def test_eq_decodes_every_fact_kind(self) -> None:
        cases = [
            ("is_student", True, True),
            ("citizenship", "egyptian", "egyptian"),
            ("other_living_sons_of_father_count", 0, 0),
            ("birth_date", {"$date": "2000-02-29"}, date(2000, 2, 29)),
            ("residence_district", "Dokki", "Dokki"),
        ]
        for fact, raw, expected in cases:
            with self.subTest(fact=fact):
                self.assertEqual(self.assert_valid(eq(fact, raw)).value, expected)

    def test_in_decodes_every_fact_kind_to_tuple(self) -> None:
        cases = [
            ("is_student", [True, False]),
            ("citizenship", ["egyptian", "other"]),
            ("other_living_sons_of_father_count", [0, 2]),
            ("birth_date", [{"$date": "2000-01-01"}]),
            ("residence_district", ["A", "B"]),
        ]
        for fact, values in cases:
            predicate = self.assert_valid({"op": "in", "fact": fact, "value": values})
            self.assertIs(type(predicate.value), tuple)

    def test_each_ordering_operator_accepts_integer_and_date(self) -> None:
        for op in ("lt", "lte", "gt", "gte"):
            for fact, value in (
                ("other_living_sons_of_father_count", 1),
                ("birth_date", {"$date": "2020-01-01"}),
            ):
                with self.subTest(op=op, fact=fact):
                    self.assertEqual(
                        self.assert_valid({"op": op, "fact": fact, "value": value}).op,
                        op,
                    )

    def test_exists_and_boolean_operators(self) -> None:
        self.assert_valid({"op": "exists", "fact": "birth_date"})
        for op in ("all", "any"):
            predicate = self.assert_valid({"op": op, "children": [eq()]})
            self.assertIs(type(predicate.children), tuple)
        self.assert_valid({"op": "not", "children": [eq()]})

    def test_nested_tree_is_deeply_immutable(self) -> None:
        predicate = self.assert_valid(
            {
                "op": "all",
                "children": [
                    {"op": "not", "children": [eq()]},
                    eq("birth_date", {"$date": "2024-01-02"}),
                ],
            }
        )
        self.assertIs(type(predicate.children), tuple)
        self.assertIs(type(predicate.children[0].children), tuple)
        self.assertEqual(predicate.children[1].value, date(2024, 1, 2))


class RejectedRuleTests(unittest.TestCase):
    def assert_codes(self, raw: object, *codes: str) -> tuple[ValidationDiagnostic, ...]:
        result = validate_rule_v1(raw)
        self.assertEqual(result.diagnostic_codes, codes)
        self.assertIsNone(result.predicate)
        self.assertFalse(result.is_valid)
        return result.diagnostics

    def test_operator_failures(self) -> None:
        diagnostic = self.assert_codes({"op": "ref", "name": "x"}, "unsupported_rule_operator:ref")[
            0
        ]
        self.assertEqual(diagnostic.path, ("rule", "op"))
        for raw, path in (
            (None, ("rule",)),
            ([], ("rule",)),
            ({}, ("rule", "op")),
            ({"op": None}, ("rule", "op")),
            ({"op": 1}, ("rule", "op")),
        ):
            diagnostics = self.assert_codes(raw, "malformed_rule:<unknown>")
            self.assertEqual(diagnostics[0].path, path)

    def test_unknown_and_forbidden_fields_are_lexical(self) -> None:
        diagnostics = self.assert_codes(
            {"op": "eq", "fact": "is_student", "value": True, "z": 1, "a": 2},
            "malformed_rule:eq",
            "malformed_rule:eq",
        )
        self.assertEqual([item.path for item in diagnostics], [("rule", "a"), ("rule", "z")])
        cases = [
            ({"op": "exists", "fact": "is_student", "value": True}, "malformed_rule:exists"),
            ({"op": "all", "children": [eq()], "fact": "is_student"}, "malformed_rule:all"),
            ({"op": "any", "children": [eq()], "value": True}, "malformed_rule:any"),
            ({"op": "not", "children": [eq()], "fact": "x"}, "malformed_rule:not"),
        ]
        for raw, code in cases:
            with self.subTest(raw=raw):
                self.assertIn(code, self.assert_codes(raw, code)[0].code)

    def test_fact_reference_failures(self) -> None:
        cases = [
            ({"op": "eq", "value": True}, "missing_rule_fact:eq", ("rule", "fact")),
            ({"op": "eq", "fact": None, "value": True}, "malformed_rule:eq", ("rule", "fact")),
            ({"op": "eq", "fact": 3, "value": True}, "malformed_rule:eq", ("rule", "fact")),
            (
                {"op": "eq", "fact": "no_such_fact", "value": True},
                "unsupported_rule_fact:no_such_fact",
                ("rule", "fact"),
            ),
            (
                {"op": "exists", "fact": "only_son_candidate"},
                "exists_requires_source_fact:only_son_candidate",
                ("rule", "fact"),
            ),
        ]
        for raw, code, path in cases:
            with self.subTest(code=code):
                self.assertEqual(self.assert_codes(raw, code)[0].path, path)

    def test_scalar_operands_reject_missing_null_and_wrong_types(self) -> None:
        for raw in (
            {"op": "eq", "fact": "is_student"},
            eq(value=None),
            eq(value=1),
            eq("other_living_sons_of_father_count", True),
            eq("other_living_sons_of_father_count", -1),
            eq("citizenship", "Egyptian"),
        ):
            self.assert_codes(raw, f"invalid_rule_operand:{raw['fact']}")

    def test_in_shape_size_and_each_invalid_entry(self) -> None:
        invalid_values: tuple[object, ...] = ([], "yes", (True,), {True}, iter([True]))
        for value in invalid_values:
            self.assert_codes(
                {"op": "in", "fact": "is_student", "value": value},
                "invalid_rule_operand:is_student",
            )
        diagnostics = self.assert_codes(
            {"op": "in", "fact": "is_student", "value": [1, True, None]},
            "invalid_rule_operand:is_student",
            "invalid_rule_operand:is_student",
        )
        self.assertEqual(
            [item.path for item in diagnostics],
            [("rule", "value", 0), ("rule", "value", 2)],
        )
        diagnostics = self.assert_codes(
            {"op": "in", "fact": "is_student", "value": [True] * (MAX_IN_OPERANDS + 1)},
            "invalid_rule_operand:is_student",
        )
        self.assertEqual(diagnostics[0].path, ("rule", "value"))

    def test_ordering_restrictions_and_invalid_operand_are_independent(self) -> None:
        for fact, value in (
            ("is_student", 1),
            ("citizenship", 1),
            ("residence_district", 1),
        ):
            diagnostics = self.assert_codes(
                {"op": "lt", "fact": fact, "value": value},
                f"ordering_not_supported_for_fact:{fact}",
                f"invalid_rule_operand:{fact}",
            )
            self.assertEqual(diagnostics[0].path, ("rule", "fact"))
            self.assertEqual(diagnostics[1].path, ("rule", "value"))

    def test_boolean_collection_and_arity_failures(self) -> None:
        for op in ("all", "any"):
            self.assert_codes({"op": op, "children": []}, f"empty_boolean_composition:{op}")
            for children in (None, (), eq()):
                self.assert_codes({"op": op, "children": children}, f"malformed_rule:{op}")
        invalid_not_children: tuple[object, ...] = (None, [], [eq(), eq()])
        for invalid_children in invalid_not_children:
            self.assert_codes({"op": "not", "children": invalid_children}, "malformed_rule:not")

    def test_non_object_children_are_all_validated(self) -> None:
        diagnostics = self.assert_codes(
            {"op": "all", "children": [None, 1]},
            "malformed_rule:<unknown>",
            "malformed_rule:<unknown>",
        )
        self.assertEqual(
            [item.path for item in diagnostics],
            [("rule", "children", 0), ("rule", "children", 1)],
        )

    def test_date_literal_contract(self) -> None:
        invalid: list[object] = [
            date(2020, 1, 1),
            datetime(2020, 1, 1),
            "2020-01-01",
            "2020-01-01T00:00:00Z",
            {"$date": "2020-02-30"},
            {"$date": "2020-1-01"},
            {"$date": 1},
            {"$date": "2020-01-01", "extra": True},
            {"date": "2020-01-01"},
        ]
        for value in invalid:
            with self.subTest(value=value):
                self.assert_codes(eq("birth_date", value), "invalid_rule_operand:birth_date")
        self.assert_codes(
            eq("residence_district", {"$date": "2020-01-01"}),
            "invalid_rule_operand:residence_district",
        )

    def test_only_exact_json_containers_and_inert_values_are_accepted(self) -> None:
        class DictSubclass(dict[str, object]):
            pass

        class ListSubclass(list[object]):
            pass

        class MappingLike:
            def get(self, key: str) -> object:
                return None

        for raw in (DictSubclass(eq()), MappingLike(), lambda: None):
            self.assert_codes(raw, "malformed_rule:<unknown>")
        self.assert_codes({"op": "all", "children": ListSubclass([eq()])}, "malformed_rule:all")
        self.assert_codes(
            {"op": "in", "fact": "is_student", "value": ListSubclass([True])},
            "invalid_rule_operand:is_student",
        )

    def test_nested_diagnostic_order_paths_and_deduplication(self) -> None:
        raw = {
            "op": "all",
            "children": [
                {"op": "eq", "fact": "is_student", "value": 1, "z": 0},
                {"op": "eq", "fact": "is_student", "value": 1},
                {"op": "ref", "children": [eq()]},
            ],
        }
        diagnostics = self.assert_codes(
            raw,
            "malformed_rule:eq",
            "invalid_rule_operand:is_student",
            "invalid_rule_operand:is_student",
            "unsupported_rule_operator:ref",
        )
        self.assertEqual(
            [item.path for item in diagnostics],
            [
                ("rule", "children", 0, "z"),
                ("rule", "children", 0, "value"),
                ("rule", "children", 1, "value"),
                ("rule", "children", 2, "op"),
            ],
        )


class ResourceGuardTests(unittest.TestCase):
    def test_exact_node_limit_succeeds_and_next_node_fails_once(self) -> None:
        valid = {"op": "all", "children": [eq() for _ in range(MAX_RULE_NODES - 1)]}
        self.assertTrue(validate_rule_v1(valid).is_valid)
        oversized = {"op": "all", "children": [eq() for _ in range(MAX_RULE_NODES)]}
        result = validate_rule_v1(oversized)
        self.assertEqual(
            result.diagnostics,
            (ValidationDiagnostic("rule_too_large", ("rule",)),),
        )

    def test_hostile_deep_nesting_does_not_recurse(self) -> None:
        raw: dict[str, Any] = eq()
        for _ in range(1000):
            raw = {"op": "not", "children": [raw]}
        self.assertEqual(validate_rule_v1(raw).diagnostic_codes, ("rule_too_large",))
