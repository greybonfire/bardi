"""Django Admin surface for version-owned planning acceptance scenarios."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from .planning_scenarios import PlanningScenario


@admin.register(PlanningScenario)
class PlanningScenarioAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "procedure_version",
        "kind",
        "expected_result_family",
        "evaluation_date_display",
    )
    list_filter = ("kind", "expected_result_family", "procedure_version__state")
    search_fields = ("name", "procedure_version__semantic_id")
    autocomplete_fields = ("procedure_version",)
    readonly_fields = ("behavior_signature",)

    @admin.display(description="Evaluation date")
    def evaluation_date_display(self, obj: PlanningScenario) -> str:
        value = obj.evaluation_context.get("evaluation_date")
        return value if isinstance(value, str) else ""

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: PlanningScenario | None = None,
    ) -> tuple[str, ...]:
        if obj and obj.procedure_version.state != obj.procedure_version.State.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return ("behavior_signature",)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: PlanningScenario | None = None,
    ) -> bool:
        if not super().has_delete_permission(request, obj):
            return False
        return bool(obj is None or obj.procedure_version.state == obj.procedure_version.State.DRAFT)


__all__ = ("PlanningScenarioAdmin",)
