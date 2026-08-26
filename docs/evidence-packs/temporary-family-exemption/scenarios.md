# Temporary family exemption named scenarios

These scenarios are authored research expectations for later prototype tickets. They are **not legal determinations** and are not executable tests yet. Unless stated otherwise:

- Goal = `handle_military_service_paperwork`
- Procedure candidate = `temporary_family_exemption_from_military_service`
- evaluation date = `2026-08-26`
- specialist review has **not** been completed, so a candidate Basis may be identified but must not be rendered as a binding exemption decision.

## Goal and Procedure boundary

### `mil.goal.stable_across_military_paperwork`

**Expected**

- `handle_military_service_paperwork` remains a stable Goal while temporary exemption, final exemption, postponement, travel permission, certificate extraction and other military transactions remain distinct Procedures.
- A family circumstance does not cause the Goal itself to own legal rules or checklist claims.

### `mil.negative.outside_egypt`

```text
application_location = outside_egypt
```

**Expected**

- This domestic fixture does not apply.
- Consular/overseas military workflows are not synthesized from domestic evidence.

### `mil.negative.no_researched_family_ground`

```text
application_location = inside_egypt
father_alive = false
other_living_sons_of_father_count = 2
mother_family_status = other
unmarried_sisters_requiring_support_count = 0
missing_relative_category = none
sibling_service_status = none
```

**Expected**

- No researched family Eligibility Basis is identified.
- The planner does not pick a “closest” family exemption.
- Other military-paperwork Procedures may exist but are outside this fixture.

## Only-son Basis

### `mil.basis.only_son.positive_candidate`

```text
application_location = inside_egypt
father_alive = true
other_living_sons_of_father_count = 0
```

**Expected**

- `family.only_son_living_father` becomes a candidate matched Basis under the research rule.
- The plan states that authority/specialist confirmation is required before treating the legal ground as established.
- No unrelated support-of-mother/sister claims are added.

### `mil.basis.only_son.negative_other_son`

```text
father_alive = true
other_living_sons_of_father_count = 1
```

**Expected**

- Only-son candidate evaluates FALSE under the provisional typed rule.
- No legal interpretation is invented about whether a particular sibling should be excluded from the count; if such an exception matters, the case requires specialist/authority facts.

### `mil.basis.only_son.unknown_sibling_count`

```text
father_alive = true
# other_living_sons_of_father_count omitted
```

**Expected**

- Only-son candidate is UNKNOWN.
- `q.mil.other_sons_count` is askable.

### `mil.basis.only_son.negative_father_not_living`

```text
father_alive = false
other_living_sons_of_father_count = 0
```

**Expected**

- The living-father only-son Basis does not match.
- The planner must not transform it into a permanent-exemption ground from the same Article without a separate researched Procedure/Basis.

## Father / incapable-brother support Basis

### `mil.basis.father_support.documented_incapacity_candidate`

```text
father_alive = true
father_unable_to_earn_status = authority_documented_unable
other_capable_family_support_for_father = none_known
```

**Expected**

- `family.support_father_or_incapable_brothers` is potentially reachable.
- Final Basis truth remains specialist-sensitive because “sole breadwinner” and Article 7/Second(b) sub-branch semantics are not frozen.
- The result may request missing reviewed/authority facts or become locally inconclusive; it must not convert `none_known` into a legal sole-breadwinner conclusion.

### `mil.basis.father_support.no_documented_incapacity`

```text
father_unable_to_earn_status = not_documented_unable
```

**Expected**

- The fixture cannot establish the father-incapacity predicate.
- It does not ask the user to self-diagnose legal/medical inability to earn.

### `mil.basis.father_support.unknown_support_semantics`

```text
father_unable_to_earn_status = authority_documented_unable
# other_capable_family_support_for_father omitted
```

**Expected**

- Candidate Basis remains consequentially UNKNOWN/inconclusive.
- No generic fallback assumes the applicant is the only supporter.

## Mother support Basis

### `mil.basis.mother_support.widowed_candidate`

```text
mother_family_status = widowed
other_capable_family_support_for_mother = none_known
```

**Expected**

- `family.support_mother` becomes potentially reachable.
- Legal sole-support conclusion stays subject to reviewed semantics and authority evidence.

### `mil.basis.mother_support.irrevocably_divorced_candidate`

```text
mother_family_status = irrevocably_divorced
other_capable_family_support_for_mother = none_known
```

**Expected**

- Same candidate Basis, distinct factual branch.
- The product does not replace the statutory divorce classification with fuzzy free text.

### `mil.basis.mother_support.husband_unable_candidate`

```text
mother_family_status = husband_authority_documented_unable
other_capable_family_support_for_mother = none_known
```

**Expected**

- Same candidate Basis remains possible.
- “Unable to earn” is accepted only as the typed authority/documented status defined by the fixture, not inferred from narrative.

### `mil.basis.mother_support.negative_other_status`

```text
mother_family_status = other
```

**Expected**

- The enumerated mother-status condition does not match this Basis.

### `mil.basis.mother_support.unknown_status`

```text
# mother_family_status omitted
```

**Expected**

- Candidate branch is UNKNOWN if it can still affect the plan.
- `q.mil.mother_status` is askable only when the mother-support branch is consequential.

## Unmarried-sister support Basis

### `mil.basis.sisters.positive_candidate`

```text
unmarried_sisters_requiring_support_count = 2
other_capable_family_support_for_sisters = none_known
```

**Expected**

- `family.support_unmarried_sisters` becomes potentially reachable.
- No legal sole-support conclusion is produced until the reviewed support predicate is established.

### `mil.basis.sisters.negative_zero`

```text
unmarried_sisters_requiring_support_count = 0
```

**Expected**

- Sister-support Basis evaluates FALSE.

### `mil.basis.sisters.unknown_count`

```text
# unmarried_sisters_requiring_support_count omitted
```

**Expected**

- UNKNOWN only when this Basis remains reachable/consequential.

## Missing-person Basis and 2026 amendment

### `mil.basis.missing.positive_war_after_amendment`

```text
missing_relative_category = citizen
missing_relative_cause = war_operations
missing_relative_alive_status = missing
applicant_largest_eligible_relative_status = authority_documented_yes
evaluation_date = 2026-08-26
```

**Expected**

- `family.missing_war_or_terror_relative` is a candidate match.
- Current Law No. 2/2026 version is selected.
- Authority/specialist review remains required.

### `mil.basis.missing.positive_terror_after_amendment`

```text
missing_relative_category = officer
missing_relative_cause = terrorist_operations
missing_relative_alive_status = missing
applicant_largest_eligible_relative_status = authority_documented_yes
evaluation_date = 2026-03-25
```

**Expected**

- Terrorist-operations branch is available beginning on the amendment effective date.
- Claim uses `EL-LAW2-2026-ART7-II-E`, not the superseded original clause.

### `mil.basis.missing.terror_before_amendment`

```text
missing_relative_category = officer
missing_relative_cause = terrorist_operations
missing_relative_alive_status = missing
applicant_largest_eligible_relative_status = authority_documented_yes
evaluation_date = 2026-03-24
```

**Expected**

- The future-effective 2026 replacement clause is not applied retroactively by the prototype.
- The historical Procedure Version must use the pre-amendment rule.
- This fixture does not assert that another historical legal theory applies; the terrorist-operations branch from Law No. 2/2026 is simply not active yet.

### `mil.basis.missing.negative_other_cause`

```text
missing_relative_cause = other
```

**Expected**

- Current war/terror statutory cause predicate does not match.

### `mil.basis.missing.lapse_returned_alive`

```text
missing_relative_cause = terrorist_operations
missing_relative_alive_status = returned_or_proven_alive
applicant_largest_eligible_relative_status = authority_documented_yes
```

**Expected**

- Missing-person Basis is not treated as continuing.
- The current amendment's lapse behavior is surfaced for specialist-reviewed guidance.

### `mil.basis.missing.unknown_largest_eligible`

```text
missing_relative_cause = war_operations
missing_relative_alive_status = missing
# applicant_largest_eligible_relative_status omitted
```

**Expected**

- Basis remains UNKNOWN/inconclusive.
- The planner must not calculate all relatives' legal conscription eligibility from insufficient family prose.

## Sibling-current-service Basis

### `mil.basis.sibling_service.compulsory_candidate`

```text
sibling_service_status = compulsory_service
applicant_eldest_remaining_brother_status = authority_documented_yes
article7_third_exclusion_status = none_documented
```

**Expected**

- `family.sibling_current_service` becomes a candidate Basis.
- Complete Article 7/Third conditions still require specialist review.

### `mil.basis.sibling_service.reserve_candidate`

```text
sibling_service_status = reserve_recall
applicant_eldest_remaining_brother_status = authority_documented_yes
article7_third_exclusion_status = none_documented
```

**Expected**

- Reserve-recall branch is represented distinctly from ordinary compulsory service but maps to the same researched Basis.

### `mil.basis.sibling_service.negative_none`

```text
sibling_service_status = none
```

**Expected**

- Sibling-current-service Basis evaluates FALSE.

### `mil.basis.sibling_service.exclusion_present`

```text
sibling_service_status = compulsory_service
applicant_eldest_remaining_brother_status = authority_documented_yes
article7_third_exclusion_status = exclusion_present
```

**Expected**

- Basis cannot be treated as matched.
- The user-facing result should not expose raw specialist/editor notes about the exclusion; it should state that this ground could not be established and provide an authority verification path.

## Additive Basis behavior

### `mil.bases.multiple_support_candidates`

```text
father_unable_to_earn_status = authority_documented_unable
other_capable_family_support_for_father = none_known
unmarried_sisters_requiring_support_count = 1
other_capable_family_support_for_sisters = none_known
```

**Expected**

- Father-support and sister-support grounds may both remain candidate/reachable Bases.
- The planner preserves them as separate identities with separate evidence.
- It does not merge the claims into one generic “family breadwinner” Basis, rank one as best, or silently discard the other.
- Shared Procedure claims appear once; Basis-specific legal claims remain distinct.

### `mil.bases.one_false_does_not_erase_other`

```text
father_unable_to_earn_status = not_documented_unable
unmarried_sisters_requiring_support_count = 1
other_capable_family_support_for_sisters = none_known
```

**Expected**

- Father-support branch can fail without suppressing the independently reachable sister-support branch.

## Temporary cause lapse

### `mil.shared.cause_ends_reporting_window`

**Expected**

- Once a temporary-exemption cause is established as ended, the researched shared claim requires presentation to the competent region within 30 days.
- Deadline is represented as a calendar-date derivation from an explicit `cause_end_date` if a later fixture adds that Fact; no system clock is implicit.
- The plan never implies that an expired temporary exemption remains effective until the user chooses to report.

## Documents, fees and authority review

### `mil.documents.no_basis_specific_list_invented`

**Expected**

- The current MOD instruction to present supporting documents is rendered at the correct high level after review.
- The generic 2026 recruitment document list is not copied wholesale as a family-exemption checklist.
- Missing basis-specific documents are shown as unresolved/editorial gaps rather than guessed quantities or form names.

### `mil.fee.official_service_amount_unknown`

**Expected**

- The certificate service can indicate that fees are determined and payable after result review.
- No current numeric amount is rendered because the official page retrieved did not publish one upfront.

### `mil.authority.rule_match_not_decision`

**Expected**

- A candidate Basis match leads to an authority-review step.
- Result wording never says “you are exempt” solely because a local rule evaluates TRUE.
- Product warning `mil.warning.authority_decides` is present without pretending it is a government-sourced claim.

## Routing and certificate service

### `mil.routing.giza`

```text
residence_governorate = giza
```

**Expected**

- Current official region association can resolve to `sp.recruitment_giza_haram`.
- No nearest-office ranking is performed.

### `mil.routing.dakahlia`

```text
residence_governorate = dakahlia
```

**Expected**

- Resolves to `sp.recruitment_mansoura_sandoub` under current official mapping.

### `mil.routing.sharqia`

```text
residence_governorate = sharqia
```

**Expected**

- Resolves to `sp.recruitment_zagazig_tel_basta`.

### `mil.routing.unknown_governorate`

```text
# residence_governorate omitted
```

**Expected**

- Legal Basis research remains available.
- Routing is locally UNKNOWN and an appropriate location Question is askable only when needed.

### `mil.routing.legacy_label_not_silently_normalized`

**Expected**

- If the current official page uses a legacy administrative label, the fixture does not invent a modern mapping without reviewed editorial normalization.
- `DISC-MIL-REGION-LABEL-NORMALIZATION` remains internal.

### `mil.certificate.online_service_scope_caveat`

**Expected**

- `sp.tagned_exemption_certificate_online` may be exposed as an official certificate-service destination.
- The plan does not claim the online form replaces first-time legal adjudication for every Basis.
- If specialists direct the person to the Administration/region, that authority-review result is respected.

## Evidence and trust scenarios

### `mil.evidence.2026_amendment_overrides_old_clause`

**Expected**

- For evaluation dates on/after 2026-03-25, superseded Article 7/Second(e) evidence does not control current output.
- The old source remains preserved as historical context and discrepancy evidence.

### `mil.evidence.specialist_gate_blocks_public_authority`

**Expected**

- Even current statutory Evidence Links cannot become authoritative public legal-eligibility conclusions until specialist review is recorded.
- The prototype fixture can test rule behavior, but publication state remains blocked.

### `mil.evidence.discrepancies_internal_only`

**Expected**

- Amendment, certificate-scope and routing-normalization discrepancy records remain internal/admin-only.
- User-facing uncertainty is concise and expressed through claim state, authority-review requirement or local inconclusiveness.

### `mil.evidence.storage_display_separation`

**Expected**

- Each legal Basis retains its own Source/Evidence Link identity internally.
- Public UI may group sources or expose them on demand.
- Shared warnings/product limits do not need a separate government citation if they add no external administrative assertion.

## Invalid and contradictory Facts

### `mil.invalid.negative_sibling_count`

```text
other_living_sons_of_father_count = -1
```

**Expected**

- Invalid integer-bound diagnostic.

### `mil.invalid.null_mother_status`

```text
mother_family_status = null
```

**Expected**

- Invalid Fact; omission is generic UNKNOWN.

### `mil.invalid.free_text_incapacity`

```text
father_unable_to_earn_status = "he is too sick to work"
```

**Expected**

- Invalid enum/type diagnostic.
- The evaluator does not parse free text into an authority-documented legal/medical status.

### `mil.contradictory.father_alive_and_dead_if_schema_split`

The preferred boolean prevents simultaneous states. If later source Facts split this into independent assertions, `father_alive=true` and `father_deceased=true` must be diagnosed as contradictory rather than selecting between only-son/permanent-exemption implications.

### `mil.contradictory.missing_and_proven_alive`

A future schema must not allow the same relevant person to be both currently `missing` and `returned_or_proven_alive` at the same evaluation date. If represented by separate Facts, the combination is invalid/contradictory, not UNKNOWN.

## Bilingual and reproducibility

### `mil.locale.ar_en_same_decision`

Evaluate an identical candidate-Basis case in Arabic and English.

**Expected**

- same Goal, Procedure, candidate Basis IDs, rule states, evidence identities, authority-review state, routing, and fee state;
- only user-facing wording changes.

### `mil.reproducible.terror_basis_after_amendment`

Repeat `mil.basis.missing.positive_terror_after_amendment` with identical knowledge version, Facts, locale, evaluation date and rules contract.

**Expected**

- structurally identical result and trace every run;
- same 2026 Procedure Version/evidence selection;
- no persisted Anonymous Case and no raw Fact logging.

## Scenario coverage finding

This fixture materially requires scenario coverage for:

- stable Goal / distinct military Procedures;
- six candidate family Eligibility Bases;
- additive Basis behavior without hidden priority;
- authority-recorded statuses for specialist-sensitive predicates;
- current vs historical statutory wording at the 2026-03-25 effective-date boundary;
- local inconclusiveness for unresolved sole-support/kinship semantics;
- authority adjudication after planner rule evaluation;
- incomplete basis-specific document research without fabricated requirements;
- official service with unknown numeric fee;
- recruitment-region jurisdiction routing and legacy-label review;
- certificate-service scope separation;
- internal-only Evidence Discrepancies;
- invalid and contradictory Facts;
- bilingual deterministic output and reproducibility.
