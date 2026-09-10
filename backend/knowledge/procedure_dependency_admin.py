"""Django Admin authoring for direct Procedure prerequisites."""

from __future__ import annotations

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.http import HttpRequest

from .domain import decode_stored_rule, diagnostic_messages
from .models import EvidenceLink, ProcedureVersion
from .procedure_dependencies import ProcedureDependency


class ProcedureDependencyForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = ProcedureDependency
        fields = "__all__"

    def clean_applicability(self) -> object:
        value = self.cleaned_data["applicability"]
        if value != {}:
            result = decode_stored_rule(value)
            if result.diagnostics:
                raise ValidationError(diagnostic_messages(result))
        return value

    def clean_satisfied_when(self) -> object:
        value = self.cleaned_data["satisfied_when"]
        if value == {}:
            raise ValidationError("Dependency satisfaction rule is required.")
        result = decode_stored_rule(value)
        if result.diagnostics:
            raise ValidationError(diagnostic_messages(result))
        return value


class ProcedureDependencyEvidenceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = EvidenceLink
    fk_name = "procedure_dependency"
    fields = (
        "id",
        "passage",
        "location",
        "applicability_context",
        "verification_state",
        "support_status",
    )
    readonly_fields = ("id",)
    extra = 1
    show_change_link = True

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: ProcedureDependency | None = None,
    ) -> bool:
        if not super().has_add_permission(request, obj):
            return False
        return bool(obj is not None and obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: ProcedureDependency | None = None,
    ) -> bool:
        if not super().has_change_permission(request, obj):
            return False
        return bool(obj is None or obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ProcedureDependency | None = None,
    ) -> bool:
        if not super().has_delete_permission(request, obj):
            return False
        return bool(obj is not None and obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: ProcedureDependency | None = None,
    ) -> tuple[str, ...]:
        if obj is not None and obj.procedure_version.state != ProcedureVersion.State.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return ("id",)


@admin.register(ProcedureDependency)
class ProcedureDependencyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = ProcedureDependencyForm
    list_display = (
        "semantic_id",
        "procedure_version",
        "target_procedure",
        "relation",
        "display_order",
        "verification_state",
    )
    list_filter = ("relation", "verification_state", "procedure_version")
    search_fields = (
        "semantic_id",
        "text_ar",
        "text_en",
        "procedure_version__semantic_id",
        "target_procedure__semantic_id",
    )
    autocomplete_fields = ("procedure_version", "target_procedure")
    inlines = (ProcedureDependencyEvidenceInline,)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: ProcedureDependency | None = None,
    ) -> tuple[str, ...]:
        return (
            tuple(field.name for field in self.model._meta.fields)
            if obj and obj.procedure_version.state != ProcedureVersion.State.DRAFT
            else ()
        )

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ProcedureDependency | None = None,
    ) -> bool:
        if not super().has_delete_permission(request, obj):
            return False
        return bool(obj is None or obj.procedure_version.state == ProcedureVersion.State.DRAFT)


class ProcedureDependencyOwnerInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ProcedureDependency
    fields = (
        "semantic_id",
        "target_procedure",
        "relation",
        "display_order",
        "verification_state",
    )
    readonly_fields = fields
    extra = 0
    show_change_link = True

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: ProcedureVersion | None = None,
    ) -> bool:
        if not super().has_add_permission(request, obj):
            return False
        return bool(obj is not None and obj.state == ProcedureVersion.State.DRAFT)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ProcedureVersion | None = None,
    ) -> bool:
        if not super().has_delete_permission(request, obj):
            return False
        return bool(obj is not None and obj.state == ProcedureVersion.State.DRAFT)

__all__ = (
    "ProcedureDependencyAdmin",
    "ProcedureDependencyEvidenceInline",
    "ProcedureDependencyForm",
    "ProcedureDependencyOwnerInline",
)
