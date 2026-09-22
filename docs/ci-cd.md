# CI/CD

The repository uses GitHub Actions for production continuous integration.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request, every push to `main`, and manual
`workflow_dispatch` runs. It has four deliberately separate required tracks:

- The Python 3.14 **Production backend** job runs against PostgreSQL 17. It installs
  only from the committed `uv.lock`, then runs Ruff lint and format checks, Mypy, Python
  compilation, Django deploy checks, migration consistency/rollback checks, PostgreSQL
  backup/restore verification, the focused cross-family production acceptance suite,
  and the broader domain/publication/API/privacy/Admin/hardening suites.
- An independent **Frontend** job uses Node 22 and `npm ci` with the committed
  `frontend/package-lock.json`. It checks the OpenAPI snapshot and generated TypeScript
  types, then runs frontend lint, type checking, the complete Vitest unit/component suite,
  a production Next build and Playwright browser tests. Managed Chromium and its Linux
  dependencies are installed with `npx playwright install --with-deps chromium` from
  `frontend/`; no locally installed browser is assumed in CI.
- A **Development Compose** job copies the safe development `.env.example`, validates
  `compose.yaml`, builds the backend and frontend development images, starts PostgreSQL,
  Django and Next.js together, and waits for real HTTP 200 responses from both
  `GET /v1/services` and `/ar`. It tears down the disposable volumes after every run.
  It also runs the [local recovery regression](operations/local-backups.md#regression-checks)
  with Python 3.14 and locked dependencies in a separate random disposable PostgreSQL project,
  verifying the guarded CLI, synthetic record preservation and restore invariants.
  This catches recovery-tooling, Dockerfile, Compose wiring, container-DNS and startup
  regressions that the backend and frontend jobs intentionally do not exercise.
- A parallel **Questionnaire sandbox** job installs Python 3.14 and locked development
  dependencies, runs tools-wide Ruff lint/format and compilation, type-checks the four
  sandbox tool files, and runs the sandbox probe unit regressions. It also installs Node 22,
  locked npm dependencies and managed Chromium with Linux dependencies, then runs the 16 focused
  real-browser configuration/reporter Vitest tests. Its `--disposable --with-browser` Docker/HTTP
  probe retains a 30-minute step limit within a 40-minute job deadline, allowing installation
  overhead. It covers copied-data fidelity, all publication gates, login/cookies/notices,
  persistence and guarded refresh, plus three real-backend questionnaire browser journeys on
  the same Next development server in owned disposable projects; see
  [sandbox regression scope and commands](operations/questionnaire-sandbox.md#regression-scope).
  It needs no copied authoring `.env` and does not establish real authored-content readiness.

Production CI intentionally uses the same Python runtime family as local backend development.
The retired research prototype is no longer compiled or tested on `main`; production acceptance
tests are authoritative for supported behavior.

The final `CI required` job depends on all four tracks and succeeds only when
`PRODUCTION_RESULT`, `FRONTEND_RESULT`, `COMPOSE_RESULT`, and `SANDBOX_RESULT` are each exactly `success`.
A failure, cancellation or skipped dependency cannot pass the aggregate. This stable name
remains the branch-protection check; the frontend, Compose and sandbox gates do not weaken or replace
the production-backend track.

The workflow uses read-only repository permissions. CI supplies explicit test-only
PostgreSQL credentials, a strong Django secret, allowed hosts, and a valid HTTPS CSRF
origin for the backend job. The Frontend job uses only loopback test origins and disables
Next telemetry; it needs no production secrets or PostgreSQL service. The Compose job uses
only the repository's safe development example values and destroys its database volume when
it finishes. The sandbox probe generates private test-only configuration and cleans up only its
verified owned disposable resources; no real archive or private artifact is uploaded.

### Frontend contract and browser gates

The Frontend job also installs Python 3.14, uv and locked Python runtime dependencies
(`uv sync --locked`). `tools/export_web_api.py` and its Vitest regression import the real
Django Ninja API declarations, but build OpenAPI entirely in memory without a database
connection, migrations or production settings/secrets. No backend test groups are duplicated
in this job.

The schema-drift gate follows the
[local API schema checks](development.md#frontend-checks-and-api-schema): the snapshot
must match backend declarations, and regenerating types must leave both
`frontend/api-schema.json` and `frontend/src/api/generated.d.ts` unchanged. Runtime response schemas are also checked against the generated
types by `npm --prefix frontend run typecheck`. An intentional API change includes both
regenerated files, not just a manually patched TypeScript declaration.

Playwright runs the built Next server at `http://localhost:3010` (bound to `127.0.0.1`)
against a **test-only** API stand-in on `127.0.0.1:8451`. The job sets
`BARDI_API_ORIGIN=http://127.0.0.1:8451` and `BARDI_SITE_ORIGIN=http://localhost:3010`
for build/runtime consistency. These synthetic web integration tests
do not establish Django/PostgreSQL correctness or replace the backend's researched-family
acceptance coverage. The workflow uploads no browser traces, screenshots, videos or reports.
Do not add artifacts or telemetry containing real case data.

See [development checks](development.md#frontend-checks-and-api-schema) for local commands,
including managed Chromium or `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` for an existing browser,
and [`frontend/README.md`](../frontend/README.md#regression-scope) for coverage limitations.
The Frontend job also runs the database-free Admin draft-pack JavaScript regressions.
Dependency-upgrade guidance lives in [frontend setup](development.md#frontend-setup);
CI uses ordinary locked `npm ci`.

### Development Compose gate

The Compose job exercises the same development topology documented in
[`development.md`](development.md). It runs `docker compose config --quiet`, then
`docker compose up --build -d`, polls the backend and frontend loopback endpoints, and always
runs `docker compose down -v --remove-orphans` afterward.

The frontend Compose service keeps `node_modules` in a named volume so the source bind mount
does not hide dependencies from the image. Because named volumes survive ordinary container
recreation, startup runs locked `npm ci` before Next so a changed `package-lock.json` cannot
leave a stale dependency tree mounted over a freshly rebuilt image.

After this workflow is merged and has produced a successful `CI required` check, protect
`main` and require `CI required` before merge.

## Continuous delivery

There is currently no application release or deployment workflow. The former prototype-only
release workflow was retired with the executable prototype under
[ADR 0018](adr/0018-retire-research-prototype.md). Frontend integration does not restore it
or add production application deployment or migrations.

A production Django/Next.js deployment still needs an explicitly selected and hardened
hosting/ingress target and a separately authorized delivery workflow, for example behind a
GitHub Environment with deployment-specific credentials and approvals. These CI additions
choose no production domain or provider and do not change the backend ingress/security
contract in [`operations/private-pilot.md`](operations/private-pilot.md). The Next proxy is
not an Admin gateway or a substitute for trusted proxy-header handling, edge rate limits and
privacy-safe platform logging; see
[`architecture/production-backend.md`](architecture/production-backend.md).
