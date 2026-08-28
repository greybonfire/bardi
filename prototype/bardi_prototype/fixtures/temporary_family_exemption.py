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
        "SRC-LAW127-1980-GAZETTE": Source("SRC-LAW127-1980-GAZETTE", "Egyptian Official Gazette", "Military and National Service Law No. 127 of 1980", VERIFIED_ON),
        "SRC-MOD-RECRUITMENT-OCT-2026": Source("SRC-MOD-RECRUITMENT-OCT-2026", "Egyptian Ministry of Defense", "Recruitment operational announcement", VERIFIED_ON),
        "SRC-TAGNED-REGIONS": Source("SRC-TAGNED-REGIONS", "Recruitment and Mobilization Administration", "Recruitment regions directory", VERIFIED_ON),
        "SRC-TAGNED-CERTIFICATE-SERVICE": Source("SRC-TAGNED-CERTIFICATE-SERVICE", "Recruitment and Mobilization Administration", "Exemption certificate service", VERIFIED_ON),
    }
    evidence_links = {
        "EL-LAW127-ART7-II-A": EvidenceLink("EL-LAW127-ART7-II-A", ("SRC-LAW127-1980-GAZETTE",)),
        "EL-MOD-SUPPORTING-DOCS": EvidenceLink("EL-MOD-SUPPORTING-DOCS", ("SRC-MOD-RECRUITMENT-OCT-2026",)),
        "EL-TAGNED-REGIONS": EvidenceLink("EL-TAGNED-REGIONS", ("SRC-TAGNED-REGIONS",)),
        "EL-TAGNED-CERT-REVIEW": EvidenceLink("EL-TAGNED-CERT-REVIEW", ("SRC-TAGNED-CERTIFICATE-SERVICE",)),
    }
    goal = GoalDefinition("handle_military_service_paperwork", t("إجراءات التجنيد والخدمة العسكرية", "Handle military-service paperwork"), ("temporary_family_exemption_from_military_service",))
    reachable_family_ground = any_of(
        all_of(eq("father_alive", True), eq("other_living_sons_of_father_count", 0)),
        eq("father_unable_to_earn_status", "authority_documented_unable"),
        one_of("mother_family_status", ("widowed", "irrevocably_divorced", "husband_authority_documented_unable")),
        gt("unmarried_sisters_requiring_support_count", 0),
        one_of("sibling_service_status", ("compulsory_service", "reserve_recall")),
    )
    procedure = ProcedureVersionDefinition(
        "temporary_family_exemption_from_military_service",
        "temporary_family_exemption_from_military_service.research-2026-08-26",
        t("طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية", "Apply for temporary exemption from military service on a family ground"),
        all_of(eq("application_location", "inside_egypt"), reachable_family_ground),
        VERIFIED_ON,
    )
    claims = (
        ClaimDefinition("mil.shared.supporting_documents", t("تقديم المستندات المؤيدة لأحقية الطلب", "Present documents supporting the claimed entitlement"), "official_requirement", None, ("EL-MOD-SUPPORTING-DOCS",), "current", 10, document_type_id="military_supporting_documents", scope="shared"),
        ClaimDefinition("mil.basis.only_son_living_father", t("الابن الوحيد لأبيه الحي", "Only son of a living father — candidate statutory ground"), "legal_basis_candidate", all_of(eq("father_alive", True), eq("other_living_sons_of_father_count", 0)), ("EL-LAW127-ART7-II-A",), "needs_reverification", 20, scope="eligibility_basis", eligibility_basis_id="family.only_son_living_father"),
    )
    steps = (
        StepDefinition("mil.step.submit_supporting_documents", t("تقديم المستندات المؤيدة للحالة إلى جهة التجنيد المختصة", "Submit supporting documents for the claimed status to the competent recruitment authority"), "submit", 10, None, ("EL-MOD-SUPPORTING-DOCS",), "current", phase_order=10),
        StepDefinition("mil.step.authority_review", t("تخضع الحالة للدراسة بواسطة المختصين لتحديد الاستحقاق", "The case is reviewed by authority specialists to determine entitlement"), "adjudicate", 20, None, ("EL-TAGNED-CERT-REVIEW",), "current", phase_order=20),
    )
    fees = (
        FeeDefinition(
            id="mil.fee.current",
            text=t("رسم شهادة الإعفاء", "Exemption-certificate fee"),
            amount=None,
            currency="EGP",
            applicability=None,
            evidence_link_ids=(),
            verification_state="unknown",
            value_state="unknown",
            fee_type="certificate",
        ),
    )
    service_points = (
        ServicePointDefinition("sp.recruitment_region_giza", t("منطقة تجنيد وتعبئة الجيزة", "Giza Recruitment and Mobilization Region"), t("الهرم، الجيزة", "Haram, Giza"), eq("residence_governorate", "giza"), ("EL-TAGNED-REGIONS",), "current"),
    )
    warnings = (
        WarningDefinition("mil.warning.candidate_not_decision", t("مطابقة ظروفك لمسار بحثي لا تعني صدور قرار إعفاء؛ يلزم تأكيد الجهة المختصة والمراجعة المتخصصة.", "Matching a researched route is not an exemption decision; specialist and authority confirmation are required."), "important", kind="product", role="limitation"),
        WarningDefinition("mil.warning.recheck", t("أعد التحقق من التعليمات قبل التوجه.", "Re-check current instructions before acting."), "important", kind="product", role="regeneration"),
    )
    unknowns = (
        UnknownDefinition("mil.documents.basis_specific", t("القائمة الدقيقة للمستندات الخاصة بهذا الأساس لم تُثبت بعد.", "The exact basis-specific document list is not yet established.")),
    )
    return KnowledgeBundle("temporary-family-exemption.research-2026-08-26", goal, procedure, sources, evidence_links, claims, steps, fees, service_points, warnings, unknowns)
