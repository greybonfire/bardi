"""Django Admin authoring surface for reachability-first Eligibility Bases."""

from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.core.exceptions import ValidationError
from django.http import HttpRequest

from .domain import decode_stored_rule, diagnostic_messages
from .models import EligibilityBasis, EvidenceLink, ProcedureVersion


class EligibilityBasisForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = EligibilityBasis
        fields = "__all__"

    def clean_reachability(self) -> object:
        value = self.cleaned_data["reachability"]
        if value != {}:
            result = decode_stored_rule(value)
            if result.diagnostics:
                raise ValidationError(diagnostic_messages(result))
        return value

    def clean_qualification(self) -> object:
        value = self.cleaned_data["qualification"]
        if value == {}:
            raise ValidationError("Eligibility Basis qualification is required.")
        result = decode_stored_rule(value)
        if result.diagnostics:
            raise ValidationError(diagnostic_messages(result))
        return value


class EligibilityBasisEvidenceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = EvidenceLink
    fk_name = "eligibility_basis"
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

    def has_add_permission(self, request: HttpRequest, obj: EligibilityBasis | None = None) -> bool:
        return bool(obj is not None and obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def has_change_permission(
        self, request: HttpRequest, obj: EligibilityBasis | None = None
    ) -> bool:
        return bool(obj is None or obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def has_delete_permission(
        self, request: HttpRequest, obj: EligibilityBasis | None = None
    ) -> bool:
        return bool(obj is not None and obj.procedure_version.state == ProcedureVersion.State.DRAFT)

    def get_readonly_fields(
        self, request: HttpRequest, obj: EligibilityBasis | None = None
    ) -> tuple[str, ...]:
        if obj is not None and obj.procedure_version.state != ProcedureVersion.State.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return ("id",)


try:
    admin.site.unregister(EligibilityBasis)
except NotRegistered:
    pass


@admin.register(EligibilityBasis)
class EligibilityBasisAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = EligibilityBasisForm
    list_display = (
        "semantic_id",
        "procedure_version",
        "display_order",
        "verification_state",
    )
    list_filter = ("verification_state", "procedure_version")
    search_fields = ("semantic_id", "text_ar", "text_en", "procedure_version__semantic_id")
    autocomplete_fields = ("procedure_version",)
    inlines = (EligibilityBasisEvidenceInline,)

    def get_readonly_fields(
        self, request: HttpRequest, obj: EligibilityBasis | None = None
    ) -> tuple[str, ...]:
        return (
            tuple(field.name for field in self.model._meta.fields)
            if obj and obj.procedure_version.state != ProcedureVersion.State.DRAFT
            else ()
        )

    def has_delete_permission(
        self, request: HttpRequest, obj: EligibilityBasis | None = None
    ) -> bool:
        return bool(obj is None or obj.procedure_version.state == ProcedureVersion.State.DRAFT)


class EligibilityBasisOwnerInline(admin.TabularInline):  # type: ignore[type-arg]
    model = EligibilityBasis
    fields = ("semantic_id", "display_order", "verification_state")
    readonly_fields = fields
    extra = 0
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: ProcedureVersion | None = None) -> bool:
        return bool(obj is not None and obj.state == ProcedureVersion.State.DRAFT)

    def has_delete_permission(
        self, request: HttpRequest, obj: ProcedureVersion | None = None
    ) -> bool:
        return bool(obj is not None and obj.state == ProcedureVersion.State.DRAFT)


def install_procedure_version_basis_inline() -> None:
    from .admin import ProcedureVersionAdmin

    if EligibilityBasisOwnerInline not in ProcedureVersionAdmin.inlines:
        ProcedureVersionAdmin.inlines = (  # type: ignore[assignment]
            *ProcedureVersionAdmin.inlines,
            EligibilityBasisOwnerInline,
        )


install_procedure_version_basis_inline()

__all__ = (
    "EligibilityBasisAdmin",
    "EligibilityBasisEvidenceInline",
    "EligibilityBasisForm",
    "EligibilityBasisOwnerInline",
)
