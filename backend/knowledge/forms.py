"""Catalog Admin forms which turn domain failures into form errors."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .domain import decode_stored_rule, diagnostic_messages, referenced_fact_keys
from .models import (
    ChecklistItem,
    EvidenceLink,
    FactDefinition,
    ServiceContradiction,
    ServiceProcedureCandidate,
    ServiceQuestion,
)


class ValidatingModelForm(forms.ModelForm):  # type: ignore[type-arg]
    """Django's ModelForm post-clean calls the catalog model's full_clean()."""


class CandidateForm(ValidatingModelForm):
    class Meta:
        model = ServiceProcedureCandidate
        fields = "__all__"


class QuestionForm(ValidatingModelForm):
    class Meta:
        model = ServiceQuestion
        fields = "__all__"


class ContradictionForm(ValidatingModelForm):
    class Meta:
        model = ServiceContradiction
        fields = "__all__"


class FactDefinitionForm(ValidatingModelForm):
    class Meta:
        model = FactDefinition
        fields = "__all__"


class ChecklistItemForm(ValidatingModelForm):
    class Meta:
        model = ChecklistItem
        fields = "__all__"

    def clean_applicability(self) -> object:
        value = self.cleaned_data["applicability"]
        if value == {}:
            return value
        result = decode_stored_rule(value)
        if result.diagnostics:
            raise ValidationError(diagnostic_messages(result))
        return value


class EvidenceLinkForm(ValidatingModelForm):
    class Meta:
        model = EvidenceLink
        exclude = ("sources",)


class QuestionResolvedFactFormSet(BaseInlineFormSet):  # type: ignore[type-arg]
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return
        facts = [
            form.cleaned_data["fact"]
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if len({fact.pk for fact in facts}) != len(facts):
            raise ValidationError("Resolved Facts cannot be duplicated.")
        if any(fact.derived for fact in facts):
            raise ValidationError("Questions may resolve source Facts only.")
        if facts and self.instance.fact_id not in {fact.pk for fact in facts}:
            raise ValidationError("Explicit resolved Facts must include the primary Fact.")


class ContradictionFactFormSet(BaseInlineFormSet):  # type: ignore[type-arg]
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return
        facts = [
            form.cleaned_data["fact"]
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if len(facts) < 2 or len({fact.pk for fact in facts}) != len(facts):
            raise ValidationError("A contradiction requires at least two distinct Facts.")
        if any(fact.derived for fact in facts):
            raise ValidationError("Contradictions may declare source Facts only.")
        result = decode_stored_rule(self.instance.condition)
        if result.diagnostics:
            raise ValidationError(diagnostic_messages(result))
        assert result.predicate is not None
        if {fact.key for fact in facts} != set(referenced_fact_keys(result.predicate)):
            raise ValidationError("Declared Facts must exactly match condition references.")
