# CI/CD

The repository uses GitHub Actions for continuous integration and conservative continuous
delivery of the framework-independent prototype.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request, every push to `main`, and manual
`workflow_dispatch` runs. It has three deliberately separate tracks:

- The frozen prototype matrix remains unchanged on Python 3.11, 3.12, and 3.13. Each
  version byte-compiles `prototype/` and runs the complete unittest suite.
- A separate Python 3.14 production-backend job runs against PostgreSQL 17. It installs
  only from the committed `uv.lock`, then runs Ruff lint and format checks, Mypy, compile
  checks, Django deploy checks, migration consistency/rollback checks and a PostgreSQL
  backup/restore probe. Its existing PostgreSQL-backed test groups run cross-family
  production acceptance separately from domain, publication, API/privacy, Admin and
  hardening suites. The production import-boundary test ensures backend code cannot
  import the frozen prototype. This track and the prototype matrix are unchanged by
  frontend integration.
- An independent **Frontend** job uses Node 22 and `npm ci` with the committed
  `frontend/package-lock.json`. It checks the OpenAPI snapshot and generated TypeScript
  types, then runs frontend lint, type checking, the complete Vitest unit/component suite,
  a production Next build and Playwright browser tests. Managed Chromium and its Linux
  dependencies are installed with `npx playwright install --with-deps chromium` from
  `frontend/`; no locally installed browser is assumed in CI.

Production CI intentionally uses the same Python runtime family as local production
backend development. The prototype matrix is historical reference coverage and does not
expand the supported production runtime surface.

The final `CI required` job depends on all three tracks and succeeds only when
`PROTOTYPE_RESULT`, `PRODUCTION_RESULT` and `FRONTEND_RESULT` are each exactly `success`.
A failure, cancellation or skipped dependency cannot pass the aggregate. This stable name
remains the branch-protection check; it does not weaken or replace either existing track.

The workflow uses read-only repository permissions. CI supplies explicit test-only
PostgreSQL credentials, a strong Django secret, allowed hosts, and a valid HTTPS CSRF
origin for the backend job. The Frontend job uses only loopback test origins and disables
Next telemetry; it needs no production secrets or PostgreSQL service.

### Frontend contract and browser gates

The Frontend job also installs Python 3.14, uv and locked Python runtime dependencies
(`uv sync --locked`). `tools/export_web_api.py` and its Vitest regression import the real
Django Ninja API declarations, but build OpenAPI entirely in memory without a database
connection, migrations or production settings/secrets. No backend test groups are duplicated
in this job.

The schema-drift gate runs from the repository root:

```bash
uv run python tools/export_web_api.py --check
npm --prefix frontend run api:generate
git diff --exit-code -- frontend/api-schema.json frontend/src/api/generated.d.ts
```

The snapshot must match the backend declarations, and regenerating types must leave the
committed files unchanged. Runtime response schemas are also checked against the generated
types by `npm --prefix frontend run typecheck`. An intentional API change includes both
regenerated files, not just a manually patched TypeScript declaration.

Playwright runs the built Next server at `http://localhost:3010` (bound to `127.0.0.1`)
against a **test-only** API stand-in on `127.0.0.1:8451`. The job sets
`BARDI_API_ORIGIN=http://127.0.0.1:8451` and `BARDI_SITE_ORIGIN=http://localhost:3010`
for build/runtime consistency. These synthetic web integration tests
do not establish Django/PostgreSQL correctness or replace the backend's researched-family
acceptance coverage. The workflow uploads no browser traces, screenshots, videos or reports.
Do not add artifacts or telemetry containing real case data.

See [`frontend/README.md`](../frontend/README.md) for current test scope and local commands,
including managed Chromium or `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` for an existing local
browser. Dependency upgrades can use npm 11 through `npx` without a global install: npm 10
encountered an Arborist dependency-update bug, while npm 11 installed the current lock.
CI uses ordinary locked `npm ci`; disabling install scripts is not assumed safe without
verifying the complete frontend checks.

After this workflow is merged and has produced a successful `CI required` check, protect
`main` and require `CI required` before merge.

## Continuous delivery

Release automation remains prototype-only. Frontend integration adds no production
application deployment or migration. `.github/workflows/release.yml` provides a release-only
delivery boundary for immutable prototype snapshots; its checkout/runtime action versions
are kept current, but its release behavior is unchanged by frontend integration.

The release workflow runs only when a tag matching `prototype-v*` is pushed. For example:

```bash
git tag prototype-v0.1.0
git push origin prototype-v0.1.0
```

Before publishing anything, it checks out the tagged commit, uses Python 3.12, compiles
the prototype, reruns its complete unittest suite, packages `README.md`, `CONTEXT.md`,
`docs/`, and `prototype/`, and publishes the archive and SHA-256 checksum on a GitHub
Release using the existing tag.

A production Django/Next.js deployment still needs an explicitly selected and hardened
hosting/ingress target and a separately authorized delivery workflow, for example behind a
GitHub Environment. These CI additions choose no production domain or provider and do not
change the backend ingress/security contract in
[`operations/private-pilot.md`](operations/private-pilot.md). The Next proxy is not an
Admin gateway or a substitute for trusted proxy-header handling, edge rate limits and
privacy-safe platform logging; see
[`architecture/production-backend.md`](architecture/production-backend.md).
