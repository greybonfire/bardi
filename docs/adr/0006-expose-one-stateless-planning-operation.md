# Expose one stateless planning operation

The public `/v1` application interface exposes one operation that advances a Goal from the caller's current Facts and locale. It returns a discriminated result: the next Question, a Personalized Plan, an inconclusive result, or invalid-input diagnostics. Rule ASTs and authoring structures remain behind the Django module; clients receive stable identifiers, user-appropriate traces, and rendered claims only. The Next.js client retains in-progress Facts in tab-scoped storage and resubmits them rather than creating a persisted server Case.
