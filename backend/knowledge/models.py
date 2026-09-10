from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q, Value
from django.db.models.lookups import Exact
from planning.trust import VERIFICATION_CHOICES

NONBLANK_PATTERN = r".*[^[:space:]].*"


def _required(value: str, field: str) -> None:
    if not value or not value.strip():
        raise ValidationError({field: "This field must contain non-whitespace text."})


class Service(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    text_ar = models.TextField()
    text_en = models.TextField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ("semantic_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="service_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="service_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="service_en_nonblank"
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
    primary_service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="primary_procedures"
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
        if self.pk and self.primary_service_id:
            incompatible = self.service_candidates.exclude(
                service_id=self.primary_service_id
            ).exists()
            if incompatible:
                raise ValidationError(
                    {"primary_service": "Existing candidates belong to a different Service."}
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.semantic_id


class ProcedureVersion(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        WITHDRAWN = "withdrawn", "Withdrawn"

    semantic_id = models.CharField(max_length=128, unique=True)
    procedure = models.ForeignKey(Procedure, on_delete=models.PROTECT, related_name="versions")
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    text_ar = models.TextField(blank=True)
    text_en = models.TextField(blank=True)
    applicability = models.JSONField(default=dict, blank=True)
    rules_contract_version = models.CharField(max_length=16, default="v1")
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.PROTECT,
        related_name="published_procedure_versions",
    )
    withdrawn_at = models.DateTimeField(null=True, blank=True, editable=False)
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.PROTECT,
        related_name="withdrawn_procedure_versions",
    )

    class Meta:
        ordering = ("procedure__semantic_id", "effective_from", "semantic_id")
        permissions = [
            ("publish_procedureversion", "Can publish Procedure Version"),
            ("withdraw_procedureversion", "Can withdraw Procedure Version"),
        ]
        indexes = [
            models.Index(fields=("procedure", "state"), name="proc_version_state_idx"),
            models.Index(fields=("state", "effective_from"), name="proc_version_effective_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="proc_version_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(state__in=["draft", "published", "withdrawn"]),
                name="proc_version_state_supported",
            ),
            models.CheckConstraint(
                condition=Q(rules_contract_version="v1"), name="proc_version_contract_supported"
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="proc_version_dates_ordered",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        state="draft",
                        published_at__isnull=True,
                        published_by__isnull=True,
                        withdrawn_at__isnull=True,
                        withdrawn_by__isnull=True,
                    )
                    | Q(
                        state="published",
                        published_at__isnull=False,
                        published_by__isnull=False,
                        withdrawn_at__isnull=True,
                        withdrawn_by__isnull=True,
                    )
                    | Q(
                        state="withdrawn",
                        published_at__isnull=False,
                        published_by__isnull=False,
                        withdrawn_at__isnull=False,
                        withdrawn_by__isnull=False,
                    )
                ),
                name="proc_version_lifecycle_metadata",
            ),
            ExclusionConstraint(
                name="exclude_published_proc_version_overlap",
                expressions=(
                    ("procedure", RangeOperators.EQUAL),
                    (
                        models.Func(
                            F("effective_from"),
                            F("effective_to"),
                            Value("[]"),
                            function="DATERANGE",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ),
                condition=Q(state="published"),
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        stored = type(self).objects.filter(pk=self.pk).only("state").first() if self.pk else None
        if stored is None:
            if self.state != self.State.DRAFT or any(
                value is not None
                for value in (
                    self.published_at,
                    self.published_by_id,
                    self.withdrawn_at,
                    self.withdrawn_by_id,
                )
            ):
                raise ValidationError("Procedure Versions may only be created as drafts.")
        elif stored.state != self.State.DRAFT:
            raise ValidationError("Published and withdrawn Procedure Versions are immutable.")
        elif self.state != self.State.DRAFT:
            raise ValidationError("Use the canonical lifecycle service to publish a draft.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        state = type(self).objects.filter(pk=self.pk).values_list("state", flat=True).first()
        if state in {self.State.PUBLISHED, self.State.WITHDRAWN}:
            raise ValidationError("Published and withdrawn Procedure Versions cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return self.semantic_id


class ProcedureVersionAuditEvent(models.Model):
    class EventType(models.TextChoices):
        PUBLISHED = "published", "Published"
        WITHDRAWN = "withdrawn", "Withdrawn"

    version = models.ForeignKey(
        ProcedureVersion, on_delete=models.PROTECT, related_name="audit_events"
    )
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="procedure_version_audit_events",
    )
    occurred_at = models.DateTimeField()
    from_state = models.CharField(max_length=16, choices=ProcedureVersion.State.choices)
    to_state = models.CharField(max_length=16, choices=ProcedureVersion.State.choices)

    class Meta:
        ordering = ("occurred_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("version",),
                condition=Q(event_type="published"),
                name="one_publication_event_per_version",
            ),
            models.CheckConstraint(
                condition=(
                    Q(event_type="published", from_state="draft", to_state="published")
                    | Q(event_type="withdrawn", from_state="published", to_state="withdrawn")
                ),
                name="proc_version_audit_transition",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        raise ValidationError("Audit events may only be created by the lifecycle service.")

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Procedure Version audit events are immutable.")


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
        if self.derived:
            from planning.case_preparation import derived_definition_is_compatible
            from planning.facts import FactDefinition as DomainFactDefinition

            definition = DomainFactDefinition(
                self.key,
                self.kind,  # type: ignore[arg-type]
                tuple(self.enum_values) if type(self.enum_values) is list else (),
                self.minimum,
                True,
            )
            if not derived_definition_is_compatible(definition):
                errors["derived"] = "Derived Facts must exactly match a pinned implementation."
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


class ServiceProcedureCandidate(models.Model):
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name="procedure_candidates"
    )
    procedure = models.ForeignKey(
        Procedure, on_delete=models.CASCADE, related_name="service_candidates"
    )
    selection_predicate = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("service", "procedure"), name="unique_service_procedure_candidate"
            )
        ]
        indexes = [models.Index(fields=("service", "procedure"), name="candidate_service_proc_idx")]

    def clean(self) -> None:
        if (
            self.service_id
            and self.procedure_id
            and self.service_id != self.procedure.primary_service_id
        ):
            raise ValidationError(
                {"procedure": "Procedure primary Service must match the candidate Service."}
            )
        from .domain import decode_stored_rule, diagnostic_messages

        result = decode_stored_rule(self.selection_predicate)
        if result.diagnostics:
            raise ValidationError({"selection_predicate": diagnostic_messages(result)})

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.service.semantic_id}:{self.procedure.semantic_id}"


class ServiceQuestion(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="questions")
    fact = models.ForeignKey(
        FactDefinition, on_delete=models.PROTECT, related_name="primary_questions"
    )
    text_ar = models.TextField()
    text_en = models.TextField()
    priority = models.PositiveIntegerField()
    resolves_facts: models.ManyToManyField[FactDefinition, ServiceQuestionResolvedFact] = (
        models.ManyToManyField(
            FactDefinition,
            through="ServiceQuestionResolvedFact",
            related_name="resolving_questions",
        )
    )

    class Meta:
        ordering = ("service_id", "priority", "semantic_id")
        indexes = [
            models.Index(fields=("service", "priority", "semantic_id"), name="question_order_idx")
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


class ServiceQuestionResolvedFact(models.Model):
    question = models.ForeignKey(
        ServiceQuestion, on_delete=models.CASCADE, related_name="resolved_fact_links"
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


class ServiceContradiction(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="contradictions")
    condition = models.JSONField()
    facts: models.ManyToManyField[FactDefinition, ServiceContradictionFact] = (
        models.ManyToManyField(
            FactDefinition, through="ServiceContradictionFact", related_name="contradictions"
        )
    )

    class Meta:
        ordering = ("service_id", "semantic_id")
        indexes = [models.Index(fields=("service", "semantic_id"), name="contradiction_order_idx")]
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


class ServiceContradictionFact(models.Model):
    contradiction = models.ForeignKey(
        ServiceContradiction, on_delete=models.CASCADE, related_name="fact_links"
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


class Authority(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    name_ar = models.TextField()
    name_en = models.TextField()

    class Meta:
        ordering = ("semantic_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="authority_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(name_ar__regex=NONBLANK_PATTERN), name="authority_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(name_en__regex=NONBLANK_PATTERN), name="authority_en_nonblank"
            ),
        ]

    def clean(self) -> None:
        for field in ("semantic_id", "name_ar", "name_en"):
            _required(getattr(self, field), field)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            self.pk
            and Source.objects.filter(authority_id=self.pk)
            .filter(
                Q(
                    evidence_source_links__evidence_link__checklist_item__procedure_version__state__in=(
                        "published",
                        "withdrawn",
                    )
                )
                | Q(
                    evidence_source_links__evidence_link__step__procedure_version__state__in=(
                        "published",
                        "withdrawn",
                    )
                )
                | Q(
                    evidence_source_links__evidence_link__warning__procedure_version__state__in=(
                        "published",
                        "withdrawn",
                    )
                )
            )
            .exists()
        ):
            old = type(self).objects.get(pk=self.pk)
            if (old.semantic_id, old.name_ar, old.name_en) != (
                self.semantic_id,
                self.name_ar,
                self.name_en,
            ):
                raise ValidationError("Authorities used by published evidence are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if (
            Source.objects.filter(authority_id=self.pk)
            .filter(
                Q(
                    evidence_source_links__evidence_link__checklist_item__procedure_version__state__in=(
                        "published",
                        "withdrawn",
                    )
                )
                | Q(
                    evidence_source_links__evidence_link__step__procedure_version__state__in=(
                        "published",
                        "withdrawn",
                    )
                )
                | Q(
                    evidence_source_links__evidence_link__warning__procedure_version__state__in=(
                        "published",
                        "withdrawn",
                    )
                )
            )
            .exists()
        ):
            raise ValidationError("Authorities used by published evidence cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return self.semantic_id


class DocumentType(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    name_ar = models.TextField()
    name_en = models.TextField()

    class Meta:
        ordering = ("semantic_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="document_type_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(name_ar__regex=NONBLANK_PATTERN), name="document_type_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(name_en__regex=NONBLANK_PATTERN), name="document_type_en_nonblank"
            ),
        ]

    def clean(self) -> None:
        for field in ("semantic_id", "name_ar", "name_en"):
            _required(getattr(self, field), field)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            self.pk
            and ChecklistItem.objects.filter(
                document_type_id=self.pk, procedure_version__state__in=("published", "withdrawn")
            ).exists()
        ):
            old = type(self).objects.get(pk=self.pk)
            if (old.semantic_id, old.name_ar, old.name_en) != (
                self.semantic_id,
                self.name_ar,
                self.name_en,
            ):
                raise ValidationError("Document Types used by published claims are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if ChecklistItem.objects.filter(
            document_type_id=self.pk, procedure_version__state__in=("published", "withdrawn")
        ).exists():
            raise ValidationError("Document Types used by published claims cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return self.semantic_id


class Source(models.Model):
    class Classification(models.TextChoices):
        OFFICIAL = "official", "Official"
        FIELD_REPORT = "field_report", "Field report"
        SECONDARY = "secondary", "Secondary"

    semantic_id = models.CharField(max_length=128, unique=True)
    authority = models.ForeignKey(Authority, on_delete=models.PROTECT, related_name="sources")
    title = models.TextField()
    locator = models.TextField()
    classification = models.CharField(max_length=16, choices=Classification.choices)
    published_on = models.DateField(null=True, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    retrieved_on = models.DateField()
    reverify_on = models.DateField(null=True, blank=True)
    observation_date = models.DateField(null=True, blank=True)
    observation_context = models.TextField(blank=True)

    class Meta:
        ordering = ("semantic_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="source_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(title__regex=NONBLANK_PATTERN), name="source_title_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(locator__regex=NONBLANK_PATTERN), name="source_locator_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(classification__in=["official", "field_report", "secondary"]),
                name="source_class_supported",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="source_dates_ordered",
            ),
        ]

    def clean(self) -> None:
        for field in ("semantic_id", "title", "locator"):
            _required(getattr(self, field), field)
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            self.pk
            and self.evidence_source_links.filter(
                Q(
                    evidence_link__checklist_item__procedure_version__state__in=(
                        "published",
                        "withdrawn",
                    )
                )
                | Q(evidence_link__step__procedure_version__state__in=("published", "withdrawn"))
                | Q(evidence_link__warning__procedure_version__state__in=("published", "withdrawn"))
            ).exists()
        ):
            old = type(self).objects.get(pk=self.pk)
            protected = tuple(f.name for f in self._meta.fields if f.name != "id")
            if any(getattr(old, f) != getattr(self, f) for f in protected):
                raise ValidationError("Sources used by published evidence are preserved.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if self.evidence_source_links.filter(
            Q(
                evidence_link__checklist_item__procedure_version__state__in=(
                    "published",
                    "withdrawn",
                )
            )
            | Q(evidence_link__step__procedure_version__state__in=("published", "withdrawn"))
            | Q(evidence_link__warning__procedure_version__state__in=("published", "withdrawn"))
        ).exists():
            raise ValidationError("Sources used by published evidence cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return self.semantic_id


class VersionOwnedModel(models.Model):
    class Meta:
        abstract = True

    def owning_version(self) -> ProcedureVersion:
        raise NotImplementedError

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.owning_version().state != ProcedureVersion.State.DRAFT:
            raise ValidationError(
                "Published and withdrawn Procedure Version children are immutable."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if self.owning_version().state != ProcedureVersion.State.DRAFT:
            raise ValidationError(
                "Published and withdrawn Procedure Version children are immutable."
            )
        return super().delete(*args, **kwargs)


class ChecklistItem(VersionOwnedModel):
    class Classification(models.TextChoices):
        OFFICIAL_REQUIREMENT = "official_requirement", "Official requirement"
        PRACTICAL_PREPARATION = "practical_preparation", "Practical preparation"
        CANDIDATE = "candidate", "Research candidate"

    class Scope(models.TextChoices):
        PROCEDURE = "procedure", "Entire procedure"
        ELIGIBILITY_BASIS = "eligibility_basis", "Eligibility basis"

    procedure_version = models.ForeignKey(
        ProcedureVersion, on_delete=models.CASCADE, related_name="checklist_items"
    )
    semantic_id = models.CharField(max_length=128)
    text_ar = models.TextField()
    text_en = models.TextField()
    classification = models.CharField(max_length=32, choices=Classification.choices)
    document_type = models.ForeignKey(
        DocumentType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="checklist_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    original_quantity = models.PositiveIntegerField(default=0)
    copy_quantity = models.PositiveIntegerField(default=0)
    display_order = models.PositiveIntegerField(default=0)
    applicability = models.JSONField(default=dict, blank=True)
    scope = models.CharField(max_length=24, choices=Scope.choices, default=Scope.PROCEDURE)
    scope_reference = models.CharField(max_length=128, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )

    class Meta:
        ordering = ("procedure_version_id", "display_order", "semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "semantic_id"), name="unique_checklist_id_per_version"
            ),
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="checklist_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="checklist_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="checklist_en_nonblank"
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="checklist_quantity_positive"),
            models.CheckConstraint(
                condition=Q(
                    classification__in=[
                        "official_requirement",
                        "practical_preparation",
                        "candidate",
                    ]
                ),
                name="checklist_class_supported",
            ),
            models.CheckConstraint(
                condition=Q(scope__in=["procedure", "eligibility_basis"]),
                name="checklist_scope_supported",
            ),
            models.CheckConstraint(
                condition=Q(
                    verification_state__in=[
                        "current",
                        "needs_reverification",
                        "stale",
                        "disputed",
                        "unknown",
                    ]
                ),
                name="checklist_verification_supported",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="checklist_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(scope="procedure", scope_reference="")
                | Q(scope="eligibility_basis", scope_reference__regex=NONBLANK_PATTERN),
                name="checklist_scope_combination",
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.procedure_version

    def clean(self) -> None:
        for field in ("semantic_id", "text_ar", "text_en"):
            _required(getattr(self, field), field)
        if self.quantity < 1:
            raise ValidationError({"quantity": "Quantity must be positive."})
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if self.scope == self.Scope.PROCEDURE and self.scope_reference:
            raise ValidationError({"scope_reference": "Procedure scope cannot have a reference."})
        if self.scope == self.Scope.ELIGIBILITY_BASIS and not self.scope_reference.strip():
            raise ValidationError(
                {"scope_reference": "Eligibility Basis scope requires a stable reference."}
            )

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.semantic_id}"


class EligibilityBasis(VersionOwnedModel):
    procedure_version = models.ForeignKey(
        ProcedureVersion, on_delete=models.CASCADE, related_name="eligibility_bases"
    )
    semantic_id = models.CharField(max_length=128)
    text_ar = models.TextField(default="")
    text_en = models.TextField(default="")
    reachability = models.JSONField(default=dict, blank=True)
    qualification = models.JSONField(default=dict, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )

    class Meta:
        ordering = ("procedure_version_id", "display_order", "semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "semantic_id"), name="unique_basis_id_per_version"
            ),
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="basis_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="basis_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="basis_en_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="basis_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="basis_verification_supported",
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.procedure_version

    def clean(self) -> None:
        _required(self.semantic_id, "semantic_id")
        _required(self.text_ar, "text_ar")
        _required(self.text_en, "text_en")
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})

        from .domain import decode_stored_rule

        if self.reachability != {}:
            reachability = decode_stored_rule(self.reachability)
            if reachability.diagnostics:
                raise ValidationError({"reachability": "Reachability rule is invalid."})
        if self.qualification == {}:
            raise ValidationError({"qualification": "Eligibility Basis qualification is required."})
        qualification = decode_stored_rule(self.qualification)
        if qualification.diagnostics:
            raise ValidationError({"qualification": "Qualification rule is invalid."})

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.semantic_id}"


class Step(VersionOwnedModel):
    class Scope(models.TextChoices):
        PROCEDURE = "procedure", "Entire procedure"
        ELIGIBILITY_BASIS = "eligibility_basis", "Eligibility basis"

    procedure_version = models.ForeignKey(
        ProcedureVersion, on_delete=models.CASCADE, related_name="steps"
    )
    semantic_id = models.CharField(max_length=128)
    text_ar = models.TextField()
    text_en = models.TextField()
    phase = models.CharField(max_length=128)
    phase_order = models.PositiveIntegerField(default=0)
    slot = models.PositiveIntegerField(default=0)
    applicability = models.JSONField(default=dict, blank=True)
    scope = models.CharField(max_length=24, choices=Scope.choices, default=Scope.PROCEDURE)
    eligibility_basis = models.ForeignKey(
        EligibilityBasis, null=True, blank=True, on_delete=models.PROTECT, related_name="steps"
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )

    class Meta:
        ordering = ("procedure_version_id", "phase_order", "slot", "semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "semantic_id"), name="unique_step_id_per_version"
            ),
            models.UniqueConstraint(
                fields=("procedure_version", "phase_order", "slot"),
                condition=Q(verification_state="current"),
                name="unique_current_step_position",
            ),
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="step_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="step_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="step_en_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(phase__regex=NONBLANK_PATTERN), name="step_phase_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(scope="procedure", eligibility_basis__isnull=True)
                | Q(scope="eligibility_basis", eligibility_basis__isnull=False),
                name="step_scope_combination",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="step_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="step_verification_supported",
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.procedure_version

    def clean(self) -> None:
        for field in ("semantic_id", "text_ar", "text_en", "phase"):
            _required(getattr(self, field), field)
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if self.scope == self.Scope.PROCEDURE and self.eligibility_basis_id is not None:
            raise ValidationError({"eligibility_basis": "Procedure scope cannot have a Basis."})
        if self.scope == self.Scope.ELIGIBILITY_BASIS:
            if self.eligibility_basis_id is None:
                raise ValidationError({"eligibility_basis": "Basis scope requires a Basis."})
            assert self.eligibility_basis is not None
            if self.eligibility_basis.procedure_version_id != self.procedure_version_id:
                raise ValidationError(
                    {"eligibility_basis": "Basis must belong to this Procedure Version."}
                )

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.semantic_id}"


class Warning(VersionOwnedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Information"
        IMPORTANT = "important", "Important"

    class Kind(models.TextChoices):
        ADMINISTRATIVE = "administrative", "Administrative"
        PRODUCT = "product", "Product"

    class Role(models.TextChoices):
        GENERAL = "general", "General"
        REGENERATION = "regeneration", "Regeneration"
        LIMITATION = "limitation", "Limitation"

    procedure_version = models.ForeignKey(
        ProcedureVersion, on_delete=models.CASCADE, related_name="warnings"
    )
    semantic_id = models.CharField(max_length=128)
    text_ar = models.TextField()
    text_en = models.TextField()
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.GENERAL)
    display_order = models.PositiveIntegerField(default=0)
    applicability = models.JSONField(default=dict, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )

    class Meta:
        ordering = ("procedure_version_id", "display_order", "semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "semantic_id"), name="unique_warning_id_per_version"
            ),
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="warning_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="warning_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="warning_en_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(severity__in=["info", "important"]),
                name="warning_severity_supported",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["administrative", "product"]),
                name="warning_kind_supported",
            ),
            models.CheckConstraint(
                condition=Q(role__in=["general", "regeneration", "limitation"]),
                name="warning_role_supported",
            ),
            models.CheckConstraint(
                condition=~Q(role="regeneration") | Q(kind="product", severity="important"),
                name="warning_regeneration_policy",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="warning_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="warning_verification_supported",
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.procedure_version

    def clean(self) -> None:
        for field in ("semantic_id", "text_ar", "text_en"):
            _required(getattr(self, field), field)
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if self.role == self.Role.REGENERATION and (
            self.kind != self.Kind.PRODUCT or self.severity != self.Severity.IMPORTANT
        ):
            raise ValidationError(
                {"role": "Regeneration warnings must be important product warnings."}
            )

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.semantic_id}"


EVIDENCE_OWNER_FIELDS = (
    "checklist_item",
    "step",
    "warning",
    "fee",
    "eligibility_basis",
    "procedure_dependency",
    "service_point_version",
    "procedure_service_point_association",
)


def _evidence_exactly_one_owner_condition() -> Q:
    terms = [
        Q(**{f"{name}__isnull": name != selected for name in EVIDENCE_OWNER_FIELDS})
        for selected in EVIDENCE_OWNER_FIELDS
    ]
    condition = terms[0]
    for term in terms[1:]:
        condition |= term
    return condition


class EvidenceLink(VersionOwnedModel):
    class SupportStatus(models.TextChoices):
        SUPPORTS = "supports", "Supports"
        CONTEXT = "context", "Context only"
        CONTRADICTS = "contradicts", "Contradicts"

    # Stable claim-specific identity. Blank remains permitted for legacy/editorial rows;
    # production importers must provide an identifier.
    semantic_id = models.CharField(max_length=128, blank=True, default="")
    checklist_item = models.ForeignKey(
        ChecklistItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    step = models.ForeignKey(
        Step, null=True, blank=True, on_delete=models.CASCADE, related_name="evidence_links"
    )
    warning = models.ForeignKey(
        Warning, null=True, blank=True, on_delete=models.CASCADE, related_name="evidence_links"
    )
    passage = models.TextField()
    location = models.TextField(blank=True)
    applicability_context = models.TextField(blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    retrieved_on = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )
    support_status = models.CharField(
        max_length=16, choices=SupportStatus.choices, default=SupportStatus.SUPPORTS
    )
    # These feature models remain in focused modules. Lazy references keep their public import
    # paths while making the complete EvidenceLink owner contract explicit at class construction.
    fee = models.ForeignKey(
        "knowledge.Fee",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    eligibility_basis = models.ForeignKey(
        EligibilityBasis,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    procedure_dependency = models.ForeignKey(
        "knowledge.ProcedureDependency",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    service_point_version = models.ForeignKey(
        "knowledge.ServicePointVersion",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    procedure_service_point_association = models.ForeignKey(
        "knowledge.ProcedureServicePointAssociation",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    sources = models.ManyToManyField(
        Source, through="EvidenceLinkSource", related_name="evidence_links"
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("checklist_item", "semantic_id"),
                condition=Q(checklist_item__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_checklist_owner",
            ),
            models.UniqueConstraint(
                fields=("step", "semantic_id"),
                condition=Q(step__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_step_owner",
            ),
            models.UniqueConstraint(
                fields=("warning", "semantic_id"),
                condition=Q(warning__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_warning_owner",
            ),
            models.CheckConstraint(
                condition=Q(
                    verification_state__in=[
                        "current",
                        "needs_reverification",
                        "stale",
                        "disputed",
                        "unknown",
                    ]
                ),
                name="evidence_verification_supported",
            ),
            models.CheckConstraint(
                condition=Q(support_status__in=["supports", "context", "contradicts"]),
                name="evidence_support_supported",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="evidence_dates_ordered",
            ),
            models.CheckConstraint(
                condition=_evidence_exactly_one_owner_condition(),
                name="evidence_exactly_one_owner",
            ),
            models.CheckConstraint(
                condition=Q(semantic_id="") | Q(semantic_id__regex=NONBLANK_PATTERN),
                name="evidence_semantic_id_blank_or_nonblank",
            ),
            models.UniqueConstraint(
                fields=("fee", "semantic_id"),
                condition=Q(fee__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_fee_owner",
            ),
            models.UniqueConstraint(
                fields=("eligibility_basis", "semantic_id"),
                condition=Q(eligibility_basis__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_basis_owner",
            ),
            models.UniqueConstraint(
                fields=("procedure_dependency", "semantic_id"),
                condition=Q(procedure_dependency__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_dependency_owner",
            ),
            models.UniqueConstraint(
                fields=("service_point_version", "semantic_id"),
                condition=Q(service_point_version__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_point_version_owner",
            ),
            models.UniqueConstraint(
                fields=("procedure_service_point_association", "semantic_id"),
                condition=Q(procedure_service_point_association__isnull=False) & ~Q(semantic_id=""),
                name="unique_evidence_id_point_association_owner",
            ),
        ]

    @property
    def owner(self) -> Any:
        owners = [
            getattr(self, name)
            for name in EVIDENCE_OWNER_FIELDS
            if getattr(self, f"{name}_id") is not None
        ]
        if len(owners) != 1:
            raise ValidationError("Evidence must have exactly one claim owner.")
        return owners[0]

    def owning_versions(self) -> tuple[ProcedureVersion, ...]:
        candidate = self.owner
        multiple = getattr(candidate, "owning_versions", None)
        if callable(multiple):
            return tuple(multiple())
        single = getattr(candidate, "owning_version", None)
        if callable(single):
            return (single(),)
        return (candidate.procedure_version,)

    def owning_version(self) -> ProcedureVersion:
        versions = self.owning_versions()
        if not versions:
            raise ValidationError("Evidence owner must belong to a Procedure Version.")
        return next(
            (version for version in versions if version.state != ProcedureVersion.State.DRAFT),
            versions[0],
        )

    def clean(self) -> None:
        owner_ids = tuple(getattr(self, f"{name}_id") for name in EVIDENCE_OWNER_FIELDS)
        if self.pk is not None:
            stored = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list(*(f"{name}_id" for name in EVIDENCE_OWNER_FIELDS))
                .first()
            )
            if stored is not None and stored != owner_ids:
                raise ValidationError("Evidence claim ownership cannot be reassigned.")
        if sum(value is not None for value in owner_ids) != 1:
            raise ValidationError("Evidence must have exactly one claim owner.")
        if (
            self.warning_id is not None
            and self.warning is not None
            and self.warning.kind == Warning.Kind.PRODUCT
        ):
            raise ValidationError({"warning": "Product warnings cannot carry Evidence Links."})
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if self.semantic_id and not self.semantic_id.strip():
            raise ValidationError({"semantic_id": "Evidence identity cannot be whitespace."})

    def __str__(self) -> str:
        identity = self.semantic_id or str(self.pk or "new")
        return f"evidence:{self.owner}:{identity}"


class EvidenceLinkSource(VersionOwnedModel):
    evidence_link = models.ForeignKey(
        EvidenceLink, on_delete=models.CASCADE, related_name="source_links"
    )
    source = models.ForeignKey(
        Source, on_delete=models.PROTECT, related_name="evidence_source_links"
    )
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ("evidence_link_id", "position", "source__semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("evidence_link", "source"), name="unique_evidence_source"
            ),
            models.UniqueConstraint(
                fields=("evidence_link", "position"), name="unique_evidence_source_position"
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.evidence_link.owning_version()