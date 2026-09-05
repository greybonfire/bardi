from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from knowledge.models import (
    Authority,
    ChecklistItem,
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
from knowledge.publication import publish_procedure_version
from knowledge.services import set_evidence_link_sources


class ProcedureDependencyApiContractTests(TransactionTestCase):
    def setUp(self) -> None:
        self.entry = FactDefinition.objects.create(
            key="dependency_api_entry",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.applies = FactDefinition.objects.create(
            key="dependency_api_applies",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.satisfied = FactDefinition.objects.create(
            key="dependency_api_satisfied",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.service = Service.objects.create(
            semantic_id="dependency.api.service",
            text_ar="خدمة",
            text_en="Service",
            is_active=True,
        )
        self.target_service = Service.objects.create(
            semantic_id="dependency.api.target-service",
            text_ar="خدمة المتطلب",
            text_en="Prerequisite service",
        )
        self.procedure = Procedure.objects.create(
            semantic_id="dependency.api.procedure",
            text_ar="الإجراء الرئيسي",
            text_en="Main procedure",
            primary_service=self.service,
        )
        self.target = Procedure.objects.create(
            semantic_id="dependency.api.target",
            text_ar="إجراء سابق موثوق",
            text_en="Researched prerequisite",
            primary_service=self.target_service,
        )
        self.unresearched = Procedure.objects.create(
            semantic_id="dependency.api.unresearched",
            text_ar="إجراء سابق غير مدروس",
            text_en="Unresearched prerequisite",
            primary_service=self.target_service,
        )
        entry_rule = {"op": "eq", "fact": self.entry.key, "value": True}
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=entry_rule,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.target_service,
            procedure=self.target,
            selection_predicate=entry_rule,
        )
        for priority, fact, semantic_id, text_ar, text_en in (
            (1, self.entry, "dependency.api.question.entry", "هل تبدأ؟", "Start?"),
            (
                2,
                self.applies,
                "dependency.api.question.applies",
                "هل ينطبق المتطلب؟",
                "Does the prerequisite apply?",
            ),
            (
                3,
                self.satisfied,
                "dependency.api.question.satisfied",
                "هل اكتمل المتطلب؟",
                "Is the prerequisite complete?",
            ),
        ):
            ServiceQuestion.objects.create(
                semantic_id=semantic_id,
                service=self.service,
                fact=fact,
                text_ar=text_ar,
                text_en=text_en,
                priority=priority,
            )

        self.authority = Authority.objects.create(
            semantic_id="dependency.api.authority",
            name_ar="جهة",
            name_en="Authority",
        )
        self.source = Source.objects.create(
            semantic_id="dependency.api.source",
            authority=self.authority,
            title="Official prerequisite page",
            locator="https://example.test/prerequisite",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )
        self.actor = get_user_model().objects.create_user(username="dependency-api-publisher")

        target_version = ProcedureVersion.objects.create(
            semantic_id="dependency.api.target.version",
            procedure=self.target,
            text_ar="نسخة المتطلب",
            text_en="Prerequisite version",
            applicability=entry_rule,
        )
        target_item = ChecklistItem.objects.create(
            procedure_version=target_version,
            semantic_id="dependency.api.target.private-checklist",
            text_ar="إرشاد الهدف الخاص",
            text_en="TARGET PROCEDURE GUIDANCE MUST NOT RECURSE",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        self.evidence(checklist_item=target_item, passage="TARGET PRIVATE PASSAGE")
        publish_procedure_version(target_version.pk, actor=self.actor)
        self.target_version_id = target_version.semantic_id

        self.version = ProcedureVersion.objects.create(
            semantic_id="dependency.api.version",
            procedure=self.procedure,
            text_ar="نسخة رئيسية",
            text_en="Main version",
            applicability=entry_rule,
        )
        owner_item = ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="dependency.api.owner.checklist",
            text_ar="احتفظ بالمستند الرئيسي",
            text_en="Keep the main document",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            display_order=1,
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        self.evidence(checklist_item=owner_item, passage="OWNER CHECKLIST PASSAGE")

        self.dependency(
            "dependency.blocking",
            target=self.target,
            order=10,
            verification_state="current",
            text_ar="أكمل الإجراء السابق الموثوق",
            text_en="Complete the researched prerequisite",
        )
        self.dependency(
            "dependency.unsupported",
            target=self.unresearched,
            order=20,
            verification_state="current",
            text_ar="تحقق من الإجراء السابق غير المدروس",
            text_en="Verify the unresearched prerequisite",
        )
        self.dependency(
            "dependency.untrusted",
            target=self.target,
            order=30,
            verification_state="needs_reverification",
            text_ar="متطلب يحتاج إعادة تحقق",
            text_en="Prerequisite needing reverification",
        )
        publish_procedure_version(self.version.pk, actor=self.actor)

    def evidence(self, *, passage: str = "PRIVATE DEPENDENCY PASSAGE", **owner: object) -> None:
        link = EvidenceLink.objects.create(
            **owner,
            passage=passage,
            location="PRIVATE DEPENDENCY LOCATION",
            applicability_context="PRIVATE DEPENDENCY CONTEXT",
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        set_evidence_link_sources(link, (self.source,))

    def dependency(
        self,
        semantic_id: str,
        *,
        target: Procedure,
        order: int,
        verification_state: str,
        text_ar: str,
        text_en: str,
    ) -> None:
        dependency = ProcedureDependency.objects.create(
            procedure_version=self.version,
            semantic_id=semantic_id,
            text_ar=text_ar,
            text_en=text_en,
            target_procedure=target,
            relation=ProcedureDependency.Relation.BLOCKING_PREREQUISITE,
            applicability={"op": "eq", "fact": self.applies.key, "value": True},
            satisfied_when={
                "op": "eq",
                "fact": self.satisfied.key,
                "value": True,
            },
            display_order=order,
            verification_state=verification_state,
            verified_on=date(2026, 8, 1),
        )
        self.evidence(procedure_dependency=dependency)

    def post(self, facts: dict[str, object], *, locale: str = "en") -> Any:
        return self.client.post(
            "/v1/planning",
            data=json.dumps(
                {
                    "service_id": self.service.semantic_id,
                    "facts": facts,
                    "locale": locale,
                    "evaluation_context": {"evaluation_date": "2026-09-01"},
                }
            ),
            content_type="application/json",
        )

    def test_api_resolves_direct_prerequisites_without_recursive_planning(self) -> None:
        applicability = self.post({self.entry.key: True})
        self.assertEqual(applicability.status_code, 200)
        self.assertEqual(applicability.json()["type"], "next_question")
        self.assertEqual(
            applicability.json()["question"]["id"],
            "dependency.api.question.applies",
        )

        satisfaction = self.post({self.entry.key: True, self.applies.key: True})
        self.assertEqual(satisfaction.status_code, 200)
        self.assertEqual(satisfaction.json()["type"], "next_question")
        self.assertEqual(
            satisfaction.json()["question"]["id"],
            "dependency.api.question.satisfied",
        )

        response = self.post(
            {
                self.entry.key: True,
                self.applies.key: True,
                self.satisfied.key: False,
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["type"], "plan")
        self.assertEqual(
            [(item["id"], item["status"]) for item in body["dependencies"]],
            [
                ("dependency.blocking", "blocking"),
                ("dependency.unsupported", "unsupported_target"),
                ("dependency.untrusted", "inconclusive"),
            ],
        )
        by_id = {item["id"]: item for item in body["dependencies"]}
        self.assertEqual(
            by_id["dependency.blocking"]["target_procedure_version_id"],
            self.target_version_id,
        )
        self.assertIsNone(
            by_id["dependency.unsupported"]["target_procedure_version_id"]
        )
        self.assertIsNone(by_id["dependency.untrusted"]["target_procedure_version_id"])
        self.assertEqual(
            [item["id"] for item in body["checklist_items"]],
            ["dependency.api.owner.checklist"],
        )
        self.assertEqual(
            set(by_id["dependency.blocking"]),
            {
                "id",
                "text",
                "relation",
                "status",
                "target_procedure_id",
                "target_procedure",
                "target_procedure_version_id",
                "sources",
                "freshness",
            },
        )
        rendered = response.content.decode()
        for private in (
            "TARGET PROCEDURE GUIDANCE MUST NOT RECURSE",
            "TARGET PRIVATE PASSAGE",
            "PRIVATE DEPENDENCY PASSAGE",
            "PRIVATE DEPENDENCY LOCATION",
            "PRIVATE DEPENDENCY CONTEXT",
            "satisfied_when",
            "applicability",
            "evidence_links",
            "procedure_dependency",
        ):
            self.assertNotIn(private, rendered)

        arabic = self.post(
            {
                self.entry.key: True,
                self.applies.key: True,
                self.satisfied.key: False,
            },
            locale="ar",
        ).json()
        arabic_by_id = {item["id"]: item for item in arabic["dependencies"]}
        self.assertEqual(
            arabic_by_id["dependency.blocking"]["text"],
            "أكمل الإجراء السابق الموثوق",
        )
        self.assertEqual(
            arabic_by_id["dependency.blocking"]["target_procedure"],
            "إجراء سابق موثوق",
        )
        for dependency_id in by_id:
            for key in (
                "id",
                "relation",
                "status",
                "target_procedure_id",
                "target_procedure_version_id",
                "sources",
                "freshness",
            ):
                self.assertEqual(arabic_by_id[dependency_id][key], by_id[dependency_id][key])

    def test_satisfied_dependency_remains_metadata_and_untrusted_edge_stays_local(self) -> None:
        response = self.post(
            {
                self.entry.key: True,
                self.applies.key: True,
                self.satisfied.key: True,
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["type"], "plan")
        self.assertEqual(
            [item["status"] for item in body["dependencies"]],
            ["satisfied", "satisfied", "inconclusive"],
        )
        self.assertEqual(
            [item["id"] for item in body["checklist_items"]],
            ["dependency.api.owner.checklist"],
        )


__all__ = ("ProcedureDependencyApiContractTests",)
