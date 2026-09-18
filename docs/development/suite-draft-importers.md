# Separate passport and National ID research-draft imports

Implementation baseline: `6b6de168a5372b8b7105a983245f71723f0248c1` (PR #138 merged).
Administrative research date: **2026-09-12**. Patch preparation: **2026-09-15**.

**This is draft staging, not the completed full-suite planning implementation.**
The commands turn the separate research packs into editable, non-routable database drafts.
They do not close the shared catalog-compatibility design or any administrative evidence gate.
They have not been executed against a deployed database.

## Scope

| Independent command | Catalog rows reported | Draft versions | Named Procedure identities |
| --- | ---: | ---: | ---: |
| `import_passport_suite` | P01–P14: 14 | 12 | 12 |
| `import_national_id_suite` | N01–N15: 15 | 12 | 11 |

N12 has separate London and Dubai research drafts. P07, P12, N08, N09, N10 and N13 remain
report-only because their transaction identities are unresolved. No identity is invented for
these rows. Other proposed but blocked identities can have a research draft, not a live candidate.
P14 has an MFA-baseline draft, not an inferred worldwide mission. N14/N15 stage the statutory
framework only; they do not gain replacement checklists from renewal sources.

The manifests contain 35 passport claim records and 17 National ID claim records: 50 unique
research claim IDs across the two families. Shared discovery IDs have family-specific scope.
Each manifest has 13 Source aliases; the union is the original 25 aliases. S25 has a separate,
National-ID-scoped locator in the National ID manifest. Source rows use family/date namespaces,
so existing August Sources and immutable publication provenance are not rewritten.

Read the administrative research separately:
[passport](../evidence-packs/passport-suite/README.md) and
[National ID](../evidence-packs/national-id-suite/README.md).
The shared [I02 design prerequisite](../evidence-packs/catalog-compatibility.md) remains open.

## What is stored

Named family/scope pairs receive normal `ProcedureVersion` drafts with bilingual research
labels and an existing `ProcedureVersionReviewPolicy` naming the supplied staff author.
Simple document observations use candidate Checklist Items, simple actions use Steps, and
compound observations/discrepancies use administrative Warnings. No compound alternative is
expanded into a list of mandatory documents. Quantities and conditions remain in research text,
not reviewed executable rules or guaranteed original/copy quantities.

Four domestic passport fee components retain their researched numerical amounts as structured
**unverified** Fee values. Issuance and loss/damage replacement amounts are not added together.
Consular prices that share a compound claim remain research notes; a mixed-transaction quote
is not converted to a fee range. Domestic National ID fee amounts remain unestablished; this
staging patch does not invent a Fee amount or complete fee model for those procedures.

All administrative material starts as `needs_reverification`, with no `verified_on` or new
re-verification window. Source retrieval dates describe the merged research, not a fresh check.
Every claim gets ordered Source links with **context-only** support. The stored passage is
explicitly a research summary, not a purported verbatim primary-source quotation. Reviewers
must retrieve exact passages and review applicability before claiming evidentiary support.
S23, the old passport locator that served a privacy policy at the research date, is retained
only as an unlinked discrepancy-source record and supports no imported claim.

A product Warning on each version records its scope, research reference, manifest fingerprint
and remaining gates. It is not an approval, a new database audit event or a substitute for
published-history protections. Bilingual drafts still require independent semantic review.

## What deliberately does not change

The commands create no Service Questions, candidates, source-Fact definitions, contradiction
rules, routing associations, dependencies or Planning Scenarios. They neither invoke nor
change the old renewal importers. Existing Service activation is preserved; a newly created
Service is inactive. No user is created. No approval, publication, deployment, migration,
network request or applicant-case storage is performed by the import operation.

Version applicability is deliberately incomplete (`{}`), with no effective interval inferred
from the research date. The existing mandatory applicability gate rejects publication of an
untouched staged version. New procedures also lack curated candidates. This is not a hidden
false rule, nor a workaround that lets incomplete guidance pass publication.

Once editors turn a staged draft into real authored content, its appropriate rules, exact
claims, sources, scenarios, applicable specialist reviews and normal publication gates still
need to be completed. The unchanged staging importer will then reject that edited aggregate;
it is not a synchronization command that overwrites editorial work.

## Run locally

Use the repository's Python 3.14, uv, exported development environment and migrated local
PostgreSQL database. See [local setup](../development.md). The author must already exist and
be both active and staff. Run from the repository root. `--list` needs normal Django setup
but does not perform the importer or author lookup.

```bash
uv run python backend/manage.py import_passport_suite --list \
  --settings=bardi.settings.development
uv run python backend/manage.py import_national_id_suite --list \
  --settings=bardi.settings.development
```

Test both operations without retaining their writes. Replace `YOUR_STAFF_USERNAME` first:

```bash
uv run python backend/manage.py import_passport_suite --author YOUR_STAFF_USERNAME \
  --dry-run --settings=bardi.settings.development
uv run python backend/manage.py import_national_id_suite --author YOUR_STAFF_USERNAME \
  --dry-run --settings=bardi.settings.development
```

To retain the research drafts in the configured **local** database, rerun those two commands
without `--dry-run`. To verify an existing pristine import without creating anything:

```bash
uv run python backend/manage.py import_passport_suite --author YOUR_STAFF_USERNAME \
  --check --settings=bardi.settings.development
uv run python backend/manage.py import_national_id_suite --author YOUR_STAFF_USERNAME \
  --check --settings=bardi.settings.development
```

A successful import reports every catalog row, resulting version IDs, blockers, fingerprint
and created-version count. An unchanged repeat should create zero versions. A dry run reports
the versions it would create but rolls back its transaction. `--check` on a missing import fails.
The modes are mutually exclusive. Never treat a successful import as publication readiness.

## Atomicity, drift and coexistence

Each public operation has one atomic transaction and one final aggregate verifier. A failure
in late verification rolls back all writes from that call. An existing namespace is verified,
not partially rebuilt. Missing/extra claims, changed text, source order, trust, author, version
fields or unexpected draft workflow children are rejected rather than repaired. The manifest
fingerprint is checked as part of expected content; it does not replace the existing importer
integrity or publication-signature mechanisms.

The two new commands use a common transaction-scoped PostgreSQL advisory lock to serialize
one another. This is not a concurrency guarantee with existing importers or Admin edits. Run
imports without simultaneous editing of their target aggregates or concurrent legacy imports.
There is no `--force`, update-in-place or signature-refresh option.

**Legacy-first:** with the existing renewal baselines imported, suite staging is designed to
leave their Questions, candidates, Fact registry and behavior signatures unchanged. Tests for
that integration are included but still require execution on the real project database.

**Suite-first:** a new Service remains inactive. The existing legacy renewal commands require
an active canonical Service; they therefore reject until an editor explicitly makes the
corresponding activation decision. This patch does not silently activate it or weaken that
legacy contract. Existing Procedure labels are retained verbatim for the two renewal identities.
Neither original dated version is deleted or rewritten.

## Required validation before merge or real use

Only the database-free manifest suite and Python syntax checks were executed during patch
preparation. Django/PostgreSQL, Ruff and Mypy validation is **pending**. No CI run was started.
Run these in a real checkout with the project's supported environment before relying on the
import operation. Tests create disposable test databases; they do not use production data.

```bash
uv sync --locked --extra dev
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend
uv run python -m compileall -q backend

(cd backend && uv run python -m unittest knowledge.tests.test_suite_specs -v)
(cd backend && uv run python manage.py test \
  knowledge.tests.test_suite_specs knowledge.tests.test_suite_draft_importers \
  --settings=bardi.settings.test --noinput)
(cd backend && uv run python manage.py test \
  --settings=bardi.settings.test --noinput)
```

The included PostgreSQL tests cover both suite import orders/repeats, command reporting,
check/dry-run behavior, late rollback, author validation, edited/deleted/extra child rejection,
source/trust drift, missing whole versions, rejected publication and legacy coexistence.
They are test implementations, **not claimed passing results** in this patch.

## Remaining work toward usable full-suite guidance

Accept and implement I02 before changing the shared interview/selection catalog. Then close
family-specific consequential gaps, choose the correct bounded transaction/mission scope,
implement typed Facts and actual conditional rules, and convert the applicable researched
scenarios into executable Planning Scenarios. Complete independent source/bilingual/specialist
review before the ordinary publication workflow. Do not use these staged notes as shortcut
approval for a blocked checklist, unreviewed military exception or invented office.

Passport and National ID work can advance independently. A staged draft is a starting point
for that editorial and engineering work, not evidence that either full suite is complete.
