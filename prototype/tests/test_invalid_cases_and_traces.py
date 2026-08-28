from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime

from prototype.bardi_prototype.contracts import InvalidResult, NextQuestionResult, PlanResult, Predicate
from prototype.bardi_prototype.evaluator import TruthValue, all_of, eq, evaluate
from prototype.bardi_prototype.fixtures import load_researched_catalog
from prototype.bardi_prototype.scenario import inspect_scenario, run_scenario


class InvalidCasesAndTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_researched_catalog()

    def test_contradictory_national_id_facts_are_rejected_before_selection(self) -> None:
        result = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_national_id",
            facts={
                "application_location": "inside_egypt",
                "national_id_possession_state": "none",
                "national_id_expiry_date": date(2026, 5, 1),
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, InvalidResult)
        self.assertEqual(result.diagnostic_code, "contradictory_facts")
        self.assertEqual(
            result.conflicting_fact_keys,
            ("national_id_expiry_date", "national_id_possession_state"),
        )
        self.assertIn(
            "contradiction:nid.no_current_card_with_expiry_date",
            result.diagnostic_codes,
        )

    def test_contradictory_military_facts_identify_only_submitted_conflict(self) -> None:
        result = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts={
                "missing_relative_category": "none",
                "missing_relative_cause": "terrorist_operations",
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, InvalidResult)
        self.assertEqual(result.diagnostic_code, "contradictory_facts")
        self.assertEqual(
            result.conflicting_fact_keys,
            ("missing_relative_category", "missing_relative_cause"),
        )
        self.assertEqual(
            result.diagnostic_codes,
            ("contradiction:mil.no_missing_relative_with_cause",),
        )

    def test_type_violations_remain_invalid_not_unknown(self) -> None:
        cases = (
            (
                "get_egyptian_national_id",
                {"national_id_expiry_date": "2026-05-01"},
                "invalid_fact_value:national_id_expiry_date",
            ),
            (
                "get_egyptian_national_id",
                {"national_id_expiry_date": datetime(2026, 5, 1, 12, 0)},
                "invalid_fact_value:national_id_expiry_date",
            ),
            (
                "handle_military_service_paperwork",
                {"other_living_sons_of_father_count": "0"},
                "invalid_fact_value:other_living_sons_of_father_count",
            ),
            (
                "get_egyptian_passport",
                {"is_student": None},
                "invalid_fact_value:is_student",
            ),
        )
        for goal_id, facts, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                result = run_scenario(
                    knowledge=self.catalog,
                    goal_id=goal_id,
                    facts=facts,
                    locale="en",
                    evaluation_date=date(2026, 8, 26),
                )
                self.assertIsInstance(result, InvalidResult)
                self.assertEqual(result.diagnostic_code, "invalid_facts")
                self.assertIn(diagnostic, result.diagnostic_codes)

    def test_trace_evaluates_dominated_unknown_child_without_making_it_consequential(self) -> None:
        result = evaluate(
            all_of(
                eq("father_alive", False),
                eq("other_living_sons_of_father_count", 0),
            ),
            {"father_alive": True},
        )
        self.assertEqual(result.value, TruthValue.FALSE)
        self.assertEqual(result.missing_facts, frozenset())
        self.assertIsNotNone(result.trace)
        trace = result.trace
        assert trace is not None
        self.assertEqual(len(trace.children), 2)

        false_child, unknown_child = trace.children
        self.assertEqual(false_child.result, TruthValue.FALSE)
        self.assertTrue(false_child.affected_result)
        self.assertEqual(false_child.fact_key, "father_alive")
        self.assertEqual(false_child.actual_value, True)
        self.assertEqual(false_child.expected_value, False)
        self.assertTrue(false_child.submitted)

        self.assertEqual(unknown_child.result, TruthValue.UNKNOWN)
        self.assertFalse(unknown_child.affected_result)
        self.assertEqual(
            unknown_child.missing_facts,
            frozenset(("other_living_sons_of_father_count",)),
        )
        self.assertFalse(unknown_child.fact_present)

    def test_editor_trace_shows_consequential_adult_military_unknown(self) -> None:
        inspection = inspect_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts={
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "expired",
                "birth_date": date(1995, 6, 10),
            },
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(inspection.result, NextQuestionResult)
        self.assertEqual(inspection.result.question_id, "q.sex")
        record = next(
            trace
            for trace in inspection.evaluation_traces
            if trace.context == "claim:passport.requirement.military_status"
        )
        self.assertTrue(record.consequential_to_planning)
        self.assertEqual(record.value, TruthValue.UNKNOWN)
        self.assertEqual(record.missing_facts, frozenset(("sex",)))
        self.assertTrue(record.trace.affected_result)

    def test_nonconsequential_unknown_does_not_drive_question_picker(self) -> None:
        inspection = inspect_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts={
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "expired",
                "birth_date": date(2010, 6, 10),
            },
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(inspection.result, NextQuestionResult)
        self.assertEqual(inspection.result.question_id, "q.is_student")
        record = next(
            trace
            for trace in inspection.evaluation_traces
            if trace.context == "claim:passport.requirement.military_status"
        )
        self.assertEqual(record.value, TruthValue.FALSE)
        self.assertEqual(record.missing_facts, frozenset())
        sex_nodes = [
            child
            for child in record.trace.children
            if child.fact_key == "sex"
        ]
        self.assertEqual(len(sex_nodes), 1)
        self.assertEqual(sex_nodes[0].result, TruthValue.UNKNOWN)
        self.assertFalse(sex_nodes[0].affected_result)

    def test_local_service_point_unknown_is_traced_but_does_not_block_plan(self) -> None:
        facts = {
            "citizenship": "egyptian",
            "application_location": "inside_egypt",
            "passport_class": "ordinary",
            "existing_passport_state": "expired",
            "birth_date": date(2010, 6, 10),
            "is_student": False,
            "service_level": "standard",
        }
        inspection = inspect_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts=facts,
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(inspection.result, PlanResult)
        self.assertEqual(inspection.result.plan.service_points, ())
        routing = next(
            trace
            for trace in inspection.evaluation_traces
            if trace.context == "service_point:sp.giza_passport_office"
        )
        self.assertFalse(routing.consequential_to_planning)
        self.assertEqual(routing.value, TruthValue.UNKNOWN)
        self.assertEqual(
            routing.missing_facts,
            frozenset(("residence_police_jurisdiction",)),
        )

    def test_public_result_excludes_full_trace_tree(self) -> None:
        request = dict(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts={
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "expired",
                "birth_date": date(2010, 6, 10),
            },
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        public_result = run_scenario(**request)
        inspection = inspect_scenario(**request)
        self.assertEqual(public_result, inspection.result)
        self.assertFalse(hasattr(public_result, "evaluation_traces"))
        self.assertTrue(inspection.evaluation_traces)

    def test_malformed_rule_is_invalid_knowledge_and_not_evaluated(self) -> None:
        goal_id = "get_egyptian_passport"
        goal_entry = self.catalog.goals[goal_id]
        bad_candidate = replace(
            goal_entry.candidates[0],
            applicability=Predicate("ref", fact="citizenship"),
        )
        bad_catalog = replace(
            self.catalog,
            goals={
                **self.catalog.goals,
                goal_id: replace(
                    goal_entry,
                    candidates=(bad_candidate, *goal_entry.candidates[1:]),
                ),
            },
        )
        inspection = inspect_scenario(
            knowledge=bad_catalog,
            goal_id=goal_id,
            facts={},
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(inspection.result, InvalidResult)
        self.assertEqual(inspection.result.diagnostic_code, "invalid_knowledge")
        self.assertIn(
            "unsupported_rule_operator:ref",
            inspection.result.diagnostic_codes,
        )
        self.assertEqual(inspection.evaluation_traces, ())


if __name__ == "__main__":
    unittest.main()
