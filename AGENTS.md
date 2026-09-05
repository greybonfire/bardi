# Bardi

## Commands

Run from the repository root unless noted. Development requires Python 3.14+, `uv`, Docker Compose, and PostgreSQL; SQLite is not supported.

### Setup

```bash
cp .env.example .env
set -a
. ./.env
set +a
uv sync --locked --extra dev
docker compose up -d postgres
uv run python backend/manage.py migrate --settings=bardi.settings.development
```

Start the server:

```bash
uv run python backend/manage.py runserver --settings=bardi.settings.development
```

### Focused checks

```bash
# Planning domain, no database
(cd backend && uv run python -m unittest discover -s planning/tests -v)

# One planning test module
(cd backend && uv run python -m unittest planning.tests.test_evaluator -v)

# One Django test module; requires PostgreSQL and exported .env values
(cd backend && uv run python manage.py test api.tests.test_application --settings=bardi.settings.test)

# Frozen prototype reference suite
python -m unittest discover -s prototype/tests -v
```

### Full checks

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

See [`docs/development.md`](docs/development.md) for CI-equivalent checks, PostgreSQL details, and teardown.

## Read Before Editing

- Production contracts and architecture: [`docs/architecture/README.md`](docs/architecture/README.md)
- Accepted architectural decisions: [`docs/adr/README.md`](docs/adr/README.md)
- Domain vocabulary: [`CONTEXT.md`](CONTEXT.md)
- Frozen prototype policy: [`prototype/FROZEN.md`](prototype/FROZEN.md)

## Guardrails

- Keep `backend/planning/` framework-independent. Materialize a consistent snapshot at the application boundary; do not query Django ORM, databases, requests, networks, or files during evaluation.
- Do not import or extend `prototype/` for production work. Port proven behavior into production contracts and tests; do not copy prototype dataclasses into ORM models.
- Preserve exact Fact and rule semantics: omitted Facts are `UNKNOWN`; `null` and wrong types are invalid; add no implicit coercion.
- Version 1 planning is stateless for anonymous cases: never persist or log raw case Facts, traces, rule ASTs, or internal evidence rationale. Public responses must be explicitly projected.
- Keep published Procedure Versions immutable and administrative claims claim-level evidence-backed. Use knowledge/publication services rather than casual model-field edits.
- Use `Service` / `خدمة` in new production contracts. `Goal` is historical/prototype terminology.
