# ADR 0010: Separate Service Point identity, material version, and Procedure association

**Status:** Accepted  
**Date:** 2026-09-01

## Context

A government office has a stable identity, but addresses, availability, and operational details can change over time. In addition, whether a person may use that office is often specific to the Procedure and the person's circumstances. Putting jurisdiction rules directly on the office would incorrectly reuse one Procedure's routing semantics for another.

## Decision

Model Service Point routing in three layers:

1. **Service Point** — stable physical/digital destination identity;
2. **Service Point Version** — time-bounded material details such as address and availability;
3. **Procedure–Service Point Association** — Procedure-Version-owned routing/jurisdiction relation with its own rule, evidence, trust, and effective interval.

Routing evaluates all applicable associations. The planner may return multiple Service Points and must not infer a nearest/best office without an explicit supported decision rule.

## Consequences

- One office can participate in many Procedures with different conditions.
- Address/availability corrections do not rewrite stable Service Point identity.
- Historical routing remains auditable by date.
- Unresolved routing remains local to the routing portion of a plan.
- The schema uses more records than a flat office table, but avoids conflating destination identity with Procedure-specific administrative rules.
