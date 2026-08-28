from __future__ import annotations

from ..contracts import (
    GoalCatalogDefinition,
    GoalDefinition,
    KnowledgeCatalog,
    LocalizedText,
    ProcedureCandidateDefinition,
    QuestionDefinition,
)
from ..evaluator import all_of, eq, one_of
from .national_id_renewal import load_national_id_renewal_fixture
from .passport_renewal import load_passport_renewal_fixture
from .temporary_family_exemption import load_temporary_family_exemption_fixture


def t(ar: str, en: str) -> LocalizedText:
    return LocalizedText(ar=ar, en=en)


def load_researched_catalog() -> KnowledgeCatalog:
    passport = load_passport_renewal_fixture()
    national_id = load_national_id_renewal_fixture()
    military = load_temporary_family_exemption_fixture()

    passport_candidates = (
        ProcedureCandidateDefinition(
            procedure_id=passport.procedure.procedure_id,
            text=passport.procedure.text,
            applicability=passport.procedure.applicability,
            fixture_id=passport.procedure.procedure_id,
        ),
        ProcedureCandidateDefinition(
            procedure_id="first_egyptian_passport_issuance",
            text=t(
                "استخراج أول جواز سفر مصري عادي داخل مصر",
                "First ordinary Egyptian passport issuance inside Egypt",
            ),
            applicability=all_of(
                eq("citizenship", "egyptian"),
                eq("application_location", "inside_egypt"),
                eq("passport_class", "ordinary"),
                eq("existing_passport_state", "none"),
            ),
        ),
        ProcedureCandidateDefinition(
            procedure_id="lost_passport_replacement",
            text=t("استخراج بدل فاقد لجواز السفر", "Replace a lost passport"),
            applicability=all_of(
                eq("citizenship", "egyptian"),
                eq("application_location", "inside_egypt"),
                eq("passport_class", "ordinary"),
                eq("existing_passport_state", "lost"),
            ),
        ),
        ProcedureCandidateDefinition(
            procedure_id="damaged_passport_replacement",
            text=t("استخراج بدل تالف لجواز السفر", "Replace a damaged passport"),
            applicability=all_of(
                eq("citizenship", "egyptian"),
                eq("application_location", "inside_egypt"),
                eq("passport_class", "ordinary"),
                eq("existing_passport_state", "damaged"),
            ),
        ),
        ProcedureCandidateDefinition(
            procedure_id="consular_passport_service",
            text=t("معاملة جواز سفر من خارج مصر", "Passport service outside Egypt"),
            applicability=all_of(
                eq("citizenship", "egyptian"),
                eq("application_location", "outside_egypt"),
            ),
        ),
    )

    national_id_candidates = (
        ProcedureCandidateDefinition(
            procedure_id=national_id.procedure.procedure_id,
            text=national_id.procedure.text,
            applicability=national_id.procedure.applicability,
            fixture_id=national_id.procedure.procedure_id,
        ),
        ProcedureCandidateDefinition(
            procedure_id="first_national_id_issuance",
            text=t("استخراج بطاقة رقم قومي لأول مرة", "First National ID issuance"),
            applicability=all_of(
                eq("application_location", "inside_egypt"),
                eq("national_id_possession_state", "none"),
            ),
        ),
        ProcedureCandidateDefinition(
            procedure_id="lost_national_id_replacement",
            text=t("استخراج بدل فاقد لبطاقة الرقم القومي", "Replace a lost National ID"),
            applicability=all_of(
                eq("application_location", "inside_egypt"),
                eq("national_id_possession_state", "lost"),
            ),
        ),
        ProcedureCandidateDefinition(
            procedure_id="damaged_national_id_replacement",
            text=t("استخراج بدل تالف لبطاقة الرقم القومي", "Replace a damaged National ID"),
            applicability=all_of(
                eq("application_location", "inside_egypt"),
                eq("national_id_possession_state", "damaged"),
            ),
        ),
        ProcedureCandidateDefinition(
            procedure_id="national_id_data_update",
            text=t("تحديث بيانات بطاقة الرقم القومي", "Update National ID data"),
            applicability=all_of(
                eq("application_location", "inside_egypt"),
                eq("national_id_possession_state", "held"),
                one_of(
                    "national_id_data_change_kind",
                    ("residence", "profession", "marital_status", "other", "multiple"),
                ),
            ),
        ),
        ProcedureCandidateDefinition(
            procedure_id="consular_national_id_service",
            text=t("معاملة بطاقة رقم قومي من خارج مصر", "National ID service outside Egypt"),
            applicability=eq("application_location", "outside_egypt"),
        ),
    )

    military_candidates = (
        ProcedureCandidateDefinition(
            procedure_id=military.procedure.procedure_id,
            text=military.procedure.text,
            applicability=military.procedure.applicability,
            fixture_id=military.procedure.procedure_id,
        ),
    )

    goals = {
        "get_egyptian_passport": GoalCatalogDefinition(
            goal=GoalDefinition(
                id="get_egyptian_passport",
                text=passport.goal.text,
                procedure_ids=tuple(candidate.procedure_id for candidate in passport_candidates),
            ),
            candidates=passport_candidates,
        ),
        "get_egyptian_national_id": GoalCatalogDefinition(
            goal=GoalDefinition(
                id="get_egyptian_national_id",
                text=national_id.goal.text,
                procedure_ids=tuple(candidate.procedure_id for candidate in national_id_candidates),
            ),
            candidates=national_id_candidates,
        ),
        "handle_military_service_paperwork": GoalCatalogDefinition(
            goal=GoalDefinition(
                id="handle_military_service_paperwork",
                text=military.goal.text,
                procedure_ids=tuple(candidate.procedure_id for candidate in military_candidates),
            ),
            candidates=military_candidates,
        ),
    }

    questions = (
        QuestionDefinition(
            "q.application_location",
            "get_egyptian_passport",
            "application_location",
            t(
                "هل ستقدّم طلب الجواز من داخل مصر أم من خارجها؟",
                "Will you apply for the passport from inside or outside Egypt?",
            ),
            10,
        ),
        QuestionDefinition(
            "q.existing_passport_state",
            "get_egyptian_passport",
            "existing_passport_state",
            t("ما حالة جواز سفرك الحالي؟", "What is the status of your current passport?"),
            20,
        ),
        QuestionDefinition(
            "q.passport_class",
            "get_egyptian_passport",
            "passport_class",
            t(
                "هل جواز السفر المطلوب جواز عادي أم من فئة أخرى؟",
                "Is the passport you need an ordinary passport or another class?",
            ),
            30,
        ),
        QuestionDefinition(
            "q.nid.application_location",
            "get_egyptian_national_id",
            "application_location",
            t(
                "هل ستجري معاملة بطاقة الرقم القومي من داخل مصر أم من خارجها؟",
                "Will you handle the National ID transaction from inside or outside Egypt?",
            ),
            10,
        ),
        QuestionDefinition(
            "q.nid.possession_state",
            "get_egyptian_national_id",
            "national_id_possession_state",
            t(
                "ما حالة بطاقة الرقم القومي الحالية لديك؟",
                "What is the status of your current National ID card?",
            ),
            20,
        ),
        QuestionDefinition(
            "q.nid.data_change_kind",
            "get_egyptian_national_id",
            "national_id_data_change_kind",
            t(
                "هل تحتاج إلى تغيير أي بيانات مسجلة على البطاقة أو في حالتك المدنية؟",
                "Do you need to change any data recorded on the card or in your civil-status record?",
            ),
            30,
        ),
        QuestionDefinition(
            "q.nid.expiry_date",
            "get_egyptian_national_id",
            "national_id_expiry_date",
            t(
                "ما تاريخ انتهاء بطاقة الرقم القومي الحالية؟",
                "What is the expiry date printed on your current National ID?",
            ),
            40,
            ("national_id_expiry_date", "card_expired_before_evaluation_date"),
        ),
        QuestionDefinition(
            "q.mil.application_location",
            "handle_military_service_paperwork",
            "application_location",
            t(
                "هل ستتعامل مع موقفك التجنيدي من داخل مصر أم من خارجها؟",
                "Will you handle your military-service status from inside or outside Egypt?",
            ),
            10,
        ),
        QuestionDefinition(
            "q.mil.father_alive",
            "handle_military_service_paperwork",
            "father_alive",
            t("هل والدك على قيد الحياة؟", "Is your father alive?"),
            20,
        ),
        QuestionDefinition(
            "q.mil.other_sons_count",
            "handle_military_service_paperwork",
            "other_living_sons_of_father_count",
            t(
                "كم عدد الأبناء الذكور الآخرين الأحياء لوالدك؟",
                "How many other living sons does your father have?",
            ),
            30,
        ),
        QuestionDefinition(
            "q.mil.father_capacity",
            "handle_military_service_paperwork",
            "father_unable_to_earn_status",
            t(
                "هل لديك مستند أو حالة معتمدة تثبت أن والدك غير قادر على الكسب؟",
                "Do you have an accepted document/status establishing that your father is unable to earn?",
            ),
            40,
        ),
        QuestionDefinition(
            "q.mil.mother_status",
            "handle_military_service_paperwork",
            "mother_family_status",
            t("ما الحالة العائلية ذات الصلة لوالدتك؟", "What is your mother's relevant family status?"),
            50,
        ),
        QuestionDefinition(
            "q.mil.unmarried_sisters",
            "handle_military_service_paperwork",
            "unmarried_sisters_requiring_support_count",
            t(
                "كم عدد أخواتك غير المتزوجات اللاتي تدخل حالتهن في طلب الإعفاء؟",
                "How many unmarried sisters are relevant to the exemption request?",
            ),
            60,
        ),
        QuestionDefinition(
            "q.mil.sibling_service",
            "handle_military_service_paperwork",
            "sibling_service_status",
            t(
                "هل أحد إخوتك حالياً في الخدمة الإلزامية أو مستدعى للاحتياط؟",
                "Is one of your brothers currently in compulsory service or called for qualifying reserve service?",
            ),
            80,
        ),
    )

    return KnowledgeCatalog(
        id="researched-procedures.2026-08-26",
        goals=goals,
        fixtures={
            passport.procedure.procedure_id: passport,
            national_id.procedure.procedure_id: national_id,
            military.procedure.procedure_id: military,
        },
        questions=questions,
    )
