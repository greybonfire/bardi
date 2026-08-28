from __future__ import annotations

import calendar
from datetime import date


def completed_years(birth_date: date, evaluation_date: date) -> int:
    if birth_date > evaluation_date:
        raise ValueError("birth_date cannot be after evaluation_date")
    years = evaluation_date.year - birth_date.year
    before_birthday = (evaluation_date.month, evaluation_date.day) < (
        birth_date.month,
        birth_date.day,
    )
    return years - int(before_birthday)


def add_calendar_months(value: date, months: int) -> date:
    """Add calendar months, clamping month-end instead of converting to days."""
    month_index = value.year * 12 + (value.month - 1) + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def derive_facts(facts: dict[str, object], evaluation_date: date) -> dict[str, object]:
    derived = dict(facts)

    birth_date = facts.get("birth_date")
    if isinstance(birth_date, date):
        derived["age_years_on_evaluation_date"] = completed_years(birth_date, evaluation_date)

    expiry_date = facts.get("national_id_expiry_date")
    if isinstance(expiry_date, date):
        deadline = add_calendar_months(expiry_date, 3)
        derived["card_expired_before_evaluation_date"] = evaluation_date > expiry_date
        derived["renewal_deadline_date"] = deadline
        derived["renewal_deadline_passed"] = evaluation_date > deadline

    derived["missing_person_basis_uses_2026_wording"] = evaluation_date >= date(2026, 3, 25)
    return derived
