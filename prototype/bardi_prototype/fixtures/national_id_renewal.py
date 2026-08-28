from __future__ import annotations

from datetime import date

from ..contracts import (
    ClaimDefinition,
    EvidenceLink,
    FeeDefinition,
    GoalDefinition,
    KnowledgeBundle,
    LocalizedText,
    ProcedureVersionDefinition,
    Source,
    StepDefinition,
    UnknownDefinition,
    WarningDefinition,
)
from ..evaluator import all_of, eq

VERIFIED_ON = date(2026, 8, 26)


def t(ar: str, en: str) -> LocalizedText:
    return LocalizedText(ar=ar, en=en)


def load_national_id_renewal_fixture() -> KnowledgeBundle:
    sources = {
        "SRC-CIVIL-LAW-143-GAZETTE": Source("SRC-CIVIL-LAW-143-GAZETTE", "Egyptian Official Gazette", "Civil Status Law No. 143 of 1994", VERIFIED_ON),
        "SRC-PSM-CIVIL-STATUS-SERVICES": Source("SRC-PSM-CIVIL-STATUS-SERVICES", "Egyptian Public Services Guide", "Civil Status services directory", VERIFIED_ON),
    }
    evidence_links = {
        "EL-CIVIL-LAW-52": EvidenceLink("EL-CIVIL-LAW-52", ("SRC-CIVIL-LAW-143-GAZETTE",)),
        "EL-PSM-NID-SERVICE": EvidenceLink("EL-PSM-NID-SERVICE", ("SRC-PSM-CIVIL-STATUS-SERVICES",)),
    }
    goal = GoalDefinition("get_egyptian_national_id", t("الحصول على بطاقة رقم قومي مصرية", "Get an Egyptian National ID"), ("ordinary_domestic_national_id_renewal",))
    procedure = ProcedureVersionDefinition(
        "ordinary_domestic_national_id_renewal",
        "ordinary_domestic_national_id_renewal.research-2026-08-26",
        t("تجديد بطاقة الرقم القومي المنتهية داخل مصر دون تغيير البيانات", "Renew an expired Egyptian National ID inside Egypt without changing its recorded data"),
        all_of(eq("application_location", "inside_egypt"), eq("national_id_possession_state", "held"), eq("national_id_data_change_kind", "none"), eq("card_expired_before_evaluation_date", True)),
        VERIFIED_ON,
    )
    claims = (
        ClaimDefinition("nid.requirement.renew_after_expiry", t("يجب التقدم لتجديد البطاقة خلال ثلاثة أشهر من انتهاء مدة سريانها", "Apply to renew within three months from expiry"), "official_requirement", None, ("EL-CIVIL-LAW-52",), "current", 10),
        ClaimDefinition("nid.requirement.previous_card", t("البطاقة الحالية/القديمة", "Current/previous card"), "official_requirement_candidate", None, (), "needs_reverification", 20, document_type_id="national_id"),
    )
    steps = (
        StepDefinition("nid.step.apply_for_renewal", t("التقدم بطلب تجديد البطاقة خلال المدة القانونية بعد انتهاء سريانها", "Apply for renewal within the legal period after expiry"), "submit", 10, None, ("EL-CIVIL-LAW-52",), "current", phase_order=10),
        StepDefinition("nid.step.resolve_service_location", t("تحديد جهة الخدمة وفق المحافظة والمنطقة", "Resolve the service location from governorate/district or another currently evidenced channel"), "route", 20, None, ("EL-PSM-NID-SERVICE",), "current", phase_order=20),
    )
    fees = (
        FeeDefinition(
            id="nid.fee.ordinary",
            text=t("رسم التجديد العادي", "Ordinary renewal fee"),
            amount=None,
            currency="EGP",
            applicability=None,
            evidence_link_ids=(),
            verification_state="unknown",
            value_state="unknown",
            fee_type="base",
        ),
    )
    warnings = (
        WarningDefinition("nid.warning.deadline", t("يجب تقديم طلب التجديد خلال ثلاثة أشهر من تاريخ انتهاء البطاقة.", "Apply for renewal within three months from the card's expiry date."), "important", ("EL-CIVIL-LAW-52",), kind="administrative"),
        WarningDefinition("nid.warning.recheck", t("أعد التحقق قبل التوجه لأن الرسوم ومنافذ الخدمة والتعليمات قد تتغير.", "Re-check the plan before acting because fees, service channels and operational instructions can change."), "important", kind="product", role="regeneration"),
    )
    unknowns = (
        UnknownDefinition("nid.turnaround.ordinary", t("مدة إنجاز التجديد العادي غير مثبتة حاليًا.", "The ordinary renewal turnaround is not currently established.")),
        UnknownDefinition("nid.routing.exact_service_point", t("نقطة الخدمة الدقيقة قد تحتاج إلى تحقق محلي إضافي.", "The exact service point may require additional local verification.")),
    )
    return KnowledgeBundle("national-id-renewal.research-2026-08-26", goal, procedure, sources, evidence_links, claims, steps, fees, (), warnings, unknowns)
