# Local development

The production backend scaffold uses Python 3.14 or newer, [uv](https://docs.astral.sh/uv/),
Docker, and Docker Compose. PostgreSQL is required; there is no SQLite fallback.

Python 3.14 is the supported production-development baseline: local development, production
CI, and the eventual deployed backend should use the same runtime family. The frozen
prototype keeps its historical 3.11–3.13 CI matrix and does not define the production
runtime.

## Setup

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
Deployment-specific HTTPS redirect, proxy-header, and HSTS policy is intentionally deferred
until the production ingress topology is selected and hardened under issue #54.

## Checks

Run the production scaffold checks with a running PostgreSQL service:

The planning validation domain has a database-free fast suite:

```bash
(cd backend && uv run python -m unittest discover -s planning/tests -v)
```

Run the complete checks with PostgreSQL available:

```bash
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend
uv run python -m compileall -q backend prototype
uv run python backend/manage.py check --settings=bardi.settings.development
uv run python backend/manage.py makemigrations --check --dry-run --settings=bardi.settings.test
uv run python backend/manage.py migrate --noinput --settings=bardi.settings.test
uv run python backend/manage.py migrate --check --settings=bardi.settings.test
(cd backend && uv run python manage.py test --settings=bardi.settings.test)
python -m unittest discover -s prototype/tests -v
```

Django test discovery intentionally runs without an app label **from the `backend/`
directory** so it discovers the current tests and automatically includes future production
apps. Procedure-Version tests require PostgreSQL: migrations install `btree_gist`, an
inclusive-range exclusion constraint, and lifecycle immutability triggers. Concurrency tests
must use separate database connections; SQLite is not a supported substitute. The prototype
commands are retained as frozen reference coverage and are intentionally not included in the
production Ruff or Mypy scope.

## Teardown

Stop the local service normally with:

```bash
docker compose down
```

To reset the local PostgreSQL database, use the destructive volume teardown. This
**deletes all local PostgreSQL data**:

```bash
docker compose down -v
```
