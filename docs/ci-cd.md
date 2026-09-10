# CI/CD

The repository uses GitHub Actions for production continuous integration.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request, every push to `main`, and manual
`workflow_dispatch` runs.

The Python 3.14 production-backend job runs against PostgreSQL 17. It installs only from the
committed `uv.lock`, then runs Ruff lint and format checks, Mypy, Python compilation, Django
deploy checks, migration consistency/rollback checks, PostgreSQL backup/restore verification,
the focused cross-family production acceptance suite, and the broader domain/publication/API/
privacy/Admin/hardening suites.

Production CI intentionally uses the same Python runtime family as local backend development.
The retired research prototype is no longer compiled or tested on `main`; production acceptance
tests are authoritative for supported behavior.

The stable `CI required` job depends on the production job and succeeds only when that job
succeeds. This aggregate name is intended for branch protection.

The workflow uses read-only repository permissions. CI supplies explicit test-only PostgreSQL
credentials, a strong Django secret, allowed hosts, and a valid HTTPS CSRF origin. No production
credentials are committed.

## Continuous delivery

There is currently no application release or deployment workflow. The former prototype-only
release workflow was retired with the executable prototype under ADR 0018.

When a deployable Django/Next.js application and hosting target exist, deployment jobs should be
added behind an explicit GitHub Environment with deployment-specific credentials and approvals.
