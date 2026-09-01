# ADR 0009: Separate Eligibility Basis reachability from qualification

**Status:** Accepted  
**Date:** 2026-09-01

## Context

The prototype initially represented an Eligibility Basis with one flat predicate. During the military family-exemption pressure test, this allowed an obviously unreachable branch to keep asking downstream qualification Questions: after the applicant stated that the father was not alive, the interview could still ask whether the father was unable to earn.

Adding independent Question-visibility predicates would duplicate business logic and make future drift likely.

## Decision

Every Eligibility Basis has two semantic rule stages:

- **reachability (`applicability`)**: whether this Basis remains relevant enough to investigate;
- **qualification**: whether a reachable case matches the Basis.

Qualification is required. Reachability may be omitted, meaning always reachable.

The evaluator must stop qualification from contributing missing Facts when reachability is FALSE. When reachability is UNKNOWN, only reachability Facts may drive Questions. Qualification is evaluated for Missing-Fact purposes only after reachability is TRUE.

Question records remain Fact-to-wording mappings; they do not duplicate Basis reachability rules.

## Consequences

- A Fact used only by an unreachable Basis cannot become a user Question.
- Basis traces and editorial diagnostics can distinguish "unreachable" from "reachable but not qualified."
- Publication validation can verify Question coverage separately for reachability and qualification Facts.
- Existing/simple Bases with no separate prerequisite put their complete rule in qualification and use no reachability gate.
- The model may contain asymmetrical Bases when research supports only asymmetrical semantics; we do not invent qualification branches merely for schema symmetry.
