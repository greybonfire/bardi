from __future__ import annotations

from typing import Any

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
    Goal,
    GoalContradiction,
    GoalContradictionFact,
    GoalProcedureCandidate,
    GoalQuestion,
    GoalQuestionResolvedFact,
    Procedure,
)


class CandidateInline(admin.TabularInline):  # type: ignore[type-arg]
    model = GoalProcedureCandidate
    form = CandidateForm
    extra = 0
    autocomplete_fields = ("procedure",)

    def get_formset(
        self, request: HttpRequest, obj: Goal | None = None, **kwargs: object
    ) -> type[BaseInlineFormSet[Any, Any, ModelForm[Any]]]:
        formset = super().get_formset(request, obj, **kwargs)
        procedure_field = formset.form.base_fields.get("procedure")
        if procedure_field is not None and hasattr(procedure_field, "queryset"):
            procedure_field.queryset = Procedure.objects.filter(primary_goal=obj)
        return formset


class QuestionOwnerInline(admin.TabularInline):  # type: ignore[type-arg]
    model = GoalQuestion
    form = QuestionForm
    extra = 0
    autocomplete_fields = ("fact",)
    fields = ("semantic_id", "fact", "priority", "text_ar", "text_en")


class ContradictionOwnerInline(admin.TabularInline):  # type: ignore[type-arg]
    model = GoalContradiction
    extra = 0
    fields = ("semantic_id", "condition")
    readonly_fields = ("semantic_id", "condition")
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: Goal | None = None) -> bool:
        return False


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("semantic_id", "text_en")
    search_fields = ("semantic_id", "text_en", "text_ar")
    ordering = ("semantic_id",)
    inlines = (CandidateInline, QuestionOwnerInline, ContradictionOwnerInline)


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("semantic_id", "primary_goal", "text_en")
    list_filter = ("primary_goal",)
    search_fields = ("semantic_id", "primary_goal__semantic_id", "text_en", "text_ar")
    autocomplete_fields = ("primary_goal",)
    ordering = ("semantic_id",)


@admin.register(GoalProcedureCandidate)
class CandidateAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = CandidateForm
    list_display = ("goal", "procedure")
    list_filter = ("goal",)
    search_fields = ("goal__semantic_id", "procedure__semantic_id")
    autocomplete_fields = ("goal", "procedure")
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
    model = GoalQuestionResolvedFact
    formset = QuestionResolvedFactFormSet
    extra = 1
    autocomplete_fields = ("fact",)


@admin.register(GoalQuestion)
class QuestionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = QuestionForm
    list_display = ("semantic_id", "goal", "fact", "priority")
    list_filter = ("goal",)
    search_fields = ("semantic_id", "goal__semantic_id", "fact__key")
    autocomplete_fields = ("goal", "fact")
    ordering = ("goal_id", "priority", "semantic_id")
    inlines = (ResolvedFactInline,)


class ContradictionFactInline(admin.TabularInline):  # type: ignore[type-arg]
    model = GoalContradictionFact
    formset = ContradictionFactFormSet
    extra = 2
    autocomplete_fields = ("fact",)


@admin.register(GoalContradiction)
class ContradictionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = ContradictionForm
    list_display = ("semantic_id", "goal", "ordered_fact_keys")
    list_filter = ("goal",)
    search_fields = ("semantic_id", "goal__semantic_id", "fact_links__fact__key")
    autocomplete_fields = ("goal",)
    ordering = ("goal_id", "semantic_id")
    inlines = (ContradictionFactInline,)
    formfield_overrides = {models.JSONField: {"widget": Textarea(attrs={"rows": 8, "cols": 80})}}

    @admin.display(description="Facts")
    def ordered_fact_keys(self, obj: GoalContradiction) -> str:
        return ", ".join(obj.fact_keys)
