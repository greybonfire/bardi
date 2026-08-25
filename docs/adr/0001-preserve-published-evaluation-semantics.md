# Preserve published evaluation semantics

Published Procedure Versions pin a rules-contract version, and published Fact keys never change meaning, type, or allowed values. When evaluator or derivation semantics change, compatible contract implementations remain available; when Fact semantics change, future Procedure Versions use a new key. This costs ongoing compatibility maintenance but prevents software releases from silently changing historical evaluations.
