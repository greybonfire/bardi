# Missing-Fact Picker compatibility follow-ups

The shared-policy refactor preserves behavior from baseline `a471ebc`. These observations are
recorded separately rather than normalized during consolidation. Malformed detached snapshots
and prepared handoffs used by the tests are not evidence that such knowledge can pass production
snapshot loading or publication gates.

## Definition handling differs before and after Procedure selection

| Input | Procedure-selection picker | Later-phase picker |
| --- | --- | --- |
| Missing consequential Fact definition | Treat the key as a source Fact, then check coverage | `unknown_fact:<key>` |
| Missing definition for a prepared source dependency | Permit it as a source, then check coverage | `missing_source_dependencies:<derived-key>` |
| Missing/empty dependency set or a dependency defined as derived | Dependency defect | Dependency defect |

Expansion defects are returned before coverage defects. Required source coverage is checked in
full before ranking any Question; a covered Question does not excuse another uncovered source.
The two named picking routes preserve these differences inside one implementation. The caller's
later-phase diagnostic prefix remains an unrestricted string, not a policy selector.

Any future alignment needs a deliberate compatibility decision for direct selector/picker
callers, plus verification of production reachability. It must not silently change diagnostics
as part of a cleanup.

## Empty source sets retain different failure modes

After expansion and coverage succeed, an empty covering set produces the native `min()`
`ValueError` on the selection route, while the later picker returns
`<diagnostic-prefix>:no_source_fact`.

The selector characterization deliberately supplies a mocked UNKNOWN evaluation with no missing
Facts; this is not a valid-rule evaluator outcome. The new selection-policy function also pins
its empty-input behavior directly. Existing phase guards and inconclusive fallbacks remain
unchanged; no new Question behavior is authorized for non-actionable UNKNOWNs.

Selection still filters covering Questions while `min()` consumes its generator; later picking
finishes tuple construction before comparing priorities. This consumption order is preserved,
not optimized or normalized during extraction.

## Picking does not validate the winner's complete answer mapping

Both direct pickers, and `select_procedure`, can return an authored Question with an invalid
additional answer key. Only `question_result` validates the complete selected mapping for the
public response. It does not skip a defective winner for a valid runner-up, nor inspect a
runner-up's answer definitions. Existing operation tests pin both cases before and after
Procedure selection.

Projection preserves authored answer order and duplicates and does not inspect `primary_fact_key`.
Direct projection of an empty answer tuple remains possible; that does not establish that an
empty-answer Question is selectable or publishable. Answer metadata construction still precedes
the missing/derived-key rejection. Stronger validation or changed exception timing would be a
separate hardening decision, not part of this behavior-preserving refactor.

`planning.tests.test_questions` and the new characterizations in `planning.tests.test_operation`
pin definition/coverage distinctions, empty-set outcomes, winner validation, and authored answer
projection. Consumption and metadata-construction ordering were also checked by source review.
Production gate, trust, and researched-case coverage remain separate integration checks.
