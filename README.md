# bardi

Bardi is the production implementation of a sourced, bilingual planning system for Egyptian
administrative services.

## Production applications

- [`backend/`](backend/): Django/PostgreSQL authored knowledge, Admin review/publication,
  and a stateless planning API. Development uses Python 3.14 and uv.
- [`frontend/`](frontend/README.md): the Next.js web app, with Arabic by default, an English
  switch, a backend-driven questionnaire and printable, sourced guidance. Use Node 22 and
  npm with the committed lockfile.

- **Run and check locally:** [development guide](docs/development.md), starting with
  [full-stack Compose](docs/development.md#full-stack-docker-compose-setup) or host-run setup.
  It includes prerequisites, Admin creation, complete checks and safe shutdown.
- **Author and publish:** [editorial workflow](docs/editorial-process.md). Publication is
  mode-aware: `solo` skips general approvals; `independent` requires them. Flagged high-risk
  content requires independent specialists in both modes.
- **Configure the web app safely:** [frontend guide](frontend/README.md) for API origins,
  case privacy, shared-device handling and deployment-security caveats.
- **Understand delivery gates:** [CI/CD](docs/ci-cd.md) for the required verification tracks.
  There is no production deployment automation for Django or Next.js.
- **Operate or recover a private pilot:** [operations guide](docs/operations/private-pilot.md)
  for ingress hardening, backups and restore procedures.

Services come from authored backend knowledge, never a bundled demo fallback. Empty or
unavailable services are shown honestly; Service activation and publication are explicit.

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
