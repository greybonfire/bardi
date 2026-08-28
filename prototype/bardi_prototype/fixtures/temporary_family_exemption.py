from __future__ import annotations

from datetime import date

from ..contracts import (
    ClaimDefinition,
    EvidenceLink,
    GoalDefinition,
    KnowledgeBundle,
    LocalizedText,
    ProcedureVersionDefinition,
    ServicePointDefinition,
    Source,
    StepDefinition,
    UnknownDefinition,
    WarningDefinition,
)
from ..evaluator import all_of, any_of, eq, gt, one_of

VERIFIED_ON = date(2026, 8, 26)


def t(ar: str, en: str) -> LocalizedText:
    return LocalizedText(ar=ar, en=en)


def load_temporary_family_exemption_fixture() -> KnowledgeBundle:
    sources = {
        "SRC-LAW127-1980-GAZETTE": Source(
            id="SRC-LAW127-1980-GAZETTE",
            authority="Egyptian Official Gazette",
            title="Military and National Service Law No. 127 of 1980",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-MOD-RECRUITMENT-OCT-2026": Source(
            id="SRC-MOD-RECRUITMENT-OCT-2026",
            authority="Egyptian Ministry of Defense",
            title="Recruitment operational announcement",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-TAGNED-REGIONS": Source(
            id="SRC-TAGNED-REGIONS",
            authority="Recruitment and Mobilization Administration",
            title="Recruitment regions directory",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-TAGNED-CERTIFICATE-SERVICE": Source(
            id="SRC-TAGNED-CERTIFICATE-SERVICE",
            authority="Recruitment and Mobilization Administration",
            title="Exemption certificate service",
            retrieved_on=VERIFIED_ON,
        ),
    }
    evidence_links = {
        "EL-LAW127-ART7-II-A": EvidenceLink(
            "EL-LAW127-ART7-II-A",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        "EL-MOD-SUPPORTING-DOCS": EvidenceLink(
            "EL-MOD-SUPPORTING-DOCS",
            ("SRC-MOD-RECRUITMENT-OCT-2026",),
        ),
        "EL-TAGNED-REGIONS": EvidenceLink(
            "EL-TAGNED-REGIONS",
            ("SRC-TAGNED-REGIONS",),
        ),
        "EL-TAGNED-CERT-REVIEW": EvidenceLink(
            "EL-TAGNED-CERT-REVIEW",
            ("SRC-TAGNED-CERTIFICATE-SERVICE",),
        ),
    }

    goal = GoalDefinition(
        id="handle_military_service_paperwork",
        text=t("إجراءات التجنيد والخدمة العسكرية", "Handle military-service paperwork"),
        procedure_ids=("temporary_family_exemption_from_military_service",),
    )
    reachable_family_ground = any_of(
        all_of(
            eq("father_alive", True),
            eq("other_living_sons_of_father_count", 0),
        ),
        eq("father_unable_to_earn_status", "authority_documented_unable"),
        one_of(
            "mother_family_status",
            ("widowed", "irrevocably_divorced", "husband_authority_documented_unable"),
        ),
        gt("unmarried_sisters_requiring_support_count", 0),
        one_of("sibling_service_status", ("compulsory_service", "reserve_recall")),
    )
    procedure = ProcedureVersionDefinition(
        procedure_id="temporary_family_exemption_from_military_service",
        version_id="temporary_family_exemption_from_military_service.research-2026-08-26",
        text=t(
            "طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية",
            "Apply for temporary exemption from military service on a family ground",
        ),
        applicability=all_of(
            eq("application_location", "inside_egypt"),
            reachable_family_ground,
        ),
        verified_on=VERIFIED_ON,
    )

    claims = (
        ClaimDefinition(
            id="mil.shared.supporting_documents",
            text=t(
                "تقديم المستندات المؤيدة لأحقية الطلب",
                "Present documents supporting the claimed entitlement",
            ),
            classification="official_requirement",
            applicability=None,
            evidence_link_ids=("EL-MOD-SUPPORTING-DOCS",),
            verification_state="current",
            display_order=10,
        ),
        ClaimDefinition(
            id="mil.basis.only_son_living_father",
            text=t(
                "الابن الوحيد لأبيه الحي",
                "Only son of a living father — candidate statutory ground",
            ),
            classification="legal_basis_candidate",
            applicability=all_of(
                eq("father_alive", True),
                eq("other_living_sons_of_father_count", 0),
            ),
            evidence_link_ids=("EL-LAW127-ART7-II-A",),
            verification_state="needs_reverification",
            display_order=20,
        ),
    )
    steps = (
        StepDefinition(
            id="mil.step.submit_supporting_documents",
            text=t(
                "تقديم المستندات المؤيدة للحالة إلى جهة التجنيد المختصة",
                "Submit supporting documents for the claimed status to the competent recruitment authority",
            ),
            phase="submit",
            slot=10,
            applicability=None,
            evidence_link_ids=("EL-MOD-SUPPORTING-DOCS",),
            verification_state="current",
        ),
        StepDefinition(
            id="mil.step.authority_review",
            text=t(
                "تخضع الحالة للدراسة بواسطة المختصين لتحديد الاستحقاق",
                "The case is reviewed by authority specialists to determine entitlement",
            ),
            phase="adjudicate",
            slot=20,
            applicability=None,
            evidence_link_ids=("EL-TAGNED-CERT-REVIEW",),
            verification_state="current",
        ),
    )
    service_points = (
        ServicePointDefinition(
            id="sp.recruitment_region_giza",
            text=t("منطقة تجنيد وتعبئة الجيزة", "Giza Recruitment and Mobilization Region"),
            address=t("الهرم، الجيزة", "Haram, Giza"),
            applicability=eq("residence_governorate", "giza"),
            evidence_link_ids=("EL-TAGNED-REGIONS",),
            verification_state="current",
        ),
    )
    warnings = (
        WarningDefinition(
            id="mil.warning.candidate_not_decision",
            text=t(
                "مطابقة ظروفك لمسار بحثي لا تعني صدور قرار إعفاء؛ يلزم تأكيد الجهة المختصة والمراجعة المتخصصة.",
                "Matching a researched route is not an exemption decision; specialist and authority confirmation are required.",
            ),
            severity="important",
        ),
        WarningDefinition(
            id="mil.warning.recheck",
            text=t(
                "أعد التحقق من التعليمات قبل التوجه.",
                "Re-check current instructions before acting.",
            ),
            severity="important",
        ),
    )
    unknowns = (
        UnknownDefinition(
            id="mil.documents.basis_specific",
            text=t(
                "القائمة الدقيقة للمستندات الخاصة بهذا الأساس لم تُثبت بعد.",
                "The exact basis-specific document list is not yet established.",
            ),
        ),
        UnknownDefinition(
            id="mil.fee.current",
            text=t(
                "قيمة رسم شهادة الإعفاء الحالية غير مثبتة في هذه الحزمة.",
                "The current exemption-certificate fee amount is not established by this fixture.",
            ),
        ),
    )

    return KnowledgeBundle(
        id="temporary-family-exemption.research-2026-08-26",
        goal=goal,
        procedure=procedure,
        sources=sources,
        evidence_links=evidence_links,
        claims=claims,
        steps=steps,
        fees=(),
        service_points=service_points,
        warnings=warnings,
        unknowns=unknowns,
    )
