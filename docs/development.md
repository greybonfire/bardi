# Local development

The production backend uses Python 3.14 or newer, [uv](https://docs.astral.sh/uv/),
Docker, and Docker Compose. PostgreSQL is required; there is no SQLite fallback.
The Next.js frontend additionally uses a current **Node 22** release and npm.

Python 3.14 is the supported production-development baseline: local development, CI, and the
eventual deployed backend should use the same runtime family. The retired research prototype is
preserved in Git history and is not part of the supported development or CI surface.

## Full-stack Docker Compose setup

For a one-command development environment, from the repository root copy the local
configuration and start the stack:

```bash
cp .env.example .env
docker compose up --build
```

Compose starts PostgreSQL, Django, and Next.js. Open **http://localhost:3000/ar**; the
Django Admin is at `http://localhost:8000/admin/`. The backend container applies pending
migrations before starting Django, and the frontend waits for the backend health check.
Source directories are mounted so Django and Next.js reload during development. Compose
uses `postgres` as the database hostname and `backend` as the server-side frontend API
hostname; these overrides are kept inside `compose.yaml` and do not change the host-run
`.env` contract.

Create an Admin user from another terminal after the stack is healthy:

```bash
docker compose exec backend \
  python backend/manage.py createsuperuser --settings=bardi.settings.development
```

Stop the services while preserving the database volume with:

```bash
docker compose down
```

Use `docker compose down -v` only when intentionally deleting the local database. This
Compose setup is for local development; it is not a production deployment definition.

## Backend setup (host-run workflow)

From the repository root, copy the development environment contract and export it for
host-run Django commands:

```bash
cp .env.example .env
set -a
. ./.env
set +a
uv sync --locked --extra dev
docker compose up -d postgres
uv run python backend/manage.py migrate --settings=bardi.settings.development
uv run python backend/manage.py createsuperuser --settings=bardi.settings.development
uv run python backend/manage.py runserver --settings=bardi.settings.development
```

Compose reads `.env` automatically. Exporting the file as shown also supplies the same
values to Django commands running on the host. The Admin is available at
`http://localhost:8000/admin/`.

The development PostgreSQL port is published only on `127.0.0.1`; the known development
credentials in `.env.example` must never be used for a deployed database.

The development settings include only local-safe defaults. Production settings fail
closed and require every secret, host, origin, and PostgreSQL value to be provided.

For the complete editor-facing workflow—including manual Admin authoring, evidence, review,
publication, successor drafts, re-verification, and deterministic programmatic imports—see
[`editorial-process.md`](editorial-process.md).

## Solo now; independent when the team joins

`PROCEDURE_VERSION_REVIEW_MODE` is a deployment-wide environment variable/Django setting with
exactly `solo` and `independent` values. Unset defaults to `independent`; invalid values fail
closed. The local `.env.example` explicitly opts into `solo`. For an existing local `.env`, set:

```dotenv
PROCEDURE_VERSION_REVIEW_MODE=solo
```

Export the updated file for host commands and restart Django; for Compose, recreate the backend
container so it receives the new environment (`docker compose up -d --force-recreate backend`).
In solo, name yourself as accountable author in the Review Policy and publish ordinary drafts
with your existing permissions. No general approvals, self-approval forms, or account switching
are needed. Optional independent general reviews remain history but are not consumed.

Always configure high-risk flags truthfully. Every legal, military, custody/guardianship, or
contested-identity flag still requires a fresh, permission-eligible specialist distinct from both
author and publisher. Without a real specialist, leave that content unpublished; never clear a
risk to bypass policy. Evidence/trust/scenario/domain/bilingual/effective-date gates remain active.

When the team joins, set `PROCEDURE_VERSION_REVIEW_MODE=independent` across the deployment and
restart/recreate all backend processes. Future attempts then require fresh, eligible general
dimension approvals (including discrepancy as applicable), independent of author and publisher,
as well as applicable specialists. The author may still publish. Existing snapshots and audit
history are not rewritten: new publish events record applied mode and only actual approvals
consumed; legacy events and withdrawal rows retain null/unrecorded mode.

Remove `PROCEDURE_VERSION_REVIEWS_REQUIRED` from old configuration; it is no longer supported and
there is no production off mode. Test-only settings isolate unrelated tests by explicitly omitting
the review gate, not by disabling production review policy.

This policy/audit boundary was established by
[ADR 0019](adr/0019-use-explicit-solo-and-independent-publication-review-modes.md). PR2 also
established the generic draft-pack CLI below. Native Admin upload/inspection/confirmation,
publication-readiness checks and stored-scenario previews are now available; manual Admin
authoring and deterministic imports remain available.

## Frontend setup

Keep Django running in its own terminal at `http://localhost:8000`. In another terminal,
from the repository root, set up and run the web app:

```bash
cp frontend/.env.example frontend/.env.local
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open **http://localhost:3000/ar**. `/` redirects to Arabic (RTL); the **English** header
link switches to the corresponding English (LTR) page. Next reads its own
`frontend/.env.local`, not the root backend `.env`. The example uses server-only
`BARDI_API_ORIGIN=http://127.0.0.1:8000` and SEO origin
`BARDI_SITE_ORIGIN=http://localhost:3000`; do not copy backend secrets into it.

Use the committed npm lock with `npm ci`. npm 10 encountered an Arborist bug during
dependency updates; npm 11 installed the current lock. For dependency upgrades use npm 11,
e.g. `(cd frontend && npx --yes npm@11 install <package>@<version>)`; no global npm upgrade
is required. See [`frontend/README.md`](../frontend/README.md) for configuration and the
complete frontend scope, security boundaries and test coverage.

The Service directory is loaded from the backend, not bundled fake data. Only explicitly
active Services are listed; publication alone does not activate one. Use the imports below
and the mode-aware Admin review/publish workflow to author usable guidance. Imports
do not publish or approve knowledge. Empty navigation and API unavailability are explicit
states, not a switch to a demo catalog or sample plan.

## Generic draft-pack authoring

See [draft packs v1](draft-packs/README.md) for the exact schema, supported synthetic example,
[external-LLM prompt](draft-packs/llm-prompt.md), permission matrix and safe update roundtrip.
Use the host-run setup above and apply pending branch migrations to your chosen local database
before database-backed commands; adding this feature does not automatically migrate an existing
host-run database or update its `.env`. No production migration is authorized by these examples.

With a real active staff `EDITOR` holding the required permissions, run from the repository root:

```bash
uv run python backend/manage.py export_draft_context --actor EDITOR \
  --output /tmp/bardi-context.json --settings=bardi.settings.development
uv run python backend/manage.py import_draft_pack docs/draft-packs/examples/minimal-research.json \
  --new --actor EDITOR --dry-run --settings=bardi.settings.development
uv run python backend/manage.py export_draft_pack --version DRAFT_ID --actor EDITOR \
  --output /tmp/bardi-draft.json --settings=bardi.settings.development
```

The last command requires an existing version: dry-run creates none. Remove `--dry-run` only
after inspecting the result on a disposable development database. The example creates an inactive
Service and unpublished source Fact, not usable government guidance. Exports refuse existing
output paths; there is no overwrite flag. For `export_draft_pack`, `--version ID` selects knowledge
and intentionally overrides Django's usual version-banner option.

For updates preserve the exported fingerprint, use `--target-version DRAFT_ID` instead of `--new`,
and add `--allow-deletions` only for reviewed intended deletions. Existing Service setup is
protected even inactive; imports cannot verify, approve, publish, clear risks or rewrite evidence
workflow history. Finish manual Admin followups. `concurrent_edit` means retry after competing
work finishes; conservative fingerprints may require re-export/reconciliation. The short
knowledge-table locks used by import/export permit ordinary reads but can briefly delay writers.

### Native Admin draft-pack workflow

With the backend running, open `/admin/knowledge/procedureversion/`. Use **Import research draft**
or **Download incomplete research template**. Existing draft pages provide **Draft-pack tools**
for export/context downloads, targeted import, **Check publication readiness as current editor**
and **Preview stored scenarios**. See [the operator guide](draft-packs/README.md#admin-upload-inspect-then-confirm)
for exact routes, permissions, 15-minute exact-file confirmation and manual followups. No new
migration, dashboard, public endpoint or Next.js change is required by this adapter.

Inspection is rollback-only and permits incomplete research despite publication blockers. Checks
are explicitly requested, not run on ordinary page loads/saves. Preview uses stored scenarios and
displays Arabic/English production projections without activation, publication or resealing.
The runtime template is `backend/knowledge/draft_pack_template.json` (the backend image does not
copy `docs/`); its regression test requires equality with the documented synthetic example.

### Draft-pack contract checks

Schema generation/parsing needs no PostgreSQL:

```bash
uv run python tools/export_draft_pack_schema.py --check
(cd backend && uv run python -m unittest knowledge.tests.test_draft_pack_schema -v)
```

When intentionally changing the transport, run `uv run python tools/export_draft_pack_schema.py`,
review `docs/draft-packs/draft-pack-v1.schema.json` and the supported example, then rerun `--check`.
Do not hand-edit the generated schema. Focused service/CLI/history/concurrency regressions require
exported environment values and PostgreSQL, using a disposable Django test database:

```bash
(cd backend && uv run python manage.py test knowledge.tests.test_draft_packs \
  --settings=bardi.settings.test --noinput)
```

Focused Admin/inspection/readiness/scenario regressions use Django's test runner, which creates
its disposable test database through PostgreSQL's maintenance connection; a pre-created base
application database is not needed. With `.env` values exported and PostgreSQL running, choose a
unique unused test database name for parallel work (do not use `--keepdb`):

```bash
(cd backend && POSTGRES_DB=bardi_task3_docs_probe uv run python manage.py test \
  knowledge.tests.test_draft_pack_inspection knowledge.tests.test_draft_preview \
  knowledge.tests.test_draft_pack_admin --settings=bardi.settings.test --noinput)
```

These tests cover transactional rollback, stale state, publication policy, stored scenarios,
authorization, CSRF, upload limits and token binding. Dependency-free JavaScript VM regressions
require Node 22 and run from the repository root without PostgreSQL or npm installation:

```bash
node --test backend/knowledge/tests/draft_pack_admin.test.cjs
```

Neither Django tests nor these VM regressions are real-browser checks. Separately check
retained-file inspection/confirmation, file-change
invalidation, no-JavaScript reselection, and Arabic RTL/English LTR desktop/mobile rendering.
These scoped checks do not replace the complete backend delivery suite below.

## Passport-renewal knowledge import and review

Import or verify the production draft with an existing staff author (the command never creates
users, approvals, or publication metadata):

```bash
uv run python backend/manage.py import_passport_renewal --author <username> \
  --settings=bardi.settings.development
```

A rerun returns the identical draft and rejects semantic conflicts. In `independent`, eligible staff
approve evidence/source, rule/logic, scenario/behavior, bilingual-semantic, and applicable
discrepancy dimensions. Solo skips those general approvals. In both modes, an independent military
specialist must approve the military risk. The publisher (who may be the author, but cannot supply
consumed approvals) finally uses the Procedure Version **publish selected** action. Import,
review, specialist approval, and canonical publish are intentionally separate operations.

## National-ID-renewal knowledge import and review

Import or verify the researched ordinary domestic National ID-renewal draft with an existing
staff author:

```bash
uv run python backend/manage.py import_national_id_renewal --author <username> \
  --settings=bardi.settings.development
```

The command does not create users, approvals, or publication metadata. A rerun returns the
identical draft and rejects planning, scenario, provenance, trust, source, and review-policy
semantic drift. In `independent`, eligible independent staff review the normal evidence/source,
rule/logic, scenario/behavior, and bilingual-semantic dimensions (and discrepancy as applicable).
In `solo`, those general approvals are skipped. A permitted publisher, who may be the author,
then uses the canonical Procedure Version **publish selected** action. The imported ordinary fee remains an
explicit unknown value, the previous-card research lead remains needs-reverification, and exact
office routing remains unresolved until stronger current evidence is authored.

## Temporary family-exemption knowledge import and review

Import or verify both researched temporary family-exemption drafts with an existing staff
author:

```bash
uv run python backend/manage.py import_temporary_family_exemption --author <username> \
  --settings=bardi.settings.development
```

The command creates neither approvals nor publication metadata. It preserves two immutable
Procedure Versions around the 2026 amendment boundary: the historical version is applicable
through March 24, 2026, and the amended version begins March 25, 2026. Both versions carry the
same six non-ranked, reachability-first Eligibility Bases, and every imported Basis remains
`needs_reverification`. A matched untrusted Basis may therefore be shown as a candidate but
cannot unlock Basis-scoped current guidance; shared trusted operating guidance and researched
jurisdiction routing remain independent.

The import deliberately preserves the research limits: it does not invent the unresolved
incapable-brother semantics, exact Basis-specific document lists, a fee amount, nationwide or
nearest-region routing, a direct prerequisite, or compatibility aliases. The only imported
jurisdiction mappings are the researched Giza, Mansoura, and Zagazig recruitment regions.
In `independent`, independent staff review evidence/source, rule/logic, scenario/behavior, and
bilingual-semantic dimensions (and discrepancy as applicable); solo skips these general approvals.
Because the review policy flags both legal and military risk, fresh eligible legal and military
specialist approvals distinct from author and publisher are required in **both modes** before the
canonical Procedure Version **publish selected** action. Without specialists, keep both drafts
unpublished.

The backend's trusted HTTPS ingress, proxy-header, HSTS and rate-limit requirements are
in [`operations/private-pilot.md`](operations/private-pilot.md). The Next integration does
not provision or replace them: only the two public `/v1` routes are proxied, without browser
cookies, credentials or forwarded client IP headers. Django normally sees a shared Next
proxy IP, so hardened edge rate limits and privacy-safe logging remain required. Production
API access requires a valid server-only `BARDI_API_ORIGIN`; set `BARDI_SITE_ORIGIN` to the
actual public SEO origin. No production domain, deployment or migration is introduced here.

## Frontend checks and API schema

These checks require Node 22, npm, Python 3.14 and uv, but **no PostgreSQL**. The frontend
unit suite includes the real database-free schema-export regression. From the repository root:

```bash
uv sync --locked
uv run python tools/export_web_api.py --check
npm --prefix frontend run api:generate
git diff --exit-code -- frontend/api-schema.json frontend/src/api/generated.d.ts
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

The exporter imports Django Ninja's declarations without connecting to a database. When
intentionally changing the public API, regenerate both committed contract files, review
them with the backend contract change, and then rerun the checks:

```bash
uv run python tools/export_web_api.py
npm --prefix frontend run api:generate
```

`--check` rejects a missing/stale `frontend/api-schema.json`; CI also regenerates
`frontend/src/api/generated.d.ts` and checks the two exact paths for drift. Do not hand-edit
generated types.

For production-build Playwright tests, install the managed browser and build with the
synthetic test origins:

```bash
(cd frontend && npx playwright install chromium)
BARDI_API_ORIGIN=http://127.0.0.1:8451 BARDI_SITE_ORIGIN=http://localhost:3010 \
  npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

The configuration starts a test-only API stand-in on `127.0.0.1:8451` and the built Next
server at `http://localhost:3010` (bound to `127.0.0.1`); keep both ports free. Build with
the same site origin so build-time SEO metadata matches. It does not start Django or PostgreSQL.
On Linux CI, browser installation uses `npx playwright install --with-deps chromium` from
`frontend/`. To use an existing local Chromium-compatible browser instead of downloading one:

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/absolute/path/to/chromium \
  npm --prefix frontend run test:e2e
```

Use only synthetic cases for browser tests and debugging; do not publish traces, screenshots
or other artifacts containing real case data. This browser suite does not replace the
backend's researched-family acceptance tests. The frontend's single-case `sessionStorage`,
shared-device clearing and print/export caveats are documented in
[`frontend/README.md`](../frontend/README.md). Keep Next configured with `logging: false`
and `experimental.serverComponentsHmrCache: false`: the development HMR cache otherwise
caches even `no-store` POSTs. Never attach Facts, Fact keys, bodies, planning responses,
exceptions or traces to Next/APM/ingress logs or analytics.

## Backend checks

Run the production backend checks with a running PostgreSQL service:

The planning validation domain has a database-free fast suite:

```bash
(cd backend && uv run python -m unittest discover -s planning/tests -v)
```

Run the complete checks with PostgreSQL available:

Database-backed Django commands require the exported `.env` values and a running local
PostgreSQL service. The `manage.py test` commands below create and destroy disposable test
databases; the `manage.py migrate` commands below target the configured `POSTGRES_DB`. Do not
use `--keepdb`: test settings select `bardi.testing.FreshDatabaseRunner`, which rejects it
before database setup. Choose a unique unused `POSTGRES_DB` for concurrent runs (Django adds
`test_`). During fresh creation only, a temporary knowledge `post_migrate` receiver disables
regular autovacuum on disposable `knowledge_` tables and their TOAST tables before parallel
cloning; clones inherit these options. Rollback-heavy tests otherwise race autovacuum's
`ShareUpdateExclusiveLock` against the production NOWAIT snapshot lock. Explicit competing
maintenance/writer locks still fail normally: there are no production retries or lock changes.
The receiver is removed even on setup failure; later migration tests, ordinary settings and
application databases are unaffected. PostgreSQL's emergency anti-wraparound vacuum is not
disabled. Disposable databases must be destroyed, not reused for long-running workloads.

The combined backend discovery suite is supported from the `backend/` directory:

```bash
(cd backend && uv run python manage.py test \
  --settings=bardi.settings.test --noinput)
```

The two existing CI database-backed groups are also supported independently:

```bash
(cd backend && uv run python manage.py test \
  api.tests.test_cross_family_production_parity \
  --settings=bardi.settings.test --noinput)

(cd backend && uv run python manage.py test \
  planning.tests knowledge.tests api.tests core.tests \
  --exclude-tag=production_acceptance \
  --settings=bardi.settings.test --noinput)
```

The focused mixed-lifecycle regression is:

```bash
(cd backend && uv run python manage.py test \
  api.tests.test_serialized_rollback_isolation \
  --settings=bardi.settings.test --noinput)
```

The broader production scaffold checks are:

```bash
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend
uv run python -m compileall -q backend
uv run python backend/manage.py check --settings=bardi.settings.development
uv run python backend/manage.py makemigrations --check --dry-run --settings=bardi.settings.test
uv run python backend/manage.py migrate --noinput --settings=bardi.settings.test
uv run python backend/manage.py migrate --check --settings=bardi.settings.test
(cd backend && uv run python manage.py test --settings=bardi.settings.test --noinput)
```

Django test discovery intentionally runs without an app label **from the `backend/`
directory** so it discovers the current tests and automatically includes future production
apps. Procedure-Version tests require PostgreSQL: migrations install `btree_gist`, an
inclusive-range exclusion constraint, and lifecycle immutability triggers. Concurrency tests
must use separate database connections; SQLite is not a supported substitute.

## Service-scoped loader measurement

Issue #119 includes a self-contained disposable PostgreSQL probe. It creates its own namespaced
requested published graph, unrelated published graphs, authoring-draft graphs with evidence,
and unrelated semantic-preserving workflow history; no pre-existing `issue119.requested`
service or custom Fact is required.

```bash
# Create and migrate a disposable database using the local PostgreSQL service.
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -c 'CREATE DATABASE bardi_issue119_repair_probe'
POSTGRES_DB=bardi_issue119_repair_probe uv run python backend/manage.py migrate \
  --settings=bardi.settings.test --noinput

# Seed, compare, and clean each unchanged generated dataset.
PYTHONPATH=backend POSTGRES_DB=bardi_issue119_repair_probe \
  uv run python tools/measure_service_scoped_snapshot.py \
  --facts '{"application_location":"inside_egypt"}' --locale en \
  --evaluation-date 2026-12-31 --scales 0,100,500 \
  --settings bardi.settings.test
```

The probe reports exact queryset-equivalent global validation row sets, SQL count, detached
object counts, elapsed time, full/scoped workflow rows, shared Fact-registry rows, requested
Graph rows, unrelated materialized rows, and full/scoped response equality. Each generated
published anchor carries two discrepancy-transition rows (open/resolved) and two repeated
re-verification rows, so event rows are distinguishable from unique workflow owners. It removes
the namespaced generated rows after each scale and vacuums/analyzes the disposable database so
sequential scales do not measure deleted-row bloat. If interrupted, drop the disposable database
rather than running it against a shared catalog:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -c 'DROP DATABASE bardi_issue119_repair_probe'
```

The 2026-09-10 run produced:

| unrelated published / draft graphs | workflow event rows | validation rows | full SQL / scoped SQL | full detached rows | scoped detached rows | full workflow rows / scoped workflow rows | responses match | full ms / scoped ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| 1 / 1 | 0 | 56 | 23 / 48 | 56 | 46 | 0 / 0 | yes | 123.241 / 214.902 |
| 101 / 101 | 400 | 1556 | 23 / 49 | 1056 | 46 | 400 / 0 | yes | 261.890 / 229.722 |
| 501 / 501 | 2000 | 7556 | 23 / 49 | 5056 | 46 | 2000 / 0 | yes | 554.380 / 333.168 |

For the 101/101 and 501/501 rows, the validation event breakdown is respectively
`200/200/100` and `1000/1000/500` for transition rows/re-verification rows/unique owner rows.

These are single-run elapsed observations, not a capacity benchmark or a query-count-only
performance claim. Global validation remains intentionally row-linear and is reported honestly;
draft graph
and evidence rows are excluded from published/withdrawn validation and scoped DTO materialization.
The validation event counts include every matching history row, while `workflow_owner_rows` is the
unique anchor-owner read used for owner resolution.
The generated workload is synthetic and does not replace imported-family acceptance coverage.
The complete raw result, including per-queryset counts and limitations, is preserved at
[`docs/operations/issue-119-loader-measurement-2026-09-09.json`](operations/issue-119-loader-measurement-2026-09-09.json).

## Teardown

Stop the Next and Django processes with `Ctrl-C` in their respective terminals. Clear any
case in the browser before leaving a shared device; closing a tab may not erase a restored
browser session, and printing/exported copies require separate safe disposal.

Stop the local database service normally with:

```bash
docker compose down
```

To reset the local PostgreSQL database, use the destructive volume teardown. This
**deletes all local PostgreSQL data**:

```bash
docker compose down -v
```
