"""Staff-only Django Admin surfaces for evidence discrepancies and review history."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest
from django.utils import timezone

from .evidence_workflow import (
    EvidenceDiscrepancy,
    EvidenceDiscrepancyEvidence,
    EvidenceReverificationEvent,
    EvidenceReverificationEvidence,
)


class EvidenceDiscrepancyEvidenceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = EvidenceDiscrepancyEvidence
    fields = ("evidence_link",)
    autocomplete_fields = ("evidence_link",)
    extra = 1

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: EvidenceDiscrepancy | None = None,
    ) -> bool:
        return bool(obj is not None and obj.status == EvidenceDiscrepancy.Status.OPEN)

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: EvidenceDiscrepancy | None = None,
    ) -> bool:
        return bool(obj is None or obj.status == EvidenceDiscrepancy.Status.OPEN)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: EvidenceDiscrepancy | None = None,
    ) -> bool:
        return bool(obj is not None and obj.status == EvidenceDiscrepancy.Status.OPEN)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: EvidenceDiscrepancy | None = None,
    ) -> tuple[str, ...]:
        if obj and obj.status == EvidenceDiscrepancy.Status.RESOLVED:
            return ("evidence_link",)
        return ()


@admin.register(EvidenceDiscrepancy)
class EvidenceDiscrepancyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "owner_display",
        "status",
        "outcome_state",
        "created_at",
        "resolved_at",
    )
    list_filter = ("status", "outcome_state", "created_at", "resolved_at")
    search_fields = (
        "rationale",
        "resolution",
        "anchor_evidence_link__checklist_item__semantic_id",
        "anchor_evidence_link__step__semantic_id",
        "anchor_evidence_link__warning__semantic_id",
        "anchor_evidence_link__fee__semantic_id",
        "anchor_evidence_link__eligibility_basis__semantic_id",
        "anchor_evidence_link__procedure_dependency__semantic_id",
        "anchor_evidence_link__procedure_service_point_association__semantic_id",
        "anchor_evidence_link__service_point_version__semantic_id",
    )
    autocomplete_fields = ("anchor_evidence_link",)
    inlines = (EvidenceDiscrepancyEvidenceInline,)

    @admin.display(description="Affected material")
    def owner_display(self, obj: EvidenceDiscrepancy) -> str:
        return str(obj.anchor_evidence_link.owner)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: EvidenceDiscrepancy | None = None,
    ) -> tuple[str, ...]:
        if obj and obj.status == EvidenceDiscrepancy.Status.RESOLVED:
            return tuple(field.name for field in self.model._meta.fields)
        if obj is None:
            return ("created_at", "created_by", "resolved_at", "resolved_by")
        return (
            "anchor_evidence_link",
            "created_at",
            "created_by",
            "resolved_at",
            "resolved_by",
        )

    def save_model(
        self,
        request: HttpRequest,
        obj: EvidenceDiscrepancy,
        form: object,
        change: bool,
    ) -> None:
        if not change:
            obj.created_by = request.user
            obj.status = EvidenceDiscrepancy.Status.OPEN
            obj.resolved_at = None
            obj.resolved_by = None
        else:
            stored = EvidenceDiscrepancy.objects.get(pk=obj.pk)
            if (
                stored.status == EvidenceDiscrepancy.Status.OPEN
                and obj.status == EvidenceDiscrepancy.Status.RESOLVED
            ):
                obj.resolved_at = timezone.now()
                obj.resolved_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: EvidenceDiscrepancy | None = None,
    ) -> bool:
        return False


class EvidenceReverificationEvidenceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = EvidenceReverificationEvidence
    fields = ("evidence_link",)
    readonly_fields = fields
    extra = 0

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: EvidenceReverificationEvent | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: EvidenceReverificationEvent | None = None,
    ) -> bool:
        return False


@admin.register(EvidenceReverificationEvent)
class EvidenceReverificationEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "owner_display",
        "verification_state",
        "verified_on",
        "reverify_on",
        "meaning_changed",
        "occurred_at",
    )
    list_filter = ("verification_state", "meaning_changed", "occurred_at")
    search_fields = ("rationale", "successor_version__semantic_id")
    inlines = (EvidenceReverificationEvidenceInline,)

    @admin.display(description="Reviewed material")
    def owner_display(self, obj: EvidenceReverificationEvent) -> str:
        return str(obj.anchor_evidence_link.owner)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: EvidenceReverificationEvent | None = None,
    ) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: EvidenceReverificationEvent | None = None,
    ) -> bool:
        return bool(obj is not None)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: EvidenceReverificationEvent | None = None,
    ) -> bool:
        return False


__all__ = (
    "EvidenceDiscrepancyAdmin",
    "EvidenceDiscrepancyEvidenceInline",
    "EvidenceReverificationEventAdmin",
    "EvidenceReverificationEvidenceInline",
)
