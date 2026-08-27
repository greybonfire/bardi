from __future__ import annotations

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


def derive_facts(facts: dict[str, object], evaluation_date: date) -> dict[str, object]:
    derived = dict(facts)
    birth_date = facts.get("birth_date")
    if isinstance(birth_date, date):
        age = completed_years(birth_date, evaluation_date)
        derived["age_years_on_evaluation_date"] = age
        derived["is_under_15"] = age < 15
        derived["is_15_or_older"] = age >= 15
    return derived
