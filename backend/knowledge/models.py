from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.lookups import Exact

NONBLANK_PATTERN = r".*[^[:space:]].*"


def _required(value: str, field: str) -> None:
    if not value or not value.strip():
        raise ValidationError({field: "This field must contain non-whitespace text."})


class Goal(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    text_ar = models.TextField()
    text_en = models.TextField()

    class Meta:
        ordering = ("semantic_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="goal_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="goal_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="goal_en_nonblank"
            ),
        ]

    def clean(self) -> None:
        _required(self.semantic_id, "semantic_id")
        _required(self.text_ar, "text_ar")
        _required(self.text_en, "text_en")

    def __str__(self) -> str:
        return self.semantic_id


class Procedure(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    text_ar = models.TextField()
    text_en = models.TextField()
    primary_goal = models.ForeignKey(
        Goal, on_delete=models.PROTECT, related_name="primary_procedures"
    )

    class Meta:
        ordering = ("semantic_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="procedure_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="procedure_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="procedure_en_nonblank"
            ),
        ]

    def clean(self) -> None:
        _required(self.semantic_id, "semantic_id")
        _required(self.text_ar, "text_ar")
        _required(self.text_en, "text_en")
        if self.pk and self.primary_goal_id:
            incompatible = self.goal_candidates.exclude(goal_id=self.primary_goal_id).exists()
            if incompatible:
                raise ValidationError(
                    {"primary_goal": "Existing candidates belong to a different Goal."}
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.semantic_id


class FactDefinition(models.Model):
    class Kind(models.TextChoices):
        BOOLEAN = "boolean", "Boolean"
        ENUM = "enum", "Enum"
        INTEGER = "integer", "Integer"
        DATE = "date", "Date"
        STRING = "string", "String"

    key = models.CharField(max_length=128, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    enum_values = models.JSONField(default=list, blank=True)
    minimum = models.IntegerField(null=True, blank=True)
    derived = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ("key",)
        constraints = [
            models.CheckConstraint(
                condition=Q(key__regex=NONBLANK_PATTERN), name="fact_key_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["boolean", "enum", "integer", "date", "string"]),
                name="fact_kind_supported",
            ),
            models.CheckConstraint(
                condition=Q(minimum__isnull=True) | Q(minimum__gte=0),
                name="fact_minimum_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(kind="integer") | Q(minimum__isnull=True),
                name="fact_minimum_integer_only",
            ),
            models.CheckConstraint(
                condition=Exact(
                    models.Func(
                        models.F("enum_values"),
                        function="jsonb_typeof",
                        output_field=models.CharField(),
                    ),
                    models.Value("array"),
                ),
                name="fact_enum_values_array",
            ),
            models.CheckConstraint(
                condition=(Q(kind="enum") & ~Q(enum_values=[]))
                | (~Q(kind="enum") & Q(enum_values=[])),
                name="fact_enum_vocabulary",
            ),
        ]

    def clean(self) -> None:
        _required(self.key, "key")
        errors: dict[str, str] = {}
        if type(self.enum_values) is not list:
            errors["enum_values"] = "Enum values must be a JSON array."
        else:
            valid = all(type(value) is str and bool(value.strip()) for value in self.enum_values)
            unique = len(set(self.enum_values)) == len(self.enum_values) if valid else False
            if not valid or not unique:
                errors["enum_values"] = "Enum values must be unique, nonblank strings."
            elif self.kind == self.Kind.ENUM and not self.enum_values:
                errors["enum_values"] = "Enum Facts require at least one value."
            elif self.kind != self.Kind.ENUM and self.enum_values:
                errors["enum_values"] = "Only enum Facts may define enum values."
        if self.minimum is not None:
            if self.kind != self.Kind.INTEGER:
                errors["minimum"] = "Minimum is allowed only for integer Facts."
            elif self.minimum < 0:
                errors["minimum"] = "Minimum must be nonnegative."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        stored = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if stored is not None and stored.is_published:
            protected = ("key", "kind", "enum_values", "minimum", "derived")
            changed = [
                field for field in protected if getattr(self, field) != getattr(stored, field)
            ]
            if changed or not self.is_published:
                raise ValidationError("Published Fact definitions are immutable.")
        self.full_clean()
        if self.is_published:
            from planning.facts import FACT_DEFINITIONS

            from .domain import compatibility_errors

            if self.key in FACT_DEFINITIONS and compatibility_errors([self]):
                raise ValidationError("Fact definition is incompatible with the planning registry.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        stored = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if stored is not None and stored.is_published:
            raise ValidationError("Published Fact definitions cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return self.key


class GoalProcedureCandidate(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="procedure_candidates")
    procedure = models.ForeignKey(
        Procedure, on_delete=models.CASCADE, related_name="goal_candidates"
    )
    selection_predicate = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("goal", "procedure"), name="unique_goal_procedure_candidate"
            )
        ]
        indexes = [models.Index(fields=("goal", "procedure"), name="candidate_goal_proc_idx")]

    def clean(self) -> None:
        if self.goal_id and self.procedure_id and self.goal_id != self.procedure.primary_goal_id:
            raise ValidationError(
                {"procedure": "Procedure primary Goal must match the candidate Goal."}
            )
        from .domain import decode_stored_rule, diagnostic_messages

        result = decode_stored_rule(self.selection_predicate)
        if result.diagnostics:
            raise ValidationError({"selection_predicate": diagnostic_messages(result)})

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.goal.semantic_id}:{self.procedure.semantic_id}"


class GoalQuestion(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="questions")
    fact = models.ForeignKey(
        FactDefinition, on_delete=models.PROTECT, related_name="primary_questions"
    )
    text_ar = models.TextField()
    text_en = models.TextField()
    priority = models.PositiveIntegerField()
    resolves_facts: models.ManyToManyField[FactDefinition, GoalQuestionResolvedFact] = (
        models.ManyToManyField(
            FactDefinition,
            through="GoalQuestionResolvedFact",
            related_name="resolving_questions",
        )
    )

    class Meta:
        ordering = ("goal_id", "priority", "semantic_id")
        indexes = [
            models.Index(fields=("goal", "priority", "semantic_id"), name="question_order_idx")
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="question_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="question_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="question_en_nonblank"
            ),
        ]

    def clean(self) -> None:
        _required(self.semantic_id, "semantic_id")
        _required(self.text_ar, "text_ar")
        _required(self.text_en, "text_en")
        if self.fact_id and self.fact.derived:
            raise ValidationError({"fact": "The primary Fact must be a source Fact."})
        if self.pk:
            rows = list(
                self.resolved_fact_links.select_related("fact").order_by("position", "fact__key")
            )
            if any(row.fact.derived for row in rows):
                raise ValidationError("Questions may resolve source Facts only.")
            if rows and self.fact_id not in {row.fact_id for row in rows}:
                raise ValidationError("Explicit resolved Facts must include the primary Fact.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def resolved_fact_keys(self) -> tuple[str, ...]:
        rows = tuple(
            self.resolved_fact_links.select_related("fact").order_by("position", "fact__key")
        )
        return tuple(row.fact.key for row in rows) if rows else (self.fact.key,)

    def __str__(self) -> str:
        return self.semantic_id


class GoalQuestionResolvedFact(models.Model):
    question = models.ForeignKey(
        GoalQuestion, on_delete=models.CASCADE, related_name="resolved_fact_links"
    )
    fact = models.ForeignKey(
        FactDefinition, on_delete=models.PROTECT, related_name="question_resolution_links"
    )
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ("position", "fact__key")
        constraints = [
            models.UniqueConstraint(
                fields=("question", "fact"), name="unique_question_resolved_fact"
            ),
            models.UniqueConstraint(
                fields=("question", "position"), name="unique_question_resolved_position"
            ),
        ]

    def clean(self) -> None:
        if self.fact_id and self.fact.derived:
            raise ValidationError({"fact": "Questions may resolve source Facts only."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class GoalContradiction(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="contradictions")
    condition = models.JSONField()
    facts: models.ManyToManyField[FactDefinition, GoalContradictionFact] = models.ManyToManyField(
        FactDefinition, through="GoalContradictionFact", related_name="contradictions"
    )

    class Meta:
        ordering = ("goal_id", "semantic_id")
        indexes = [models.Index(fields=("goal", "semantic_id"), name="contradiction_order_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="contradiction_id_nonblank"
            )
        ]

    def clean(self) -> None:
        _required(self.semantic_id, "semantic_id")
        from .domain import decode_stored_rule, diagnostic_messages, referenced_fact_keys

        result = decode_stored_rule(self.condition)
        if result.diagnostics:
            raise ValidationError({"condition": diagnostic_messages(result)})
        if self.pk:
            rows = list(self.fact_links.select_related("fact"))
            if len(rows) < 2:
                raise ValidationError("A contradiction requires at least two declared Facts.")
            if any(row.fact.derived for row in rows):
                raise ValidationError("Contradictions may declare source Facts only.")
            assert result.predicate is not None
            declared = {row.fact.key for row in rows}
            if declared != set(referenced_fact_keys(result.predicate)):
                raise ValidationError("Declared Facts must exactly match condition references.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def fact_keys(self) -> tuple[str, ...]:
        return tuple(
            row.fact.key
            for row in self.fact_links.select_related("fact").order_by("position", "fact__key")
        )

    def __str__(self) -> str:
        return self.semantic_id


class GoalContradictionFact(models.Model):
    contradiction = models.ForeignKey(
        GoalContradiction, on_delete=models.CASCADE, related_name="fact_links"
    )
    fact = models.ForeignKey(
        FactDefinition, on_delete=models.PROTECT, related_name="contradiction_links"
    )
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ("position", "fact__key")
        constraints = [
            models.UniqueConstraint(
                fields=("contradiction", "fact"), name="unique_contradiction_fact"
            ),
            models.UniqueConstraint(
                fields=("contradiction", "position"), name="unique_contradiction_position"
            ),
        ]
