from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from prototype.bardi_prototype.capabilities import build_capability_report
from prototype.bardi_prototype.contracts import (
    InconclusiveResult,
    NextQuestionResult,
    PlanResult,
)
from prototype.bardi_prototype.fixtures import load_researched_catalog
from prototype.bardi_prototype.scenario import inspect_scenario, run_scenario
from prototype.bardi_prototype.validation import validate_catalog


EVALUATION_DATE = date(2026, 8, 26)
GOAL_ID = "handle_military_service_paperwork"


class EligibilityBasisReachabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_researched_catalog()

    @staticmethod
    def unrelated_false_facts(**overrides: object) -> dict[str, object]:
        facts: dict[str, object] = {
            "application_location": "inside_egypt",
            "father_alive": False,
            "mother_family_status": "other",
            "unmarried_sisters_requiring_support_count": 0,
            "missing_relative_category": "none",
            "sibling_service_status": "none",
            "residence_governorate": "giza",
        }
        facts.update(overrides)
        return facts

    def run(self, facts: dict[str, object]):  # type: ignore[override]
        return run_scenario(
            knowledge=self.catalog,
            goal_id=GOAL_ID,
            facts=facts,
            locale="en",
            evaluation_date=EVALUATION_DATE,
        )

    def test_dead_father_skips_both_father_route_qualification_questions(self) -> None:
        result = self.run(self.unrelated_false_facts())

        self.assertIsInstance(result, InconclusiveResult)
        self.assertEqual(result.reason_code, "no_applicable_basis")
        self.assertNotIsInstance(result, NextQuestionResult)

        inspection = inspect_scenario(
            knowledge=self.catalog,
            goal_id=GOAL_ID,
            facts=self.unrelated_false_facts(),
            locale="en",
            evaluation_date=EVALUATION_DATE,
        )
        contexts = {record.context for record in inspection.evaluation_traces}
        for basis_id in (
            "family.only_son_living_father",
            "family.support_father_or_incapable_brothers",
        ):
            self.assertIn(
                f"eligibility_basis_reachability:{basis_id}",
                contexts,
            )
            self.assertIn(
                f"eligibility_basis_qualification_skipped_unreachable:{basis_id}",
                contexts,
            )
            self.assertNotIn(
                f"eligibility_basis_qualification:{basis_id}",
                contexts,
            )

    def test_unknown_father_state_asks_reachability_before_qualification(self) -> None:
        facts = self.unrelated_false_facts()
        del facts["father_alive"]

        result = self.run(facts)

        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.mil.father_alive")
        self.assertEqual(result.fact_key, "father_alive")

    def test_living_father_unlocks_only_relevant_qualification_facts(self) -> None:
        facts = self.unrelated_false_facts(father_alive=True)

        first = self.run(facts)
        self.assertIsInstance(first, NextQuestionResult)
        self.assertEqual(first.question_id, "q.mil.other_sons_count")
        self.assertEqual(first.fact_key, "other_living_sons_of_father_count")

        facts["other_living_sons_of_father_count"] = 1
        second = self.run(facts)
        self.assertIsInstance(second, NextQuestionResult)
        self.assertEqual(second.question_id, "q.mil.father_capacity")
        self.assertEqual(second.fact_key, "father_unable_to_earn_status")

    def test_missing_relative_gate_skips_detail_questions_when_no_relative_exists(self) -> None:
        result = self.run(self.unrelated_false_facts())
        self.assertIsInstance(result, InconclusiveResult)
        self.assertEqual(result.reason_code, "no_applicable_basis")

        reachable = self.unrelated_false_facts(missing_relative_category="citizen")
        result = self.run(reachable)
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.mil.missing_cause")
        self.assertEqual(result.fact_key, "missing_relative_cause")

    def test_sibling_service_gate_skips_order_and_exclusion_until_reachable(self) -> None:
        result = self.run(self.unrelated_false_facts())
        self.assertIsInstance(result, InconclusiveResult)

        reachable = self.unrelated_false_facts(
            sibling_service_status="compulsory_service"
        )
        result = self.run(reachable)
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.mil.eldest_remaining_brother")
        self.assertEqual(
            result.fact_key,
            "applicant_eldest_remaining_brother_status",
        )

    def test_ungated_mother_and_sister_bases_still_use_qualification_questions(self) -> None:
        mother_unknown = self.unrelated_false_facts()
        del mother_unknown["mother_family_status"]
        result = self.run(mother_unknown)
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.mil.mother_status")

        sister_unknown = self.unrelated_false_facts()
        del sister_unknown["unmarried_sisters_requiring_support_count"]
        result = self.run(sister_unknown)
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.mil.unmarried_sisters")

    def test_matching_one_basis_does_not_hide_other_reachable_alternatives(self) -> None:
        result = self.run(
            self.unrelated_false_facts(
                father_alive=True,
                other_living_sons_of_father_count=0,
                father_unable_to_earn_status="authority_documented_unable",
                mother_family_status="widowed",
            )
        )

        self.assertIsInstance(result, PlanResult)
        ids = tuple(basis.id for basis in result.plan.eligibility_bases)
        self.assertEqual(
            ids,
            (
                "family.only_son_living_father",
                "family.support_father_or_incapable_brothers",
                "family.support_mother",
            ),
        )
        self.assertEqual(result.plan.inconclusive_basis_ids, ids)

    def test_capability_report_separates_reachability_and_qualification_facts(self) -> None:
        report = build_capability_report(self.catalog)
        military = next(
            fixture
            for fixture in report.fixtures
            if fixture.procedure_id
            == "temporary_family_exemption_from_military_service"
        )
        stages = {
            item.id: item for item in military.eligibility_basis_fact_stages
        }

        self.assertEqual(
            stages["family.only_son_living_father"].reachability_fact_keys,
            ("father_alive",),
        )
        self.assertEqual(
            stages["family.only_son_living_father"].qualification_fact_keys,
            ("other_living_sons_of_father_count",),
        )
        self.assertEqual(
            stages[
                "family.support_father_or_incapable_brothers"
            ].reachability_fact_keys,
            ("father_alive",),
        )
        self.assertEqual(
            stages[
                "family.support_father_or_incapable_brothers"
            ].qualification_fact_keys,
            ("father_unable_to_earn_status",),
        )
        self.assertEqual(
            stages[
                "family.missing_war_or_terror_relative"
            ].reachability_fact_keys,
            ("missing_relative_category",),
        )
        self.assertEqual(
            stages[
                "family.sibling_current_service"
            ].reachability_fact_keys,
            ("sibling_service_status",),
        )

    def test_catalog_validation_requires_question_coverage_for_each_basis_stage(self) -> None:
        without_father_capacity = replace(
            self.catalog,
            questions=tuple(
                question
                for question in self.catalog.questions
                if question.id != "q.mil.father_capacity"
            ),
        )
        diagnostics = validate_catalog(without_father_capacity)
        self.assertIn(
            "missing_basis_qualification_question:family.support_father_or_incapable_brothers:father_unable_to_earn_status",
            diagnostics,
        )

        without_father_alive = replace(
            self.catalog,
            questions=tuple(
                question
                for question in self.catalog.questions
                if question.id != "q.mil.father_alive"
            ),
        )
        diagnostics = validate_catalog(without_father_alive)
        self.assertIn(
            "missing_basis_reachability_question:family.support_father_or_incapable_brothers:father_alive",
            diagnostics,
        )


if __name__ == "__main__":
    unittest.main()
