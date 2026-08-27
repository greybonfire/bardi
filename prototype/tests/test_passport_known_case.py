from __future__ import annotations

import unittest
from datetime import date

from prototype.bardi_prototype.contracts import PlanResult
from prototype.bardi_prototype.fixtures import load_passport_renewal_fixture
from prototype.bardi_prototype.scenario import run_scenario


KNOWN_FACTS = {
    "citizenship": "egyptian",
    "application_location": "inside_egypt",
    "existing_passport_state": "expired",
    "passport_class": "ordinary",
    "birth_date": date(1995, 6, 10),
    "sex": "female",
    "national_id_status": "valid_current_data",
    "is_student": False,
    "service_level": "standard",
    "residence_police_jurisdiction": "giza",
}
EVALUATION_DATE = date(2026, 8, 25)


class PassportKnownCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.knowledge = load_passport_renewal_fixture()

    def run_known(self, locale="en") -> PlanResult:
        result = run_scenario(
            knowledge=self.knowledge,
            goal_id="get_egyptian_passport",
            facts=KNOWN_FACTS,
            locale=locale,
            evaluation_date=EVALUATION_DATE,
        )
        self.assertIsInstance(result, PlanResult)
        return result  # type: ignore[return-value]

    def test_known_adult_expired_standard_case(self) -> None:
        result = self.run_known()
        plan = result.plan

        self.assertEqual(plan.goal_id, "get_egyptian_passport")
        self.assertEqual(plan.procedure_id, "ordinary_domestic_passport_renewal")
        self.assertEqual(
            plan.procedure_version_id,
            "ordinary_domestic_passport_renewal.research-2026-08-25",
        )

        checklist_ids = tuple(item.id for item in plan.checklist)
        self.assertEqual(
            checklist_ids,
            (
                "passport.requirement.national_id",
                "passport.requirement.photos",
                "passport.requirement.originals_and_copy",
            ),
        )
        self.assertNotIn("passport.requirement.previous_passport", checklist_ids)
        self.assertNotIn("passport.requirement.birth_certificate", checklist_ids)
        self.assertNotIn("passport.requirement.student_enrollment", checklist_ids)
        self.assertNotIn("passport.requirement.military_status", checklist_ids)

        self.assertEqual(tuple(fee.id for fee in plan.fees), ("passport.fee.base",))
        self.assertEqual(plan.fees[0].amount, 705)
        self.assertEqual(plan.fees[0].currency, "EGP")

        self.assertEqual(
            tuple(step.id for step in plan.steps),
            (
                "passport.step.obtain_form_29",
                "passport.step.complete_form",
                "passport.step.submit_and_pay",
            ),
        )
        self.assertEqual(
            tuple(point.id for point in plan.service_points),
            ("sp.giza_passport_office",),
        )
        self.assertEqual(len(plan.unknowns), 1)
        self.assertIn("standard-service turnaround", plan.unknowns[0])

        self.assertEqual(plan.freshness.verified_on, EVALUATION_DATE)
        self.assertEqual(plan.freshness.evaluation_date, EVALUATION_DATE)
        self.assertEqual(plan.freshness.generated_on, EVALUATION_DATE)

    def test_every_rendered_evidence_bearing_item_has_source_metadata(self) -> None:
        plan = self.run_known().plan
        for item in (*plan.checklist, *plan.steps, *plan.fees, *plan.service_points):
            self.assertTrue(item.sources, item.id)
            self.assertTrue(all(source.source_id.startswith("SRC-") for source in item.sources))

        sourced_warnings = {warning.id: warning for warning in plan.warnings}
        self.assertTrue(sourced_warnings["passport.warning.personal_document"].sources)
        self.assertTrue(sourced_warnings["passport.warning.validity"].sources)
        self.assertFalse(sourced_warnings["passport.warning.regenerate"].sources)
        self.assertFalse(sourced_warnings["passport.warning.guidance_not_decision"].sources)

    def test_unverified_previous_passport_claim_remains_in_fixture_but_not_plan(self) -> None:
        fixture_claim = next(
            claim
            for claim in self.knowledge.claims
            if claim.id == "passport.requirement.previous_passport"
        )
        self.assertEqual(fixture_claim.verification_state, "needs_reverification")
        self.assertNotIn(
            fixture_claim.id,
            {item.id for item in self.run_known().plan.checklist},
        )

    def test_bilingual_projection_preserves_semantics(self) -> None:
        en = self.run_known("en").plan
        ar = self.run_known("ar").plan

        self.assertEqual(en.goal_id, ar.goal_id)
        self.assertEqual(en.procedure_id, ar.procedure_id)
        self.assertEqual(
            tuple(item.id for item in en.checklist),
            tuple(item.id for item in ar.checklist),
        )
        self.assertEqual(tuple(step.id for step in en.steps), tuple(step.id for step in ar.steps))
        self.assertEqual(tuple(fee.id for fee in en.fees), tuple(fee.id for fee in ar.fees))
        self.assertEqual(
            tuple(point.id for point in en.service_points),
            tuple(point.id for point in ar.service_points),
        )
        self.assertNotEqual(en.goal, ar.goal)
        self.assertNotEqual(en.checklist[0].text, ar.checklist[0].text)

    def test_same_input_is_structurally_deterministic(self) -> None:
        first = self.run_known()
        second = self.run_known()
        self.assertEqual(first, second)

    def test_result_does_not_retain_raw_facts(self) -> None:
        result = self.run_known()
        self.assertFalse(hasattr(result.plan, "facts"))


if __name__ == "__main__":
    unittest.main()
