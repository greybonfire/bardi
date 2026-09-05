from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TransactionTestCase, override_settings

from knowledge.evidence_workflow import open_evidence_discrepancy
from knowledge.models import (
    ChecklistItem,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.review_workflow import (
    ProcedureVersionAuditApproval,
    ProcedureVersionReviewApproval,
    ProcedureVersionReviewPolicy,
    approve_review_dimension,
    approve_specialist_risk,
    required_review_dimensions,
    review_state_signature,
)

REVIEW_GATE = ("knowledge.review_workflow.ProcedureVersionReviewPublicationGate",)
CORE_DIMENSIONS = {
    ProcedureVersionReviewApproval.Dimension.EVIDENCE_SOURCE,
    ProcedureVersionReviewApproval.Dimension.RULE_LOGIC,
    ProcedureVersionReviewApproval.Dimension.SCENARIO_BEHAVIOR,
    ProcedureVersionReviewApproval.Dimension.BILINGUAL_SEMANTIC,
}


@override_settings(
    PROCEDURE_VERSION_REVIEWS_REQUIRED=True,
    PROCEDURE_VERSION_PUBLICATION_GATES=REVIEW_GATE,
)
class ProcedureVersionReviewWorkflowTests(TransactionTestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.author = user_model.objects.create_user(username="review-author")
        self.reviewer = user_model.objects.create_user(username="reviewer")
        self.specialist = user_model.objects.create_user(username="military-specialist")
        self.publisher = user_model.objects.create_user(username="review-publisher")
        self._grant(self.reviewer, "review_procedureversion")

        self.fact = FactDefinition.objects.create(
            key="review_case_flag",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.service = Service.objects.create(
            semantic_id="review.service",
            text_ar="خدمة المراجعة",
            text_en="Review service",
            is_active=True,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="review.procedure",
            text_ar="إجراء المراجعة",
            text_en="Review procedure",
            primary_service=self.service,
        )
        rule = {"op": "eq", "fact": self.fact.key, "value": True}
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=rule,
        )
        ServiceQuestion.objects.create(
            semantic_id="review.question.flag",
            service=self.service,
            fact=self.fact,
            text_ar="هل تنطبق الحالة؟",
            text_en="Does the case apply?",
            priority=1,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="review.procedure.v1",
            procedure=self.procedure,
            text_ar="نسخة قابلة للنشر",
            text_en="Publishable review version",
            applicability=rule,
        )

    def _permission(self, codename: str) -> Permission:
        return Permission.objects.get(
            content_type__app_label="knowledge",
            codename=codename,
        )

    def _grant(self, user: User, codename: str) -> None:
        user.user_permissions.add(self._permission(codename))
        for cache_name in ("_perm_cache", "_user_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def _revoke(self, user: User, codename: str) -> None:
        user.user_permissions.remove(self._permission(codename))
        for cache_name in ("_perm_cache", "_user_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def policy(self, **risks: bool) -> ProcedureVersionReviewPolicy:
        return ProcedureVersionReviewPolicy.objects.create(
            procedure_version=self.version,
            author=self.author,
            **risks,
        )

    def approve_core(
        self,
        reviewer: User | None = None,
    ) -> tuple[ProcedureVersionReviewApproval, ...]:
        actor = self.reviewer if reviewer is None else reviewer
        return tuple(
            approve_review_dimension(
                self.version.pk,
                dimension=dimension,
                actor=actor,
            )
            for dimension in sorted(CORE_DIMENSIONS)
        )

    def test_missing_policy_and_missing_dimensions_block_precisely(self) -> None:
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.publisher)
        self.assertIn(
            ("missing_review_policy", ""),
            {(item.code, item.detail) for item in caught.exception.diagnostics},
        )

        self.policy()
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.publisher)

        missing = {
            item.detail
            for item in caught.exception.diagnostics
            if item.gate == "core.procedure_version_reviews"
            and item.code == "missing_review_approval"
        }
        self.assertEqual(missing, CORE_DIMENSIONS)
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)
        self.assertFalse(self.version.audit_events.exists())

    def test_second_person_review_must_be_distinct_from_author_and_publisher(self) -> None:
        self.policy()
        self._grant(self.author, "review_procedureversion")
        with self.assertRaises(ValidationError):
            approve_review_dimension(
                self.version.pk,
                dimension=ProcedureVersionReviewApproval.Dimension.RULE_LOGIC,
                actor=self.author,
            )

        self.approve_core()
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.reviewer)
        self.assertEqual(
            {
                item.detail
                for item in caught.exception.diagnostics
                if item.code == "review_not_independent"
            },
            CORE_DIMENSIONS,
        )
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)

        published = publish_procedure_version(self.version.pk, actor=self.publisher)
        event = published.audit_events.get(event_type="published")
        audit_rows = tuple(event.approvals.select_related("actor", "approval").all())
        self.assertEqual(len(audit_rows), len(CORE_DIMENSIONS))
        self.assertEqual({row.actor for row in audit_rows}, {self.reviewer})
        self.assertEqual({row.dimension for row in audit_rows}, CORE_DIMENSIONS)

    def test_configured_military_risk_requires_currently_eligible_specialist(self) -> None:
        self.policy(military_risk=True)
        self.approve_core()

        with self.assertRaises(ValidationError):
            approve_specialist_risk(
                self.version.pk,
                risk_kind=ProcedureVersionReviewApproval.SpecialistRisk.MILITARY,
                actor=self.reviewer,
            )

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.publisher)
        self.assertIn(
            ("missing_specialist_approval", "military"),
            {(item.code, item.detail) for item in caught.exception.diagnostics},
        )

        self._grant(self.specialist, "specialist_approve_military")
        approval = approve_specialist_risk(
            self.version.pk,
            risk_kind=ProcedureVersionReviewApproval.SpecialistRisk.MILITARY,
            actor=self.specialist,
        )
        self.assertEqual(approval.specialist_risk, "military")

        self._revoke(self.specialist, "specialist_approve_military")
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.publisher)
        self.assertIn(
            ("specialist_reviewer_not_eligible", "military"),
            {(item.code, item.detail) for item in caught.exception.diagnostics},
        )

        self._grant(self.specialist, "specialist_approve_military")
        published = publish_procedure_version(self.version.pk, actor=self.publisher)
        event = published.audit_events.get(event_type="published")
        self.assertEqual(
            set(event.approvals.values_list("actor__username", flat=True)),
            {self.reviewer.username, self.specialist.username},
        )
        self.assertTrue(
            event.approvals.filter(
                approval_kind="specialist",
                specialist_risk="military",
                actor=self.specialist,
            ).exists()
        )

    def test_semantic_change_makes_existing_approvals_stale_until_reapproved(self) -> None:
        self.policy()
        original = self.approve_core()
        original_signature = review_state_signature(self.version)
        self.assertEqual({row.reviewed_signature for row in original}, {original_signature})

        self.version.text_en = "Changed reviewed meaning"
        self.version.save()
        changed_signature = review_state_signature(self.version)
        self.assertNotEqual(changed_signature, original_signature)

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.publisher)
        stale = {
            item.detail
            for item in caught.exception.diagnostics
            if item.code == "stale_review_approval"
        }
        self.assertEqual(stale, CORE_DIMENSIONS)

        fresh = self.approve_core()
        self.assertEqual({row.reviewed_signature for row in fresh}, {changed_signature})
        published = publish_procedure_version(self.version.pk, actor=self.publisher)
        event = published.audit_events.get(event_type="published")
        self.assertEqual(event.approvals.count(), len(CORE_DIMENSIONS))
        self.assertEqual(
            set(event.approvals.values_list("approval__reviewed_signature", flat=True)),
            {changed_signature},
        )

    def test_discrepancy_adds_its_own_required_review_dimension(self) -> None:
        self.policy()
        item = ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="review.checklist",
            text_ar="مستند",
            text_en="Document",
            classification=ChecklistItem.Classification.CANDIDATE,
            verification_state="current",
        )
        link = EvidenceLink.objects.create(
            checklist_item=item,
            passage="Conflicting researched passage",
            verification_state="current",
        )
        open_evidence_discrepancy(
            anchor_evidence_link=link,
            evidence_links=(link,),
            rationale="Internal disagreement requires disposition review.",
            actor=self.author,
        )

        self.assertEqual(
            required_review_dimensions(self.version),
            CORE_DIMENSIONS | {ProcedureVersionReviewApproval.Dimension.DISCREPANCY},
        )
        approval = approve_review_dimension(
            self.version.pk,
            dimension=ProcedureVersionReviewApproval.Dimension.DISCREPANCY,
            actor=self.reviewer,
        )
        self.assertEqual(approval.dimension, "discrepancy")

    def test_review_history_and_policy_cannot_be_rewritten_after_publication(self) -> None:
        policy = self.policy()
        approvals = self.approve_core()
        published = publish_procedure_version(self.version.pk, actor=self.publisher)

        policy.legal_risk = True
        with self.assertRaises(ValidationError):
            policy.save()
        approvals[0].dimension = ProcedureVersionReviewApproval.Dimension.RULE_LOGIC
        with self.assertRaises(ValidationError):
            approvals[0].save()
        with self.assertRaises(ValidationError):
            approvals[0].delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProcedureVersionReviewApproval.objects.filter(pk=approvals[0].pk).update(
                dimension=ProcedureVersionReviewApproval.Dimension.RULE_LOGIC
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProcedureVersionAuditApproval.objects.filter(
                audit_event__version=published
            ).update(dimension="rule_logic")
