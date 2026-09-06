from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from knowledge.evidence_workflow_temporal import load_knowledge_snapshot_as_of
from knowledge.importers.passport_renewal import import_passport_renewal
from knowledge.publication import publish_procedure_version
from planning import PlanningInput, PlanResult, plan_stateless


@override_settings(
    SELECTION_QUESTIONS_REQUIRED=True,
    PLANNING_SCENARIOS_REQUIRED=False,
    PROCEDURE_VERSION_REVIEWS_REQUIRED=False,
)
class PassportRenewalProductionPlanningTests(TestCase):
    def test_detached_bilingual_plan_preserves_ids_fees_and_giza_only(self) -> None:
        author = get_user_model().objects.create_user(username="passport-api-author", is_staff=True)
        publisher = get_user_model().objects.create_user(username="passport-api-publisher")
        version = import_passport_renewal(author=author)
        publish_procedure_version(version.pk, actor=publisher)
        snapshot = load_knowledge_snapshot_as_of(date(2026, 8, 25))
        facts = {
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
        results = tuple(
            plan_stateless(
                snapshot,
                PlanningInput("get_egyptian_passport", facts, locale, date(2026, 8, 25)),
            )
            for locale in ("ar", "en")
        )
        self.assertTrue(all(isinstance(result, PlanResult) for result in results))
        arabic, english = results
        assert isinstance(arabic, PlanResult) and isinstance(english, PlanResult)
        self.assertEqual(
            [item.id for item in arabic.checklist_items],
            [item.id for item in english.checklist_items],
        )
        self.assertNotIn(
            "passport.requirement.previous_passport",
            [item.id for item in english.checklist_items],
        )
        self.assertEqual([item.id for item in english.fees], ["passport.fee.base"])
        self.assertEqual(
            [item.association_id for item in english.routing.destinations],
            ["spa.passport_renewal.giza_standard"],
        )
