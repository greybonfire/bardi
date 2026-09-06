from __future__ import annotations

from datetime import date
from io import StringIO
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from knowledge.importers.temporary_family_exemption import (
    CURRENT_VERSION_ID,
    HISTORICAL_VERSION_ID,
    import_temporary_family_exemption,
)
from knowledge.models import ChecklistItem, EligibilityBasis, ProcedureVersion
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.review_workflow import (
    ProcedureVersionAuditApproval,
    ProcedureVersionReviewPolicy,
    approve_review_dimension,
    approve_specialist_risk,
)
from knowledge.service_point_routing import ProcedureServicePointAssociation


class TemporaryFamilyExemptionImportTests(TestCase):
    def test_import_is_idempotent_and_preserves_temporal_basis_and_routing_contract(self) -> None:
        author = get_user_model().objects.create_user(username="mil-import-author", is_staff=True)

        first = import_temporary_family_exemption(author=author)
        second = import_temporary_family_exemption(author=author)

        self.assertEqual([item.pk for item in first], [item.pk for item in second])
        historical, current = first
        self.assertEqual(historical.semantic_id, HISTORICAL_VERSION_ID)
        self.assertIsNone(historical.effective_from)
        self.assertEqual(historical.effective_to, date(2026, 3, 24))
        self.assertEqual(current.semantic_id, CURRENT_VERSION_ID)
        self.assertEqual(current.effective_from, date(2026, 3, 25))
        self.assertIsNone(current.effective_to)

        expected_bases = {
            "family.only_son_living_father",
            "family.support_father_or_incapable_brothers",
            "family.support_mother",
            "family.support_unmarried_sisters",
            "family.missing_war_or_terror_relative",
            "family.sibling_current_service",
        }
        for version in first:
            self.assertEqual(
                set(
                    EligibilityBasis.objects.filter(procedure_version=version).values_list(
                        "semantic_id", flat=True
                    )
                ),
                expected_bases,
            )
            self.assertFalse(
                EligibilityBasis.objects.filter(procedure_version=version)
                .exclude(verification_state="needs_reverification")
                .exists()
            )
            self.assertFalse(version.dependencies.exists())
            self.assertEqual(
                set(
                    ProcedureServicePointAssociation.objects.filter(
                        procedure_version=version
                    ).values_list("semantic_id", flat=True)
                ),
                {
                    "spa.mil.giza_region",
                    "spa.mil.mansoura_region",
                    "spa.mil.zagazig_region",
                },
            )
            policy = ProcedureVersionReviewPolicy.objects.get(procedure_version=version)
            self.assertTrue(policy.legal_risk)
            self.assertTrue(policy.military_risk)

        historical_missing = EligibilityBasis.objects.get(
            procedure_version=historical,
            semantic_id="family.missing_war_or_terror_relative",
        )
        current_missing = EligibilityBasis.objects.get(
            procedure_version=current,
            semantic_id="family.missing_war_or_terror_relative",
        )
        self.assertNotIn("terrorist_operations", str(cast(Any, historical_missing).qualification))
        self.assertIn("terrorist_operations", str(cast(Any, current_missing).qualification))

        father_basis = EligibilityBasis.objects.get(
            procedure_version=current,
            semantic_id="family.support_father_or_incapable_brothers",
        )
        self.assertEqual(
            cast(Any, father_basis).reachability,
            {"op": "eq", "fact": "father_alive", "value": True},
        )
        self.assertEqual(
            cast(Any, father_basis).qualification,
            {
                "op": "eq",
                "fact": "father_unable_to_earn_status",
                "value": "authority_documented_unable",
            },
        )
        self.assertFalse(
            ChecklistItem.objects.filter(
                procedure_version=current,
                semantic_id__icontains="incapable_brother",
            ).exists()
        )

    def test_management_command_creates_both_accountable_drafts(self) -> None:
        author = get_user_model().objects.create_user(username="mil-command", is_staff=True)
        output = StringIO()

        call_command("import_temporary_family_exemption", author=author.username, stdout=output)

        versions = ProcedureVersion.objects.filter(
            semantic_id__in=(HISTORICAL_VERSION_ID, CURRENT_VERSION_ID)
        )
        self.assertEqual(versions.count(), 2)
        self.assertTrue(all(version.state == ProcedureVersion.State.DRAFT for version in versions))
        self.assertTrue(all(version.published_by is None for version in versions))
        self.assertEqual(
            output.getvalue().strip().splitlines(),
            [f"{HISTORICAL_VERSION_ID} draft", f"{CURRENT_VERSION_ID} draft"],
        )

    def test_rerun_rejects_semantic_drift(self) -> None:
        author = get_user_model().objects.create_user(username="mil-conflict", is_staff=True)
        _, current = import_temporary_family_exemption(author=author)
        basis = EligibilityBasis.objects.get(
            procedure_version=current,
            semantic_id="family.only_son_living_father",
        )
        EligibilityBasis.objects.filter(pk=basis.pk).update(
            qualification={"op": "eq", "fact": "other_living_sons_of_father_count", "value": 1}
        )

        with self.assertRaisesMessage(ValidationError, "semantic conflict in planning behavior"):
            import_temporary_family_exemption(author=author)

    @override_settings(
        SELECTION_QUESTIONS_REQUIRED=True,
        PLANNING_SCENARIOS_REQUIRED=True,
        PROCEDURE_VERSION_REVIEWS_REQUIRED=True,
    )
    def test_both_versions_pass_normal_review_and_specialist_publication_gates(self) -> None:
        author = get_user_model().objects.create_user(username="mil-publish-author", is_staff=True)
        reviewer = get_user_model().objects.create_user(username="mil-reviewer")
        legal_specialist = get_user_model().objects.create_user(username="mil-legal-specialist")
        military_specialist = get_user_model().objects.create_user(
            username="mil-military-specialist"
        )
        publisher = get_user_model().objects.create_user(username="mil-publisher")
        reviewer.user_permissions.add(Permission.objects.get(codename="review_procedureversion"))
        legal_specialist.user_permissions.add(
            Permission.objects.get(codename="specialist_approve_legal")
        )
        military_specialist.user_permissions.add(
            Permission.objects.get(codename="specialist_approve_military")
        )
        versions = import_temporary_family_exemption(author=author)

        for version in versions:
            for dimension in (
                "evidence_source",
                "rule_logic",
                "scenario_behavior",
                "bilingual_semantic",
            ):
                approve_review_dimension(version.pk, dimension=dimension, actor=reviewer)
            approve_specialist_risk(version.pk, risk_kind="legal", actor=legal_specialist)
            approve_specialist_risk(version.pk, risk_kind="military", actor=military_specialist)
            try:
                published = publish_procedure_version(version.pk, actor=publisher)
            except PublicationRejected as exc:
                self.fail(str([(item.code, item.detail) for item in exc.diagnostics]))
            self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)
            event = published.audit_events.get(event_type="published")
            self.assertEqual(event.approvals.count(), 6)

        self.assertEqual(ProcedureVersionAuditApproval.objects.count(), 12)
