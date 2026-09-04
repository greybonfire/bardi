"""Canonical atomic lifecycle boundary for immutable Procedure Versions.

Issue #36 installs core structural gates only. Future mandatory readiness gates must be
registered through ``PROCEDURE_VERSION_PUBLICATION_GATES`` and use this same service.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Protocol, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.module_loading import import_string
from planning.facts import FactDefinition as DomainFactDefinition

from .domain import decode_stored_rule, to_domain_fact
from .models import (
    ChecklistItem,
    EvidenceLink,
    EvidenceLinkSource,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    ProcedureVersionAuditEvent,
    Source,
)


@dataclass(frozen=True, slots=True)
class PublicationDiagnostic:
    gate: str
    code: str
    detail: str = ""


class PublicationRejected(Exception):
    def __init__(self, diagnostics: Iterable[PublicationDiagnostic]) -> None:
        self.diagnostics = tuple(
            sorted(diagnostics, key=lambda item: (item.gate, item.code, item.detail))
        )
        super().__init__(", ".join(f"{item.gate}:{item.code}" for item in self.diagnostics))


@dataclass(frozen=True, slots=True)
class PublicationContext:
    version: ProcedureVersion
    actor: models.Model
    fact_definitions: Mapping[str, DomainFactDefinition]


class PublicationGate(Protocol):
    name: str

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]: ...


def _diagnostic(gate: str, code: str, detail: str = "") -> tuple[PublicationDiagnostic, ...]:
    return (PublicationDiagnostic(gate, code, detail),)


def _load_published_fact_definitions() -> Mapping[str, DomainFactDefinition]:
    values = {
        row.key: to_domain_fact(row)
        for row in FactDefinition.objects.filter(is_published=True).order_by("key")
    }
    return MappingProxyType(values)


class StateAndActorGate:
    name = "core.state_actor"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        diagnostics: list[PublicationDiagnostic] = []
        if context.version.state != ProcedureVersion.State.DRAFT:
            diagnostics.append(PublicationDiagnostic(self.name, "version_not_draft"))
        actor = context.actor
        user_model = get_user_model()
        if (
            not isinstance(actor, user_model)
            or actor.pk is None
            or not user_model._default_manager.filter(pk=actor.pk).exists()
        ):
            diagnostics.append(PublicationDiagnostic(self.name, "invalid_actor"))
        return diagnostics


class OwnershipGate:
    name = "core.ownership"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        version = context.version
        procedure = version.procedure
        if not procedure.service_candidates.filter(
            service_id=procedure.primary_service_id
        ).exists():
            return _diagnostic(self.name, "missing_curated_service_candidate")
        return ()


class IdentityGate:
    name = "core.identity"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        semantic_id = context.version.semantic_id
        if not semantic_id or not semantic_id.strip():
            return _diagnostic(self.name, "blank_semantic_id")
        if (
            ProcedureVersion.objects.filter(semantic_id=semantic_id)
            .exclude(pk=context.version.pk)
            .exists()
        ):
            return _diagnostic(self.name, "duplicate_semantic_id")
        return ()


class BilingualCompletenessGate:
    name = "core.bilingual"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        diagnostics: list[PublicationDiagnostic] = []
        if not context.version.text_ar.strip():
            diagnostics.append(PublicationDiagnostic(self.name, "missing_arabic_text"))
        if not context.version.text_en.strip():
            diagnostics.append(PublicationDiagnostic(self.name, "missing_english_text"))
        return diagnostics


class RulesContractGate:
    name = "core.rules_contract"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        if context.version.rules_contract_version != "v1":
            return _diagnostic(self.name, "unsupported_rules_contract")
        return ()


class ApplicabilityGate:
    name = "core.applicability"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        decoded = decode_stored_rule(context.version.applicability, context.fact_definitions)
        return tuple(
            PublicationDiagnostic(self.name, diagnostic.code) for diagnostic in decoded.diagnostics
        )


class TemporalGate:
    name = "core.temporal"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        start = context.version.effective_from
        end = context.version.effective_to
        if start is not None and type(start) is not date:
            return _diagnostic(self.name, "invalid_effective_from")
        if end is not None and type(end) is not date:
            return _diagnostic(self.name, "invalid_effective_to")
        if start is not None and end is not None and start > end:
            return _diagnostic(self.name, "invalid_effective_interval")
        return ()


def _overlap_queryset(version: ProcedureVersion) -> models.QuerySet[ProcedureVersion]:
    candidates = ProcedureVersion.objects.filter(
        procedure_id=version.procedure_id, state=ProcedureVersion.State.PUBLISHED
    ).exclude(pk=version.pk)
    if version.effective_to is not None:
        candidates = candidates.filter(
            Q(effective_from__isnull=True) | Q(effective_from__lte=version.effective_to)
        )
    if version.effective_from is not None:
        candidates = candidates.filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=version.effective_from)
        )
    return candidates.order_by("semantic_id")


class ChecklistEvidenceGate:
    name = "core.checklist_evidence"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        failures: list[PublicationDiagnostic] = []
        items = context.version.checklist_items.prefetch_related(
            "evidence_links__source_links__source"
        ).order_by("display_order", "semantic_id")
        for item in items:
            owner = item.semantic_id
            if not item.text_ar.strip() or not item.text_en.strip():
                failures.append(
                    PublicationDiagnostic(self.name, "incomplete_bilingual_claim", owner)
                )
            if item.quantity < 1:
                failures.append(PublicationDiagnostic(self.name, "invalid_quantity", owner))
            if item.applicability != {}:
                decoded = decode_stored_rule(item.applicability, context.fact_definitions)
                for diagnostic in decoded.diagnostics:
                    failures.append(PublicationDiagnostic(self.name, diagnostic.code, owner))
            links = list(item.evidence_links.all())
            adequate_support = False
            authoritative = False
            for link in links:
                detail = f"{owner}:{link.pk}"
                sources = [row.source for row in link.source_links.all()]
                has_complete_context = bool(
                    sources
                    and link.passage.strip()
                    and link.location.strip()
                    and link.applicability_context.strip()
                )
                supports_current_claim = (
                    link.support_status == EvidenceLink.SupportStatus.SUPPORTS
                    and link.verification_state == "current"
                    and has_complete_context
                )
                adequate_support = adequate_support or supports_current_claim
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
                if supports_current_claim and all(
                    source.classification == Source.Classification.OFFICIAL for source in sources
                ):
                    authoritative = True
                if item.classification == ChecklistItem.Classification.PRACTICAL_PREPARATION:
                    for source in sources:
                        if source.classification == Source.Classification.FIELD_REPORT and (
                            source.observation_date is None
                            or not source.observation_context.strip()
                        ):
                            failures.append(
                                PublicationDiagnostic(self.name, "malformed_field_guidance", detail)
                            )
            if item.verification_state == "current":
                if not links:
                    failures.append(
                        PublicationDiagnostic(self.name, "missing_evidence_link", owner)
                    )
                elif not adequate_support:
                    failures.append(
                        PublicationDiagnostic(self.name, "adequate_evidence_required", owner)
                    )
            if (
                item.classification == ChecklistItem.Classification.OFFICIAL_REQUIREMENT
                and links
                and not authoritative
            ):
                failures.append(
                    PublicationDiagnostic(self.name, "official_evidence_required", owner)
                )
        return failures


class TemporalOverlapGate:
    name = "core.temporal_overlap"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        conflicts = tuple(_overlap_queryset(context.version).values_list("semantic_id", flat=True))
        if conflicts:
            return _diagnostic(self.name, "overlapping_published_version", ",".join(conflicts))
        return ()


_CORE_GATES: tuple[PublicationGate, ...] = (
    StateAndActorGate(),
    OwnershipGate(),
    IdentityGate(),
    BilingualCompletenessGate(),
    RulesContractGate(),
    ApplicabilityGate(),
    ChecklistEvidenceGate(),
    TemporalGate(),
    TemporalOverlapGate(),
)


def _configured_gates() -> tuple[tuple[PublicationGate, ...], tuple[PublicationDiagnostic, ...]]:
    configured = getattr(settings, "PROCEDURE_VERSION_PUBLICATION_GATES", ())
    diagnostics: list[PublicationDiagnostic] = []
    loaded: list[PublicationGate] = []
    if isinstance(configured, str) or not isinstance(configured, (list, tuple)):
        return (), _diagnostic("policy", "invalid_gate_configuration")
    for position, path in enumerate(configured):
        if not isinstance(path, str) or not path.strip():
            diagnostics.append(
                PublicationDiagnostic("policy", "missing_configured_gate", str(position))
            )
            continue
        try:
            candidate = import_string(path)
            gate = candidate() if isinstance(candidate, type) else candidate
            name = gate.name
            validate = gate.validate
            if not isinstance(name, str) or not name.strip() or not callable(validate):
                raise TypeError("invalid gate")
            loaded.append(cast(PublicationGate, gate))
        except Exception:
            diagnostics.append(PublicationDiagnostic("policy", "gate_load_failed", path))
    names = [gate.name for gate in (*_CORE_GATES, *loaded)]
    for name in sorted({name for name in names if names.count(name) > 1}):
        diagnostics.append(PublicationDiagnostic("policy", "duplicate_gate_name", name))
    return tuple(loaded), tuple(diagnostics)


def _run_policy(context: PublicationContext) -> tuple[PublicationDiagnostic, ...]:
    extension_gates, diagnostics = _configured_gates()
    failures = list(diagnostics)
    for gate in (*_CORE_GATES, *extension_gates):
        try:
            result = tuple(gate.validate(context))
            if any(not isinstance(item, PublicationDiagnostic) for item in result):
                raise TypeError("invalid gate result")
            failures.extend(result)
        except Exception:
            failures.append(PublicationDiagnostic(gate.name, "gate_execution_failed"))
    return tuple(sorted(failures, key=lambda item: (item.gate, item.code, item.detail)))


def _enable_transition(name: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('bardi.procedure_version_lifecycle', %s, true)", [name])


def _create_audit_event(
    version: ProcedureVersion,
    *,
    event_type: str,
    actor: models.Model,
    occurred_at: datetime,
    from_state: str,
    to_state: str,
) -> None:
    table = ProcedureVersionAuditEvent._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f'INSERT INTO "{table}" '
            "(version_id, event_type, actor_id, occurred_at, from_state, to_state) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [version.pk, event_type, actor.pk, occurred_at, from_state, to_state],
        )


def publish_procedure_version(version_id: int, *, actor: models.Model) -> ProcedureVersion:
    """Validate and atomically publish one freshly locked draft."""

    try:
        with transaction.atomic():
            version = (
                ProcedureVersion.objects.select_for_update()
                .select_related("procedure")
                .get(pk=version_id)
            )
            Procedure.objects.select_for_update().get(pk=version.procedure_id)
            # Lock the complete version-owned aggregate and reusable provenance before gates.
            item_ids = list(
                ChecklistItem.objects.select_for_update()
                .filter(procedure_version=version)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            link_ids = list(
                EvidenceLink.objects.select_for_update()
                .filter(checklist_item_id__in=item_ids)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            source_ids = list(
                EvidenceLinkSource.objects.select_for_update()
                .filter(evidence_link_id__in=link_ids)
                .order_by("pk")
                .values_list("source_id", flat=True)
            )
            list(Source.objects.select_for_update().filter(pk__in=source_ids).order_by("pk"))
            context = PublicationContext(version, actor, _load_published_fact_definitions())
            diagnostics = _run_policy(context)
            if diagnostics:
                raise PublicationRejected(diagnostics)
            published_at = timezone.now()
            _enable_transition("publish")
            updated = ProcedureVersion.objects.filter(
                pk=version.pk, state=ProcedureVersion.State.DRAFT
            ).update(
                state=ProcedureVersion.State.PUBLISHED,
                published_at=published_at,
                published_by_id=actor.pk,
            )
            if updated != 1:
                raise PublicationRejected(_diagnostic("core.state_actor", "version_not_draft"))
            _create_audit_event(
                version,
                event_type=ProcedureVersionAuditEvent.EventType.PUBLISHED,
                actor=actor,
                occurred_at=published_at,
                from_state=ProcedureVersion.State.DRAFT,
                to_state=ProcedureVersion.State.PUBLISHED,
            )
            _enable_transition("")
            version.refresh_from_db()
            return version
    except IntegrityError as exc:
        if "exclude_published_proc_version_overlap" not in str(exc):
            raise
        raise PublicationRejected(
            _diagnostic("core.temporal_overlap", "overlapping_published_version")
        ) from exc


def withdraw_procedure_version(version_id: int, *, actor: models.Model) -> ProcedureVersion:
    """Atomically withdraw a published version without changing its semantics."""

    with transaction.atomic():
        version = ProcedureVersion.objects.select_for_update().get(pk=version_id)
        Procedure.objects.select_for_update().get(pk=version.procedure_id)
        user_model = get_user_model()
        if (
            not isinstance(actor, user_model)
            or actor.pk is None
            or not user_model._default_manager.filter(pk=actor.pk).exists()
        ):
            raise PublicationRejected(_diagnostic("core.state_actor", "invalid_actor"))
        if version.state != ProcedureVersion.State.PUBLISHED:
            raise PublicationRejected(_diagnostic("core.state_actor", "version_not_published"))
        withdrawn_at = timezone.now()
        _enable_transition("withdraw")
        updated = ProcedureVersion.objects.filter(
            pk=version.pk, state=ProcedureVersion.State.PUBLISHED
        ).update(
            state=ProcedureVersion.State.WITHDRAWN,
            withdrawn_at=withdrawn_at,
            withdrawn_by_id=actor.pk,
        )
        if updated != 1:
            raise PublicationRejected(_diagnostic("core.state_actor", "version_not_published"))
        _create_audit_event(
            version,
            event_type=ProcedureVersionAuditEvent.EventType.WITHDRAWN,
            actor=actor,
            occurred_at=withdrawn_at,
            from_state=ProcedureVersion.State.PUBLISHED,
            to_state=ProcedureVersion.State.WITHDRAWN,
        )
        _enable_transition("")
        version.refresh_from_db()
        return version
