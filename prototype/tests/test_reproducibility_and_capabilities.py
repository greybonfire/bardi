from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path

from prototype.bardi_prototype.capabilities import build_capability_report
from prototype.bardi_prototype.contracts import (
    InconclusiveResult,
    InvalidResult,
    NextQuestionResult,
    PlanResult,
)
from prototype.bardi_prototype.derivations import derive_facts
from prototype.bardi_prototype.fixtures import load_researched_catalog
from prototype.bardi_prototype.scenario import run_scenario


class ReproducibilityAndCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_researched_catalog()

    @staticmethod
    def passport_facts(**overrides: object) -> dict[str, object]:
        facts: dict[str, object] = {
            "citizenship": "egyptian",
            "application_location": "inside_egypt",
            "existing_passport_state": "expired",
            "passport_class": "ordinary",
            "birth_date": date(1995, 6, 10),
            "sex": "female",
            "is_student": False,
            "service_level": "standard",
            "residence_police_jurisdiction": "giza",
        }
        facts.update(overrides)
        return facts

    @staticmethod
    def national_id_facts(**overrides: object) -> dict[str, object]:
        facts: dict[str, object] = {
            "application_location": "inside_egypt",
            "national_id_possession_state": "held",
            "national_id_data_change_kind": "none",
            "national_id_expiry_date": date(2026, 5, 1),
            "residence_governorate": "giza",
            "residence_district": "dokki",
        }
        facts.update(overrides)
        return facts

    @staticmethod
    def military_false_facts(**overrides: object) -> dict[str, object]:
        facts: dict[str, object] = {
            "application_location": "inside_egypt",
            "father_alive": False,
            "other_living_sons_of_father_count": 1,
            "father_unable_to_earn_status": "not_documented_unable",
            "mother_family_status": "other",
            "unmarried_sisters_requiring_support_count": 0,
            "missing_relative_category": "none",
            "sibling_service_status": "none",
            "residence_governorate": "giza",
        }
        facts.update(overrides)
        return facts

    def test_identical_inputs_are_structurally_reproducible_without_fact_persistence(self) -> None:
        cases = (
            (
                "get_egyptian_passport",
                "ordinary_domestic_passport_renewal",
                self.passport_facts(),
                date(2026, 8, 25),
            ),
            (
                "get_egyptian_national_id",
                "ordinary_domestic_national_id_renewal",
                self.national_id_facts(),
                date(2026, 8, 26),
            ),
            (
                "handle_military_service_paperwork",
                "temporary_family_exemption_from_military_service",
                self.military_false_facts(
                    father_alive=True,
                    other_living_sons_of_father_count=0,
                ),
                date(2026, 8, 26),
            ),
        )
        for goal_id, procedure_id, facts, evaluation_date in cases:
            with self.subTest(procedure_id=procedure_id):
                original = deepcopy(facts)
                version_id = self.catalog.fixtures[procedure_id].procedure.version_id
                request = dict(
                    knowledge=self.catalog,
                    goal_id=goal_id,
                    facts=facts,
                    locale="en",
                    evaluation_date=evaluation_date,
                    procedure_version_id=version_id,
                )
                results = tuple(run_scenario(**request) for _ in range(5))
                self.assertTrue(all(result == results[0] for result in results[1:]))
                self.assertEqual(facts, original)
                self.assertIsInstance(results[0], PlanResult)
                self.assertEqual(results[0].plan.procedure_version_id, version_id)  # type: ignore[union-attr]
                self.assertFalse(hasattr(results[0], "facts"))
                self.assertFalse(hasattr(results[0], "anonymous_case"))

    def test_capability_report_is_deterministic_and_covers_all_researched_fixtures(self) -> None:
        first = build_capability_report(self.catalog)
        second = build_capability_report(load_researched_catalog())
        self.assertEqual(first, second)
        self.assertEqual(len(first.fixtures), 3)

        by_id = {item.procedure_id: item for item in first.fixtures}
        passport = by_id["ordinary_domestic_passport_renewal"]
        national_id = by_id["ordinary_domestic_national_id_renewal"]
        military = by_id["temporary_family_exemption_from_military_service"]

        self.assertIn("age_years_on_evaluation_date", passport.derived_fact_keys)
        self.assertIn("citizenship", passport.missing_question_fact_keys)
        self.assertIn("quantity", passport.claim_attributes)
        self.assertIn("copy_quantity", passport.claim_attributes)
        self.assertEqual(passport.contradiction_ids, ())

        self.assertIn("card_expired_before_evaluation_date", national_id.derived_fact_keys)
        self.assertIn("nid.no_current_card_with_expiry_date", national_id.contradiction_ids)
        self.assertEqual(national_id.fee_value_states, ("unknown",))
        self.assertTrue(national_id.routing_has_verification_path)

        self.assertEqual(military.eligibility_basis_count, 6)
        self.assertEqual(military.eligibility_basis_states, ("needs_reverification",))
        self.assertEqual(len(military.eligibility_basis_fact_stages), 6)
        self.assertEqual(len(military.service_point_ids), 3)
        self.assertEqual(military.service_point_association_count, 3)
        self.assertEqual(len(military.procedure_version_ids), 2)
        self.assertIn("secondary", military.source_classifications)
        self.assertIn("scope", military.claim_attributes)
        self.assertIn("eligibility_basis_id", military.claim_attributes)

        self.assertTrue(all(item.dependency_count == 0 for item in first.fixtures))
        self.assertTrue(all(item.rules_contract_versions == ("v1",) for item in first.fixtures))

    def test_committed_capability_report_documents_required_boundaries(self) -> None:
        report = Path("docs/prototype-capability-report.md").read_text(encoding="utf-8")
        for procedure_id in (
            "ordinary_domestic_passport_renewal",
            "ordinary_domestic_national_id_renewal",
            "temporary_family_exemption_from_military_service",
        ):
            self.assertIn(procedure_id, report)
        for heading in (
            "Required Facts and Derived Facts",
            "Eligibility Basis behavior",
            "Eligibility Basis reachability and qualification Facts",
            "Dependencies",
            "Routing",
            "Temporal and trust states",
            "Missing Questions",
            "Unsupported assumptions",
            "Do not promote to the production contract",
        ):
            self.assertIn(heading, report)

    def test_passport_positive_negative_unknown_and_age_boundaries(self) -> None:
        exact_15 = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(
                birth_date=date(2011, 8, 25),
                sex="female",
            ),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(exact_15, PlanResult)
        ids = {item.id for item in exact_15.plan.checklist}  # type: ignore[union-attr]
        self.assertIn("passport.requirement.national_id", ids)
        self.assertNotIn("passport.requirement.birth_certificate", ids)

        exact_19_male = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(
                birth_date=date(2007, 8, 25),
                sex="male",
            ),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(exact_19_male, PlanResult)
        self.assertIn(
            "passport.requirement.military_status",
            {item.id for item in exact_19_male.plan.checklist},  # type: ignore[union-attr]
        )

        negative = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts={
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
                "existing_passport_state": "none",
            },
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(negative, InconclusiveResult)
        self.assertEqual(negative.reason_code, "procedure_not_researched")

        unknown = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_passport",
            facts={
                "citizenship": "egyptian",
                "application_location": "inside_egypt",
                "passport_class": "ordinary",
            },
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(unknown, NextQuestionResult)
        self.assertEqual(unknown.question_id, "q.existing_passport_state")

    def test_national_id_positive_negative_unknown_contradiction_and_deadline_edge(self) -> None:
        positive = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_national_id",
            facts=self.national_id_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(positive, PlanResult)

        negative = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_national_id",
            facts={
                "application_location": "inside_egypt",
                "national_id_possession_state": "lost",
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(negative, InconclusiveResult)
        self.assertEqual(negative.reason_code, "procedure_not_researched")

        unknown = run_scenario(
            knowledge=self.catalog,
            goal_id="get_egyptian_national_id",
            facts={
                "application_location": "inside_egypt",
                "national_id_possession_state": "held",
                "national_id_data_change_kind": "none",
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(unknown, NextQuestionResult)
        self.assertEqual(unknown.question_id, "q.nid.expiry_date")

        contradictory = run_scenario(
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
        self.assertIsInstance(contradictory, InvalidResult)
        self.assertEqual(contradictory.diagnostic_code, "contradictory_facts")

        on_deadline = derive_facts(
            {"national_id_expiry_date": date(2026, 5, 30)},
            date(2026, 8, 30),
        )
        after_deadline = derive_facts(
            {"national_id_expiry_date": date(2026, 5, 30)},
            date(2026, 8, 31),
        )
        self.assertEqual(on_deadline["renewal_deadline_date"], date(2026, 8, 30))
        self.assertFalse(on_deadline["renewal_deadline_passed"])
        self.assertTrue(after_deadline["renewal_deadline_passed"])

    def test_all_six_military_basis_branches_plus_negative_unknown_and_contradiction(self) -> None:
        cases = (
            (
                "family.only_son_living_father",
                {"father_alive": True, "other_living_sons_of_father_count": 0},
            ),
            (
                "family.support_father_or_incapable_brothers",
                {
                    "father_alive": True,
                    "other_living_sons_of_father_count": 1,
                    "father_unable_to_earn_status": "authority_documented_unable",
                },
            ),
            (
                "family.support_mother",
                {"mother_family_status": "widowed"},
            ),
            (
                "family.support_unmarried_sisters",
                {"unmarried_sisters_requiring_support_count": 1},
            ),
            (
                "family.missing_war_or_terror_relative",
                {
                    "missing_relative_category": "citizen",
                    "missing_relative_cause": "terrorist_operations",
                    "missing_relative_alive_status": "missing",
                    "applicant_largest_eligible_relative_status": "authority_documented_yes",
                },
            ),
            (
                "family.sibling_current_service",
                {
                    "sibling_service_status": "compulsory_service",
                    "applicant_eldest_remaining_brother_status": "authority_documented_yes",
                    "article7_third_exclusion_status": "none_documented",
                },
            ),
        )
        for expected_basis_id, overrides in cases:
            with self.subTest(basis=expected_basis_id):
                result = run_scenario(
                    knowledge=self.catalog,
                    goal_id="handle_military_service_paperwork",
                    facts=self.military_false_facts(**overrides),
                    locale="en",
                    evaluation_date=date(2026, 8, 26),
                )
                self.assertIsInstance(result, PlanResult)
                basis_ids = {basis.id for basis in result.plan.eligibility_bases}  # type: ignore[union-attr]
                self.assertIn(expected_basis_id, basis_ids)
                self.assertIn(expected_basis_id, result.plan.inconclusive_basis_ids)  # type: ignore[union-attr]

        negative = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts=self.military_false_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(negative, InconclusiveResult)
        self.assertEqual(negative.reason_code, "no_applicable_basis")

        unknown = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts={"application_location": "inside_egypt"},
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(unknown, NextQuestionResult)
        self.assertEqual(unknown.question_id, "q.mil.father_alive")

        contradictory = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts={
                "application_location": "inside_egypt",
                "missing_relative_category": "none",
                "missing_relative_cause": "war_operations",
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(contradictory, InvalidResult)
        self.assertEqual(contradictory.diagnostic_code, "contradictory_facts")

    def test_military_version_boundary_is_reproducible_at_march_24_and_25(self) -> None:
        facts = self.military_false_facts(
            father_alive=True,
            other_living_sons_of_father_count=0,
            missing_relative_category="officer",
            missing_relative_cause="terrorist_operations",
            missing_relative_alive_status="missing",
            applicant_largest_eligible_relative_status="authority_documented_yes",
        )
        before = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts=facts,
            locale="en",
            evaluation_date=date(2026, 3, 24),
        )
        after = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts=facts,
            locale="en",
            evaluation_date=date(2026, 3, 25),
        )
        self.assertIsInstance(before, PlanResult)
        self.assertIsInstance(after, PlanResult)
        self.assertEqual(
            before.plan.procedure_version_id,  # type: ignore[union-attr]
            "temporary_family_exemption_from_military_service.research-2026-03-24",
        )
        self.assertEqual(
            after.plan.procedure_version_id,  # type: ignore[union-attr]
            "temporary_family_exemption_from_military_service.research-2026-08-26",
        )
        self.assertNotIn(
            "family.missing_war_or_terror_relative",
            {basis.id for basis in before.plan.eligibility_bases},  # type: ignore[union-attr]
        )
        self.assertIn(
            "family.missing_war_or_terror_relative",
            {basis.id for basis in after.plan.eligibility_bases},  # type: ignore[union-attr]
        )


if __name__ == "__main__":
    unittest.main()
