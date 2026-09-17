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
When the team joins, set `PROCEDURE_VERSION_REVIEW_MODE=independent`
across the deployment and restart/recreate all backend processes.

Solo does not bypass specialist safety: keep risk flags truthful and high-risk content unpublished
without eligible specialists independent of author and publisher.

Remove `PROCEDURE_VERSION_REVIEWS_REQUIRED` from old configuration; it is no longer supported and
there is no production off mode. Test-only settings isolate unrelated tests by explicitly omitting
the review gate, not by disabling production review policy.

See the [review-mode contract](architecture/procedure-version-review-roles.md#deployment-review-mode)
and [editor workflow](editorial-process.md#solo-now-independent-when-the-team-joins)
for policy, approvals and audit behavior.

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

Use the committed npm lock with `npm ci`; use npm 11 for dependency upgrades,
e.g. `(cd frontend && npx --yes npm@11 install <package>@<version>)`. No global npm upgrade
is required. Do not assume disabling install scripts is safe without running the complete
frontend checks. See [`frontend/README.md`](../frontend/README.md) for configuration,
UX and privacy/security boundaries.

The Service directory is loaded from the backend, not bundled fake data. Only explicitly
active Services are listed; publication alone does not activate one. Use the imports below
and the mode-aware Admin review/publish workflow to author usable guidance. Imports
do not publish or approve knowledge. Empty navigation and API unavailability are explicit
states, not a switch to a demo catalog or sample plan.

## Generic draft-pack authoring

Draft packs transport research into unpublished drafts. Start with the operator guide's
[CLI research/dry-run/write workflow](draft-packs/README.md#cli-research-dry-run-then-write),
[update roundtrip](draft-packs/README.md#update-roundtrip-and-deletion-consent) and
[output/recovery guidance](draft-packs/README.md#output-and-recovery).
Use the host-run setup above and apply pending branch migrations to your chosen local database
before database-backed commands; adding this feature does not automatically migrate an existing
host-run database or update its `.env`. No production migration is authorized by these examples.

### Native Admin draft-pack workflow

Open `/admin/knowledge/procedureversion/` for **Import research draft** and template downloads;
existing drafts expose **Draft-pack tools**. Follow the operator guide for
[upload/inspection/confirmation](draft-packs/README.md#admin-upload-inspect-then-confirm) and
[advisory readiness/scenario previews](draft-packs/README.md#advisory-readiness-and-stored-scenario-previews).
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
(cd backend && POSTGRES_DB=bardi_draft_pack_checks uv run python manage.py test \
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

A rerun returns the identical draft and rejects semantic conflicts. Its military risk requires an
independent military specialist in both review modes; import is not review or publication.

## National-ID-renewal knowledge import and review

Import or verify the researched ordinary domestic National ID-renewal draft with an existing
staff author:

```bash
uv run python backend/manage.py import_national_id_renewal --author <username> \
  --settings=bardi.settings.development
```

The command does not create users, approvals, or publication metadata. A rerun returns the
identical draft and rejects planning, scenario, provenance, trust, source, and review-policy
semantic drift. The imported ordinary fee remains an explicit unknown value, the previous-card
research lead remains needs-reverification, and exact
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
Both drafts flag legal and military risk and require eligible independent specialists for both
in either review mode. Without specialists, keep both drafts unpublished.

The backend's trusted HTTPS ingress, proxy-header, HSTS and rate-limit requirements, plus
[backup](operations/private-pilot.md#backup-policy) and
[restore procedures](operations/private-pilot.md#restore-procedure), are in
[`operations/private-pilot.md`](operations/private-pilot.md). The Next integration does
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

Servers are not reused. If port 8451 is occupied, set `BARDI_E2E_API_PORT=8471` for
`test:e2e` and use `BARDI_API_ORIGIN=http://127.0.0.1:8471` for its build. CI uses 8451.

For visual inspection after the browser-test build, start these in two terminals from
`frontend/` (with the default API port free):

```bash
node --experimental-strip-types e2e/api-stand-in.mjs
```

```bash
BARDI_API_ORIGIN=http://127.0.0.1:8451 BARDI_SITE_ORIGIN=http://localhost:3010 \
  npm run start -- --port 3010
```

Open `http://localhost:3010/ar` or `/en`. Follow `frontend/e2e/fixtures.mjs` and use
`TEST-ONLY-NOTE`, never personal information. Stop both processes before Playwright,
which needs to own the same ports.

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

The historical issue #119 probe commands, 2026-09-10 results, limitations and linked raw
JSON are preserved in the [loader performance baseline](operations/loader-performance-baseline.md).
This synthetic disposable-database probe is not a routine setup or acceptance check.

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
