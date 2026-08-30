from __future__ import annotations

import unittest
from datetime import date

from prototype.bardi_prototype.contracts import (
    InconclusiveResult,
    NextQuestionResult,
    PlanResult,
)
from prototype.bardi_prototype.fixtures import load_researched_catalog
from prototype.bardi_prototype.scenario import run_scenario


class CrossFixtureSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_researched_catalog()

    def run_case(
        self,
        goal_id: str,
        facts: dict[str, object],
        locale: str = "en",
        evaluation_date: date = date(2026, 8, 26),
    ):
        return run_scenario(
            knowledge=self.catalog,
            goal_id=goal_id,
            facts=facts,
            locale=locale,  # type: ignore[arg-type]
            evaluation_date=evaluation_date,
        )

    def test_passport_known_case_still_runs_through_catalog(self) -> None:
        result = self.run_case(
            "get_egyptian_passport",
            {
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "existing_passport_state": "expired",
                "passport_class": "ordinary",
                "birth_date": date(1995, 6, 10),
                "sex": "female",
                "is_student": False,
                "service_level": "standard",
                "residence_police_jurisdiction": "giza",
            },
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        self.assertEqual(
            result.plan.procedure_id,  # type: ignore[union-attr]
            "ordinary_domestic_passport_renewal",
        )

    def test_national_id_known_case_runs_same_seam(self) -> None:
        result = self.run_case(
            "get_egyptian_national_id",
            {
                "application_location": "inside_egypt",
                "national_id_possession_state": "held",
                "national_id_data_change_kind": "none",
                "national_id_expiry_date": date(2026, 5, 1),
                "residence_governorate": "giza",
                "residence_district": "dokki",
            },
        )
        self.assertIsInstance(result, PlanResult)
        plan = result.plan  # type: ignore[union-attr]
        self.assertEqual(plan.procedure_id, "ordinary_domestic_national_id_renewal")
        self.assertEqual(len(plan.fees), 1)
        self.assertEqual(plan.fees[0].id, "nid.fee.ordinary")
        self.assertEqual(plan.fees[0].value_state, "unknown")
        self.assertIsNone(plan.fees[0].amount)
        self.assertIn(
            "nid.requirement.renew_after_expiry",
            {item.id for item in plan.checklist},
        )
        self.assertNotIn(
            "nid.requirement.previous_card",
            {item.id for item in plan.checklist},
        )

    def test_military_only_son_candidate_runs_same_seam(self) -> None:
        result = self.run_case(
            "handle_military_service_paperwork",
            {
                "application_location": "inside_egypt",
                "father_alive": True,
                "other_living_sons_of_father_count": 0,
                "father_unable_to_earn_status": "not_documented_unable",
                "mother_family_status": "other",
                "unmarried_sisters_requiring_support_count": 0,
                "missing_relative_category": "none",
                "sibling_service_status": "none",
                "residence_governorate": "giza",
            },
        )
        self.assertIsInstance(result, PlanResult)
        plan = result.plan  # type: ignore[union-attr]
        self.assertEqual(
            plan.procedure_id,
            "temporary_family_exemption_from_military_service",
        )
        self.assertEqual(
            tuple(basis.id for basis in plan.eligibility_bases),
            ("family.only_son_living_father",),
        )
        self.assertIn(
            "mil.shared.supporting_documents",
            {item.id for item in plan.checklist},
        )
        self.assertNotIn(
            "mil.basis.only_son_living_father",
            {item.id for item in plan.checklist},
        )
        self.assertIn(
            "mil.warning.candidate_not_decision",
            {warning.id for warning in plan.warnings},
        )
        self.assertEqual(
            tuple(point.id for point in plan.service_points),
            ("sp.recruitment_region_giza",),
        )
        self.assertEqual(plan.routing.status, "resolved")

    def test_passport_missing_state_asks_authored_question_deterministically(self) -> None:
        facts = {
            "citizenship": "egyptian",
            "application_location": "inside_egypt",
            "passport_class": "ordinary",
        }
        first = self.run_case("get_egyptian_passport", facts)
        second = self.run_case("get_egyptian_passport", facts)
        self.assertIsInstance(first, NextQuestionResult)
        self.assertEqual(first.question_id, "q.existing_passport_state")  # type: ignore[union-attr]
        self.assertEqual(first.fact_key, "existing_passport_state")  # type: ignore[union-attr]
        self.assertEqual(first, second)

    def test_national_id_missing_possession_asks_before_later_facts(self) -> None:
        result = self.run_case(
            "get_egyptian_national_id",
            {"application_location": "inside_egypt"},
        )
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.nid.possession_state")  # type: ignore[union-attr]

    def test_national_id_expiry_question_resolves_derived_selection_fact(self) -> None:
        result = self.run_case(
            "get_egyptian_national_id",
            {
                "application_location": "inside_egypt",
                "national_id_possession_state": "held",
                "national_id_data_change_kind": "none",
            },
        )
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.nid.expiry_date")  # type: ignore[union-attr]
        self.assertEqual(result.fact_key, "national_id_expiry_date")  # type: ignore[union-attr]

    def test_unresearched_related_procedure_is_named_not_approximated(self) -> None:
        result = self.run_case(
            "get_egyptian_passport",
            {
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "none",
            },
        )
        self.assertIsInstance(result, InconclusiveResult)
        self.assertEqual(result.reason_code, "procedure_not_researched")  # type: ignore[union-attr]
        self.assertEqual(result.procedure_id, "first_egyptian_passport_issuance")  # type: ignore[union-attr]

    def test_missing_consequential_question_is_configuration_defect(self) -> None:
        result = self.run_case(
            "get_egyptian_passport",
            {
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "expired",
            },
        )
        self.assertIsInstance(result, InconclusiveResult)
        self.assertEqual(  # type: ignore[union-attr]
            result.reason_code,
            "procedure_selection_configuration_defect",
        )
        self.assertIn(  # type: ignore[union-attr]
            "missing_procedure_selection_question:citizenship",
            result.diagnostic_codes,
        )

    def test_goal_stays_stable_while_procedure_changes(self) -> None:
        renewal = self.run_case(
            "get_egyptian_passport",
            {
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "expired",
                "birth_date": date(1995, 6, 10),
                "sex": "female",
                "is_student": False,
                "service_level": "standard",
                "residence_police_jurisdiction": "giza",
            },
            evaluation_date=date(2026, 8, 25),
        )
        first_issuance = self.run_case(
            "get_egyptian_passport",
            {
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "none",
            },
        )
        self.assertIsInstance(renewal, PlanResult)
        self.assertEqual(renewal.plan.goal_id, "get_egyptian_passport")  # type: ignore[union-attr]
        self.assertIsInstance(first_issuance, InconclusiveResult)
        self.assertEqual(  # type: ignore[union-attr]
            first_issuance.procedure_id,
            "first_egyptian_passport_issuance",
        )

    def test_question_localizes_without_changing_identity(self) -> None:
        facts = {"application_location": "inside_egypt"}
        en = self.run_case("get_egyptian_national_id", facts, "en")
        ar = self.run_case("get_egyptian_national_id", facts, "ar")
        self.assertIsInstance(en, NextQuestionResult)
        self.assertIsInstance(ar, NextQuestionResult)
        self.assertEqual(en.question_id, ar.question_id)  # type: ignore[union-attr]
        self.assertEqual(en.fact_key, ar.fact_key)  # type: ignore[union-attr]
        self.assertNotEqual(en.question, ar.question)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
