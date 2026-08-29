from __future__ import annotations

from datetime import date

from ..contracts import (
    ClaimDefinition,
    EligibilityBasisDefinition,
    EvidenceLink,
    FeeDefinition,
    GoalDefinition,
    KnowledgeBundle,
    LocalizedText,
    ProcedureServicePointAssociationDefinition,
    ProcedureVersionDefinition,
    ServicePointDefinition,
    ServicePointVersionDefinition,
    Source,
    StepDefinition,
    UnknownDefinition,
    VerificationPathDefinition,
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
        "SRC-LAW2-2026-GAZETTE-METADATA": Source(
            id="SRC-LAW2-2026-GAZETTE-METADATA",
            authority="Egyptian State Information Service — Official Gazette repository",
            title="Law No. 2 of 2026 — Official Gazette metadata",
            retrieved_on=VERIFIED_ON,
        ),
        "SRC-LAW2-2026-TEXT": Source(
            id="SRC-LAW2-2026-TEXT",
            authority="MKS Egypt legal-text mirror",
            title="Law No. 2 of 2026 amending Military and National Service Law",
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
        "EL-LAW127-ART7-II-B": EvidenceLink(
            "EL-LAW127-ART7-II-B",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        "EL-LAW127-ART7-II-C": EvidenceLink(
            "EL-LAW127-ART7-II-C",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        "EL-LAW127-ART7-II-D": EvidenceLink(
            "EL-LAW127-ART7-II-D",
            ("SRC-LAW127-1980-GAZETTE",),
        ),
        "EL-LAW2-2026-ART7-II-E": EvidenceLink(
            "EL-LAW2-2026-ART7-II-E",
            ("SRC-LAW2-2026-GAZETTE-METADATA", "SRC-LAW2-2026-TEXT"),
        ),
        "EL-LAW127-ART7-III": EvidenceLink(
            "EL-LAW127-ART7-III",
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
    procedure = ProcedureVersionDefinition(
        procedure_id="temporary_family_exemption_from_military_service",
        version_id="temporary_family_exemption_from_military_service.research-2026-08-26",
        text=t(
            "طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية",
            "Apply for temporary exemption from military service on a family ground",
        ),
        applicability=eq("application_location", "inside_egypt"),
        verified_on=VERIFIED_ON,
    )

    eligibility_bases = (
        EligibilityBasisDefinition(
            id="family.only_son_living_father",
            text=t("الابن الوحيد لأبيه الحي", "Only son of a living father"),
            applicability=all_of(
                eq("father_alive", True),
                eq("other_living_sons_of_father_count", 0),
            ),
            evidence_link_ids=("EL-LAW127-ART7-II-A",),
            verification_state="needs_reverification",
            display_order=10,
        ),
        EligibilityBasisDefinition(
            id="family.support_father_or_incapable_brothers",
            text=t(
                "أساس إعالة الأب غير القادر على الكسب أو الصياغة المرتبطة بالإخوة غير القادرين",
                "Father/incapable-brother family-support ground",
            ),
            applicability=eq(
                "father_unable_to_earn_status",
                "authority_documented_unable",
            ),
            evidence_link_ids=("EL-LAW127-ART7-II-B",),
            verification_state="needs_reverification",
            display_order=20,
        ),
        EligibilityBasisDefinition(
            id="family.support_mother",
            text=t("أساس إعالة الأم", "Mother family-support ground"),
            applicability=one_of(
                "mother_family_status",
                (
                    "widowed",
                    "irrevocably_divorced",
                    "husband_authority_documented_unable",
                ),
            ),
            evidence_link_ids=("EL-LAW127-ART7-II-C",),
            verification_state="needs_reverification",
            display_order=30,
        ),
        EligibilityBasisDefinition(
            id="family.support_unmarried_sisters",
            text=t(
                "أساس إعالة الأخت أو الأخوات غير المتزوجات",
                "Unmarried-sister family-support ground",
            ),
            applicability=gt("unmarried_sisters_requiring_support_count", 0),
            evidence_link_ids=("EL-LAW127-ART7-II-D",),
            verification_state="needs_reverification",
            display_order=40,
        ),
        EligibilityBasisDefinition(
            id="family.missing_war_or_terror_relative",
            text=t(
                "أساس قريب مفقود بسبب العمليات الحربية أو الإرهابية",
                "Missing-relative ground involving war or terrorist operations",
            ),
            applicability=all_of(
                eq(
                    "applicant_largest_eligible_relative_status",
                    "authority_documented_yes",
                ),
                one_of(
                    "missing_relative_category",
                    ("officer", "volunteer", "conscript", "citizen"),
                ),
                eq("missing_relative_alive_status", "missing"),
                any_of(
                    eq("missing_relative_cause", "war_operations"),
                    all_of(
                        eq("missing_person_basis_uses_2026_wording", True),
                        eq("missing_relative_cause", "terrorist_operations"),
                    ),
                ),
            ),
            evidence_link_ids=("EL-LAW2-2026-ART7-II-E",),
            verification_state="needs_reverification",
            display_order=50,
        ),
        EligibilityBasisDefinition(
            id="family.sibling_current_service",
            text=t(
                "أساس وجود أخ في الخدمة الإلزامية أو استدعاء احتياط مؤهل",
                "Sibling currently in compulsory service or qualifying reserve recall",
            ),
            applicability=all_of(
                one_of(
                    "sibling_service_status",
                    ("compulsory_service", "reserve_recall"),
                ),
                eq(
                    "applicant_eldest_remaining_brother_status",
                    "authority_documented_yes",
                ),
                eq("article7_third_exclusion_status", "none_documented"),
            ),
            evidence_link_ids=("EL-LAW127-ART7-III",),
            verification_state="needs_reverification",
            display_order=60,
        ),
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
            document_type_id="military_supporting_documents",
            scope="shared",
        ),
        ClaimDefinition(
            id="mil.basis.only_son_living_father",
            text=t(
                "الابن الوحيد لأبيه الحي",
                "Only son of a living father — candidate statutory ground",
            ),
            classification="legal_basis_candidate",
            applicability=None,
            evidence_link_ids=("EL-LAW127-ART7-II-A",),
            verification_state="needs_reverification",
            display_order=20,
            scope="eligibility_basis",
            eligibility_basis_id="family.only_son_living_father",
        ),
        ClaimDefinition(
            id="mil.basis.support_father_or_brothers",
            text=t(
                "أساس إعالة الأب أو الإخوة وفق المادة 7/ثانياً (ب)",
                "Father/incapable-brother support ground — candidate statutory ground",
            ),
            classification="legal_basis_candidate",
            applicability=None,
            evidence_link_ids=("EL-LAW127-ART7-II-B",),
            verification_state="needs_reverification",
            display_order=30,
            scope="eligibility_basis",
            eligibility_basis_id="family.support_father_or_incapable_brothers",
        ),
        ClaimDefinition(
            id="mil.basis.support_mother",
            text=t("أساس إعالة الأم", "Mother support — candidate statutory ground"),
            classification="legal_basis_candidate",
            applicability=None,
            evidence_link_ids=("EL-LAW127-ART7-II-C",),
            verification_state="needs_reverification",
            display_order=40,
            scope="eligibility_basis",
            eligibility_basis_id="family.support_mother",
        ),
        ClaimDefinition(
            id="mil.basis.support_unmarried_sisters",
            text=t(
                "أساس إعالة الأخوات غير المتزوجات",
                "Unmarried-sister support — candidate statutory ground",
            ),
            classification="legal_basis_candidate",
            applicability=None,
            evidence_link_ids=("EL-LAW127-ART7-II-D",),
            verification_state="needs_reverification",
            display_order=50,
            scope="eligibility_basis",
            eligibility_basis_id="family.support_unmarried_sisters",
        ),
        ClaimDefinition(
            id="mil.basis.missing_war_or_terror_relative",
            text=t(
                "أساس القريب المفقود بسبب العمليات الحربية أو الإرهابية",
                "Missing war/terror relative — candidate statutory ground",
            ),
            classification="legal_basis_candidate",
            applicability=None,
            evidence_link_ids=("EL-LAW2-2026-ART7-II-E",),
            verification_state="needs_reverification",
            display_order=60,
            scope="eligibility_basis",
            eligibility_basis_id="family.missing_war_or_terror_relative",
        ),
        ClaimDefinition(
            id="mil.basis.sibling_current_service",
            text=t(
                "أساس وجود أخ في الخدمة الحالية",
                "Sibling-current-service — candidate statutory ground",
            ),
            classification="legal_basis_candidate",
            applicability=None,
            evidence_link_ids=("EL-LAW127-ART7-III",),
            verification_state="needs_reverification",
            display_order=70,
            scope="eligibility_basis",
            eligibility_basis_id="family.sibling_current_service",
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
            phase_order=10,
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
            phase_order=20,
        ),
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
        ServicePointDefinition(
            id="sp.recruitment_region_giza",
            text=t("منطقة تجنيد وتعبئة الجيزة", "Giza Recruitment and Mobilization Region"),
        ),
        ServicePointDefinition(
            id="sp.recruitment_region_mansoura",
            text=t("منطقة تجنيد وتعبئة المنصورة", "Mansoura Recruitment and Mobilization Region"),
        ),
        ServicePointDefinition(
            id="sp.recruitment_region_zagazig",
            text=t("منطقة تجنيد وتعبئة الزقازيق", "Zagazig Recruitment and Mobilization Region"),
        ),
    )
    service_point_versions = (
        ServicePointVersionDefinition(
            id="spv.recruitment_region_giza.research-2026-08-26",
            service_point_id="sp.recruitment_region_giza",
            address=t("الهرم، الجيزة", "Haram, Giza"),
            availability="available",
            effective_from=None,
            effective_to=None,
            evidence_link_ids=("EL-TAGNED-REGIONS",),
            verification_state="current",
        ),
        ServicePointVersionDefinition(
            id="spv.recruitment_region_mansoura.research-2026-08-26",
            service_point_id="sp.recruitment_region_mansoura",
            address=t("سندوب، المنصورة", "Sandoub, Mansoura"),
            availability="available",
            effective_from=None,
            effective_to=None,
            evidence_link_ids=("EL-TAGNED-REGIONS",),
            verification_state="current",
        ),
        ServicePointVersionDefinition(
            id="spv.recruitment_region_zagazig.research-2026-08-26",
            service_point_id="sp.recruitment_region_zagazig",
            address=t("تل بسطا، الزقازيق", "Tel Basta, Zagazig"),
            availability="available",
            effective_from=None,
            effective_to=None,
            evidence_link_ids=("EL-TAGNED-REGIONS",),
            verification_state="current",
        ),
    )
    service_point_associations = (
        ProcedureServicePointAssociationDefinition(
            id="spa.mil.giza_region",
            service_point_version_id="spv.recruitment_region_giza.research-2026-08-26",
            applicability=one_of(
                "residence_governorate",
                ("giza", "fayoum", "6_october"),
            ),
            effective_from=None,
            effective_to=None,
            evidence_link_ids=("EL-TAGNED-REGIONS",),
            verification_state="current",
        ),
        ProcedureServicePointAssociationDefinition(
            id="spa.mil.mansoura_region",
            service_point_version_id="spv.recruitment_region_mansoura.research-2026-08-26",
            applicability=one_of(
                "residence_governorate",
                ("dakahlia", "damietta", "kafr_el_sheikh"),
            ),
            effective_from=None,
            effective_to=None,
            evidence_link_ids=("EL-TAGNED-REGIONS",),
            verification_state="current",
        ),
        ProcedureServicePointAssociationDefinition(
            id="spa.mil.zagazig_region",
            service_point_version_id="spv.recruitment_region_zagazig.research-2026-08-26",
            applicability=one_of(
                "residence_governorate",
                (
                    "sharqia",
                    "suez",
                    "ismailia",
                    "port_said",
                    "north_sinai",
                    "south_sinai",
                ),
            ),
            effective_from=None,
            effective_to=None,
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
            kind="product",
            role="limitation",
        ),
        WarningDefinition(
            id="mil.warning.recheck",
            text=t(
                "أعد التحقق من التعليمات قبل التوجه.",
                "Re-check current instructions before acting.",
            ),
            severity="important",
            kind="product",
            role="regeneration",
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
    )

    return KnowledgeBundle(
        id="temporary-family-exemption.research-2026-08-26",
        goal=goal,
        procedure=procedure,
        sources=sources,
        evidence_links=evidence_links,
        claims=claims,
        steps=steps,
        fees=fees,
        service_points=service_points,
        warnings=warnings,
        unknowns=unknowns,
        eligibility_bases=eligibility_bases,
        service_point_versions=service_point_versions,
        service_point_associations=service_point_associations,
        basis_verification_path=VerificationPathDefinition(
            id="mil.basis.verify",
            text=t(
                "تحقق من أساس الإعفاء وحالتك التجنيدية لدى منطقة التجنيد والتعبئة المختصة؛ مطابقة الخطة ليست قرار إعفاء.",
                "Verify the exemption ground and military-service status with the competent Recruitment and Mobilization region; a planner match is not an exemption decision.",
            ),
            evidence_link_ids=("EL-TAGNED-REGIONS", "EL-TAGNED-CERT-REVIEW"),
        ),
        no_applicable_basis_text=t(
            "لا يطابق ما قدمته أي أساس عائلي مؤقت مدعوم في هذه الحزمة البحثية. لا تستخدم أقرب أساس بديل؛ تحقق من حالتك لدى الجهة المختصة.",
            "The supplied facts do not match any temporary family ground supported by this research fixture. Do not use a closest-match ground; verify your status with the competent authority.",
        ),
        routing_verification_path=VerificationPathDefinition(
            id="mil.routing.verify",
            text=t(
                "تحقق من منطقة التجنيد والتعبئة المختصة من دليل المناطق الرسمي قبل التوجه.",
                "Verify the competent Recruitment and Mobilization region in the official regions directory before acting.",
            ),
            evidence_link_ids=("EL-TAGNED-REGIONS",),
        ),
    )
