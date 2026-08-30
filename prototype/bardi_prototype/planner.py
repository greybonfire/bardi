from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .contracts import (
    ClaimDefinition,
    EligibilityBasisDefinition,
    FeeDefinition,
    KnowledgeBundle,
    KnowledgeCatalog,
    ProcedureDependencyDefinition,
    ProcedureServicePointAssociationDefinition,
    ServicePointDefinition,
    ServicePointVersionDefinition,
    StepDefinition,
    UnknownDefinition,
    VerificationPathDefinition,
    WarningDefinition,
)
from .derivations import derive_facts
from .evaluator import RuleEvaluationRecord, TruthValue, evaluate, record_evaluation
from .trust import (
    is_currently_trusted,
    is_historical_context_candidate,
    trust_state,
)
from .versions import resolve_procedure_version


@dataclass(frozen=True)
class SemanticDependency:
    definition: ProcedureDependencyDefinition
    status: str
    target_knowledge: KnowledgeBundle | None


@dataclass(frozen=True)
class SemanticServicePoint:
    point: ServicePointDefinition
    version: ServicePointVersionDefinition
    association: ProcedureServicePointAssociationDefinition


@dataclass(frozen=True)
class SemanticRouting:
    status: str
    service_points: tuple[SemanticServicePoint, ...]
    unresolved_association_ids: tuple[str, ...]
    unresolved_fact_keys: tuple[str, ...]
    verification_path: VerificationPathDefinition | None


@dataclass(frozen=True)
class SemanticHistoricalItem:
    item: object
    kind: str
    verification_state: str


@dataclass(frozen=True)
class SemanticPlan:
    knowledge: KnowledgeBundle
    facts: Mapping[str, object]
    evaluation_date: date
    generated_on: date
    claims: tuple[ClaimDefinition, ...]
    steps: tuple[StepDefinition, ...]
    fees: tuple[FeeDefinition, ...]
    service_points: tuple[SemanticServicePoint, ...]
    warnings: tuple[WarningDefinition, ...]
    unknowns: tuple[UnknownDefinition, ...]
    eligibility_bases: tuple[EligibilityBasisDefinition, ...]
    dependencies: tuple[SemanticDependency, ...]
    routing: SemanticRouting
    historical_items: tuple[SemanticHistoricalItem, ...] = ()
    inconclusive_claim_ids: tuple[str, ...] = ()
    inconclusive_basis_ids: tuple[str, ...] = ()
    historical: bool = False
    upcoming_versions: tuple[KnowledgeBundle, ...] = ()


@dataclass(frozen=True)
class PlanAssembly:
    plan: SemanticPlan | None
    missing_facts: frozenset[str] = frozenset()
    traces: tuple[RuleEvaluationRecord, ...] = ()


class KnownCaseIncomplete(Exception):
    """Compatibility name retained from the pre-#7 prototype."""


class ProcedureNotApplicable(Exception):
    def __init__(
        self,
        procedure_id: str,
        traces: tuple[RuleEvaluationRecord, ...] = (),
    ) -> None:
        super().__init__(procedure_id)
        self.procedure_id = procedure_id
        self.traces = traces


class NoApplicableBasis(Exception):
    def __init__(
        self,
        procedure_id: str,
        text,
        verification_path: VerificationPathDefinition,
        traces: tuple[RuleEvaluationRecord, ...] = (),
    ) -> None:
        super().__init__(procedure_id)
        self.procedure_id = procedure_id
        self.text = text
        self.verification_path = verification_path
        self.traces = traces


def _date_applies(
    evaluation_date: date,
    effective_from: date | None,
    effective_to: date | None,
) -> bool:
    if effective_from is not None and evaluation_date < effective_from:
        return False
    if effective_to is not None and evaluation_date > effective_to:
        return False
    return True


def _current_items(
    knowledge: KnowledgeBundle,
    items,
    evaluation_date: date | None = None,
):
    return tuple(
        item
        for item in items
        if is_currently_trusted(knowledge, item, evaluation_date)
        and (
            evaluation_date is None
            or _date_applies(
                evaluation_date,
                getattr(item, "effective_from", None),
                getattr(item, "effective_to", None),
            )
        )
    )


def _belongs_to_matched_basis(item, matched_basis_ids: frozenset[str]) -> bool:
    if getattr(item, "scope", "shared") != "eligibility_basis":
        return True
    return getattr(item, "eligibility_basis_id", None) in matched_basis_ids


def _historical_items(
    knowledge: KnowledgeBundle,
    items,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    evaluation_date: date,
    *,
    kind: str,
    matched_basis_ids: frozenset[str] = frozenset(),
):
    """Keep established past values as context, never current advice.

    A generic trust problem is not a historical value. In particular,
    ``needs_reverification``, ``disputed`` and ``unknown`` items stay out of
    this projection unless they have explicitly become stale with their own
    item-level verification date.
    """
    selected: list[SemanticHistoricalItem] = []
    for item in items:
        if not _belongs_to_matched_basis(item, matched_basis_ids):
            continue
        effective_from = getattr(item, "effective_from", None)
        if effective_from is not None and effective_from > evaluation_date:
            continue
        if not is_historical_context_candidate(
            knowledge,
            item,
            evaluation_date,
        ):
            continue
        result = evaluate(
            getattr(item, "applicability", None),
            facts,
            submitted_keys=submitted_keys,
        )
        if result.value is not TruthValue.TRUE:
            continue
        if kind == "fee" and getattr(item, "value_state", None) == "unknown":
            # There is no prior value to present as historical context.
            continue
        state = trust_state(knowledge, item, evaluation_date)
        if state == "current":
            state = "stale"
        selected.append(SemanticHistoricalItem(item, kind, state))
    return tuple(selected)


def _select_bases(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    evaluation_date: date,
):
    selected: list[EligibilityBasisDefinition] = []
    inconclusive: set[str] = set()
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for basis in knowledge.eligibility_bases:
        if not _date_applies(
            evaluation_date,
            basis.effective_from,
            basis.effective_to,
        ):
            continue
        result = evaluate(
            basis.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"eligibility_basis:{basis.id}",
                result,
                consequential_to_planning=True,
            )
        )
        state = trust_state(knowledge, basis, evaluation_date)
        if result.value is TruthValue.TRUE:
            # A researched Basis may still be shown as a factual candidate, but
            # every non-current trust state prevents it from establishing
            # eligibility or unlocking Basis-scoped current guidance.
            selected.append(basis)
            if state != "current":
                inconclusive.add(basis.id)
        elif result.value is TruthValue.UNKNOWN:
            if state in {"stale", "disputed", "unknown"}:
                # Do not ask users to resolve an UNKNOWN rule that is itself no
                # longer trustworthy. needs_reverification is different: those
                # researched candidates still need factual resolution so #10's
                # exhaustive alternative set remains deterministic.
                inconclusive.add(basis.id)
            else:
                missing.update(result.missing_facts)
    return (
        tuple(sorted(selected, key=lambda item: (item.display_order, item.id))),
        frozenset(missing),
        tuple(traces),
        frozenset(inconclusive),
    )


def _select_items(
    knowledge: KnowledgeBundle,
    items,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    *,
    context_prefix: str,
    consequential: bool,
    matched_basis_ids: frozenset[str] = frozenset(),
    evaluation_date: date | None = None,
):
    selected = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for item in _current_items(knowledge, items, evaluation_date):
        if not _belongs_to_matched_basis(item, matched_basis_ids):
            continue
        result = evaluate(
            item.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"{context_prefix}:{item.id}",
                result,
                consequential_to_planning=consequential,
            )
        )
        if result.value is TruthValue.TRUE:
            selected.append(item)
        elif result.value is TruthValue.UNKNOWN and consequential:
            missing.update(result.missing_facts)
    return tuple(selected), frozenset(missing), tuple(traces)


def _applicable_untrusted_items(
    knowledge: KnowledgeBundle,
    items,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    evaluation_date: date,
    *,
    matched_basis_ids: frozenset[str] = frozenset(),
):
    """Return current-date items whose rule matches but trust is not current."""
    selected = []
    for item in items:
        if not _belongs_to_matched_basis(item, matched_basis_ids):
            continue
        if not _date_applies(
            evaluation_date,
            getattr(item, "effective_from", None),
            getattr(item, "effective_to", None),
        ):
            continue
        if is_currently_trusted(knowledge, item, evaluation_date):
            continue
        result = evaluate(
            getattr(item, "applicability", None),
            facts,
            submitted_keys=submitted_keys,
        )
        if result.value is TruthValue.TRUE:
            selected.append(item)
    return tuple(selected)


def _select_fees(
    knowledge: KnowledgeBundle,
    items,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    evaluation_date: date,
):
    """Select current fee states while retaining explicit unverified states.

    A stale/ended fee is historical context only. A current-date unverified or
    disputed fee may still render as an explicit current-value-unknown fee; the
    presentation layer suppresses its amount.
    """
    selected = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for item in items:
        if not _date_applies(
            evaluation_date,
            item.effective_from,
            item.effective_to,
        ):
            continue
        result = evaluate(
            item.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"fee:{item.id}",
                result,
                consequential_to_planning=True,
            )
        )
        state = trust_state(knowledge, item, evaluation_date)
        if result.value is TruthValue.TRUE:
            if state == "stale" or is_historical_context_candidate(
                knowledge,
                item,
                evaluation_date,
            ):
                continue
            selected.append(item)
        elif result.value is TruthValue.UNKNOWN and state == "current":
            missing.update(result.missing_facts)
    return tuple(selected), frozenset(missing), tuple(traces)


def _select_dependencies(
    knowledge: KnowledgeBundle,
    catalog: KnowledgeCatalog | None,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    evaluation_date: date,
):
    selected: list[SemanticDependency] = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for dependency in knowledge.dependencies:
        if not _date_applies(
            evaluation_date,
            dependency.effective_from,
            dependency.effective_to,
        ):
            continue
        if not is_currently_trusted(knowledge, dependency, evaluation_date):
            applies = evaluate(
                dependency.applicability,
                facts,
                submitted_keys=submitted_keys,
            )
            traces.append(
                record_evaluation(
                    f"dependency_applicability:{dependency.id}",
                    applies,
                    consequential_to_planning=True,
                )
            )
            # Trust uncertainty must not make a possible blocking edge vanish.
            # Keep TRUE/UNKNOWN edges local and inconclusive without asking
            # questions about an untrusted rule.
            if applies.value is not TruthValue.FALSE:
                selected.append(
                    SemanticDependency(dependency, "inconclusive", None)
                )
            continue
        applies = evaluate(
            dependency.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"dependency_applicability:{dependency.id}",
                applies,
                consequential_to_planning=True,
            )
        )
        if applies.value is TruthValue.FALSE:
            continue
        if applies.value is TruthValue.UNKNOWN:
            missing.update(applies.missing_facts)
            continue

        satisfied = evaluate(
            dependency.satisfied_when,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"dependency_satisfied:{dependency.id}",
                satisfied,
                consequential_to_planning=True,
            )
        )
        if satisfied.value is TruthValue.UNKNOWN:
            missing.update(satisfied.missing_facts)
            continue

        target = None
        if catalog is not None:
            target = resolve_procedure_version(
                catalog,
                dependency.target_procedure_id,
                evaluation_date,
            ).bundle
        if satisfied.value is TruthValue.TRUE:
            status = "satisfied"
        elif target is None:
            status = "unsupported_target"
        else:
            status = "blocking"
        selected.append(SemanticDependency(dependency, status, target))

    return (
        tuple(sorted(selected, key=lambda item: item.definition.id)),
        frozenset(missing),
        tuple(traces),
    )


def _select_routing(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    evaluation_date: date,
):
    point_by_id = {point.id: point for point in knowledge.service_points}
    version_by_id = {
        version.id: version for version in knowledge.service_point_versions
    }
    selected: list[SemanticServicePoint] = []
    unresolved_associations: set[str] = set()
    unresolved_facts: set[str] = set()
    traces: list[RuleEvaluationRecord] = []

    for association in knowledge.service_point_associations:
        if not _date_applies(
            evaluation_date,
            association.effective_from,
            association.effective_to,
        ):
            continue

        result = evaluate(
            association.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"service_point_association:{association.id}",
                result,
                consequential_to_planning=False,
            )
        )
        if result.value is TruthValue.FALSE:
            continue
        if result.value is TruthValue.UNKNOWN:
            unresolved_associations.add(association.id)
            unresolved_facts.update(result.missing_facts)
            continue
        if not is_currently_trusted(knowledge, association, evaluation_date):
            unresolved_associations.add(association.id)
            continue

        version = version_by_id.get(association.service_point_version_id)
        if (
            version is None
            or not is_currently_trusted(knowledge, version, evaluation_date)
            or not _date_applies(
                evaluation_date,
                version.effective_from,
                version.effective_to,
            )
        ):
            unresolved_associations.add(association.id)
            continue
        point = point_by_id.get(version.service_point_id)
        if point is None:
            unresolved_associations.add(association.id)
            continue
        selected.append(SemanticServicePoint(point, version, association))

    selected = sorted(
        selected,
        key=lambda item: (
            item.point.id,
            item.version.id,
            item.association.id,
        ),
    )
    if selected and unresolved_associations:
        status = "partially_resolved"
    elif selected:
        status = "resolved"
    else:
        status = "unresolved"

    routing = SemanticRouting(
        status=status,
        service_points=tuple(selected),
        unresolved_association_ids=tuple(sorted(unresolved_associations)),
        unresolved_fact_keys=tuple(sorted(unresolved_facts)),
        verification_path=knowledge.routing_verification_path,
    )
    return routing, tuple(traces)


def assemble_plan(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    evaluation_date: date,
    *,
    submitted_keys: frozenset[str] | None = None,
    generated_on: date | None = None,
    catalog: KnowledgeCatalog | None = None,
    historical: bool = False,
    upcoming_versions: tuple[KnowledgeBundle, ...] = (),
) -> PlanAssembly:
    """Assemble one Procedure plan while preserving local uncertainty."""
    submitted = frozenset(facts) if submitted_keys is None else submitted_keys
    generated = evaluation_date if generated_on is None else generated_on
    derived = derive_facts(dict(facts), evaluation_date)
    traces: list[RuleEvaluationRecord] = []

    procedure_result = evaluate(
        knowledge.procedure.applicability,
        derived,
        submitted_keys=submitted,
    )
    traces.append(
        record_evaluation(
            f"procedure_applicability:{knowledge.procedure.procedure_id}",
            procedure_result,
            consequential_to_planning=True,
        )
    )
    if procedure_result.value is TruthValue.FALSE:
        raise ProcedureNotApplicable(
            knowledge.procedure.procedure_id,
            tuple(traces),
        )
    if procedure_result.value is TruthValue.UNKNOWN:
        return PlanAssembly(
            None,
            procedure_result.missing_facts,
            tuple(traces),
        )

    (
        bases,
        basis_missing,
        basis_traces,
        inconclusive_basis_ids,
    ) = _select_bases(
        knowledge,
        derived,
        submitted,
        evaluation_date,
    )
    traces.extend(basis_traces)
    if basis_missing:
        return PlanAssembly(None, basis_missing, tuple(traces))
    if knowledge.eligibility_bases and not bases and not inconclusive_basis_ids:
        assert knowledge.no_applicable_basis_text is not None
        assert knowledge.basis_verification_path is not None
        raise NoApplicableBasis(
            knowledge.procedure.procedure_id,
            knowledge.no_applicable_basis_text,
            knowledge.basis_verification_path,
            tuple(traces),
        )

    matched_basis_ids = frozenset(
        basis.id for basis in bases if basis.id not in inconclusive_basis_ids
    )

    claims, claim_missing, claim_traces = _select_items(
        knowledge,
        knowledge.claims,
        derived,
        submitted,
        context_prefix="claim",
        consequential=True,
        matched_basis_ids=matched_basis_ids,
        evaluation_date=evaluation_date,
    )
    traces.extend(claim_traces)

    steps, step_missing, step_traces = _select_items(
        knowledge,
        knowledge.steps,
        derived,
        submitted,
        context_prefix="step",
        consequential=True,
        matched_basis_ids=matched_basis_ids,
        evaluation_date=evaluation_date,
    )
    traces.extend(step_traces)

    fees, fee_missing, fee_traces = _select_fees(
        knowledge,
        knowledge.fees,
        derived,
        submitted,
        evaluation_date,
    )
    traces.extend(fee_traces)

    dependencies, dependency_missing, dependency_traces = _select_dependencies(
        knowledge,
        catalog,
        derived,
        submitted,
        evaluation_date,
    )
    traces.extend(dependency_traces)

    routing, routing_traces = _select_routing(
        knowledge,
        derived,
        submitted,
        evaluation_date,
    )
    traces.extend(routing_traces)

    unknowns: list[UnknownDefinition] = []
    for item in knowledge.unknowns:
        result = evaluate(
            item.applicability,
            derived,
            submitted_keys=submitted,
        )
        traces.append(
            record_evaluation(
                f"unknown:{item.id}",
                result,
                consequential_to_planning=False,
            )
        )
        if result.value is TruthValue.TRUE:
            unknowns.append(item)

    historical_items = (
        _historical_items(
            knowledge,
            knowledge.claims,
            derived,
            submitted,
            evaluation_date,
            kind="claim",
            matched_basis_ids=matched_basis_ids,
        )
        + _historical_items(
            knowledge,
            knowledge.steps,
            derived,
            submitted,
            evaluation_date,
            kind="step",
            matched_basis_ids=matched_basis_ids,
        )
        + _historical_items(
            knowledge,
            knowledge.fees,
            derived,
            submitted,
            evaluation_date,
            kind="fee",
            matched_basis_ids=matched_basis_ids,
        )
    )

    untrusted_claims = _applicable_untrusted_items(
        knowledge,
        knowledge.claims,
        derived,
        submitted,
        evaluation_date,
        matched_basis_ids=matched_basis_ids,
    )
    untrusted_steps = _applicable_untrusted_items(
        knowledge,
        knowledge.steps,
        derived,
        submitted,
        evaluation_date,
        matched_basis_ids=matched_basis_ids,
    )
    # Candidate/research-only claim records remain internal unless they become
    # current. Only consequential official requirements/steps are surfaced as
    # local inconclusive decisions.
    inconclusive_claim_ids = {
        item.id
        for item in untrusted_claims
        if getattr(item, "classification", None) == "official_requirement"
    }
    inconclusive_claim_ids.update(item.id for item in untrusted_steps)

    missing = claim_missing | step_missing | fee_missing | dependency_missing
    if missing:
        return PlanAssembly(None, missing, tuple(traces))

    semantic_plan = SemanticPlan(
        knowledge=knowledge,
        facts=derived,
        evaluation_date=evaluation_date,
        generated_on=generated,
        claims=tuple(
            sorted(claims, key=lambda item: (item.display_order, item.id))
        ),
        steps=tuple(
            sorted(
                steps,
                key=lambda item: (item.phase_order, item.slot, item.id),
            )
        ),
        fees=tuple(sorted(fees, key=lambda item: item.id)),
        service_points=routing.service_points,
        warnings=tuple(
            warning
            for warning in knowledge.warnings
            if warning.role == "regeneration"
            or is_currently_trusted(knowledge, warning, evaluation_date)
        ),
        unknowns=tuple(sorted(unknowns, key=lambda item: item.id)),
        eligibility_bases=bases,
        dependencies=dependencies,
        routing=routing,
        historical_items=tuple(
            sorted(
                historical_items,
                key=lambda entry: (
                    entry.kind,
                    getattr(entry.item, "display_order", 0),
                    getattr(entry.item, "id", ""),
                ),
            )
        ),
        inconclusive_claim_ids=tuple(sorted(inconclusive_claim_ids)),
        inconclusive_basis_ids=tuple(sorted(inconclusive_basis_ids)),
        historical=historical,
        upcoming_versions=upcoming_versions,
    )
    return PlanAssembly(semantic_plan, traces=tuple(traces))


def assemble_known_case_plan(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    evaluation_date: date,
) -> SemanticPlan:
    """Compatibility wrapper for the complete-input issue #5 API."""
    assembly = assemble_plan(
        knowledge,
        facts,
        evaluation_date,
        submitted_keys=frozenset(facts),
    )
    if assembly.plan is None:
        raise KnownCaseIncomplete(",".join(sorted(assembly.missing_facts)))
    return assembly.plan
