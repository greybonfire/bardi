"""Django Admin authoring surface for structured Fees."""

from __future__ import annotations

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.http import HttpRequest

from .domain import decode_stored_rule, diagnostic_messages
from .fees import Fee
from .models import EvidenceLink, ProcedureVersion


class FeeForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Fee
        fields = "__all__"

    def clean_applicability(self) -> object:
        value = self.cleaned_data["applicability"]
        if value != {}:
            result = decode_stored_rule(value)
            if result.diagnostics:
                raise ValidationError(diagnostic_messages(result))
        return value


class FeeEvidenceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = EvidenceLink
    fk_name = "fee"
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

    def has_add_permission(self, request: HttpRequest, obj: Fee | None = None) -> bool:
        return bool(obj is not None and obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def has_change_permission(self, request: HttpRequest, obj: Fee | None = None) -> bool:
        return bool(obj is None or obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def has_delete_permission(self, request: HttpRequest, obj: Fee | None = None) -> bool:
        return bool(obj is not None and obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def get_readonly_fields(self, request: HttpRequest, obj: Fee | None = None) -> tuple[str, ...]:
        if obj is not None and obj.procedure_version.state != ProcedureVersion.State.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return ("id",)


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = FeeForm
    list_display = (
        "semantic_id",
        "procedure_version",
        "value_state",
        "currency",
        "display_order",
        "verification_state",
    )
    list_filter = ("value_state", "currency", "verification_state", "procedure_version")
    search_fields = ("semantic_id", "text_ar", "text_en", "procedure_version__semantic_id")
    autocomplete_fields = ("procedure_version", "eligibility_basis")
    inlines = (FeeEvidenceInline,)

    def get_readonly_fields(self, request: HttpRequest, obj: Fee | None = None) -> tuple[str, ...]:
        return (
            tuple(field.name for field in self.model._meta.fields)
            if obj and obj.procedure_version.state != ProcedureVersion.State.DRAFT
            else ()
        )

    def has_delete_permission(self, request: HttpRequest, obj: Fee | None = None) -> bool:
        return bool(obj is None or obj.procedure_version.state == ProcedureVersion.State.DRAFT)


class FeeOwnerInline(admin.TabularInline):  # type: ignore[type-arg]
    model = Fee
    fields = (
        "semantic_id",
        "value_state",
        "currency",
        "display_order",
        "verification_state",
    )
    readonly_fields = fields
    extra = 0
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: ProcedureVersion | None = None) -> bool:
        return bool(obj is not None and obj.state == ProcedureVersion.State.DRAFT)

    def has_delete_permission(
        self, request: HttpRequest, obj: ProcedureVersion | None = None
    ) -> bool:
        return bool(obj is not None and obj.state == ProcedureVersion.State.DRAFT)


def install_procedure_version_fee_inline() -> None:
    """Add Fee navigation to the already registered ProcedureVersion Admin."""
    from .admin import ProcedureVersionAdmin

    if FeeOwnerInline not in ProcedureVersionAdmin.inlines:
        ProcedureVersionAdmin.inlines = (  # type: ignore[assignment]
            *ProcedureVersionAdmin.inlines,
            FeeOwnerInline,
        )


install_procedure_version_fee_inline()

__all__ = ("FeeAdmin", "FeeEvidenceInline", "FeeForm", "FeeOwnerInline")
