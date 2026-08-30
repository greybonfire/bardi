from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from prototype.bardi_prototype.contracts import ClaimDefinition, FeeDefinition, PlanResult
from prototype.bardi_prototype.fixtures import (
    load_national_id_renewal_fixture,
    load_passport_renewal_fixture,
    load_temporary_family_exemption_fixture,
)
from prototype.bardi_prototype.scenario import run_scenario
from prototype.bardi_prototype.validation import validate_bundle
from prototype.bardi_prototype.facts import FACT_DEFINITIONS


class PersonalizedPlanAssemblyTests(unittest.TestCase):
    def passport_facts(self) -> dict[str, object]:
        return {
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

    def test_passport_plan_preserves_actionable_checklist_metadata_and_evidence(self) -> None:
        fixture = load_passport_renewal_fixture()
        result = run_scenario(
            knowledge=fixture,
            goal_id=fixture.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        plan = result.plan  # type: ignore[union-attr]
        photos = next(item for item in plan.checklist if item.id == "passport.requirement.photos")
        originals = next(item for item in plan.checklist if item.id == "passport.requirement.originals_and_copy")
        self.assertEqual(photos.classification, "official_requirement")
        self.assertEqual(photos.classification_label, "Official requirement")
        self.assertEqual(photos.quantity, 3)
        self.assertTrue(photos.sources)
        self.assertEqual(originals.original_quantity, 1)
        self.assertEqual(originals.copy_quantity, 1)
        self.assertTrue(originals.sources)
        self.assertNotIn("passport.requirement.previous_passport", {item.id for item in plan.checklist})
        self.assertEqual(
            tuple(item.id for group in plan.checklist_groups for item in group.items),
            tuple(item.id for item in plan.checklist),
        )

    def test_current_evidence_bearing_claim_without_evidence_is_invalid_knowledge(self) -> None:
        fixture = load_passport_renewal_fixture()
        first = fixture.claims[0]
        bad = replace(fixture, claims=(replace(first, evidence_link_ids=()), *fixture.claims[1:]))
        diagnostics = validate_bundle(bad, FACT_DEFINITIONS)
        self.assertIn(f"missing_claim_specific_evidence:claim:{first.id}", diagnostics)

    def test_known_unknown_range_and_unverified_fee_states_are_representable(self) -> None:
        passport = load_passport_renewal_fixture()
        result = run_scenario(
            knowledge=passport,
            goal_id=passport.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        self.assertEqual(result.plan.fees[0].value_state, "known")  # type: ignore[union-attr]
        self.assertEqual(result.plan.fees[0].amount, 705)  # type: ignore[union-attr]

        nid = load_national_id_renewal_fixture()
        nid_result = run_scenario(
            knowledge=nid,
            goal_id=nid.goal.id,
            facts={
                "application_location": "inside_egypt",
                "national_id_possession_state": "held",
                "national_id_data_change_kind": "none",
                "national_id_expiry_date": date(2026, 5, 1),
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(nid_result, PlanResult)
        self.assertEqual(nid_result.plan.fees[0].value_state, "unknown")  # type: ignore[union-attr]
        self.assertIsNone(nid_result.plan.fees[0].amount)  # type: ignore[union-attr]

        range_fee = FeeDefinition(
            "test.fee.range",
            passport.fees[0].text,
            None,
            "EGP",
            None,
            ("EL-MOI-FEE-01",),
            "current",
            value_state="range",
            minimum_amount=700,
            maximum_amount=800,
        )
        unverified_fee = FeeDefinition(
            "test.fee.unverified",
            passport.fees[0].text,
            900,
            "EGP",
            None,
            ("EL-MOI-FEE-01",),
            "needs_reverification",
            value_state="unverified",
        )
        variant = replace(passport, fees=(range_fee, unverified_fee))
        variant_result = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(variant_result, PlanResult)
        by_id = {fee.id: fee for fee in variant_result.plan.fees}  # type: ignore[union-attr]
        self.assertEqual((by_id["test.fee.range"].minimum_amount, by_id["test.fee.range"].maximum_amount), (700, 800))
        self.assertEqual(by_id["test.fee.unverified"].verification_state, "needs_reverification")
        self.assertTrue(by_id["test.fee.unverified"].current_value_unknown)
        self.assertIsNone(by_id["test.fee.unverified"].amount)

    def test_step_order_uses_phase_order_then_slot(self) -> None:
        fixture = load_passport_renewal_fixture()
        result = run_scenario(
            knowledge=fixture,
            goal_id=fixture.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        self.assertEqual(
            tuple((step.phase_order, step.slot, step.id) for step in result.plan.steps),  # type: ignore[union-attr]
            (
                (10, 10, "passport.step.obtain_form_29"),
                (10, 20, "passport.step.complete_form"),
                (20, 30, "passport.step.submit_and_pay"),
            ),
        )

    def test_shared_and_basis_scoped_claims_group_without_merging_identity(self) -> None:
        fixture = load_temporary_family_exemption_fixture()
        shared = fixture.claims[0]
        basis = ClaimDefinition(
            id="test.basis.supporting_documents",
            text=shared.text,
            classification="practical_preparation",
            applicability=None,
            evidence_link_ids=shared.evidence_link_ids,
            verification_state="current",
            display_order=15,
            document_type_id="military_supporting_documents",
            copy_quantity=1,
            scope="eligibility_basis",
            eligibility_basis_id="family.only_son_living_father",
        )
        trusted_bases = tuple(
            replace(item, verification_state="current")
            for item in fixture.eligibility_bases
        )
        variant = replace(
            fixture,
            eligibility_bases=trusted_bases,
            claims=(shared, basis, *fixture.claims[1:]),
        )
        result = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts={
                "application_location": "inside_egypt",
                "father_alive": True,
                "other_living_sons_of_father_count": 0,
                "father_unable_to_earn_status": "not_documented_unable",
                "mother_family_status": "other",
                "unmarried_sisters_requiring_support_count": 0,
                "missing_relative_category": "none",
                "sibling_service_status": "none",
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, PlanResult)
        group = next(group for group in result.plan.checklist_groups if group.document_type_id == "military_supporting_documents")  # type: ignore[union-attr]
        self.assertEqual(tuple(item.id for item in group.items), ("mil.shared.supporting_documents", "test.basis.supporting_documents"))
        self.assertEqual(group.items[1].classification_label, "Practical preparation")
        self.assertEqual(group.items[1].scope, "eligibility_basis")
        self.assertEqual(group.items[1].eligibility_basis_id, "family.only_son_living_father")
        self.assertEqual(group.items[1].copy_quantity, 1)
        self.assertTrue(group.items[0].sources)
        self.assertTrue(group.items[1].sources)

    def test_bilingual_projection_keeps_semantics_and_provenance_identical(self) -> None:
        fixture = load_passport_renewal_fixture()
        request = dict(
            knowledge=fixture,
            goal_id=fixture.goal.id,
            facts=self.passport_facts(),
            evaluation_date=date(2026, 8, 25),
            generated_on=date(2026, 8, 29),
        )
        en = run_scenario(locale="en", **request)
        ar = run_scenario(locale="ar", **request)
        self.assertIsInstance(en, PlanResult)
        self.assertIsInstance(ar, PlanResult)
        en_plan = en.plan  # type: ignore[union-attr]
        ar_plan = ar.plan  # type: ignore[union-attr]
        self.assertEqual(tuple(item.id for item in en_plan.checklist), tuple(item.id for item in ar_plan.checklist))
        self.assertEqual(tuple(tuple(source.source_id for source in item.sources) for item in en_plan.checklist), tuple(tuple(source.source_id for source in item.sources) for item in ar_plan.checklist))
        self.assertNotEqual(en_plan.checklist[0].text, ar_plan.checklist[0].text)
        self.assertNotEqual(en_plan.checklist[0].classification_label, ar_plan.checklist[0].classification_label)
        self.assertEqual(en_plan.freshness.generated_on, date(2026, 8, 29))
        self.assertEqual(en_plan.freshness.last_verified_on, date(2026, 8, 25))
        self.assertEqual(en_plan.freshness.procedure_version_id, fixture.procedure.version_id)
        self.assertEqual(en_plan.regeneration_warning.id, "passport.warning.regenerate")
        self.assertEqual(en_plan.regeneration_warning.severity, "important")
        self.assertEqual(en_plan.regeneration_warning.role, "regeneration")


if __name__ == "__main__":
    unittest.main()
