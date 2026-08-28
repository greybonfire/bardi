from dataclasses import replace

from ..contracts import ContradictionDefinition, LocalizedText, QuestionDefinition
from ..evaluator import all_of, eq, exists
from ..facts import FACT_DEFINITIONS
from .catalog import load_researched_catalog as _load_researched_catalog
from .national_id_renewal import load_national_id_renewal_fixture
from .passport_renewal import load_passport_renewal_fixture
from .temporary_family_exemption import load_temporary_family_exemption_fixture


def _t(ar: str, en: str) -> LocalizedText:
    return LocalizedText(ar=ar, en=en)


def load_researched_catalog():
    """Load the researched catalog enriched with typed Facts and diagnostics."""
    catalog = _load_researched_catalog()
    additional_questions = (
        QuestionDefinition(
            "q.birth_date",
            "get_egyptian_passport",
            "birth_date",
            _t("ما تاريخ ميلادك؟", "What is your date of birth?"),
            40,
            ("birth_date", "age_years_on_evaluation_date"),
        ),
        QuestionDefinition(
            "q.sex",
            "get_egyptian_passport",
            "sex",
            _t(
                "ما الجنس المثبت في مستنداتك الرسمية؟",
                "What sex is recorded on your official documents?",
            ),
            50,
        ),
        QuestionDefinition(
            "q.is_student",
            "get_egyptian_passport",
            "is_student",
            _t(
                "هل أنت طالب أو طالبة في العام الدراسي الحالي؟",
                "Are you a student in the current academic year?",
            ),
            70,
        ),
        QuestionDefinition(
            "q.service_level",
            "get_egyptian_passport",
            "service_level",
            _t(
                "هل تريد الخدمة العادية أم العاجلة أم المميزة؟",
                "Do you want standard, urgent, or premium service?",
            ),
            80,
        ),
        QuestionDefinition(
            "q.residence_police_jurisdiction",
            "get_egyptian_passport",
            "residence_police_jurisdiction",
            _t(
                "ما قسم أو مركز الشرطة التابع له محل إقامتك؟",
                "Which police district or centre covers your residence?",
            ),
            90,
        ),
        QuestionDefinition(
            "q.nid.residence_governorate",
            "get_egyptian_national_id",
            "residence_governorate",
            _t("ما محافظة محل إقامتك؟", "What is your governorate of residence?"),
            50,
        ),
        QuestionDefinition(
            "q.nid.residence_district",
            "get_egyptian_national_id",
            "residence_district",
            _t(
                "ما المركز أو القسم التابع له محل إقامتك؟",
                "Which district or centre covers your residence?",
            ),
            60,
        ),
        QuestionDefinition(
            "q.mil.governorate",
            "handle_military_service_paperwork",
            "residence_governorate",
            _t(
                "ما محافظة محل الإقامة المستخدمة في معاملتك التجنيدية؟",
                "Which governorate of residence is used for your recruitment transaction?",
            ),
            90,
        ),
    )
    contradictions = (
        ContradictionDefinition(
            id="nid.no_current_card_with_expiry_date",
            goal_id="get_egyptian_national_id",
            fact_keys=("national_id_possession_state", "national_id_expiry_date"),
            condition=all_of(
                eq("national_id_possession_state", "none"),
                exists("national_id_expiry_date"),
            ),
        ),
        ContradictionDefinition(
            id="mil.no_missing_relative_with_cause",
            goal_id="handle_military_service_paperwork",
            fact_keys=("missing_relative_category", "missing_relative_cause"),
            condition=all_of(
                eq("missing_relative_category", "none"),
                exists("missing_relative_cause"),
            ),
        ),
        ContradictionDefinition(
            id="mil.no_missing_relative_with_alive_status",
            goal_id="handle_military_service_paperwork",
            fact_keys=("missing_relative_category", "missing_relative_alive_status"),
            condition=all_of(
                eq("missing_relative_category", "none"),
                exists("missing_relative_alive_status"),
            ),
        ),
        ContradictionDefinition(
            id="mil.no_missing_relative_with_relative_order_status",
            goal_id="handle_military_service_paperwork",
            fact_keys=("missing_relative_category", "applicant_largest_eligible_relative_status"),
            condition=all_of(
                eq("missing_relative_category", "none"),
                exists("applicant_largest_eligible_relative_status"),
            ),
        ),
    )
    return replace(
        catalog,
        questions=catalog.questions + additional_questions,
        fact_definitions=FACT_DEFINITIONS,
        contradictions=contradictions,
    )


__all__ = [
    "load_passport_renewal_fixture",
    "load_national_id_renewal_fixture",
    "load_temporary_family_exemption_fixture",
    "load_researched_catalog",
]
