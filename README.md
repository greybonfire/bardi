# bardi

Bardi is the production implementation of a sourced, bilingual planning system for Egyptian
administrative services.

## Production applications

- [`backend/`](backend/): Django/PostgreSQL authored knowledge, Admin review/publication,
  and a stateless planning API. Development uses Python 3.14 and uv.
- [`frontend/`](frontend/README.md): the Next.js web app, with Arabic by default, an English
  switch, a backend-driven questionnaire and printable, sourced guidance. Use Node 22 and
  npm with the committed lockfile.

The Django/PostgreSQL backend provides environment-specific settings, Django Admin/authentication,
deterministic planning, publication/review workflows, Django Ninja APIs, reproducible uv tooling,
and PostgreSQL-backed checks. See [`docs/development.md`](docs/development.md) for local setup
and validation. Editors should use [`docs/editorial-process.md`](docs/editorial-process.md) for the
end-to-end authoring, review, publication, and programmatic-import workflow.

Start PostgreSQL and run Django at `http://localhost:8000` in a separate terminal using
[`docs/development.md`](docs/development.md). Then, from the repository root:

```bash
cp frontend/.env.example frontend/.env.local
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open **http://localhost:3000/ar**; **English** switches to `/en`. Services come from the
backend, never a bundled demo fallback. Import authored knowledge, complete independent
Admin review and publish it through the normal workflow; empty or unavailable services
are shown honestly. See [`frontend/README.md`](frontend/README.md) for configuration,
case privacy, schema generation, unit/browser tests and deployment-security caveats.
[`docs/ci-cd.md`](docs/ci-cd.md) describes the two independent CI tracks. There is no
production deployment automation for Django or Next.js.

## Production design

The authoritative production design starts at
[`docs/architecture/README.md`](docs/architecture/README.md). Accepted architectural decisions
are recorded in [`docs/adr/`](docs/adr/).

The production architecture uses a Django/PostgreSQL modular monolith with a small Django Ninja
application interface and a separate Next.js web application. The planning engine remains a pure domain
component behind the Django application layer. The public API contract is documented in
[`docs/api/v1.md`](docs/api/v1.md).

## Research history

The framework-independent research prototype completed its pressure-test role and was retired
from `main` after production parity was established. The final `main` commit containing the
complete executable prototype is `95128e22767edf8ffb9f3db838178b327b079aa0`; Git history is
the canonical archive.

The retained [prototype capability report](docs/prototype-capability-report.md),
[evidence packs](docs/evidence-packs/README.md),
and historical ADRs document what the research phase proved and what remained unsupported.
See [ADR 0018](docs/adr/0018-retire-research-prototype.md) for the retirement decision.
