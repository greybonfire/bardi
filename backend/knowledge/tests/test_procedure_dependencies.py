from __future__ import annotations

from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase

from knowledge.domain import load_knowledge_snapshot
from knowledge.models import (
    Authority,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
)
from knowledge.procedure_dependencies import ProcedureDependency
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.services import set_evidence_link_sources


class ProcedureDependencyKnowledgeTests(TestCase):
    def setUp(self) -> None:
        self.entry = FactDefinition.objects.create(
            key="dependency_entry",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.applies = FactDefinition.objects.create(
            key="dependency_applies",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.satisfied = FactDefinition.objects.create(
            key="dependency_satisfied",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.actor = get_user_model().objects.create_user(username="dependency-publisher")
        self.service = Service.objects.create(
            semantic_id="dependency.service",
            text_ar="خدمة",
            text_en="Service",
        )
        self.target_service = Service.objects.create(
            semantic_id="dependency.target-service",
            text_ar="خدمة مستهدفة",
            text_en="Target service",
        )
        self.procedure = Procedure.objects.create(
            semantic_id="dependency.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        self.target = Procedure.objects.create(
            semantic_id="dependency.target",
            text_ar="الإجراء السابق",
            text_en="Prerequisite procedure",
            primary_service=self.target_service,
        )
        self.entry_rule = {"op": "eq", "fact": self.entry.key, "value": True}
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=self.entry_rule,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.target_service,
            procedure=self.target,
            selection_predicate=self.entry_rule,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="dependency.version",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=self.entry_rule,
        )
        self.authority = Authority.objects.create(
            semantic_id="dependency.authority",
            name_ar="جهة",
            name_en="Authority",
        )
        self.source = Source.objects.create(
            semantic_id="dependency.source",
            authority=self.authority,
            title="Official prerequisite source",
            locator="https://example.test/prerequisite",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )

    def add_question(self, fact: FactDefinition, *, suffix: str, priority: int) -> None:
        ServiceQuestion.objects.create(
            semantic_id=f"dependency.question.{suffix}",
            service=self.service,
            fact=fact,
            text_ar=f"سؤال {suffix}",
            text_en=f"Question {suffix}",
            priority=priority,
        )

    def dependency(self, **overrides: Any) -> ProcedureDependency:
        values: dict[str, Any] = {
            "procedure_version": self.version,
            "semantic_id": "dependency.required-id",
            "text_ar": "استوفِ الإجراء السابق",
            "text_en": "Complete the prerequisite procedure",
            "target_procedure": self.target,
            "relation": ProcedureDependency.Relation.BLOCKING_PREREQUISITE,
            "applicability": {"op": "eq", "fact": self.applies.key, "value": True},
            "satisfied_when": {
                "op": "eq",
                "fact": self.satisfied.key,
                "value": True,
            },
            "display_order": 10,
            "verification_state": "current",
            "verified_on": date(2026, 8, 1),
        }
        values.update(overrides)
        return ProcedureDependency.objects.create(**values)

    def evidence(self, dependency: ProcedureDependency) -> EvidenceLink:
        link = EvidenceLink.objects.create(
            procedure_dependency=dependency,
            passage="Prerequisite passage",
            location="Section 1",
            applicability_context="Ordinary applicant",
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        set_evidence_link_sources(link, (self.source,))
        return link

    def rejection(self) -> PublicationRejected:
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)
        return caught.exception

    def test_model_rejects_self_dependency_relation_and_malformed_rules(self) -> None:
        invalid = (
            ProcedureDependency(
                procedure_version=self.version,
                semantic_id="dependency.self",
                text_ar="ذاتي",
                text_en="Self",
                target_procedure=self.procedure,
                satisfied_when=self.entry_rule,
            ),
            ProcedureDependency(
                procedure_version=self.version,
                semantic_id="dependency.relation",
                text_ar="علاقة",
                text_en="Relation",
                target_procedure=self.target,
                relation="unsupported",
                satisfied_when=self.entry_rule,
            ),
            ProcedureDependency(
                procedure_version=self.version,
                semantic_id="dependency.missing-rule",
                text_ar="قاعدة",
                text_en="Rule",
                target_procedure=self.target,
                satisfied_when={},
            ),
            ProcedureDependency(
                procedure_version=self.version,
                semantic_id="dependency.bad-rule",
                text_ar="قاعدة",
                text_en="Rule",
                target_procedure=self.target,
                satisfied_when={"op": "unsupported", "fact": self.satisfied.key},
            ),
        )
        for dependency in invalid:
            with self.subTest(semantic_id=dependency.semantic_id), self.assertRaises(
                ValidationError
            ):
                dependency.full_clean()

    def test_evidence_requires_exactly_one_dependency_owner(self) -> None:
        dependency = self.dependency()
        valid = EvidenceLink(
            procedure_dependency=dependency,
            passage="Passage",
            location="Section",
            applicability_context="Context",
            verification_state="current",
        )
        valid.full_clean()
        self.assertIs(valid.owner, dependency)

        invalid = EvidenceLink(
            procedure_dependency=dependency,
            passage="Passage",
            location="Section",
            applicability_context="Context",
            verification_state="current",
        )
        invalid.warning_id = 999
        with self.assertRaises(ValidationError):
            invalid.full_clean(exclude=("warning",))

    def test_publication_requires_evidence_and_question_coverage(self) -> None:
        self.add_question(self.applies, suffix="applies", priority=1)
        self.dependency()

        diagnostics = self.rejection().diagnostics
        codes = {(item.code, item.detail) for item in diagnostics}
        self.assertIn(("evidence_required", "dependency.required-id"), codes)
        self.assertIn(("adequate_evidence_required", "dependency.required-id"), codes)
        self.assertIn(("missing_service_question", self.satisfied.key), codes)

    def test_publication_rejects_malformed_persisted_rules_and_self_dependency(self) -> None:
        self.add_question(self.applies, suffix="applies", priority=1)
        self.add_question(self.satisfied, suffix="satisfied", priority=2)
        dependency = self.dependency()
        self.evidence(dependency)

        ProcedureDependency.objects.filter(pk=dependency.pk).update(
            applicability={"op": "unsupported", "fact": self.applies.key}
        )
        malformed = self.rejection().diagnostics
        self.assertTrue(
            any(item.detail == "dependency.required-id:applicability" for item in malformed)
        )

        ProcedureDependency.objects.filter(pk=dependency.pk).update(
            applicability={"op": "eq", "fact": self.applies.key, "value": True},
            target_procedure=self.procedure,
        )
        self.assertIn(
            ("self_dependency", "dependency.required-id"),
            {(item.code, item.detail) for item in self.rejection().diagnostics},
        )

    def test_publication_rejects_blocking_cycle(self) -> None:
        self.add_question(self.applies, suffix="applies", priority=1)
        self.add_question(self.satisfied, suffix="satisfied", priority=2)
        target_question = ServiceQuestion.objects.create(
            semantic_id="dependency.target.question.satisfied",
            service=self.target_service,
            fact=self.satisfied,
            text_ar="هل اكتمل؟",
            text_en="Completed?",
            priority=1,
        )
        self.assertIsNotNone(target_question.pk)
        target_version = ProcedureVersion.objects.create(
            semantic_id="dependency.target.version",
            procedure=self.target,
            text_ar="نسخة مستهدفة",
            text_en="Target version",
            applicability=self.entry_rule,
        )
        reverse = ProcedureDependency.objects.create(
            procedure_version=target_version,
            semantic_id="dependency.reverse",
            text_ar="الإجراء الأصلي مطلوب",
            text_en="Original procedure required",
            target_procedure=self.procedure,
            satisfied_when={"op": "eq", "fact": self.satisfied.key, "value": True},
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        reverse_evidence = EvidenceLink.objects.create(
            procedure_dependency=reverse,
            passage="Reverse passage",
            location="Section 2",
            applicability_context="Target applicant",
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
            verification_state="current",
        )
        set_evidence_link_sources(reverse_evidence, (self.source,))
        publish_procedure_version(target_version.pk, actor=self.actor)

        dependency = self.dependency()
        self.evidence(dependency)
        self.assertIn(
            ("blocking_cycle", self.version.semantic_id),
            {(item.code, item.detail) for item in self.rejection().diagnostics},
        )

    def test_published_snapshot_contains_detached_dependency_and_target_identity(self) -> None:
        self.add_question(self.applies, suffix="applies", priority=1)
        self.add_question(self.satisfied, suffix="satisfied", priority=2)
        dependency = self.dependency()
        self.evidence(dependency)
        publish_procedure_version(self.version.pk, actor=self.actor)

        snapshot = load_knowledge_snapshot()
        version = next(
            item
            for item in snapshot.procedure_versions
            if item.semantic_id == self.version.semantic_id
        )
        self.assertEqual(len(version.dependencies), 1)
        detached = version.dependencies[0]
        self.assertEqual(detached.semantic_id, dependency.semantic_id)
        self.assertEqual(detached.target_procedure_id, self.target.semantic_id)
        self.assertEqual(detached.target_procedure_text.en, "Prerequisite procedure")
        self.assertIsNotNone(detached.satisfied_when)
        self.assertEqual(detached.evidence_links[0].sources[0].semantic_id, self.source.semantic_id)

    def test_published_dependency_and_evidence_are_database_immutable(self) -> None:
        self.add_question(self.applies, suffix="applies", priority=1)
        self.add_question(self.satisfied, suffix="satisfied", priority=2)
        dependency = self.dependency()
        evidence = self.evidence(dependency)
        publish_procedure_version(self.version.pk, actor=self.actor)

        for model, primary_key, values in (
            (ProcedureDependency, dependency.pk, {"text_en": "Changed"}),
            (EvidenceLink, evidence.pk, {"passage": "Changed"}),
            (Source, self.source.pk, {"title": "Changed"}),
            (Authority, self.authority.pk, {"name_en": "Changed"}),
        ):
            with self.subTest(model=model.__name__), self.assertRaises(DatabaseError):
                with transaction.atomic():
                    model.objects.filter(pk=primary_key).update(**values)


__all__ = ("ProcedureDependencyKnowledgeTests",)
