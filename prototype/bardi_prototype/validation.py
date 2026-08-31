from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from .contracts import (
    FactDefinition,
    KnowledgeBundle,
    KnowledgeCatalog,
    LocalizedText,
    Predicate,
    VerificationPathDefinition,
)
from .versions import bundles_for_procedure, version_collection_conflicts
from .evaluator import validate_predicate
from .facts import FACT_DEFINITIONS


def _bundle_rules(bundle: KnowledgeBundle) -> Iterable[Predicate | None]:
    yield bundle.procedure.applicability
    for basis in bundle.eligibility_bases:
        yield basis.applicability
        yield basis.qualification
    for item in bundle.claims:
        yield item.applicability
    for item in bundle.steps:
        yield item.applicability
    for item in bundle.fees:
        yield item.applicability
    for dependency in bundle.dependencies:
        yield dependency.applicability
        yield dependency.satisfied_when
    for association in bundle.service_point_associations:
        yield association.applicability
    for item in bundle.unknowns:
        yield item.applicability


def _predicate_fact_keys(predicate: Predicate) -> frozenset[str]:
    keys: set[str] = set()
    if predicate.fact is not None:
        keys.add(predicate.fact)
    for child in predicate.children:
        keys.update(_predicate_fact_keys(child))
    return frozenset(keys)


def _localized_complete(text: LocalizedText) -> bool:
    return bool(text.ar.strip() and text.en.strip())


def _validate_evidence(
    bundle: KnowledgeBundle,
    owner: str,
    evidence_link_ids: tuple[str, ...],
    *,
    required: bool,
) -> list[str]:
    diagnostics: list[str] = []
    if required and not evidence_link_ids:
        diagnostics.append(f"missing_claim_specific_evidence:{owner}")
    for link_id in evidence_link_ids:
        link = bundle.evidence_links.get(link_id)
        if link is None:
            diagnostics.append(f"unknown_evidence_link:{owner}:{link_id}")
            continue
        if not link.source_ids:
            diagnostics.append(f"evidence_link_without_source:{link_id}")
        # Passage/context are optional research metadata: a missing value is
        # an explicit unknown, not permission to fabricate a placeholder. If
        # supplied, however, a passage must contain non-whitespace text.
        if link.exact_passage is not None and not link.exact_passage.strip():
            diagnostics.append(f"empty_evidence_passage:{link_id}")
        if link.verification_state not in {
            "current", "needs_reverification", "stale", "disputed", "unknown"
        }:
            diagnostics.append(f"unsupported_evidence_verification_state:{link_id}")
        for metadata_name in (
            "retrieved_on", "effective_from", "effective_to", "reverification_due_on"
        ):
            metadata_value = getattr(link, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_evidence_metadata:{link_id}:{metadata_name}")
        if not _valid_interval(link.effective_from, link.effective_to):
            diagnostics.append(f"invalid_evidence_link_interval:{link_id}")
        for source_id in link.source_ids:
            source = bundle.sources.get(source_id)
            if source is None:
                diagnostics.append(f"unknown_evidence_source:{link_id}:{source_id}")
            elif source.classification == "field_report" and (
                source.observed_on is None
                or source.context is None
                or not source.context.strip()
            ):
                diagnostics.append(f"field_report_missing_context:{source_id}")
    return diagnostics


def _validate_verification_path(
    bundle: KnowledgeBundle,
    path: VerificationPathDefinition | None,
    owner: str,
    *,
    required: bool,
) -> list[str]:
    diagnostics: list[str] = []
    if path is None:
        if required:
            diagnostics.append(f"missing_verification_path:{owner}")
        return diagnostics
    if not _localized_complete(path.text):
        diagnostics.append(f"incomplete_bilingual_text:verification_path:{path.id}")
    diagnostics.extend(
        _validate_evidence(
            bundle,
            f"verification_path:{path.id}",
            path.evidence_link_ids,
            required=True,
        )
    )
    return diagnostics


def _valid_interval(
    effective_from: date | None,
    effective_to: date | None,
) -> bool:
    if effective_from is not None and type(effective_from) is not date:
        return False
    if effective_to is not None and type(effective_to) is not date:
        return False
    return effective_from is None or effective_to is None or effective_from <= effective_to


def _intervals_overlap(
    left_from: date | None,
    left_to: date | None,
    right_from: date | None,
    right_to: date | None,
) -> bool:
    if not _valid_interval(left_from, left_to) or not _valid_interval(right_from, right_to):
        return False
    if left_to is not None and right_from is not None and left_to < right_from:
        return False
    if right_to is not None and left_from is not None and right_to < left_from:
        return False
    return True


SUPPORTED_RULES_CONTRACT_VERSIONS = frozenset({"v1"})


def validate_bundle(
    bundle: KnowledgeBundle,
    fact_definitions: Mapping[str, FactDefinition],
) -> tuple[str, ...]:
    diagnostics: list[str] = []
    procedure = bundle.procedure
    if (
        not isinstance(procedure.rules_contract_version, str)
        or procedure.rules_contract_version not in SUPPORTED_RULES_CONTRACT_VERSIONS
    ):
        diagnostics.append(
            f"unsupported_rules_contract_version:{procedure.version_id}:{procedure.rules_contract_version}"
        )
    if not isinstance(procedure.procedure_id, str) or not procedure.procedure_id.strip():
        diagnostics.append("empty_procedure_id")
    if not isinstance(procedure.version_id, str) or not procedure.version_id.strip():
        diagnostics.append("empty_procedure_version_id")
    if procedure.procedure_id not in bundle.goal.procedure_ids:
        diagnostics.append(
            f"procedure_goal_ownership_mismatch:{procedure.procedure_id}:{bundle.goal.id}"
        )
    if procedure.publication_state not in {"draft", "published", "withdrawn"}:
        diagnostics.append(f"unsupported_publication_state:{procedure.version_id}")
    if procedure.trust_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
        diagnostics.append(f"unsupported_procedure_trust_state:{procedure.version_id}")
    for metadata_name in (
        "verified_on", "published_on", "withdrawn_on", "effective_from", "effective_to",
        "reverification_due_on"
    ):
        metadata_value = getattr(procedure, metadata_name)
        if metadata_value is not None and type(metadata_value) is not date:
            diagnostics.append(
                f"invalid_procedure_version_metadata:{procedure.version_id}:{metadata_name}"
            )
    if not _valid_interval(procedure.effective_from, procedure.effective_to):
        diagnostics.append(f"invalid_procedure_version_interval:{procedure.version_id}")
    if (
        procedure.publication_state == "withdrawn"
        and type(procedure.withdrawn_on) is date
        and (procedure.effective_from is None or type(procedure.effective_from) is date)
        and procedure.withdrawn_on < (procedure.effective_from or date.min)
    ):
        diagnostics.append(f"invalid_withdrawal_date:{procedure.version_id}")
    for rule in _bundle_rules(bundle):
        diagnostics.extend(validate_predicate(rule, fact_definitions))

    if not _localized_complete(bundle.goal.text):
        diagnostics.append(f"incomplete_bilingual_text:goal:{bundle.goal.id}")
    if not _localized_complete(bundle.procedure.text):
        diagnostics.append(
            f"incomplete_bilingual_text:procedure:{bundle.procedure.procedure_id}"
        )

    for source_id, source in bundle.sources.items():
        if source_id != source.id:
            diagnostics.append(f"source_key_mismatch:{source_id}")
        if source.classification not in {"official", "field_report", "secondary"}:
            diagnostics.append(f"unsupported_source_classification:{source_id}")
        if not _valid_interval(source.effective_from, source.effective_to):
            diagnostics.append(f"invalid_source_interval:{source_id}")
        for metadata_name in (
            "retrieved_on", "published_on", "effective_from", "effective_to",
            "observed_on", "reverification_due_on"
        ):
            metadata_value = getattr(source, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_source_metadata:{source_id}:{metadata_name}")
        if source.classification == "field_report" and (
            source.observed_on is None or not source.context or not source.context.strip()
        ):
            diagnostics.append(f"field_report_missing_context:{source_id}")
    for link_id, link in bundle.evidence_links.items():
        if link_id != link.id:
            diagnostics.append(f"evidence_link_key_mismatch:{link_id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"evidence_link:{link_id}",
                (link_id,),
                required=False,
            )
        )

    basis_ids: set[str] = set()
    basis_orders: set[int] = set()
    for basis in bundle.eligibility_bases:
        if basis.id in basis_ids:
            diagnostics.append(f"duplicate_eligibility_basis_id:{basis.id}")
        basis_ids.add(basis.id)
        if basis.qualification is None:
            diagnostics.append(f"missing_basis_qualification:{basis.id}")
        if basis.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_basis_verification_state:{basis.id}")
        for metadata_name in (
            "verified_on", "reverified_on", "effective_from", "effective_to",
            "reverification_due_on"
        ):
            metadata_value = getattr(basis, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_basis_metadata:{basis.id}:{metadata_name}")
        if not _valid_interval(basis.effective_from, basis.effective_to):
            diagnostics.append(f"invalid_basis_interval:{basis.id}")
        if basis.display_order in basis_orders:
            diagnostics.append(f"duplicate_eligibility_basis_order:{basis.display_order}")
        basis_orders.add(basis.display_order)
        if not _localized_complete(basis.text):
            diagnostics.append(f"incomplete_bilingual_text:eligibility_basis:{basis.id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"eligibility_basis:{basis.id}",
                basis.evidence_link_ids,
                required=True,
            )
        )

    if bundle.eligibility_bases:
        if bundle.no_applicable_basis_text is None:
            diagnostics.append("missing_no_applicable_basis_text")
        elif not _localized_complete(bundle.no_applicable_basis_text):
            diagnostics.append("incomplete_bilingual_text:no_applicable_basis")
        diagnostics.extend(
            _validate_verification_path(
                bundle,
                bundle.basis_verification_path,
                "eligibility_bases",
                required=True,
            )
        )
    elif bundle.basis_verification_path is not None:
        diagnostics.extend(
            _validate_verification_path(
                bundle,
                bundle.basis_verification_path,
                "eligibility_bases",
                required=False,
            )
        )

    claim_ids: set[str] = set()
    for claim in bundle.claims:
        if claim.id in claim_ids:
            diagnostics.append(f"duplicate_claim_id:{claim.id}")
        claim_ids.add(claim.id)
        if claim.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_claim_verification_state:{claim.id}")
        for metadata_name in (
            "verified_on", "reverified_on", "effective_from", "effective_to",
            "reverification_due_on"
        ):
            metadata_value = getattr(claim, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_claim_metadata:{claim.id}:{metadata_name}")
        if not _valid_interval(claim.effective_from, claim.effective_to):
            diagnostics.append(f"invalid_claim_interval:{claim.id}")
        for dependency_id in claim.claim_dependencies:
            if dependency_id not in claim_ids and dependency_id not in {item.id for item in bundle.claims}:
                diagnostics.append(f"unknown_claim_dependency:{claim.id}:{dependency_id}")
        if not _localized_complete(claim.text):
            diagnostics.append(f"incomplete_bilingual_text:claim:{claim.id}")
        if claim.verification_state == "current":
            if claim.classification not in {
                "official_requirement",
                "practical_preparation",
            }:
                diagnostics.append(
                    f"unsupported_current_checklist_classification:{claim.id}"
                )
        # Always validate references, including stale/disputed historical
        # material. Only the requirement for an evidence link is state-based.
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"claim:{claim.id}",
                claim.evidence_link_ids,
                required=claim.verification_state == "current",
            )
        )
        if claim.scope == "eligibility_basis":
            if not claim.eligibility_basis_id:
                diagnostics.append(f"basis_scoped_claim_missing_basis:{claim.id}")
            elif claim.eligibility_basis_id not in basis_ids:
                diagnostics.append(
                    f"basis_scoped_claim_unknown_basis:{claim.id}:{claim.eligibility_basis_id}"
                )
        if claim.scope == "shared" and claim.eligibility_basis_id is not None:
            diagnostics.append(f"shared_claim_has_basis:{claim.id}")
        for name, value in (
            ("quantity", claim.quantity),
            ("original_quantity", claim.original_quantity),
            ("copy_quantity", claim.copy_quantity),
        ):
            if value is not None and (type(value) is not int or value <= 0):
                diagnostics.append(f"invalid_checklist_quantity:{claim.id}:{name}")

    claim_graph = {
        claim.id: tuple(
            dependency_id
            for dependency_id in claim.claim_dependencies
            if dependency_id in claim_ids
        )
        for claim in bundle.claims
    }
    claim_visiting: set[str] = set()
    claim_visited: set[str] = set()

    def visit_claim(node: str, path: tuple[str, ...]) -> None:
        if node in claim_visiting:
            start = path.index(node) if node in path else 0
            diagnostics.append(
                f"claim_dependency_cycle:{'->'.join(path[start:] + (node,))}"
            )
            return
        if node in claim_visited:
            return
        claim_visiting.add(node)
        for target in claim_graph.get(node, ()):
            visit_claim(target, path + (node,))
        claim_visiting.remove(node)
        claim_visited.add(node)

    for claim_id in sorted(claim_graph):
        visit_claim(claim_id, ())

    for basis in bundle.eligibility_bases:
        for dependency_id in basis.claim_dependencies:
            if dependency_id not in claim_ids:
                diagnostics.append(
                    f"unknown_claim_dependency:{basis.id}:{dependency_id}"
                )

    step_ids: set[str] = set()
    step_positions: set[tuple[int, int]] = set()
    for step in bundle.steps:
        if step.id in step_ids:
            diagnostics.append(f"duplicate_step_id:{step.id}")
        step_ids.add(step.id)
        if step.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_step_verification_state:{step.id}")
        for metadata_name in (
            "verified_on", "reverified_on", "effective_from", "effective_to",
            "reverification_due_on"
        ):
            metadata_value = getattr(step, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_step_metadata:{step.id}:{metadata_name}")
        if not _valid_interval(step.effective_from, step.effective_to):
            diagnostics.append(f"invalid_step_interval:{step.id}")
        if not _localized_complete(step.text):
            diagnostics.append(f"incomplete_bilingual_text:step:{step.id}")
        if step.phase_order < 0 or step.slot < 0:
            diagnostics.append(f"invalid_step_order:{step.id}")
        if step.scope == "eligibility_basis":
            if not step.eligibility_basis_id:
                diagnostics.append(f"basis_scoped_step_missing_basis:{step.id}")
            elif step.eligibility_basis_id not in basis_ids:
                diagnostics.append(
                    f"basis_scoped_step_unknown_basis:{step.id}:{step.eligibility_basis_id}"
                )
        if step.scope == "shared" and step.eligibility_basis_id is not None:
            diagnostics.append(f"shared_step_has_basis:{step.id}")
        for dependency_id in step.claim_dependencies:
            if dependency_id not in claim_ids:
                diagnostics.append(
                    f"unknown_claim_dependency:{step.id}:{dependency_id}"
                )
        position = (step.phase_order, step.slot)
        if step.verification_state == "current":
            if position in step_positions:
                diagnostics.append(
                    f"ambiguous_step_order:{step.phase_order}:{step.slot}"
                )
            step_positions.add(position)
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"step:{step.id}",
                step.evidence_link_ids,
                required=step.verification_state == "current",
            )
        )

    fee_ids: set[str] = set()
    for fee in bundle.fees:
        if fee.id in fee_ids:
            diagnostics.append(f"duplicate_fee_id:{fee.id}")
        fee_ids.add(fee.id)
        if fee.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_fee_verification_state:{fee.id}")
        for metadata_name in (
            "verified_on", "reverified_on", "effective_from", "effective_to",
            "reverification_due_on"
        ):
            metadata_value = getattr(fee, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_fee_metadata:{fee.id}:{metadata_name}")
        if not _valid_interval(fee.effective_from, fee.effective_to):
            diagnostics.append(f"invalid_fee_interval:{fee.id}")
        if not _localized_complete(fee.text):
            diagnostics.append(f"incomplete_bilingual_text:fee:{fee.id}")
        if not fee.currency.strip():
            diagnostics.append(f"missing_fee_currency:{fee.id}")
        for dependency_id in fee.claim_dependencies:
            if dependency_id not in claim_ids:
                diagnostics.append(
                    f"unknown_claim_dependency:{fee.id}:{dependency_id}"
                )
        amount_ok = type(fee.amount) is int and fee.amount >= 0
        range_ok = (
            type(fee.minimum_amount) is int
            and type(fee.maximum_amount) is int
            and fee.minimum_amount >= 0
            and fee.maximum_amount >= fee.minimum_amount
        )
        if fee.value_state == "known":
            if (
                not amount_ok
                or fee.minimum_amount is not None
                or fee.maximum_amount is not None
            ):
                diagnostics.append(f"invalid_known_fee:{fee.id}")
        elif fee.value_state == "range":
            if fee.amount is not None or not range_ok:
                diagnostics.append(f"invalid_fee_range:{fee.id}")
        elif fee.value_state == "unknown":
            if (
                fee.amount is not None
                or fee.minimum_amount is not None
                or fee.maximum_amount is not None
            ):
                diagnostics.append(f"unknown_fee_has_value:{fee.id}")
        elif fee.value_state == "unverified":
            if not (amount_ok or range_ok):
                diagnostics.append(f"unverified_fee_without_value:{fee.id}")
            if fee.verification_state not in {
                "needs_reverification", "stale", "disputed"
            }:
                diagnostics.append(
                    f"unverified_fee_wrong_verification_state:{fee.id}"
                )
        else:
            diagnostics.append(f"unsupported_fee_value_state:{fee.id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"fee:{fee.id}",
                fee.evidence_link_ids,
                required=fee.value_state in {"known", "range", "unverified"},
            )
        )

    dependency_ids: set[str] = set()
    for dependency in bundle.dependencies:
        if dependency.id in dependency_ids:
            diagnostics.append(f"duplicate_dependency_id:{dependency.id}")
        dependency_ids.add(dependency.id)
        if dependency.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_dependency_verification_state:{dependency.id}")
        for metadata_name in (
            "verified_on", "reverified_on", "effective_from", "effective_to",
            "reverification_due_on"
        ):
            metadata_value = getattr(dependency, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_dependency_metadata:{dependency.id}:{metadata_name}")
        if not _valid_interval(dependency.effective_from, dependency.effective_to):
            diagnostics.append(f"invalid_dependency_interval:{dependency.id}")
        if not _localized_complete(dependency.text):
            diagnostics.append(f"incomplete_bilingual_text:dependency:{dependency.id}")
        for claim_id in dependency.claim_dependencies:
            if claim_id not in claim_ids:
                diagnostics.append(
                    f"unknown_claim_dependency:{dependency.id}:{claim_id}"
                )
        if dependency.target_procedure_id == bundle.procedure.procedure_id:
            diagnostics.append(f"blocking_dependency_self_cycle:{dependency.id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"dependency:{dependency.id}",
                dependency.evidence_link_ids,
                required=dependency.verification_state == "current",
            )
        )
        diagnostics.extend(
            _validate_verification_path(
                bundle,
                dependency.verification_path,
                f"dependency:{dependency.id}",
                required=True,
            )
        )

    point_ids: set[str] = set()
    for point in bundle.service_points:
        if point.id in point_ids:
            diagnostics.append(f"duplicate_service_point_id:{point.id}")
        point_ids.add(point.id)
        if not _localized_complete(point.text):
            diagnostics.append(f"incomplete_bilingual_text:service_point:{point.id}")

    version_ids: set[str] = set()
    versions_by_point: dict[str, list] = {}
    for version in bundle.service_point_versions:
        if version.id in version_ids:
            diagnostics.append(f"duplicate_service_point_version_id:{version.id}")
        version_ids.add(version.id)
        if version.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_service_point_version_verification_state:{version.id}")
        if version.service_point_id not in point_ids:
            diagnostics.append(
                f"service_point_version_unknown_point:{version.id}:{version.service_point_id}"
            )
        if not _localized_complete(version.address):
            diagnostics.append(
                f"incomplete_bilingual_text:service_point_version:{version.id}"
            )
        for metadata_name in (
            "verified_on", "reverified_on", "reverification_due_on"
        ):
            metadata_value = getattr(version, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_service_point_version_metadata:{version.id}:{metadata_name}")
        if not _valid_interval(version.effective_from, version.effective_to):
            diagnostics.append(f"invalid_service_point_version_interval:{version.id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"service_point_version:{version.id}",
                version.evidence_link_ids,
                required=version.verification_state == "current",
            )
        )
        if version.verification_state == "current" and _valid_interval(
            version.effective_from, version.effective_to
        ):
            versions_by_point.setdefault(version.service_point_id, []).append(version)

    for point_id, versions in versions_by_point.items():
        ordered = sorted(
            versions,
            key=lambda item: (
                item.effective_from
                if type(item.effective_from) is date
                else date.min,
                str(item.id),
            ),
        )
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if _intervals_overlap(
                    left.effective_from,
                    left.effective_to,
                    right.effective_from,
                    right.effective_to,
                ):
                    diagnostics.append(
                        f"overlapping_service_point_versions:{point_id}:{left.id}:{right.id}"
                    )

    association_ids: set[str] = set()
    for association in bundle.service_point_associations:
        if association.id in association_ids:
            diagnostics.append(f"duplicate_service_point_association_id:{association.id}")
        association_ids.add(association.id)
        if association.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_service_point_association_verification_state:{association.id}")
        if association.procedure_version_id != bundle.procedure.version_id:
            diagnostics.append(
                f"association_procedure_version_mismatch:{association.id}:{association.procedure_version_id}"
            )
        if association.service_point_version_id not in version_ids:
            diagnostics.append(
                f"association_unknown_service_point_version:{association.id}:{association.service_point_version_id}"
            )
        for metadata_name in (
            "verified_on", "reverified_on", "reverification_due_on"
        ):
            metadata_value = getattr(association, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_service_point_association_metadata:{association.id}:{metadata_name}")
        if not _valid_interval(
            association.effective_from,
            association.effective_to,
        ):
            diagnostics.append(
                f"invalid_service_point_association_interval:{association.id}"
            )
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"service_point_association:{association.id}",
                association.evidence_link_ids,
                required=association.verification_state == "current",
            )
        )

    material_ids = (
        claim_ids
        | step_ids
        | fee_ids
        | basis_ids
        | dependency_ids
        | version_ids
        | association_ids
    )
    discrepancy_ids: set[str] = set()
    for discrepancy in bundle.discrepancies:
        if discrepancy.id in discrepancy_ids:
            diagnostics.append(f"duplicate_discrepancy_id:{discrepancy.id}")
        discrepancy_ids.add(discrepancy.id)
        if discrepancy.status not in {
            "open", "resolved", "resolved_for_current_version",
            "open_editorial", "needs_reverification"
        }:
            diagnostics.append(f"unsupported_discrepancy_status:{discrepancy.id}")
        if discrepancy.consequence not in {"none", "needs_reverification", "disputed"}:
            diagnostics.append(f"unsupported_discrepancy_consequence:{discrepancy.id}")
        if discrepancy.claim_id not in material_ids:
            diagnostics.append(
                f"discrepancy_unknown_claim:{discrepancy.id}:{discrepancy.claim_id}"
            )
        if not discrepancy.evidence_link_ids:
            diagnostics.append(f"discrepancy_without_evidence:{discrepancy.id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"discrepancy:{discrepancy.id}",
                discrepancy.evidence_link_ids,
                required=True,
            )
        )
        if not discrepancy.rationale.strip():
            diagnostics.append(f"empty_discrepancy_rationale:{discrepancy.id}")

    diagnostics.extend(
        _validate_verification_path(
            bundle,
            bundle.routing_verification_path,
            "routing",
            required=True,
        )
    )

    regeneration = []
    warning_ids: set[str] = set()
    for warning in bundle.warnings:
        if warning.id in warning_ids:
            diagnostics.append(f"duplicate_warning_id:{warning.id}")
        warning_ids.add(warning.id)
        if warning.verification_state not in {"current", "needs_reverification", "stale", "disputed", "unknown"}:
            diagnostics.append(f"unsupported_warning_verification_state:{warning.id}")
        for metadata_name in (
            "verified_on", "reverified_on", "reverification_due_on"
        ):
            metadata_value = getattr(warning, metadata_name)
            if metadata_value is not None and type(metadata_value) is not date:
                diagnostics.append(f"invalid_warning_metadata:{warning.id}:{metadata_name}")
        if not _localized_complete(warning.text):
            diagnostics.append(f"incomplete_bilingual_text:warning:{warning.id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"warning:{warning.id}",
                warning.evidence_link_ids,
                required=warning.kind == "administrative",
            )
        )
        if warning.role == "regeneration":
            regeneration.append(warning)
            if warning.kind != "product" or warning.severity != "important":
                diagnostics.append(f"invalid_regeneration_warning:{warning.id}")
    if len(regeneration) != 1:
        diagnostics.append("requires_exactly_one_regeneration_warning")

    for unknown in bundle.unknowns:
        if not _localized_complete(unknown.text):
            diagnostics.append(f"incomplete_bilingual_text:unknown:{unknown.id}")

    return tuple(dict.fromkeys(diagnostics))


def _interval_intersection(
    *intervals: tuple[date | None, date | None],
) -> tuple[date | None, date | None] | None:
    if any(not _valid_interval(start, end) for start, end in intervals):
        return None
    starts = [start for start, _ in intervals if start is not None]
    ends = [end for _, end in intervals if end is not None]
    start = max(starts) if starts else None
    end = min(ends) if ends else None
    if start is not None and end is not None and start > end:
        return None
    return start, end


def _blocking_dependency_cycle_diagnostics(
    catalog: KnowledgeCatalog,
) -> tuple[str, ...]:
    """Reject cycles that can exist in one coherent date-applicable graph."""
    all_bundles = {
        bundle.procedure.version_id: bundle
        for procedure_id in (
            {
                bundle.procedure.procedure_id
                for bundle in catalog.fixtures.values()
            }
            | set(catalog.versioned_fixtures)
            | set(catalog.versions)
            | set(catalog.procedure_versions)
            | set(catalog.version_collections)
        )
        for bundle in bundles_for_procedure(catalog, procedure_id)
    }
    # Keep the interval carried by each edge. A graph cycle is only blocking
    # when all procedure and dependency intervals in that cycle intersect.
    graph: dict[
        str, tuple[tuple[str, date | None, date | None], ...]
    ] = {}
    for version_id, bundle in all_bundles.items():
        edges: list[tuple[str, date | None, date | None]] = []
        if bundle.procedure.publication_state == "published":
            source_interval = (
                bundle.procedure.effective_from,
                bundle.procedure.effective_to,
            )
            for dependency in bundle.dependencies:
                if (
                    dependency.relation != "blocking_prerequisite"
                    or dependency.verification_state != "current"
                ):
                    continue
                for target_bundle in bundles_for_procedure(
                    catalog, dependency.target_procedure_id
                ):
                    if target_bundle.procedure.publication_state != "published":
                        continue
                    edge_interval = _interval_intersection(
                        source_interval,
                        (dependency.effective_from, dependency.effective_to),
                        (
                            target_bundle.procedure.effective_from,
                            target_bundle.procedure.effective_to,
                        ),
                    )
                    if edge_interval is not None:
                        edges.append(
                            (
                                target_bundle.procedure.version_id,
                                edge_interval[0],
                                edge_interval[1],
                            )
                        )
        graph[version_id] = tuple(
            sorted(edges, key=lambda edge: str(edge[0]))
        )

    diagnostics: set[str] = set()

    def visit(
        node: str,
        path: tuple[str, ...],
        active_interval: tuple[date | None, date | None],
    ) -> None:
        for target, edge_from, edge_to in graph.get(node, ()):
            common = _interval_intersection(
                active_interval,
                (edge_from, edge_to),
            )
            if common is None:
                continue
            if target in path:
                cycle_start = path.index(target)
                cycle = path[cycle_start:] + (target,)
                diagnostics.add(
                    f"blocking_dependency_cycle:{'->'.join(cycle)}"
                )
                continue
            visit(target, path + (target,), common)

    for version_id, bundle in all_bundles.items():
        if bundle.procedure.publication_state != "published":
            continue
        visit(
            version_id,
            (version_id,),
            (bundle.procedure.effective_from, bundle.procedure.effective_to),
        )
    return tuple(sorted(diagnostics))


def validate_catalog(catalog: KnowledgeCatalog) -> tuple[str, ...]:
    diagnostics: list[str] = []
    definitions = catalog.fact_definitions or FACT_DEFINITIONS

    for key, definition in definitions.items():
        if key != definition.key:
            diagnostics.append(f"fact_definition_key_mismatch:{key}")
        if definition.kind == "enum" and not definition.enum_values:
            diagnostics.append(f"empty_enum_definition:{key}")

    for goal_id, goal_entry in catalog.goals.items():
        if goal_entry.goal.id != goal_id:
            diagnostics.append(f"goal_key_mismatch:{goal_id}")
        if not _localized_complete(goal_entry.goal.text):
            diagnostics.append(f"incomplete_bilingual_text:goal:{goal_id}")
        for candidate in goal_entry.candidates:
            if not _localized_complete(candidate.text):
                diagnostics.append(
                    f"incomplete_bilingual_text:procedure_candidate:{candidate.procedure_id}"
                )
            diagnostics.extend(
                validate_predicate(candidate.applicability, definitions)
            )
            if candidate.fixture_id is not None and candidate.fixture_id not in catalog.fixtures and candidate.procedure_id not in (
                set(catalog.versioned_fixtures)
                | set(catalog.versions)
                | set(catalog.procedure_versions)
                | set(catalog.version_collections)
            ):
                diagnostics.append(
                    f"candidate_fixture_missing:{candidate.procedure_id}"
                )

    seen_bundles: dict[str, KnowledgeBundle] = {}
    seen_version_ids: set[str] = set()
    for fixture_id, fixture in catalog.fixtures.items():
        if fixture_id not in {
            fixture.procedure.procedure_id,
            fixture.procedure.version_id,
        }:
            diagnostics.append(f"fixture_key_mismatch:{fixture_id}")

    raw_version_collections = (
        catalog.versioned_fixtures,
        catalog.versions,
        catalog.procedure_versions,
        catalog.version_collections,
    )
    raw_version_bundles: dict[str, KnowledgeBundle] = {}
    for collection in raw_version_collections:
        for procedure_id, collection_bundles in collection.items():
            local_ids: set[str] = set()
            for fixture in collection_bundles:
                version_id = fixture.procedure.version_id
                if version_id in local_ids:
                    diagnostics.append(f"duplicate_procedure_version_id:{version_id}")
                local_ids.add(version_id)
                existing = raw_version_bundles.get(version_id)
                if existing is not None and existing != fixture:
                    diagnostics.append(
                        f"conflicting_procedure_version_representation:{version_id}"
                    )
                raw_version_bundles.setdefault(version_id, fixture)
                if fixture.procedure.procedure_id != procedure_id:
                    diagnostics.append(
                        f"procedure_version_ownership_mismatch:{procedure_id}:{version_id}"
                    )

    catalog_fixture_procedures = {
        fixture.procedure.procedure_id for fixture in catalog.fixtures.values()
    }
    for procedure_id in sorted(
        catalog_fixture_procedures
        | set(catalog.versioned_fixtures)
        | set(catalog.versions)
        | set(catalog.procedure_versions)
        | set(catalog.version_collections)
    ):
        for version_id in version_collection_conflicts(catalog, procedure_id):
            diagnostics.append(
                f"conflicting_procedure_version_representation:{procedure_id}:{version_id}"
            )
    for procedure_id in sorted(
        catalog_fixture_procedures
        | set(catalog.versioned_fixtures)
        | set(catalog.versions)
        | set(catalog.procedure_versions)
        | set(catalog.version_collections)
    ):
        collections = bundles_for_procedure(catalog, procedure_id)
        for fixture in collections:
            if fixture.procedure.procedure_id != procedure_id:
                diagnostics.append(
                    f"procedure_version_ownership_mismatch:{procedure_id}:{fixture.procedure.version_id}"
                )
            if fixture.procedure.version_id in seen_version_ids:
                # A compatibility override is intentionally the same version;
                # validate it once rather than reporting a false duplicate.
                previous = seen_bundles.get(fixture.procedure.version_id)
                if previous is fixture or previous is not None and previous.id == fixture.id:
                    continue
                diagnostics.append(f"duplicate_procedure_version_id:{fixture.procedure.version_id}")
            seen_version_ids.add(fixture.procedure.version_id)
            seen_bundles[fixture.procedure.version_id] = fixture
            diagnostics.extend(validate_bundle(fixture, definitions))

    versions_by_procedure: dict[str, list[KnowledgeBundle]] = {}
    for fixture in seen_bundles.values():
        if fixture.procedure.publication_state == "published":
            versions_by_procedure.setdefault(fixture.procedure.procedure_id, []).append(fixture)
    for procedure_id, versions in versions_by_procedure.items():
        ordered = sorted(
            versions,
            key=lambda item: (
                item.procedure.effective_from
                if type(item.procedure.effective_from) is date
                else date.min,
                str(item.procedure.version_id),
            ),
        )
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if _intervals_overlap(
                    left.procedure.effective_from,
                    left.procedure.effective_to,
                    right.procedure.effective_from,
                    right.procedure.effective_to,
                ):
                    diagnostics.append(
                        f"overlapping_published_procedure_versions:{procedure_id}:{left.procedure.version_id}:{right.procedure.version_id}"
                    )

    diagnostics.extend(_blocking_dependency_cycle_diagnostics(catalog))

    question_ids: set[str] = set()
    question_keys_by_goal: dict[str, set[str]] = {}
    for question in catalog.questions:
        if question.id in question_ids:
            diagnostics.append(f"duplicate_question_id:{question.id}")
        question_ids.add(question.id)
        if not _localized_complete(question.text):
            diagnostics.append(f"incomplete_bilingual_text:question:{question.id}")
        definition = definitions.get(question.fact_key)
        if definition is None:
            diagnostics.append(f"unsupported_question_fact:{question.fact_key}")
        elif definition.derived:
            diagnostics.append(f"question_writes_derived_fact:{question.fact_key}")
        for key in question.resolved_keys:
            if key not in definitions:
                diagnostics.append(f"unsupported_question_resolved_fact:{key}")
            question_keys_by_goal.setdefault(question.goal_id, set()).add(key)

    # Reachability and qualification are separate authoring stages, but both
    # must remain answerable from source Facts when they are consequential.
    # Derived Facts are excluded because their source Question owns coverage.
    for fixture in seen_bundles.values():
        covered = question_keys_by_goal.get(fixture.goal.id, set())
        for basis in fixture.eligibility_bases:
            for stage, predicate in (
                ("reachability", basis.applicability),
                ("qualification", basis.qualification),
            ):
                if predicate is None:
                    continue
                for key in sorted(_predicate_fact_keys(predicate)):
                    definition = definitions.get(key)
                    if definition is None or definition.derived:
                        continue
                    if key not in covered:
                        diagnostics.append(
                            f"missing_basis_{stage}_question:{basis.id}:{key}"
                        )

    contradiction_ids: set[str] = set()
    for contradiction in catalog.contradictions:
        if contradiction.id in contradiction_ids:
            diagnostics.append(f"duplicate_contradiction_id:{contradiction.id}")
        contradiction_ids.add(contradiction.id)
        if contradiction.goal_id not in catalog.goals:
            diagnostics.append(
                f"unsupported_contradiction_goal:{contradiction.goal_id}"
            )
        if len(contradiction.fact_keys) < 2:
            diagnostics.append(
                f"contradiction_requires_multiple_facts:{contradiction.id}"
            )
        if len(set(contradiction.fact_keys)) != len(contradiction.fact_keys):
            diagnostics.append(
                f"duplicate_contradiction_fact_key:{contradiction.id}"
            )
        for key in contradiction.fact_keys:
            definition = definitions.get(key)
            if definition is None:
                diagnostics.append(f"unsupported_contradiction_fact:{key}")
            elif definition.derived:
                diagnostics.append(
                    f"contradiction_conflict_key_must_be_source_fact:{key}"
                )
        if _predicate_fact_keys(contradiction.condition) != frozenset(
            contradiction.fact_keys
        ):
            diagnostics.append(
                f"contradiction_fact_keys_mismatch:{contradiction.id}"
            )
        diagnostics.extend(
            validate_predicate(contradiction.condition, definitions)
        )

    return tuple(dict.fromkeys(diagnostics))