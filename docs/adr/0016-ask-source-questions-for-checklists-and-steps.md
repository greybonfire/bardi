# ADR 0016: Ask source Questions for checklist and step applicability

**Status:** Accepted  
**Date:** 2026-09-08

## Context

ADR 0015 establishes consequential source Questions after version selection. Official checklist
requirements and steps still stop at UNKNOWN applicability even when a Service Question can
resolve it. Some UNKNOWN items also lack usable evidence; asking a user cannot repair that.

## Decision

Extend ADR 0015's question and configuration-defect policy to official checklist requirements
and all supported steps. Preserve phase order: checklist, then steps, then fees. Within a phase,
use the existing picker, priority/semantic-id ordering, source-dependency expansion and single
stateless `next_question` response. Fully supplied source Facts are not asked again.

Apply existing date and basis scopes first. FALSE items remain excluded before trust checks.
For UNKNOWN items, collect askable missing Facts only when both item trust and the existing
supporting-source policy permit assertion. A current checklist requirement still needs official
support; steps retain their existing source policy. UNKNOWN practical preparation remains omitted
without questions or blocking.

Keep blocked applicability separate from askable missing Facts. Ask usable consequential questions
first within that phase; if none remain, blocked UNKNOWN applicability retains
`checklist_applicability_unknown` or `step_applicability_unknown`. UNKNOWN with no actionable Facts
also retains that reason. Do not drop an uncertain official item and return an apparently complete
plan. Once applicability is TRUE, the existing local trust/inconclusive-section behavior applies.
User answers never promote evidence trust. TRUE/FALSE projection and optional preparation behavior
are otherwise unchanged. Fee and routing questioning are not extended here.

The mandatory core applicability publication gate structurally covers version applicability,
official checklist predicates and step predicates in procedure/basis scopes. It expands derived
references to pinned source dependencies and validates every Question answer key. Coverage includes
future and non-current material regardless of today's runtime trust/date/basis filtering. Optional
preparation and unsupported scopes are not added to this coverage requirement. Existing validity
and ownership gates remain in force. No bypass setting or lock-order change is introduced.

## Compatibility and consequences

As in ADR 0015, this corrects application progression for existing `v1` versions, including
historical evaluations, without changing evaluator/derivation semantics or published rows.
Incomplete responses may change to `next_question`; missing required coverage fails closed.
ADR 0001's pinned rule meanings and ADR 0003's immutability remain in force.

The passport importer changes only `passport.student.unknown` to expect `q.is_student`; existing
bilingual questions already cover the new predicates. Its exact pre-Question and pre-routing
scenario seals remain accepted. After all other integrity checks, draft imports upgrade the student
expectation and, for pre-routing imports, the existing three routing expectations in one transaction.
Published/withdrawn scenarios remain read-only historical records. Model saves preserve review
invalidation; arbitrary drift is rejected. No schema migration is required.

Unconditionally asking about every UNKNOWN item was rejected because it confuses user facts with
research uncertainty. Silently discarding blocked UNKNOWN items was rejected because it can make
an incomplete plan appear complete.
