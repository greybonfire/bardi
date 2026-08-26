# National ID renewal named scenarios

These scenarios define evidence-pack expectations for later prototype tickets. They are not executable tests yet. Unless stated otherwise, evaluation date is `2026-08-26` and Goal is `get_egyptian_national_id`.

## Goal and Procedure selection

### `nid.goal.stable_across_related_transactions`

Evaluate the same Goal while varying the card circumstance:

```text
Goal = get_egyptian_national_id
national_id_possession_state = none | held | lost | damaged
national_id_data_change_kind = none | residence | profession | marital_status
```

**Expected**

- Goal remains `get_egyptian_national_id`.
- The applicable Procedure can change.
- Lost/damaged cases do not become expiry-renewal branches.
- Data-change cases do not become ordinary renewal branches.
- Unresearched adjacent Procedures are named as unsupported rather than approximated.

### `nid.positive.expired_held_no_changes`

**Facts**

```text
application_location = inside_egypt
national_id_possession_state = held
national_id_data_change_kind = none
national_id_expiry_date = 2026-05-01
residence_governorate = giza
residence_district = dokki
```

**Expected**

- Procedure resolves to `ordinary_domestic_national_id_renewal`.
- Renewal deadline derives to `2026-08-01`.
- Deadline is passed on the evaluation date, but the planner still provides the supported renewal route rather than inventing a new Procedure.
- Current ordinary fee stays unknown.
- Current domestic previous-card checklist claim does not render because it is not adequately verified.
- Routing may remain locally inconclusive if no current office association for Dokki is encoded.

### `nid.negative.first_issuance`

```text
application_location = inside_egypt
national_id_possession_state = none
```

**Expected**

- Ordinary renewal evaluates FALSE.
- First issuance is a related Procedure under the same Goal.
- Renewal requirements are not reused.

### `nid.negative.lost_card`

```text
application_location = inside_egypt
national_id_possession_state = lost
```

**Expected**

- Ordinary renewal evaluates FALSE.
- Lost/damaged replacement is identified as a distinct related Procedure.
- Article 54 / the current service-directory replacement boundary may be cited, but the unresearched replacement checklist is not synthesized.

### `nid.negative.damaged_card`

```text
application_location = inside_egypt
national_id_possession_state = damaged
```

**Expected**

- Same as lost-card behavior: distinct replacement Procedure, no ordinary-renewal fallback.

### `nid.negative.residence_change`

```text
application_location = inside_egypt
national_id_possession_state = held
national_id_data_change_kind = residence
national_id_expiry_date = 2026-01-01
```

**Expected**

- Ordinary no-data-change renewal evaluates FALSE.
- A residence-data update Procedure is the related route when researched.
- The plan may state the current legal update deadline rule, but must not invent the update Procedure's documentary checklist.

### `nid.negative.profession_change`

```text
national_id_possession_state = held
national_id_data_change_kind = profession
```

**Expected**

- Ordinary renewal does not absorb the profession-change service.

### `nid.negative.marital_status_change`

```text
national_id_possession_state = held
national_id_data_change_kind = marital_status
```

**Expected**

- Ordinary renewal does not absorb the marital-status-change service.

### `nid.negative.consular`

```text
application_location = outside_egypt
national_id_possession_state = held
national_id_data_change_kind = none
national_id_expiry_date = 2025-12-01
```

**Expected**

- Domestic renewal evaluates FALSE.
- The current overseas guide remains jurisdiction-specific rather than becoming a universal Procedure.

## UNKNOWN and question selection

### `nid.unknown.possession_state`

```text
application_location = inside_egypt
```

**Expected**

- Procedure selection is UNKNOWN.
- `q.nid.possession_state` is the next relevant Question once location is known.

### `nid.unknown.data_change`

```text
application_location = inside_egypt
national_id_possession_state = held
```

**Expected**

- Ordinary renewal vs a data-update Procedure is consequentially UNKNOWN.
- `q.nid.data_change_kind` is askable before expiry details because it can redirect the transaction family.

### `nid.unknown.expiry_date`

```text
application_location = inside_egypt
national_id_possession_state = held
national_id_data_change_kind = none
```

**Expected**

- Applicability of the expired-card Procedure remains UNKNOWN.
- `q.nid.expiry_date` resolves the branch.

### `nid.unknown.routing_district`

```text
application_location = inside_egypt
national_id_possession_state = held
national_id_data_change_kind = none
national_id_expiry_date = 2026-01-01
residence_governorate = giza
# residence_district omitted
```

**Expected**

- Core renewal route can be supported.
- Service Point routing remains locally UNKNOWN.
- Reliable deadline guidance remains available.

## Date and temporal edge cases

### `nid.edge.calendar_month_deadline_january_31`

**Facts**

```text
national_id_expiry_date = 2026-01-31
evaluation_date = 2026-04-30
```

**Expected**

- `renewal_deadline_date = 2026-04-30` using three calendar months with month-end clamping.
- The implementation must not substitute 90-day arithmetic.

### `nid.edge.calendar_month_deadline_leap_safe`

**Facts**

```text
national_id_expiry_date = 2024-11-30
evaluation_date = 2025-02-28
```

**Expected**

- Three-calendar-month derivation produces `2025-02-28`.
- No timezone conversion participates.

### `nid.edge.expiry_date_equals_evaluation_date`

```text
national_id_expiry_date = 2026-08-26
evaluation_date = 2026-08-26
```

**Expected**

- This fixture does not assert same-day expiry semantics that were not established by the recovered sources.
- Result is treated as an unsupported boundary/policy gap rather than silently choosing expired or unexpired.

### `nid.edge.not_yet_expired`

```text
national_id_expiry_date = 2026-09-10
evaluation_date = 2026-08-26
national_id_data_change_kind = none
national_id_possession_state = held
```

**Expected**

- This expired-card Procedure does not apply.
- The result does not claim that early renewal is forbidden; early-renewal availability is simply unverified.

## Evidence and trust behavior

### `nid.evidence.previous_card_not_publishable_domestically`

**Expected**

- Current consular material can remain a research lead for presenting the old card.
- It cannot make `nid.requirement.previous_card` a current domestic Official Requirement.
- Editor-facing state is `needs-reverification`; public checklist omits the claim.

### `nid.evidence.current_fee_unknown`

**Expected**

- No current fee amount is rendered.
- Historical statutory caps, secondary articles, or commercial fee tables are not converted into a current government fee.
- A later verified fee can be added without changing the Procedure identity.

### `nid.evidence.online_domestic_unresolved`

**Expected**

- The overseas government's online-renewal instructions remain available to researchers.
- Domestic plan output does not promise an online route.
- Internal discrepancy `DISC-NID-ONLINE-DOMESTIC-APPLICABILITY` is not rendered verbatim.

### `nid.evidence.mobile_channel_requires_freshness`

**Expected**

- The 2026 caravan/humanitarian announcement can establish that those channel types exist.
- A plan generated later must not assume the January 2026 caravan schedule is still active without re-verification.
- Failure to resolve a current mobile channel does not invalidate the statutory renewal deadline.

### `nid.evidence.storage_display_separation`

**Expected**

- Evidence-bearing claims retain Source/Evidence Link identities internally.
- UI is free to group sources or expose them on demand.
- Goal labels, Questions, Derived Fact explanations, and product re-check warnings require no standalone government Evidence Link.
- Internal discrepancy rationale never appears as user-facing copy.

## Routing scenarios

### `nid.routing.psm_requires_location_context`

**Expected**

- The service-directory behavior establishes that governorate/area can be required for service discovery.
- Absence of a verified office mapping does not trigger a nearest-office guess.

### `nid.routing.civil_status_hq_not_universal_office`

**Expected**

- `sp.civil_status_sector_abbassia` may identify the Authority/sector location.
- It is not automatically returned as the user's ordinary renewal submission point merely because it is the Sector headquarters.

## Invalid and contradictory input

### `nid.invalid.null_expiry`

```text
national_id_expiry_date = null
```

**Expected**

- Invalid Fact diagnostic; omission is UNKNOWN.

### `nid.invalid.date_shape`

```text
national_id_expiry_date = "31/01/2026"
```

**Expected**

- Invalid calendar-date diagnostic; no locale coercion.

### `nid.invalid.possession_enum`

```text
national_id_possession_state = stolen_but_still_valid
```

**Expected**

- Invalid enum diagnostic rather than fuzzy classification.

### `nid.contradictory.held_and_lost_if_schema_is_split`

The preferred enum prevents `held` and `lost` from coexisting. If a future schema replaces the enum with independent booleans, a case asserting both must be diagnosed as contradictory rather than choosing a Procedure.

## Bilingual and reproducibility

### `nid.locale.ar_en_same_decision`

Evaluate a complete positive case in Arabic and English.

**Expected**

- same Goal, Procedure, rule results, claim IDs, fee state, deadline date, and routing state;
- only presentation text changes.

### `nid.reproducible.expired_held_no_changes`

Repeat the positive case with identical knowledge bundle, Goal, Facts, locale, evaluation date and rules-contract version.

**Expected**

- structurally identical result and editor trace;
- identical claim/Evidence Link identities internally;
- no saved Anonymous Case and no raw Fact logging.

## Scenario coverage finding

This fixture proves scenario needs for:

- stable Goal identity across renewal/replacement/update Procedures;
- exact typed Procedure selection;
- calendar-month deadline derivation and month-end clamping;
- unsupported same-day and early-renewal boundaries;
- current fee/document gaps without fabricated defaults;
- jurisdiction-specific evidence exclusion;
- local routing inconclusiveness;
- freshness of transient Service Point channels;
- storage/display separation;
- invalid and contradictory Facts;
- bilingual deterministic output.
