# Private-pilot backend operations

This document is the deployment and recovery contract for the first Bardi private pilot. It is intentionally provider-neutral. The backend remains one Django/PostgreSQL modular monolith and does not require Redis, Celery, a search service, a workflow engine, a microservice, or any paid SaaS dependency.

## Deployment topology

Run the Django application behind one trusted HTTPS reverse proxy. The application process must not be directly reachable from the public internet.

The proxy contract is strict:

- terminate TLS at the proxy;
- redirect or reject plaintext traffic before it reaches Django;
- overwrite, rather than append to or trust client-supplied, `X-Forwarded-Proto`;
- overwrite `X-Real-IP` with the actual client address;
- forward `X-Forwarded-Proto: https` to Django;
- keep the application port private to the proxy/network;
- apply sensible request-size and connection limits at ingress.

Django production settings trust only `X-Forwarded-Proto` for HTTPS detection. This is safe only when the application is unreachable except through a proxy that strips/overwrites that header.

The built-in API limiter is deliberately process-local. The initial pilot should therefore run one application process/worker when relying on that limiter alone. If the deployment is changed to multiple application workers or instances, add a global rate limit at the trusted ingress before increasing concurrency. That ingress limit does not need access to request bodies.

## Required production configuration

Production startup fails if any of these are missing or blank:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

Additional fail-closed rules:

- `DJANGO_SECRET_KEY` must be at least 50 characters and may not use Django's `django-insecure-` prefix.
- `DJANGO_ALLOWED_HOSTS` may not contain `*`.
- every `CSRF_TRUSTED_ORIGINS` entry must use HTTPS.
- PostgreSQL is the only supported production database.

Optional bounded tuning:

- `DJANGO_SECURE_HSTS_SECONDS` — defaults to 3600 seconds, minimum 300, maximum one year.
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` — defaults to false.
- `DJANGO_SECURE_HSTS_PRELOAD` — defaults to false and is rejected unless HSTS is at least one year and includes subdomains.
- `DJANGO_ADMIN_SESSION_AGE_SECONDS` — defaults to 3600 seconds, range 300–43200.
- `PUBLIC_API_RATE_LIMIT_REQUESTS` — defaults to 60 requests per window, range 1–10000.
- `PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS` — defaults to 60 seconds, range 1–3600.

Do not enable HSTS subdomains or preload until every relevant subdomain is known to support HTTPS permanently. The short initial HSTS duration is intentional for the pilot and should be increased only after the ingress/domain configuration has been verified in production.

## Browser and Admin protections

Production enforces HTTPS redirects, secure session and CSRF cookies, HTTP-only session cookies, `SameSite=Lax`, browser-close session expiry, a bounded Admin session lifetime, `X-Content-Type-Options: nosniff`, same-origin referrer/COOP policy, and `X-Frame-Options: DENY`.

Django Admin remains staff-only. Do not create public accounts. Give staff individual accounts rather than shared credentials, use strong unique passwords, remove access promptly when no longer needed, and keep superuser accounts to the minimum necessary for recovery/administration. Publication and specialist-review permissions remain governed by the application review workflow rather than by hiding the Admin URL.

## Public API abuse control

Every `/v1/` request passes through the built-in fixed-window limiter in production.

The limiter:

- never reads the request body;
- never stores Facts;
- never stores raw client addresses;
- HMACs the trusted client address with the Django secret before using it as a process-local counter key;
- maintains separate route buckets for planning and service navigation;
- returns HTTP 429 with the stable body `{"type":"invalid","diagnostics":[{"code":"rate_limited","path":[]}]}` and a `Retry-After` header.

The limit is an application safety net for a small single-process pilot, not a distributed denial-of-service control. A future multi-worker deployment must add an ingress-level global limit while keeping body logging disabled.

## Error behavior

Public API parsing, schema validation, expected knowledge/database failures, rate limiting, and unexpected exceptions all return bounded public error/result shapes. Unexpected exceptions are handled even when Django `DEBUG` is accidentally enabled in a non-production test context; traceback locals and exception values are never serialized into the API response.

Do not add exception objects, request objects, request bodies, planning inputs, raw Facts, full evaluation traces, or contradiction values to public API logs.

## Health and readiness

Two provider-neutral endpoints are available:

- `GET /health/live` — application liveness only. It does not query PostgreSQL and returns `200 {"status":"ok"}`.
- `GET /health/ready` — readiness. It executes only `SELECT 1` against PostgreSQL and returns either `200 {"status":"ready","checks":{"database":"ok"}}` or `503 {"status":"not_ready","checks":{"database":"unavailable"}}`.

Both responses use `Cache-Control: no-store`. They expose no database host, credentials, exception messages, migration names, knowledge records, or Facts.

Use liveness to decide whether the application process should be restarted. Use readiness to decide whether it should receive traffic. A readiness failure should not automatically destroy or recreate the database.

## Structured operational observability

Production emits allow-listed JSON operational events for known application routes. The schema is limited to:

- timestamp and severity;
- event name;
- fixed route label (`/v1/planning`, `/v1/services`, `/health/live`, `/health/ready`, or `/admin/*`);
- HTTP method and status;
- coarse duration in milliseconds;
- readiness database state (`ok`, `unavailable`, or `not_checked`);
- a server-generated request ID.

Dynamic URL segments, query strings, client addresses, headers, request/response bodies, raw Facts, planning traces, exception objects, and traceback text are not part of this schema. The formatter/filter fail closed to a fixed vocabulary even if an application record is populated with hostile extra fields.

The existing planning privacy filter remains in front of Django/framework logging as a separate defense for `/v1/planning`.

## Schema migrations

Treat migrations as forward operations in production unless a specific rollback has been tested against the exact deployed application/data state.

Deployment procedure:

1. Take a verified PostgreSQL backup before applying schema changes that could affect stored knowledge, review, or audit data.
2. Run `python backend/manage.py migrate --plan --settings=bardi.settings.production` and review the plan.
3. Deploy application code compatible with the target migration sequence.
4. Run `python backend/manage.py migrate --noinput --settings=bardi.settings.production` exactly once from the deployment/release process.
5. Run `python backend/manage.py migrate --check --settings=bardi.settings.production`.
6. Require `/health/ready` to return 200 before sending pilot traffic.

Do not run ad-hoc DDL against production. Do not blindly reverse migrations after a failed deploy: a syntactically reversible migration may still have lost or transformed data in a way that cannot be reconstructed. Restore from the pre-migration backup when the safe forward fix is not possible.

CI deliberately reverses the latest project-owned `knowledge` migration across one supported boundary (`0016` to `0015`) on a disposable database, reapplies it, and verifies the migration state. This proves that the current rollback boundary can execute on PostgreSQL; it does **not** assert that production data rollback is semantically safe. A teardown of the entire historical migration chain to zero is not a recovery strategy and is not treated as a release requirement.

## Backup policy

The database contains curated knowledge, publication/review state, users/staff permissions, and audit history. It does **not** contain raw anonymous planning Facts, so those Facts must never appear in database backups.

Private-pilot baseline:

- take a backup before every production migration;
- take at least one automated database backup every 24 hours while the pilot is active;
- keep at least seven daily recovery points;
- store backups separately from the running database and application host;
- encrypt backups at rest and in transit using whatever facility the chosen host/environment provides;
- restrict backup access to the same or narrower group that can administer production PostgreSQL.

Initial recovery target: RPO up to 24 hours and RTO up to 4 hours. These are pilot targets, not guarantees from the application; tighten them when a deployment provider and operational budget are selected.

## Restore procedure

Restore into a new empty PostgreSQL database first; do not overwrite the only production database during a drill.

1. Provision an empty PostgreSQL database with a compatible major version.
2. Restore the latest selected backup with `pg_restore` (or the provider's equivalent PostgreSQL-native restore).
3. Point a non-public application instance at the restored database.
4. Run `migrate --check` with production-equivalent settings.
5. Run Django system checks.
6. Verify `/health/ready` returns 200.
7. Verify Admin login and a read-only sample of Services/Procedure Versions/audit history.
8. Only then decide whether to promote the restored database or keep the current production database.

CI exercises the same primitive with PostgreSQL 17: it creates a custom-format `pg_dump`, restores it into a separate disposable database, and runs `migrate --check` against the restored copy. This detects basic backup-format, schema, and credential regressions without requiring a hosted backup product.

Perform a manual restore drill before the private pilot begins and after any material change to database hosting or backup tooling.

## Secret rotation and incident notes

Rotate `DJANGO_SECRET_KEY` deliberately: doing so invalidates signed values and should be treated as a deployment event. Rotate database credentials through the hosting environment and restart application processes so no stale connection continues using the old credentials.

If logs or error monitoring ever contain a raw planning Fact, request body, or full planning trace, treat that as a privacy incident: stop the affected sink, preserve only what is required for investigation, remove the unsafe logging path, and verify the privacy tests before resuming traffic.
