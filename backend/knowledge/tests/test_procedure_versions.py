from __future__ import annotations

from datetime import date
from threading import Barrier, Thread
from typing import Any
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from knowledge.models import (
    FactDefinition,
    Procedure,
    ProcedureVersion,
    ProcedureVersionAuditEvent,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.publication import (
    PublicationDiagnostic,
    PublicationRejected,
    publish_procedure_version,
    withdraw_procedure_version,
)


class RejectingGate:
    name = "test.rejecting"

    def validate(self, context: object) -> tuple[PublicationDiagnostic, ...]:
        return (PublicationDiagnostic(self.name, "rejected"),)


class RaisingGate:
    name = "test.raising"

    def validate(self, context: object) -> tuple[PublicationDiagnostic, ...]:
        raise RuntimeError("must fail closed")


class DuplicateCoreNameGate:
    name = "core.bilingual"

    def validate(self, context: object) -> tuple[PublicationDiagnostic, ...]:
        return ()


class ProcedureVersionTests(TestCase):
    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="publisher")
        self.student_fact, _ = FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        self.service = Service.objects.create(
            semantic_id="versions.service", text_ar="خدمة", text_en="Service"
        )
        ServiceQuestion.objects.create(
            semantic_id="versions.question.is-student",
            service=self.service,
            fact=self.student_fact,
            text_ar="هل أنت طالب؟",
            text_en="Are you a student?",
            priority=10,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="versions.procedure",
            text_ar="تنقل",
            text_en="Navigation",
            primary_service=self.service,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate={"op": "eq", "fact": "is_student", "value": True},
        )

    def draft(self, semantic_id: str = "versions.v1", **kwargs: Any) -> ProcedureVersion:
        values: dict[str, Any] = {
            "semantic_id": semantic_id,
            "procedure": self.procedure,
            "text_ar": "إجراء عام",
            "text_en": "Public procedure",
            "applicability": {"op": "eq", "fact": "is_student", "value": True},
        }
        values.update(kwargs)
        return ProcedureVersion.objects.create(**values)

    def test_drafts_allow_incomplete_editorial_content(self) -> None:
        draft = self.draft(text_ar="", text_en="", applicability={"op": "broken"})
        self.assertEqual(draft.state, ProcedureVersion.State.DRAFT)
        self.assertIsNone(draft.published_at)

    def test_success_records_actor_and_audit_then_withdraws_without_semantic_change(self) -> None:
        draft = self.draft(effective_from=date(2025, 1, 1), effective_to=None)
        published = publish_procedure_version(draft.pk, actor=self.actor)
        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)
        self.assertEqual(published.published_by, self.actor)
        event = published.audit_events.get(event_type="published")
        self.assertEqual(
            (event.actor, event.from_state, event.to_state),
            (
                self.actor,
                "draft",
                "published",
            ),
        )
        original = (published.semantic_id, published.text_ar, published.applicability)
        withdrawn = withdraw_procedure_version(published.pk, actor=self.actor)
        self.assertEqual(withdrawn.state, ProcedureVersion.State.WITHDRAWN)
        self.assertEqual(
            (withdrawn.semantic_id, withdrawn.text_ar, withdrawn.applicability), original
        )
        self.assertEqual(withdrawn.audit_events.count(), 2)

    def test_all_core_failures_leave_draft_and_audit_unchanged(self) -> None:
        cases: tuple[tuple[dict[str, Any], str], ...] = (
            ({"text_ar": ""}, "missing_arabic_text"),
            ({"text_en": "  "}, "missing_english_text"),
            ({"applicability": {"op": "broken"}}, "unsupported_rule_operator:broken"),
            (
                {"applicability": {"op": "eq", "fact": "unknown", "value": True}},
                "unsupported_rule_fact:unknown",
            ),
        )
        for index, (changes, code) in enumerate(cases):
            with self.subTest(code=code):
                draft = self.draft(f"versions.bad.{index}", **changes)
                with self.assertRaises(PublicationRejected) as caught:
                    publish_procedure_version(draft.pk, actor=self.actor)
                self.assertIn(code, {item.code for item in caught.exception.diagnostics})
                draft.refresh_from_db()
                self.assertEqual(draft.state, ProcedureVersion.State.DRAFT)
                self.assertIsNone(draft.published_at)
                self.assertFalse(draft.audit_events.exists())

    def test_unpublished_fact_dependency_rejects_publication(self) -> None:
        fact = FactDefinition.objects.create(
            key="versions.unpublished_dependency", kind=FactDefinition.Kind.BOOLEAN
        )
        draft = self.draft(
            "versions.unpublished-fact",
            applicability={"op": "eq", "fact": fact.key, "value": True},
        )

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(draft.pk, actor=self.actor)

        self.assertIn(
            f"unsupported_rule_fact:{fact.key}",
            {item.code for item in caught.exception.diagnostics},
        )
        draft.refresh_from_db()
        self.assertEqual(draft.state, ProcedureVersion.State.DRAFT)
        self.assertIsNone(draft.published_at)
        self.assertFalse(draft.audit_events.exists())

    def test_published_fact_dependency_allows_publication_and_is_immutable(self) -> None:
        fact = FactDefinition.objects.create(
            key="versions.published_dependency", kind=FactDefinition.Kind.BOOLEAN
        )
        fact.is_published = True
        fact.save()
        ServiceQuestion.objects.create(
            semantic_id="versions.question.published-dependency",
            service=self.service,
            fact=fact,
            text_ar="هل ينطبق الشرط المنشور؟",
            text_en="Does the published condition apply?",
            priority=20,
        )
        draft = self.draft(
            "versions.published-fact",
            applicability={"op": "eq", "fact": fact.key, "value": True},
        )

        published = publish_procedure_version(draft.pk, actor=self.actor)

        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)
        self.assertEqual(published.published_by, self.actor)
        fact.kind = FactDefinition.Kind.STRING
        with self.assertRaises(ValidationError):
            fact.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactDefinition.objects.filter(pk=fact.pk).update(kind=FactDefinition.Kind.STRING)

    def test_non_user_actor_is_rejected_even_when_its_primary_key_matches_a_user(self) -> None:
        draft = self.draft()
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(draft.pk, actor=self.service)
        self.assertIn("invalid_actor", {item.code for item in caught.exception.diagnostics})
        draft.refresh_from_db()
        self.assertEqual(draft.state, ProcedureVersion.State.DRAFT)

    def test_lifecycle_capability_does_not_leak_into_an_outer_transaction(self) -> None:
        published = self.draft(
            "versions.closed", effective_from=None, effective_to=date(2025, 1, 1)
        )
        bypass = self.draft("versions.bypass", effective_from=date(2025, 1, 2))
        publish_procedure_version(published.pk, actor=self.actor)

        with self.assertRaises(DatabaseError), transaction.atomic():
            ProcedureVersion.objects.filter(pk=bypass.pk).update(
                state=ProcedureVersion.State.PUBLISHED,
                published_at=timezone.now(),
                published_by_id=self.actor.pk,
            )
        bypass.refresh_from_db()
        self.assertEqual(bypass.state, ProcedureVersion.State.DRAFT)

    def test_overlap_is_inclusive_and_null_unbounded(self) -> None:
        first = self.draft("versions.first", effective_from=None, effective_to=date(2025, 1, 31))
        publish_procedure_version(first.pk, actor=self.actor)
        touching = self.draft(
            "versions.touching", effective_from=date(2025, 1, 31), effective_to=None
        )
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(touching.pk, actor=self.actor)
        self.assertIn(
            "overlapping_published_version",
            {item.code for item in caught.exception.diagnostics},
        )
        touching.refresh_from_db()
        self.assertEqual(touching.state, "draft")

    def test_ordinary_model_queryset_and_audit_paths_cannot_bypass_services(self) -> None:
        draft = self.draft()
        draft.state = ProcedureVersion.State.PUBLISHED
        with self.assertRaises(ValidationError):
            draft.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProcedureVersion.objects.filter(pk=draft.pk).update(state="published")
        with self.assertRaises(ValidationError):
            ProcedureVersionAuditEvent.objects.create(
                version=draft,
                event_type="published",
                actor=self.actor,
                occurred_at="2025-01-01T00:00:00Z",
                from_state="draft",
                to_state="published",
            )

    def test_published_semantics_deletion_and_procedure_ownership_are_protected(self) -> None:
        published = publish_procedure_version(self.draft().pk, actor=self.actor)
        published.text_en = "Changed"
        with self.assertRaises(ValidationError):
            published.save()
        with self.assertRaises(ValidationError):
            published.delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProcedureVersion.objects.filter(pk=published.pk).update(text_en="Changed")
        with self.assertRaises(DatabaseError), transaction.atomic():
            Procedure.objects.filter(pk=self.procedure.pk).update(semantic_id="changed")

    def test_audit_failure_rolls_back_publication(self) -> None:
        draft = self.draft()
        with (
            patch("knowledge.publication._create_audit_event", side_effect=RuntimeError("audit")),
            self.assertRaises(RuntimeError),
        ):
            publish_procedure_version(draft.pk, actor=self.actor)
        draft.refresh_from_db()
        self.assertEqual(draft.state, "draft")
        self.assertFalse(draft.audit_events.exists())

    @override_settings(
        PROCEDURE_VERSION_PUBLICATION_GATES=(
            "knowledge.tests.test_procedure_versions.RejectingGate",
            "knowledge.tests.test_procedure_versions.RaisingGate",
        )
    )
    def test_extension_gates_all_run_and_fail_closed(self) -> None:
        draft = self.draft()
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(draft.pk, actor=self.actor)
        self.assertEqual(
            tuple(
                (item.gate, item.code)
                for item in caught.exception.diagnostics
                if item.gate.startswith("test.")
            ),
            (("test.raising", "gate_execution_failed"), ("test.rejecting", "rejected")),
        )

    @override_settings(PROCEDURE_VERSION_PUBLICATION_GATES=("missing.module.Gate",))
    def test_missing_gate_fails_closed(self) -> None:
        draft = self.draft()
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(draft.pk, actor=self.actor)
        self.assertIn("gate_load_failed", {item.code for item in caught.exception.diagnostics})

    @override_settings(
        PROCEDURE_VERSION_PUBLICATION_GATES=(
            "knowledge.tests.test_procedure_versions.DuplicateCoreNameGate",
        )
    )
    def test_duplicate_gate_name_fails_closed(self) -> None:
        draft = self.draft()
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(draft.pk, actor=self.actor)
        self.assertIn("duplicate_gate_name", {item.code for item in caught.exception.diagnostics})


class ConcurrentProcedureVersionPublicationTests(TransactionTestCase):
    reset_sequences = True

    def test_overlapping_publications_serialize_on_the_procedure(self) -> None:
        student_fact, _ = FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        actor = get_user_model().objects.create_user(username="concurrent-publisher")
        service = Service.objects.create(
            semantic_id="concurrent.service", text_ar="خدمة", text_en="Service"
        )
        ServiceQuestion.objects.create(
            semantic_id="concurrent.question.is-student",
            service=service,
            fact=student_fact,
            text_ar="هل أنت طالب؟",
            text_en="Are you a student?",
            priority=10,
        )
        procedure = Procedure.objects.create(
            semantic_id="concurrent.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        ServiceProcedureCandidate.objects.create(
            service=service,
            procedure=procedure,
            selection_predicate={"op": "eq", "fact": "is_student", "value": True},
        )
        drafts = tuple(
            ProcedureVersion.objects.create(
                semantic_id=f"concurrent.v{index}",
                procedure=procedure,
                effective_from=date(2025, 1, 1),
                text_ar="نسخة",
                text_en="Version",
                applicability={"op": "eq", "fact": "is_student", "value": True},
            )
            for index in (1, 2)
        )
        barrier = Barrier(2)
        results: list[str] = []

        def publish(version_id: int) -> None:
            close_old_connections()
            try:
                thread_actor = get_user_model().objects.get(pk=actor.pk)
                barrier.wait(timeout=10)
                publish_procedure_version(version_id, actor=thread_actor)
            except PublicationRejected:
                results.append("rejected")
            else:
                results.append("published")
            finally:
                close_old_connections()

        threads = [Thread(target=publish, args=(draft.pk,), daemon=True) for draft in drafts]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads), "publication deadlocked")
        self.assertCountEqual(results, ("published", "rejected"))
        self.assertEqual(
            ProcedureVersion.objects.filter(state=ProcedureVersion.State.PUBLISHED).count(), 1
        )
        self.assertEqual(
            ProcedureVersion.objects.filter(state=ProcedureVersion.State.DRAFT).count(), 1
        )
        self.assertEqual(ProcedureVersionAuditEvent.objects.count(), 1)
