from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from prototype.bardi_prototype.contracts import (
    ClaimDefinition,
    InconclusiveResult,
    InvalidResult,
    LocalizedText,
    NextQuestionResult,
    PlanResult,
    ProcedureDependencyDefinition,
    ProcedureServicePointAssociationDefinition,
    ServicePointVersionDefinition,
    VerificationPathDefinition,
)
from prototype.bardi_prototype.evaluator import eq
from prototype.bardi_prototype.fixtures import (
    load_passport_renewal_fixture,
    load_researched_catalog,
    load_temporary_family_exemption_fixture,
)
from prototype.bardi_prototype.scenario import run_scenario
from prototype.bardi_prototype.validation import validate_catalog


class BasisDependencyRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_researched_catalog()

    def military_facts(self, **overrides: object) -> dict[str, object]:
        facts: dict[str, object] = {
            "application_location": "inside_egypt",
            "father_alive": True,
            "other_living_sons_of_father_count": 0,
            "father_unable_to_earn_status": "not_documented_unable",
            "mother_family_status": "other",
            "unmarried_sisters_requiring_support_count": 0,
            "missing_relative_category": "none",
            "sibling_service_status": "none",
            "residence_governorate": "giza",
        }
        facts.update(overrides)
        return facts

    def passport_facts(self, **overrides: object) -> dict[str, object]:
        facts: dict[str, object] = {
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
        facts.update(overrides)
        return facts

    def test_all_matched_bases_are_returned_as_alternatives(self) -> None:
        result = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts=self.military_facts(mother_family_status="widowed"),
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, PlanResult)
        bases = result.plan.eligibility_bases  # type: ignore[union-attr]
        self.assertEqual(
            tuple(basis.id for basis in bases),
            (
                "family.only_son_living_father",
                "family.support_mother",
            ),
        )
        self.assertTrue(
            all(
                basis.verification_state == "needs_reverification"
                for basis in bases
            )
        )
        self.assertTrue(all(basis.sources for basis in bases))
        self.assertEqual(
            result.plan.inconclusive_basis_ids,  # type: ignore[union-attr]
            (
                "family.only_son_living_father",
                "family.support_mother",
            ),
        )
        self.assertFalse(
            hasattr(result.plan, "recommended_eligibility_basis_id")  # type: ignore[union-attr]
        )

    def test_matching_one_basis_does_not_hide_unknown_alternatives(self) -> None:
        result = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts={
                "application_location": "inside_egypt",
                "father_alive": True,
                "other_living_sons_of_father_count": 0,
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, NextQuestionResult)
        self.assertEqual(result.question_id, "q.mil.father_capacity")  # type: ignore[union-attr]
        self.assertEqual(result.fact_key, "father_unable_to_earn_status")  # type: ignore[union-attr]

    def test_no_applicable_basis_is_safe_and_has_official_verification_path(self) -> None:
        result = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts={
                "application_location": "inside_egypt",
                "father_alive": False,
                "father_unable_to_earn_status": "not_documented_unable",
                "mother_family_status": "other",
                "unmarried_sisters_requiring_support_count": 0,
                "missing_relative_category": "none",
                "sibling_service_status": "none",
            },
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, InconclusiveResult)
        self.assertEqual(result.reason_code, "no_applicable_basis")  # type: ignore[union-attr]
        self.assertIn("Do not use a closest-match ground", result.message)  # type: ignore[union-attr]
        self.assertIsNotNone(result.verification_path)  # type: ignore[union-attr]
        self.assertEqual(result.verification_path.id, "mil.basis.verify")  # type: ignore[union-attr]
        self.assertTrue(result.verification_path.sources)  # type: ignore[union-attr]

    def test_basis_specific_claims_are_additive_and_keep_separate_identity(self) -> None:
        fixture = load_temporary_family_exemption_fixture()
        only_son_claim = ClaimDefinition(
            id="test.claim.only_son_documents",
            text=LocalizedText(
                ar="مستند إضافي لاختبار أساس الابن الوحيد",
                en="Synthetic only-son preparation claim",
            ),
            classification="practical_preparation",
            applicability=None,
            evidence_link_ids=("EL-MOD-SUPPORTING-DOCS",),
            verification_state="current",
            display_order=15,
            document_type_id="test.family_evidence",
            scope="eligibility_basis",
            eligibility_basis_id="family.only_son_living_father",
        )
        mother_claim = replace(
            only_son_claim,
            id="test.claim.mother_documents",
            text=LocalizedText(
                ar="مستند إضافي لاختبار أساس إعالة الأم",
                en="Synthetic mother-support preparation claim",
            ),
            display_order=16,
            eligibility_basis_id="family.support_mother",
        )
        # This test isolates the #10 additive-grouping capability. The real
        # military Bases remain needs_reverification; make only this synthetic
        # variant trusted so Basis-scoped current guidance may be unlocked.
        trusted_bases = tuple(
            replace(basis, verification_state="current")
            for basis in fixture.eligibility_bases
        )
        variant = replace(
            fixture,
            eligibility_bases=trusted_bases,
            claims=(
                fixture.claims[0],
                only_son_claim,
                mother_claim,
                *fixture.claims[1:],
            ),
        )

        result = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.military_facts(mother_family_status="widowed"),
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, PlanResult)
        plan = result.plan  # type: ignore[union-attr]
        by_id = {item.id: item for item in plan.checklist}
        self.assertIn("test.claim.only_son_documents", by_id)
        self.assertIn("test.claim.mother_documents", by_id)
        self.assertEqual(
            by_id["test.claim.only_son_documents"].eligibility_basis_id,
            "family.only_son_living_father",
        )
        self.assertEqual(
            by_id["test.claim.mother_documents"].eligibility_basis_id,
            "family.support_mother",
        )
        group = next(
            group
            for group in plan.checklist_groups
            if group.document_type_id == "test.family_evidence"
        )
        self.assertEqual(
            tuple(item.id for item in group.items),
            ("test.claim.only_son_documents", "test.claim.mother_documents"),
        )

    def _dependency(
        self,
        *,
        target_procedure_id: str,
        evidence_link_id: str,
        text: str,
    ) -> ProcedureDependencyDefinition:
        return ProcedureDependencyDefinition(
            id=f"test.dependency.{target_procedure_id}",
            text=LocalizedText(ar="متطلب سابق اختباري", en=text),
            target_procedure_id=target_procedure_id,
            relation="blocking_prerequisite",
            applicability=None,
            satisfied_when=eq("national_id_status", "valid_current_data"),
            evidence_link_ids=(evidence_link_id,),
            verification_state="current",
            verification_path=VerificationPathDefinition(
                id=f"test.verify.{target_procedure_id}",
                text=LocalizedText(
                    ar="تحقق من المتطلب السابق لدى الجهة المختصة.",
                    en="Verify this prerequisite with the competent authority.",
                ),
                evidence_link_ids=(evidence_link_id,),
            ),
        )

    def test_supported_dependency_resolves_one_target_version_without_recursing(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        dependency = self._dependency(
            target_procedure_id="ordinary_domestic_national_id_renewal",
            evidence_link_id="EL-MOI-REQ-01",
            text="Renew the National ID prerequisite",
        )
        passport_variant = replace(passport, dependencies=(dependency,))
        catalog = replace(
            self.catalog,
            fixtures={
                **self.catalog.fixtures,
                passport.procedure.procedure_id: passport_variant,
            },
            versioned_fixtures={
                **self.catalog.versioned_fixtures,
                passport.procedure.procedure_id: (passport_variant,),
            },
        )

        result = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(national_id_status="invalid_or_expired"),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        dependencies = result.plan.dependencies  # type: ignore[union-attr]
        self.assertEqual(len(dependencies), 1)
        dependency_result = dependencies[0]
        self.assertEqual(dependency_result.status, "blocking")
        self.assertEqual(
            dependency_result.target_procedure_id,
            "ordinary_domestic_national_id_renewal",
        )
        self.assertEqual(
            dependency_result.target_procedure_version_id,
            "ordinary_domestic_national_id_renewal.research-2026-08-26",
        )
        self.assertTrue(dependency_result.verification_path.sources)
        self.assertFalse(hasattr(dependency_result, "dependencies"))

    def test_unsupported_dependency_target_is_named_with_verification_path(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        dependency = self._dependency(
            target_procedure_id="unresearched_identity_prerequisite",
            evidence_link_id="EL-MOI-REQ-01",
            text="Unresearched identity prerequisite",
        )
        passport_variant = replace(passport, dependencies=(dependency,))
        catalog = replace(
            self.catalog,
            fixtures={
                **self.catalog.fixtures,
                passport.procedure.procedure_id: passport_variant,
            },
            versioned_fixtures={
                **self.catalog.versioned_fixtures,
                passport.procedure.procedure_id: (passport_variant,),
            },
        )

        result = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(national_id_status="invalid_or_expired"),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        dependency_result = result.plan.dependencies[0]  # type: ignore[union-attr]
        self.assertEqual(dependency_result.status, "unsupported_target")
        self.assertEqual(
            dependency_result.target_procedure_id,
            "unresearched_identity_prerequisite",
        )
        self.assertEqual(
            dependency_result.target_procedure,
            "Unresearched identity prerequisite",
        )
        self.assertIsNone(dependency_result.target_procedure_version_id)
        self.assertTrue(dependency_result.verification_path.sources)

    def test_blocking_dependency_cycle_is_invalid_catalog_configuration(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        national_id = self.catalog.fixtures["ordinary_domestic_national_id_renewal"]
        passport_dependency = self._dependency(
            target_procedure_id=national_id.procedure.procedure_id,
            evidence_link_id="EL-MOI-REQ-01",
            text="National ID prerequisite",
        )
        national_id_dependency = ProcedureDependencyDefinition(
            id="test.dependency.passport",
            text=LocalizedText(ar="متطلب جواز اختباري", en="Passport prerequisite"),
            target_procedure_id=passport.procedure.procedure_id,
            relation="blocking_prerequisite",
            applicability=None,
            satisfied_when=eq("national_id_possession_state", "held"),
            evidence_link_ids=("EL-CIVIL-LAW-52",),
            verification_state="current",
            verification_path=VerificationPathDefinition(
                id="test.verify.passport",
                text=LocalizedText(
                    ar="تحقق من المتطلب لدى الجهة المختصة.",
                    en="Verify the prerequisite with the competent authority.",
                ),
                evidence_link_ids=("EL-CIVIL-LAW-52",),
            ),
        )
        catalog = replace(
            self.catalog,
            fixtures={
                **self.catalog.fixtures,
                passport.procedure.procedure_id: replace(
                    passport,
                    dependencies=(passport_dependency,),
                ),
                national_id.procedure.procedure_id: replace(
                    national_id,
                    dependencies=(national_id_dependency,),
                ),
            },
            versioned_fixtures={
                **self.catalog.versioned_fixtures,
                passport.procedure.procedure_id: (
                    replace(passport, dependencies=(passport_dependency,)),
                ),
                national_id.procedure.procedure_id: (
                    replace(national_id, dependencies=(national_id_dependency,)),
                ),
            },
        )

        diagnostics = validate_catalog(catalog)
        self.assertTrue(
            any(code.startswith("blocking_dependency_cycle:") for code in diagnostics)
        )
        result = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, InvalidResult)
        self.assertEqual(result.diagnostic_code, "invalid_knowledge")

    def test_all_matching_service_point_associations_are_returned(self) -> None:
        military = self.catalog.fixtures[
            "temporary_family_exemption_from_military_service"
        ]
        giza, mansoura, zagazig = military.service_point_associations
        second_giza_match = replace(
            mansoura,
            id="spa.mil.mansoura.synthetic_giza_match",
            applicability=eq("residence_governorate", "giza"),
        )
        variant = replace(
            military,
            service_point_associations=(giza, second_giza_match, zagazig),
        )
        catalog = replace(
            self.catalog,
            fixtures={
                **self.catalog.fixtures,
                military.procedure.procedure_id: variant,
            },
            versioned_fixtures={
                **self.catalog.versioned_fixtures,
                military.procedure.procedure_id: (
                    self.catalog.versioned_fixtures[
                        military.procedure.procedure_id
                    ][0],
                    variant,
                ),
            },
        )

        result = run_scenario(
            knowledge=catalog,
            goal_id="handle_military_service_paperwork",
            facts=self.military_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, PlanResult)
        plan = result.plan  # type: ignore[union-attr]
        self.assertEqual(plan.routing.status, "resolved")
        self.assertEqual(
            tuple(point.id for point in plan.service_points),
            (
                "sp.recruitment_region_giza",
                "sp.recruitment_region_mansoura",
            ),
        )

    def test_unresolved_routing_does_not_remove_reliable_guidance(self) -> None:
        facts = self.military_facts()
        facts.pop("residence_governorate")
        result = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts=facts,
            locale="en",
            evaluation_date=date(2026, 8, 26),
        )
        self.assertIsInstance(result, PlanResult)
        plan = result.plan  # type: ignore[union-attr]
        self.assertIn(
            "mil.shared.supporting_documents",
            {item.id for item in plan.checklist},
        )
        self.assertTrue(plan.steps)
        self.assertEqual(plan.service_points, ())
        self.assertEqual(plan.routing.status, "unresolved")
        self.assertEqual(
            plan.routing.unresolved_fact_keys,
            ("residence_governorate",),
        )
        self.assertIsNotNone(plan.routing.verification_path)
        self.assertTrue(plan.routing.verification_path.sources)

    def test_routing_association_owner_is_explicit_and_mismatch_is_invalid(self) -> None:
        passport = load_passport_renewal_fixture()
        association = passport.service_point_associations[0]
        self.assertEqual(
            association.procedure_version_id,
            passport.procedure.version_id,
        )
        bad_association = replace(
            association,
            procedure_version_id="wrong.procedure.version",
        )
        bad_passport = replace(
            passport,
            service_point_associations=(bad_association,),
        )
        catalog = replace(
            self.catalog,
            fixtures={
                **self.catalog.fixtures,
                passport.procedure.procedure_id: bad_passport,
            },
            versioned_fixtures={
                **self.catalog.versioned_fixtures,
                passport.procedure.procedure_id: (bad_passport,),
            },
        )
        diagnostics = validate_catalog(catalog)
        self.assertIn(
            "association_procedure_version_mismatch:spa.passport_renewal.giza_standard:wrong.procedure.version",
            diagnostics,
        )

    def test_service_point_material_details_respect_evaluation_date(self) -> None:
        passport = load_passport_renewal_fixture()
        old_version = replace(
            passport.service_point_versions[0],
            effective_to=date(2026, 12, 31),
        )
        new_version = ServicePointVersionDefinition(
            id="spv.giza_passport_office.synthetic-2027",
            service_point_id=old_version.service_point_id,
            address=LocalizedText(
                ar="عنوان اختباري جديد من 2027",
                en="Synthetic new address from 2027",
            ),
            availability="unknown",
            effective_from=date(2027, 1, 1),
            effective_to=None,
            evidence_link_ids=old_version.evidence_link_ids,
            verification_state="current",
        )
        old_association = replace(
            passport.service_point_associations[0],
            effective_to=date(2026, 12, 31),
        )
        new_association = ProcedureServicePointAssociationDefinition(
            id="spa.passport_renewal.giza_standard.synthetic-2027",
            service_point_version_id=new_version.id,
            applicability=eq(
                "residence_police_jurisdiction",
                "boulak_el_dakrour",
            ),
            effective_from=date(2027, 1, 1),
            effective_to=None,
            evidence_link_ids=old_association.evidence_link_ids,
            verification_state="current",
        )
        variant = replace(
            passport,
            service_point_versions=(old_version, new_version),
            service_point_associations=(old_association, new_association),
        )

        old_result = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        stale_jurisdiction = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2027, 1, 2),
        )
        new_result = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.passport_facts(
                residence_police_jurisdiction="boulak_el_dakrour",
            ),
            locale="en",
            evaluation_date=date(2027, 1, 2),
        )
        self.assertIsInstance(old_result, PlanResult)
        self.assertIsInstance(stale_jurisdiction, PlanResult)
        self.assertIsInstance(new_result, PlanResult)
        old_point = old_result.plan.service_points[0]  # type: ignore[union-attr]
        self.assertEqual(stale_jurisdiction.plan.service_points, ())  # type: ignore[union-attr]
        self.assertEqual(stale_jurisdiction.plan.routing.status, "unresolved")  # type: ignore[union-attr]
        new_point = new_result.plan.service_points[0]  # type: ignore[union-attr]
        self.assertEqual(old_point.id, new_point.id)
        self.assertNotEqual(old_point.version_id, new_point.version_id)
        self.assertNotEqual(old_point.address, new_point.address)
        self.assertEqual(new_point.address, "Synthetic new address from 2027")
        self.assertEqual(old_point.availability, "available")
        self.assertEqual(new_point.availability, "unknown")


if __name__ == "__main__":
    unittest.main()
