# ADR 0013: Author planning Questions at Goal level

**Status:** Accepted  
**Date:** 2026-09-01

## Context

The planner can require a missing Fact before a concrete Procedure has been selected. For example, a broad passport Goal may need to ask whether the person has an existing passport in order to choose renewal versus first issuance/replacement. A Question owned exclusively by a Procedure Version is therefore unavailable at exactly the point where Procedure selection may need it.

The prototype's cross-fixture selector successfully used Goal-scoped Questions and deterministic Fact coverage.

## Decision

Author planning Questions under the Goal. A Question provides bilingual wording, stable priority, and the source Fact key(s) it resolves. The Missing-Fact Picker chooses Questions only when their Fact is consequential to Procedure selection or the selected Procedure Version's current evaluation.

Procedure Versions reference Facts through rules; they do not own duplicate Question text for each version. Question wording is not itself an administrative assertion and may be improved without creating a new Procedure Version as long as the Fact semantics and answer mapping do not change.

Business-rule visibility remains in Procedure/Basis predicates, not in separate Question applicability scripts.

## Consequences

- Questions are available both before and after Procedure selection.
- One Goal can reuse consistent wording for a Fact across related Procedures.
- Publication/knowledge validation must verify Goal Question coverage for consequential source Facts used by candidate Procedure selectors and Procedure-Version/Basis rules.
- Changing a Fact's meaning or answer mapping is a semantic contract change and requires a new Fact key/contract treatment; changing plain-language wording alone is not.
