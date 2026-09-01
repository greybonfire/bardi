# bardi

Bardi is transitioning from a completed research prototype to a production implementation.

## Production design

The authoritative production design starts at [`docs/architecture/README.md`](docs/architecture/README.md). Accepted architectural decisions are recorded in [`docs/adr/`](docs/adr/).

Production will be a Django/PostgreSQL modular monolith with a small Django Ninja application interface and a separate Next.js web application. The planning engine remains a pure domain component behind the Django application layer.

## Frozen prototype

The framework-independent prototype under [`prototype/`](prototype/) is frozen as an executable reference. It must not be imported into production code or extended as the production implementation. See [`prototype/FROZEN.md`](prototype/FROZEN.md) and [`docs/prototype-capability-report.md`](docs/prototype-capability-report.md).

Run the frozen reference suite from the repository root with:

```bash
python -m unittest discover -s prototype/tests -v
```
