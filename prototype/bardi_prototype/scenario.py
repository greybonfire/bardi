from __future__ import annotations

from datetime import date
from typing import Mapping

from .contracts import InconclusiveResult, InvalidResult, KnowledgeBundle, Locale, PlanResult, PlanningResult
from .planner import KnownCaseIncomplete, ProcedureNotApplicable, assemble_known_case_plan
from .presentation import project_plan


def run_scenario(
    *,
    knowledge: KnowledgeBundle,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
) -> PlanningResult:
    """The prototype's single application-level behavioral seam."""
    if locale not in ("ar", "en"):
        return InvalidResult("unsupported_locale")
    if goal_id != knowledge.goal.id:
        return InvalidResult("unknown_goal")

    try:
        semantic_plan = assemble_known_case_plan(knowledge, facts, evaluation_date)
    except KnownCaseIncomplete:
        # Issue #7 will replace this known-case-only fallback with deterministic
        # UNKNOWN evaluation and an authored Missing-Fact Picker.
        return InconclusiveResult("known_case_requires_complete_facts")
    except (ProcedureNotApplicable, ValueError, TypeError):
        # Full invalid/unsupported diagnostics are deliberately deferred to #8.
        return InconclusiveResult("known_case_not_supported")

    return PlanResult(project_plan(semantic_plan, locale))
