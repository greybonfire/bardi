# Frozen prototype

**Status:** Frozen  
**Freeze date:** 2026-09-01  
**Final semantic milestone:** Issue #1 completed; PR #28 merged  
**PR #28 merge commit:** `caecbdc58e6908014c98f85a3620b6628d1a24e1`

The `prototype/` directory is no longer an implementation target. It is retained as an executable record of the research phase and as a behavioral reference while production code is built.

## What the freeze means

- Do not add new product features, Procedures, rule operators, persistence, APIs, framework integrations, or production infrastructure to the prototype.
- Do not import `prototype.bardi_prototype` from production Django code.
- Do not mechanically translate prototype dataclasses into Django models. Production persistence follows the authoritative architecture documents and ADRs.
- Keep the reference tests runnable while production parity is being established.
- Port proven behavior into production through production contracts and acceptance tests rather than by wrapping or subclassing prototype code.

The prototype capability report at `docs/prototype-capability-report.md` records what the pressure test actually proved and which assumptions remained unsupported.

## Allowed changes after freeze

A prototype change is exceptional. It is allowed only when necessary to:

1. repair test/toolchain compatibility so the frozen reference remains executable;
2. correct a demonstrable defect in the frozen reference that would otherwise misstate the intended production contract; or
3. preserve reproducibility after a repository-wide infrastructure change.

Any semantic correction must be explicit in the PR, must update the relevant authoritative design document or ADR, and must explain whether production behavior changes. Prototype changes must never be used as a shortcut around production design review.

## Relationship to production

Production code may reuse concepts, identifiers, fixtures as migration inputs, and acceptance scenarios. It must not depend on prototype modules at runtime.

During the transition, the prototype suite acts as an executable specification for proven behavior. Once equivalent production acceptance coverage exists, production tests become authoritative and the frozen suite may be moved out of the default CI path by a separate decision.
