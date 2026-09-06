from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from knowledge.evidence_workflow_temporal import load_knowledge_snapshot_as_of
from knowledge.importers.temporary_family_exemption import (
    CURRENT_VERSION_ID,
    HISTORICAL_VERSION_ID,
    import_temporary_family_exemption,
)
from knowledge.publication import publish_procedure_version
from planning import (
    InconclusiveResult,
    NextQuestionResult,
    PlanningInput,
    PlanResult,
    plan_stateless,
)


@override_settings(
    SELECTION_QUESTIONS_REQUIRED=True,
    PLANNING_SCENARIOS_REQUIRED=False,
    PROCEDURE_VERSION_REVIEWS_REQUIRED=False,
)
class TemporaryFamilyExemptionProductionPlanningTests(TestCase):
    def publish_versions(self) -> None:
        author = get_user_model().objects.create_user(username="mil-api-author", is_staff=True)
        publisher = get_user_model().objects.create_user(username="mil-api-publisher")
        versions = import_temporary_family_exemption(author=author)
        for version in versions:
            publish_procedure_version(version.pk, actor=publisher)

    def test_untrusted_basis_does_not_unlock_basis_scoped_guidance(self) -> None:
        self.publish_versions()
        snapshot = load_knowledge_snapshot_as_of(date(2026, 8, 26))
        facts = {
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

        result = plan_stateless(
            snapshot,
            PlanningInput(
                "handle_military_service_paperwork",
                facts,
                "en",
                date(2026, 8, 26),
            ),
        )

        self.assertIsInstance(result, PlanResult)
        assert isinstance(result, PlanResult)
        self.assertEqual(result.procedure_version_id, CURRENT_VERSION_ID)
        self.assertEqual(
            [basis.id for basis in result.eligibility_bases],
            ["family.only_son_living_father"],
        )
        self.assertEqual(
            result.inconclusive_basis_ids,
            ("family.only_son_living_father",),
        )
        checklist_ids = [item.id for item in result.checklist_items]
        self.assertIn("mil.shared.supporting_documents", checklist_ids)
        self.assertNotIn("mil.basis.only_son_living_father", checklist_ids)
        self.assertFalse(any(item.id.startswith("mil.basis.") for item in result.checklist_items))
        self.assertEqual(
            [item.id for item in result.steps],
            ["mil.step.submit_supporting_documents", "mil.step.authority_review"],
        )
        self.assertEqual(result.routing.status, "resolved")
        self.assertEqual(
            [destination.association_id for destination in result.routing.destinations],
            ["spa.mil.giza_region"],
        )
        self.assertEqual(
            [destination.service_point_id for destination in result.routing.destinations],
            ["sp.recruitment_region_giza"],
        )
        self.assertEqual([fee.id for fee in result.fees], ["mil.fee.current"])
        fee = result.fees[0]
        self.assertEqual(fee.value_state, "unknown")
        self.assertIsNone(fee.amount)
        self.assertIsNone(fee.minimum_amount)
        self.assertIsNone(fee.maximum_amount)
        self.assertTrue(fee.current_value_unknown)

    def test_reachability_false_suppresses_father_qualification_questions(self) -> None:
        self.publish_versions()
        snapshot = load_knowledge_snapshot_as_of(date(2026, 8, 26))
        result = plan_stateless(
            snapshot,
            PlanningInput(
                "handle_military_service_paperwork",
                {"application_location": "inside_egypt", "father_alive": False},
                "en",
                date(2026, 8, 26),
            ),
        )

        self.assertIsInstance(result, NextQuestionResult)
        assert isinstance(result, NextQuestionResult)
        self.assertEqual(result.question.id, "q.mil.mother_status")

    def test_march_24_25_amendment_boundary_changes_terrorist_operations_route(self) -> None:
        self.publish_versions()
        facts = {
            "application_location": "inside_egypt",
            "father_alive": False,
            "mother_family_status": "other",
            "unmarried_sisters_requiring_support_count": 0,
            "missing_relative_category": "officer",
            "missing_relative_cause": "terrorist_operations",
            "missing_relative_alive_status": "missing",
            "applicant_largest_eligible_relative_status": "authority_documented_yes",
            "sibling_service_status": "none",
            "residence_governorate": "giza",
        }

        historical = plan_stateless(
            load_knowledge_snapshot_as_of(date(2026, 3, 24)),
            PlanningInput(
                "handle_military_service_paperwork",
                facts,
                "en",
                date(2026, 3, 24),
            ),
        )
        current = plan_stateless(
            load_knowledge_snapshot_as_of(date(2026, 3, 25)),
            PlanningInput(
                "handle_military_service_paperwork",
                facts,
                "en",
                date(2026, 3, 25),
            ),
        )

        self.assertIsInstance(historical, InconclusiveResult)
        assert isinstance(historical, InconclusiveResult)
        self.assertEqual(historical.reason, "no_applicable_eligibility_basis")
        self.assertIsInstance(current, PlanResult)
        assert isinstance(current, PlanResult)
        self.assertEqual(current.procedure_version_id, CURRENT_VERSION_ID)
        self.assertNotEqual(current.procedure_version_id, HISTORICAL_VERSION_ID)
        self.assertEqual(
            [basis.id for basis in current.eligibility_bases],
            ["family.missing_war_or_terror_relative"],
        )
        self.assertEqual(
            current.inconclusive_basis_ids,
            ("family.missing_war_or_terror_relative",),
        )
