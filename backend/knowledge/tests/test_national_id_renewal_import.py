from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from knowledge.fees import Fee
from knowledge.importers.national_id_renewal import VERSION_ID, import_national_id_renewal
from knowledge.models import (
    ChecklistItem,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceContradiction,
)
from knowledge.planning_scenarios import PlanningScenario
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.review_workflow import (
    ProcedureVersionAuditApproval,
    approve_review_dimension,
)


class NationalIdRenewalImportTests(TestCase):
    def test_import_is_an_idempotent_researched_draft(self) -> None:
        author = get_user_model().objects.create_user(username="nid-author", is_staff=True)

        first = import_national_id_renewal(author=author)
        second = import_national_id_renewal(author=author)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.semantic_id, VERSION_ID)
        self.assertEqual(first.state, ProcedureVersion.State.DRAFT)
        self.assertFalse(first.eligibility_bases.exists())
        self.assertFalse(first.dependencies.exists())
        self.assertFalse(first.service_point_associations.exists())
        self.assertFalse(Service.objects.filter(semantic_id="goal.national_id").exists())
        self.assertFalse(
            Procedure.objects.filter(semantic_id="procedure.national_id_renewal").exists()
        )

        fee = Fee.objects.get(procedure_version=first, semantic_id="nid.fee.ordinary")
        self.assertEqual(fee.value_state, Fee.ValueState.UNKNOWN)
        self.assertIsNone(fee.amount)
        self.assertIsNone(fee.minimum_amount)
        self.assertIsNone(fee.maximum_amount)

        previous = ChecklistItem.objects.get(
            procedure_version=first,
            semantic_id="nid.requirement.previous_card",
        )
        self.assertEqual(previous.classification, ChecklistItem.Classification.CANDIDATE)
        self.assertEqual(previous.verification_state, "needs_reverification")
        self.assertIsNone(previous.document_type)

        contradiction = ServiceContradiction.objects.get(
            semantic_id="nid.no_current_card_with_expiry_date"
        )
        self.assertEqual(
            contradiction.fact_keys,
            ("national_id_possession_state", "national_id_expiry_date"),
        )

        scenarios = {
            row.name: row for row in PlanningScenario.objects.filter(procedure_version=first)
        }
        self.assertEqual(
            scenarios["nid.positive.expired_held_no_changes"].expected_identifiers[
                "routing_status"
            ],
            "unresolved",
        )
        self.assertEqual(
            scenarios["nid.positive.expired_held_no_changes"].expected_identifiers[
                "checklist_item_ids"
            ],
            ["nid.requirement.renew_after_expiry"],
        )
        self.assertEqual(
            scenarios["nid.edge.deadline_exact_three_calendar_months"].evaluation_context[
                "evaluation_date"
            ],
            "2026-08-26",
        )
        self.assertIn("nid.edge.deadline_month_end_clamping", scenarios)

    def test_management_command_creates_only_the_accountable_draft(self) -> None:
        author = get_user_model().objects.create_user(username="nid-command", is_staff=True)
        output = StringIO()

        call_command("import_national_id_renewal", author=author.username, stdout=output)

        version = ProcedureVersion.objects.get(semantic_id=VERSION_ID)
        self.assertEqual(version.state, ProcedureVersion.State.DRAFT)
        self.assertIsNone(version.published_by)
        self.assertEqual(output.getvalue().strip(), f"{VERSION_ID} draft")

    def test_rerun_rejects_planning_semantic_drift(self) -> None:
        author = get_user_model().objects.create_user(username="nid-conflict", is_staff=True)
        version = import_national_id_renewal(author=author)
        Fee.objects.filter(
            procedure_version=version,
            semantic_id="nid.fee.ordinary",
        ).update(currency="USD")

        with self.assertRaisesMessage(ValidationError, "semantic conflict in planning behavior"):
            import_national_id_renewal(author=author)

    @override_settings(
        SELECTION_QUESTIONS_REQUIRED=True,
        PLANNING_SCENARIOS_REQUIRED=True,
        PROCEDURE_VERSION_REVIEWS_REQUIRED=True,
    )
    def test_complete_draft_passes_production_semantic_and_scenario_gates(self) -> None:
        author = get_user_model().objects.create_user(username="nid-publish-author", is_staff=True)
        reviewer = get_user_model().objects.create_user(username="nid-reviewer")
        publisher = get_user_model().objects.create_user(username="nid-publisher")
        reviewer.user_permissions.add(Permission.objects.get(codename="review_procedureversion"))
        version = import_national_id_renewal(author=author)
        for dimension in (
            "evidence_source",
            "rule_logic",
            "scenario_behavior",
            "bilingual_semantic",
        ):
            approve_review_dimension(version.pk, dimension=dimension, actor=reviewer)

        try:
            published = publish_procedure_version(version.pk, actor=publisher)
        except PublicationRejected as exc:
            self.fail(str([(item.code, item.detail) for item in exc.diagnostics]))

        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)
        event = published.audit_events.get(event_type="published")
        self.assertEqual(event.approvals.count(), 4)
        self.assertEqual(ProcedureVersionAuditApproval.objects.count(), 4)
