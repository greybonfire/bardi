from dataclasses import replace

from ..contracts import LocalizedText, QuestionDefinition
from ..facts import FACT_DEFINITIONS
from .catalog import load_researched_catalog as _load_researched_catalog
from .national_id_renewal import load_national_id_renewal_fixture
from .passport_renewal import load_passport_renewal_fixture
from .temporary_family_exemption import load_temporary_family_exemption_fixture


def _t(ar: str, en: str) -> LocalizedText:
    return LocalizedText(ar=ar, en=en)


def load_researched_catalog():
    """Load the researched catalog enriched with the typed #7 Fact contract."""
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
    return replace(
        catalog,
        questions=catalog.questions + additional_questions,
        fact_definitions=FACT_DEFINITIONS,
    )


__all__ = [
    "load_passport_renewal_fixture",
    "load_national_id_renewal_fixture",
    "load_temporary_family_exemption_fixture",
    "load_researched_catalog",
]
