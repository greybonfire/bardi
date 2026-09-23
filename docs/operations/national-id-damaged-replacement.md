# Damaged National ID replacement: Task 5 handoff

## Scope and files

**Partially researched, unpublished; sandbox + reusable files only.** Authoring must remain
unchanged. Persistent additions, including the new Fact definition and Procedure Version,
stay unpublished; no approvals, verification-date advancement or promotion back to authoring.
The guarded local application is complete. The sandbox was resumed/rebuilt without a refresh;
its active database was retained. The measured outcome is recorded below.

- [Full draft pack](../draft-packs/examples/national-id-damaged-replacement.json) owns
  `ordinary_domestic_national_id_damaged_replacement.research-2026-09-22`, two Warnings,
  one Evidence Link and twelve scenarios. `service_setup` is `null`.
- [Native setup specification](../evidence-packs/national-id-damaged-replacement/setup.json)
  is **NOT IMPORTABLE**: it describes ordinary Admin/model operations on the existing
  `get_egyptian_national_id` Service. Generic packs cannot add Questions/candidates to an
  existing Service or define a new derived Fact.
- [Source assessment](../evidence-packs/national-id-damaged-replacement/sources.md) retains
  PR147 S10/C-N-08 provenance and attributed retrieval **2026-09-12**, not fresh verification.

Stable selection is domestic application + damaged possession + no requested data changes.
Version applicability adds Egyptian citizenship and `card_expires_after_evaluation_date`:
expiry strictly after evaluation date, equality false, omission UNKNOWN. This additive pinned
native definition does not reinterpret existing keys or require migration, schema/API/UI changes.
September 22 is authored coverage, not a government effective date. These are product research
boundaries, not legal ineligibility or exact jurisdiction claims; expired-and-damaged selection
remains unresolved.

The supported damaged-card passage is an evidence-bearing administrative Warning, not a
checklist with invented quantities. An **unconditional important product Warning** preserves
incompleteness: empty checklist does not mean no requirements; marriage-document applicability,
channel entitlement, fees, steps, office and turnaround remain unknown. No checklist items,
Steps, Fees, Bases, dependencies, routing associations or fifteen-day legal rule are supplied.

## Guarded native setup, then generic import

Use the [sandbox lifecycle guide](questionnaire-sandbox.md), not ordinary authoring Compose or
host commands loading authoring `.env`. The parent may resume/rebuild current code with
`uv run python tools/local_sandbox.py start` after checking `status`; **no `refresh`, archive
replacement or migration**. This preserves Task 3 additions. Default Admin is
**http://127.0.0.1:18000/admin/**, headed **LOCAL QUESTIONNAIRE SANDBOX**, not authoring Admin.
Use an existing permitted staff actor; create no accounts. Keep private inventories outside
Git in a `0700` directory with `umask 077` (`0600` files); use only synthetic case Facts.

Before writes, verify sandbox identity/active generation and retain private before-state
inventories/fingerprints of both environments, authoring `.env` and sandbox manifest. Confirm
renewal's fourteen baseline + twenty-one Task 3 scenarios are present. Preserve every existing
Question, candidate, contradiction, source Fact, claim and evidence date. Unexpected drift means
**stop**, not reset/reimport. Parent's guarded model application should be atomic; Admin edits
are separate saves, not a multi-page transaction.

Apply exact values from `setup.json` in this order. For every semantic identity, **create if
absent, otherwise compare all specified fields and relations exactly; stop on conflict**.
Never overwrite a shared definition merely to match the file.

1. Register `card_expires_after_evaluation_date` as a boolean derived `FactDefinition`,
   unpublished, only after the rebuilt code supports it. Use native `full_clean()` then
   `save()` (or ordinary Fact Admin creation). Admin's `is_published` is read-only;
   there is no Fact publication action to invoke here.
2. Create/compare the Procedure with the existing Service and exact bilingual text;
   native model path is `Procedure.full_clean()` then `save()`.
3. Create/compare `q.nid.citizenship` on that Service, priority 70, using the existing
   published `citizenship` Fact and exact bilingual text. Native path: `ServiceQuestion`
   `full_clean()`/`save()`, then `set_question_resolved_facts` for citizenship only.
   Do this **before pack import**. Do not change the expiry Question: derivation maps
   its existing source dependency.
4. Create/compare the new Service candidate, using the exact ordered predicate from the
   specification and native `save_candidate`. Retain the renewal candidate unchanged.
5. Use **Import research draft** in Procedure versions with the JSON pack, following
   [inspect then confirm](../draft-packs/README.md#admin-upload-inspect-then-confirm).
   The precreated Procedure must exactly compare with its catalog entry. Expect only
   this draft's owned content and absent declared shared source/authority identities;
   no Service setup replacement, deletions or unrelated writes. Readiness blockers do
   not prevent a structurally valid incomplete import. Confirm only the reviewed diff.
   Inspection rolls back rows but may advance sequences; it is not a read-only audit.

Exact retry can be a no-op only under the generic receipt/live-state rules. After subsequent
native reviews or other state changes, do not force the original new-import receipt: export
fresh and reconcile via an explicitly targeted draft update. No new importer/helper CLI is
needed; the [draft-pack guide](../draft-packs/README.md) owns conflict/revision recovery.

## Review seals without hiding blockers

Adding the citizenship Question makes **all 35 renewal scenario signatures stale**. Individually
inspect each stored result and expectation, then use normal Planning Scenario Admin/model save
to record that review. Preserve names, source Facts, dates and all other expectations. Only
`nid.negative.damaged_card` needs an expected-reason change to `no_published_version` while
the damaged version is draft. Record actual review results; never write signatures directly,
rerun the deterministic importer to bypass its seal, or resave an inconvenient failure into a
false green result. Stop and report any other mismatch.

For the new draft, the unpublished derived Fact is an intentional readiness limitation:
`unsupported_rule_fact:card_expires_after_evaluation_date`; scenario execution also reports
`scenario_execution_failed`. The positive stored preview has **no result** and diagnostic
`scenario_execution_failed`, not a successful incomplete plan. Preserve these findings and
any other actual blockers. Readiness/previews must not persist changes. The new Warning and
Evidence Link remain unknown/unverified with no verification dates; no blanket trust promotion.
Normal public planning excludes the persistent draft.

## Disposable tests and browser smoke

[`test_national_id_damaged_replacement.py`](../../backend/knowledge/tests/test_national_id_damaged_replacement.py)
contains five broad Django `TestCase` tests: import/retry/conflict and preservation; atomic
failure; read-only raw readiness/preview and renewal review; canonical publication with bilingual
partial guidance; and corrections, invalid/derived input, missing Questions and trust fallback.
Stored cases cover equal/expired dates, noncitizen, lost, changed-data and overseas exclusions.
API projections use the real `execute_planning` application with an injected snapshot loader
inside `TestCase`; this is **not HTTP or browser proof**.

Only disposable fixtures publish the compatible Fact and simulate current trust for
`nid.damaged.warning.card` and `EL-NID-DAMAGED-S10` with explicit test dates. They review the
changed warning expectations, publish damaged first under normal gates, then review all renewal
cases and publish renewal. In that final catalog the baseline damaged case expects
`not_yet_effective`: its unchanged **2026-08-26** evaluation precedes September 22. Simulation
is not human review or new source verification. Trust fallback removes administrative text
while retaining the unconditional incomplete-guidance warning. Solo mode does not waive base
publication gates or truthful specialist requirements.

## Measured local outcome

The guarded application added one draft with **12 scenarios**, one unpublished derived Fact,
one citizenship Question and one candidate, plus the declared source/authority/evidence records.
A rollback-only rehearsal preserved all rows; the confirmed atomic operation matched its allowed
changes and an exact pack retry was a no-op.

- All **35 renewal cases** were checked individually before normal saves. Their signatures were
  refreshed for the added Question; only the damaged-card case's expected reason changed.
  All 35 stored previews then matched, were non-stale, and renewal readiness had zero blockers.
  This was agent-assisted scenario checking, not human evidence or publication approval.
- Damaged readiness retained exactly the two expected diagnostics above; its positive preview
  remained unavailable. The new Fact and both versions remain **unpublished**, and new evidence
  and Warning trust remain unknown with no verification dates. No approval/audit events were added.
- Existing sandbox rows were unchanged except those 35 scenario signatures and one expectation.
  Only the declared new records and associated sequences were added/advanced; other public rows,
  constraints and triggers were preserved. Authoring's public rows, sequence positions, stable
  constraint/trigger fingerprints, `.env`, container configuration and sandbox manifest were unchanged.
- Independent review and the fresh-PostgreSQL backend suite passed: **685 tests, one skip**,
  plus lint, formatting, types, artifact/system/migration checks and nine Admin JavaScript tests.
  The existing plan-view component suite passed **70 tests**.
- A separate disposable Next → Django → PostgreSQL browser smoke passed Arabic and English
  damaged guidance and damaged → renewal → damaged corrections: **30 planning exchanges**.
  It used full publication gates, a pinned September 22 date, and explicitly simulated verification;
  it did not verify source truth or publish persistent content. Browser requests changed no database
  rows/state fingerprint. Its database, processes and temporary frontend were removed.

A sandbox refresh would discard these local changes; the artifacts and recipe are the recovery
path, not a database copy back to authoring. Do not promote disposable publication/trust changes
into either persistent database.
