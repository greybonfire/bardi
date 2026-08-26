# Store typed claims relationally and rules as validated JSON

Procedure Versions own relational records for checklist items, steps, fees, warnings, dependencies, Evidence Links, and Service Point associations; the complete procedure is not an opaque JSON document. Preserved Sources are reusable records. Evidence-bearing Procedure Version claims connect to those Sources through Evidence Links so provenance remains claim-specific without duplicating the Source itself.

Evidence Discrepancies are also persisted, but only as lightweight internal/admin records. A discrepancy links the relevant claim and evidence, records a small status vocabulary, concise research rationale, and an optional resolution. It exists to preserve editorial reasoning around conflicting, stale, or wrong-applicability evidence; it is not a public-plan object and should not grow into a generalized evidence graph in version 1.

Persistence does not dictate presentation. The database may retain fine-grained Sources, Evidence Links, and internal discrepancy records while the public interface groups citations, exposes compact verification information, or reveals sources on demand. Internal discrepancy rationale is not returned as public guidance.

Each Applicability Rule is a versioned, schema-validated JSONB AST rather than normalized rule-node rows or executable text. Editors change a published version by cloning its coherent records into a draft and publishing the reviewed replacement atomically. This preserves identity, provenance, admin usability, and future flexibility without turning the small nested rules language into a large relational model.
