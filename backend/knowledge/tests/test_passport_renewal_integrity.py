from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from knowledge.fees import Fee
from knowledge.importers.passport_renewal import import_passport_renewal
from knowledge.models import EvidenceLink, ServiceProcedureCandidate
from knowledge.planning_scenarios import PlanningScenario


class PassportRenewalIntegrityTests(TestCase):
    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(
            username="passport-integrity-author",
            is_staff=True,
        )
        self.version = import_passport_renewal(author=self.author)

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
