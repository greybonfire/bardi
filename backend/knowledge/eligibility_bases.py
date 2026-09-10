"""Eligibility Basis authoring, publication, and snapshot adaptation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from typing import Any, cast

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
from planning.trust import VerificationState

from .domain import (
    KnowledgeSnapshotLoadError,
    StoredRuleLoadDiagnostic,
    decode_stored_rule,
    referenced_fact_keys,
)
from .models import (
    Authority,
    EligibilityBasis,
    EvidenceLink,
    EvidenceLinkSource,
    ProcedureVersion,
    Source,
)
from .publication import PublicationContext, PublicationDiagnostic


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
        for basis_model in bases:
            basis = cast(Any, basis_model)
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
                        PublicationDiagnostic(
                            self.name,
                            diagnostic.code,
                            f"{owner_id}:reachability",
                        )
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
                        PublicationDiagnostic(
                            self.name,
                            diagnostic.code,
                            f"{owner_id}:qualification",
                        )
                        for diagnostic in decoded.diagnostics
                    )
                else:
                    predicates.append(decoded.predicate)

            links = list(basis.evidence_links.all())
            adequate_current_support = False
            for link in links:
                sources = [source_link.source for source_link in link.source_links.all()]
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


def _basis_snapshots(snapshot: KnowledgeSnapshot, *, scope: Any | None = None) -> KnowledgeSnapshot:
    basis_queryset = EligibilityBasis.objects.filter(
        procedure_version__state__in=(
            ProcedureVersion.State.PUBLISHED,
            ProcedureVersion.State.WITHDRAWN,
        )
    )
    if scope is not None:
        basis_queryset = basis_queryset.filter(procedure_version_id__in=scope.version_ids)
    basis_rows = list(
        basis_queryset.order_by(
            "procedure_version__semantic_id", "display_order", "semantic_id"
        ).values(
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
        EvidenceLink.objects.filter(
            eligibility_basis_id__in=[basis_row["id"] for basis_row in basis_rows]
        )
        .order_by("id")
        .values(
            "id",
            "semantic_id",
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
        EvidenceLinkSource.objects.filter(
            evidence_link_id__in=[evidence_row["id"] for evidence_row in evidence_rows]
        )
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
    for source_row in evidence_source_rows:
        source_id = source_row["source__semantic_id"]
        source = source_snapshots.setdefault(
            source_id,
            SourceSnapshot(
                source_id,
                AuthoritySnapshot(
                    source_row["source__authority__semantic_id"],
                    LocalizedText(
                        source_row["source__authority__name_ar"],
                        source_row["source__authority__name_en"],
                    ),
                ),
                source_row["source__title"],
                source_row["source__locator"],
                source_row["source__classification"],
                source_row["source__retrieved_on"],
                source_row["source__published_on"],
                source_row["source__effective_from"],
                source_row["source__effective_to"],
                source_row["source__reverify_on"],
                source_row["source__observation_date"],
                source_row["source__observation_context"],
            ),
        )
        sources_by_link[source_row["evidence_link_id"]].append(source)

    evidence_by_basis: dict[int, list[EvidenceLinkSnapshot]] = defaultdict(list)
    for evidence_row in cast(list[dict[str, Any]], evidence_rows):
        evidence_by_basis[evidence_row["eligibility_basis_id"]].append(
            EvidenceLinkSnapshot(
                evidence_row["passage"],
                evidence_row["location"],
                evidence_row["applicability_context"],
                evidence_row["support_status"],
                cast(VerificationState, evidence_row["verification_state"]),
                tuple(sources_by_link[evidence_row["id"]]),
                evidence_row["effective_from"],
                evidence_row["effective_to"],
                evidence_row["retrieved_on"],
                evidence_row["verified_on"],
                evidence_row["reverify_on"],
                semantic_id=evidence_row["semantic_id"],
            )
        )

    failures: list[StoredRuleLoadDiagnostic] = []
    by_version: dict[str, list[EligibilityBasisSnapshot]] = defaultdict(list)
    for basis_row in cast(list[dict[str, Any]], basis_rows):
        owner = (
            f"eligibility_basis:{basis_row['procedure_version__semantic_id']}:"
            f"{basis_row['semantic_id']}"
        )
        reachability: Predicate | None = None
        if basis_row["reachability"] != {}:
            decoded = decode_stored_rule(basis_row["reachability"], snapshot.fact_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
            reachability = decoded.predicate
        if basis_row["qualification"] == {}:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    (ValidationDiagnostic("missing_qualification", ("qualification",)),),
                )
            )
            continue
        decoded = decode_stored_rule(basis_row["qualification"], snapshot.fact_definitions)
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue
        links = tuple(evidence_by_basis[basis_row["id"]])
        invalid = (
            not basis_row["text_ar"].strip()
            or not basis_row["text_en"].strip()
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
        by_version[basis_row["procedure_version__semantic_id"]].append(
            EligibilityBasisSnapshot(
                basis_row["semantic_id"],
                LocalizedText(basis_row["text_ar"], basis_row["text_en"]),
                reachability,
                decoded.predicate,
                basis_row["display_order"],
                basis_row["effective_from"],
                basis_row["effective_to"],
                cast(VerificationState, basis_row["verification_state"]),
                basis_row["verified_on"],
                basis_row["reverify_on"],
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


__all__ = ("EligibilityBasisPublicationGate",)