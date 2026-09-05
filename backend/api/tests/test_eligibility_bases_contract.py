from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from knowledge.models import (
    Authority,
    ChecklistItem,
    EligibilityBasis,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.publication import publish_procedure_version
from knowledge.services import set_evidence_link_sources


class EligibilityBasisApiContractTests(TransactionTestCase):
    def setUp(self) -> None:
        self.entry = FactDefinition.objects.create(
            key="basis_api_entry",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.gate = FactDefinition.objects.create(
            key="basis_api_gate",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.qualification = FactDefinition.objects.create(
            key="basis_api_qualification",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.service = Service.objects.create(
            semantic_id="basis.api.service",
            text_ar="خدمة",
            text_en="Service",
            is_active=True,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="basis.api.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate={"op": "eq", "fact": self.entry.key, "value": True},
        )
        for priority, fact, semantic_id, text_ar, text_en in (
            (1, self.entry, "basis.api.question.entry", "هل تبدأ؟", "Start?"),
            (2, self.gate, "basis.api.question.gate", "هل المسار متاح؟", "Is the route reachable?"),
            (
                3,
                self.qualification,
                "basis.api.question.qualification",
                "هل تستوفي الشرط؟",
                "Do you qualify?",
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
        self.version = ProcedureVersion.objects.create(
            semantic_id="basis.api.version",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability={"op": "eq", "fact": self.entry.key, "value": True},
        )
        Warning.objects.create(
            procedure_version=self.version,
            semantic_id="basis.api.regenerate",
            text_ar="أعد إنشاء الخطة قبل التنفيذ",
            text_en="Regenerate the plan before acting",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            display_order=100,
            verification_state="current",
        )
        self.authority = Authority.objects.create(
            semantic_id="basis.api.authority",
            name_ar="جهة",
            name_en="Authority",
        )
        self.source = Source.objects.create(
            semantic_id="basis.api.source",
            authority=self.authority,
            title="Official eligibility guidance",
            locator="https://example.test/eligibility",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )
        self.actor = get_user_model().objects.create_user(username="basis-api-publisher")

    def post(self, facts: dict[str, object], *, locale: str = "en") -> Any:
        payload = {
            "service_id": self.service.semantic_id,
            "facts": facts,
            "locale": locale,
            "evaluation_context": {"evaluation_date": "2026-09-01"},
        }
        return self.client.post(
            "/v1/planning",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def basis(
        self,
        semantic_id: str,
        *,
        display_order: int,
        verification_state: str = "current",
        text_ar: str | None = None,
        text_en: str | None = None,
    ) -> EligibilityBasis:
        basis = EligibilityBasis.objects.create(
            procedure_version=self.version,
            semantic_id=semantic_id,
            text_ar=text_ar or f"{semantic_id} عربي",
            text_en=text_en or semantic_id,
            reachability={"op": "eq", "fact": self.gate.key, "value": True},
            qualification={
                "op": "eq",
                "fact": self.qualification.key,
                "value": True,
            },
            display_order=display_order,
            verification_state=verification_state,
            verified_on=date(2026, 8, 1),
        )
        self.evidence(eligibility_basis=basis)
        return basis

    def evidence(self, **owner: object) -> EvidenceLink:
        values: dict[str, object] = {
            **owner,
            "passage": "PRIVATE BASIS PASSAGE",
            "location": "PRIVATE BASIS LOCATION",
            "applicability_context": "PRIVATE BASIS CONTEXT",
            "support_status": EvidenceLink.SupportStatus.SUPPORTS,
            "verification_state": "current",
            "verified_on": date(2026, 8, 1),
        }
        link = EvidenceLink.objects.create(**values)
        set_evidence_link_sources(link, (self.source,))
        return link

    def publish(self) -> None:
        publish_procedure_version(self.version.pk, actor=self.actor)

    def test_api_covers_every_reachability_and_qualification_stage_transition(self) -> None:
        second = self.basis(
            "basis.second-authored",
            display_order=20,
            text_ar="المسار الثاني",
            text_en="Second route",
        )
        first = self.basis(
            "basis.first-authored",
            display_order=10,
            text_ar="المسار الأول",
            text_en="First route",
        )
        self.publish()

        reachability_unknown = self.post({self.entry.key: True})
        self.assertEqual(reachability_unknown.status_code, 200)
        self.assertEqual(reachability_unknown.json()["type"], "next_question")
        self.assertEqual(
            reachability_unknown.json()["question"]["id"],
            "basis.api.question.gate",
        )
        self.assertEqual(
            [answer["key"] for answer in reachability_unknown.json()["question"]["answers"]],
            [self.gate.key],
        )

        reachability_false = self.post({self.entry.key: True, self.gate.key: False})
        self.assertEqual(reachability_false.status_code, 200)
        self.assertEqual(reachability_false.json()["type"], "inconclusive")
        self.assertEqual(
            reachability_false.json()["reason"],
            "no_applicable_eligibility_basis",
        )

        qualification_unknown = self.post({self.entry.key: True, self.gate.key: True})
        self.assertEqual(qualification_unknown.status_code, 200)
        self.assertEqual(qualification_unknown.json()["type"], "next_question")
        self.assertEqual(
            qualification_unknown.json()["question"]["id"],
            "basis.api.question.qualification",
        )
        self.assertEqual(
            [answer["key"] for answer in qualification_unknown.json()["question"]["answers"]],
            [self.qualification.key],
        )

        qualification_false = self.post(
            {
                self.entry.key: True,
                self.gate.key: True,
                self.qualification.key: False,
            }
        )
        self.assertEqual(qualification_false.status_code, 200)
        self.assertEqual(qualification_false.json()["type"], "inconclusive")
        self.assertEqual(
            qualification_false.json()["reason"],
            "no_applicable_eligibility_basis",
        )

        qualification_true = self.post(
            {
                self.entry.key: True,
                self.gate.key: True,
                self.qualification.key: True,
            }
        )
        self.assertEqual(qualification_true.status_code, 200)
        body = qualification_true.json()
        self.assertEqual(body["type"], "plan")
        self.assertEqual(
            [item["id"] for item in body["eligibility_bases"]],
            [first.semantic_id, second.semantic_id],
        )
        self.assertEqual(body["inconclusive_basis_ids"], [])
        self.assertEqual(
            set(body["eligibility_bases"][0]),
            {"id", "text", "checklist_item_ids", "step_ids", "sources", "freshness"},
        )
        rendered = qualification_true.content.decode()
        for private in (
            "PRIVATE BASIS PASSAGE",
            "PRIVATE BASIS LOCATION",
            "PRIVATE BASIS CONTEXT",
            "reachability",
            "qualification",
            "recommended",
            "closest",
            "score",
        ):
            self.assertNotIn(private, rendered)

        arabic = self.post(
            {
                self.entry.key: True,
                self.gate.key: True,
                self.qualification.key: True,
            },
            locale="ar",
        ).json()
        self.assertEqual(
            [item["text"] for item in arabic["eligibility_bases"]],
            ["المسار الأول", "المسار الثاني"],
        )
        for index in range(2):
            for key in ("id", "checklist_item_ids", "step_ids", "sources", "freshness"):
                self.assertEqual(
                    arabic["eligibility_bases"][index][key],
                    body["eligibility_bases"][index][key],
                )

    def test_untrusted_matched_basis_is_visible_but_cannot_unlock_scoped_guidance(self) -> None:
        trusted = self.basis(
            "basis.trusted",
            display_order=10,
            text_ar="مسار موثوق",
            text_en="Trusted route",
        )
        untrusted = self.basis(
            "basis.untrusted",
            display_order=20,
            verification_state="needs_reverification",
            text_ar="مسار يحتاج تحقق",
            text_en="Needs reverification route",
        )
        for index, basis in enumerate((trusted, untrusted), start=1):
            checklist = ChecklistItem.objects.create(
                procedure_version=self.version,
                semantic_id=f"{basis.semantic_id}.document",
                text_ar="مستند",
                text_en=f"{basis.semantic_id} document",
                classification=ChecklistItem.Classification.PRACTICAL_PREPARATION,
                quantity=1,
                original_quantity=1,
                copy_quantity=0,
                display_order=index,
                scope=ChecklistItem.Scope.ELIGIBILITY_BASIS,
                scope_reference=basis.semantic_id,
                verification_state="current",
                verified_on=date(2026, 8, 1),
            )
            self.evidence(checklist_item=checklist)
            step = Step.objects.create(
                procedure_version=self.version,
                semantic_id=f"{basis.semantic_id}.step",
                text_ar="خطوة",
                text_en=f"{basis.semantic_id} step",
                phase="submit",
                phase_order=index,
                slot=index,
                scope=Step.Scope.ELIGIBILITY_BASIS,
                eligibility_basis=basis,
                verification_state="current",
                verified_on=date(2026, 8, 1),
            )
            self.evidence(step=step)
        self.publish()

        response = self.post(
            {
                self.entry.key: True,
                self.gate.key: True,
                self.qualification.key: True,
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["type"], "plan")
        self.assertEqual(
            [item["id"] for item in body["eligibility_bases"]],
            [trusted.semantic_id, untrusted.semantic_id],
        )
        self.assertEqual(body["inconclusive_basis_ids"], [untrusted.semantic_id])
        self.assertEqual(
            [item["id"] for item in body["checklist_items"]],
            [f"{trusted.semantic_id}.document"],
        )
        self.assertEqual(
            [item["id"] for item in body["steps"]],
            [f"{trusted.semantic_id}.step"],
        )
        by_id = {item["id"]: item for item in body["eligibility_bases"]}
        self.assertEqual(
            by_id[trusted.semantic_id]["checklist_item_ids"],
            [f"{trusted.semantic_id}.document"],
        )
        self.assertEqual(
            by_id[trusted.semantic_id]["step_ids"],
            [f"{trusted.semantic_id}.step"],
        )
        self.assertEqual(by_id[untrusted.semantic_id]["checklist_item_ids"], [])
        self.assertEqual(by_id[untrusted.semantic_id]["step_ids"], [])
