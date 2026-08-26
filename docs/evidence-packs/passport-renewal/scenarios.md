# Passport renewal named scenarios

These scenarios are authored evidence-pack expectations for later prototype tickets. They are not executable tests yet. They intentionally exercise Goal-to-Procedure organization, positive, negative, UNKNOWN, contradictory, supported-edge, evidence, and presentation behavior at the scenario seam required by #1.

Evaluation date for current scenarios unless stated otherwise: `2026-08-25`.

Unless a scenario says otherwise, the selected Goal is `get_egyptian_passport`. The Goal is an organizational set of related candidate Procedures and does not itself evaluate requirements, fees, steps, routing, or evidence.

## Goal and Procedure-selection scenarios

### `passport.goal.stable_across_related_procedures`

Evaluate the same Goal with different passport-state Facts:

```text
Goal = get_egyptian_passport
existing_passport_state = none | expired | pages_full | lost | damaged
```

**Expected**

- Goal remains `get_egyptian_passport` for all cases.
- The applicable Procedure may change as Facts change.
- `expired` or `pages_full` can resolve to `ordinary_domestic_passport_renewal` when the other supported boundary Facts match.
- `none`, `lost`, and `damaged` point toward distinct related Procedures and must not be collapsed into renewal.
- The Goal itself contributes no checklist items, fees, steps, routing rules, or Evidence Links.
- An unresearched related Procedure remains unsupported rather than causing the Goal identity to change.

### `passport.positive.adult_expired_standard`

**Facts**

```text
citizenship = egyptian
application_location = inside_egypt
existing_passport_state = expired
passport_class = ordinary
birth_date = 1995-06-10
sex = female
national_id_status = valid_current_data
is_student = false
service_level = standard
residence_police_jurisdiction = giza
```

**Expected**

- Goal remains `get_egyptian_passport`.
- Procedure resolves to `ordinary_domestic_passport_renewal`.
- Adult National ID claim applies.
- Birth-certificate claim does not apply.
- Student and military claims do not apply.
- Three-photo and originals/copy claims apply.
- Previous-passport candidate does **not** render as current authoritative guidance until re-verified.
- Routing can return the researched Giza Service Point association.
- Base fee renders as 705 EGP for this research snapshot.
- Standard turnaround remains unknown.

### `passport.positive.minor_pages_full`

**Facts**

```text
citizenship = egyptian
application_location = inside_egypt
existing_passport_state = pages_full
passport_class = ordinary
birth_date = 2013-12-01
sex = female
is_student = true
service_level = standard
residence_police_jurisdiction = giza
minor_presenting_adult_role = unknown
```

**Expected**

- Goal remains `get_egyptian_passport`.
- Procedure resolves to renewal.
- Machine-readable birth-certificate claim applies.
- National ID claim does not apply.
- Current-year student-enrollment claim applies.
- Minor submission-authority portion is locally inconclusive because the domestic rule remains unresolved.
- Supported checklist claims remain available; the planner must not silently invent a parent/guardian rule.

### `passport.negative.first_issuance`

**Facts**

```text
citizenship = egyptian
application_location = inside_egypt
existing_passport_state = none
passport_class = ordinary
```

**Expected**

- Goal remains `get_egyptian_passport`.
- This Procedure evaluates FALSE.
- The result must not repurpose renewal as first issuance.
- When cross-fixture Procedure selection is implemented, a curated first-issuance Procedure may be selected only if separately researched.

### `passport.negative.lost_passport`

**Facts**

```text
citizenship = egyptian
application_location = inside_egypt
existing_passport_state = lost
passport_class = ordinary
```

**Expected**

- Goal remains `get_egyptian_passport`.
- Renewal evaluates FALSE / recognized unsupported for this fixture.
- Lost-passport replacement must be named as a distinct Procedure rather than treated as a renewal branch.

### `passport.negative.damaged_passport`

**Facts**

```text
citizenship = egyptian
application_location = inside_egypt
existing_passport_state = damaged
passport_class = ordinary
```

**Expected**

- Goal remains `get_egyptian_passport`.
- Renewal evaluates FALSE / recognized unsupported.
- Damaged-passport replacement remains a distinct Procedure.

### `passport.negative.consular`

**Facts**

```text
citizenship = egyptian
application_location = outside_egypt
existing_passport_state = expired
passport_class = ordinary
```

**Expected**

- Goal may still be `get_egyptian_passport`.
- Domestic renewal fixture does not apply.
- Current consular evidence may not be borrowed to fabricate a domestic/overseas universal route.

### `passport.unknown.passport_state`

**Facts**

```text
citizenship = egyptian
application_location = inside_egypt
passport_class = ordinary
```

**Expected**

- Renewal applicability is UNKNOWN because `existing_passport_state` is omitted.
- Next Question is `q.existing_passport_state` once higher-priority unresolved boundary facts are known.
- No checklist is returned yet if the top-level discriminated result is next Question.

### `passport.unknown.application_location`

**Facts**

```text
citizenship = egyptian
existing_passport_state = expired
passport_class = ordinary
```

**Expected**

- Domestic applicability is UNKNOWN.
- `q.application_location` wins over lower-priority Questions.

## Identity-document branch scenarios

### `passport.edge.turns_15_on_evaluation_date`

**Facts**

```text
birth_date = 2011-08-25
```

**Expected**

- `age_years_on_evaluation_date = 15`.
- National ID branch applies.
- Birth-certificate-under-15 branch does not apply.
- This guards against the stale former age-16 rule.

### `passport.edge.one_day_before_15`

**Facts**

```text
birth_date = 2011-08-26
```

**Expected**

- `age_years_on_evaluation_date = 14`.
- Under-15 birth-certificate branch applies.

### `passport.unknown.birth_date`

**Facts**

```text
citizenship = egyptian
application_location = inside_egypt
existing_passport_state = expired
passport_class = ordinary
```

**Expected**

- Identity-document branch is consequentially UNKNOWN.
- `q.birth_date` becomes the next relevant Question after boundary Questions are resolved.

### `passport.invalid.birth_date_string_shape`

**Facts**

```text
birth_date = "25/08/2000"
```

**Expected**

- Invalid Fact diagnostic, not UNKNOWN.
- No date-format coercion.

## Student branch scenarios

### `passport.positive.student`

**Facts**

```text
is_student = true
```

**Expected**

- Current-academic-year enrollment certificate claim applies.

### `passport.negative.not_student`

**Facts**

```text
is_student = false
```

**Expected**

- Enrollment certificate claim evaluates FALSE and is omitted.

### `passport.unknown.student_status`

**Facts**

```text
# is_student omitted
```

**Expected**

- Student checklist applicability is UNKNOWN.
- If no other unresolved branch can change more consequential output first, `q.is_student` is askable.

## Military-document scenarios

### `passport.positive.male_military_document_branch`

**Facts**

```text
sex = male
birth_date = 1995-01-01
```

**Expected**

- Military-status document claim applies under the current source’s ordinary mechanical branch.
- The plan must not infer a person’s military legal status; it only requires the authority-issued document where the rule applies.

### `passport.negative.female_military_document_branch`

**Facts**

```text
sex = female
birth_date = 1995-01-01
```

**Expected**

- Military-status-document requirement does not apply.

### `passport.edge.male_under_19`

**Facts**

```text
sex = male
birth_date = 2008-08-26
```

**Expected**

- Age on evaluation date is 17.
- Military-document branch does not apply.

### `passport.unknown.sex_for_military_branch`

**Facts**

```text
birth_date = 1995-01-01
```

**Expected**

- Military branch remains UNKNOWN.
- `q.sex` can resolve it.

## Service-level and routing scenarios

### `passport.positive.urgent_next_working_day`

**Facts**

```text
service_level = urgent
```

**Expected**

- Urgent fee claim: 100 EGP additional fee.
- Published timing: next working day.
- All evidenced eligible urgent Service Points may be returned; no unsupported ranking.

### `passport.positive.premium_same_day`

**Facts**

```text
service_level = premium
```

**Expected**

- Premium fee claim: 500 EGP additional fee.
- Published timing: same day.
- All evidenced premium-capable Service Points may be returned.

### `passport.routing.standard_giza`

**Facts**

```text
service_level = standard
residence_police_jurisdiction = giza
```

**Expected**

- Researched Giza Passport Office association matches.
- Routing result carries the office’s published territorial context.

### `passport.routing.unknown_district`

**Facts**

```text
service_level = standard
# residence_police_jurisdiction omitted
```

**Expected**

- Routing is UNKNOWN and `q.residence_police_jurisdiction` is askable.
- Already reliable checklist/fee claims remain semantically independent; when the application result variant allows a full Plan, only the routing subsection should be inconclusive.

### `passport.routing.unresearched_district`

**Facts**

```text
service_level = standard
residence_police_jurisdiction = a_valid_but_not_fixture_encoded_district
```

**Expected**

- No invented nearest-office fallback.
- Routing is locally inconclusive with official verification path.
- Other reliable requirements remain available.

## Evidence/trust and presentation scenarios

### `passport.evidence.previous_passport_not_publishable`

**Expected**

- `passport.requirement.previous_passport` has corroborating historical/consular evidence but no recovered current domestic exact-passage support.
- It must be excluded from current authoritative checklist output.
- Editor-facing result identifies `needs-reverification`, not TRUE/FALSE domain applicability.

### `passport.evidence.age_stale_source_does_not_override`

**Expected**

- Current Ministry age-15 claim remains the current claim.
- Stale age-16 government material is retained as internal discrepancy/history.
- The fixture does not choose a source merely by a generic “newest URL” rule; internal adjudication records competent authority, applicability and staleness.
- The public plan does not expose the discrepancy record or editorial rationale verbatim.

### `passport.evidence.field_fee_report_not_guidance`

**Expected**

- Low-context 2026 field-style fee report is not public Field Guidance.
- Current official base fee remains 705 EGP for the research snapshot.
- The field report may trigger re-verification internally but cannot override the official claim.

### `passport.evidence.standard_turnaround_unknown`

**Expected**

- Standard turnaround is represented as unknown.
- The plan never synthesizes a value from older or secondary reports.
- Urgent/premium timings remain available because they have current first-party support.

### `passport.evidence.storage_does_not_dictate_display`

**Expected**

- Evidence-bearing administrative claims retain their internal Evidence Links and Source provenance.
- The public plan is not required to render one citation beside every checklist line or sentence.
- The presentation layer may group sources, show compact verification metadata, or expose claim-specific evidence on demand without changing stored provenance.
- Goal/Procedure labels, Question wording, Derived Fact explanations, UI grouping, and product safety warnings require no independent Evidence Link when they introduce no new administrative assertion.
- Internal Evidence Discrepancy records and adjudication rationale are excluded from the public planning contract.
- Any user-facing explanation of uncertainty is concise and derived from the claim state rather than exposing admin/editorial notes.

## Contradictory and invalid case scenarios

### `passport.contradictory.passport_none_and_expired`

This contradiction is represented at the input-contract level once the final Fact vocabulary is encoded. A single enum-valued `existing_passport_state` prevents this exact contradiction by construction. If a future schema splits these into booleans such as `has_existing_passport` and `existing_passport_expired`, the combination `false` + `true` must be diagnosed as contradictory rather than UNKNOWN.

**Capability finding:** prefer one normalized enum Fact for mutually exclusive passport states to prevent avoidable contradiction space.

### `passport.invalid.null_fact`

**Facts**

```text
is_student = null
```

**Expected**

- Invalid Fact diagnostic.
- Omission is the generic UNKNOWN representation; null is not accepted.

### `passport.invalid.enum_member`

**Facts**

```text
service_level = super_fast
```

**Expected**

- Invalid enum diagnostic rather than UNKNOWN or fuzzy matching.

### `passport.invalid.numeric_age_instead_of_birth_date`

If the final fixture exposes only `birth_date` as the source Fact, direct user submission of a derived `age` value is invalid/unsupported. The evaluator must derive age rather than trusting a user-provided administrative conclusion.

## Reproducibility scenario

### `passport.reproducible.adult_expired_standard`

Run `passport.positive.adult_expired_standard` repeatedly with identical:

- evidence-pack/Procedure Version;
- Facts;
- Goal = `get_egyptian_passport`;
- locale;
- evaluation date;
- rules-contract version.

**Expected**

- structurally identical planning result every run;
- identical Goal and selected Procedure identities;
- identical claim IDs and ordering;
- identical selected Service Point identities for the same fixture data;
- identical evidence-link IDs internally;
- no persisted Anonymous Case required;
- no raw Fact logging required.

## Bilingual parity scenario

### `passport.locale.ar_en_same_decision`

Evaluate the same complete known case once with `locale = ar` and once with `locale = en`.

**Expected**

- same Goal identity;
- same Procedure identity;
- same rule results;
- same claim IDs;
- same Fee values/states;
- same Service Point matches;
- only user-facing wording changes.

## Scenario coverage finding

This fixture materially requires scenario coverage for:

- a stable organizational Goal containing multiple related Procedures;
- Procedure boundary and adjacent Procedures;
- calendar-date age derivation;
- a changed temporal threshold (15 vs stale 16);
- conditional checklist claims;
- a sex/age-conditioned authority-document requirement;
- optional service-level fees/timing;
- Procedure-specific territorial vs non-territorial Service Point routing;
- stale/foreign-jurisdiction/low-context evidence exclusion;
- granular internal provenance with independently designed public evidence presentation;
- internal-only discrepancy handling;
- locally inconclusive claims without global failure;
- invalid typed Facts;
- deterministic bilingual output and reproducibility.
