# Evidence projection follow-ups

The projection extraction preserves the behavior at baseline `abc7777`. These compatibility
observations are recorded separately rather than corrected or normalized during the refactor.
They are not new policy decisions or evidence that ordinary editorial workflows are broken.

## Calendar cutoff versus verification establishment

History admission uses PostgreSQL's `occurred_at__date` under Django's active timezone.
Verification establishment uses the loaded timestamp's `.date()`. With an active timezone west
of UTC, an event just after midnight UTC can therefore be admitted for the preceding evaluation
date while establishing verification on the following UTC date. Planning's existing trust
assessment still treats future verification as inconclusive; projection does not change it.

This is pinned for both history kinds by
`EvidenceWorkflowTests.test_active_timezone_cutoff_differs_from_timestamp_date_establishment`.
A future normalization would need an explicit calendar/timezone policy decision, not a mechanical
replacement of the SQL cutoff with Python filtering.

## Later review replaces the previous review's verification date

Each review establishes `max(verified_on, occurred_at.date())` and assigns it to the owner's
overlay. It does not retain a running maximum across reviews. A later review can therefore lower
an earlier review's future verification date. Final claim rewriting still takes the maximum of
the authored date and the final overlay date. A reviewed `reverify_on=None` explicitly clears
the deadline, while no review preserves it.

The persisted same-timestamp/primary-key characterization and pure date tests preserve these
results. Any change to date accumulation must be evaluated separately for historical behavior.

## Malformed open-transition trust states

Replay expects an open discrepancy to have `disputed`, `needs_reverification`, or `unknown`
trust. If all still-open transitions for an owner instead contain unsupported open states,
precedence selection raises `StopIteration`, including for owners absent from the supplied
snapshot. The extraction preserves that failure rather than inventing a new diagnostic or
ignoring unmatched owners.

Pure tests characterize malformed input directly. They do not establish that normal editorial
writes create such history. A future hardening change should first establish the reachable
persistence cases and explicitly choose its diagnostic compatibility policy.
