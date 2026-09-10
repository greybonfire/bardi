from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from knowledge.evidence_workflow import (
    EvidenceReverificationEvent,
    _lock_workflow_evidence,
    open_evidence_discrepancy,
    resolve_evidence_discrepancy,
)
from knowledge.evidence_workflow_temporal import (
    EvidenceDiscrepancyTransition,
    _workflow_overlays_as_of,
)
from knowledge.models import ChecklistItem, EvidenceLink, Procedure, ProcedureVersion, Service

DAY_1 = date(2026, 9, 1)
DAY_2 = date(2026, 9, 2)
DAY_3 = date(2026, 9, 3)
DAY_4 = date(2026, 9, 4)


def _at(day: date, hour: int = 9) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


class RecentWorkflowRegressionTests(TransactionTestCase):
    """Backfill correctness coverage skipped by issues #93 and #109."""

    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="recent-workflow-regression")
        self.service = Service.objects.create(
            semantic_id="recent.workflow.service",
            text_ar="خدمة",
            text_en="Service",
        )
        self.procedure = Procedure.objects.create(
            semantic_id="recent.workflow.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="recent.workflow.procedure.v1",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability={},
        )
        self.item = ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="recent.workflow.item",
            text_ar="متطلب",
            text_en="Requirement",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            verification_state="current",
            verified_on=DAY_1,
        )
        self.link = EvidenceLink.objects.create(
            checklist_item=self.item,
            semantic_id="recent.workflow.evidence",
            passage="Passage",
            location="Section 1",
            applicability_context="Applies to the procedure",
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
            verification_state="current",
            verified_on=DAY_1,
        )

    @property
    def owner_key(self) -> tuple[str, str, str]:
        return ("checklist", self.version.semantic_id, self.item.semantic_id)

    def _open(self, state: str, day: date):
        with patch("django.utils.timezone.now", return_value=_at(day)):
            discrepancy = open_evidence_discrepancy(
                anchor_evidence_link=self.link,
                evidence_links=(self.link,),
                rationale=f"Open {state} discrepancy",
                actor=self.actor,
                outcome_state=state,  # type: ignore[arg-type]
            )
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.OPENED,
        ).update(occurred_at=_at(day))
        return discrepancy

    def _resolve(self, discrepancy, state: str, day: date) -> None:
        with patch("django.utils.timezone.now", return_value=_at(day)):
            resolve_evidence_discrepancy(
                discrepancy.pk,
                outcome_state=state,  # type: ignore[arg-type]
                resolution=f"Resolve to {state}",
                actor=self.actor,
            )
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.RESOLVED,
        ).update(occurred_at=_at(day))

    def _review(self, state: str, day: date) -> None:
        event = EvidenceReverificationEvent.objects.create(
            anchor_evidence_link=self.link,
            verification_state=state,
            verified_on=day,
            reverify_on=None,
            rationale=f"Review to {state}",
            meaning_changed=False,
            actor=self.actor,
        )
        EvidenceReverificationEvent.objects.filter(pk=event.pk).update(occurred_at=_at(day, 10))

    def test_open_discrepancy_survives_later_current_review_without_erasing_evidence_overlay(
        self,
    ) -> None:
        self._open("disputed", DAY_1)
        self._review("current", DAY_2)

        overlay = _workflow_overlays_as_of(DAY_3)[self.owner_key]

        self.assertEqual(overlay.state, "disputed")
        self.assertEqual(overlay.evidence_state, "current")
        self.assertEqual(overlay.evidence_verified_on, DAY_2)

    def test_resolving_one_discrepancy_does_not_clear_another_and_history_uses_transitions(
        self,
    ) -> None:
        first = self._open("needs_reverification", DAY_1)
        second = self._open("disputed", DAY_2)

        both_open = _workflow_overlays_as_of(DAY_2)[self.owner_key]
        self.assertEqual(both_open.state, "disputed")

        self._resolve(second, "current", DAY_3)
        one_open = _workflow_overlays_as_of(DAY_3)[self.owner_key]
        self.assertEqual(one_open.state, "needs_reverification")

        # Present-day resolution must not back-project into an earlier evaluation date.
        historical = _workflow_overlays_as_of(DAY_2)[self.owner_key]
        self.assertEqual(historical.state, "disputed")

        self._resolve(first, "unknown", DAY_4)
        fully_resolved = _workflow_overlays_as_of(DAY_4)[self.owner_key]
        self.assertEqual(fully_resolved.state, "unknown")

    def test_workflow_lock_helper_locks_all_versions_before_any_evidence(self) -> None:
        successor = ProcedureVersion.objects.create(
            semantic_id="recent.workflow.procedure.v2",
            procedure=self.procedure,
            text_ar="نسخة لاحقة",
            text_en="Successor",
            applicability={},
        )

        with transaction.atomic():
            with CaptureQueriesContext(connection) as queries:
                _lock_workflow_evidence(
                    {self.link.pk},
                    successor_version_id=successor.pk,
                )

        locking_sql = [
            query["sql"] for query in queries if "FOR UPDATE" in query["sql"].upper()
        ]
        version_lock_positions = [
            index
            for index, sql in enumerate(locking_sql)
            if "knowledge_procedureversion" in sql
        ]
        evidence_lock_positions = [
            index for index, sql in enumerate(locking_sql) if "knowledge_evidencelink" in sql
        ]
        self.assertTrue(version_lock_positions, locking_sql)
        self.assertTrue(evidence_lock_positions, locking_sql)
        self.assertLess(max(version_lock_positions), min(evidence_lock_positions), locking_sql)
