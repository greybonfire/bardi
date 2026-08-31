from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import KnowledgeBundle, KnowledgeCatalog, Predicate
from .versions import bundles_for_procedure


@dataclass(frozen=True)
class EligibilityBasisCapability:
    id: str
    reachability_fact_keys: tuple[str, ...]
    qualification_fact_keys: tuple[str, ...]


@dataclass(frozen=True)
class FixtureCapability:
    goal_id: str
    procedure_id: str
    procedure_version_ids: tuple[str, ...]
    rules_contract_versions: tuple[str, ...]
    fact_keys: tuple[str, ...]
    submitted_fact_keys: tuple[str, ...]
    derived_fact_keys: tuple[str, ...]
    question_fact_keys: tuple[str, ...]
    missing_question_fact_keys: tuple[str, ...]
    operators: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    claim_attributes: tuple[str, ...]
    eligibility_basis_count: int
    eligibility_basis_states: tuple[str, ...]
    eligibility_basis_fact_stages: tuple[EligibilityBasisCapability, ...]
    basis_scoped_claim_ids: tuple[str, ...]
    dependency_relations: tuple[str, ...]
    dependency_count: int
    routing_fact_keys: tuple[str, ...]
    service_point_ids: tuple[str, ...]
    service_point_version_count: int
    service_point_association_count: int
    routing_has_verification_path: bool
    publication_states: tuple[str, ...]
    verification_states: tuple[str, ...]
    fee_value_states: tuple[str, ...]
    source_classifications: tuple[str, ...]
    unresolved_evidence: tuple[str, ...]
    unsupported_assumptions: tuple[str, ...]
    production_contract_exclusions: tuple[str, ...]


@dataclass(frozen=True)
class PrototypeCapabilityReport:
    fixtures: tuple[FixtureCapability, ...]
    global_contract_exclusions: tuple[str, ...]


_GLOBAL_CONTRACT_EXCLUSIONS = (
    "Anonymous Case persistence",
    "raw Fact persistence or logging",
    "public or persisted Evaluation Trace trees",
    "internal Evidence Link and editorial discrepancy records in public plans",
    "synthetic test-only dependency, routing, fee, or claim variants",
    "framework-specific persistence/API choices from this throwaway prototype",
)


_FIXTURE_NOTES = {
    "ordinary_domestic_passport_renewal": (
        (
            "Previous-passport requirement remains needs_reverification and must not be promoted to current guidance.",
            "Standard turnaround is not established.",
            "Routing models only researched associations; there is no nearest-office ranking.",
            "No real direct Procedure dependency is established by the evidence pack.",
        ),
        (
            "passport.requirement.previous_passport remains unverified",
            "passport.turnaround.standard remains unknown",
        ),
    ),
    "ordinary_domestic_national_id_renewal": (
        (
            "The ordinary renewal fee amount is unknown.",
            "The exact service point is unresolved and requires directory verification.",
            "Previous-card requirement remains needs_reverification and is not current guidance.",
            "No real direct Procedure dependency is established by the evidence pack.",
        ),
        (
            "nid.fee.ordinary amount remains unknown",
            "nid.routing.exact_service_point remains unresolved",
            "nid.requirement.previous_card remains unverified",
        ),
    ),
    "temporary_family_exemption_from_military_service": (
        (
            "Eligibility Basis matches are research candidates, not exemption determinations; specialist and authority review remain required.",
            "Article 7 II-B reachability gates only the currently modeled father sub-route; incapable-brother qualification semantics remain unresolved and are not separately modeled.",
            "Exact Basis-specific document lists are unresolved.",
            "The exemption-certificate fee amount is unknown.",
            "Only researched recruitment-region mappings are modeled; there is no nearest-office ranking.",
            "No real direct Procedure dependency is established by the evidence pack.",
        ),
        (
            "all six Eligibility Bases remain needs_reverification",
            "Article 7 II-B incapable-brother semantics remain unresolved",
            "mil.documents.basis_specific remains unresolved",
            "mil.fee.current amount remains unknown",
            "the 2026 amendment text uses official Gazette metadata plus a secondary legal-text mirror",
        ),
    ),
}


def _walk(predicate: Predicate | None) -> Iterable[Predicate]:
    if predicate is None:
        return ()
    nodes = [predicate]
    for child in predicate.children:
        nodes.extend(_walk(child))
    return tuple(nodes)


def _fact_keys(predicate: Predicate | None) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                node.fact
                for node in _walk(predicate)
                if node.fact is not None
            }
        )
    )


def _predicates_for_bundle(bundle: KnowledgeBundle) -> tuple[Predicate, ...]:
    predicates: list[Predicate] = []

    def add(predicate: Predicate | None) -> None:
        if predicate is not None:
            predicates.append(predicate)

    add(bundle.procedure.applicability)
    for item in bundle.claims:
        add(item.applicability)
    for item in bundle.steps:
        add(item.applicability)
    for item in bundle.fees:
        add(item.applicability)
    for item in bundle.eligibility_bases:
        add(item.applicability)
        add(item.qualification)
    for item in bundle.dependencies:
        add(item.applicability)
        add(item.satisfied_when)
    for item in bundle.service_point_associations:
        add(item.applicability)
    for item in bundle.unknowns:
        add(item.applicability)
    return tuple(predicates)


def _claim_attributes(bundles: tuple[KnowledgeBundle, ...]) -> tuple[str, ...]:
    claims = tuple(claim for bundle in bundles for claim in bundle.claims)
    attributes = {
        "classification",
        "applicability",
        "evidence_link_ids",
        "verification_state",
        "display_order",
    }
    optional_checks = {
        "quantity": lambda claim: claim.quantity is not None,
        "document_type_id": lambda claim: claim.document_type_id is not None,
        "original_quantity": lambda claim: claim.original_quantity is not None,
        "copy_quantity": lambda claim: claim.copy_quantity is not None,
        "scope": lambda claim: claim.scope != "shared",
        "eligibility_basis_id": lambda claim: claim.eligibility_basis_id is not None,
        "verified_on": lambda claim: claim.verified_on is not None,
        "reverified_on": lambda claim: claim.reverified_on is not None,
        "effective_from": lambda claim: claim.effective_from is not None,
        "effective_to": lambda claim: claim.effective_to is not None,
        "claim_dependencies": lambda claim: bool(claim.claim_dependencies),
        "reverification_due_on": lambda claim: claim.reverification_due_on is not None,
    }
    for attribute, predicate in optional_checks.items():
        if any(predicate(claim) for claim in claims):
            attributes.add(attribute)
    return tuple(sorted(attributes))


def _verification_states(bundles: tuple[KnowledgeBundle, ...]) -> tuple[str, ...]:
    states: set[str] = set()
    for bundle in bundles:
        states.add(bundle.procedure.trust_state)
        for collection in (
            bundle.claims,
            bundle.steps,
            bundle.fees,
            bundle.eligibility_bases,
            bundle.dependencies,
            bundle.service_point_versions,
            bundle.service_point_associations,
            bundle.warnings,
            tuple(bundle.evidence_links.values()),
        ):
            for item in collection:
                state = getattr(item, "verification_state", None)
                if state is not None:
                    states.add(state)
    return tuple(sorted(states))


def _unresolved_evidence(bundles: tuple[KnowledgeBundle, ...]) -> tuple[str, ...]:
    unresolved: set[str] = set()
    for bundle in bundles:
        for claim in bundle.claims:
            if claim.verification_state != "current":
                unresolved.add(f"claim:{claim.id}:{claim.verification_state}")
        for basis in bundle.eligibility_bases:
            if basis.verification_state != "current":
                unresolved.add(f"basis:{basis.id}:{basis.verification_state}")
        for fee in bundle.fees:
            if fee.verification_state != "current" or fee.value_state in {"unknown", "unverified"}:
                unresolved.add(
                    f"fee:{fee.id}:{fee.value_state}/{fee.verification_state}"
                )
        for unknown in bundle.unknowns:
            unresolved.add(f"unknown:{unknown.id}")
        for source in bundle.sources.values():
            if source.classification != "official":
                unresolved.add(f"source:{source.id}:{source.classification}")
    return tuple(sorted(unresolved))


def _basis_fact_stages(
    bundles: tuple[KnowledgeBundle, ...],
) -> tuple[EligibilityBasisCapability, ...]:
    stages: dict[str, tuple[set[str], set[str]]] = {}
    for bundle in bundles:
        for basis in bundle.eligibility_bases:
            reachability, qualification = stages.setdefault(
                basis.id,
                (set(), set()),
            )
            reachability.update(_fact_keys(basis.applicability))
            qualification.update(_fact_keys(basis.qualification))
    return tuple(
        EligibilityBasisCapability(
            id=basis_id,
            reachability_fact_keys=tuple(sorted(reachability)),
            qualification_fact_keys=tuple(sorted(qualification)),
        )
        for basis_id, (reachability, qualification) in sorted(stages.items())
    )


def fixture_capability(
    catalog: KnowledgeCatalog,
    procedure_id: str,
) -> FixtureCapability:
    bundles = bundles_for_procedure(catalog, procedure_id)
    if not bundles:
        raise KeyError(procedure_id)
    goal_id = bundles[0].goal.id

    predicates: list[Predicate] = []
    goal = catalog.goals[goal_id]
    candidate = next(
        candidate
        for candidate in goal.candidates
        if candidate.procedure_id == procedure_id
    )
    predicates.append(candidate.applicability)
    for bundle in bundles:
        predicates.extend(_predicates_for_bundle(bundle))
    contradictions = tuple(
        item for item in catalog.contradictions if item.goal_id == goal_id
    )
    predicates.extend(item.condition for item in contradictions)

    nodes = tuple(node for predicate in predicates for node in _walk(predicate))
    fact_keys = tuple(sorted({node.fact for node in nodes if node.fact is not None}))
    definitions = catalog.fact_definitions
    derived_fact_keys = tuple(
        key
        for key in fact_keys
        if key in definitions and definitions[key].derived
    )
    submitted_fact_keys = tuple(
        key
        for key in fact_keys
        if key not in derived_fact_keys
    )
    question_resolved_keys = {
        key
        for question in catalog.questions
        if question.goal_id == goal_id
        for key in question.resolved_keys
    }
    question_fact_keys = tuple(
        key for key in submitted_fact_keys if key in question_resolved_keys
    )
    missing_question_fact_keys = tuple(
        key for key in submitted_fact_keys if key not in question_resolved_keys
    )

    routing_nodes = tuple(
        node
        for bundle in bundles
        for association in bundle.service_point_associations
        for node in _walk(association.applicability)
    )
    routing_fact_keys = tuple(
        sorted({node.fact for node in routing_nodes if node.fact is not None})
    )

    notes, unresolved_notes = _FIXTURE_NOTES.get(procedure_id, ((), ()))
    unresolved = set(_unresolved_evidence(bundles))
    unresolved.update(unresolved_notes)

    return FixtureCapability(
        goal_id=goal_id,
        procedure_id=procedure_id,
        procedure_version_ids=tuple(bundle.procedure.version_id for bundle in bundles),
        rules_contract_versions=tuple(
            sorted({bundle.procedure.rules_contract_version for bundle in bundles})
        ),
        fact_keys=fact_keys,
        submitted_fact_keys=submitted_fact_keys,
        derived_fact_keys=derived_fact_keys,
        question_fact_keys=question_fact_keys,
        missing_question_fact_keys=missing_question_fact_keys,
        operators=tuple(sorted({node.op for node in nodes})),
        contradiction_ids=tuple(sorted(item.id for item in contradictions)),
        claim_attributes=_claim_attributes(bundles),
        eligibility_basis_count=max(len(bundle.eligibility_bases) for bundle in bundles),
        eligibility_basis_states=tuple(
            sorted(
                {
                    basis.verification_state
                    for bundle in bundles
                    for basis in bundle.eligibility_bases
                }
            )
        ),
        eligibility_basis_fact_stages=_basis_fact_stages(bundles),
        basis_scoped_claim_ids=tuple(
            sorted(
                {
                    claim.id
                    for bundle in bundles
                    for claim in bundle.claims
                    if claim.scope == "eligibility_basis"
                }
            )
        ),
        dependency_relations=tuple(
            sorted(
                {
                    dependency.relation
                    for bundle in bundles
                    for dependency in bundle.dependencies
                }
            )
        ),
        dependency_count=max(len(bundle.dependencies) for bundle in bundles),
        routing_fact_keys=routing_fact_keys,
        service_point_ids=tuple(
            sorted(
                {
                    service_point.id
                    for bundle in bundles
                    for service_point in bundle.service_points
                }
            )
        ),
        service_point_version_count=max(
            len(bundle.service_point_versions) for bundle in bundles
        ),
        service_point_association_count=max(
            len(bundle.service_point_associations) for bundle in bundles
        ),
        routing_has_verification_path=any(
            bundle.routing_verification_path is not None for bundle in bundles
        ),
        publication_states=tuple(
            sorted({bundle.procedure.publication_state for bundle in bundles})
        ),
        verification_states=_verification_states(bundles),
        fee_value_states=tuple(
            sorted({fee.value_state for bundle in bundles for fee in bundle.fees})
        ),
        source_classifications=tuple(
            sorted(
                {
                    source.classification
                    for bundle in bundles
                    for source in bundle.sources.values()
                }
            )
        ),
        unresolved_evidence=tuple(sorted(unresolved)),
        unsupported_assumptions=tuple(notes),
        production_contract_exclusions=_GLOBAL_CONTRACT_EXCLUSIONS,
    )


def build_capability_report(catalog: KnowledgeCatalog) -> PrototypeCapabilityReport:
    procedure_ids = tuple(
        sorted(
            {
                bundle.procedure.procedure_id
                for bundle in catalog.fixtures.values()
            }
        )
    )
    return PrototypeCapabilityReport(
        fixtures=tuple(
            fixture_capability(catalog, procedure_id)
            for procedure_id in procedure_ids
        ),
        global_contract_exclusions=_GLOBAL_CONTRACT_EXCLUSIONS,
    )


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "None"


def render_capability_report(catalog: KnowledgeCatalog) -> str:
    report = build_capability_report(catalog)
    lines = [
        "# Prototype capability report",
        "",
        "This report is generated from the researched catalog structure. It records what the three pressure-test fixtures actually require; it is not a proposed production schema.",
        "",
        "## Cross-fixture conclusions",
        "",
        "- The same stateless `run_scenario()` seam executes passport renewal, National ID renewal, and military family-exemption research fixtures.",
        "- Omitted Facts remain UNKNOWN; raw Facts and Anonymous Cases do not need to be persisted for deterministic execution.",
        "- Rules use a small typed predicate AST with strong-Kleene three-valued evaluation.",
        "- Eligibility Basis reachability and qualification are separate stages; an unreachable Basis cannot make qualification-only Facts consequential.",
        "- Real researched fixtures currently establish no direct blocking Procedure dependency; that capability remains generic and synthetic-test-only.",
        "- Service Point identity, versioned material details, and Procedure-Version routing associations remain separate concepts.",
        "- Publication/version state remains separate from item/evidence trust state.",
        "",
        "### Concepts that should not enter the production contract from this prototype",
        "",
    ]
    lines.extend(f"- {item}" for item in report.global_contract_exclusions)

    for capability in report.fixtures:
        lines.extend(
            [
                "",
                f"## `{capability.procedure_id}`",
                "",
                f"- Goal: `{capability.goal_id}`",
                f"- Procedure Versions: {_csv(capability.procedure_version_ids)}",
                f"- Rules contract versions: {_csv(capability.rules_contract_versions)}",
                f"- Required Fact keys: {_csv(capability.fact_keys)}",
                f"- Submitted Fact keys: {_csv(capability.submitted_fact_keys)}",
                f"- Derived Facts: {_csv(capability.derived_fact_keys)}",
                f"- Questions covering required submitted Facts: {_csv(capability.question_fact_keys)}",
                f"- Missing Questions: {_csv(capability.missing_question_fact_keys)}",
                f"- Operators: {_csv(capability.operators)}",
                f"- Fixture contradictions: {_csv(capability.contradiction_ids)}",
                f"- Claim attributes used: {_csv(capability.claim_attributes)}",
                f"- Eligibility Bases: {capability.eligibility_basis_count}; states: {_csv(capability.eligibility_basis_states)}",
                f"- Basis-scoped claims: {_csv(capability.basis_scoped_claim_ids)}",
                f"- Real dependencies: {capability.dependency_count}; relations: {_csv(capability.dependency_relations)}",
                f"- Routing Facts: {_csv(capability.routing_fact_keys)}",
                f"- Service Points: {_csv(capability.service_point_ids)}",
                f"- Service Point material versions: {capability.service_point_version_count}",
                f"- Procedure-Service Point associations: {capability.service_point_association_count}",
                f"- Routing verification path available: {capability.routing_has_verification_path}",
                f"- Publication states: {_csv(capability.publication_states)}",
                f"- Verification/trust states represented: {_csv(capability.verification_states)}",
                f"- Fee value states represented: {_csv(capability.fee_value_states)}",
                f"- Source classifications represented: {_csv(capability.source_classifications)}",
                "",
                "### Eligibility Basis reachability and qualification Facts",
                "",
            ]
        )
        if capability.eligibility_basis_fact_stages:
            for basis in capability.eligibility_basis_fact_stages:
                lines.extend(
                    [
                        f"- `{basis.id}`",
                        f"  - Reachability: {_csv(basis.reachability_fact_keys)}",
                        f"  - Qualification: {_csv(basis.qualification_fact_keys)}",
                    ]
                )
        else:
            lines.append("- None")
        lines.extend(
            [
                "",
                "### Unresolved evidence / research state",
                "",
            ]
        )
        lines.extend(
            f"- {item}" for item in capability.unresolved_evidence
        )
        lines.extend(
            [
                "",
                "### Unsupported assumptions",
                "",
            ]
        )
        lines.extend(
            f"- {item}" for item in capability.unsupported_assumptions
        )

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    from .fixtures import load_researched_catalog

    print(render_capability_report(load_researched_catalog()), end="")