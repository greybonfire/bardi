"""Coherent authoring snapshots, including protected trust and workflow state."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any, NoReturn

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.db.models import Q, QuerySet

from knowledge import models as m
from knowledge.evidence_workflow import (
    EvidenceDiscrepancy,
    EvidenceDiscrepancyEvidence,
    EvidenceReverificationEvent,
    EvidenceReverificationEvidence,
)
from knowledge.evidence_workflow_temporal import EvidenceDiscrepancyTransition
from knowledge.fees import Fee
from knowledge.planning_scenarios import PlanningScenario
from knowledge.procedure_dependencies import ProcedureDependency
from knowledge.review_workflow import (
    ProcedureVersionAuditApproval,
    ProcedureVersionReviewApproval,
    ProcedureVersionReviewPolicy,
)
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)

from .mapping import OWNED

# Fixed allowlist, not app-registry discovery or uploaded labels. Row-only locks cannot
# exclude ordinary Admin inserts. NOWAIT also avoids publisher row -> table deadlocks.
LOCK_MODELS = (
    m.Service,
    m.Procedure,
    m.ProcedureVersion,
    m.FactDefinition,
    m.ServiceProcedureCandidate,
    m.ServiceQuestion,
    m.ServiceQuestionResolvedFact,
    m.ServiceContradiction,
    m.ServiceContradictionFact,
    m.Authority,
    m.DocumentType,
    m.Source,
    m.EligibilityBasis,
    m.ChecklistItem,
    m.Step,
    m.Warning,
    Fee,
    ProcedureDependency,
    ServicePoint,
    ServicePointVersion,
    ProcedureServicePointAssociation,
    m.EvidenceLink,
    m.EvidenceLinkSource,
    EvidenceDiscrepancy,
    EvidenceDiscrepancyEvidence,
    EvidenceDiscrepancyTransition,
    EvidenceReverificationEvent,
    EvidenceReverificationEvidence,
    PlanningScenario,
    ProcedureVersionReviewPolicy,
    ProcedureVersionReviewApproval,
    m.ProcedureVersionAuditEvent,
    ProcedureVersionAuditApproval,
    m.DraftPackImportReceipt,
)


def fail(code: str, path: tuple[str | int, ...], message: str) -> NoReturn:
    from .errors import Diagnostic, DraftPackError

    raise DraftPackError((Diagnostic(code, path, message),))


def actor_for(actor: Any, permission: str) -> Any:
    pk = getattr(actor, "pk", None)
    if not isinstance(actor, get_user_model()) or pk is None:
        fail("permission_denied", (), "A persisted staff actor is required.")
    # Keep the freshly authorized FK target protected through the outer commit.
    user = get_user_model()._default_manager.select_for_update(nowait=True).filter(pk=pk).first()
    if user is None or not user.is_active or not user.is_staff or not user.has_perm(permission):
        fail(
            "permission_denied", (), "An active staff actor with the required permission is needed."
        )
    return user


def require_add(actor: Any, model: Any, path: tuple[str | int, ...]) -> None:
    if not actor.has_perm(f"knowledge.add_{model._meta.model_name}"):
        fail("permission_denied", path, "Creation requires the catalog or setup add permission.")


@contextmanager
def locked_snapshot() -> Iterator[None]:
    nested = connection.in_atomic_block
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            previous = cursor.fetchone()[0]
            cursor.execute("SELECT set_config('lock_timeout', '750ms', true)")
        try:
            with connection.cursor() as cursor:
                names = ", ".join(
                    connection.ops.quote_name(model._meta.db_table) for model in LOCK_MODELS
                )
                cursor.execute(f"LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE NOWAIT")
                # Deferred FK checks may run after this savepoint releases and its
                # timeout is restored. Protect every existing knowledge FK target
                # until outer commit; table locks exclude new concurrent targets.
                # Fixed table -> row -> actor ordering, all NOWAIT, cannot wait in
                # a cycle with publishers that acquire row locks before writing.
                for model in LOCK_MODELS:
                    table = connection.ops.quote_name(model._meta.db_table)
                    column = model._meta.pk.column
                    assert column is not None
                    pk = connection.ops.quote_name(column)
                    cursor.execute(f"SELECT {pk} FROM {table} ORDER BY {pk} FOR KEY SHARE NOWAIT")
                    cursor.fetchall()
            yield
        except BaseException:
            # atomic rolls back SET LOCAL along with the failed transaction/savepoint.
            raise
        else:
            # Outermost SET LOCAL expires at commit, including deferred checks.
            # Nested callers regain their setting without changing constraint modes;
            # the key-share/actor locks above still protect deferred FK checks.
            if nested and not connection.needs_rollback:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('lock_timeout', %s, true)", [previous])


class _RevisionEncoder(DjangoJSONEncoder):
    def default(self, value: Any) -> Any:
        if isinstance(value, date):
            # Django's default datetime encoder truncates microseconds. A complete
            # revision must retain all persisted workflow/approval timestamp bits.
            return value.isoformat()
        return super().default(value)


def json_equal(left: Any, right: Any) -> bool:
    """Canonical JSON equality keeps booleans, integers and floats distinct."""
    return json.dumps(left, sort_keys=True, cls=_RevisionEncoder) == json.dumps(
        right, sort_keys=True, cls=_RevisionEncoder
    )


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), cls=_RevisionEncoder
        ).encode()
    ).hexdigest()


def evidence_for(version: Any) -> QuerySet[m.EvidenceLink]:
    query = Q(pk__in=[])
    for spec in OWNED.values():
        if spec.owner_kind:
            query |= Q(**{f"{spec.owner_kind}__procedure_version": version})
    return m.EvidenceLink.objects.filter(query)


def revision(version: Any) -> str:
    """All concrete fields, not the semantic-only review/planning signatures.

    Shared registries and dependency edges are conservatively complete. Unrelated
    version-owned claims, scenarios and workflow records are deliberately excluded.
    """
    payload: dict[str, Any] = {"target_version": version.pk}
    # Prerequisite behavior can depend on its Bases/claims/trust, not just edge rows.
    # Include all temporal versions in the reachable Procedure closure, but no
    # unrelated version-owned aggregates. Cycles terminate without recursion.
    edges: dict[int, set[int]] = {}
    for source, target in ProcedureDependency.objects.values_list(
        "procedure_version__procedure_id", "target_procedure_id"
    ):
        edges.setdefault(source, set()).add(target)
    procedures: set[int] = set()
    pending = [version.procedure_id]
    while pending:
        procedure_id = pending.pop()
        if procedure_id not in procedures:
            procedures.add(procedure_id)
            pending.extend(edges.get(procedure_id, ()))
    version_ids = list(
        m.ProcedureVersion.objects.filter(procedure_id__in=procedures).values_list("pk", flat=True)
    )

    def include(model: Any, rows: Any) -> None:
        payload[model._meta.label_lower] = list(rows.order_by("pk").values())

    for model in (
        m.Service,
        m.Procedure,
        m.FactDefinition,
        m.Authority,
        m.DocumentType,
        m.Source,
        m.ServiceQuestion,
        m.ServiceQuestionResolvedFact,
        m.ServiceProcedureCandidate,
        m.ServiceContradiction,
        m.ServiceContradictionFact,
        ServicePoint,
        ServicePointVersion,
        ProcedureDependency,
    ):
        include(model, model.objects.all())
    # Version metadata participates in the dependency graph and lifecycle safety.
    include(m.ProcedureVersion, m.ProcedureVersion.objects.all())
    for spec in OWNED.values():
        if spec.model is not ProcedureDependency:
            include(spec.model, spec.model.objects.filter(procedure_version_id__in=version_ids))
    evidence_query = Q(service_point_version__isnull=False)
    for spec in OWNED.values():
        if spec.owner_kind:
            evidence_query |= Q(**{f"{spec.owner_kind}__procedure_version_id__in": version_ids})
    links = m.EvidenceLink.objects.filter(evidence_query)
    include(m.EvidenceLink, links)
    include(m.EvidenceLinkSource, m.EvidenceLinkSource.objects.filter(evidence_link__in=links))
    discrepancies = EvidenceDiscrepancy.objects.filter(
        Q(anchor_evidence_link__in=links) | Q(evidence_rows__evidence_link__in=links)
    ).distinct()
    events = EvidenceReverificationEvent.objects.filter(
        Q(anchor_evidence_link__in=links)
        | Q(evidence_rows__evidence_link__in=links)
        | Q(successor_version_id__in=version_ids)
    ).distinct()
    include(EvidenceDiscrepancy, discrepancies)
    include(
        EvidenceDiscrepancyEvidence,
        EvidenceDiscrepancyEvidence.objects.filter(discrepancy__in=discrepancies),
    )
    include(
        EvidenceDiscrepancyTransition,
        EvidenceDiscrepancyTransition.objects.filter(discrepancy__in=discrepancies),
    )
    include(EvidenceReverificationEvent, events)
    include(
        EvidenceReverificationEvidence,
        EvidenceReverificationEvidence.objects.filter(event__in=events),
    )
    for review_model in (ProcedureVersionReviewPolicy, ProcedureVersionReviewApproval):
        include(review_model, review_model.objects.filter(procedure_version_id__in=version_ids))
    audits = m.ProcedureVersionAuditEvent.objects.filter(version_id__in=version_ids)
    include(m.ProcedureVersionAuditEvent, audits)
    include(
        ProcedureVersionAuditApproval,
        ProcedureVersionAuditApproval.objects.filter(audit_event__in=audits),
    )
    return digest(payload)
