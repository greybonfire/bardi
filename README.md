# bardi

Bardi is transitioning from a completed research prototype to a production implementation.

## Production applications

- [`backend/`](backend/): Django/PostgreSQL authored knowledge, Admin review/publication,
  and a stateless planning API. Development uses Python 3.14 and uv.
- [`frontend/`](frontend/README.md): the Next.js web app, with Arabic by default, an English
  switch, a backend-driven questionnaire and printable, sourced guidance. Use Node 22 and
  npm with the committed lockfile.

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
[`docs/ci-cd.md`](docs/ci-cd.md) describes the three independent CI tracks. There is no
production deployment automation for Django or Next.js.

## Production design

The authoritative production design starts at [`docs/architecture/README.md`](docs/architecture/README.md). Accepted architectural decisions are recorded in [`docs/adr/`](docs/adr/).

Production uses a Django/PostgreSQL modular monolith with a small Django Ninja application interface and a separate Next.js web application. The planning engine remains a pure domain component behind the Django application layer. The first public endpoint contract is documented in [`docs/api/v1.md`](docs/api/v1.md).

## Frozen prototype

The framework-independent prototype under [`prototype/`](prototype/) is frozen as an executable reference. It must not be imported into production code or extended as the production implementation. See [`prototype/FROZEN.md`](prototype/FROZEN.md) and [`docs/prototype-capability-report.md`](docs/prototype-capability-report.md).

Run the frozen reference suite from the repository root with:

```bash
python -m unittest discover -s prototype/tests -v
```
