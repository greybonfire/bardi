from __future__ import annotations

import importlib
import json
from datetime import UTC, date, datetime
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase, override_settings, tag
from knowledge.evidence_workflow import (
    open_evidence_discrepancy,
    resolve_evidence_discrepancy,
)
from knowledge.evidence_workflow_temporal import (
    EvidenceDiscrepancyTransition,
    load_consistent_service_knowledge_snapshot_as_of,
    load_knowledge_snapshot_as_of,
)
from knowledge.importers.national_id_renewal import (
    import_national_id_renewal,
)
from knowledge.importers.passport_renewal import (
    VERSION_ID as PASSPORT_VERSION_ID,
)
from knowledge.importers.passport_renewal import (
    import_passport_renewal,
)
from knowledge.importers.temporary_family_exemption import (
    CURRENT_VERSION_ID as MILITARY_CURRENT_VERSION_ID,
)
from knowledge.importers.temporary_family_exemption import (
    HISTORICAL_VERSION_ID as MILITARY_HISTORICAL_VERSION_ID,
)
from knowledge.importers.temporary_family_exemption import (
    import_temporary_family_exemption,
)
from knowledge.models import EvidenceLink, FactDefinition
from knowledge.planning_scenarios import PlanningScenario
from knowledge.publication import publish_procedure_version
from planning import CasePreparationSuccess, KnowledgeSnapshot, PlanningInput, prepare_case

from api.application import execute_planning

PASSPORT_SERVICE_ID = "get_egyptian_passport"
PASSPORT_PROCEDURE_ID = "ordinary_domestic_passport_renewal"
NATIONAL_ID_SERVICE_ID = "get_egyptian_national_id"
NATIONAL_ID_PROCEDURE_ID = "ordinary_domestic_national_id_renewal"
MILITARY_SERVICE_ID = "handle_military_service_paperwork"
MILITARY_PROCEDURE_ID = "temporary_family_exemption_from_military_service"

PASSPORT_PLAN_FACTS: dict[str, object] = {
    "citizenship": "egyptian",
    "application_location": "inside_egypt",
    "existing_passport_state": "expired",
    "passport_class": "ordinary",
    "birth_date": "1995-06-10",
    "sex": "female",
    "is_student": False,
    "service_level": "standard",
    "residence_police_jurisdiction": "giza",
}
NATIONAL_ID_PLAN_FACTS: dict[str, object] = {
    "application_location": "inside_egypt",
    "national_id_possession_state": "held",
    "national_id_data_change_kind": "none",
    "national_id_expiry_date": "2026-05-01",
    "residence_governorate": "giza",
    "residence_district": "dokki",
}
MILITARY_ONLY_SON_FACTS: dict[str, object] = {
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


@tag("production_acceptance")
@override_settings(
    SELECTION_QUESTIONS_REQUIRED=True,
    PLANNING_SCENARIOS_REQUIRED=False,
    PROCEDURE_VERSION_REVIEWS_REQUIRED=False,
)
class CrossFamilyProductionParityAcceptanceTests(TransactionTestCase):
    serialized_rollback = True

    @classmethod
    def _fixture_setup(cls) -> None:
        # Ordinary TransactionTestCase teardown can leave post_migrate metadata behind.
        # Remove all test state before restoring the complete migrated snapshot, including
        # the migration-seeded facts required by the acceptance importers.
        for db_name in cls._databases_names(include_mirrors=False):  # type: ignore[attr-defined]
            connection = connections[db_name]
            if cls.serialized_rollback and hasattr(connection, "_test_serialized_contents"):
                call_command(
                    "flush",
                    verbosity=0,
                    interactive=False,
                    database=db_name,
                    reset_sequences=False,
                    inhibit_post_migrate=True,
                )
        super()._fixture_setup()  # type: ignore[misc]

    def setUp(self) -> None:
        migration = importlib.import_module("knowledge.migrations.0001_initial")
        for key, kind, enum_values, minimum, derived in migration.SEEDED_FACTS:
            with self.subTest(fact=key):
                fact = FactDefinition.objects.get(key=key)
                self.assertEqual(fact.kind, kind)
                self.assertEqual(fact.enum_values, enum_values)
                self.assertEqual(fact.minimum, minimum)
                self.assertEqual(fact.derived, derived)
                self.assertTrue(fact.is_published)

        author = get_user_model().objects.create_user(
            username="cross-family-acceptance-author",
            is_staff=True,
        )
        publisher = get_user_model().objects.create_user(
            username="cross-family-acceptance-publisher"
        )
        self.actor = publisher
        versions = [
            import_passport_renewal(author=author),
            import_national_id_renewal(author=author),
            *import_temporary_family_exemption(author=author),
        ]
        for version in versions:
            publish_procedure_version(version.pk, actor=publisher)

    def post(
        self,
        service_id: str,
        facts: dict[str, object],
        *,
        locale: str,
        evaluation_date: str,
    ) -> dict[str, Any]:
        response = self.client.post(
            "/v1/planning",
            data=json.dumps(
                {
                    "service_id": service_id,
                    "facts": facts,
                    "locale": locale,
                    "evaluation_context": {"evaluation_date": evaluation_date},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        assert isinstance(body, dict)
        return body

    @staticmethod
    def semantic_projection(body: dict[str, Any]) -> dict[str, Any]:
        result_type = body["type"]
        if result_type == "next_question":
            question = body["question"]
            return {
                "type": result_type,
                "service_id": body["service_id"],
                "question_id": question["id"],
                "answers": [
                    {
                        "key": answer["key"],
                        "kind": answer["kind"],
                        "enum_options": answer["enum_options"],
                        "minimum": answer["minimum"],
                    }
                    for answer in question["answers"]
                ],
            }
        if result_type == "inconclusive":
            return {"type": result_type, "reason": body["reason"]}
        if result_type == "invalid":
            return {"type": result_type, "diagnostics": body["diagnostics"]}
        assert result_type == "plan"
        routing = body["routing"]
        return {
            "type": result_type,
            "service_id": body["service_id"],
            "procedure_id": body["procedure_id"],
            "procedure_version_id": body["procedure_version_id"],
            "checklist_item_ids": [item["id"] for item in body["checklist_items"]],
            "step_ids": [item["id"] for item in body["steps"]],
            "warning_ids": [item["id"] for item in body["warnings"]],
            "fee_ids": [item["id"] for item in body["fees"]],
            "eligibility_basis_ids": [item["id"] for item in body["eligibility_bases"]],
            "inconclusive_basis_ids": body["inconclusive_basis_ids"],
            "routing_status": routing["status"],
            "routing_association_ids": [item["association_id"] for item in routing["destinations"]],
            "routing_service_point_ids": [
                item["service_point_id"] for item in routing["destinations"]
            ],
        }

    def assert_locale_semantic_parity(
        self,
        service_id: str,
        facts: dict[str, object],
        *,
        evaluation_date: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        arabic = self.post(
            service_id,
            facts,
            locale="ar",
            evaluation_date=evaluation_date,
        )
        english = self.post(
            service_id,
            facts,
            locale="en",
            evaluation_date=evaluation_date,
        )
        self.assertEqual(self.semantic_projection(arabic), self.semantic_projection(english))
        return arabic, english

    def test_scoped_and_full_public_responses_match_imported_scenarios(self) -> None:
        scenarios = (
            (PASSPORT_SERVICE_ID, PASSPORT_PLAN_FACTS, date(2026, 8, 24)),
            (PASSPORT_SERVICE_ID, PASSPORT_PLAN_FACTS, date(2026, 8, 25)),
            (NATIONAL_ID_SERVICE_ID, NATIONAL_ID_PLAN_FACTS, date(2026, 8, 26)),
            (MILITARY_SERVICE_ID, MILITARY_ONLY_SON_FACTS, date(2026, 8, 26)),
        )
        for service_id, facts, evaluation_date in scenarios:
            with self.subTest(service_id=service_id):
                full = load_knowledge_snapshot_as_of(evaluation_date)
                scoped = load_consistent_service_knowledge_snapshot_as_of(
                    service_id, evaluation_date
                )
                planning_input = PlanningInput(service_id, facts, "en", evaluation_date)

                def full_loader(snapshot: KnowledgeSnapshot = full) -> KnowledgeSnapshot:
                    return snapshot

                def scoped_loader(snapshot: KnowledgeSnapshot = scoped) -> KnowledgeSnapshot:
                    return snapshot

                self.assertEqual(
                    execute_planning(planning_input, snapshot_loader=full_loader),
                    execute_planning(planning_input, snapshot_loader=scoped_loader),
                )

    def test_scoped_and_full_public_responses_match_every_imported_planning_scenario(self) -> None:
        full_snapshots: dict[date, KnowledgeSnapshot] = {}
        scoped_snapshots: dict[tuple[str, date], KnowledgeSnapshot] = {}
        scenarios = tuple(
            PlanningScenario.objects.select_related(
                "procedure_version__procedure__primary_service"
            ).order_by("pk")
        )
        self.assertGreater(len(scenarios), 10)
        for scenario in scenarios:
            expected_identifiers = cast(dict[str, Any], scenario.expected_identifiers)
            expected_diagnostics = cast(list[str], scenario.expected_diagnostics)
            evaluation_date = date.fromisoformat(scenario.evaluation_context["evaluation_date"])
            service_id = scenario.procedure_version.procedure.primary_service.semantic_id
            full = full_snapshots.setdefault(
                evaluation_date, load_knowledge_snapshot_as_of(evaluation_date)
            )
            scoped = scoped_snapshots.setdefault(
                (service_id, evaluation_date),
                load_consistent_service_knowledge_snapshot_as_of(service_id, evaluation_date),
            )
            planning_input = PlanningInput(
                service_id,
                scenario.source_facts,
                scenario.evaluation_context["locale"],
                evaluation_date,
            )

            def full_loader(snapshot: KnowledgeSnapshot = full) -> KnowledgeSnapshot:
                return snapshot

            def scoped_loader(snapshot: KnowledgeSnapshot = scoped) -> KnowledgeSnapshot:
                return snapshot

            full_response = cast(
                dict[str, Any], execute_planning(planning_input, snapshot_loader=full_loader)
            )
            scoped_response = cast(
                dict[str, Any], execute_planning(planning_input, snapshot_loader=scoped_loader)
            )
            with self.subTest(scenario=scenario.name):
                self.assertEqual(scoped_response, full_response)
                self.assertEqual(full_response["type"], scenario.expected_result_family)
                if scenario.expected_result_family == "next_question":
                    self.assertEqual(
                        full_response["question"]["id"],
                        expected_identifiers["question_id"],
                    )
                elif scenario.expected_result_family == "inconclusive":
                    self.assertEqual(full_response["reason"], expected_identifiers["reason"])
                elif scenario.expected_result_family == "invalid":
                    self.assertEqual(
                        [item["code"] for item in full_response["diagnostics"]],
                        expected_diagnostics,
                    )
                else:
                    identifier_values = {
                        "procedure_version_id": full_response["procedure_version_id"],
                        "checklist_item_ids": [
                            item["id"] for item in full_response["checklist_items"]
                        ],
                        "step_ids": [item["id"] for item in full_response["steps"]],
                        "warning_ids": [item["id"] for item in full_response["warnings"]],
                        "fee_ids": [item["id"] for item in full_response["fees"]],
                        "routing_status": full_response["routing"]["status"],
                        "routing_association_ids": [
                            item["association_id"]
                            for item in full_response["routing"]["destinations"]
                        ],
                    }
                    for key, expected in expected_identifiers.items():
                        if key in identifier_values:
                            self.assertEqual(identifier_values[key], expected)

    def test_temporal_full_scoped_comparison_separates_before_open_open_and_resolved(self) -> None:
        link = EvidenceLink.objects.get(
            checklist_item__semantic_id="passport.requirement.national_id"
        )
        discrepancy = open_evidence_discrepancy(
            anchor_evidence_link=link,
            evidence_links=(link,),
            rationale="Imported-scenario temporal comparison.",
            actor=self.actor,
            outcome_state="disputed",
        )
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.OPENED,
        ).update(occurred_at=datetime(2026, 8, 26, tzinfo=UTC))
        resolve_evidence_discrepancy(
            discrepancy.pk,
            outcome_state="current",
            resolution="Imported-scenario temporal comparison resolved.",
            actor=self.actor,
        )
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.RESOLVED,
        ).update(occurred_at=datetime(2026, 8, 28, tzinfo=UTC))

        facts = PASSPORT_PLAN_FACTS
        for evaluation_date, expected_state in (
            (date(2026, 8, 25), "current"),
            (date(2026, 8, 26), "disputed"),
            (date(2026, 8, 28), "current"),
        ):
            with self.subTest(evaluation_date=evaluation_date):
                full = load_knowledge_snapshot_as_of(evaluation_date)
                scoped = load_consistent_service_knowledge_snapshot_as_of(
                    PASSPORT_SERVICE_ID, evaluation_date
                )
                planning_input = PlanningInput(PASSPORT_SERVICE_ID, facts, "en", evaluation_date)

                def full_loader(snapshot: KnowledgeSnapshot = full) -> KnowledgeSnapshot:
                    return snapshot

                def scoped_loader(snapshot: KnowledgeSnapshot = scoped) -> KnowledgeSnapshot:
                    return snapshot

                self.assertEqual(
                    execute_planning(planning_input, snapshot_loader=full_loader),
                    execute_planning(planning_input, snapshot_loader=scoped_loader),
                )
                scoped_item = next(
                    item
                    for version in scoped.procedure_versions
                    for item in version.checklist_items
                    if item.semantic_id == "passport.requirement.national_id"
                )
                self.assertEqual(scoped_item.verification_state, expected_state)

    def test_public_result_families_are_cross_family_bilingual(self) -> None:
        services_response = self.client.get("/v1/services")
        self.assertEqual(services_response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in services_response.json()["services"]],
            sorted((PASSPORT_SERVICE_ID, NATIONAL_ID_SERVICE_ID, MILITARY_SERVICE_ID)),
        )

        cases: tuple[
            tuple[str, str, dict[str, object], str, str, str],
            ...,
        ] = (
            (
                "passport-question",
                PASSPORT_SERVICE_ID,
                {},
                "2026-08-25",
                "next_question",
                "q.citizenship",
            ),
            (
                "passport-plan",
                PASSPORT_SERVICE_ID,
                PASSPORT_PLAN_FACTS,
                "2026-08-25",
                "plan",
                PASSPORT_PROCEDURE_ID,
            ),
            (
                "passport-inconclusive",
                PASSPORT_SERVICE_ID,
                {"application_location": "outside_egypt"},
                "2026-08-25",
                "inconclusive",
                "no_matching_researched_procedure",
            ),
            (
                "passport-invalid",
                PASSPORT_SERVICE_ID,
                {"birth_date": None},
                "2026-08-25",
                "invalid",
                "invalid_fact_value",
            ),
            (
                "national-id-question",
                NATIONAL_ID_SERVICE_ID,
                {},
                "2026-08-26",
                "next_question",
                "q.nid.application_location",
            ),
            (
                "national-id-plan",
                NATIONAL_ID_SERVICE_ID,
                NATIONAL_ID_PLAN_FACTS,
                "2026-08-26",
                "plan",
                NATIONAL_ID_PROCEDURE_ID,
            ),
            (
                "national-id-inconclusive",
                NATIONAL_ID_SERVICE_ID,
                {"application_location": "outside_egypt"},
                "2026-08-26",
                "inconclusive",
                "no_matching_researched_procedure",
            ),
            (
                "national-id-invalid",
                NATIONAL_ID_SERVICE_ID,
                {
                    "application_location": "inside_egypt",
                    "national_id_possession_state": "none",
                    "national_id_expiry_date": "2026-05-01",
                },
                "2026-08-26",
                "invalid",
                "contradictory_facts",
            ),
            (
                "military-question",
                MILITARY_SERVICE_ID,
                {"application_location": "inside_egypt"},
                "2026-08-26",
                "next_question",
                "q.mil.father_alive",
            ),
            (
                "military-plan",
                MILITARY_SERVICE_ID,
                MILITARY_ONLY_SON_FACTS,
                "2026-08-26",
                "plan",
                MILITARY_PROCEDURE_ID,
            ),
            (
                "military-inconclusive",
                MILITARY_SERVICE_ID,
                {"application_location": "outside_egypt"},
                "2026-08-26",
                "inconclusive",
                "no_matching_researched_procedure",
            ),
            (
                "military-invalid",
                MILITARY_SERVICE_ID,
                {
                    "application_location": "inside_egypt",
                    "missing_relative_category": "none",
                    "missing_relative_cause": "war_operations",
                },
                "2026-08-26",
                "invalid",
                "contradictory_facts",
            ),
        )

        for name, service_id, facts, evaluation_date, family, stable_value in cases:
            with self.subTest(case=name):
                arabic, english = self.assert_locale_semantic_parity(
                    service_id,
                    facts,
                    evaluation_date=evaluation_date,
                )
                self.assertEqual(arabic["type"], family)
                self.assertEqual(english["type"], family)
                if family == "next_question":
                    self.assertEqual(english["question"]["id"], stable_value)
                elif family == "plan":
                    self.assertEqual(english["procedure_id"], stable_value)
                elif family == "inconclusive":
                    self.assertEqual(english["reason"], stable_value)
                else:
                    self.assertTrue(
                        any(
                            diagnostic["code"] == stable_value
                            for diagnostic in english["diagnostics"]
                        )
                    )

    def test_all_six_military_basis_branches_are_non_ranked_bilingual_candidates(self) -> None:
        false_branches: dict[str, object] = {
            "father_alive": False,
            "mother_family_status": "other",
            "unmarried_sisters_requiring_support_count": 0,
            "missing_relative_category": "none",
            "sibling_service_status": "none",
        }
        branches: tuple[tuple[str, dict[str, object], str], ...] = (
            (
                "family.only_son_living_father",
                MILITARY_ONLY_SON_FACTS,
                "spa.mil.giza_region",
            ),
            (
                "family.support_father_or_incapable_brothers",
                {
                    **MILITARY_ONLY_SON_FACTS,
                    "other_living_sons_of_father_count": 1,
                    "father_unable_to_earn_status": "authority_documented_unable",
                },
                "spa.mil.giza_region",
            ),
            (
                "family.support_mother",
                {
                    "application_location": "inside_egypt",
                    **false_branches,
                    "mother_family_status": "widowed",
                    "residence_governorate": "dakahlia",
                },
                "spa.mil.mansoura_region",
            ),
            (
                "family.support_unmarried_sisters",
                {
                    "application_location": "inside_egypt",
                    **false_branches,
                    "unmarried_sisters_requiring_support_count": 1,
                    "residence_governorate": "sharqia",
                },
                "spa.mil.zagazig_region",
            ),
            (
                "family.missing_war_or_terror_relative",
                {
                    "application_location": "inside_egypt",
                    **false_branches,
                    "missing_relative_category": "citizen",
                    "missing_relative_cause": "war_operations",
                    "missing_relative_alive_status": "missing",
                    "applicant_largest_eligible_relative_status": "authority_documented_yes",
                    "residence_governorate": "giza",
                },
                "spa.mil.giza_region",
            ),
            (
                "family.sibling_current_service",
                {
                    "application_location": "inside_egypt",
                    **false_branches,
                    "sibling_service_status": "compulsory_service",
                    "applicant_eldest_remaining_brother_status": "authority_documented_yes",
                    "article7_third_exclusion_status": "none_documented",
                    "residence_governorate": "giza",
                },
                "spa.mil.giza_region",
            ),
        )

        for basis_id, facts, route_id in branches:
            with self.subTest(basis=basis_id):
                _, english = self.assert_locale_semantic_parity(
                    MILITARY_SERVICE_ID,
                    facts,
                    evaluation_date="2026-08-26",
                )
                self.assertEqual(english["type"], "plan")
                self.assertEqual(english["procedure_version_id"], MILITARY_CURRENT_VERSION_ID)
                self.assertEqual(
                    [item["id"] for item in english["eligibility_bases"]],
                    [basis_id],
                )
                self.assertEqual(english["inconclusive_basis_ids"], [basis_id])
                self.assertEqual(
                    [item["association_id"] for item in english["routing"]["destinations"]],
                    [route_id],
                )

    def test_temporal_boundaries_fail_closed_without_backdating_research(self) -> None:
        passport_before = self.post(
            PASSPORT_SERVICE_ID,
            PASSPORT_PLAN_FACTS,
            locale="en",
            evaluation_date="2026-08-24",
        )
        passport_effective = self.post(
            PASSPORT_SERVICE_ID,
            PASSPORT_PLAN_FACTS,
            locale="en",
            evaluation_date="2026-08-25",
        )
        self.assertEqual(passport_before["type"], "inconclusive")
        self.assertEqual(passport_effective["type"], "plan")
        self.assertEqual(passport_effective["procedure_version_id"], PASSPORT_VERSION_ID)

        terrorist_facts: dict[str, object] = {
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
        march_24 = self.post(
            MILITARY_SERVICE_ID,
            terrorist_facts,
            locale="en",
            evaluation_date="2026-03-24",
        )
        march_25 = self.post(
            MILITARY_SERVICE_ID,
            terrorist_facts,
            locale="en",
            evaluation_date="2026-03-25",
        )
        self.assertEqual(march_24["type"], "inconclusive")
        self.assertEqual(march_24["reason"], "no_applicable_eligibility_basis")
        self.assertEqual(march_25["type"], "plan")
        self.assertEqual(march_25["procedure_version_id"], MILITARY_CURRENT_VERSION_ID)
        self.assertNotEqual(march_25["procedure_version_id"], MILITARY_HISTORICAL_VERSION_ID)
        self.assertEqual(march_25["routing"]["status"], "unresolved")
        self.assertEqual(march_25["routing"]["destinations"], [])

        snapshot = load_knowledge_snapshot_as_of(date(2026, 8, 26))
        national_id_service = next(
            service
            for service in snapshot.services
            if service.semantic_id == NATIONAL_ID_SERVICE_ID
        )
        exact = prepare_case(
            snapshot.fact_definitions,
            national_id_service,
            {"national_id_expiry_date": date(2026, 5, 26)},
            date(2026, 8, 26),
        )
        self.assertIsInstance(exact, CasePreparationSuccess)
        assert isinstance(exact, CasePreparationSuccess)
        self.assertEqual(
            exact.prepared_facts.values["renewal_deadline_date"],
            date(2026, 8, 26),
        )
        self.assertFalse(exact.prepared_facts.values["renewal_deadline_passed"])

        clamped = prepare_case(
            snapshot.fact_definitions,
            national_id_service,
            {"national_id_expiry_date": date(2026, 5, 31)},
            date(2026, 8, 31),
        )
        self.assertIsInstance(clamped, CasePreparationSuccess)
        assert isinstance(clamped, CasePreparationSuccess)
        self.assertEqual(
            clamped.prepared_facts.values["renewal_deadline_date"],
            date(2026, 8, 31),
        )
        self.assertFalse(clamped.prepared_facts.values["renewal_deadline_passed"])

    def test_trust_evidence_and_routing_are_gated_locally_per_family(self) -> None:
        passport = self.post(
            PASSPORT_SERVICE_ID,
            PASSPORT_PLAN_FACTS,
            locale="en",
            evaluation_date="2026-08-25",
        )
        passport_ids = [item["id"] for item in passport["checklist_items"]]
        self.assertNotIn("passport.requirement.previous_passport", passport_ids)
        self.assertTrue(all(item["sources"] for item in passport["checklist_items"]))
        self.assertEqual(passport["routing"]["status"], "resolved")
        self.assertEqual(
            [item["association_id"] for item in passport["routing"]["destinations"]],
            ["spa.passport_renewal.giza_standard"],
        )

        national_id = self.post(
            NATIONAL_ID_SERVICE_ID,
            NATIONAL_ID_PLAN_FACTS,
            locale="en",
            evaluation_date="2026-08-26",
        )
        self.assertEqual(
            [item["id"] for item in national_id["checklist_items"]],
            ["nid.requirement.renew_after_expiry"],
        )
        self.assertEqual(national_id["fees"][0]["id"], "nid.fee.ordinary")
        self.assertEqual(national_id["fees"][0]["value_state"], "unknown")
        self.assertEqual(national_id["routing"]["status"], "unresolved")
        self.assertEqual(national_id["routing"]["destinations"], [])
        route_step = next(
            item
            for item in national_id["steps"]
            if item["id"] == "nid.step.resolve_service_location"
        )
        self.assertEqual(
            [source["id"] for source in route_step["sources"]],
            ["SRC-PSM-CIVIL-STATUS-SERVICES"],
        )

        military = self.post(
            MILITARY_SERVICE_ID,
            MILITARY_ONLY_SON_FACTS,
            locale="en",
            evaluation_date="2026-08-26",
        )
        self.assertEqual(
            [item["id"] for item in military["eligibility_bases"]],
            ["family.only_son_living_father"],
        )
        self.assertEqual(
            military["eligibility_bases"][0]["freshness"]["state"],
            "needs_reverification",
        )
        military_checklist_ids = [item["id"] for item in military["checklist_items"]]
        self.assertIn("mil.shared.supporting_documents", military_checklist_ids)
        self.assertFalse(any(item.startswith("mil.basis.") for item in military_checklist_ids))
        self.assertEqual(military["routing"]["status"], "resolved")

        serialized = json.dumps((passport, national_id, military), ensure_ascii=False)
        for editorial_field in (
            "passage",
            "applicability_context",
            "support_status",
        ):
            self.assertNotIn(f'"{editorial_field}"', serialized)

    def test_identical_requests_are_byte_semantically_deterministic(self) -> None:
        cases = (
            (PASSPORT_SERVICE_ID, PASSPORT_PLAN_FACTS, "2026-08-25"),
            (NATIONAL_ID_SERVICE_ID, NATIONAL_ID_PLAN_FACTS, "2026-08-26"),
            (MILITARY_SERVICE_ID, MILITARY_ONLY_SON_FACTS, "2026-08-26"),
        )
        for service_id, facts, evaluation_date in cases:
            for locale in ("ar", "en"):
                with self.subTest(service=service_id, locale=locale):
                    first = self.post(
                        service_id,
                        facts,
                        locale=locale,
                        evaluation_date=evaluation_date,
                    )
                    second = self.post(
                        service_id,
                        facts,
                        locale=locale,
                        evaluation_date=evaluation_date,
                    )
                    self.assertEqual(first, second)
