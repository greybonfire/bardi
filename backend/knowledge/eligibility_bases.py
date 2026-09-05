"""Eligibility Basis authoring, evidence ownership, publication, and snapshot adaptation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from planning.case_preparation import DERIVED_FACT_DEPENDENCIES
from planning.catalog import (
    AuthoritySnapshot,
    EligibilityBasisSnapshot,
    EvidenceLinkSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    SourceSnapshot,
)
from planning.diagnostics import ValidationDiagnostic
from planning.rules import Predicate
from planning.trust import VERIFICATION_CHOICES, VerificationState

from . import domain as knowledge_domain
from .domain import (
    KnowledgeSnapshotLoadError,
    StoredRuleLoadDiagnostic,
    decode_stored_rule,
    referenced_fact_keys,
)
from .models import (
    NONBLANK_PATTERN,
    Authority,
    EligibilityBasis,
    EvidenceLink,
    EvidenceLinkSource,
    ProcedureVersion,
    Source,
    Warning,
    _required,
)
from .publication import PublicationContext, PublicationDiagnostic


def _install_basis_fields() -> None:
    existing = {field.name for field in EligibilityBasis._meta.fields}
    fields: tuple[tuple[str, models.Field[Any, Any]], ...] = (
        ("text_ar", models.TextField(default="")),
        ("text_en", models.TextField(default="")),
        ("reachability", models.JSONField(default=dict, blank=True)),
        ("qualification", models.JSONField(default=dict, blank=True)),
        ("display_order", models.PositiveIntegerField(default=0)),
        ("effective_from", models.DateField(null=True, blank=True)),
        ("effective_to", models.DateField(null=True, blank=True)),
        ("verified_on", models.DateField(null=True, blank=True)),
        ("reverify_on", models.DateField(null=True, blank=True)),
        (
            "verification_state",
            models.CharField(max_length=24, choices=VERIFICATION_CHOICES, default="unknown"),
        ),
    )
    for name, field in fields:
        if name not in existing:
            EligibilityBasis.add_to_class(name, field)

    EligibilityBasis._meta.ordering = ("procedure_version_id", "display_order", "semantic_id")
    constraint_names = {constraint.name for constraint in EligibilityBasis._meta.constraints}
    additions: list[models.BaseConstraint] = []
    if "basis_ar_nonblank" not in constraint_names:
        additions.append(
            models.CheckConstraint(
                condition=Q(text_ar__regex=NONBLANK_PATTERN), name="basis_ar_nonblank"
            )
        )
    if "basis_en_nonblank" not in constraint_names:
        additions.append(
            models.CheckConstraint(
                condition=Q(text_en__regex=NONBLANK_PATTERN), name="basis_en_nonblank"
            )
        )
    if "basis_dates_ordered" not in constraint_names:
        additions.append(
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="basis_dates_ordered",
            )
        )
    if "basis_verification_supported" not in constraint_names:
        additions.append(
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="basis_verification_supported",
            )
        )
    EligibilityBasis._meta.constraints = [*EligibilityBasis._meta.constraints, *additions]

    def clean(basis: EligibilityBasis) -> None:
        _required(basis.semantic_id, "semantic_id")
        _required(basis.text_ar, "text_ar")
        _required(basis.text_en, "text_en")
        if basis.effective_from and basis.effective_to and basis.effective_from > basis.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if basis.reachability != {}:
            reachability = decode_stored_rule(basis.reachability)
            if reachability.diagnostics:
                raise ValidationError({"reachability": "Reachability rule is invalid."})
        if basis.qualification == {}:
            raise ValidationError({"qualification": "Eligibility Basis qualification is required."})
        qualification = decode_stored_rule(basis.qualification)
        if qualification.diagnostics:
            raise ValidationError({"qualification": "Qualification rule is invalid."})

    EligibilityBasis.clean = clean  # type: ignore[assignment]


_install_basis_fields()


def _install_basis_evidence_owner() -> None:
    if not any(field.name == "eligibility_basis" for field in EvidenceLink._meta.fields):
        EvidenceLink.add_to_class(
            "eligibility_basis",
            models.ForeignKey(
                EligibilityBasis,
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
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=False,
                    warning__isnull=True,
                    fee__isnull=True,
                    eligibility_basis__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=False,
                    fee__isnull=True,
                    eligibility_basis__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=True,
                    fee__isnull=False,
                    eligibility_basis__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=True,
                    fee__isnull=True,
                    eligibility_basis__isnull=False,
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


_install_basis_evidence_owner()


def _source_fact_keys(
    predicates: Iterable[Predicate], context: PublicationContext
) -> tuple[set[str], set[str]]:
    source_keys: set[str] = set()
    defects: set[str] = set()
    for predicate in predicates:
        for key in referenced_fact_keys(predicate):
            definition = context.fact_definitions.get(key)
            if definition is None:
                defects.add(key)
                continue
            if not definition.derived:
                source_keys.add(key)
                continue
            dependencies = DERIVED_FACT_DEPENDENCIES.get(key)
            if not dependencies or any(
                (dependency := context.fact_definitions.get(source)) is None or dependency.derived
                for source in dependencies
            ):
                defects.add(key)
            else:
                source_keys.update(dependencies)
    return source_keys, defects


class EligibilityBasisPublicationGate:
    """Validate Basis stages, evidence, ownership, and consequential Question coverage."""

    name = "core.eligibility_bases"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        failures: list[PublicationDiagnostic] = []
        basis_ids = list(
            EligibilityBasis.objects.select_for_update()
            .filter(procedure_version=context.version)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        link_ids = list(
            EvidenceLink.objects.select_for_update()
            .filter(eligibility_basis_id__in=basis_ids)
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
        bases = list(
            EligibilityBasis.objects.prefetch_related("evidence_links__source_links__source")
            .filter(pk__in=basis_ids)
            .order_by("display_order", "semantic_id")
        )
        semantic_ids = {basis.semantic_id for basis in bases}
        for item in context.version.checklist_items.filter(scope="eligibility_basis").order_by(
            "semantic_id"
        ):
            if item.scope_reference not in semantic_ids:
                failures.append(
                    PublicationDiagnostic(self.name, "invalid_basis_owner", item.semantic_id)
                )

        predicates: list[Predicate] = []
        for basis in bases:
            owner_id = basis.semantic_id
            if not basis.text_ar.strip() or not basis.text_en.strip():
                failures.append(
                    PublicationDiagnostic(self.name, "incomplete_bilingual_basis", owner_id)
                )
            if (
                basis.effective_from
                and basis.effective_to
                and basis.effective_from > basis.effective_to
            ):
                failures.append(
                    PublicationDiagnostic(self.name, "invalid_effective_interval", owner_id)
                )
            if basis.reachability != {}:
                decoded = decode_stored_rule(basis.reachability, context.fact_definitions)
                if decoded.predicate is None:
                    failures.extend(
                        PublicationDiagnostic(self.name, diagnostic.code, f"{owner_id}:reachability")
                        for diagnostic in decoded.diagnostics
                    )
                else:
                    predicates.append(decoded.predicate)
            if basis.qualification == {}:
                failures.append(
                    PublicationDiagnostic(self.name, "qualification_required", owner_id)
                )
            else:
                decoded = decode_stored_rule(basis.qualification, context.fact_definitions)
                if decoded.predicate is None:
                    failures.extend(
                        PublicationDiagnostic(self.name, diagnostic.code, f"{owner_id}:qualification")
                        for diagnostic in decoded.diagnostics
                    )
                else:
                    predicates.append(decoded.predicate)

            links = list(basis.evidence_links.all())
            adequate_current_support = False
            for link in links:
                sources = [row.source for row in link.source_links.all()]
                detail = f"{owner_id}:{link.pk}"
                complete = bool(
                    sources
                    and link.passage.strip()
                    and link.location.strip()
                    and link.applicability_context.strip()
                )
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
                    basis.verification_state == "current"
                    and link.verification_state == "current"
                    and link.support_status == EvidenceLink.SupportStatus.CONTRADICTS
                ):
                    failures.append(
                        PublicationDiagnostic(
                            self.name, "unresolved_evidence_contradiction", detail
                        )
                    )
                adequate_current_support |= (
                    complete
                    and link.verification_state == "current"
                    and link.support_status == EvidenceLink.SupportStatus.SUPPORTS
                )
            if not links:
                failures.append(PublicationDiagnostic(self.name, "evidence_required", owner_id))
            if basis.verification_state == "current" and not adequate_current_support:
                failures.append(
                    PublicationDiagnostic(self.name, "adequate_evidence_required", owner_id)
                )

        source_keys, dependency_defects = _source_fact_keys(predicates, context)
        failures.extend(
            PublicationDiagnostic(self.name, "invalid_derived_fact_dependency", key)
            for key in sorted(dependency_defects)
        )
        questions = context.version.procedure.primary_service.questions.prefetch_related(
            "resolved_fact_links__fact", "fact"
        )
        covered = {key for question in questions for key in question.resolved_fact_keys}
        failures.extend(
            PublicationDiagnostic(self.name, "missing_service_question", key)
            for key in sorted(source_keys - covered)
        )
        return failures


def _basis_snapshots(snapshot: KnowledgeSnapshot) -> KnowledgeSnapshot:
    basis_rows = list(
        EligibilityBasis.objects.filter(
            procedure_version__state__in=(ProcedureVersion.State.PUBLISHED, ProcedureVersion.State.WITHDRAWN)
        )
        .order_by("procedure_version__semantic_id", "display_order", "semantic_id")
        .values(
            "id",
            "procedure_version__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "reachability",
            "qualification",
            "display_order",
            "effective_from",
            "effective_to",
            "verification_state",
            "verified_on",
            "reverify_on",
        )
    )
    if not basis_rows:
        return snapshot

    evidence_rows = list(
        EvidenceLink.objects.filter(eligibility_basis_id__in=[row["id"] for row in basis_rows])
        .order_by("id")
        .values(
            "id",
            "eligibility_basis_id",
            "passage",
            "location",
            "applicability_context",
            "support_status",
            "verification_state",
            "effective_from",
            "effective_to",
            "retrieved_on",
            "verified_on",
            "reverify_on",
        )
    )
    evidence_source_rows = list(
        EvidenceLinkSource.objects.filter(evidence_link_id__in=[row["id"] for row in evidence_rows])
        .order_by("evidence_link_id", "position", "source__semantic_id")
        .values(
            "evidence_link_id",
            "source__semantic_id",
            "source__title",
            "source__locator",
            "source__classification",
            "source__retrieved_on",
            "source__published_on",
            "source__effective_from",
            "source__effective_to",
            "source__reverify_on",
            "source__observation_date",
            "source__observation_context",
            "source__authority__semantic_id",
            "source__authority__name_ar",
            "source__authority__name_en",
        )
    )
    source_snapshots: dict[str, SourceSnapshot] = {}
    sources_by_link: dict[int, list[SourceSnapshot]] = defaultdict(list)
    for row in evidence_source_rows:
        source_id = row["source__semantic_id"]
        source = source_snapshots.setdefault(
            source_id,
            SourceSnapshot(
                source_id,
                AuthoritySnapshot(
                    row["source__authority__semantic_id"],
                    LocalizedText(
                        row["source__authority__name_ar"], row["source__authority__name_en"]
                    ),
                ),
                row["source__title"],
                row["source__locator"],
                row["source__classification"],
                row["source__retrieved_on"],
                row["source__published_on"],
                row["source__effective_from"],
                row["source__effective_to"],
                row["source__reverify_on"],
                row["source__observation_date"],
                row["source__observation_context"],
            ),
        )
        sources_by_link[row["evidence_link_id"]].append(source)

    evidence_by_basis: dict[int, list[EvidenceLinkSnapshot]] = defaultdict(list)
    for row in cast(list[dict[str, Any]], evidence_rows):
        evidence_by_basis[row["eligibility_basis_id"]].append(
            EvidenceLinkSnapshot(
                row["passage"],
                row["location"],
                row["applicability_context"],
                row["support_status"],
                cast(VerificationState, row["verification_state"]),
                tuple(sources_by_link[row["id"]]),
                row["effective_from"],
                row["effective_to"],
                row["retrieved_on"],
                row["verified_on"],
                row["reverify_on"],
            )
        )

    failures: list[StoredRuleLoadDiagnostic] = []
    by_version: dict[str, list[EligibilityBasisSnapshot]] = defaultdict(list)
    for row in cast(list[dict[str, Any]], basis_rows):
        owner = f"eligibility_basis:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        reachability: Predicate | None = None
        if row["reachability"] != {}:
            decoded = decode_stored_rule(row["reachability"], snapshot.fact_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
            reachability = decoded.predicate
        if row["qualification"] == {}:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    (ValidationDiagnostic("missing_qualification", ("qualification",)),),
                )
            )
            continue
        decoded = decode_stored_rule(row["qualification"], snapshot.fact_definitions)
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue
        links = tuple(evidence_by_basis[row["id"]])
        invalid = (
            not row["text_ar"].strip()
            or not row["text_en"].strip()
            or not links
            or any(not link.sources for link in links)
        )
        if invalid:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    (ValidationDiagnostic("invalid_basis_evidence", ("evidence",)),),
                )
            )
            continue
        by_version[row["procedure_version__semantic_id"]].append(
            EligibilityBasisSnapshot(
                row["semantic_id"],
                LocalizedText(row["text_ar"], row["text_en"]),
                reachability,
                decoded.predicate,
                row["display_order"],
                row["effective_from"],
                row["effective_to"],
                cast(VerificationState, row["verification_state"]),
                row["verified_on"],
                row["reverify_on"],
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
                eligibility_bases=tuple(by_version[version.semantic_id]),
            )
            for version in snapshot.procedure_versions
        ),
    )


_original_materialize = knowledge_domain._materialize_knowledge_snapshot


def _materialize_with_bases() -> KnowledgeSnapshot:
    return _basis_snapshots(_original_materialize())


knowledge_domain._materialize_knowledge_snapshot = _materialize_with_bases


__all__ = ("EligibilityBasisPublicationGate",)
