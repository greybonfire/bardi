"""Evidence-backed, versioned Service Point routing persistence and adapter."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from typing import Any, cast

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Func, Q
from planning.catalog import (
    AuthoritySnapshot,
    EvidenceLinkSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    ProcedureServicePointAssociationSnapshot,
    ServicePointSnapshot,
    ServicePointVersionSnapshot,
    SourceSnapshot,
)
from planning.diagnostics import ValidationDiagnostic
from planning.trust import VERIFICATION_CHOICES, VerificationState

from . import domain as knowledge_domain
from .domain import KnowledgeSnapshotLoadError, StoredRuleLoadDiagnostic, decode_stored_rule
from .models import (
    NONBLANK_PATTERN,
    Authority,
    EvidenceLink,
    EvidenceLinkSource,
    ProcedureVersion,
    Source,
    VersionOwnedModel,
    Warning,
    _required,
)
from .publication import PublicationContext, PublicationDiagnostic


class ServicePoint(models.Model):
    semantic_id = models.CharField(max_length=128, unique=True)
    name_ar = models.TextField()
    name_en = models.TextField()

    class Meta:
        app_label = "knowledge"
        ordering = ("semantic_id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN), name="service_point_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(name_ar__regex=NONBLANK_PATTERN), name="service_point_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(name_en__regex=NONBLANK_PATTERN), name="service_point_en_nonblank"
            ),
        ]

    def clean(self) -> None:
        for field in ("semantic_id", "name_ar", "name_en"):
            _required(getattr(self, field), field)

    def __str__(self) -> str:
        return self.semantic_id


class ServicePointVersion(models.Model):
    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        UNKNOWN = "unknown", "Unknown"

    semantic_id = models.CharField(max_length=128, unique=True)
    service_point = models.ForeignKey(
        ServicePoint, on_delete=models.PROTECT, related_name="versions"
    )
    address_ar = models.TextField()
    address_en = models.TextField()
    availability = models.CharField(max_length=16, choices=Availability.choices)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("service_point_id", "effective_from", "semantic_id")
        constraints = [
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN),
                name="service_point_version_id_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(address_ar__regex=NONBLANK_PATTERN),
                name="service_point_address_ar_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(address_en__regex=NONBLANK_PATTERN),
                name="service_point_address_en_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(availability__in=["available", "unknown"]),
                name="service_point_availability_supported",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="service_point_version_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="service_point_version_verification_supported",
            ),
            models.CheckConstraint(
                condition=Q(verified_on__isnull=True)
                | Q(reverify_on__isnull=True)
                | Q(verified_on__lte=F("reverify_on")),
                name="service_point_version_verification_dates_ordered",
            ),
            ExclusionConstraint(
                name="exclude_current_service_point_version_overlap",
                expressions=(
                    ("service_point", RangeOperators.EQUAL),
                    (
                        Func(
                            "effective_from",
                            "effective_to",
                            models.Value("[]"),
                            function="DATERANGE",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ),
                condition=Q(verification_state="current"),
            ),
        ]

    def clean(self) -> None:
        for field in ("semantic_id", "address_ar", "address_en"):
            _required(getattr(self, field), field)
        if self.availability not in self.Availability.values:
            raise ValidationError({"availability": "Unsupported availability."})
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if self.verified_on and self.reverify_on and self.verified_on > self.reverify_on:
            raise ValidationError({"reverify_on": "Verification interval is not ordered."})

    def owning_versions(self) -> tuple[ProcedureVersion, ...]:
        return tuple(
            ProcedureVersion.objects.filter(service_point_associations__service_point_version=self)
            .distinct()
            .order_by("pk")
        )

    def owning_version(self) -> ProcedureVersion:
        versions = self.owning_versions()
        if not versions:
            raise ValidationError(
                "Service Point Version must be associated before evidence is added."
            )
        return next(
            (version for version in versions if version.state != ProcedureVersion.State.DRAFT),
            versions[0],
        )

    def __str__(self) -> str:
        return self.semantic_id


class ProcedureServicePointAssociation(VersionOwnedModel):
    procedure_version = models.ForeignKey(
        ProcedureVersion, on_delete=models.CASCADE, related_name="service_point_associations"
    )
    semantic_id = models.CharField(max_length=128)
    service_point_version = models.ForeignKey(
        ServicePointVersion, on_delete=models.PROTECT, related_name="associations"
    )
    applicability = models.JSONField()
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("procedure_version_id", "semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "semantic_id"),
                name="unique_service_point_association_id_per_version",
            ),
            models.CheckConstraint(
                condition=Q(semantic_id__regex=NONBLANK_PATTERN),
                name="service_point_association_id_nonblank",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="service_point_association_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="service_point_association_verification_supported",
            ),
            models.CheckConstraint(
                condition=Q(verified_on__isnull=True)
                | Q(reverify_on__isnull=True)
                | Q(verified_on__lte=F("reverify_on")),
                name="service_point_association_verification_dates_ordered",
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.procedure_version

    def clean(self) -> None:
        _required(self.semantic_id, "semantic_id")
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": "Effective interval is not ordered."})
        if self.verified_on and self.reverify_on and self.verified_on > self.reverify_on:
            raise ValidationError({"reverify_on": "Verification interval is not ordered."})
        if self.applicability == {}:
            raise ValidationError({"applicability": "Routing applicability is required."})
        if decode_stored_rule(self.applicability).diagnostics:
            raise ValidationError({"applicability": "Routing applicability is invalid."})

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.semantic_id}"


def _install_routing_evidence_owners() -> None:
    for name, model, related_name in (
        ("service_point_version", ServicePointVersion, "evidence_links"),
        ("procedure_service_point_association", ProcedureServicePointAssociation, "evidence_links"),
    ):
        if not any(field.name == name for field in EvidenceLink._meta.fields):
            EvidenceLink.add_to_class(
                name,
                models.ForeignKey(
                    model,
                    null=True,
                    blank=True,
                    on_delete=models.CASCADE,
                    related_name=related_name,
                ),
            )

    names = (
        "checklist_item",
        "step",
        "warning",
        "fee",
        "eligibility_basis",
        "procedure_dependency",
        "service_point_version",
        "procedure_service_point_association",
    )
    terms = []
    for selected in names:
        terms.append(Q(**{f"{name}__isnull": name != selected for name in names}))
    union = terms[0]
    for term in terms[1:]:
        union |= term
    EvidenceLink._meta.constraints = [
        c for c in EvidenceLink._meta.constraints if c.name != "evidence_exactly_one_owner"
    ] + [models.CheckConstraint(condition=union, name="evidence_exactly_one_owner")]

    def owner(link: EvidenceLink) -> object:
        owners = [
            getattr(link, name, None)
            for name in names
            if getattr(link, f"{name}_id", None) is not None
        ]
        if len(owners) != 1:
            raise ValidationError("Evidence must have exactly one claim owner.")
        return owners[0]

    def owning_versions(link: EvidenceLink) -> tuple[ProcedureVersion, ...]:
        candidate = owner(link)
        method = getattr(candidate, "owning_versions", None)
        if callable(method):
            return cast(tuple[ProcedureVersion, ...], method())
        single = getattr(candidate, "owning_version", None)
        if callable(single):
            return (cast(ProcedureVersion, single()),)
        return (cast(ProcedureVersion, cast(Any, candidate).procedure_version),)

    def owning_version(link: EvidenceLink) -> ProcedureVersion:
        versions = owning_versions(link)
        if not versions:
            raise ValidationError("Evidence owner must belong to a Procedure Version.")
        return next(
            (version for version in versions if version.state != ProcedureVersion.State.DRAFT),
            versions[0],
        )

    def clean(link: EvidenceLink) -> None:
        owner_ids = tuple(getattr(link, f"{name}_id", None) for name in names)
        if link.pk is not None:
            stored = (
                type(link)
                .objects.filter(pk=link.pk)
                .values_list(*(f"{name}_id" for name in names))
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
    EvidenceLink.owning_versions = owning_versions  # type: ignore[attr-defined]
    EvidenceLink.owning_version = owning_version  # type: ignore[assignment]
    EvidenceLink.clean = clean  # type: ignore[assignment]


_install_routing_evidence_owners()


def _complete_support(
    links: Iterable[EvidenceLink], *, current_claim: bool
) -> tuple[bool, list[PublicationDiagnostic]]:
    adequate = False
    failures: list[PublicationDiagnostic] = []
    for link in links:
        detail = str(link.pk)
        sources = [row.source for row in link.source_links.all()]
        complete = bool(
            sources
            and link.passage.strip()
            and link.location.strip()
            and link.applicability_context.strip()
        )
        if not sources:
            failures.append(
                PublicationDiagnostic(
                    "core.service_point_routing", "missing_evidence_source", detail
                )
            )
        if not link.passage.strip():
            failures.append(
                PublicationDiagnostic(
                    "core.service_point_routing", "missing_evidence_passage", detail
                )
            )
        if not link.location.strip() or not link.applicability_context.strip():
            failures.append(
                PublicationDiagnostic(
                    "core.service_point_routing", "missing_evidence_context", detail
                )
            )
        for source in sources:
            if source.classification == Source.Classification.FIELD_REPORT and (
                source.observation_date is None or not source.observation_context.strip()
            ):
                failures.append(
                    PublicationDiagnostic(
                        "core.service_point_routing", "malformed_field_report", detail
                    )
                )
        if (
            current_claim
            and link.verification_state == "current"
            and link.support_status == EvidenceLink.SupportStatus.CONTRADICTS
        ):
            failures.append(
                PublicationDiagnostic(
                    "core.service_point_routing", "unresolved_evidence_contradiction", detail
                )
            )
        adequate |= (
            complete
            and link.verification_state == "current"
            and link.support_status == EvidenceLink.SupportStatus.SUPPORTS
        )
    return adequate, failures


class ServicePointRoutingPublicationGate:
    name = "core.service_point_routing"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        failures: list[PublicationDiagnostic] = []
        associations = list(
            ProcedureServicePointAssociation.objects.select_for_update()
            .select_related("service_point_version__service_point")
            .prefetch_related("evidence_links__source_links__source")
            .filter(procedure_version=context.version)
            .order_by("pk")
        )
        material_ids = sorted({item.service_point_version_id for item in associations})
        materials = list(
            ServicePointVersion.objects.select_for_update()
            .select_related("service_point")
            .prefetch_related("evidence_links__source_links__source")
            .filter(pk__in=material_ids)
            .order_by("pk")
        )
        list(
            ServicePoint.objects.select_for_update()
            .filter(pk__in={item.service_point_id for item in materials})
            .order_by("pk")
        )
        links = list(
            EvidenceLink.objects.select_for_update()
            .filter(
                Q(procedure_service_point_association_id__in=[item.pk for item in associations])
                | Q(service_point_version_id__in=material_ids)
            )
            .order_by("pk")
        )
        source_ids = list(
            EvidenceLinkSource.objects.select_for_update()
            .filter(evidence_link__in=links)
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
            .filter(pk__in={row[1] for row in source_rows})
            .order_by("pk")
        )

        material_map = {item.pk: item for item in materials}
        checked_material: set[int] = set()
        for association in associations:
            owner = association.semantic_id
            if association.procedure_version_id != context.version.pk:
                failures.append(PublicationDiagnostic(self.name, "invalid_owner", owner))
            if (
                association.effective_from
                and association.effective_to
                and association.effective_from > association.effective_to
            ):
                failures.append(
                    PublicationDiagnostic(self.name, "invalid_effective_interval", owner)
                )
            decoded = decode_stored_rule(association.applicability, context.fact_definitions)
            if association.applicability == {}:
                failures.append(PublicationDiagnostic(self.name, "applicability_required", owner))
            failures.extend(
                PublicationDiagnostic(self.name, item.code, owner) for item in decoded.diagnostics
            )
            if association.verification_state == "current" and association.verified_on is None:
                failures.append(
                    PublicationDiagnostic(
                        self.name, "association_verification_date_required", owner
                    )
                )
            association_links = tuple(association.evidence_links.all())
            adequate, evidence_failures = _complete_support(
                association_links,
                current_claim=association.verification_state == "current",
            )
            failures.extend(evidence_failures)
            if not association_links:
                failures.append(
                    PublicationDiagnostic(self.name, "association_evidence_required", owner)
                )
            elif association.verification_state == "current" and not adequate:
                failures.append(
                    PublicationDiagnostic(
                        self.name, "adequate_association_evidence_required", owner
                    )
                )
            material = material_map.get(association.service_point_version_id)
            if material is None:
                failures.append(
                    PublicationDiagnostic(self.name, "missing_service_point_version", owner)
                )
                continue
            if material.pk in checked_material:
                continue
            checked_material.add(material.pk)
            if (
                not material.service_point.name_ar.strip()
                or not material.service_point.name_en.strip()
            ):
                failures.append(
                    PublicationDiagnostic(
                        self.name, "incomplete_bilingual_identity", material.semantic_id
                    )
                )
            if not material.address_ar.strip() or not material.address_en.strip():
                failures.append(
                    PublicationDiagnostic(
                        self.name, "incomplete_bilingual_address", material.semantic_id
                    )
                )
            if material.availability not in ServicePointVersion.Availability.values:
                failures.append(
                    PublicationDiagnostic(
                        self.name, "unsupported_availability", material.semantic_id
                    )
                )
            if (
                material.effective_from
                and material.effective_to
                and material.effective_from > material.effective_to
            ):
                failures.append(
                    PublicationDiagnostic(
                        self.name, "invalid_material_interval", material.semantic_id
                    )
                )
            if material.verification_state == "current" and material.verified_on is None:
                failures.append(
                    PublicationDiagnostic(
                        self.name, "material_verification_date_required", material.semantic_id
                    )
                )
            if material.verification_state == "current":
                overlaps = (
                    ServicePointVersion.objects.select_for_update()
                    .filter(
                        service_point_id=material.service_point_id,
                        verification_state="current",
                    )
                    .exclude(pk=material.pk)
                )
                if material.effective_to is not None:
                    overlaps = overlaps.filter(
                        Q(effective_from__isnull=True)
                        | Q(effective_from__lte=material.effective_to)
                    )
                if material.effective_from is not None:
                    overlaps = overlaps.filter(
                        Q(effective_to__isnull=True) | Q(effective_to__gte=material.effective_from)
                    )
                if overlaps.exists():
                    failures.append(
                        PublicationDiagnostic(
                            self.name, "overlapping_current_material", material.semantic_id
                        )
                    )
            material_links = tuple(material.evidence_links.all())
            adequate, evidence_failures = _complete_support(
                material_links,
                current_claim=material.verification_state == "current",
            )
            failures.extend(evidence_failures)
            if not material_links:
                failures.append(
                    PublicationDiagnostic(
                        self.name, "material_evidence_required", material.semantic_id
                    )
                )
            elif material.verification_state == "current" and not adequate:
                failures.append(
                    PublicationDiagnostic(
                        self.name, "adequate_material_evidence_required", material.semantic_id
                    )
                )
        return failures


def _source_snapshot(row: dict[str, Any]) -> SourceSnapshot:
    return SourceSnapshot(
        row["source__semantic_id"],
        AuthoritySnapshot(
            row["source__authority__semantic_id"],
            LocalizedText(row["source__authority__name_ar"], row["source__authority__name_en"]),
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
    )


def _snapshot_evidence_is_adequate(links: tuple[EvidenceLinkSnapshot, ...]) -> bool:
    adequate = False
    for link in links:
        if (
            not link.passage.strip()
            or not link.location.strip()
            or not link.applicability_context.strip()
        ):
            return False
        for source in link.sources:
            if source.classification == Source.Classification.FIELD_REPORT and (
                source.observation_date is None or not source.observation_context.strip()
            ):
                return False
        if link.verification_state == "current" and link.support_status == "contradicts":
            return False
        adequate |= (
            link.verification_state == "current"
            and link.support_status == "supports"
            and bool(link.sources)
        )
    return adequate


def _routing_snapshots(snapshot: KnowledgeSnapshot) -> KnowledgeSnapshot:
    associations = cast(
        list[dict[str, Any]],
        list(
            ProcedureServicePointAssociation.objects.filter(
                procedure_version__state__in=("published", "withdrawn")
            )
            .order_by("procedure_version__semantic_id", "semantic_id")
            .values(
                "id",
                "procedure_version__semantic_id",
                "semantic_id",
                "service_point_version_id",
                "applicability",
                "effective_from",
                "effective_to",
                "verification_state",
                "verified_on",
                "reverify_on",
            )
        ),
    )
    material_ids = sorted({row["service_point_version_id"] for row in associations})
    materials = cast(
        list[dict[str, Any]],
        list(
            ServicePointVersion.objects.filter(pk__in=material_ids)
            .order_by("semantic_id")
            .values(
                "id",
                "semantic_id",
                "service_point__semantic_id",
                "service_point__name_ar",
                "service_point__name_en",
                "address_ar",
                "address_en",
                "availability",
                "effective_from",
                "effective_to",
                "verification_state",
                "verified_on",
                "reverify_on",
            )
        ),
    )
    owner_ids = [row["id"] for row in associations]
    evidence = cast(
        list[dict[str, Any]],
        list(
            EvidenceLink.objects.filter(
                Q(procedure_service_point_association_id__in=owner_ids)
                | Q(service_point_version_id__in=material_ids)
            )
            .order_by("id")
            .values(
                "id",
                "semantic_id",
                "procedure_service_point_association_id",
                "service_point_version_id",
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
        ),
    )
    source_rows = cast(
        list[dict[str, Any]],
        list(
            EvidenceLinkSource.objects.filter(evidence_link_id__in=[row["id"] for row in evidence])
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
        ),
    )
    sources: dict[int, list[SourceSnapshot]] = defaultdict(list)
    for row in source_rows:
        sources[row["evidence_link_id"]].append(_source_snapshot(row))
    evidence_assoc: dict[int, list[EvidenceLinkSnapshot]] = defaultdict(list)
    evidence_material: dict[int, list[EvidenceLinkSnapshot]] = defaultdict(list)
    for row in evidence:
        link = EvidenceLinkSnapshot(
            row["passage"],
            row["location"],
            row["applicability_context"],
            row["support_status"],
            cast(VerificationState, row["verification_state"]),
            tuple(sources[row["id"]]),
            row["effective_from"],
            row["effective_to"],
            row["retrieved_on"],
            row["verified_on"],
            row["reverify_on"],
            semantic_id=row["semantic_id"],
        )
        target = (
            evidence_assoc
            if row["procedure_service_point_association_id"] is not None
            else evidence_material
        )
        target[
            row["procedure_service_point_association_id"] or row["service_point_version_id"]
        ].append(link)
    failures: list[StoredRuleLoadDiagnostic] = []
    by_version: dict[str, list[ProcedureServicePointAssociationSnapshot]] = defaultdict(list)
    for row in associations:
        decoded = decode_stored_rule(row["applicability"], snapshot.fact_definitions)
        links = tuple(evidence_assoc[row["id"]])
        if (
            decoded.predicate is None
            or not links
            or any(not link.sources for link in links)
            or (
                row["verification_state"] == "current" and not _snapshot_evidence_is_adequate(links)
            )
        ):
            diagnostics = decoded.diagnostics or (
                ValidationDiagnostic("invalid_routing_evidence", ("evidence",)),
            )
            failures.append(
                StoredRuleLoadDiagnostic(
                    f"service_point_association:{row['procedure_version__semantic_id']}:{row['semantic_id']}",
                    diagnostics,
                )
            )
            continue
        by_version[row["procedure_version__semantic_id"]].append(
            ProcedureServicePointAssociationSnapshot(
                row["semantic_id"],
                next(
                    (
                        item["semantic_id"]
                        for item in materials
                        if item["id"] == row["service_point_version_id"]
                    ),
                    "",
                ),
                decoded.predicate,
                row["effective_from"],
                row["effective_to"],
                cast(VerificationState, row["verification_state"]),
                row["verified_on"],
                row["reverify_on"],
                links,
            )
        )
    material_snapshots: list[ServicePointVersionSnapshot] = []
    point_snapshots: dict[str, ServicePointSnapshot] = {}
    for row in materials:
        links = tuple(evidence_material[row["id"]])
        if (
            not row["address_ar"].strip()
            or not row["address_en"].strip()
            or row["availability"] not in ServicePointVersion.Availability.values
            or not links
            or any(not link.sources for link in links)
            or (
                row["verification_state"] == "current" and not _snapshot_evidence_is_adequate(links)
            )
        ):
            failures.append(
                StoredRuleLoadDiagnostic(
                    f"service_point_version:{row['semantic_id']}",
                    (ValidationDiagnostic("invalid_service_point_material", ()),),
                )
            )
            continue
        point_snapshots[row["service_point__semantic_id"]] = ServicePointSnapshot(
            row["service_point__semantic_id"],
            LocalizedText(row["service_point__name_ar"], row["service_point__name_en"]),
        )
        material_snapshots.append(
            ServicePointVersionSnapshot(
                row["semantic_id"],
                row["service_point__semantic_id"],
                LocalizedText(row["address_ar"], row["address_en"]),
                row["availability"],
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
            replace(version, service_point_associations=tuple(by_version[version.semantic_id]))
            for version in snapshot.procedure_versions
        ),
        tuple(point_snapshots[key] for key in sorted(point_snapshots)),
        tuple(material_snapshots),
    )


_original_materialize = knowledge_domain._materialize_knowledge_snapshot


def _materialize_with_routing() -> KnowledgeSnapshot:
    return _routing_snapshots(_original_materialize())


knowledge_domain._materialize_knowledge_snapshot = _materialize_with_routing

__all__ = (
    "ProcedureServicePointAssociation",
    "ServicePoint",
    "ServicePointRoutingPublicationGate",
    "ServicePointVersion",
)
