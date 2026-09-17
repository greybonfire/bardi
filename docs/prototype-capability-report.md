# Prototype capability report

**Status:** Historical research record

The research prototype established the findings below for three evidence-backed Procedures;
it is not today's model, API or publication contract. All fixture publication/trust states below
refer to the retired research snapshot, not to published production guidance.

The executable prototype was retired under [ADR 0018](adr/0018-retire-research-prototype.md).
Its final state is preserved at `95128e22767edf8ffb9f3db838178b327b079aa0`. The full generated
Fact/operator/claim inventories and original report remain available without a second live copy:

```bash
git show 95128e22767edf8ffb9f3db838178b327b079aa0:docs/prototype-capability-report.md
```

Current [production contracts](architecture/README.md) and
[production acceptance coverage](production-parity.md) supersede prototype implementation shapes.
The retained evidence packs preserve source provenance and scenario rationale.

## Cross-fixture conclusions

All three fixtures used the same stateless `run_scenario()` seam. Identical Goal (now Service),
Facts, locale, Procedure Version, rules-contract version and evaluation date produced structurally
equal results without storing an Anonymous Case or raw Facts.

The researched rule language needed typed predicates, deterministic Derived Facts, strong-Kleene
TRUE/FALSE/UNKNOWN evaluation, deterministic Questions, explicit contradictions and local routing
uncertainty. Eligibility Basis **reachability precedes qualification**: an unreachable Basis
cannot introduce downstream qualification Questions. No evidence pack established a real direct
blocking Procedure Dependency; one-level dependency behavior and cycle rejection were synthetic
capability tests only.

### Do not promote to the production contract

The prototype did not justify persisted Cases/raw Facts, public or persisted Evaluation Traces,
editorial Evidence Links/discrepancies in public plans, or any particular framework/database/API
shape. Synthetic dependencies, routing, fees and claims were tests, not researched guidance.
Compatibility aliases and loader conveniences were not new domain concepts. Nearest-office
ranking, closest-match legal grounds and recursive dependency planning remained unsupported.

## `ordinary_domestic_passport_renewal`

Historical fixture: `ordinary_domestic_passport_renewal.research-2026-08-25`, published, rules `v1`.
See the [sources](evidence-packs/passport-renewal/sources.md) and
[scenarios](evidence-packs/passport-renewal/scenarios.md).

- The fixture exercised age derivation, age-15/age-19 boundaries, conditional requirements,
  document identity and simple/original/copy quantities; it needed no Eligibility Bases.
- Current official requirements coexisted with `passport.requirement.previous_passport` in
  `needs_reverification`. That candidate was neither current nor established historical guidance.
  Base/accelerated fees were known; standard turnaround was explicitly unknown.
- `spa.passport_renewal.giza_standard` separated office identity, versioned details and the
  Procedure association. It used `service_level` and `residence_police_jurisdiction`; UNKNOWN
  routing stayed local with an evidence-backed verification path, not nationwide/nearest-office
  coverage.
- Consequential selection Fact `citizenship` lacked an authored Question in this snapshot.
  Omission produced a selection-configuration defect, not an invented answer. This was a
  recorded foundation gap, not a current production claim.

Do not promote the previous-passport candidate without re-verification, invent turnaround or a
blocking prerequisite, or generalize the one researched routing association.

## `ordinary_domestic_national_id_renewal`

Historical fixture: `ordinary_domestic_national_id_renewal.research-2026-08-26`, published, rules `v1`.
See the [sources](evidence-packs/national-id-renewal/sources.md) and
[scenarios](evidence-packs/national-id-renewal/scenarios.md).

- Selection used `card_expired_before_evaluation_date`. Derivation also calculated
  `renewal_deadline_date` and `renewal_deadline_passed`; tests covered the exact three-calendar-month
  boundary although these were not selection predicates.
- The ordinary fee, turnaround and exact Service Point were unknown.
  `nid.requirement.previous_card` remained `needs_reverification`; no Eligibility Bases were needed.
- Routing provided a step and official-directory verification path, not an exact office.
  Governorate/district Questions did not establish a nationwide mapping; unresolved routing did
  not make the entire plan inconclusive.
- Required selection/contradiction Facts had Questions. `q.nid.expiry_date` resolved the submitted
  expiry date and derived expiry condition.

Do not invent the fee, infer an office from governorate/district alone, promote the previous-card
candidate without re-verification, or add a researched blocking prerequisite.

## `temporary_family_exemption_from_military_service`

Two published `v1` research snapshots straddled the amendment:
`temporary_family_exemption_from_military_service.research-2026-03-24` applied through March 24;
`temporary_family_exemption_from_military_service.research-2026-08-26` applied from March 25, 2026.
See the [sources](evidence-packs/temporary-family-exemption/sources.md) and
[scenarios](evidence-packs/temporary-family-exemption/scenarios.md).

Six candidate Bases were evaluated exhaustively, never ranked:

| Basis | Reachability Facts | Qualification Facts |
| --- | --- | --- |
| `family.only_son_living_father` | `father_alive` | `other_living_sons_of_father_count` |
| `family.support_father_or_incapable_brothers` | `father_alive` | `father_unable_to_earn_status` |
| `family.support_mother` | none | `mother_family_status` |
| `family.support_unmarried_sisters` | none | `unmarried_sisters_requiring_support_count` |
| `family.missing_war_or_terror_relative` | `missing_relative_category` | `missing_relative_cause`, `missing_relative_alive_status`, `applicant_largest_eligible_relative_status` |
| `family.sibling_current_service` | `sibling_service_status` | `applicant_eldest_remaining_brother_status`, `article7_third_exclusion_status` |

FALSE reachability skipped qualification; UNKNOWN reachability asked only reachability Facts.
Every real Basis remained `needs_reverification`: TRUE matches were candidate alternatives in
`inconclusive_basis_ids`, not authority to unlock Basis-scoped current guidance. UNKNOWN untrusted
candidates could still drive authored Questions. All-FALSE returned `no_applicable_basis` with an
official verification path. Both stages had source-Question coverage. No Derived Fact was a rule
input; registry entry `only_son_candidate` did not establish a required domain concept.

The Article 7 II-B name includes incapable brothers, but `father_alive` gated only the modeled
father sub-route: precise incapable-brother qualification was unresolved. Basis-scoped candidate
claims retained separate identities rather than being merged into shared supporting documents.

The earlier missing-relative wording covered war operations; the amended wording added terrorist
operations. Official Gazette metadata plus a secondary legal-text mirror did not remove the need
for specialist verification. Certificate fees and exact Basis-specific documents remained unknown.
Separately sourced shared operating guidance and Giza/Mansoura/Zagazig routing used
`residence_governorate`, evaluating all associations without nationwide or distance-ranking claims.
A rule match was not an exemption decision or specialist approval; no real prerequisite was asserted.

## Acceptance-suite coverage

At the archived commit, `prototype/tests/test_reproducibility_and_capabilities.py` covered
reproducibility without Fact mutation/persistence, positive/negative/UNKNOWN cases, National ID
and military contradictions, age/deadline boundaries, all six Bases, no-applicable-Basis handling,
the March 24/25 version edge and the missing citizenship Question.

`prototype/tests/test_eligibility_basis_reachability.py` captured the father-route bug, staged
Question coverage, skipped unreachable qualification, ungated mother/sister behavior, exhaustive
alternatives, editor trace separation and per-Basis introspection. These are historical evidence;
production acceptance tests now own supported behavior. Synthetic cases remain tests, not research.
