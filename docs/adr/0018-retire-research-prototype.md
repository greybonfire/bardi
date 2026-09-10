# ADR 0018: Retire the executable research prototype

**Status:** Accepted  
**Date:** 2026-09-11  
**Supersedes:** ADR 0012

## Context

ADR 0012 froze the framework-independent prototype as an executable reference while production
parity was being established. That transition is complete.

The production stack now carries the researched behavior through authoritative architecture
contracts, deterministic production importers, publication/review gates, PostgreSQL-backed
planning snapshots, the pure production planning domain, and the public Django Ninja API.
Cross-family production acceptance covers passport renewal, National ID renewal, and temporary
family exemption without importing or executing prototype modules.

Keeping the prototype executable on `main` would preserve a second implementation, require a
separate Python 3.11–3.13 CI matrix and prototype-only release workflow, and create an ongoing
maintenance surface after production has become authoritative.

## Decision

Retire the executable `prototype/` tree from `main`.

Production contracts, production tests, reviewed production data, and current evidence packs are
the living authority. The prototype is historical research evidence only.

The final `main` commit containing the complete executable prototype is
`95128e22767edf8ffb9f3db838178b327b079aa0`. Git history is the canonical archive. The
prototype capability report and historical ADR/evidence-pack references remain in the repository
as provenance; historical paths in those documents refer to that archived revision.

Remove prototype-specific CI, compilation, release automation, and operational instructions.
Do not migrate prototype-only helpers, compatibility aliases, fixtures, traces, or abstractions
into production merely to preserve them.

## Consequences

- `main` has one living implementation: the production Django/PostgreSQL application and pure
  planning domain.
- Production acceptance tests are authoritative for supported behavior.
- The Python 3.11–3.13 prototype CI matrix and prototype-only release workflow are removed.
- Historical prototype behavior remains inspectable through Git history and retained research
  documentation.
- Future behavior changes are made and reviewed only through production contracts, data, and
  tests.
- Reintroducing an executable prototype would require a new explicit architectural decision.
