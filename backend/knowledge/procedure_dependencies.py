"""Version-owned direct Procedure prerequisites and publication policy."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from planning.catalog import (
    AuthoritySnapshot,
    EvidenceLinkSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    ProcedureDependencySnapshot,
    SourceSnapshot,
)
from planning.diagnostics import ValidationDiagnostic
from planning.rules import Predicate
from planning.trust import VERIFICATION_CHOICES, VerificationState

from .domain import KnowledgeSnapshotLoadError, StoredRuleLoadDiagnostic, decode_stored_rule
from .eligibility_bases import _source_fact_keys
from .models import (
    NONBLANK_PATTERN,
    Authority,
    EvidenceLink,
    EvidenceLinkSource,
    Procedure,
    ProcedureVersion,
    Source,
    VersionOwnedModel,
    Warning,
    _required,
)
from .publication import PublicationContext, PublicationDiagnostic


class ProcedureDependency(VersionOwnedModel):
    class Relation(models.TextChoices):
        BLOCKING_PREREQUISITE = "blocking_prerequisite", "Blocking prerequisite"

    procedure_version = models.ForeignKey(
        ProcedureVersion,
        on_delete=models.CASCADE,
        related_name="dependencies",
    )
    semantic_id = models.CharField(max_length=128)
    text_ar = models.TextField()
    text_en = models.TextField()
    target_procedure = models.ForeignKey(
        Procedure,
        on_delete=models.PROTECT,
        related_name="incoming_dependencies",
    )
    relation = models.CharField(
        max_length=32,
        choices=Relation.choices,
        default=Relation.BLOCKING_PREREQUISITE,
    )
    applicability = models.JSONField(default=dict, blank=True)
    satisfied_when = models.JSONField(default=dict, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24,
        choices=VERIFICATION_CHOICES,
        default="unknown",
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("procedure_version_id", "display_order", "semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "semantic_id"),
                name="unique_dependency_id_per_version",
            ),
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN),
                name="dependency_id_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN),
                name="dependency_ar_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN),
                name="dependency_en_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(relation="blocking_prerequisite"),
                name="dependency_relation_supported",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="dependency_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="dependency_verification_supported",
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.procedure_version

    def clean(self) -> None:
        for field in ("semantic_id", "text_ar", "text_en"):
            _required(getattr(self, field), field)
        if self.relation != self.Relation.BLOCKING_PREREQUISITE:
            raise ValidationError({"relation": "Unsupported Procedure dependency relation."})
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if (
            self.procedure_version_id
            and self.target_procedure_id
            and self.procedure_version.procedure_id == self.target_procedure_id
        ):
            raise ValidationError({"target_procedure": "A Procedure cannot depend on itself."})
        if self.applicability != {} and decode_stored_rule(self.applicability).diagnostics:
            raise ValidationError({"applicability": "Dependency applicability is invalid."})
        if self.satisfied_when == {}:
            raise ValidationError({"satisfied_when": "Dependency satisfaction rule is required."})
        if decode_stored_rule(self.satisfied_when).diagnostics:
            raise ValidationError({"satisfied_when": "Dependency satisfaction rule is invalid."})

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.semantic_id}"


def _install_dependency_evidence_owner() -> None:
    if not any(field.name == "procedure_dependency" for field in EvidenceLink._meta.fields):
        EvidenceLink.add_to_class(
            "procedure_dependency",
            models.ForeignKey(
                ProcedureDependency,
                null=True,
                blank=True,
                on_delete=models.CASCADE,
                related_name="evidence_links",
            ),
        )

    EvidenceLink._meta.constraints = [
        constraint
        for constraint in EvidenceLink._meta.constraints
        if constraint.name != "evidence_exactly_one_owner"
    ] + [
        models.CheckConstraint(
            condition=(
                Q(
                    checklist_item__isnull=False,
                    step__isnull=True,
                    warning__isnull=True,
                    fee__isnull=True,
                    eligibility_basis__isnull=True,
                    procedure_dependency__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=False,
                    warning__isnull=True,
                    fee__isnull=True,
                    eligibility_basis__isnull=True,
                    procedure_dependency__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=False,
                    fee__isnull=True,
                    eligibility_basis__isnull=True,
                    procedure_dependency__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=True,
                    fee__isnull=False,
                    eligibility_basis__isnull=True,
                    procedure_dependency__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=True,
                    fee__isnull=True,
                    eligibility_basis__isnull=False,
                    procedure_dependency__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=True,
                    fee__isnull=True,
                    eligibility_basis__isnull=True,
                    procedure_dependency__isnull=False,
                )
            ),
            name="evidence_exactly_one_owner",
        )
    ]

    def owner(link: EvidenceLink) -> object:
        owners = [
            candidate
            for candidate in (
                link.checklist_item,
                link.step,
                link.warning,
                getattr(link, "fee", None),
                getattr(link, "eligibility_basis", None),
                getattr(link, "procedure_dependency", None),
            )
            if candidate is not None
        ]
        if len(owners) != 1:
            raise ValidationError("Evidence must have exactly one claim owner.")
        return owners[0]

    def owning_version(link: EvidenceLink) -> ProcedureVersion:
        candidate = owner(link)
        return candidate.procedure_version  # type: ignore[attr-defined,no-any-return]

    def clean(link: EvidenceLink) -> None:
        owner_ids = (
            link.checklist_item_id,
            link.step_id,
            link.warning_id,
            getattr(link, "fee_id", None),
            getattr(link, "eligibility_basis_id", None),
            getattr(link, "procedure_dependency_id", None),
        )
        if link.pk is not None:
            stored = (
                type(link)
                .objects.filter(pk=link.pk)
                .values_list(
                    "checklist_item_id",
                    "step_id",
                    "warning_id",
                    "fee_id",
                    "eligibility_basis_id",
                    "procedure_dependency_id",
                )
                .first()
            )
            if stored is not None and stored != owner_ids:
                raise ValidationError("Evidence claim ownership cannot be reassigned.")
        if sum(value is not None for value in owner_ids) != 1:
            raise ValidationError("Evidence must have exactly one claim owner.")
        if (
            link.warning_id is not None
            and link.warning is not None
            and link.warning.kind == Warning.Kind.PRODUCT
        ):
            raise ValidationError({"warning": "Product warnings cannot carry Evidence Links."})
        if link.effective_from and link.effective_to and link.effective_from > link.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})

    EvidenceLink.owner = property(owner)  # type: ignore[assignment]
    EvidenceLink.owning_version = owning_version  # type: ignore[assignment]
    EvidenceLink.clean = clean  # type: ignore[assignment]


_install_dependency_evidence_owner()


def _has_blocking_cycle(rows: Iterable[ProcedureDependency]) -> bool:
    edges: dict[int, set[int]] = defaultdict(set)
    for dependency in rows:
        if dependency.relation == ProcedureDependency.Relation.BLOCKING_PREREQUISITE:
            edges[dependency.procedure_version.procedure_id].add(dependency.target_procedure_id)

    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(node: int) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(target) for target in edges.get(node, set())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(edges))


def _evidence_complete(link: EvidenceLink) -> bool:
    return bool(
        list(link.source_links.all())
        and link.passage.strip()
        and link.location.strip()
        and link.applicability_context.strip()
    )


class ProcedureDependencyPublicationGate:
    """Validate direct prerequisite rules, evidence, ownership, and cycle safety."""

    name = "core.procedure_dependencies"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        failures: list[PublicationDiagnostic] = []
        dependency_ids = list(
            ProcedureDependency.objects.select_for_update()
            .filter(procedure_version=context.version)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        link_ids = list(
            EvidenceLink.objects.select_for_update()
            .filter(procedure_dependency_id__in=dependency_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        source_ids = list(
            EvidenceLinkSource.objects.select_for_update()
            .filter(evidence_link_id__in=link_ids)
            .order_by("pk")
            .values_list("source_id", flat=True)
        )
        source_rows = list(
            Source.objects.select_for_update()
            .filter(pk__in=source_ids)
            .order_by("pk")
            .values_list("pk", "authority_id")
        )
        list(
            Authority.objects.select_for_update()
            .filter(pk__in={authority_id for _, authority_id in source_rows})
            .order_by("pk")
        )

        dependencies = list(
            ProcedureDependency.objects.select_related(
                "procedure_version__procedure",
                "target_procedure",
            )
            .prefetch_related("evidence_links__source_links__source")
            .filter(pk__in=dependency_ids)
            .order_by("display_order", "semantic_id")
        )
        predicates: list[Predicate] = []
        for dependency in dependencies:
            owner_id = dependency.semantic_id
            if not dependency.text_ar.strip() or not dependency.text_en.strip():
                failures.append(
                    PublicationDiagnostic(self.name, "incomplete_bilingual_dependency", owner_id)
                )
            if dependency.relation != ProcedureDependency.Relation.BLOCKING_PREREQUISITE:
                failures.append(
                    PublicationDiagnostic(self.name, "unsupported_dependency_relation", owner_id)
                )
            if dependency.procedure_version_id != context.version.pk:
                failures.append(PublicationDiagnostic(self.name, "invalid_owner", owner_id))
            if dependency.target_procedure_id == context.version.procedure_id:
                failures.append(PublicationDiagnostic(self.name, "self_dependency", owner_id))
            if (
                dependency.effective_from
                and dependency.effective_to
                and dependency.effective_from > dependency.effective_to
            ):
                failures.append(
                    PublicationDiagnostic(self.name, "invalid_effective_interval", owner_id)
                )

            for field_name in ("applicability", "satisfied_when"):
                stored_rule = getattr(dependency, field_name)
                if field_name == "applicability" and stored_rule == {}:
                    continue
                if stored_rule == {}:
                    failures.append(
                        PublicationDiagnostic(self.name, "satisfied_when_required", owner_id)
                    )
                    continue
                decoded = decode_stored_rule(stored_rule, context.fact_definitions)
                if decoded.predicate is None:
                    failures.extend(
                        PublicationDiagnostic(
                            self.name,
                            diagnostic.code,
                            f"{owner_id}:{field_name}",
                        )
                        for diagnostic in decoded.diagnostics
                    )
                else:
                    predicates.append(decoded.predicate)

            links = list(dependency.evidence_links.all())
            adequate_current_support = False
            for link in links:
                owner_ids = (
                    link.checklist_item_id,
                    link.step_id,
                    link.warning_id,
                    getattr(link, "fee_id", None),
                    getattr(link, "eligibility_basis_id", None),
                    getattr(link, "procedure_dependency_id", None),
                )
                detail = f"{owner_id}:{link.pk}"
                valid_owner = (
                    sum(value is not None for value in owner_ids) == 1
                    and owner_ids[-1] == dependency.pk
                )
                if not valid_owner:
                    failures.append(
                        PublicationDiagnostic(self.name, "invalid_evidence_owner", detail)
                    )
                sources = [row.source for row in link.source_links.all()]
                if not sources:
                    failures.append(
                        PublicationDiagnostic(self.name, "missing_evidence_source", detail)
                    )
                if not link.passage.strip():
                    failures.append(
                        PublicationDiagnostic(self.name, "missing_evidence_passage", detail)
                    )
                if not link.location.strip() or not link.applicability_context.strip():
                    failures.append(
                        PublicationDiagnostic(self.name, "missing_evidence_context", detail)
                    )
                for source in sources:
                    if source.classification == Source.Classification.FIELD_REPORT and (
                        source.observation_date is None or not source.observation_context.strip()
                    ):
                        failures.append(
                            PublicationDiagnostic(self.name, "malformed_field_guidance", detail)
                        )
                if (
                    dependency.verification_state == "current"
                    and link.verification_state == "current"
                    and link.support_status == EvidenceLink.SupportStatus.CONTRADICTS
                ):
                    failures.append(
                        PublicationDiagnostic(
                            self.name,
                            "unresolved_evidence_contradiction",
                            detail,
                        )
                    )
                adequate_current_support |= (
                    _evidence_complete(link)
                    and link.verification_state == "current"
                    and link.support_status == EvidenceLink.SupportStatus.SUPPORTS
                )
            if not links:
                failures.append(PublicationDiagnostic(self.name, "evidence_required", owner_id))
            if dependency.verification_state == "current" and not adequate_current_support:
                failures.append(
                    PublicationDiagnostic(self.name, "adequate_evidence_required", owner_id)
                )

        graph_rows = list(
            ProcedureDependency.objects.select_for_update()
            .select_related("procedure_version")
            .filter(
                Q(procedure_version=context.version)
                | Q(procedure_version__state=ProcedureVersion.State.PUBLISHED)
            )
            .order_by("procedure_version__procedure_id", "semantic_id")
        )
        if _has_blocking_cycle(graph_rows):
            failures.append(
                PublicationDiagnostic(self.name, "blocking_cycle", context.version.semantic_id)
            )

        source_keys, dependency_defects = _source_fact_keys(predicates, context)
        failures.extend(
            PublicationDiagnostic(self.name, "invalid_derived_fact_dependency", key)
            for key in sorted(dependency_defects)
        )
        questions = context.version.procedure.primary_service.questions.prefetch_related(
            "resolved_fact_links__fact",
            "fact",
        )
        covered = {key for question in questions for key in question.resolved_fact_keys}
        failures.extend(
            PublicationDiagnostic(self.name, "missing_service_question", key)
            for key in sorted(source_keys - covered)
        )
        return failures


def _source_snapshot(source: Source) -> SourceSnapshot:
    return SourceSnapshot(
        source.semantic_id,
        AuthoritySnapshot(
            source.authority.semantic_id,
            LocalizedText(source.authority.name_ar, source.authority.name_en),
        ),
        source.title,
        source.locator,
        source.classification,
        source.retrieved_on,
        source.published_on,
        source.effective_from,
        source.effective_to,
        source.reverify_on,
        source.observation_date,
        source.observation_context,
    )


def _evidence_snapshot(link: EvidenceLink) -> EvidenceLinkSnapshot:
    source_rows = sorted(
        link.source_links.all(),
        key=lambda row: (row.position, row.source.semantic_id),
    )
    return EvidenceLinkSnapshot(
        link.passage,
        link.location,
        link.applicability_context,
        link.support_status,
        cast(VerificationState, link.verification_state),
        tuple(_source_snapshot(row.source) for row in source_rows),
        link.effective_from,
        link.effective_to,
        link.retrieved_on,
        link.verified_on,
        link.reverify_on,
        semantic_id=link.semantic_id,
    )


def _dependency_snapshots(
    snapshot: KnowledgeSnapshot, *, scope: Any | None = None
) -> KnowledgeSnapshot:
    dependency_queryset = (
        ProcedureDependency.objects.select_related(
            "procedure_version__procedure",
            "target_procedure",
        )
        .prefetch_related("evidence_links__source_links__source__authority")
        .filter(
            procedure_version__state__in=(
                ProcedureVersion.State.PUBLISHED,
                ProcedureVersion.State.WITHDRAWN,
            )
        )
    )
    if scope is not None:
        dependency_queryset = dependency_queryset.filter(procedure_version_id__in=scope.version_ids)
    rows = list(
        dependency_queryset.order_by(
            "procedure_version__semantic_id", "display_order", "semantic_id"
        )
    )
    if not rows:
        return snapshot

    failures: list[StoredRuleLoadDiagnostic] = []
    by_version: dict[str, list[ProcedureDependencySnapshot]] = defaultdict(list)
    for dependency in rows:
        owner = (
            f"procedure_dependency:{dependency.procedure_version.semantic_id}:"
            f"{dependency.semantic_id}"
        )
        if dependency.relation != ProcedureDependency.Relation.BLOCKING_PREREQUISITE:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    (ValidationDiagnostic("unsupported_dependency_relation", ("relation",)),),
                )
            )
            continue
        if dependency.procedure_version.procedure_id == dependency.target_procedure_id:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    (ValidationDiagnostic("self_dependency", ("target_procedure",)),),
                )
            )
            continue

        applicability: Predicate | None = None
        if dependency.applicability != {}:
            decoded = decode_stored_rule(dependency.applicability, snapshot.fact_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
            applicability = decoded.predicate
        if dependency.satisfied_when == {}:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    (ValidationDiagnostic("missing_satisfied_when", ("satisfied_when",)),),
                )
            )
            continue
        decoded = decode_stored_rule(dependency.satisfied_when, snapshot.fact_definitions)
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue

        links = tuple(_evidence_snapshot(link) for link in dependency.evidence_links.all())
        invalid = (
            not dependency.text_ar.strip()
            or not dependency.text_en.strip()
            or not links
            or any(not link.sources for link in links)
        )
        if invalid:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    (ValidationDiagnostic("invalid_dependency_evidence", ("evidence",)),),
                )
            )
            continue

        by_version[dependency.procedure_version.semantic_id].append(
            ProcedureDependencySnapshot(
                dependency.semantic_id,
                LocalizedText(dependency.text_ar, dependency.text_en),
                dependency.target_procedure.semantic_id,
                LocalizedText(
                    dependency.target_procedure.text_ar,
                    dependency.target_procedure.text_en,
                ),
                dependency.relation,
                applicability,
                decoded.predicate,
                dependency.display_order,
                dependency.effective_from,
                dependency.effective_to,
                cast(VerificationState, dependency.verification_state),
                dependency.verified_on,
                dependency.reverify_on,
                links,
            )
        )
    if failures:
        raise KnowledgeSnapshotLoadError(failures)

    return KnowledgeSnapshot(
        snapshot.fact_definitions,
        snapshot.services,
        tuple(
            replace(
                version,
                dependencies=tuple(by_version[version.semantic_id]),
            )
            for version in snapshot.procedure_versions
        ),
    )


__all__ = ("ProcedureDependency", "ProcedureDependencyPublicationGate")
