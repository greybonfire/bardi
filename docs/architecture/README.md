# Production architecture authority

**Status:** Authoritative  
**Effective:** 2026-09-01

This directory defines the production contract derived from the completed Bardi research prototype. Production implementation work should be reviewed against these documents rather than against prototype class shapes.

## Authority order

When repository material conflicts, use this order:

1. **Accepted ADRs** in `docs/adr/` control explicit architectural decisions and their rationale.
2. **Authoritative production design documents** in this directory define the current intended system contract.
3. `CONTEXT.md` provides shared domain vocabulary; it should be kept consistent with the authoritative documents but is not a substitute for them.
4. `docs/prototype-capability-report.md`, evidence packs, and the retired prototype preserved in Git history are supporting research evidence.
5. Issue and PR discussion is historical context unless its decision has been promoted into an ADR or authoritative design document.

An ADR may intentionally supersede an older ADR. The newer ADR must say so explicitly.

## Authoritative documents

- [`production-backend.md`](production-backend.md) — system boundaries, application layers, persistence strategy, privacy constraints, testing strategy, and initial infrastructure constraints.
- [`domain-model.md`](domain-model.md) — stable identities, version-owned content, ownership rules, evidence/trust concepts, and persistence boundaries.
- [`rules-contract.md`](rules-contract.md) — typed Facts, rules AST, three-valued semantics, Procedure/Basis evaluation, Missing-Fact behavior, diagnostics, and public result families.
- [`knowledge-publication.md`](knowledge-publication.md) — draft/review/publish lifecycle, immutable Procedure Versions, evidence gates, trust/freshness, review requirements, and withdrawal/re-verification behavior.

## Change process

A production change that alters one of these contracts must do one of the following:

- update the relevant authoritative document when it clarifies or extends an already accepted decision; or
- add/supersede an ADR when it changes an architectural choice, ownership boundary, persistence strategy, safety invariant, or externally observable planning behavior.

Implementation PRs should not silently redefine domain concepts through ORM convenience, API serialization, UI behavior, or migration shape.

## Prototype relationship

The research prototype was retired from `main` after production parity became authoritative.
Its final executable state is preserved in Git history at commit
`95128e22767edf8ffb9f3db838178b327b079aa0`. Production contracts, production acceptance
tests, and reviewed production data are authoritative; historical prototype class shapes and
implementation details are not.
