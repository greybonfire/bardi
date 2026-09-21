# National ID renewal: Task 3 readiness handoff

## Scope and observed baseline

Approved scope is **sandbox + files**: reviewed synthetic Scenario additions to the existing
sandbox draft, with durable definitions/tests. The authoring database remains untouched.
No publication, withdrawal, activation, evidence-date advancement, new Procedure, importer,
engine change or browser journey is authorized here. Task 4 is the separate real-API bilingual
journey; stored-scenario previews are not that journey.

Read-only private authoring and sandbox inventories agree on:

- Active Service `get_egyptian_national_id` and one draft
  `ordinary_domestic_national_id_renewal.research-2026-08-26`.
- Four selection Questions plus two residence/routing Questions, one renewal candidate and
  one no-card/expiry contradiction. No actual Question, candidate or configuration defect
  has been established; no Service setup change is planned.
- Fourteen baseline stored scenarios, none stale, and no publication/withdrawal audit events.
  They are preserved unchanged alongside the additions below.

The selector tests location, possession, data-change kind and expiry, not citizenship,
contested identity or guardianship. This audit does not certify those cases or the wider
National ID Service. Private inventories are not import files; never commit raw exports,
users, credentials or real case data. Use only synthetic Facts.

## Evidence limits remain unchanged

The source/retrieval baseline is **2026-08-26**; recorded re-verification boundaries are
**2026-09-25 inclusive**. Where otherwise current, evidence is not overdue on September 25;
it is overdue on September 26. No new evidence has been verified and no dates may be advanced
merely to make previews pass. Follow the [rules contract](../architecture/rules-contract.md)
and [publication freshness contract](../architecture/knowledge-publication.md).

Current fees remain unknown; domestic documentary evidence is incomplete. The previous-card
item remains a candidate based on consular context, not an allowed domestic requirement.
Exact routing remains unresolved, with no routing associations. Residence answers cannot
supply missing jurisdiction evidence. Successful planning must retain these uncertainties,
not manufacture fees, documentary requirements, penalties or an office destination.

### Optional research, not runtime authority

At handoff, [PR 147](https://github.com/greybonfire/bardi/pull/147) is OPEN and unmerged.
Research links are pinned to its docs head `dd0d8cda84a7bda55871836e477341594755f300`:

- [Claims and gaps](https://github.com/greybonfire/bardi/blob/dd0d8cda84a7bda55871836e477341594755f300/docs/evidence-packs/national-id-suite/claims.md)
- [Scenarios](https://github.com/greybonfire/bardi/blob/dd0d8cda84a7bda55871836e477341594755f300/docs/evidence-packs/national-id-suite/scenarios.md)
- [Sources](https://github.com/greybonfire/bardi/blob/dd0d8cda84a7bda55871836e477341594755f300/docs/evidence-packs/national-id-suite/sources.md)

C-N-07 is a newer channel-specific old-card lead, not permission to promote the existing
candidate: D03 marriage applicability, G02 completeness and D09 current-law review remain
unresolved. SC31–44, SC61–63 and SC68 are relevant research prompts, not imported runtime rows.
Older PR instructions requiring ordinary independent review or new per-Procedure importers
are superseded by [ADR 0019](../adr/0019-use-explicit-solo-and-independent-publication-review-modes.md)
and [ADR 0020](../adr/0020-use-versioned-draft-pack-authoring-contract.md). Solo still preserves
all evidence/domain gates and genuinely independent specialists for truthful high-risk flags.

## Durable coverage

The 21 additions-only native Scenario rows are in
[`national-id-renewal-readiness.json`](../draft-packs/scenarios/national-id-renewal-readiness.json).
This array is **not an importable draft pack** or a new transport format. Coverage includes:

- Empty Facts select the first Question; additional unsupported changes/combinations stay
  outside the researched renewal route.
- Same-day expiry is not expired; deadline passage is strictly after three calendar months.
  Exercise genuine destination-month clamping, not May 31 → August 31 (no clamp).
- Omitted routing Facts do not force irrelevant residence Questions without associations.
- Invalid typed inputs stay invalid; corrected synthetic inputs recover normally.
- September 25/26 distinguish inclusive freshness from overdue evidence without changing dates.

[`knowledge.tests.test_national_id_renewal_readiness`](../../backend/knowledge/tests/test_national_id_renewal_readiness.py)
checks generic-pack import/retry, unchanged baseline rows and seals, previews, production
readiness gates, stateless corrections and Arabic/English projections.
[`api.tests.test_national_id_renewal`](../../backend/api/tests/test_national_id_renewal.py)
asserts the exact derived date values separately from trust-sensitive plan expectations.

## Reproduce the sandbox-only additions

Use the existing [sandbox](questionnaire-sandbox.md), verify its identity and explicit target,
and use an existing permitted staff actor. For the default sandbox, use
**http://127.0.0.1:18000/admin/**, headed **LOCAL QUESTIONNAIRE SANDBOX**, not authoring Admin.
Keep exports and composed packs outside Git in a private `0700` directory;
set `umask 077` before creating files.

1. Obtain a **fresh revision-bearing full authoring pack** from the selected sandbox draft's
   [Admin export tool](../draft-packs/README.md#admin-upload-inspect-then-confirm).
   Do not reuse an old inventory's embedded pack or a read-only vocabulary context.
2. Retain every root field, `base_revision`, version/Procedure identity, catalog, Service setup,
   owned row and existing scenario. Append only absent names from the reviewed native array.
   An exactly equal existing row is acceptable; a conflicting same name means **stop**.
3. On that same draft's page, choose **Inspect import into [semantic ID]**, then inspect the
   composed pack. Only new Scenario additions are expected (or no changes on repeat application):
   no deletions, replacements, trust/date resets, catalog or setup changes. Existing Service
   setup is compare-only. Stop on any other diff; never use the new-draft import route.
4. Confirm that same reviewed pack into that same sandbox draft without deletion consent.
   Inspection rolls back but can advance sequences; it is not a strictly read-only inventory
   or evidence verification. Host CLI commands using the ordinary authoring `.env` target the
   wrong database for this task; the file-only fragment below needs no database environment.

Optional local composition fragment, run from `backend` with `uv run python`, uses only files
and the existing parser (no database). Substitute private paths; inputs must be trusted native
export/additions JSON. The final full-pack parse validates row shape; this is not an ingestion
helper for arbitrary external JSON:

```python
import json
from pathlib import Path
from knowledge.draft_packs.schema import parse_draft_pack

pack = json.loads(Path("/private/draft-before.json").read_text())
parse_draft_pack(pack)
rows = json.loads(Path("../docs/draft-packs/scenarios/national-id-renewal-readiness.json").read_text())
if not isinstance(rows, list):
    raise ValueError("Expected native Scenario row array")
by_name = {row["name"]: row for row in pack["scenarios"]}
for row in rows:
    name = row["name"]
    if name in by_name:
        if row != by_name[name]:
            raise ValueError(f"Conflicting Scenario: {name}")
    else:
        pack["scenarios"].append(row)
        by_name[name] = row
payload = json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False)
parse_draft_pack(payload)
with Path("/private/draft-additions.json").open("x") as output:
    output.write(payload + "\n")
```

New scenarios receive normal model-generated seals through the importer only. Unchanged
scenarios keep their existing seals. If any old scenario is genuinely stale, **stop for explicit
manual review** in Planning Scenario Admin; do not reseal mechanically or rewrite expectations
to conceal a mismatch. A stale revision requires a fresh export and reconciliation.

After authored additions, the deterministic research importer intentionally rejects Scenario
drift from its original baseline. Do not reset the draft, delete additions or update its digest
to restore bootstrap idempotency. Use the supported draft-pack workflow for subsequent edits.

## Measured local outcome

The guarded sandbox application added **21 scenarios**, bringing the draft to **35**:

- All fourteen baseline rows/seals were unchanged. All 35 previews matched expectations and
  were non-stale; Arabic/English plan projections preserved the same Procedure Version.
- Only the new Scenario rows, the target's draft-pack receipt and their sequences changed.
  All other public-table rows, constraints and triggers were unchanged. Preview/readiness
  checks and an exact retry persisted no further changes.
- The authoring recovery fingerprint (public rows, sequence positions, stable constraint
  metadata and trigger definitions), authoring `.env` and sandbox manifest were unchanged.
  No accounts, approvals or publication audits were added.
- The Service remains active and the Procedure Version remains **draft**. Readiness for the
  existing permitted operator reported `solo` and **zero blockers**, not approval or evidence
  verification. Unknown fees, blocked previous-card material and unresolved routing remain.
- The 12 focused regressions passed, followed by the full fresh-PostgreSQL backend suite:
  **676 tests, one skip, no failures**. Lint, formatting, types, schema/API artifact checks,
  read-only Django/migration checks and nine Admin JavaScript regressions passed.

The normal Next.js/API path still excludes this draft. Task 4's real-API Arabic/English journey
is a separate followup, requiring explicit sandbox-only publication under the normal gates.
A future sandbox refresh replaces these local additions; use the native rows and a fresh export
to reapply them. The authoring draft still has its original fourteen scenarios.
