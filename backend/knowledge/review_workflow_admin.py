"""Django Admin visibility for Procedure Version review policy and approval history."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from .review_workflow import (
    ProcedureVersionAuditApproval,
    ProcedureVersionReviewApproval,
    ProcedureVersionReviewPolicy,
)


@admin.register(ProcedureVersionReviewPolicy)
class ProcedureVersionReviewPolicyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "procedure_version",
        "author",
        "legal_risk",
        "military_risk",
        "custody_guardianship_risk",
        "contested_identity_risk",
    )
    list_filter = (
        "legal_risk",
        "military_risk",
        "custody_guardianship_risk",
        "contested_identity_risk",
        "procedure_version__state",
    )
    search_fields = ("procedure_version__semantic_id", "author__username")
    autocomplete_fields = ("procedure_version", "author")

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: ProcedureVersionReviewPolicy | None = None,
    ) -> tuple[str, ...]:
        if obj and obj.procedure_version.state != obj.procedure_version.State.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return ()

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ProcedureVersionReviewPolicy | None = None,
    ) -> bool:
        if obj and obj.procedure_version.state != obj.procedure_version.State.DRAFT:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ProcedureVersionReviewApproval)
class ProcedureVersionReviewApprovalAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "procedure_version",
        "approval_kind",
        "dimension",
        "specialist_risk",
        "reviewer",
        "approved_at",
    )
    list_filter = ("approval_kind", "dimension", "specialist_risk", "approved_at")
    search_fields = ("procedure_version__semantic_id", "reviewer__username")
    readonly_fields = tuple(field.name for field in ProcedureVersionReviewApproval._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ProcedureVersionReviewApproval | None = None,
    ) -> bool:
        return False


@admin.register(ProcedureVersionAuditApproval)
class ProcedureVersionAuditApprovalAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "audit_event",
        "approval_kind",
        "dimension",
        "specialist_risk",
        "actor",
        "approved_at",
    )
    list_filter = ("approval_kind", "dimension", "specialist_risk")
    search_fields = ("audit_event__version__semantic_id", "actor__username")
    readonly_fields = tuple(field.name for field in ProcedureVersionAuditApproval._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ProcedureVersionAuditApproval | None = None,
    ) -> bool:
        return False


__all__ = (
    "ProcedureVersionAuditApprovalAdmin",
    "ProcedureVersionReviewApprovalAdmin",
    "ProcedureVersionReviewPolicyAdmin",
)
