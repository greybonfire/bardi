from __future__ import annotations

from typing import Any, cast

from django.contrib import admin
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
    Service,
    ServiceContradiction,
    ServiceContradictionFact,
    ServiceProcedureCandidate,
    ServiceQuestion,
    ServiceQuestionResolvedFact,
    Procedure,
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
    list_display = ("semantic_id", "text_en")
    search_fields = ("semantic_id", "text_en", "text_ar")
    ordering = ("semantic_id",)
    inlines = (CandidateInline, QuestionOwnerInline, ContradictionOwnerInline)


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("semantic_id", "primary_service", "text_en")
    list_filter = ("primary_service",)
    search_fields = ("semantic_id", "primary_service__semantic_id", "text_en", "text_ar")
    autocomplete_fields = ("primary_service",)
    ordering = ("semantic_id",)


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
