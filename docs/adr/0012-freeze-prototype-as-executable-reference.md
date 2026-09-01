# ADR 0012: Freeze the prototype as an executable reference

**Status:** Accepted  
**Date:** 2026-09-01

## Context

Issue #1 and the follow-up prototype issues completed the intended pressure test across passport renewal, National ID renewal, and military family exemption. Continuing to add production concerns to the framework-independent prototype would blur the boundary between experimental code and architecture intended to live for years.

At the same time, deleting the prototype would discard useful executable evidence while production parity is being established.

## Decision

Freeze `prototype/` after the completed research phase. Retain it, its fixtures, and its acceptance tests as an executable specification during production migration.

Production code must not import prototype modules or treat prototype dataclasses as ORM design requirements. New product features and Procedure expansion happen only in production work.

Prototype changes after freeze are exceptional and limited to reproducibility/toolchain repair or explicit semantic corrections accompanied by an architecture/ADR update.

## Consequences

- The production implementation starts from validated concepts rather than experimental class shapes.
- The prototype remains available for semantic comparison and migration of researched fixtures.
- Duplicate production implementations of some logic are intentional during the transition; production becomes authoritative once parity coverage exists.
- A later decision may remove frozen prototype tests from default CI after production acceptance tests fully replace their role.
