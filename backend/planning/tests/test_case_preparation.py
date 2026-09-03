from __future__ import annotations

import unittest
from datetime import date, datetime

from planning import (
    FACT_DEFINITIONS,
    CasePreparationConfigurationDefect,
    CasePreparationInvalid,
    CasePreparationSuccess,
    ContradictionSnapshot,
    FactDefinition,
    LocalizedText,
    Predicate,
    ServiceSnapshot,
    prepare_case,
)


def service(*contradictions: ContradictionSnapshot) -> ServiceSnapshot:
    return ServiceSnapshot(
        "service", LocalizedText("خدمة", "Service"), (), (), contradictions, True
    )


def definitions(*keys: str) -> dict[str, FactDefinition]:
    required = set(keys)
    dependencies = {
        "age_years_on_evaluation_date": {"birth_date"},
        "card_expired_before_evaluation_date": {"national_id_expiry_date"},
        "renewal_deadline_date": {"national_id_expiry_date"},
        "renewal_deadline_passed": {"national_id_expiry_date"},
        "only_son_candidate": {"father_alive", "other_living_sons_of_father_count"},
    }
    for key in keys:
        required.update(dependencies.get(key, set()))
    return {key: FACT_DEFINITIONS[key] for key in required}


class CasePreparationTests(unittest.TestCase):
    def successful(self, defs, facts, evaluation=date(2026, 9, 1)):  # type: ignore[no-untyped-def]
        outcome = prepare_case(defs, service(), facts, evaluation)
        self.assertIsInstance(outcome, CasePreparationSuccess)
        assert isinstance(outcome, CasePreparationSuccess)
        return outcome.prepared_facts

    def test_completed_year_boundaries_include_leap_birth_date(self) -> None:
        defs = definitions("age_years_on_evaluation_date")
        cases = (
            (date(2000, 9, 2), date(2026, 9, 1), 25),
            (date(2000, 9, 2), date(2026, 9, 2), 26),
            (date(2004, 2, 29), date(2025, 2, 28), 20),
            (date(2004, 2, 29), date(2025, 3, 1), 21),
        )
        for birth, evaluation, expected in cases:
            with self.subTest(birth=birth, evaluation=evaluation):
                prepared = self.successful(defs, {"birth_date": birth}, evaluation)
                self.assertEqual(prepared.values["age_years_on_evaluation_date"], expected)
                self.assertEqual(prepared.submitted_keys, frozenset({"birth_date"}))

    def test_calendar_month_clamping_and_strict_boundaries(self) -> None:
        defs = definitions(
            "card_expired_before_evaluation_date",
            "renewal_deadline_date",
            "renewal_deadline_passed",
        )
        april = self.successful(
            defs, {"national_id_expiry_date": date(2026, 1, 31)}, date(2026, 4, 30)
        )
        self.assertEqual(april.values["renewal_deadline_date"], date(2026, 4, 30))
        self.assertFalse(april.values["renewal_deadline_passed"])
        self.assertTrue(april.values["card_expired_before_evaluation_date"])
        february = self.successful(
            defs, {"national_id_expiry_date": date(2025, 11, 30)}, date(2026, 3, 1)
        )
        self.assertEqual(february.values["renewal_deadline_date"], date(2026, 2, 28))
        self.assertTrue(february.values["renewal_deadline_passed"])
        equal_expiry = self.successful(defs, {"national_id_expiry_date": date(2026, 9, 1)})
        self.assertFalse(equal_expiry.values["card_expired_before_evaluation_date"])

    def test_only_son_and_missing_dependencies(self) -> None:
        defs = definitions("only_son_candidate")
        for alive, count, expected in (
            (True, 0, True),
            (True, 1, False),
            (False, 0, False),
            (False, 2, False),
        ):
            prepared = self.successful(
                defs, {"father_alive": alive, "other_living_sons_of_father_count": count}
            )
            self.assertIs(prepared.values["only_son_candidate"], expected)
        missing = self.successful(defs, {"father_alive": True})
        self.assertEqual(
            missing.missing_source_dependencies["only_son_candidate"],
            frozenset({"other_living_sons_of_father_count"}),
        )
        self.assertNotIn("only_son_candidate", missing.values)

    def test_input_is_copied_and_calls_are_deterministic(self) -> None:
        defs = definitions("age_years_on_evaluation_date")
        facts: dict[str, object] = {"birth_date": date(2000, 1, 1)}
        first = prepare_case(defs, service(), facts, date(2026, 1, 1))
        second = prepare_case(defs, service(), facts, date(2026, 1, 1))
        self.assertEqual(first, second)
        self.assertEqual(facts, {"birth_date": date(2000, 1, 1)})

    def test_invalid_dates_and_derived_submission_are_not_coerced(self) -> None:
        defs = definitions("age_years_on_evaluation_date")
        for value in ("2000-01-01", datetime(2000, 1, 1), None):
            with self.subTest(value=value):
                self.assertIsInstance(
                    prepare_case(defs, service(), {"birth_date": value}, date(2026, 1, 1)),
                    CasePreparationInvalid,
                )
        future = prepare_case(defs, service(), {"birth_date": date(2027, 1, 1)}, date(2026, 1, 1))
        self.assertIsInstance(future, CasePreparationInvalid)
        submitted = prepare_case(
            defs, service(), {"age_years_on_evaluation_date": 20}, date(2026, 1, 1)
        )
        self.assertIsInstance(submitted, CasePreparationInvalid)
        overflow = prepare_case(
            definitions("renewal_deadline_date"),
            service(),
            {"national_id_expiry_date": date.max},
            date.max,
        )
        self.assertIsInstance(overflow, CasePreparationInvalid)

    def test_unsupported_derived_definition_is_configuration_defect(self) -> None:
        defs = {"editor_formula": FactDefinition("editor_formula", "boolean", derived=True)}
        self.assertIsInstance(
            prepare_case(defs, service(), {}, date(2026, 1, 1)),
            CasePreparationConfigurationDefect,
        )

    def test_contradictions_reject_only_true_and_redact_diagnostics(self) -> None:
        defs = {
            "father_alive": FACT_DEFINITIONS["father_alive"],
            "is_student": FACT_DEFINITIONS["is_student"],
        }
        condition = Predicate(
            "all",
            children=(
                Predicate("eq", "father_alive", True),
                Predicate("eq", "is_student", True),
            ),
        )
        contradiction = ContradictionSnapshot(
            "secret-id", condition, ("is_student", "father_alive")
        )
        true = prepare_case(
            defs,
            service(contradiction),
            {"father_alive": True, "is_student": True},
            date(2026, 1, 1),
        )
        self.assertIsInstance(true, CasePreparationInvalid)
        assert isinstance(true, CasePreparationInvalid)
        self.assertEqual(
            true.diagnostics,
            (
                true.diagnostics[0].__class__("contradictory_facts", ("facts", "father_alive")),
                true.diagnostics[0].__class__("contradictory_facts", ("facts", "is_student")),
            ),
        )
        false = prepare_case(
            defs,
            service(contradiction),
            {"father_alive": False, "is_student": True},
            date(2026, 1, 1),
        )
        self.assertIsInstance(false, CasePreparationSuccess)
        unknown = prepare_case(
            defs, service(contradiction), {"father_alive": True}, date(2026, 1, 1)
        )
        self.assertIsInstance(unknown, CasePreparationSuccess)
        assert isinstance(unknown, CasePreparationSuccess)
        self.assertEqual(unknown.prepared_facts.missing_source_dependencies, {})

    def test_true_contradiction_reports_only_influential_submitted_facts(self) -> None:
        defs = {
            "father_alive": FACT_DEFINITIONS["father_alive"],
            "is_student": FACT_DEFINITIONS["is_student"],
        }
        contradiction = ContradictionSnapshot(
            "secret-id",
            Predicate(
                "any",
                children=(
                    Predicate("eq", "father_alive", True),
                    Predicate("eq", "is_student", True),
                ),
            ),
            ("father_alive", "is_student"),
        )

        omitted_unknown = prepare_case(
            defs, service(contradiction), {"father_alive": True}, date(2026, 1, 1)
        )
        self.assertIsInstance(omitted_unknown, CasePreparationInvalid)
        assert isinstance(omitted_unknown, CasePreparationInvalid)
        self.assertEqual(
            tuple(item.path for item in omitted_unknown.diagnostics),
            (("facts", "father_alive"),),
        )

        dominated_false = prepare_case(
            defs,
            service(contradiction),
            {"father_alive": True, "is_student": False},
            date(2026, 1, 1),
        )
        self.assertIsInstance(dominated_false, CasePreparationInvalid)
        assert isinstance(dominated_false, CasePreparationInvalid)
        self.assertEqual(
            tuple(item.path for item in dominated_false.diagnostics),
            (("facts", "father_alive"),),
        )

        both_true = prepare_case(
            defs,
            service(contradiction),
            {"father_alive": True, "is_student": True},
            date(2026, 1, 1),
        )
        self.assertIsInstance(both_true, CasePreparationInvalid)
        assert isinstance(both_true, CasePreparationInvalid)
        self.assertEqual(
            tuple(item.path for item in both_true.diagnostics),
            (("facts", "father_alive"), ("facts", "is_student")),
        )


if __name__ == "__main__":
    unittest.main()
