from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from prototype.bardi_prototype.contracts import (
    InvalidResult,
    NextQuestionResult,
    PlanResult,
    Predicate,
    QuestionDefinition,
)
from prototype.bardi_prototype.evaluator import (
    TruthValue,
    all_of,
    any_of,
    eq,
    evaluate,
    exists,
    validate_predicate,
)
from prototype.bardi_prototype.fixtures import load_researched_catalog
from prototype.bardi_prototype.scenario import run_scenario


class TypedRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_researched_catalog()

    def run_passport(self, facts: dict[str, object]):
        return run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts=facts,
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )

    def test_strong_kleene_boolean_dominance(self) -> None:
        false_and_unknown = evaluate(
            all_of(eq("father_alive", False), eq("other_living_sons_of_father_count", 0)),
            {"father_alive": True},
        )
        self.assertEqual(false_and_unknown.value, TruthValue.FALSE)
        self.assertEqual(false_and_unknown.missing_facts, frozenset())

        true_or_unknown = evaluate(
            any_of(eq("father_alive", True), eq("other_living_sons_of_father_count", 0)),
            {"father_alive": True},
        )
        self.assertEqual(true_or_unknown.value, TruthValue.TRUE)
        self.assertEqual(true_or_unknown.missing_facts, frozenset())

        true_and_unknown = evaluate(
            all_of(eq("father_alive", True), eq("other_living_sons_of_father_count", 0)),
            {"father_alive": True},
        )
        self.assertEqual(true_and_unknown.value, TruthValue.UNKNOWN)
        self.assertEqual(
            true_and_unknown.missing_facts,
            frozenset(("other_living_sons_of_father_count",)),
        )

    def test_exists_checks_submitted_key_presence_only(self) -> None:
        facts = {
            "birth_date": date(2000, 1, 1),
            "age_years_on_evaluation_date": 26,
        }
        submitted = frozenset(("birth_date",))
        self.assertEqual(
            evaluate(exists("birth_date"), facts, submitted_keys=submitted).value,
            TruthValue.TRUE,
        )
        self.assertEqual(
            evaluate(exists("is_student"), facts, submitted_keys=submitted).value,
            TruthValue.FALSE,
        )
        self.assertIn(
            "exists_requires_source_fact:age_years_on_evaluation_date",
            validate_predicate(exists("age_years_on_evaluation_date")),
        )

    def test_invalid_fact_values_are_not_coerced(self) -> None:
        base = {
            "citizenship": "egyptian",
            "application_location": "inside_egypt",
            "passport_class": "ordinary",
            "existing_passport_state": "expired",
        }
        cases = (
            ({**base, "is_student": 1}, "invalid_fact_value:is_student"),
            ({**base, "birth_date": "1995-06-10"}, "invalid_fact_value:birth_date"),
            ({**base, "passport_class": "ORDINARY"}, "invalid_fact_value:passport_class"),
            ({**base, "is_student": None}, "invalid_fact_value:is_student"),
        )
        for facts, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                result = self.run_passport(facts)
                self.assertIsInstance(result, InvalidResult)
                self.assertEqual(result.diagnostic_code, "invalid_facts")
                self.assertIn(diagnostic, result.diagnostic_codes)

    def test_unsupported_submitted_fact_key_is_invalid(self) -> None:
        result = self.run_passport({"made_up_fact": True})
        self.assertIsInstance(result, InvalidResult)
        self.assertIn("unsupported_fact_key:made_up_fact", result.diagnostic_codes)

    def test_rule_validation_rejects_malformed_contracts(self) -> None:
        self.assertIn(
            "unsupported_rule_operator:ref",
            validate_predicate(Predicate("ref", fact="citizenship")),
        )
        self.assertIn(
            "empty_boolean_composition:all",
            validate_predicate(Predicate("all")),
        )
        self.assertIn(
            "unsupported_rule_fact:not_a_fact",
            validate_predicate(eq("not_a_fact", "x")),
        )
        oversized = Predicate(
            "any",
            children=tuple(eq("citizenship", "egyptian") for _ in range(128)),
        )
        self.assertIn("rule_too_large", validate_predicate(oversized))

    def test_malformed_rule_returns_invalid_result_end_to_end(self) -> None:
        goal_id = "get_egyptian_passport"
        goal_entry = self.catalog.goals[goal_id]
        bad_candidate = replace(
            goal_entry.candidates[0],
            applicability=Predicate("ref", fact="citizenship"),
        )
        bad_goal_entry = replace(
            goal_entry,
            candidates=(bad_candidate, *goal_entry.candidates[1:]),
        )
        bad_catalog = replace(
            self.catalog,
            goals={**self.catalog.goals, goal_id: bad_goal_entry},
        )
        result = run_scenario(
            knowledge=bad_catalog,
            goal_id=goal_id,
            facts={},
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, InvalidResult)
        self.assertEqual(result.diagnostic_code, "invalid_knowledge")
        self.assertIn("unsupported_rule_operator:ref", result.diagnostic_codes)

    def test_missing_fact_picker_skips_nonconsequential_sex_for_minor(self) -> None:
        facts = {
            "citizenship": "egyptian",
            "application_location": "inside_egypt",
            "passport_class": "ordinary",
            "existing_passport_state": "expired",
        }
        first = self.run_passport(facts)
        self.assertIsInstance(first, NextQuestionResult)
        self.assertEqual(first.question_id, "q.birth_date")

        facts["birth_date"] = date(2010, 6, 10)
        second = self.run_passport(facts)
        self.assertIsInstance(second, NextQuestionResult)
        self.assertEqual(second.question_id, "q.is_student")

        facts["is_student"] = False
        third = self.run_passport(facts)
        self.assertIsInstance(third, NextQuestionResult)
        self.assertEqual(third.question_id, "q.service_level")

        facts["service_level"] = "standard"
        final = self.run_passport(facts)
        self.assertIsInstance(final, PlanResult)
        self.assertEqual(final.plan.service_points, ())

    def test_adult_military_branch_makes_sex_consequential(self) -> None:
        result = self.run_passport(
            {
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "expired",
                "birth_date": date(1995, 6, 10),
            }
        )
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.sex")

    def test_question_tie_break_is_stable_by_id(self) -> None:
        extra_questions = (
            QuestionDefinition(
                "q.test.b",
                "get_egyptian_passport",
                "citizenship",
                self.catalog.goals["get_egyptian_passport"].goal.text,
                1,
            ),
            QuestionDefinition(
                "q.test.a",
                "get_egyptian_passport",
                "citizenship",
                self.catalog.goals["get_egyptian_passport"].goal.text,
                1,
            ),
        )
        catalog = replace(
            self.catalog,
            questions=self.catalog.questions + extra_questions,
        )
        request = dict(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts={
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "expired",
            },
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        first = run_scenario(**request)
        second = run_scenario(**request)
        self.assertIsInstance(first, NextQuestionResult)
        self.assertEqual(first.question_id, "q.test.a")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
