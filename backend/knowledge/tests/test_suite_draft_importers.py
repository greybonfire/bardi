"""PostgreSQL integration checks for non-routable suite imports.

Run with the project's real Django settings. Pure manifest checks live separately.
"""

from dataclasses import asdict
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from knowledge.fees import Fee
from knowledge.importers.national_id_suite import import_national_id_suite
from knowledge.importers.passport_suite import import_passport_suite
from knowledge.importers.suite_drafts import _verify_suite
from knowledge.importers.suite_specs import load_suite
from knowledge.models import (
    Authority,
    ChecklistItem,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceContradiction,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scenarios import PlanningScenario, planning_behavior_signature
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.review_workflow import ProcedureVersionReviewApproval, ProcedureVersionReviewPolicy


class SuiteDraftImportTests(TestCase):
    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(
            username="suite-author", is_active=True, is_staff=True
        )
        self.publisher = get_user_model().objects.create_user(
            username="suite-publisher", is_active=True, is_staff=True
        )

    def counts(self) -> tuple[int, ...]:
        return tuple(
            model.objects.count()
            for model in (
                Authority,
                Source,
                Procedure,
                ProcedureVersion,
                ChecklistItem,
                Step,
                Warning,
                Fee,
                EvidenceLink,
                ProcedureVersionReviewPolicy,
            )
        )

    def test_both_commands_stage_all_named_rows_without_activating_anything(self) -> None:
        for command in ("import_passport_suite", "import_national_id_suite"):
            output = StringIO()
            call_command(command, author=self.author.username, stdout=output)
            self.assertIn("Research drafts only", output.getvalue())
        self.assertEqual(ProcedureVersion.objects.filter(state="draft").count(), 24)
        self.assertFalse(Service.objects.filter(is_active=True).exists())
        self.assertFalse(ServiceProcedureCandidate.objects.exists())
        self.assertFalse(ServiceQuestion.objects.exists())
        self.assertFalse(ServiceContradiction.objects.exists())
        self.assertFalse(PlanningScenario.objects.exists())
        self.assertFalse(ProcedureVersionReviewApproval.objects.exists())
        self.assertFalse(ProcedureVersion.objects.exclude(applicability={}).exists())
        self.assertFalse(ProcedureVersion.objects.filter(effective_from__isnull=False).exists())
        self.assertFalse(ChecklistItem.objects.exclude(classification="candidate").exists())
        self.assertFalse(EvidenceLink.objects.exclude(support_status="context").exists())
        self.assertFalse(EvidenceLink.objects.filter(verified_on__isnull=False).exists())

    def test_national_id_first_then_passport_repeats_are_identical(self) -> None:
        import_national_id_suite(author=self.author)
        import_passport_suite(author=self.author)
        before = self.counts()
        for importer in (import_passport_suite, import_national_id_suite):
            result = importer(author=self.author)
            self.assertEqual(result.created_versions, 0)
            self.assertEqual(self.counts(), before)
            importer(author=self.author, check_only=True)
            self.assertEqual(self.counts(), before)

    def test_check_and_dry_run_leave_no_rows(self) -> None:
        before = self.counts()
        with self.assertRaises(ValidationError):
            import_passport_suite(author=self.author, check_only=True)
        self.assertEqual(self.counts(), before)
        result = import_passport_suite(author=self.author, dry_run=True)
        self.assertTrue(result.dry_run)
        self.assertEqual(result.created_versions, 12)
        self.assertEqual(self.counts(), before)
        self.assertFalse(Service.objects.exists())

    def test_final_verification_runs_once_and_failure_rolls_back_every_write(self) -> None:
        before = self.counts()
        with patch("knowledge.importers.suite_drafts._verify_suite", wraps=_verify_suite) as verify:
            import_passport_suite(author=self.author, dry_run=True)
            self.assertEqual(verify.call_count, 1)
        with patch(
            "knowledge.importers.suite_drafts._verify_suite",
            side_effect=ValidationError("late"),
        ):
            with self.assertRaises(ValidationError):
                import_passport_suite(author=self.author)
        self.assertEqual(self.counts(), before)
        self.assertFalse(Service.objects.exists())

    def test_edited_claim_is_rejected_not_silently_repaired(self) -> None:
        import_passport_suite(author=self.author)
        item = ChecklistItem.objects.first()
        self.assertIsNotNone(item)
        assert item is not None
        item.text_en = "Editorially changed"
        item.save()
        with self.assertRaises(ValidationError):
            import_passport_suite(author=self.author)
        item.refresh_from_db()
        self.assertEqual(item.text_en, "Editorially changed")

    def test_deleted_child_and_trust_drift_are_rejected(self) -> None:
        import_national_id_suite(author=self.author)
        item = ChecklistItem.objects.first()
        assert item is not None
        item.verification_state = "current"
        item.save()
        with self.assertRaises(ValidationError):
            import_national_id_suite(author=self.author, check_only=True)
        item.verification_state = "needs_reverification"
        item.save()
        item.delete()
        with self.assertRaises(ValidationError):
            import_national_id_suite(author=self.author)

    def test_author_and_source_drift_are_rejected(self) -> None:
        import_passport_suite(author=self.author)
        with self.assertRaises(ValidationError):
            import_passport_suite(author=self.publisher)
        source = Source.objects.get(semantic_id="passport.suite.source.S02.2026-09-12")
        source.locator = "https://example.invalid/edited"
        source.save()
        with self.assertRaises(ValidationError):
            import_passport_suite(author=self.author)
        source.refresh_from_db()
        self.assertEqual(source.locator, "https://example.invalid/edited")

    def test_unsaved_inactive_and_nonstaff_authors_are_rejected(self) -> None:
        user_model = get_user_model()
        bad = [user_model(username="unsaved", is_staff=True)]
        for name, active, staff in (("inactive", False, True), ("nonstaff", True, False)):
            bad.append(
                user_model.objects.create_user(username=name, is_active=active, is_staff=staff)
            )
        for actor in bad:
            with self.assertRaises(ValidationError):
                import_passport_suite(author=actor)
        self.assertFalse(ProcedureVersion.objects.exists())

    @override_settings(PLANNING_SCENARIOS_REQUIRED=False, PROCEDURE_VERSION_REVIEWS_REQUIRED=False)
    def test_even_without_optional_review_gates_drafts_cannot_publish(self) -> None:
        import_passport_suite(author=self.author)
        version = ProcedureVersion.objects.first()
        assert version is not None
        with self.assertRaises(PublicationRejected) as rejected:
            publish_procedure_version(version.pk, actor=self.publisher)
        self.assertTrue(
            any(item.gate == "core.applicability" for item in rejected.exception.diagnostics)
        )
        version.refresh_from_db()
        self.assertEqual(version.state, "draft")
        self.assertIsNone(version.published_at)

    def test_legacy_renewal_reimports_and_signatures_survive_staging(self) -> None:
        from knowledge.importers.national_id_renewal import import_national_id_renewal
        from knowledge.importers.passport_renewal import import_passport_renewal

        old_passport = import_passport_renewal(author=self.author)
        old_id = import_national_id_renewal(author=self.author)
        signatures = tuple(planning_behavior_signature(v) for v in (old_passport, old_id))
        questions = list(ServiceQuestion.objects.order_by("pk").values())
        candidates = list(ServiceProcedureCandidate.objects.order_by("pk").values())
        facts = list(FactDefinition.objects.order_by("pk").values())
        import_passport_suite(author=self.author)
        import_national_id_suite(author=self.author)
        self.assertEqual(import_passport_renewal(author=self.author).pk, old_passport.pk)
        self.assertEqual(import_national_id_renewal(author=self.author).pk, old_id.pk)
        self.assertEqual(
            tuple(planning_behavior_signature(v) for v in (old_passport, old_id)), signatures
        )
        self.assertEqual(list(ServiceQuestion.objects.order_by("pk").values()), questions)
        self.assertEqual(
            list(ServiceProcedureCandidate.objects.order_by("pk").values()), candidates
        )
        self.assertEqual(list(FactDefinition.objects.order_by("pk").values()), facts)

    def test_preview_and_report_do_not_claim_missing_identities_were_imported(self) -> None:
        output = StringIO()
        call_command("import_national_id_suite", list=True, stdout=output)
        self.assertFalse(ProcedureVersion.objects.exists())
        self.assertIn('"publishable": false', output.getvalue())
        result = asdict(import_national_id_suite(author=self.author))
        rows = {row["row"]: row for row in result["families"]}
        self.assertEqual(rows["N08"]["versions"], ())
        self.assertEqual(rows["N13"]["versions"], ())
        self.assertEqual(len(rows["N12"]["versions"]), 2)

    def test_original_passport_privacy_locator_is_never_claim_evidence(self) -> None:
        import_passport_suite(author=self.author)
        source = Source.objects.get(semantic_id="passport.suite.source.S23.2026-09-12")
        self.assertFalse(source.evidence_source_links.exists())
        self.assertEqual(len(load_suite("passport").families), 14)

    def test_missing_whole_version_is_rejected_not_recreated(self) -> None:
        import_passport_suite(author=self.author)
        version = ProcedureVersion.objects.first()
        assert version is not None
        identity = version.semantic_id
        version.delete()
        with self.assertRaises(ValidationError):
            import_passport_suite(author=self.author)
        self.assertFalse(ProcedureVersion.objects.filter(semantic_id=identity).exists())

    def test_suite_first_does_not_implicitly_activate_the_legacy_service(self) -> None:
        from knowledge.importers.national_id_renewal import import_national_id_renewal

        import_national_id_suite(author=self.author)
        service = Service.objects.get(semantic_id="get_egyptian_national_id")
        self.assertFalse(service.is_active)
        # The old public command intentionally requires an active canonical Service.
        # Its contract is not weakened just to make staging order look transparent.
        with self.assertRaises(ValidationError):
            import_national_id_renewal(author=self.author)
        service.is_active = True  # Explicit editorial decision in this test only.
        service.save()
        baseline = import_national_id_renewal(author=self.author)
        self.assertEqual(baseline.state, "draft")
        import_national_id_suite(author=self.author, check_only=True)

    def test_passport_first_then_national_id_repeats_are_identical(self) -> None:
        import_passport_suite(author=self.author)
        import_national_id_suite(author=self.author)
        before = self.counts()
        for importer in (import_national_id_suite, import_passport_suite):
            self.assertEqual(importer(author=self.author).created_versions, 0)
            importer(author=self.author, check_only=True)
            self.assertEqual(self.counts(), before)

    def test_extra_child_is_rejected_without_overwriting_editor_work(self) -> None:
        import_passport_suite(author=self.author)
        version = ProcedureVersion.objects.first()
        assert version is not None
        extra = Warning.objects.create(
            procedure_version=version,
            semantic_id="editor.note",
            text_ar="ملاحظة المحرر",
            text_en="An editor's note",
            kind="product",
        )
        with self.assertRaises(ValidationError):
            import_passport_suite(author=self.author)
        self.assertTrue(Warning.objects.filter(pk=extra.pk).exists())
