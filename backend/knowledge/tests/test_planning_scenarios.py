from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings

from knowledge.models import (
    FactDefinition,
    Procedure,
    ProcedureVersion,
    ProcedureVersionAuditEvent,
    Service,
    ServiceContradiction,
    ServiceContradictionFact,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.planning_scenarios import PlanningScenario
from knowledge.publication import PublicationRejected, publish_procedure_version

EDGE_DATE = date(2026, 1, 1)
NORMAL_DATE = date(2026, 9, 5)
ELIGIBLE_RULE = {"op": "eq", "fact": "scenario_eligible", "value": True}
INELIGIBLE_RULE = {"op": "eq", "fact": "scenario_eligible", "value": False}


@override_settings(PLANNING_SCENARIOS_REQUIRED=True)
class PlanningScenarioPublicationTests(TransactionTestCase):
    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="scenario-publisher")
        self.eligible = FactDefinition.objects.create(
            key="scenario_eligible",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.secret = FactDefinition.objects.create(
            key="scenario_private_note",
            kind=FactDefinition.Kind.STRING,
            enum_values=[],
            is_published=True,
        )
        self.service = Service.objects.create(
            semantic_id="scenario.service",
            text_ar="خدمة السيناريو",
            text_en="Scenario service",
            is_active=True,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="scenario.procedure",
            text_ar="إجراء السيناريو",
            text_en="Scenario procedure",
            primary_service=self.service,
        )
        self.candidate = ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=ELIGIBLE_RULE,
        )
        self.question = ServiceQuestion.objects.create(
            semantic_id="scenario.question.eligible",
            service=self.service,
            fact=self.eligible,
            text_ar="هل تنطبق الحالة؟",
            text_en="Does the case qualify?",
            priority=1,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="scenario.procedure.v1",
            procedure=self.procedure,
            effective_from=EDGE_DATE,
            text_ar="نسخة السيناريو",
            text_en="Scenario version",
            applicability=ELIGIBLE_RULE,
        )

    def scenario(
        self,
        *,
        name: str,
        kind: str,
        evaluation_date: date,
        facts: dict[str, object],
        family: str,
        identifiers: dict[str, object],
        diagnostics: list[str] | None = None,
    ) -> PlanningScenario:
        return PlanningScenario.objects.create(
            procedure_version=self.version,
            name=name,
            kind=kind,
            evaluation_context={
                "evaluation_date": evaluation_date.isoformat(),
                "locale": "en",
            },
            source_facts=facts,
            expected_result_family=family,
            expected_identifiers=identifiers,
            expected_diagnostics=[] if diagnostics is None else diagnostics,
        )

    def author_required_scenarios(self, *, reverse: bool = False) -> tuple[PlanningScenario, ...]:
        matching = False if reverse else True
        rejected = True if reverse else False
        version_id = self.version.semantic_id
        return (
            self.scenario(
                name="eligible case produces the researched plan",
                kind=PlanningScenario.Kind.POSITIVE,
                evaluation_date=NORMAL_DATE,
                facts={"scenario_eligible": matching},
                family=PlanningScenario.ResultFamily.PLAN,
                identifiers={"procedure_version_id": version_id},
            ),
            self.scenario(
                name="nonmatching case is not routed into this procedure",
                kind=PlanningScenario.Kind.NEGATIVE,
                evaluation_date=NORMAL_DATE,
                facts={"scenario_eligible": rejected},
                family=PlanningScenario.ResultFamily.INCONCLUSIVE,
                identifiers={"reason": "no_matching_researched_procedure"},
            ),
            self.scenario(
                name="missing consequential fact asks the named question",
                kind=PlanningScenario.Kind.UNKNOWN,
                evaluation_date=NORMAL_DATE,
                facts={},
                family=PlanningScenario.ResultFamily.NEXT_QUESTION,
                identifiers={"question_id": self.question.semantic_id},
            ),
            self.scenario(
                name="effective start date is supported inclusively",
                kind=PlanningScenario.Kind.SUPPORTED_EDGE,
                evaluation_date=EDGE_DATE,
                facts={"scenario_eligible": matching},
                family=PlanningScenario.ResultFamily.PLAN,
                identifiers={"procedure_version_id": version_id},
            ),
        )

    def test_missing_required_scenarios_block_publication_atomically(self) -> None:
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)

        scenario_diagnostics = [
            item
            for item in caught.exception.diagnostics
            if item.gate == "core.planning_scenarios"
        ]
        self.assertEqual(
            {(item.code, item.detail) for item in scenario_diagnostics},
            {
                ("missing_required_scenario", "negative"),
                ("missing_required_scenario", "positive"),
                ("missing_required_scenario", "supported_edge"),
                ("missing_required_scenario", "unknown"),
            },
        )
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)
        self.assertIsNone(self.version.published_at)
        self.assertEqual(ProcedureVersionAuditEvent.objects.count(), 0)

    def test_required_scenarios_execute_and_publish_through_production_planner(self) -> None:
        scenarios = self.author_required_scenarios()

        published = publish_procedure_version(self.version.pk, actor=self.actor)

        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)
        self.assertEqual(
            ProcedureVersionAuditEvent.objects.filter(
                version=self.version,
                event_type=ProcedureVersionAuditEvent.EventType.PUBLISHED,
            ).count(),
            1,
        )
        scenarios[0].name = "changed after publication"
        with self.assertRaises(ValidationError):
            scenarios[0].save()
        with self.assertRaises(ValidationError):
            scenarios[1].delete()

    def test_failing_scenario_names_only_the_scenario_and_rolls_back_publication(self) -> None:
        scenarios = list(self.author_required_scenarios())
        secret_value = "PRIVATE-CASE-VALUE-9e5519"
        failing = scenarios[0]
        failing.source_facts = {
            "scenario_eligible": True,
            "scenario_private_note": secret_value,
        }
        failing.expected_identifiers = {
            "procedure_version_id": self.version.semantic_id,
            "routing_status": "resolved",
        }
        failing.save()

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)

        scenario_diagnostics = [
            item
            for item in caught.exception.diagnostics
            if item.gate == "core.planning_scenarios"
        ]
        self.assertEqual(
            [(item.code, item.detail) for item in scenario_diagnostics],
            [("scenario_failed", failing.name)],
        )
        diagnostic_text = str(caught.exception) + repr(caught.exception.diagnostics)
        self.assertNotIn(secret_value, diagnostic_text)
        self.assertNotIn("scenario_private_note", diagnostic_text)
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)
        self.assertIsNone(self.version.published_at)
        self.assertEqual(ProcedureVersionAuditEvent.objects.count(), 0)

    def test_invalid_required_scenario_blocks_before_execution(self) -> None:
        scenarios = self.author_required_scenarios()
        invalid = scenarios[2]
        PlanningScenario.objects.filter(pk=invalid.pk).update(
            evaluation_context={"evaluation_date": "not-a-date", "locale": "en"}
        )

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)

        self.assertIn(
            ("invalid_scenario", invalid.name),
            {
                (item.code, item.detail)
                for item in caught.exception.diagnostics
                if item.gate == "core.planning_scenarios"
            },
        )
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)
        self.assertEqual(ProcedureVersionAuditEvent.objects.count(), 0)

    def test_rule_semantic_change_requires_scenario_updates_before_publication(self) -> None:
        scenarios = self.author_required_scenarios()
        old_signatures = {scenario.behavior_signature for scenario in scenarios}
        self.assertEqual(len(old_signatures), 1)

        self.candidate.selection_predicate = INELIGIBLE_RULE
        self.candidate.save()
        self.version.applicability = INELIGIBLE_RULE
        self.version.save()

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)

        stale_names = {
            item.detail
            for item in caught.exception.diagnostics
            if item.gate == "core.planning_scenarios"
            and item.code == "scenario_stale_after_semantic_change"
        }
        self.assertEqual(stale_names, {scenario.name for scenario in scenarios})
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)
        self.assertEqual(ProcedureVersionAuditEvent.objects.count(), 0)

        for scenario in scenarios:
            if scenario.kind in {PlanningScenario.Kind.POSITIVE, PlanningScenario.Kind.SUPPORTED_EDGE}:
                scenario.source_facts = {"scenario_eligible": False}
            elif scenario.kind == PlanningScenario.Kind.NEGATIVE:
                scenario.source_facts = {"scenario_eligible": True}
            scenario.save()

        refreshed_signatures = {
            scenario.behavior_signature
            for scenario in PlanningScenario.objects.filter(procedure_version=self.version)
        }
        self.assertEqual(len(refreshed_signatures), 1)
        self.assertNotEqual(refreshed_signatures, old_signatures)
        published = publish_procedure_version(self.version.pk, actor=self.actor)
        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)

    def test_contradiction_capability_requires_and_executes_contradictory_scenario(self) -> None:
        conflict = FactDefinition.objects.create(
            key="scenario_conflict",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        contradiction = ServiceContradiction.objects.create(
            semantic_id="scenario.contradiction",
            service=self.service,
            condition={
                "op": "all",
                "children": [
                    {"op": "eq", "fact": "scenario_eligible", "value": True},
                    {"op": "eq", "fact": "scenario_conflict", "value": True},
                ],
            },
        )
        ServiceContradictionFact.objects.create(
            contradiction=contradiction,
            fact=self.eligible,
            position=1,
        )
        ServiceContradictionFact.objects.create(
            contradiction=contradiction,
            fact=conflict,
            position=2,
        )
        self.author_required_scenarios()

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)
        self.assertIn(
            ("missing_required_scenario", "contradictory"),
            {
                (item.code, item.detail)
                for item in caught.exception.diagnostics
                if item.gate == "core.planning_scenarios"
            },
        )

        self.scenario(
            name="contradictory submitted facts are rejected",
            kind=PlanningScenario.Kind.CONTRADICTORY,
            evaluation_date=NORMAL_DATE,
            facts={"scenario_eligible": True, "scenario_conflict": True},
            family=PlanningScenario.ResultFamily.INVALID,
            identifiers={},
            diagnostics=["contradictory_facts", "contradictory_facts"],
        )
        published = publish_procedure_version(self.version.pk, actor=self.actor)
        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)
