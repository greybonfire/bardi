# Draft packs v1

A draft pack is a versioned **staff authoring transport**, not publication, verification, backup,
a public API response or a saved Anonymous Case. Import/export through CLI or Django Admin;
Admin also offers advisory readiness and stored-scenario previews, not a free-form simulator.
Manual editing and deterministic research importers remain supported.

**One pack imports one draft Procedure Version, not a whole Service.** Other procedures in that
Service are untouched. Use this guide for pack preparation, inspection, confirmation and recovery;
use the [editorial workflow](../editorial-process.md) for field meaning and human completion.

## Contract and supported inputs

- [JSON Schema: `draft-pack-v1.schema.json`](draft-pack-v1.schema.json) is generated from
  `backend/knowledge/draft_packs/schema.py`; do not hand-edit it.
- [Minimal synthetic research example](examples/minimal-research.json) is a supported incomplete
  draft: a new inactive Service, Procedure, unpublished source Fact, initial Question and candidate.
  It contains no fabricated government claims or evidence and is not publication-ready.
- [External-LLM prompt](llm-prompt.md) supports researcher-assisted JSON preparation, not automatic
  ingestion or trusted AI decisions. Review all generated material before importing.
- [ADR 0020](../adr/0020-use-versioned-draft-pack-authoring-contract.md) records the safety and
  concurrency tradeoffs. The [domain vocabulary](../../CONTEXT.md) and
  [rules contract](../architecture/rules-contract.md) retain their meaning.

Every root field is required; unknown fields are rejected at typed boundaries:

```text
format: "bardi.draft-pack"
format_version: 1
base_revision: null | 64-character lowercase SHA-256 fingerprint
catalog: {services: [], procedures: [], facts: [], authorities: [], sources: [], document_types: []}
version: {semantic_id, procedure, rules_contract_version, text_ar, text_en,
          effective_from, effective_to, applicability}
risks: {legal: boolean, military: boolean, custody_guardianship: boolean, contested_identity: boolean}
service_setup: null | {service, questions: [], candidates: [], contradictions: []}
bases: []
checklist_items: []
steps: []
warnings: []
fees: []
dependencies: []
routing_associations: []
evidence_links: []
scenarios: []
```

This is a shape guide, not JSON to paste. Use the complete example or an export. Some row fields
have defaults; canonical exports include all authored fields, nulls, and collections. Version
text can remain blank in an incomplete draft; authored claims still require meaningful bilingual
text and production model validation. Omit unsupported claims rather than inventing evidence.

The owned arrays are the **full desired snapshot**, not patches. Removing a row means deletion;
omitting a root collection is invalid. Shared catalog arrays are create-or-exact-compare, not
replacement lists: existing definitions are never overwritten, even unpublished ones. References
may resolve existing identities without repeating their definitions. Existing Derived Facts can
be referenced, but never defined or assigned formulas in a pack. New Fact definitions are source
Facts and remain unpublished. The current pack exporter includes the full non-derived Fact
registry, not just directly referenced keys.

Initial `service_setup` is permitted only for a Service created by **this import transaction**.
It cannot add, edit, or delete Questions, candidates, or contradictions on any preexisting Service,
even an inactive one. An exact exported setup may be compared/reused unchanged. `null` never
removes setup. Additional configuration for existing Services is a separate manual operation.

Identifiers are stable semantic IDs, not database primary keys. Owned claim IDs are version-scoped;
Evidence Link IDs are scoped by owner kind and owner semantic ID. Scenario identity is `name`.
Preserve source-list and rule-child order. Checklist Basis scope uses `scope_reference` (empty
string for procedure scope); Steps and Fees use nullable `eligibility_basis`. Routing associations
reference existing shared Service Point Versions; v1 cannot create/edit Service Point material or
its Evidence Links.

Dates are canonical `YYYY-MM-DD` strings or allowed nulls; rule date literals use
`{"$date":"YYYY-MM-DD"}`. Rules use the exact `v1` AST, with `{}` only in optional rule positions,
never executable formulas. Scenarios use synthetic source Facts only; deliberate invalid-value
test cases are allowed, but undefined or derived input keys are not. Their expected result shape
also undergoes production model validation.

Input is bounded to 8 MiB, 512 nesting levels and 10,000 records; rules retain the 128-node and
128-operand limits. Malformed UTF-8/JSON, duplicate JSON keys, duplicate scoped identities,
nonfinite numbers, wrong scalar types (including boolean/integer coercion), invalid dates and
unknown typed fields fail closed. JSON Schema is an authoring aid, not a substitute for the
parser, database-backed rule/reference checks, and production structural validation.

## Staff permissions and accountability

Use your own existing, persisted, currently active staff account. The service reloads permissions
from the database, including on confirmation. Ask an operator for version add/change access for a
new draft, change access for an update, view access for exports, and add access for any new shared
catalog/setup types. The exact permission names and aggregate-versus-child authorization boundary
are defined in the [Admin capability contract](../architecture/django-admin-lifecycle.md#generic-draft-pack-service-permissions).
Import access does not grant publication, review, verification or ordinary child-model Admin access. `--actor` names the real operator; there is no second
`--author` impersonation flag. The actor becomes accountable author for a new Review Policy;
an existing author is retained. No users, approvals, publication actors/dates, trust metadata,
scenario seals, or lifecycle state may be supplied in JSON.

## Admin: upload, inspect, then confirm

Open **Procedure versions** at `/admin/knowledge/procedureversion/`:

- **Download incomplete research template** downloads the supported synthetic example, not
  publication-ready guidance (`draft-pack/template/`).
- **Download global vocabulary context** downloads read-only context before any version exists
  (`draft-pack/context/`), for external-LLM drafting alongside the template.
- **Import research draft** selects a new draft, never an existing target implicitly
  (`draft-pack/import/`).

An existing version's change page has **Draft-pack tools**. Routes below are relative to
`/admin/knowledge/procedureversion/<object_id>/`, where `object_id` is the Admin database ID:

| Tool label | Route |
| --- | --- |
| Export authoring pack with revision | `draft-pack/export/` |
| Download read-only vocabulary context | `draft-pack/context/` |
| Inspect import into [semantic ID] | `draft-pack/import/` |
| Check publication readiness as current editor | `draft-pack/readiness/` |
| Preview stored scenarios | `draft-pack/scenarios/` |

Exports are JSON attachments with `Cache-Control: no-store`. The version-specific context selects this version's
Service setup but retains global shared vocabulary; it is not importable. Finalized versions can
be exported, not updated or previewed as drafts. Clone a successor through the existing action.
Downloads and standalone checks require version view permission; imports retain the aggregate
permissions above, freshly checked again on confirmation.

Choose one JSON file (at most 8 MiB), then **Inspect proposed changes**. Inspection runs the import path and publication gates, then rolls back; sequences may advance.
Review before/after values, deletions, shared/setup creations, trust/date resets, risk increases
and stale scenarios. Publication blockers allow structurally valid incomplete research;
structural, authorization, history, identity and revision errors prevent import. Consent explicitly to any displayed deletions,
then use **Confirm draft import**. Success redirects to the draft; it never publishes or approves.

With JavaScript, inspection retains the original File input and replaces only the rendered result;
changing files clears the old inspection and discards obsolete responses. Without JavaScript,
reselect the **same file** after inspection before confirming. Confirmation resends the file with a
signed, 15-minute token bound to its exact bytes, current editor, route-selected target, deletion
requirement and inspected live-state precondition. Even whitespace changes invalidate inspection.
Tokens are stateless, **not one-use**; exact retries within expiry follow the receipt rules below.
Confirmation rechecks permissions, draft identity, exported revision and live state. Its global
precondition includes knowledge rows and readiness settings, so unrelated edits can cause
`stale_inspection`. See the [recovery table](#recovery-quick-reference) for next actions.

The upload handler is installed before multipart/CSRF parsing; during parsing it bounds actual
received file bytes and rejects extra files. Actual operations remain CSRF-protected. This is an application limit,
not a guarantee against earlier proxy/server buffering; configure upstream limits separately.
The bounded request-local buffer is not persistent staging. Raw packs are never retained in
sessions, cookies, browser storage or a server upload archive, nor embedded in confirmation fields.
Only the small signed token crosses requests alongside the explicitly resubmitted file.

### Advisory readiness and stored-scenario previews

Readiness checks the current editor as **prospective publisher** against all canonical gates,
including dates, evidence, scenarios and mode-required reviews/specialists. Missing publish
permission adds `missing_publish_permission` without suppressing other diagnostics. Readiness
is advisory, not approval; publication reruns all gates.

Readiness and scenario evaluation run only on explicit tool requests (and proposed-state readiness
on inspection), not ordinary draft page loads or saves. **Preview stored scenarios** lists existing
scenarios; **Preview [name]** runs the selected scenario via `?scenario=<scenario_id>`. There is no
free-form Fact entry. It uses the stored synthetic source Facts, date and authored locale with the
production date-aware loader and planner, then displays Arabic RTL and English LTR projections,
including returned guidance sections, uncertainty, sources and freshness.

Scenario seal staleness is independent of expectation matching: a stale valid scenario may run
and match, but still needs explicit human review/resave in Planning Scenario Admin. Invalid
scenarios, overlapping published versions or execution failures are unavailable, not successful
previews. An inactive Service stays inactive and produces honest inconclusive planning output;
preview never publishes Facts, activates Services, verifies evidence or refreshes seals. Temporary
lifecycle exposure is rolled back. Readiness also rolls back database gate effects and callbacks;
trusted custom gates must not perform irreversible external I/O, which database rollback cannot undo.

All [manual followups](#trust-history-and-manual-followups) still apply.

## CLI: research, dry-run, then write

Run from the repository root with the [development environment](../development.md#backend-setup-host-run-workflow)
configured, exported environment values, and PostgreSQL with the branch's migrations applied.
These commands do not migrate your database or modify `.env`. Replace `EDITOR`, `SERVICE_ID` and
`DRAFT_ID` with real identities; do not create fictional reviewer accounts.

First export vocabulary for your researcher or external LLM:

```bash
uv run python backend/manage.py export_draft_context --actor EDITOR \
  --service SERVICE_ID --output /tmp/bardi-context.json --settings=bardi.settings.development
```

Omit `--service` for all Service setups. The filter selects setup entries only: the shared catalog,
Fact registry and Service Point Version references are still global. Context has
`format: "bardi.draft-context"` and `status: "read_only"`; it is deliberately **not importable**.
Its Fact `derived`/`is_published` flags are information, not permitted draft-pack fields. Exports
are internal research material; inspect and minimize them before sharing externally.

Try the supported synthetic example on a disposable development database:

```bash
uv run python backend/manage.py import_draft_pack docs/draft-packs/examples/minimal-research.json \
  --new --actor EDITOR --dry-run --settings=bardi.settings.development
uv run python backend/manage.py import_draft_pack docs/draft-packs/examples/minimal-research.json \
  --new --actor EDITOR --settings=bardi.settings.development
```

Dry-run uses the real transactional application/validation path and rolls it back, including
shared rows and the internal receipt. Database sequences may advance. Inspect `changes` and
`manual_actions`; a dry-run revision describes the hypothetical result and is not an update token
for the unchanged database. Dry-run is not a publication preview and does not run publication gates.

### Update roundtrip and deletion consent

Export the selected draft before editing:

```bash
uv run python backend/manage.py export_draft_pack --version DRAFT_ID --actor EDITOR \
  --output /tmp/bardi-draft-before.json --settings=bardi.settings.development
cp /tmp/bardi-draft-before.json /tmp/bardi-draft-edit.json
# Edit the complete snapshot, retaining base_revision, version identity and Procedure identity.
uv run python backend/manage.py import_draft_pack /tmp/bardi-draft-edit.json \
  --target-version DRAFT_ID --actor EDITOR --dry-run --settings=bardi.settings.development
uv run python backend/manage.py import_draft_pack /tmp/bardi-draft-edit.json \
  --target-version DRAFT_ID --actor EDITOR --settings=bardi.settings.development
```

If the reviewed diff intentionally deletes owned rows, add `--allow-deletions` to the write command.
Dry-run reports deletions without that flag, but structural and history protections still apply.
No flag bypasses them. A matching uploaded ID alone never selects an existing draft for update:
`--new` and `--target-version` are mutually exclusive and one is required. No renaming,
reparenting, or published/withdrawn updates are permitted. Exports may inspect finalized versions,
but that does not make them editable; use Admin successor cloning, then export the successor.

`base_revision` is an opaque fingerprint of the complete relevant live state, not merely authored
text or the review signature. It includes trust, seals, policy, approvals, evidence workflow and
audit history, shared registries and dependency state. Conservative shared/global inputs mean an
apparently unrelated catalog change can cause `stale_revision`, even if your text already matches.

The sole stale/new-collision retry exception is the **exact normalized last successful request**,
including original revision and target, whose receipt's post-import revision still matches live
state. It may return `noop`; authorization and draft state are rechecked. Older requests or changed
content, targets or fingerprinted state do not qualify. The one-per-version receipt stores hashes,
not raw packs or replacement audit history; dry-run creates none. Re-export before a different update.

### Output and recovery

Import returns one JSON object on stdout with `status` (`dry_run`, `written`, or `noop`), `version`,
`revision`, `changes`, and `manual_actions`. Operational failures return `status: "error"` and
`diagnostics` entries with `code`, field `path` segments and `message`, plus a nonzero exit and a
short stderr error. Argument-parser usage failures use Django's normal CLI handling.

Exports without `--output` emit the pack/context directly. With `--output`, they atomically create
a new file and emit `{"status":"written","output":"..."}`; this means a file was written, not
knowledge was changed. Existing files and symlinks are refused, with **no overwrite flag**. In `export_draft_pack`, `--version ID` deliberately overrides Django's normally
reserved version-banner option and selects the knowledge version.

During import/export, ordinary reads continue but writers may wait. If calling these tools inside
an outer transaction, keep it short: locks persist until it ends. There is no total latency
guarantee. For lock and timeout implementation, see
[draft authoring transport](../architecture/production-backend.md#draft-authoring-transport);
for retryable `concurrent_edit` and other failures, use the table below.

### Recovery quick reference

| Situation | Safe next action |
| --- | --- |
| File changed, confirmation expired, or `stale_inspection` | Inspect the exact intended file again; recheck the new diff before confirming. Without JavaScript, reselect that same file. |
| `stale_revision` | Export to a new file and reconcile your edits against current state. Do not paste in a replacement hash blindly. |
| `concurrent_edit` | Let the competing transaction finish, then reload/re-export as needed and retry. |
| Write response lost | Retry only the exact last request; `noop` requires a matching receipt and unchanged live state. Otherwise inspect/export current state before deciding what remains to do. |
| `protected_history` | Use a successor or supported manual workflow; do not delete discrepancy/re-verification history. |
| `risk_reduction` | Restore true risk flags; do not remove a risk to avoid specialist review. |
| `legacy_evidence_identity` (blank Evidence Link ID) | Assign a stable owner-scoped ID in Admin where lifecycle guards permit; immutable material needs the supported successor/manual path. Export never repairs it silently. |
| Export destination exists | Choose a new output filename; files and symlinks are never overwritten. |
| Permission or structural diagnostic | Ask an operator for required access or correct the indicated field/reference. A new confirmation token cannot bypass validation. |

Keep your reviewed local baseline and edited file for reconciliation; the server does not archive
uploaded packs. Successful import still needs human completion below.

## Trust, history, and manual followups

Import never publishes, approves or verifies. New Services stay inactive and new source Facts stay
unpublished. Review evidence and bilingual meaning, complete consequential Question/candidate
coverage, publish appropriate Fact definitions, author/run scenarios, and explicitly activate the
Service only when ready for navigation. Finish mode-required reviews/specialists and canonical
Admin publication separately. `manual_actions` is guidance, not an exhaustive publication verdict.

Unchanged rows preserve primary keys, trust and approvals. Changed claims reset owner trust and
retained evidence trust; evidence additions/edits/deletions or reordered Sources reset the owner
and siblings. Basis changes also invalidate Basis-scoped claims; version semantic changes
conservatively reset the whole owned trust aggregate. Reset state is `unknown`, with null
`verified_on`/`reverify_on`; unverified Fees use `needs_reverification` to satisfy their model
contract. Shared Service Point material is never reset or rewritten.

Edits **and deletions** affecting owners with discrepancy or re-verification workflow history
are refused (`protected_history`). Historical overlays could otherwise apply old trust to changed
meaning; imports cannot safely rewrite those overlays. Follow the recovery table above.
Approval/audit rows remain immutable
history, not silently regenerated approval for the new content. Signature-changing edits make
prior approvals stale. Existing true risk flags cannot be cleared (`risk_reduction`).

Unchanged scenarios are not saved/resealed by import. Their old seals remain and can become stale
after semantic changes. Explicitly review their expectations and **resave through Planning Scenario
Admin** when stale; exporting and reimporting identical scenario JSON is not review. New or genuinely
changed scenarios receive normal model-generated seals, never seals asserted by an LLM.

See the [editorial process](../editorial-process.md) for the manual completion and publication path.
