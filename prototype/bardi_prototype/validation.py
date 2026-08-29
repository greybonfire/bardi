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
from .evaluator import validate_predicate
from .facts import FACT_DEFINITIONS


def _bundle_rules(bundle: KnowledgeBundle) -> Iterable[Predicate | None]:
    yield bundle.procedure.applicability
    for basis in bundle.eligibility_bases:
        yield basis.applicability
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
        for source_id in link.source_ids:
            if source_id not in bundle.sources:
                diagnostics.append(f"unknown_evidence_source:{link_id}:{source_id}")
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
    return effective_from is None or effective_to is None or effective_from <= effective_to


def _intervals_overlap(
    left_from: date | None,
    left_to: date | None,
    right_from: date | None,
    right_to: date | None,
) -> bool:
    if left_to is not None and right_from is not None and left_to < right_from:
        return False
    if right_to is not None and left_from is not None and right_to < left_from:
        return False
    return True


def validate_bundle(
    bundle: KnowledgeBundle,
    fact_definitions: Mapping[str, FactDefinition],
) -> tuple[str, ...]:
    diagnostics: list[str] = []
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
    for link_id, link in bundle.evidence_links.items():
        if link_id != link.id:
            diagnostics.append(f"evidence_link_key_mismatch:{link_id}")
        diagnostics.extend(
            _validate_evidence(
                bundle,
                f"evidence_link:{link_id}",
                (link_id,),
                required=True,
            )
        )

    basis_ids: set[str] = set()
    basis_orders: set[int] = set()
    for basis in bundle.eligibility_bases:
        if basis.id in basis_ids:
            diagnostics.append(f"duplicate_eligibility_basis_id:{basis.id}")
        basis_ids.add(basis.id)
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

    for claim in bundle.claims:
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
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"claim:{claim.id}",
                    claim.evidence_link_ids,
                    required=True,
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

    step_positions: set[tuple[int, int]] = set()
    for step in bundle.steps:
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
                    required=True,
                )
            )

    for fee in bundle.fees:
        if not _localized_complete(fee.text):
            diagnostics.append(f"incomplete_bilingual_text:fee:{fee.id}")
        if not fee.currency.strip():
            diagnostics.append(f"missing_fee_currency:{fee.id}")
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
            if fee.verification_state != "current":
                diagnostics.append(f"known_fee_not_current:{fee.id}")
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"fee:{fee.id}",
                    fee.evidence_link_ids,
                    required=True,
                )
            )
        elif fee.value_state == "range":
            if fee.amount is not None or not range_ok:
                diagnostics.append(f"invalid_fee_range:{fee.id}")
            if fee.verification_state != "current":
                diagnostics.append(f"range_fee_not_current:{fee.id}")
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"fee:{fee.id}",
                    fee.evidence_link_ids,
                    required=True,
                )
            )
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
            if fee.verification_state != "needs_reverification":
                diagnostics.append(
                    f"unverified_fee_wrong_verification_state:{fee.id}"
                )
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"fee:{fee.id}",
                    fee.evidence_link_ids,
                    required=True,
                )
            )
        else:
            diagnostics.append(f"unsupported_fee_value_state:{fee.id}")

    dependency_ids: set[str] = set()
    for dependency in bundle.dependencies:
        if dependency.id in dependency_ids:
            diagnostics.append(f"duplicate_dependency_id:{dependency.id}")
        dependency_ids.add(dependency.id)
        if not _localized_complete(dependency.text):
            diagnostics.append(f"incomplete_bilingual_text:dependency:{dependency.id}")
        if dependency.target_procedure_id == bundle.procedure.procedure_id:
            diagnostics.append(f"blocking_dependency_self_cycle:{dependency.id}")
        if dependency.verification_state == "current":
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"dependency:{dependency.id}",
                    dependency.evidence_link_ids,
                    required=True,
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
        if version.service_point_id not in point_ids:
            diagnostics.append(
                f"service_point_version_unknown_point:{version.id}:{version.service_point_id}"
            )
        if not _localized_complete(version.address):
            diagnostics.append(
                f"incomplete_bilingual_text:service_point_version:{version.id}"
            )
        if not _valid_interval(version.effective_from, version.effective_to):
            diagnostics.append(f"invalid_service_point_version_interval:{version.id}")
        if version.verification_state == "current":
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"service_point_version:{version.id}",
                    version.evidence_link_ids,
                    required=True,
                )
            )
            versions_by_point.setdefault(version.service_point_id, []).append(version)

    for point_id, versions in versions_by_point.items():
        ordered = sorted(versions, key=lambda item: (item.effective_from or date.min, item.id))
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
        if association.procedure_version_id != bundle.procedure.version_id:
            diagnostics.append(
                f"association_procedure_version_mismatch:{association.id}:{association.procedure_version_id}"
            )
        if association.service_point_version_id not in version_ids:
            diagnostics.append(
                f"association_unknown_service_point_version:{association.id}:{association.service_point_version_id}"
            )
        if not _valid_interval(
            association.effective_from,
            association.effective_to,
        ):
            diagnostics.append(
                f"invalid_service_point_association_interval:{association.id}"
            )
        if association.verification_state == "current":
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"service_point_association:{association.id}",
                    association.evidence_link_ids,
                    required=True,
                )
            )

    diagnostics.extend(
        _validate_verification_path(
            bundle,
            bundle.routing_verification_path,
            "routing",
            required=True,
        )
    )

    regeneration = []
    for warning in bundle.warnings:
        if not _localized_complete(warning.text):
            diagnostics.append(f"incomplete_bilingual_text:warning:{warning.id}")
        if warning.kind == "administrative":
            diagnostics.extend(
                _validate_evidence(
                    bundle,
                    f"warning:{warning.id}",
                    warning.evidence_link_ids,
                    required=True,
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


def _blocking_dependency_cycle_diagnostics(
    catalog: KnowledgeCatalog,
) -> tuple[str, ...]:
    graph: dict[str, tuple[str, ...]] = {}
    for procedure_id, bundle in catalog.fixtures.items():
        graph[procedure_id] = tuple(
            sorted(
                dependency.target_procedure_id
                for dependency in bundle.dependencies
                if dependency.relation == "blocking_prerequisite"
                and dependency.verification_state == "current"
                and dependency.target_procedure_id in catalog.fixtures
            )
        )

    diagnostics: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in visiting:
            cycle_start = path.index(node) if node in path else 0
            cycle = path[cycle_start:] + (node,)
            diagnostics.append(f"blocking_dependency_cycle:{'->'.join(cycle)}")
            return
        if node in visited:
            return
        visiting.add(node)
        for target in graph.get(node, ()):
            visit(target, path + (node,))
        visiting.remove(node)
        visited.add(node)

    for procedure_id in sorted(graph):
        visit(procedure_id, ())
    return tuple(dict.fromkeys(diagnostics))


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

    for fixture_id, fixture in catalog.fixtures.items():
        if fixture_id != fixture.procedure.procedure_id:
            diagnostics.append(f"fixture_key_mismatch:{fixture_id}")
        diagnostics.extend(validate_bundle(fixture, definitions))

    diagnostics.extend(_blocking_dependency_cycle_diagnostics(catalog))

    question_ids: set[str] = set()
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
