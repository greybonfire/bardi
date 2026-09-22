from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from knowledge.evidence_workflow_temporal import load_knowledge_snapshot_as_of
from knowledge.importers.national_id_renewal import import_national_id_renewal
from knowledge.publication import publish_procedure_version
from planning import (
    CasePreparationSuccess,
    PlanningInput,
    PlanResult,
    plan_stateless,
    prepare_case,
)


@override_settings(
    SELECTION_QUESTIONS_REQUIRED=True,
    PLANNING_SCENARIOS_REQUIRED=False,
)
class NationalIdRenewalProductionPlanningTests(TestCase):
    def publish_snapshot(self):  # type: ignore[no-untyped-def]
        author = get_user_model().objects.create_user(username="nid-api-author", is_staff=True)
        publisher = get_user_model().objects.create_user(username="nid-api-publisher")
        version = import_national_id_renewal(author=author)
        publish_procedure_version(version.pk, actor=publisher)
        return load_knowledge_snapshot_as_of(date(2026, 8, 26))

    def test_detached_bilingual_plan_keeps_unknown_fee_and_unresolved_routing(self) -> None:
        snapshot = self.publish_snapshot()
        facts = {
            "application_location": "inside_egypt",
            "national_id_possession_state": "held",
            "national_id_data_change_kind": "none",
            "national_id_expiry_date": date(2026, 5, 1),
            "residence_governorate": "giza",
            "residence_district": "dokki",
        }
        results = tuple(
            plan_stateless(
                snapshot,
                PlanningInput("get_egyptian_national_id", facts, locale, date(2026, 8, 26)),
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
        self.assertEqual(
            [item.id for item in english.checklist_items],
            ["nid.requirement.renew_after_expiry"],
        )
        self.assertNotIn(
            "nid.requirement.previous_card",
            [item.id for item in english.checklist_items],
        )
        self.assertEqual([item.id for item in english.fees], ["nid.fee.ordinary"])
        fee = english.fees[0]
        self.assertEqual(fee.value_state, "unknown")
        self.assertIsNone(fee.amount)
        self.assertIsNone(fee.minimum_amount)
        self.assertIsNone(fee.maximum_amount)
        self.assertTrue(fee.current_value_unknown)
        self.assertEqual(english.routing.status, "unresolved")
        self.assertEqual(english.routing.destinations, ())
        self.assertEqual(english.routing.verification_sources, ())
        route_step = next(
            item for item in english.steps if item.id == "nid.step.resolve_service_location"
        )
        self.assertEqual(
            [source.id for source in route_step.sources],
            ["SRC-PSM-CIVIL-STATUS-SERVICES"],
        )

    def test_imported_deadline_scenarios_use_exact_calendar_month_semantics(self) -> None:
        snapshot = self.publish_snapshot()
        service = next(
            item for item in snapshot.services if item.semantic_id == "get_egyptian_national_id"
        )
        definitions = snapshot.fact_definitions

        exact = prepare_case(
            definitions,
            service,
            {"national_id_expiry_date": date(2026, 5, 26)},
            date(2026, 8, 26),
        )
        self.assertIsInstance(exact, CasePreparationSuccess)
        assert isinstance(exact, CasePreparationSuccess)
        self.assertEqual(exact.prepared_facts.values["renewal_deadline_date"], date(2026, 8, 26))
        self.assertFalse(exact.prepared_facts.values["renewal_deadline_passed"])
        self.assertTrue(exact.prepared_facts.values["card_expired_before_evaluation_date"])

        same_day = prepare_case(
            definitions,
            service,
            {"national_id_expiry_date": date(2026, 5, 31)},
            date(2026, 8, 31),
        )
        self.assertIsInstance(same_day, CasePreparationSuccess)
        assert isinstance(same_day, CasePreparationSuccess)
        self.assertEqual(same_day.prepared_facts.values["renewal_deadline_date"], date(2026, 8, 31))
        self.assertFalse(same_day.prepared_facts.values["renewal_deadline_passed"])

        # May 31 -> August 31 preserves the day; August -> November actually clamps.
        for evaluation_date, passed in ((date(2026, 11, 30), False), (date(2026, 12, 1), True)):
            clamped = prepare_case(
                definitions,
                service,
                {"national_id_expiry_date": date(2026, 8, 31)},
                evaluation_date,
            )
            self.assertIsInstance(clamped, CasePreparationSuccess)
            assert isinstance(clamped, CasePreparationSuccess)
            self.assertEqual(
                clamped.prepared_facts.values["renewal_deadline_date"], date(2026, 11, 30)
            )
            self.assertIs(clamped.prepared_facts.values["renewal_deadline_passed"], passed)

        for expiry, expired in ((date(2026, 8, 26), False), (date(2026, 8, 25), True)):
            prepared = prepare_case(
                definitions,
                service,
                {"national_id_expiry_date": expiry},
                date(2026, 8, 26),
            )
            assert isinstance(prepared, CasePreparationSuccess)
            self.assertIs(
                prepared.prepared_facts.values["card_expired_before_evaluation_date"], expired
            )
        next_day = prepare_case(
            definitions,
            service,
            {"national_id_expiry_date": date(2026, 5, 26)},
            date(2026, 8, 27),
        )
        assert isinstance(next_day, CasePreparationSuccess)
        self.assertTrue(next_day.prepared_facts.values["renewal_deadline_passed"])
