from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from prototype.bardi_prototype.contracts import (
    EvidenceDiscrepancy,
    EvidenceLink,
    InconclusiveResult,
    InvalidResult,
    PlanResult,
    Source,
)
from prototype.bardi_prototype.evaluator import all_of, eq
from prototype.bardi_prototype.fixtures import load_researched_catalog
from prototype.bardi_prototype.scenario import run_scenario
from prototype.bardi_prototype.validation import validate_catalog


class ProcedureVersionFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_researched_catalog()

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

    def military_facts(self) -> dict[str, object]:
        return {
            "application_location": "inside_egypt",
            "father_alive": True,
            "other_living_sons_of_father_count": 0,
            "father_unable_to_earn_status": "not_documented_unable",
            "mother_family_status": "other",
            "unmarried_sisters_requiring_support_count": 0,
            "missing_relative_category": "none",
            "sibling_service_status": "none",
        }

    def test_military_version_boundary_is_inclusive_and_rule_snapshot_is_selected(self) -> None:
        terrorist_facts = self.military_facts()
        terrorist_facts.update(
            {
                "missing_relative_category": "officer",
                "missing_relative_cause": "terrorist_operations",
                "missing_relative_alive_status": "missing",
                "applicant_largest_eligible_relative_status": "authority_documented_yes",
            }
        )
        before = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts=terrorist_facts,
            locale="en",
            evaluation_date=date(2026, 3, 24),
        )
        after = run_scenario(
            knowledge=self.catalog,
            goal_id="handle_military_service_paperwork",
            facts=terrorist_facts,
            locale="en",
            evaluation_date=date(2026, 3, 25),
        )
        self.assertIsInstance(before, PlanResult)
        self.assertIsInstance(after, PlanResult)
        self.assertEqual(
            before.plan.procedure_version_id,
            "temporary_family_exemption_from_military_service.research-2026-03-24",
        )
        self.assertEqual(
            after.plan.procedure_version_id,
            "temporary_family_exemption_from_military_service.research-2026-08-26",
        )
        self.assertEqual(
            tuple(basis.id for basis in before.plan.eligibility_bases),
            ("family.only_son_living_father",),
        )
        self.assertEqual(
            tuple(basis.id for basis in after.plan.eligibility_bases),
            (
                "family.only_son_living_father",
                "family.missing_war_or_terror_relative",
            ),
        )
        # These researched legal Bases remain candidates, not established
        # eligibility, until specialist re-verification occurs.
        self.assertEqual(
            before.plan.inconclusive_basis_ids,
            ("family.only_son_living_father",),
        )
        self.assertEqual(
            after.plan.inconclusive_basis_ids,
            (
                "family.missing_war_or_terror_relative",
                "family.only_son_living_father",
            ),
        )
        self.assertNotIn(
            "mil.basis.missing_war_or_terror_relative",
            {item.id for item in after.plan.historical_claims},
        )
        # Operational evidence retrieved in August must not be presented as
        # historical guidance for a March evaluation date.
        self.assertNotIn(
            "mil.shared.supporting_documents",
            {item.id for item in before.plan.historical_claims},
        )
        self.assertIn(
            "mil.shared.supporting_documents",
            before.plan.inconclusive_claim_ids,
        )

    def test_future_published_versions_are_upcoming_but_drafts_are_not(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        passport = replace(
            passport,
            procedure=replace(
                passport.procedure,
                effective_to=date(2026, 12, 31),
            ),
        )
        future = replace(
            passport,
            procedure=replace(
                passport.procedure,
                version_id="passport.future",
                effective_from=date(2027, 1, 1),
                effective_to=None,
            ),
            service_point_associations=tuple(
                replace(item, procedure_version_id="passport.future")
                for item in passport.service_point_associations
            ),
        )
        draft = replace(
            future,
            procedure=replace(
                future.procedure,
                version_id="passport.draft",
                publication_state="draft",
            ),
            service_point_associations=tuple(
                replace(item, procedure_version_id="passport.draft")
                for item in future.service_point_associations
            ),
        )
        pid = passport.procedure.procedure_id
        catalog = replace(
            self.catalog,
            fixtures={**self.catalog.fixtures, pid: passport},
            versioned_fixtures={pid: (passport, future, draft)},
        )
        result = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        self.assertEqual(result.plan.procedure_version_id, passport.procedure.version_id)
        self.assertEqual(
            tuple(item.procedure_version_id for item in result.plan.upcoming_versions),
            ("passport.future",),
        )

    def test_no_current_version_reports_upcoming_without_leaking_draft(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        future = replace(
            passport,
            procedure=replace(
                passport.procedure,
                version_id="passport.future.only",
                effective_from=date(2027, 1, 1),
            ),
            service_point_associations=tuple(
                replace(item, procedure_version_id="passport.future.only")
                for item in passport.service_point_associations
            ),
        )
        draft = replace(
            future,
            procedure=replace(
                future.procedure,
                version_id="passport.draft.only",
                publication_state="draft",
            ),
            service_point_associations=tuple(
                replace(item, procedure_version_id="passport.draft.only")
                for item in future.service_point_associations
            ),
        )
        pid = passport.procedure.procedure_id
        catalog = replace(
            self.catalog,
            fixtures={**self.catalog.fixtures, pid: future},
            versioned_fixtures={pid: (future, draft)},
        )
        result = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, InconclusiveResult)
        self.assertEqual(result.reason_code, "procedure_version_not_yet_effective")
        self.assertEqual(
            tuple(item.procedure_version_id for item in result.upcoming_versions),
            ("passport.future.only",),
        )

    def test_overlapping_published_intervals_are_invalid(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        second = replace(
            passport,
            procedure=replace(
                passport.procedure,
                version_id="passport.overlap",
                effective_from=date(2026, 1, 1),
            ),
            service_point_associations=tuple(
                replace(item, procedure_version_id="passport.overlap")
                for item in passport.service_point_associations
            ),
        )
        pid = passport.procedure.procedure_id
        catalog = replace(
            self.catalog,
            fixtures={**self.catalog.fixtures, pid: passport},
            versioned_fixtures={pid: (passport, second)},
        )
        self.assertTrue(
            any(
                code.startswith("overlapping_published_procedure_versions:")
                for code in validate_catalog(catalog)
            )
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
        self.assertTrue(
            any(
                code.startswith("overlapping_published_procedure_versions:")
                for code in result.diagnostic_codes
            )
        )

    def test_withdrawn_version_requires_explicit_historical_selector(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        withdrawn = replace(
            passport,
            procedure=replace(
                passport.procedure,
                version_id="passport.withdrawn",
                publication_state="withdrawn",
            ),
            service_point_associations=tuple(
                replace(item, procedure_version_id="passport.withdrawn")
                for item in passport.service_point_associations
            ),
        )
        pid = passport.procedure.procedure_id
        catalog = replace(
            self.catalog,
            fixtures={**self.catalog.fixtures, pid: withdrawn},
            versioned_fixtures={pid: (withdrawn,)},
        )
        ordinary = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        historical = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
            historical_version_id="passport.withdrawn",
        )
        self.assertIsInstance(ordinary, InconclusiveResult)
        self.assertIsInstance(historical, PlanResult)
        self.assertTrue(historical.plan.freshness.historical)
        self.assertEqual(historical.plan.freshness.publication_state, "withdrawn")

    def test_goal_selection_is_independent_of_version_specific_applicability(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        pid = passport.procedure.procedure_id
        historical = replace(
            passport,
            procedure=replace(
                passport.procedure,
                version_id="passport.historical.selector-test",
                effective_from=None,
                effective_to=date(2026, 3, 24),
            ),
            service_point_associations=tuple(
                replace(
                    item,
                    procedure_version_id="passport.historical.selector-test",
                )
                for item in passport.service_point_associations
            ),
        )
        current = replace(
            passport,
            procedure=replace(
                passport.procedure,
                version_id="passport.current.selector-test",
                effective_from=date(2026, 3, 25),
                applicability=all_of(
                    passport.procedure.applicability,
                    eq("service_level", "urgent"),
                ),
            ),
            service_point_associations=tuple(
                replace(
                    item,
                    procedure_version_id="passport.current.selector-test",
                )
                for item in passport.service_point_associations
            ),
        )
        catalog = replace(
            self.catalog,
            fixtures={**self.catalog.fixtures, pid: current},
            versioned_fixtures={pid: (historical, current)},
        )
        result = run_scenario(
            knowledge=catalog,
            goal_id="get_egyptian_passport",
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 3, 24),
        )
        self.assertIsInstance(result, PlanResult)
        self.assertEqual(
            result.plan.procedure_version_id,
            "passport.historical.selector-test",
        )

    def test_stale_consequential_claim_is_local_and_keeps_reliable_claims(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        stale = replace(
            passport.claims[0],
            verification_state="stale",
            verified_on=date(2026, 7, 1),
        )
        variant = replace(passport, claims=(stale, *passport.claims[1:]))
        result = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        self.assertNotIn(stale.id, {item.id for item in result.plan.checklist})
        self.assertIn(stale.id, result.plan.inconclusive_claim_ids)
        historical = next(
            item for item in result.plan.historical_claims if item.id == stale.id
        )
        self.assertEqual(historical.verification_state, "stale")
        self.assertEqual(historical.verified_on, date(2026, 7, 1))
        self.assertTrue(historical.current_value_unknown)
        self.assertIn(
            "passport.requirement.photos",
            {item.id for item in result.plan.checklist},
        )

    def test_needs_reverification_candidate_is_not_historical(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        result = run_scenario(
            knowledge=passport,
            goal_id=passport.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        candidate_id = "passport.requirement.previous_passport"
        self.assertNotIn(candidate_id, {item.id for item in result.plan.checklist})
        self.assertNotIn(
            candidate_id,
            {item.id for item in result.plan.historical_claims},
        )
        self.assertNotIn(candidate_id, result.plan.inconclusive_claim_ids)

    def test_field_guidance_discrepancy_preserves_authority_and_is_local(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        claim = passport.claims[0]
        official_link_id = claim.evidence_link_ids[0]
        official_source_id = passport.evidence_links[official_link_id].source_ids[0]
        field_source = Source(
            id="SRC-FIELD-PASSPORT-NID",
            authority="Giza passport office field observation",
            title="Observed National ID handling",
            retrieved_on=date(2026, 8, 25),
            classification="field_report",
            observed_on=date(2026, 8, 24),
            context="Observed at the Giza office; conflicts with the researched official requirement.",
        )
        field_link = EvidenceLink(
            id="EL-FIELD-PASSPORT-NID",
            source_ids=(field_source.id,),
            exact_passage="Observed handling differed from the official requirement.",
            applicability_context="Field observation only; not authority guidance.",
            retrieved_on=date(2026, 8, 25),
        )
        variant = replace(
            passport,
            sources={**passport.sources, field_source.id: field_source},
            evidence_links={
                **passport.evidence_links,
                field_link.id: field_link,
            },
            discrepancies=(
                EvidenceDiscrepancy(
                    id="disc.field.passport.nid",
                    claim_id=claim.id,
                    evidence_link_ids=(official_link_id, field_link.id),
                    status="open",
                    rationale="Official requirement conflicts with a field observation.",
                    consequence="disputed",
                ),
            ),
        )
        result = run_scenario(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.passport_facts(),
            locale="en",
            evaluation_date=date(2026, 8, 25),
        )
        self.assertIsInstance(result, PlanResult)
        self.assertIn(claim.id, result.plan.inconclusive_claim_ids)
        self.assertNotIn(claim.id, {item.id for item in result.plan.checklist})
        self.assertNotIn(
            claim.id,
            {item.id for item in result.plan.historical_claims},
        )
        self.assertIn(
            "passport.requirement.photos",
            {item.id for item in result.plan.checklist},
        )
        self.assertEqual(variant.sources[official_source_id].classification, "official")
        self.assertEqual(variant.sources[field_source.id].classification, "field_report")
        self.assertFalse(hasattr(result.plan, "discrepancies"))
        self.assertNotIn(
            "Official requirement conflicts with a field observation.",
            repr(result),
        )

    def test_historical_claim_projection_has_arabic_english_identity_parity(self) -> None:
        passport = self.catalog.fixtures["ordinary_domestic_passport_renewal"]
        stale = replace(
            passport.claims[0],
            verification_state="stale",
            verified_on=date(2026, 7, 1),
        )
        variant = replace(passport, claims=(stale, *passport.claims[1:]))
        request = dict(
            knowledge=variant,
            goal_id=variant.goal.id,
            facts=self.passport_facts(),
            evaluation_date=date(2026, 8, 25),
        )
        en = run_scenario(locale="en", **request)
        ar = run_scenario(locale="ar", **request)
        self.assertIsInstance(en, PlanResult)
        self.assertIsInstance(ar, PlanResult)
        self.assertEqual(
            tuple(item.id for item in en.plan.historical_claims),
            tuple(item.id for item in ar.plan.historical_claims),
        )
        self.assertEqual(
            en.plan.historical_claims[0].sources,
            ar.plan.historical_claims[0].sources,
        )
        self.assertNotEqual(
            en.plan.historical_claims[0].text,
            ar.plan.historical_claims[0].text,
        )


if __name__ == "__main__":
    unittest.main()
