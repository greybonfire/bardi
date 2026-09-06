from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from knowledge.importers.passport_renewal import VERSION_ID, import_passport_renewal
from knowledge.models import ChecklistItem, Procedure, ProcedureVersion, Service, Warning
from knowledge.planning_scenarios import PlanningScenario
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.review_workflow import (
    ProcedureVersionAuditApproval,
    approve_review_dimension,
    approve_specialist_risk,
)


class PassportRenewalImportTests(TestCase):
    def test_import_is_an_idempotent_researched_draft(self) -> None:
        author = get_user_model().objects.create_user(username="passport-author", is_staff=True)
        first = import_passport_renewal(author=author)
        second = import_passport_renewal(author=author)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.semantic_id, VERSION_ID)
        self.assertEqual(first.state, ProcedureVersion.State.DRAFT)
        previous = ChecklistItem.objects.get(
            procedure_version=first,
            semantic_id="passport.requirement.previous_passport",
        )
        self.assertEqual(previous.classification, ChecklistItem.Classification.CANDIDATE)
        self.assertEqual(previous.verification_state, "needs_reverification")
        self.assertFalse(first.eligibility_bases.exists())
        self.assertFalse(first.dependencies.exists())
        self.assertFalse(
            Warning.objects.filter(
                procedure_version=first,
                semantic_id="passport.turnaround.standard",
            ).exists()
        )
        self.assertFalse(Service.objects.filter(semantic_id="goal.passport").exists())
        self.assertFalse(
            Procedure.objects.filter(semantic_id="procedure.passport_renewal").exists()
        )

        expectations = {
            scenario.name: scenario.expected_identifiers
            for scenario in PlanningScenario.objects.filter(procedure_version=first)
        }
        self.assertEqual(
            expectations["passport.edge.turns_15"]["checklist_item_ids"],
            [
                "passport.requirement.national_id",
                "passport.requirement.photos",
                "passport.requirement.originals_and_copy",
            ],
        )
        self.assertEqual(
            expectations["passport.edge.one_day_under_15"]["checklist_item_ids"][0],
            "passport.requirement.birth_certificate",
        )
        self.assertIn(
            "passport.requirement.military_status",
            expectations["passport.edge.male_turns_19"]["checklist_item_ids"],
        )
        self.assertNotIn(
            "passport.requirement.military_status",
            expectations["passport.edge.male_one_day_under_19"]["checklist_item_ids"],
        )
        self.assertEqual(
            expectations["passport.fee.urgent"]["fee_ids"],
            ["passport.fee.base", "passport.fee.urgent_service"],
        )
        self.assertEqual(
            expectations["passport.routing.unresearched_district"]["routing_association_ids"],
            [],
        )

    def test_management_command_creates_only_the_accountable_draft(self) -> None:
        author = get_user_model().objects.create_user(username="passport-command", is_staff=True)
        output = StringIO()

        call_command("import_passport_renewal", author=author.username, stdout=output)

        version = ProcedureVersion.objects.get(semantic_id=VERSION_ID)
        self.assertEqual(version.state, ProcedureVersion.State.DRAFT)
        self.assertIsNone(version.published_by)
        self.assertEqual(output.getvalue().strip(), f"{VERSION_ID} draft")

    def test_rerun_rejects_a_conflicting_stable_version_identity(self) -> None:
        author = get_user_model().objects.create_user(username="passport-conflict", is_staff=True)
        version = import_passport_renewal(author=author)
        ProcedureVersion.objects.filter(pk=version.pk).update(text_en="Conflicting meaning")

        with self.assertRaisesMessage(ValidationError, "semantic conflict in text_en"):
            import_passport_renewal(author=author)

    @override_settings(
        SELECTION_QUESTIONS_REQUIRED=True,
        PLANNING_SCENARIOS_REQUIRED=True,
        PROCEDURE_VERSION_REVIEWS_REQUIRED=True,
    )
    def test_complete_draft_passes_production_semantic_and_scenario_gates(self) -> None:
        author = get_user_model().objects.create_user(
            username="passport-publish-author", is_staff=True
        )
        reviewer = get_user_model().objects.create_user(username="passport-reviewer")
        specialist = get_user_model().objects.create_user(username="passport-specialist")
        publisher = get_user_model().objects.create_user(username="passport-publisher")
        reviewer.user_permissions.add(Permission.objects.get(codename="review_procedureversion"))
        specialist.user_permissions.add(
            Permission.objects.get(codename="specialist_approve_military")
        )
        version = import_passport_renewal(author=author)
        for dimension in (
            "evidence_source",
            "rule_logic",
            "scenario_behavior",
            "bilingual_semantic",
        ):
            approve_review_dimension(version.pk, dimension=dimension, actor=reviewer)
        approve_specialist_risk(version.pk, risk_kind="military", actor=specialist)
        try:
            published = publish_procedure_version(version.pk, actor=publisher)
        except PublicationRejected as exc:
            self.fail(str([(item.code, item.detail) for item in exc.diagnostics]))
        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)
        event = published.audit_events.get(event_type="published")
        self.assertEqual(event.approvals.count(), 5)
        self.assertEqual(ProcedureVersionAuditApproval.objects.count(), 5)
