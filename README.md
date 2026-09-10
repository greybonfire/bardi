# bardi

Bardi is the production implementation of a sourced, bilingual planning system for Egyptian
administrative services.

## Production backend

The Django/PostgreSQL backend provides environment-specific settings, Django Admin/authentication,
deterministic planning, publication/review workflows, Django Ninja APIs, reproducible uv tooling,
and PostgreSQL-backed checks. See [`docs/development.md`](docs/development.md) for local setup
and validation.

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

The retained [prototype capability report](docs/prototype-capability-report.md), evidence packs,
and historical ADRs document what the research phase proved and what remained unsupported.
See [ADR 0018](docs/adr/0018-retire-research-prototype.md) for the retirement decision.
