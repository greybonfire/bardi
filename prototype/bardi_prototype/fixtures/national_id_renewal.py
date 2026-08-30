from __future__ import annotations

from dataclasses import replace
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
    VerificationPathDefinition,
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
            published_on=date(1994, 6, 9),
            effective_from=date(1994, 6, 10),
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
    evidence_metadata = {
        "EL-CIVIL-LAW-52": (
            "خلال ثلاثة أشهر من تاريخ انتهاء مدة سريانها",
            "Civil Status Law, Article 52; Official Gazette scan page 18",
            "National ID cardholder renewal; original Article 52 wording.",
        ),
        "EL-PSM-NID-SERVICE": (
            None,
            "Public Services Guide ordinary National ID service listing",
            "Current directory behavior; governorate/area input is exposed, but no nationwide office mapping is asserted.",
        ),
    }
    evidence_links = {
        key: replace(
            link,
            exact_passage=metadata[0],
            location=metadata[1],
            applicability_context=metadata[2],
            retrieved_on=VERIFIED_ON,
        )
        for key, link in evidence_links.items()
        for metadata in (evidence_metadata[key],)
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
        publication_state="published",
        published_on=VERIFIED_ON,
        trust_state="current",
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
            document_type_id="national_id",
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
            phase_order=10,
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
            phase_order=20,
        ),
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
        WarningDefinition(
            id="nid.warning.deadline",
            text=t(
                "يجب تقديم طلب التجديد خلال ثلاثة أشهر من تاريخ انتهاء البطاقة.",
                "Apply for renewal within three months from the card's expiry date.",
            ),
            severity="important",
            evidence_link_ids=("EL-CIVIL-LAW-52",),
            kind="administrative",
        ),
        WarningDefinition(
            id="nid.warning.recheck",
            text=t(
                "أعد التحقق قبل التوجه لأن الرسوم ومنافذ الخدمة والتعليمات قد تتغير.",
                "Re-check the plan before acting because fees, service channels and operational instructions can change.",
            ),
            severity="important",
            kind="product",
            role="regeneration",
        ),
    )

    unknowns = (
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
        fees=fees,
        service_points=(),
        warnings=warnings,
        unknowns=unknowns,
        routing_verification_path=VerificationPathDefinition(
            id="nid.routing.verify",
            text=t(
                "تحقق من منفذ الخدمة المختص من دليل خدمات الأحوال المدنية قبل التوجه.",
                "Verify the competent service location in the Civil Status services directory before acting.",
            ),
            evidence_link_ids=("EL-PSM-NID-SERVICE",),
        ),
    )
