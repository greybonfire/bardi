# ADR 0017: Ask source Questions for Fee applicability

**Status:** Accepted

**Date:** 2026-09-09

## Context

ADRs 0015 and 0016 establish consequential source Questions for Procedure Version,
checklist, and step applicability. Trusted Fees still stopped with
`fee_applicability_unknown` when an authored Service Question could resolve an UNKNOWN
applicability predicate. Fee applicability and confidence in the monetary value are separate:
a user answer cannot repair missing, stale, disputed, or otherwise unavailable fee evidence.

## Decision

Extend the shared consequential-Question policy to the Fee phase, after checklist and steps and
before warnings and plan assembly. Apply the existing date, procedure/Eligibility-Basis scope,
matched-Basis, and `context_only` filters first. An UNKNOWN Fee predicate contributes its
consequential missing Facts only when item trust is `assert_current`. Unlike checklist and step
policy, no known/range value state or usable supporting-evidence prerequisite applies. A trusted
Fee with an authored unknown or unverified value, or a known/range value whose current support is
unavailable, can therefore ask a source Question about applicability.

The shared picker expands derived Facts through `prepared_facts.missing_source_dependencies`,
chooses one Question deterministically by priority then semantic identifier, supports partially
answered multi-Fact Questions, and never asks a derived Fact directly. Unknown Facts, unsupported
or missing source dependencies, invalid Question answer keys, and absent same-Service coverage
return the existing sanitized `invalid` / `knowledge_configuration_invalid` response. Once
askable Facts are exhausted, an UNKNOWN trusted predicate with no actionable Facts retains
`fee_applicability_unknown`. The operation remains stateless and returns one `next_question`.

Publication's mandatory `ApplicabilityGate` structurally requires same-Service source-Question
coverage for every non-empty Fee applicability predicate in procedure and Eligibility-Basis
scope. Coverage includes future-dated, inactive-at-present, and non-current-trust Fees; it does
not depend on runtime date, Basis matching, freshness, evidence, or amount state. Derived
references expand to source dependencies, and every answer key of every multi-Fact Question must
exist and be non-derived. This gate cannot be bypassed by selection-question settings and uses
the existing publication transaction, aggregate locks, and lock order.

Answers resolve applicability only. They do not promote item or evidence trust, recover or assert
an unavailable amount, resolve an Evidence Discrepancy, or alter fee calculation. In particular,
the #110/#113 fallback remains unchanged: unavailable current support for an applicable
known/range Fee yields `unverified`, null amount/range fields, `current_value_unknown=True`, and
preserved claim-source and unknown-freshness history. Authored unknown/unverified values never
become guessed current amounts.

## Compatibility and consequences

This extends ADRs 0015 and 0016 without superseding ADR 0001's pinned rules-contract semantics or
ADR 0003's publication immutability. Existing `v1` and historical evaluations use the corrected
application progression: an incomplete response may move from `fee_applicability_unknown` to
`next_question`, but Fact meanings, derivations, TRUE/FALSE evaluation, predicates, monetary
fields/calculation, trust decisions, and immutable published or withdrawn rows do not change.
Pinned implementations remain available exactly as before.

Published knowledge is never rewritten to gain coverage. Existing published versions without an
actionable Question fail closed when the missing Fact becomes consequential; future publication
must satisfy structural coverage. Import compatibility accepts and atomically upgrades only exact
known prior draft scenario seals through normal saves, invalidating prior review approvals, while
exact finalized historical seals remain unchanged and arbitrary or partial drift is rejected.

Requiring current supporting evidence before asking was rejected because it would conflate factual
applicability with monetary certainty and weaken the local unknown-value fallback. Asking for
non-current or context-only Fees was rejected because user answers cannot repair research trust.
