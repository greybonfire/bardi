from __future__ import annotations

import json
from datetime import date
from typing import Any, Protocol

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from knowledge.fees import Fee
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
    Warning,
)
from knowledge.publication import publish_procedure_version
from knowledge.services import set_evidence_link_sources


class _TestClientResponse(Protocol):
    status_code: int
    content: bytes

    def json(self) -> Any: ...


class FeePlanningContractTests(TransactionTestCase):
    def setUp(self) -> None:
        self.fact, _ = FactDefinition.objects.get_or_create(
            key="fee_contract_applicable",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        self.service = Service.objects.create(
            semantic_id="fee.contract.service",
            text_ar="خدمة الرسوم",
            text_en="Fee service",
            is_active=True,
        )
        ServiceQuestion.objects.create(
            semantic_id="fee.contract.service.question.applicability",
            service=self.service,
            fact=self.fact,
            text_ar="هل ينطبق عليك شرط الخدمة؟",
            text_en="Does the service condition apply to you?",
            priority=100,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="fee.contract.procedure",
            text_ar="إجراء الرسوم",
            text_en="Fee procedure",
            primary_service=self.service,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate={"op": "eq", "fact": self.fact.key, "value": True},
        )

    def _post(self, *, locale: str = "en") -> _TestClientResponse:
        return self.client.post(
            "/v1/planning",
            data=json.dumps(
                {
                    "service_id": self.service.semantic_id,
                    "facts": {self.fact.key: True},
                    "locale": locale,
                    "evaluation_context": {"evaluation_date": "2026-09-01"},
                }
            ),
            content_type="application/json",
        )

    def test_every_fee_value_state_is_safe_bilingual_and_compact(self) -> None:
        actor = get_user_model().objects.create_user(username="fee-contract-publisher")
        version = ProcedureVersion.objects.create(
            semantic_id="fee.contract.version",
            procedure=self.procedure,
            text_ar="نسخة الرسوم",
            text_en="Fee version",
            applicability={"op": "eq", "fact": self.fact.key, "value": True},
        )
        Warning.objects.create(
            procedure_version=version,
            semantic_id="fee.contract.regenerate",
            text_ar="أعد إنشاء الخطة قبل التنفيذ",
            text_en="Regenerate the plan before acting",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            display_order=100,
            verification_state="current",
        )
        authority = Authority.objects.create(
            semantic_id="fee.contract.authority",
            name_ar="جهة الرسوم",
            name_en="Fee authority",
        )
        source = Source.objects.create(
            semantic_id="fee.contract.source",
            authority=authority,
            title="Official fee schedule",
            locator="https://example.test/fees",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )
        fees = (
            Fee.objects.create(
                procedure_version=version,
                semantic_id="fee.known",
                text_ar="رسم معلوم",
                text_en="Known fee",
                value_state=Fee.ValueState.KNOWN,
                amount=705,
                currency="EGP",
                display_order=10,
                verification_state="current",
                verified_on=date(2026, 8, 1),
            ),
            Fee.objects.create(
                procedure_version=version,
                semantic_id="fee.range",
                text_ar="نطاق رسوم",
                text_en="Fee range",
                value_state=Fee.ValueState.RANGE,
                minimum_amount=100,
                maximum_amount=150,
                currency="EGP",
                display_order=20,
                verification_state="current",
                verified_on=date(2026, 8, 1),
            ),
            Fee.objects.create(
                procedure_version=version,
                semantic_id="fee.unknown",
                text_ar="الرسم الحالي غير معلوم",
                text_en="Current fee unknown",
                value_state=Fee.ValueState.UNKNOWN,
                currency="EGP",
                display_order=30,
                verification_state="current",
                verified_on=date(2026, 8, 1),
            ),
            Fee.objects.create(
                procedure_version=version,
                semantic_id="fee.unverified",
                text_ar="قيمة تحتاج للتحقق",
                text_en="Value needs verification",
                value_state=Fee.ValueState.UNVERIFIED,
                amount=999,
                currency="EGP",
                display_order=40,
                verification_state="disputed",
                verified_on=date(2026, 7, 1),
            ),
        )
        for fee in (fees[0], fees[1], fees[3]):
            link = EvidenceLink.objects.create(
                fee=fee,
                passage=f"PRIVATE FEE PASSAGE {fee.semantic_id}",
                location="PRIVATE FEE LOCATION",
                applicability_context="PRIVATE FEE CONTEXT",
                verification_state="current",
                support_status=EvidenceLink.SupportStatus.SUPPORTS,
            )
            set_evidence_link_sources(link, (source,))

        publish_procedure_version(version.pk, actor=actor)
        response = self._post()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["type"], "plan")
        self.assertEqual(
            [item["id"] for item in body["fees"]],
            [
                "fee.known",
                "fee.range",
                "fee.unknown",
                "fee.unverified",
            ],
        )
        known, range_fee, unknown, unverified = body["fees"]
        self.assertEqual((known["value_state"], known["amount"]), ("known", 705))
        self.assertFalse(known["current_value_unknown"])
        self.assertEqual(
            (range_fee["value_state"], range_fee["minimum_amount"], range_fee["maximum_amount"]),
            ("range", 100, 150),
        )
        self.assertEqual(unknown["value_state"], "unknown")
        self.assertIsNone(unknown["amount"])
        self.assertIsNone(unknown["minimum_amount"])
        self.assertIsNone(unknown["maximum_amount"])
        self.assertTrue(unknown["current_value_unknown"])
        self.assertEqual(unverified["value_state"], "unverified")
        self.assertIsNone(unverified["amount"])
        self.assertIsNone(unverified["minimum_amount"])
        self.assertIsNone(unverified["maximum_amount"])
        self.assertTrue(unverified["current_value_unknown"])
        self.assertEqual(unverified["freshness"]["state"], "disputed")
        self.assertEqual(unverified["sources"][0]["id"], source.semantic_id)

        rendered = response.content.decode()
        for private in (
            "999",
            "PRIVATE FEE PASSAGE",
            "PRIVATE FEE LOCATION",
            "PRIVATE FEE CONTEXT",
            "evidence_links",
            "support_status",
            "display_order",
            "eligibility_basis",
            "applicability",
        ):
            self.assertNotIn(private, rendered)

        arabic = self._post(locale="ar").json()
        self.assertEqual(arabic["fees"][0]["text"], "رسم معلوم")
        self.assertEqual(arabic["fees"][2]["text"], "الرسم الحالي غير معلوم")
        for index in range(4):
            for invariant in (
                "id",
                "value_state",
                "amount",
                "minimum_amount",
                "maximum_amount",
                "currency",
                "fee_type",
                "current_value_unknown",
                "sources",
                "freshness",
            ):
                self.assertEqual(arabic["fees"][index][invariant], body["fees"][index][invariant])
