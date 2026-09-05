from __future__ import annotations

from datetime import date
from threading import Event, Thread
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from knowledge.domain import load_knowledge_snapshot
from knowledge.models import (
    Authority,
    ChecklistItem,
    DocumentType,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    Source,
)
from knowledge.publication import (
    PublicationDiagnostic,
    PublicationRejected,
    publish_procedure_version,
)
from knowledge.services import set_evidence_link_sources

PUBLICATION_LOCKED = Event()
PUBLICATION_CONTINUE = Event()


class BlockingChecklistGate:
    name = "test.blocking_checklist"

    def validate(self, context: object) -> tuple[PublicationDiagnostic, ...]:
        PUBLICATION_LOCKED.set()
        if not PUBLICATION_CONTINUE.wait(timeout=10):
            raise RuntimeError("test synchronization timeout")
        return ()


class ChecklistPublicationTests(TestCase):
    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="checklist-publisher")
        self.service = Service.objects.create(
            semantic_id="checklist.service", text_ar="خدمة", text_en="Service"
        )
        self.procedure = Procedure.objects.create(
            semantic_id="checklist.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        predicate = {"op": "eq", "fact": "is_student", "value": True}
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=predicate,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="checklist.version",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=predicate,
        )
        self.authority = Authority.objects.create(
            semantic_id="authority.civil", name_ar="جهة", name_en="Authority"
        )
        self.document_type = DocumentType.objects.create(
            semantic_id="document.identity", name_ar="هوية", name_en="Identity"
        )

    def source(self, classification: str = Source.Classification.OFFICIAL, **kwargs: Any) -> Source:
        values: dict[str, Any] = {
            "semantic_id": f"source.{classification}",
            "authority": self.authority,
            "title": "Source title",
            "locator": "https://example.test/source",
            "classification": classification,
            "retrieved_on": date(2026, 8, 1),
        }
        values.update(kwargs)
        return Source.objects.create(**values)

    def item(
        self,
        classification: str = ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
        **kwargs: Any,
    ) -> ChecklistItem:
        values: dict[str, Any] = {
            "procedure_version": self.version,
            "semantic_id": "claim.identity",
            "text_ar": "أحضر الهوية",
            "text_en": "Bring identification",
            "classification": classification,
            "document_type": self.document_type,
            "quantity": 1,
            "verification_state": "current",
        }
        values.update(kwargs)
        return ChecklistItem.objects.create(**values)

    def evidence(
        self,
        item: ChecklistItem,
        source: Source,
        **kwargs: Any,
    ) -> EvidenceLink:
        values: dict[str, Any] = {
            "checklist_item": item,
            "passage": "Exact relied-upon passage",
            "location": "Section 1",
            "applicability_context": "Applies to this procedure",
            "verification_state": "current",
            "support_status": EvidenceLink.SupportStatus.SUPPORTS,
        }
        values.update(kwargs)
        link = EvidenceLink.objects.create(**values)
        set_evidence_link_sources(link, (source,))
        return link

    def rejection_codes(self) -> set[str]:
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)
        return {diagnostic.code for diagnostic in caught.exception.diagnostics}

    def test_current_claim_requires_complete_current_support(self) -> None:
        item = self.item(ChecklistItem.Classification.PRACTICAL_PREPARATION)
        source = self.source()
        self.evidence(item, source, support_status=EvidenceLink.SupportStatus.CONTEXT)
        self.assertIn("adequate_evidence_required", self.rejection_codes())

    def test_current_claim_rejects_unresolved_current_contradiction(self) -> None:
        item = self.item()
        self.evidence(item, self.source())
        field_report = self.source(
            Source.Classification.FIELD_REPORT,
            observation_date=date(2026, 7, 31),
            observation_context="Observed at the named office.",
        )
        self.evidence(
            item,
            field_report,
            support_status=EvidenceLink.SupportStatus.CONTRADICTS,
        )

        self.assertIn("unresolved_evidence_contradiction", self.rejection_codes())

    def test_official_requirement_cannot_rely_only_on_a_field_report(self) -> None:
        item = self.item()
        field_report = self.source(
            Source.Classification.FIELD_REPORT,
            observation_date=date(2026, 7, 31),
            observation_context="Observed at the named office.",
        )
        self.evidence(item, field_report)
        self.assertIn("official_evidence_required", self.rejection_codes())

    def test_field_guidance_requires_observation_date_and_context(self) -> None:
        item = self.item(ChecklistItem.Classification.PRACTICAL_PREPARATION)
        self.evidence(item, self.source(Source.Classification.FIELD_REPORT))
        self.assertIn("malformed_field_guidance", self.rejection_codes())

    def test_candidate_and_basis_scoped_claims_remain_authored_but_not_current(self) -> None:
        self.item(
            ChecklistItem.Classification.CANDIDATE,
            verification_state="needs_reverification",
            scope=ChecklistItem.Scope.ELIGIBILITY_BASIS,
            scope_reference="basis.family",
        )
        published = publish_procedure_version(self.version.pk, actor=self.actor)
        self.assertEqual(published.state, ProcedureVersion.State.PUBLISHED)

    def test_reusable_provenance_is_preserved_after_publication(self) -> None:
        item = self.item()
        source = self.source()
        link = self.evidence(item, source)
        publish_procedure_version(self.version.pk, actor=self.actor)

        second = ProcedureVersion.objects.create(
            semantic_id="checklist.version.next",
            procedure=self.procedure,
            text_ar="نسخة لاحقة",
            text_en="Next version",
            applicability={},
        )
        reused = ChecklistItem.objects.create(
            procedure_version=second,
            semantic_id="claim.identity",
            text_ar="أحضر الهوية",
            text_en="Bring identification",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            document_type=self.document_type,
            verification_state="needs_reverification",
        )
        reused_link = self.evidence(reused, source)
        self.assertEqual(Source.objects.filter(semantic_id=source.semantic_id).count(), 1)

        updates = (
            (EvidenceLink, reused_link.pk, {"checklist_item_id": item.pk}),
            (ChecklistItem, item.pk, {"text_en": "Changed"}),
            (EvidenceLink, link.pk, {"passage": "Changed"}),
            (Source, source.pk, {"title": "Changed"}),
            (Authority, self.authority.pk, {"name_en": "Changed"}),
            (DocumentType, self.document_type.pk, {"name_en": "Changed"}),
        )
        for model, primary_key, values in updates:
            with self.subTest(model=model.__name__), self.assertRaises(DatabaseError):
                with transaction.atomic():
                    model.objects.filter(pk=primary_key).update(**values)

        with self.assertRaises(ValidationError):
            source.delete()
        with self.assertRaises(ValidationError):
            self.document_type.delete()

    def test_snapshot_detaches_claim_specific_evidence_from_the_orm(self) -> None:
        item = self.item()
        source = self.source()
        self.evidence(item, source)
        publish_procedure_version(self.version.pk, actor=self.actor)

        snapshot = load_knowledge_snapshot()
        version = next(
            value
            for value in snapshot.procedure_versions
            if value.semantic_id == self.version.semantic_id
        )
        with self.assertNumQueries(0):
            claim = version.checklist_items[0]
            self.assertEqual(claim.semantic_id, item.semantic_id)
            self.assertEqual(claim.evidence_links[0].sources[0].semantic_id, source.semantic_id)
            self.assertEqual(claim.evidence_links[0].sources[0].title, "Source title")


@override_settings(
    PROCEDURE_VERSION_PUBLICATION_GATES=(
        "knowledge.tests.test_checklist_items.BlockingChecklistGate",
    )
)
class ChecklistPublicationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_evidence_provenance_cannot_change_during_publication(self) -> None:
        PUBLICATION_LOCKED.clear()
        PUBLICATION_CONTINUE.clear()
        FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        actor = get_user_model().objects.create_user(username="checklist-race-publisher")
        service = Service.objects.create(
            semantic_id="checklist.race.service", text_ar="خدمة", text_en="Service"
        )
        procedure = Procedure.objects.create(
            semantic_id="checklist.race.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        predicate = {"op": "eq", "fact": "is_student", "value": True}
        ServiceProcedureCandidate.objects.create(
            service=service, procedure=procedure, selection_predicate=predicate
        )
        version = ProcedureVersion.objects.create(
            semantic_id="checklist.race.version",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=predicate,
        )
        authority = Authority.objects.create(
            semantic_id="checklist.race.authority", name_ar="جهة", name_en="Authority"
        )
        document_type = DocumentType.objects.create(
            semantic_id="checklist.race.document",
            name_ar="مستند",
            name_en="Document",
        )
        source = Source.objects.create(
            semantic_id="checklist.race.source",
            authority=authority,
            title="Official source",
            locator="https://example.test/race",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )
        item = ChecklistItem.objects.create(
            procedure_version=version,
            semantic_id="checklist.race.claim",
            text_ar="مستند",
            text_en="Document",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            document_type=document_type,
            verification_state="current",
        )
        evidence = EvidenceLink.objects.create(
            checklist_item=item,
            passage="Passage",
            location="Section",
            applicability_context="Context",
            verification_state="current",
        )
        set_evidence_link_sources(evidence, (source,))
        outcomes: list[str] = []

        def publish() -> None:
            close_old_connections()
            try:
                thread_actor = get_user_model().objects.get(pk=actor.pk)
                publish_procedure_version(version.pk, actor=thread_actor)
                outcomes.append("published")
            finally:
                close_old_connections()

        def mutate(model: Any, primary_key: int, values: dict[str, object]) -> None:
            close_old_connections()
            try:
                model.objects.filter(pk=primary_key).update(**values)
            except DatabaseError:
                outcomes.append(f"{model.__name__}_mutation_blocked")
            finally:
                close_old_connections()

        publisher = Thread(target=publish, daemon=True)
        publisher.start()
        self.assertTrue(PUBLICATION_LOCKED.wait(timeout=10))
        mutations = (
            (EvidenceLink, evidence.pk, {"passage": "Raced mutation"}),
            (Authority, authority.pk, {"name_en": "Raced mutation"}),
            (DocumentType, document_type.pk, {"name_en": "Raced mutation"}),
        )
        mutators = tuple(
            Thread(target=mutate, args=mutation, daemon=True) for mutation in mutations
        )
        for mutator in mutators:
            mutator.start()
        PUBLICATION_CONTINUE.set()
        publisher.join(timeout=20)
        for mutator in mutators:
            mutator.join(timeout=20)
        self.assertFalse(
            publisher.is_alive() or any(mutator.is_alive() for mutator in mutators),
            "publication deadlocked",
        )
        self.assertCountEqual(
            outcomes,
            (
                "published",
                "EvidenceLink_mutation_blocked",
                "Authority_mutation_blocked",
                "DocumentType_mutation_blocked",
            ),
        )
        version.refresh_from_db()
        evidence.refresh_from_db()
        authority.refresh_from_db()
        document_type.refresh_from_db()
        self.assertEqual(version.state, ProcedureVersion.State.PUBLISHED)
        self.assertEqual(evidence.passage, "Passage")
        self.assertEqual(authority.name_en, "Authority")
        self.assertEqual(document_type.name_en, "Document")
