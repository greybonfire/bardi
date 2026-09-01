from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import date, datetime

from planning import (
    FACT_DEFINITIONS,
    FactDefinition,
    ValidationDiagnostic,
    validate_submitted_facts,
)


class FactRegistryTests(unittest.TestCase):
    def test_registry_is_complete_and_roles_are_exact(self) -> None:
        self.assertEqual(len(FACT_DEFINITIONS), 39)
        self.assertEqual(
            {key for key, item in FACT_DEFINITIONS.items() if item.derived},
            {
                "age_years_on_evaluation_date",
                "card_expired_before_evaluation_date",
                "only_son_candidate",
                "renewal_deadline_date",
                "renewal_deadline_passed",
            },
        )
        self.assertEqual(set(FACT_DEFINITIONS), {item.key for item in FACT_DEFINITIONS.values()})

    def test_contract_objects_are_immutable(self) -> None:
        with self.assertRaises(TypeError):
            FACT_DEFINITIONS["new"] = FactDefinition("new", "string")  # type: ignore[index]
        definition = FACT_DEFINITIONS["citizenship"]
        self.assertIs(type(definition.enum_values), tuple)
        with self.assertRaises(FrozenInstanceError):
            definition.key = "changed"  # type: ignore[misc]
        diagnostic = ValidationDiagnostic("x", ("facts", "x"))
        with self.assertRaises(FrozenInstanceError):
            diagnostic.code = "y"  # type: ignore[misc]


class SubmittedFactValidationTests(unittest.TestCase):
    def test_accepts_every_kind_and_omission(self) -> None:
        values = {
            "is_student": True,
            "citizenship": "egyptian",
            "other_living_sons_of_father_count": 0,
            "birth_date": date(2000, 2, 29),
            "residence_district": "Dokki",
        }
        result = validate_submitted_facts(values)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.diagnostic_codes, ())
        self.assertEqual(result.facts, values)
        self.assertTrue(validate_submitted_facts({}).is_valid)
        with self.assertRaises(TypeError):
            assert result.facts is not None
            result.facts["is_student"] = False  # type: ignore[index]

    def test_rejects_null_and_prohibited_coercions(self) -> None:
        invalid = [
            ("is_student", None),
            ("is_student", 1),
            ("other_living_sons_of_father_count", True),
            ("other_living_sons_of_father_count", 1.0),
            ("other_living_sons_of_father_count", "1"),
            ("birth_date", datetime(2000, 1, 1)),
            ("birth_date", "2000-01-01"),
            ("residence_district", 1),
            ("citizenship", "Egyptian"),
            ("citizenship", "unknown"),
        ]
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                result = validate_submitted_facts({key: value})
                self.assertEqual(result.diagnostic_codes, (f"invalid_fact_value:{key}",))
                self.assertIsNone(result.facts)

    def test_all_constrained_integers_reject_negative_values(self) -> None:
        constrained = {
            key
            for key, item in FACT_DEFINITIONS.items()
            if item.kind == "integer" and item.minimum is not None and not item.derived
        }
        self.assertEqual(
            constrained,
            {
                "other_living_sons_of_father_count",
                "unmarried_sisters_requiring_support_count",
            },
        )
        for key in constrained:
            self.assertFalse(validate_submitted_facts({key: -1}).is_valid)

    def test_unknown_and_every_derived_fact_are_rejected(self) -> None:
        result = validate_submitted_facts({"zzz": 1})
        self.assertEqual(result.diagnostic_codes, ("unsupported_fact_key:zzz",))
        for key, definition in FACT_DEFINITIONS.items():
            if definition.derived:
                result = validate_submitted_facts({key: None})
                self.assertEqual(
                    result.diagnostic_codes,
                    (f"derived_fact_cannot_be_submitted:{key}",),
                )

    def test_diagnostics_are_lexical_and_have_exact_paths(self) -> None:
        result = validate_submitted_facts({"zzz": 1, "citizenship": None, "aaa": 1})
        self.assertEqual(
            result.diagnostics,
            (
                ValidationDiagnostic("unsupported_fact_key:aaa", ("facts", "aaa")),
                ValidationDiagnostic("invalid_fact_value:citizenship", ("facts", "citizenship")),
                ValidationDiagnostic("unsupported_fact_key:zzz", ("facts", "zzz")),
            ),
        )

    def test_input_is_not_modified_or_retained(self) -> None:
        submitted: dict[str, object] = {"is_student": True}
        result = validate_submitted_facts(submitted)
        submitted["is_student"] = False
        submitted["citizenship"] = "other"
        self.assertEqual(result.facts, {"is_student": True})
