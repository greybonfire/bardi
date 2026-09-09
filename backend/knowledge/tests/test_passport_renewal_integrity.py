from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from knowledge.fees import Fee
from knowledge.importers.passport_renewal import import_passport_renewal
from knowledge.importers.passport_renewal_integrity import (
    _LEGACY_SCENARIO_DIGEST,
    _PRE_FEE_QUESTION_SCENARIO_DIGEST,
    _PRE_QUESTION_SCENARIO_DIGEST,
    _verify_scenarios,
)
from knowledge.models import EvidenceLink, ProcedureVersion, ServiceProcedureCandidate, Source
from knowledge.planning_scenarios import PlanningScenario
from knowledge.review_workflow import (
    approve_review_dimension,
    review_state_signature,
)


class PassportRenewalIntegrityTests(TestCase):
    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(
            username="passport-integrity-author",
            is_staff=True,
        )
        self.version = import_passport_renewal(author=self.author)

    def set_prior_scenario_seal(self, seal: str) -> None:
        PlanningScenario.objects.filter(
            procedure_version=self.version,
            name="passport.fee.service_level_unknown",
        ).delete()
        if seal in {"legacy", "pre_question"}:
            PlanningScenario.objects.filter(
                procedure_version=self.version,
                name="passport.student.unknown",
            ).update(
                expected_result_family="inconclusive",
                expected_identifiers={"reason": "checklist_applicability_unknown"},
            )
        if seal == "legacy":
            for name in (
                "passport.fee.urgent",
                "passport.fee.premium",
                "passport.routing.unresearched_district",
            ):
                scenario = PlanningScenario.objects.get(
                    procedure_version=self.version,
                    name=name,
                )
                PlanningScenario.objects.filter(pk=scenario.pk).update(
                    expected_identifiers={
                        **scenario.expected_identifiers,
                        "routing_status": "resolved",
                    }
                )

    def assert_current_scenario_seal(self) -> None:
        self.assertIsNone(_verify_scenarios(self.version, allow_legacy=True))
        self.assertTrue(
            PlanningScenario.objects.filter(
                procedure_version=self.version,
                name="passport.fee.service_level_unknown",
                expected_result_family="next_question",
                expected_identifiers={"question_id": "q.service_level"},
            ).exists()
        )

    def set_finalized_state(self, state: str) -> None:
        now = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('bardi.procedure_version_lifecycle', %s, true)",
                ["publish"],
            )
        ProcedureVersion.objects.filter(pk=self.version.pk).update(
            state=ProcedureVersion.State.PUBLISHED,
            published_at=now,
            published_by=self.author,
        )
        if state == ProcedureVersion.State.WITHDRAWN:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('bardi.procedure_version_lifecycle', %s, true)",
                    ["withdraw"],
                )
            ProcedureVersion.objects.filter(pk=self.version.pk).update(
                state=ProcedureVersion.State.WITHDRAWN,
                withdrawn_at=now,
                withdrawn_by=self.author,
            )
        self.version.refresh_from_db()

    def test_direct_upgrade_from_exact_legacy_scenario_seal(self) -> None:
        self.set_prior_scenario_seal("legacy")
        self.assertEqual(
            _verify_scenarios(self.version, allow_legacy=True),
            _LEGACY_SCENARIO_DIGEST,
        )

        import_passport_renewal(author=self.author)

        self.assert_current_scenario_seal()

    def test_direct_upgrade_from_exact_pre_question_scenario_seal(self) -> None:
        self.set_prior_scenario_seal("pre_question")
        self.assertEqual(
            _verify_scenarios(self.version, allow_legacy=True),
            _PRE_QUESTION_SCENARIO_DIGEST,
        )

        import_passport_renewal(author=self.author)

        self.assert_current_scenario_seal()

    def test_direct_upgrade_from_exact_pre_fee_question_scenario_seal(self) -> None:
        self.set_prior_scenario_seal("pre_fee")
        self.assertEqual(
            _verify_scenarios(self.version, allow_legacy=True),
            _PRE_FEE_QUESTION_SCENARIO_DIGEST,
        )

        import_passport_renewal(author=self.author)

        self.assert_current_scenario_seal()

    def test_sequential_exact_prior_seals_are_recognized_before_current_upgrade(self) -> None:
        current = {
            scenario.name: (scenario.expected_result_family, scenario.expected_identifiers)
            for scenario in PlanningScenario.objects.filter(procedure_version=self.version)
        }
        self.set_prior_scenario_seal("legacy")
        self.assertEqual(
            _verify_scenarios(self.version, allow_legacy=True),
            _LEGACY_SCENARIO_DIGEST,
        )
        for name in (
            "passport.fee.urgent",
            "passport.fee.premium",
            "passport.routing.unresearched_district",
        ):
            PlanningScenario.objects.filter(procedure_version=self.version, name=name).update(
                expected_identifiers=current[name][1]
            )
        self.assertEqual(
            _verify_scenarios(self.version, allow_legacy=True),
            _PRE_QUESTION_SCENARIO_DIGEST,
        )
        family, identifiers = current["passport.student.unknown"]
        PlanningScenario.objects.filter(
            procedure_version=self.version,
            name="passport.student.unknown",
        ).update(expected_result_family=family, expected_identifiers=identifiers)
        self.assertEqual(
            _verify_scenarios(self.version, allow_legacy=True),
            _PRE_FEE_QUESTION_SCENARIO_DIGEST,
        )

        import_passport_renewal(author=self.author)

        self.assert_current_scenario_seal()

    def assert_finalized_prior_seal_is_immutable(self, state: str) -> None:
        self.set_prior_scenario_seal("pre_fee")
        before = list(
            PlanningScenario.objects.filter(procedure_version=self.version)
            .order_by("name")
            .values("name", "expected_result_family", "expected_identifiers")
        )
        self.set_finalized_state(state)

        import_passport_renewal(author=self.author)

        after = list(
            PlanningScenario.objects.filter(procedure_version=self.version)
            .order_by("name")
            .values("name", "expected_result_family", "expected_identifiers")
        )
        self.assertEqual(after, before)

    def test_exact_published_prior_seal_remains_immutable(self) -> None:
        self.assert_finalized_prior_seal_is_immutable(ProcedureVersion.State.PUBLISHED)

    def test_exact_withdrawn_prior_seal_remains_immutable(self) -> None:
        self.assert_finalized_prior_seal_is_immutable(ProcedureVersion.State.WITHDRAWN)

    def test_partial_scenario_upgrade_is_rejected(self) -> None:
        self.set_prior_scenario_seal("pre_fee")
        PlanningScenario.objects.filter(
            procedure_version=self.version,
            name="passport.student.false",
        ).delete()

        with self.assertRaisesMessage(ValidationError, "semantic conflict in scenarios"):
            import_passport_renewal(author=self.author)

    def test_failed_prior_upgrade_rolls_back_without_scenario_changes(self) -> None:
        self.set_prior_scenario_seal("legacy")
        before = list(
            PlanningScenario.objects.filter(procedure_version=self.version)
            .order_by("name")
            .values("name", "expected_result_family", "expected_identifiers")
        )
        Source.objects.filter(semantic_id="SRC-MOI-PASSPORT-REQ").update(title="Drift")

        with self.assertRaisesMessage(ValidationError, "semantic conflict in sources"):
            import_passport_renewal(author=self.author)

        after = list(
            PlanningScenario.objects.filter(procedure_version=self.version)
            .order_by("name")
            .values("name", "expected_result_family", "expected_identifiers")
        )
        self.assertEqual(after, before)

    def test_post_upgrade_failure_rolls_back_all_scenario_writes(self) -> None:
        self.set_prior_scenario_seal("legacy")
        before = list(
            PlanningScenario.objects.filter(procedure_version=self.version)
            .order_by("name")
            .values()
        )
        # The second seal check runs after routing/student saves and Fee scenario creation.
        with patch(
            "knowledge.importers.passport_renewal_integrity._verify_scenarios",
            side_effect=[
                _LEGACY_SCENARIO_DIGEST,
                ValidationError("injected post-upgrade failure"),
            ],
        ):
            with self.assertRaisesMessage(ValidationError, "injected post-upgrade failure"):
                import_passport_renewal(author=self.author)

        after = list(
            PlanningScenario.objects.filter(procedure_version=self.version)
            .order_by("name")
            .values()
        )
        self.assertEqual(after, before)
        self.assertEqual(
            _verify_scenarios(self.version, allow_legacy=True),
            _LEGACY_SCENARIO_DIGEST,
        )

    def test_prior_upgrade_invalidates_scenario_review_signature(self) -> None:
        self.set_prior_scenario_seal("pre_fee")
        reviewer = get_user_model().objects.create_user(username="passport-upgrade-reviewer")
        reviewer.user_permissions.add(Permission.objects.get(codename="review_procedureversion"))
        approval = approve_review_dimension(
            self.version.pk,
            dimension="scenario_behavior",
            actor=reviewer,
        )
        old_signature = approval.reviewed_signature
        self.assertEqual(old_signature, review_state_signature(self.version))

        import_passport_renewal(author=self.author)

        self.assertNotEqual(old_signature, review_state_signature(self.version))

    def test_rerun_rejects_fee_semantic_drift(self) -> None:
        Fee.objects.filter(
            procedure_version=self.version,
            semantic_id="passport.fee.base",
        ).update(amount=999)

        with self.assertRaisesMessage(ValidationError, "semantic conflict in planning behavior"):
            import_passport_renewal(author=self.author)

    def test_rerun_rejects_candidate_semantic_drift(self) -> None:
        candidate = ServiceProcedureCandidate.objects.get(
            procedure=self.version.procedure,
            service=self.version.procedure.primary_service,
        )
        ServiceProcedureCandidate.objects.filter(pk=candidate.pk).update(
            selection_predicate={"op": "eq", "fact": "citizenship", "value": "egyptian"}
        )

        with self.assertRaises(ValidationError):
            import_passport_renewal(author=self.author)

    def test_rerun_rejects_scenario_semantic_drift(self) -> None:
        scenario = PlanningScenario.objects.get(
            procedure_version=self.version,
            name="passport.fee.urgent",
        )
        PlanningScenario.objects.filter(pk=scenario.pk).update(
            expected_identifiers={"procedure_version_id": self.version.semantic_id}
        )

        with self.assertRaisesMessage(ValidationError, "semantic conflict in scenarios"):
            import_passport_renewal(author=self.author)

    def test_rerun_rejects_evidence_semantic_drift(self) -> None:
        fee = Fee.objects.get(
            procedure_version=self.version,
            semantic_id="passport.fee.base",
        )
        link = EvidenceLink.objects.get(fee=fee, semantic_id="EL-MOI-FEE-01")
        EvidenceLink.objects.filter(pk=link.pk).update(passage="Conflicting fee evidence")

        with self.assertRaisesMessage(ValidationError, "semantic conflict in evidence"):
            import_passport_renewal(author=self.author)

    def test_whitespace_evidence_identity_is_rejected_after_owner_installation(self) -> None:
        fee = Fee.objects.get(
            procedure_version=self.version,
            semantic_id="passport.fee.base",
        )
        link = EvidenceLink(
            fee=fee,
            semantic_id="   ",
            passage="Passage",
            location="Section",
            applicability_context="Context",
        )

        with self.assertRaisesMessage(ValidationError, "Evidence identity cannot be whitespace"):
            link.full_clean()

    def test_database_rejects_whitespace_evidence_identity(self) -> None:
        fee = Fee.objects.get(
            procedure_version=self.version,
            semantic_id="passport.fee.base",
        )
        link = EvidenceLink(
            fee=fee,
            semantic_id="   ",
            passage="Passage",
            location="Section",
            applicability_context="Context",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            EvidenceLink.objects.bulk_create([link])
