from __future__ import annotations

from datetime import date

from ..contracts import (
    ClaimDefinition,
    EvidenceLink,
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
        "SRC-CIVIL-LAW-143-GAZETTE": Source(
            id="SRC-CIVIL-LAW-143-GAZETTE",
            authority="Egyptian Official Gazette",
            title="Civil Status Law No. 143 of 1994",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-PSM-CIVIL-STATUS-SERVICES": Source(
            id="SRC-PSM-CIVIL-STATUS-SERVICES",
            authority="Egyptian Public Services Guide",
            title="Civil Status services directory",
            retrieved_on=VERIFIED_ON,
        ),
    }
    evidence_links = {
        "EL-CIVIL-LAW-52": EvidenceLink(
            "EL-CIVIL-LAW-52",
            ("SRC-CIVIL-LAW-143-GAZETTE",),
        ),
        "EL-PSM-NID-SERVICE": EvidenceLink(
            "EL-PSM-NID-SERVICE",
            ("SRC-PSM-CIVIL-STATUS-SERVICES",),
        ),
    }

    goal = GoalDefinition(
        id="get_egyptian_national_id",
        text=t("الحصول على بطاقة رقم قومي مصرية", "Get an Egyptian National ID"),
        procedure_ids=("ordinary_domestic_national_id_renewal",),
    )
    procedure = ProcedureVersionDefinition(
        procedure_id="ordinary_domestic_national_id_renewal",
        version_id="ordinary_domestic_national_id_renewal.research-2026-08-26",
        text=t(
            "تجديد بطاقة الرقم القومي المنتهية داخل مصر دون تغيير البيانات",
            "Renew an expired Egyptian National ID inside Egypt without changing its recorded data",
        ),
        applicability=all_of(
            eq("application_location", "inside_egypt"),
            eq("national_id_possession_state", "held"),
            eq("national_id_data_change_kind", "none"),
            eq("card_expired_before_evaluation_date", True),
        ),
        verified_on=VERIFIED_ON,
    )

    claims = (
        ClaimDefinition(
            id="nid.requirement.renew_after_expiry",
            text=t(
                "يجب التقدم لتجديد البطاقة خلال ثلاثة أشهر من انتهاء مدة سريانها",
                "Apply to renew within three months from expiry",
            ),
            classification="official_requirement",
            applicability=None,
            evidence_link_ids=("EL-CIVIL-LAW-52",),
            verification_state="current",
            display_order=10,
        ),
        ClaimDefinition(
            id="nid.requirement.previous_card",
            text=t("البطاقة الحالية/القديمة", "Current/previous card"),
            classification="official_requirement_candidate",
            applicability=None,
            evidence_link_ids=(),
            verification_state="needs_reverification",
            display_order=20,
        ),
    )
    steps = (
        StepDefinition(
            id="nid.step.apply_for_renewal",
            text=t(
                "التقدم بطلب تجديد البطاقة خلال المدة القانونية بعد انتهاء سريانها",
                "Apply for renewal within the legal period after expiry",
            ),
            phase="submit",
            slot=10,
            applicability=None,
            evidence_link_ids=("EL-CIVIL-LAW-52",),
            verification_state="current",
        ),
        StepDefinition(
            id="nid.step.resolve_service_location",
            text=t(
                "تحديد جهة الخدمة وفق المحافظة والمنطقة",
                "Resolve the service location from governorate/district or another currently evidenced channel",
            ),
            phase="route",
            slot=20,
            applicability=None,
            evidence_link_ids=("EL-PSM-NID-SERVICE",),
            verification_state="current",
        ),
    )
    warnings = (
        WarningDefinition(
            id="nid.warning.deadline",
            text=t(
                "يجب تقديم طلب التجديد خلال ثلاثة أشهر من تاريخ انتهاء البطاقة.",
                "Apply for renewal within three months from the card's expiry date.",
            ),
            severity="important",
            evidence_link_ids=("EL-CIVIL-LAW-52",),
        ),
        WarningDefinition(
            id="nid.warning.recheck",
            text=t(
                "أعد التحقق قبل التوجه لأن الرسوم ومنافذ الخدمة والتعليمات قد تتغير.",
                "Re-check the plan before acting because fees, service channels and operational instructions can change.",
            ),
            severity="important",
        ),
    )
    unknowns = (
        UnknownDefinition(
            id="nid.fee.ordinary",
            text=t(
                "الرسم الحالي للتجديد العادي غير مثبت في هذه الحزمة.",
                "The current ordinary-renewal fee is not established by this research fixture.",
            ),
        ),
        UnknownDefinition(
            id="nid.turnaround.ordinary",
            text=t(
                "مدة إنجاز التجديد العادي غير مثبتة حاليًا.",
                "The ordinary renewal turnaround is not currently established.",
            ),
        ),
        UnknownDefinition(
            id="nid.routing.exact_service_point",
            text=t(
                "نقطة الخدمة الدقيقة قد تحتاج إلى تحقق محلي إضافي.",
                "The exact service point may require additional local verification.",
            ),
        ),
    )

    return KnowledgeBundle(
        id="national-id-renewal.research-2026-08-26",
        goal=goal,
        procedure=procedure,
        sources=sources,
        evidence_links=evidence_links,
        claims=claims,
        steps=steps,
        fees=(),
        service_points=(),
        warnings=warnings,
        unknowns=unknowns,
    )
