# ADR 0011: Keep the planning engine independent of Django ORM and request objects

**Status:** Accepted  
**Date:** 2026-09-01

## Context

The prototype proved that planning semantics are easiest to test and reason about as deterministic functions over a coherent knowledge snapshot, current Facts, locale, and evaluation date. Production needs Django/PostgreSQL for editing, publication, audit, and APIs, but embedding ORM queries inside rule evaluation would couple semantic behavior to persistence details, make historical reproduction harder, and force database setup into low-level tests.

## Decision

Django services load/assemble a validated immutable domain snapshot from persistence. The planning engine receives that snapshot and typed request inputs and evaluates it without ORM queries, Django model methods, HTTP request objects, or network access.

Django Ninja and Django Admin remain application/presentation boundaries around the domain engine; they do not own rule semantics.

The production evaluator is reimplemented from the authoritative contracts and acceptance scenarios. It does not import or wrap the frozen prototype package.

## Consequences

- Rule/evaluator tests run quickly without PostgreSQL.
- Persistence migrations can evolve without implicitly changing planning semantics.
- Snapshot loading becomes an explicit application responsibility and must be tested.
- Some mapping code exists between ORM records and domain representations, but that boundary is intentional.
- Historical contract implementations can remain available independently of the current ORM model API.
