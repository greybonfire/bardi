"""Django Admin authoring and lifecycle protection for Service Point routing."""

from __future__ import annotations

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.http import HttpRequest

from .domain import decode_stored_rule, diagnostic_messages
from .models import EvidenceLink, ProcedureVersion
from .service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)


def _material_is_preserved(obj: ServicePointVersion) -> bool:
    return obj.associations.filter(procedure_version__state__in=("published", "withdrawn")).exists()


def _point_is_preserved(obj: ServicePoint) -> bool:
    return obj.versions.filter(
        associations__procedure_version__state__in=("published", "withdrawn")
    ).exists()


class ProcedureServicePointAssociationForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = ProcedureServicePointAssociation
        fields = "__all__"

    def clean_applicability(self) -> object:
        value = self.cleaned_data["applicability"]
        if value == {}:
            raise ValidationError("Routing applicability is required.")
        decoded = decode_stored_rule(value)
        if decoded.diagnostics:
            raise ValidationError(diagnostic_messages(decoded))
        return value

    def clean(self) -> dict[str, object] | None:
        cleaned = super().clean()
        if cleaned:
            start, end = cleaned.get("effective_from"), cleaned.get("effective_to")
            if start and end and start > end:
                self.add_error("effective_to", "Effective interval is not ordered.")
        return cleaned


class RoutingEvidenceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = EvidenceLink
    extra = 1
    show_change_link = True
    fields = (
        "id",
        "passage",
        "location",
        "applicability_context",
        "verification_state",
        "support_status",
    )
    readonly_fields = ("id",)

    def _draft(self, obj: object | None) -> bool:
        if obj is None:
            return True
        if isinstance(obj, ProcedureServicePointAssociation):
            return obj.procedure_version.state == ProcedureVersion.State.DRAFT
        assert isinstance(obj, ServicePointVersion)
        return not _material_is_preserved(obj)

    def has_add_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return obj is not None and self._draft(obj)

    def has_change_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return self._draft(obj)

    def has_delete_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return obj is not None and self._draft(obj)


class ServicePointVersionEvidenceInline(RoutingEvidenceInline):
    fk_name = "service_point_version"


class AssociationEvidenceInline(RoutingEvidenceInline):
    fk_name = "procedure_service_point_association"


@admin.register(ServicePoint)
class ServicePointAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("semantic_id", "name_en", "name_ar")
    search_fields = ("semantic_id", "name_en", "name_ar")
    ordering = ("semantic_id",)

    def get_readonly_fields(
        self, request: HttpRequest, obj: ServicePoint | None = None
    ) -> tuple[str, ...]:
        return (
            tuple(field.name for field in self.model._meta.fields)
            if obj and _point_is_preserved(obj)
            else ()
        )

    def has_delete_permission(self, request: HttpRequest, obj: ServicePoint | None = None) -> bool:
        return not (obj and _point_is_preserved(obj))


@admin.register(ServicePointVersion)
class ServicePointVersionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "semantic_id",
        "service_point",
        "availability",
        "effective_from",
        "effective_to",
        "verification_state",
    )
    list_filter = ("availability", "verification_state", "service_point")
    search_fields = ("semantic_id", "service_point__semantic_id", "address_en", "address_ar")
    autocomplete_fields = ("service_point",)
    ordering = ("service_point__semantic_id", "effective_from", "semantic_id")
    inlines = (ServicePointVersionEvidenceInline,)

    def get_readonly_fields(
        self, request: HttpRequest, obj: ServicePointVersion | None = None
    ) -> tuple[str, ...]:
        return (
            tuple(field.name for field in self.model._meta.fields)
            if obj and _material_is_preserved(obj)
            else ()
        )

    def has_delete_permission(
        self, request: HttpRequest, obj: ServicePointVersion | None = None
    ) -> bool:
        return not (obj and _material_is_preserved(obj))


@admin.register(ProcedureServicePointAssociation)
class ProcedureServicePointAssociationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = ProcedureServicePointAssociationForm
    list_display = (
        "semantic_id",
        "procedure_version",
        "service_point_version",
        "effective_from",
        "effective_to",
        "verification_state",
    )
    list_filter = ("verification_state", "procedure_version")
    search_fields = (
        "semantic_id",
        "procedure_version__semantic_id",
        "service_point_version__semantic_id",
    )
    autocomplete_fields = ("procedure_version", "service_point_version")
    ordering = ("procedure_version__semantic_id", "semantic_id")
    inlines = (AssociationEvidenceInline,)

    def get_readonly_fields(
        self, request: HttpRequest, obj: ProcedureServicePointAssociation | None = None
    ) -> tuple[str, ...]:
        return (
            tuple(field.name for field in self.model._meta.fields)
            if obj and obj.procedure_version.state != ProcedureVersion.State.DRAFT
            else ()
        )

    def has_delete_permission(
        self, request: HttpRequest, obj: ProcedureServicePointAssociation | None = None
    ) -> bool:
        return not (obj and obj.procedure_version.state != ProcedureVersion.State.DRAFT)


class ProcedureServicePointAssociationInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ProcedureServicePointAssociation
    fields = ("semantic_id", "service_point_version", "verification_state")
    readonly_fields = fields
    extra = 0
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: ProcedureVersion | None = None) -> bool:
        return bool(obj and obj.state == ProcedureVersion.State.DRAFT)

    def has_delete_permission(
        self, request: HttpRequest, obj: ProcedureVersion | None = None
    ) -> bool:
        return bool(obj and obj.state == ProcedureVersion.State.DRAFT)


def install_procedure_version_routing_inline() -> None:
    from .admin import ProcedureVersionAdmin

    if ProcedureServicePointAssociationInline not in ProcedureVersionAdmin.inlines:
        ProcedureVersionAdmin.inlines = (
            *ProcedureVersionAdmin.inlines,
            ProcedureServicePointAssociationInline,
        )  # type: ignore[assignment]


install_procedure_version_routing_inline()

__all__ = ("ProcedureServicePointAssociationAdmin", "ServicePointAdmin", "ServicePointVersionAdmin")
