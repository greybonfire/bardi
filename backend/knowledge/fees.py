"""Structured Fee persistence and publication policy for issue #42.

Fee is kept in a focused module while remaining a first-class model in the ``knowledge``
app. ``install_fee_evidence_owner`` extends the shared EvidenceLink owner union so Fees use
the same provenance aggregate as Checklist Items, Steps, and administrative Warnings.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from planning.trust import VERIFICATION_CHOICES

from .models import (
    Authority,
    EligibilityBasis,
    EvidenceLink,
    EvidenceLinkSource,
    ProcedureVersion,
    Source,
    VersionOwnedModel,
    Warning,
    _required,
)
from .publication import PublicationContext, PublicationDiagnostic


class Fee(VersionOwnedModel):
    class ValueState(models.TextChoices):
        KNOWN = "known", "Known"
        RANGE = "range", "Range"
        UNKNOWN = "unknown", "Unknown"
        UNVERIFIED = "unverified", "Unverified"

    class Scope(models.TextChoices):
        PROCEDURE = "procedure", "Entire procedure"
        ELIGIBILITY_BASIS = "eligibility_basis", "Eligibility basis"

    procedure_version = models.ForeignKey(
        ProcedureVersion, on_delete=models.CASCADE, related_name="fees"
    )
    semantic_id = models.CharField(max_length=128)
    text_ar = models.TextField()
    text_en = models.TextField()
    value_state = models.CharField(max_length=16, choices=ValueState.choices)
    amount = models.PositiveBigIntegerField(null=True, blank=True)
    minimum_amount = models.PositiveBigIntegerField(null=True, blank=True)
    maximum_amount = models.PositiveBigIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=16)
    fee_type = models.CharField(max_length=64, default="service_fee")
    display_order = models.PositiveIntegerField(default=0)
    applicability = models.JSONField(default=dict, blank=True)
    scope = models.CharField(max_length=24, choices=Scope.choices, default=Scope.PROCEDURE)
    eligibility_basis = models.ForeignKey(
        EligibilityBasis,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fees",
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    reverify_on = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=24, choices=VERIFICATION_CHOICES, default="unknown"
    )

    class Meta:
        app_label = "knowledge"
        ordering = ("procedure_version_id", "display_order", "semantic_id")
        constraints = [
            models.UniqueConstraint(
                fields=("procedure_version", "semantic_id"), name="unique_fee_id_per_version"
            ),
            models.CheckConstraint(
                condition=Q(semantic_id__regex=r".*[^[:space:]].*"), name="fee_id_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_ar__regex=r".*[^[:space:]].*"), name="fee_ar_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(text_en__regex=r".*[^[:space:]].*"), name="fee_en_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(currency__regex=r".*[^[:space:]].*"), name="fee_currency_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(fee_type__regex=r".*[^[:space:]].*"), name="fee_type_nonblank"
            ),
            models.CheckConstraint(
                condition=Q(value_state__in=["known", "range", "unknown", "unverified"]),
                name="fee_value_state_supported",
            ),
            models.CheckConstraint(
                condition=Q(scope="procedure", eligibility_basis__isnull=True)
                | Q(scope="eligibility_basis", eligibility_basis__isnull=False),
                name="fee_scope_combination",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_from__lte=F("effective_to")),
                name="fee_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(verification_state__in=[choice[0] for choice in VERIFICATION_CHOICES]),
                name="fee_verification_supported",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        value_state="known",
                        amount__isnull=False,
                        minimum_amount__isnull=True,
                        maximum_amount__isnull=True,
                    )
                    | Q(
                        value_state="range",
                        amount__isnull=True,
                        minimum_amount__isnull=False,
                        maximum_amount__isnull=False,
                        minimum_amount__lte=F("maximum_amount"),
                    )
                    | Q(
                        value_state="unknown",
                        amount__isnull=True,
                        minimum_amount__isnull=True,
                        maximum_amount__isnull=True,
                    )
                    | (
                        Q(
                            value_state="unverified",
                            verification_state__in=[
                                "needs_reverification",
                                "stale",
                                "disputed",
                            ],
                        )
                        & (
                            Q(
                                amount__isnull=False,
                                minimum_amount__isnull=True,
                                maximum_amount__isnull=True,
                            )
                            | Q(
                                amount__isnull=True,
                                minimum_amount__isnull=False,
                                maximum_amount__isnull=False,
                                minimum_amount__lte=F("maximum_amount"),
                            )
                        )
                    )
                ),
                name="fee_value_shape",
            ),
        ]

    def owning_version(self) -> ProcedureVersion:
        return self.procedure_version

    def clean(self) -> None:
        for field in ("semantic_id", "text_ar", "text_en", "currency", "fee_type"):
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

        amount_ok = self.amount is not None and self.amount >= 0
        range_ok = (
            self.minimum_amount is not None
            and self.maximum_amount is not None
            and self.minimum_amount >= 0
            and self.maximum_amount >= self.minimum_amount
        )
        errors: dict[str, str] = {}
        if self.value_state == self.ValueState.KNOWN:
            if not amount_ok or self.minimum_amount is not None or self.maximum_amount is not None:
                errors["value_state"] = "Known Fees require exactly one nonnegative amount."
        elif self.value_state == self.ValueState.RANGE:
            if self.amount is not None or not range_ok:
                errors["value_state"] = "Range Fees require an ordered nonnegative minimum/maximum."
        elif self.value_state == self.ValueState.UNKNOWN:
            if any(
                value is not None
                for value in (self.amount, self.minimum_amount, self.maximum_amount)
            ):
                errors["value_state"] = "Unknown Fees cannot assert a monetary value."
        elif self.value_state == self.ValueState.UNVERIFIED:
            if not (amount_ok or range_ok):
                errors["value_state"] = "Unverified Fees require a researched amount or range."
            elif amount_ok and (self.minimum_amount is not None or self.maximum_amount is not None):
                errors["value_state"] = "Unverified Fees must use one amount shape only."
            if self.verification_state not in {
                "needs_reverification",
                "stale",
                "disputed",
            }:
                errors["verification_state"] = (
                    "Unverified Fees require needs_reverification, stale, or disputed trust."
                )
        else:
            errors["value_state"] = "Unsupported Fee value state."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.procedure_version.semantic_id}:{self.semantic_id}"


def _install_fee_evidence_owner() -> None:
    """Extend the shared EvidenceLink owner union with Fee exactly once."""
    if any(field.name == "fee" for field in EvidenceLink._meta.fields):
        return

    EvidenceLink.add_to_class(
        "fee",
        models.ForeignKey(
            Fee,
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
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=False,
                    warning__isnull=True,
                    fee__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=False,
                    fee__isnull=True,
                )
                | Q(
                    checklist_item__isnull=True,
                    step__isnull=True,
                    warning__isnull=True,
                    fee__isnull=False,
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
        )
        if link.pk is not None:
            stored = (
                type(link)
                .objects.filter(pk=link.pk)
                .values_list("checklist_item_id", "step_id", "warning_id", "fee_id")
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


_install_fee_evidence_owner()


def _valid_value_shape(fee: Fee) -> bool:
    amount_ok = fee.amount is not None and fee.amount >= 0
    range_ok = (
        fee.minimum_amount is not None
        and fee.maximum_amount is not None
        and fee.minimum_amount >= 0
        and fee.maximum_amount >= fee.minimum_amount
    )
    if fee.value_state == Fee.ValueState.KNOWN:
        return amount_ok and fee.minimum_amount is None and fee.maximum_amount is None
    if fee.value_state == Fee.ValueState.RANGE:
        return fee.amount is None and range_ok
    if fee.value_state == Fee.ValueState.UNKNOWN:
        return fee.amount is None and fee.minimum_amount is None and fee.maximum_amount is None
    if fee.value_state == Fee.ValueState.UNVERIFIED:
        exact_shape = (amount_ok and fee.minimum_amount is None and fee.maximum_amount is None) or (
            fee.amount is None and range_ok
        )
        return exact_shape and fee.verification_state in {
            "needs_reverification",
            "stale",
            "disputed",
        }
    return False


class FeePublicationGate:
    """Validate and lock the complete Fee/evidence aggregate before publication."""

    name = "core.fees"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        failures: list[PublicationDiagnostic] = []
        fee_ids = list(
            Fee.objects.select_for_update()
            .filter(procedure_version=context.version)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        link_ids = list(
            EvidenceLink.objects.select_for_update()
            .filter(fee_id__in=fee_ids)
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

        fees = list(
            Fee.objects.select_related("eligibility_basis")
            .prefetch_related("evidence_links__source_links__source")
            .filter(pk__in=fee_ids)
            .order_by("display_order", "semantic_id")
        )
        if fees:
            regeneration_count = context.version.warnings.filter(
                role=Warning.Role.REGENERATION
            ).count()
            if regeneration_count != 1:
                failures.append(
                    PublicationDiagnostic(
                        self.name,
                        "exactly_one_regeneration_warning_required",
                        context.version.semantic_id,
                    )
                )

        from .domain import decode_stored_rule

        for fee in fees:
            owner_id = fee.semantic_id
            if not fee.text_ar.strip() or not fee.text_en.strip():
                failures.append(
                    PublicationDiagnostic(self.name, "incomplete_bilingual_fee", owner_id)
                )
            if not fee.currency.strip():
                failures.append(PublicationDiagnostic(self.name, "missing_currency", owner_id))
            if not fee.fee_type.strip():
                failures.append(PublicationDiagnostic(self.name, "missing_fee_type", owner_id))
            if not _valid_value_shape(fee):
                failures.append(PublicationDiagnostic(self.name, "invalid_value_state", owner_id))
            if fee.effective_from and fee.effective_to and fee.effective_from > fee.effective_to:
                failures.append(
                    PublicationDiagnostic(self.name, "invalid_effective_interval", owner_id)
                )
            if fee.scope == Fee.Scope.ELIGIBILITY_BASIS and (
                fee.eligibility_basis_id is None
                or fee.eligibility_basis is None
                or fee.eligibility_basis.procedure_version_id != context.version.pk
            ):
                failures.append(PublicationDiagnostic(self.name, "invalid_basis_owner", owner_id))
            if fee.applicability != {}:
                decoded = decode_stored_rule(fee.applicability, context.fact_definitions)
                failures.extend(
                    PublicationDiagnostic(self.name, diagnostic.code, owner_id)
                    for diagnostic in decoded.diagnostics
                )

            links = list(fee.evidence_links.all())
            requires_evidence = fee.value_state in {
                Fee.ValueState.KNOWN,
                Fee.ValueState.RANGE,
                Fee.ValueState.UNVERIFIED,
            }
            requires_current_support = (
                fee.value_state in {Fee.ValueState.KNOWN, Fee.ValueState.RANGE}
                and fee.verification_state == "current"
            )
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
                    requires_current_support
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
            if requires_evidence and not links:
                failures.append(PublicationDiagnostic(self.name, "evidence_required", owner_id))
            if requires_current_support and not adequate_current_support:
                failures.append(
                    PublicationDiagnostic(self.name, "adequate_evidence_required", owner_id)
                )
        return failures


__all__ = ("Fee", "FeePublicationGate")
