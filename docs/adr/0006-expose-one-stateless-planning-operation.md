# Expose one stateless planning operation

The public `/v1` application interface exposes one operation that advances a Goal from the caller's current Facts and locale. A Goal supplies the curated organizational set of related candidate Procedures; the planning operation resolves the applicable Procedure from that set and returns a discriminated result: the next Question, a Personalized Plan, an inconclusive result, or invalid-input diagnostics.

Rule ASTs, authoring structures, full Evidence Links, and Evidence Discrepancy records remain behind the Django module. Clients receive stable identifiers, user-appropriate reasons, rendered claims, and only the compact source or verification metadata required by the product experience. Public presentation may aggregate or progressively disclose evidence and does not mirror the relational provenance model. Internal discrepancy rationale is never part of the public planning contract.

The Next.js client retains in-progress Facts in tab-scoped storage and resubmits them rather than creating a persisted server Case.
