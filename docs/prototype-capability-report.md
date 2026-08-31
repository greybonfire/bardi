# Prototype capability report

This report closes the research-prototype loop for the three evidence-backed Procedures. It records what the fixtures actually require after issues #5–#11; it is **not** a proposed Django model, database schema, API contract, or publication workflow.

The structural portions can be reproduced from `prototype.bardi_prototype.capabilities.build_capability_report()`. The caveats below remain deliberately human-authored because they describe evidence limits and product boundaries rather than Python structure.

## Cross-fixture conclusions

All three researched evidence packs execute through the same stateless `run_scenario()` seam. Identical Goal, Facts, locale, Procedure Version, rules-contract version, and evaluation date produce structurally equal results without storing an Anonymous Case or raw Facts.

The fixture-proven rule language remains small: typed predicates, derived Facts, strong-Kleene TRUE/FALSE/UNKNOWN evaluation, deterministic Questions, explicit contradictions, and local routing uncertainty. Real evidence packs establish no direct blocking Procedure Dependency; direct dependency behavior is therefore a generic capability exercised only by synthetic tests.

### Do not promote to the production contract

The following are prototype/editor/testing concerns rather than domain concepts proven by the three evidence packs:

- Anonymous Case persistence as a requirement for planning.
- Raw Fact persistence or raw-Fact logging.
- Public or persisted Evaluation Trace trees.
- Internal Evidence Link objects and editorial discrepancy records in the public Personalized Plan.
- Synthetic test-only dependency, routing, fee, or claim variants.
- Compatibility aliases and fixture-loader conveniences introduced while the prototype evolved.
- Framework-specific persistence/API choices; the prototype does not justify Django model boundaries, PostgreSQL tables, or HTTP shapes by itself.
- Hidden nearest-office ranking, closest-match legal-ground selection, or recursive dependency planning.

## `ordinary_domestic_passport_renewal`

Procedure Version: `ordinary_domestic_passport_renewal.research-2026-08-25`  
Rules contract: `v1`  
Publication state represented: `published`

### Required Facts and Derived Facts

Required submitted Facts used by Procedure selection, current/candidate guidance, fees, routing, or unknown-state rules:

- `citizenship`
- `application_location`
- `existing_passport_state`
- `passport_class`
- `birth_date`
- `sex`
- `is_student`
- `service_level`
- `residence_police_jurisdiction`

Derived Facts actually used by rules:

- `age_years_on_evaluation_date`

Rule operators exercised: `all`, `eq`, `gte`, `in`, `lt`.

### Claim attributes

The fixture demonstrates claim classification, applicability, claim-specific Evidence Links, verification state, display order, document type identity, simple quantity, original quantity, and copy quantity. It does not require Basis scope or claim dependencies.

### Eligibility Basis behavior

None. Passport renewal has no Eligibility Basis collection.

### Dependencies

No real direct Procedure Dependency is asserted by the passport evidence pack.

### Routing

The fixture separates stable Service Point identity, versioned Service Point details, and the Procedure-Version association. The current researched association is `spa.passport_renewal.giza_standard`, keyed by `service_level` and `residence_police_jurisdiction`. Routing UNKNOWN remains local and an evidence-backed routing verification path is available.

There is no nearest-office ranking and no claim that the single researched Giza association is a nationwide routing model.

### Temporal and trust states

The Procedure Version is published/current. Current official requirements coexist with the `passport.requirement.previous_passport` candidate in `needs_reverification`; that candidate is neither current guidance nor historical guidance. Fee values are currently known for the researched base/accelerated services. Standard turnaround remains an explicit unknown.

### Missing Questions

`citizenship` is consequential to Goal-level Procedure selection but currently has **no authored Question**. If it is omitted, the public seam correctly returns a Procedure-selection configuration defect rather than inventing a value. The capability report intentionally preserves this as a foundation finding instead of silently adding a product question in issue #12.

### Unsupported assumptions

- Do not promote the previous-passport candidate until evidence is reverified.
- Do not invent standard turnaround.
- Do not infer nationwide office coverage or nearest-office ranking from the Giza routing fixture.
- Do not invent a direct blocking prerequisite Procedure.

## `ordinary_domestic_national_id_renewal`

Procedure Version: `ordinary_domestic_national_id_renewal.research-2026-08-26`  
Rules contract: `v1`  
Publication state represented: `published`

### Required Facts and Derived Facts

Required submitted Facts:

- `application_location`
- `national_id_possession_state`
- `national_id_data_change_kind`
- `national_id_expiry_date`

Derived Facts actually used by Procedure selection:

- `card_expired_before_evaluation_date`

The derivation layer also computes `renewal_deadline_date` and `renewal_deadline_passed` from the expiry date; issue #12 explicitly tests the exact three-calendar-month boundary even though those values are not currently selection predicates.

Rule operators exercised: `all`, `eq`, `exists`.

### Claim attributes

The fixture demonstrates claim classification, Evidence Links, verification state, display order, and document type identity. `nid.requirement.previous_card` remains a candidate with `needs_reverification` rather than current guidance.

### Eligibility Basis behavior

None. National ID renewal has no Eligibility Basis collection.

### Dependencies

No real direct Procedure Dependency is asserted by the National ID evidence pack.

### Routing

No exact Service Point is asserted. The Procedure includes a routing step and an official-directory verification path, while the public plan remains locally unresolved rather than globally inconclusive. Governorate/district Questions exist for future/local resolution, but the current evidence pack does not promote a nationwide office mapping.

### Temporal and trust states

The Procedure Version is published/current. The ordinary renewal fee uses the explicit `unknown` value state. The previous-card candidate uses `needs_reverification`. Turnaround and exact Service Point remain explicit unknowns.

### Missing Questions

None for the Facts currently required by the researched selection/contradiction rules. `q.nid.expiry_date` resolves both the submitted expiry date and the derived expired-before-evaluation-date Fact.

### Unsupported assumptions

- Do not invent an ordinary renewal fee amount.
- Do not invent an exact Service Point from governorate/district alone.
- Do not promote the previous-card candidate until reverified.
- Do not invent a direct blocking prerequisite Procedure.

## `temporary_family_exemption_from_military_service`

Procedure Versions:

- `temporary_family_exemption_from_military_service.research-2026-03-24` — effective through 2026-03-24.
- `temporary_family_exemption_from_military_service.research-2026-08-26` — effective from 2026-03-25.

Rules contract represented by both snapshots: `v1`  
Publication state represented: `published`

### Required Facts and Derived Facts

Required submitted Facts across Procedure selection, all six Basis rules, routing, and contradiction checks:

- `application_location`
- `father_alive`
- `other_living_sons_of_father_count`
- `father_unable_to_earn_status`
- `mother_family_status`
- `unmarried_sisters_requiring_support_count`
- `missing_relative_category`
- `missing_relative_cause`
- `missing_relative_alive_status`
- `applicant_largest_eligible_relative_status`
- `sibling_service_status`
- `applicant_eldest_remaining_brother_status`
- `article7_third_exclusion_status`
- `residence_governorate`

No derived Fact is currently required by the military rule snapshots. `only_son_candidate` exists in the prototype Fact registry but is not a fixture rule input and therefore should not be treated as a required production-domain concept.

Rule operators exercised across the two versions: `all`, `any`, `eq`, `exists`, `gt`, `in`.

### Claim attributes

The fixture requires shared versus Eligibility-Basis scope, stable `eligibility_basis_id`, claim classification, Evidence Links, verification state, display order, and document type identity. Basis-scoped candidate claims retain separate semantic identities and are not merged into the shared supporting-document claim.

### Eligibility Basis behavior

Six researched candidate Bases are evaluated exhaustively:

1. `family.only_son_living_father`
2. `family.support_father_or_incapable_brothers`
3. `family.support_mother`
4. `family.support_unmarried_sisters`
5. `family.missing_war_or_terror_relative`
6. `family.sibling_current_service`

Every real Basis remains `needs_reverification`. TRUE untrusted Bases may be shown as candidate alternatives and listed in `inconclusive_basis_ids`, but they **cannot unlock Basis-scoped current guidance**. UNKNOWN `needs_reverification` candidates may still drive authored Questions so the researched alternative set can be factually resolved. If all Bases are FALSE, the result is `no_applicable_basis` with an official verification path; the planner never chooses a closest match.

### Dependencies

No real direct Procedure Dependency is asserted by the military evidence pack. Synthetic tests remain the only proof of one-level blocking dependency behavior and cycle rejection.

### Routing

Three researched recruitment-region identities and associations are represented: Giza, Mansoura, and Zagazig. Routing is keyed by `residence_governorate`, evaluates all matching associations, and remains local if unresolved. The fixture does not rank regions by distance or claim nationwide completeness.

### Temporal and trust states

The March 24/25 boundary is an immutable Procedure-Version boundary. The pre-amendment snapshot only models the war-operations missing-relative wording; the amended snapshot includes terrorist operations. The amendment text currently combines official Gazette metadata with a secondary legal-text mirror, so the legal Bases remain specialist-sensitive and `needs_reverification`.

The exemption-certificate fee amount is `unknown`. Exact Basis-specific document lists are unresolved. Current shared operational steps and researched region routing remain separately sourced from the legal Basis candidates.

### Missing Questions

None for the source Facts currently referenced by military Procedure/Basis/routing/contradiction rules. The question catalog covers the exhaustive Basis Fact set plus `residence_governorate`.

### Unsupported assumptions

- A rule match is not an exemption decision or specialist legal approval.
- Do not invent exact Basis-specific document lists.
- Do not invent the certificate fee.
- Do not infer nationwide routing or nearest-region behavior beyond researched associations.
- Do not invent a direct blocking prerequisite Procedure.

## Acceptance-suite coverage

`prototype/tests/test_reproducibility_and_capabilities.py` is the final high-level foundation suite. It adds explicit coverage for:

- repeated structurally identical runs using an explicit Procedure Version for all three researched Procedures;
- no mutation or persistence requirement for supplied raw Facts;
- passport positive/negative/UNKNOWN behavior and exact age-15/age-19 boundaries;
- National ID positive/negative/UNKNOWN/contradictory behavior and the exact three-calendar-month deadline boundary;
- each of the six military Basis branches, all-FALSE/no-basis handling, UNKNOWN questioning, and contradiction handling;
- the military March 24/25 immutable-version edge;
- deterministic capability introspection and documentation of the one known missing Question (`citizenship`).

The earlier focused suites remain authoritative for detailed typed-rule semantics, traces, trust propagation, dependency cycles, Service Point temporal behavior, bilingual projection, evidence gating, and synthetic supported-edge behavior. Issue #12 does not duplicate those tests or promote their synthetic fixture data into researched guidance.
