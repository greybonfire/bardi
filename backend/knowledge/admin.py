from __future__ import annotations

from typing import Any, cast

from django.contrib import admin, messages
from django.db import models
from django.forms import ModelForm, Textarea
from django.forms.models import BaseInlineFormSet
from django.http import HttpRequest

from .forms import (
    CandidateForm,
    ContradictionFactFormSet,
    ContradictionForm,
    FactDefinitionForm,
    QuestionForm,
    QuestionResolvedFactFormSet,
)
from .models import (
    FactDefinition,
    Procedure,
    ProcedureVersion,
    ProcedureVersionAuditEvent,
    Service,
    ServiceContradiction,
    ServiceContradictionFact,
    ServiceProcedureCandidate,
    ServiceQuestion,
    ServiceQuestionResolvedFact,
)
from .publication import (
    PublicationRejected,
    publish_procedure_version,
    withdraw_procedure_version,
)
from .services import set_contradiction_facts, set_question_resolved_facts


def _ordered_formset_facts(
    formset: BaseInlineFormSet[Any, Any, ModelForm[Any]],
) -> list[FactDefinition]:
    rows: list[tuple[int, str, FactDefinition]] = []
    for inline_form in formset.forms:
        cleaned_data = inline_form.cleaned_data
        if not cleaned_data or cleaned_data.get("DELETE"):
            continue
        fact = cleaned_data["fact"]
        position = cleaned_data["position"]
        assert isinstance(fact, FactDefinition)
        assert isinstance(position, int)
        rows.append((position, fact.key, fact))
    rows.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in rows]


class CandidateInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ServiceProcedureCandidate
    form = CandidateForm
    extra = 0
    autocomplete_fields = ("procedure",)

    def get_formset(
        self, request: HttpRequest, obj: Service | None = None, **kwargs: object
    ) -> type[BaseInlineFormSet[Any, Any, ModelForm[Any]]]:
        formset = super().get_formset(request, obj, **kwargs)
        procedure_field = formset.form.base_fields.get("procedure")
        if procedure_field is not None and hasattr(procedure_field, "queryset"):
            procedure_field.queryset = Procedure.objects.filter(primary_service=obj)
        return formset


class QuestionOwnerInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ServiceQuestion
    form = QuestionForm
    extra = 0
    autocomplete_fields = ("fact",)
    fields = ("semantic_id", "fact", "priority", "text_ar", "text_en")


class ContradictionOwnerInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ServiceContradiction
    extra = 0
    fields = ("semantic_id", "condition")
    readonly_fields = ("semantic_id", "condition")
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: Service | None = None) -> bool:
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("semantic_id", "text_en", "is_active")
    list_filter = ("is_active",)
    search_fields = ("semantic_id", "text_en", "text_ar")
    ordering = ("semantic_id",)
    inlines = (CandidateInline, QuestionOwnerInline, ContradictionOwnerInline)


class ProcedureVersionHistoryInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ProcedureVersion
    fields = ("semantic_id", "state", "effective_from", "effective_to", "published_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: Procedure | None = None) -> bool:
        return False


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("semantic_id", "primary_service", "text_en")
    list_filter = ("primary_service",)
    search_fields = ("semantic_id", "primary_service__semantic_id", "text_en", "text_ar")
    autocomplete_fields = ("primary_service",)
    ordering = ("semantic_id",)
    inlines = (ProcedureVersionHistoryInline,)

    def get_readonly_fields(
        self, request: HttpRequest, obj: Procedure | None = None
    ) -> tuple[str, ...]:
        if obj is not None and obj.versions.exclude(state=ProcedureVersion.State.DRAFT).exists():
            return ("semantic_id", "primary_service")
        return ()


@admin.register(ProcedureVersion)
class ProcedureVersionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "semantic_id",
        "procedure",
        "state",
        "effective_from",
        "effective_to",
        "published_at",
    )
    list_filter = ("state", "procedure", "effective_from", "effective_to")
    search_fields = (
        "semantic_id",
        "procedure__semantic_id",
        "text_ar",
        "text_en",
    )
    autocomplete_fields = ("procedure",)
    ordering = ("procedure__semantic_id", "effective_from", "semantic_id")
    actions = ("publish_selected", "withdraw_selected")
    lifecycle_fields = (
        "state",
        "published_at",
        "published_by",
        "withdrawn_at",
        "withdrawn_by",
    )

    def get_readonly_fields(
        self, request: HttpRequest, obj: ProcedureVersion | None = None
    ) -> tuple[str, ...]:
        if obj is not None and obj.state != ProcedureVersion.State.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return self.lifecycle_fields

    def has_delete_permission(
        self, request: HttpRequest, obj: ProcedureVersion | None = None
    ) -> bool:
        if obj is not None and obj.state != ProcedureVersion.State.DRAFT:
            return False
        return super().has_delete_permission(request, obj)

    def has_publish_procedureversion_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm("knowledge.publish_procedureversion")

    def has_withdraw_procedureversion_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm("knowledge.withdraw_procedureversion")

    def _report_rejection(self, request: HttpRequest, exc: PublicationRejected) -> None:
        rendered = "; ".join(
            f"{item.gate}: {item.code}" + (f" ({item.detail})" if item.detail else "")
            for item in exc.diagnostics
        )
        self.message_user(request, rendered, level=messages.ERROR)

    @admin.action(description="Publish selected drafts", permissions=["publish_procedureversion"])
    def publish_selected(
        self, request: HttpRequest, queryset: models.QuerySet[ProcedureVersion]
    ) -> None:
        for version_id in queryset.order_by("semantic_id").values_list("pk", flat=True):
            try:
                publish_procedure_version(version_id, actor=cast(models.Model, request.user))
            except PublicationRejected as exc:
                self._report_rejection(request, exc)

    @admin.action(
        description="Withdraw selected published versions",
        permissions=["withdraw_procedureversion"],
    )
    def withdraw_selected(
        self, request: HttpRequest, queryset: models.QuerySet[ProcedureVersion]
    ) -> None:
        for version_id in queryset.order_by("semantic_id").values_list("pk", flat=True):
            try:
                withdraw_procedure_version(version_id, actor=cast(models.Model, request.user))
            except PublicationRejected as exc:
                self._report_rejection(request, exc)


@admin.register(ProcedureVersionAuditEvent)
class ProcedureVersionAuditEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("version", "event_type", "actor", "occurred_at", "from_state", "to_state")
    list_filter = ("event_type", "actor", "occurred_at", "version")
    search_fields = ("version__semantic_id", "actor__username")
    readonly_fields = (
        "version",
        "event_type",
        "actor",
        "occurred_at",
        "from_state",
        "to_state",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: ProcedureVersionAuditEvent | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: ProcedureVersionAuditEvent | None = None
    ) -> bool:
        return False


@admin.register(ServiceProcedureCandidate)
class CandidateAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = CandidateForm
    list_display = ("service", "procedure")
    list_filter = ("service",)
    search_fields = ("service__semantic_id", "procedure__semantic_id")
    autocomplete_fields = ("service", "procedure")
    formfield_overrides = {models.JSONField: {"widget": Textarea(attrs={"rows": 8, "cols": 80})}}


@admin.register(FactDefinition)
class FactDefinitionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = FactDefinitionForm
    list_display = ("key", "kind", "derived", "is_published")
    list_filter = ("kind", "derived", "is_published")
    search_fields = ("key",)
    ordering = ("key",)
    readonly_fields = ("is_published",)

    def get_readonly_fields(
        self, request: HttpRequest, obj: FactDefinition | None = None
    ) -> tuple[str, ...]:
        base = ("is_published",)
        if obj is not None and obj.is_published:
            return ("key", "kind", "enum_values", "minimum", "derived", "is_published")
        return base

    def has_delete_permission(
        self, request: HttpRequest, obj: FactDefinition | None = None
    ) -> bool:
        if obj is not None and obj.is_published:
            return False
        return super().has_delete_permission(request, obj)


class ResolvedFactInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ServiceQuestionResolvedFact
    formset = QuestionResolvedFactFormSet
    extra = 1
    autocomplete_fields = ("fact",)


@admin.register(ServiceQuestion)
class QuestionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = QuestionForm
    list_display = ("semantic_id", "service", "fact", "priority")
    list_filter = ("service",)
    search_fields = ("semantic_id", "service__semantic_id", "fact__key")
    autocomplete_fields = ("service", "fact")
    ordering = ("service_id", "priority", "semantic_id")
    inlines = (ResolvedFactInline,)

    def save_formset(
        self,
        request: HttpRequest,
        form: ModelForm[Any],
        formset: BaseInlineFormSet[Any, Any, ModelForm[Any]],
        change: bool,
    ) -> None:
        if formset.model is ServiceQuestionResolvedFact:
            set_question_resolved_facts(
                cast(ServiceQuestion, form.instance), _ordered_formset_facts(formset)
            )
            return
        super().save_formset(request, form, formset, change)


class ContradictionFactInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ServiceContradictionFact
    formset = ContradictionFactFormSet
    extra = 2
    autocomplete_fields = ("fact",)


@admin.register(ServiceContradiction)
class ContradictionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = ContradictionForm
    list_display = ("semantic_id", "service", "ordered_fact_keys")
    list_filter = ("service",)
    search_fields = ("semantic_id", "service__semantic_id", "fact_links__fact__key")
    autocomplete_fields = ("service",)
    ordering = ("service_id", "semantic_id")
    inlines = (ContradictionFactInline,)
    formfield_overrides = {models.JSONField: {"widget": Textarea(attrs={"rows": 8, "cols": 80})}}

    def save_formset(
        self,
        request: HttpRequest,
        form: ModelForm[Any],
        formset: BaseInlineFormSet[Any, Any, ModelForm[Any]],
        change: bool,
    ) -> None:
        if formset.model is ServiceContradictionFact:
            set_contradiction_facts(
                cast(ServiceContradiction, form.instance), _ordered_formset_facts(formset)
            )
            return
        super().save_formset(request, form, formset, change)

    @admin.display(description="Facts")
    def ordered_fact_keys(self, obj: ServiceContradiction) -> str:
        return ", ".join(obj.fact_keys)
