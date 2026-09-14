# Editorial process

**Status:** Operational guide  
**Audience:** Researchers, editors, reviewers, specialists, publishers, and developers supporting editorial imports

This guide explains how researched administrative guidance moves from source material to a
published Bardi Procedure Version. It covers both normal staff editing through Django Admin and
the supported programmatic importer pattern.

The production architecture and ADRs remain authoritative if this guide ever conflicts with them.
Start with [the production architecture authority](architecture/README.md), especially
[the domain model](architecture/domain-model.md),
[knowledge publication](architecture/knowledge-publication.md),
[review roles](architecture/procedure-version-review-roles.md), and
[the Admin lifecycle](architecture/django-admin-lifecycle.md).

## 1. The editorial mental model

Bardi separates stable catalog identities from versioned guidance.

- A **Service** is the broad user-entry grouping, such as a family of related passport
  procedures. It owns Service-level Questions, Procedure candidates, and contradictions.
- A **Procedure** is one concrete administrative transaction. It belongs to one primary Service.
- A **Procedure Version** is the editable/publishable semantic snapshot. Requirements, steps,
  fees, warnings, Eligibility Bases, dependencies, and routing associations belong here.
- A **Fact Definition** is a stable typed vocabulary entry. Facts are reused across Services when
  they mean the same thing.
- A **Service Question** is Service-scoped wording used to obtain one or more source Facts.
  Questions are not business rules.
- **Authorities, Sources, Document Types, and Service Points** are reusable identities/provenance.
- **Evidence Links** connect individual claims or routing material to the Sources that support
  them.
- **Planning Scenarios** are executable editorial acceptance cases for a Procedure Version.
- A **Review Policy** names the accountable author and declares any high-risk specialist review
  that publication requires.

The most important lifecycle rule is:

```text
research -> draft -> independent review -> publish -> immutable
                                      |
                                      +-> publication rejected -> edit draft -> review again
```

After publication, meaning-changing edits never reopen the published row:

```text
published version -> clone to successor draft -> edit/review -> publish successor
```

Withdrawal is also not deletion. A withdrawn version remains immutable and auditable.

## 2. Roles and permissions

A small team can give one person several operational roles, but Bardi preserves independence
where publication safety requires it.

| Role | Typical responsibility | Important permission/capability |
| --- | --- | --- |
| Researcher/editor | Build and edit drafts | ordinary Django add/change permissions |
| Accountable author | Own the coherent draft presented for review | named in the Procedure Version Review Policy |
| General reviewer | Review evidence, rules, scenarios, bilingual meaning, discrepancies | `knowledge.review_procedureversion` |
| Specialist reviewer | Approve configured high-risk material | matching `knowledge.specialist_approve_*` permission |
| Publisher | Make a reviewed draft public | `knowledge.publish_procedureversion` |
| Withdrawer | Remove a published version from normal future selection | `knowledge.withdraw_procedureversion` |
| Evidence reverifier | Record semantic-preserving evidence re-verification | `knowledge.add_evidencereverificationevent` |

The accountable author cannot satisfy an independent review or specialist approval for their own
draft. The eventual publisher also cannot satisfy the independent approvals used to publish that
draft. One eligible reviewer may approve several ordinary dimensions.

## 3. Before entering data

Do the research first. Editorial data entry should transcribe an evidence-backed understanding,
not become the place where unsupported assumptions are invented.

For a new Procedure, prepare at least:

1. the Service and concrete Procedure identity;
2. source Facts needed to select or personalize it;
3. bilingual Questions for consequential source Facts;
4. version applicability and effective dates;
5. checklist requirements, preparation items, steps, fees, warnings, Eligibility Bases,
   dependencies, and routing that are actually supported;
6. Sources and Authorities for material administrative claims;
7. explicit unknown or `needs_reverification` states where research is incomplete;
8. named scenarios covering the meaningful positive, negative, UNKNOWN, contradictory, and edge
   behavior for that Procedure; and
9. the accountable author and any legal, military, custody/guardianship, or contested-identity
   specialist risks.

Stable semantic IDs are part of the editorial contract. Prefer readable IDs that identify the
concept rather than database row numbers or temporary research labels.

Never use a new Fact key merely because a different Service asks the same underlying question.
Reuse the existing Fact Definition when the meaning and type are genuinely the same.

## 4. Manual workflow through Django Admin

### 4.1 Start the local Admin

With the development environment configured:

```bash
cp .env.example .env
set -a
. ./.env
set +a
uv sync --locked --extra dev
docker compose up -d postgres
uv run python backend/manage.py migrate --settings=bardi.settings.development
uv run python backend/manage.py runserver --settings=bardi.settings.development
```

Open `http://localhost:8000/admin/` and sign in with a staff account that has the permissions
needed for your role.

### 4.2 Create or reuse stable vocabulary and provenance

Before building version-owned guidance, create or locate reusable records where appropriate:

- **Fact Definitions** for typed source or derived Facts;
- **Authorities** for government bodies or other source publishers;
- **Sources** for preserved source material;
- **Document Types** for reusable document identities; and
- **Service Points** plus **Service Point Versions** for physical or digital destinations.

Do not casually edit a Source, Authority, Document Type, Service Point, or other shared identity
after it has become part of published or withdrawn history. Admin intentionally makes preserved
material read-only. If a newly retrieved source materially differs from a preserved source,
normally create a new Source record rather than rewriting history.

Derived Facts require deterministic production code. Editors should not invent new derived-Fact
semantics purely through Admin.

### 4.3 Create the Service

Create the stable **Service** first. Give it its semantic ID and bilingual public text.

The Service Admin also exposes:

- **Procedure candidates**, each with its Service-level selection predicate;
- **Questions**, including the Fact they primarily resolve, priority, and bilingual wording; and
- existing **Contradictions** for inspection.

A Service candidate decides which concrete Procedure is relevant before a Procedure Version is
selected. Do not copy version applicability into the Service candidate merely because the rules
look similar.

Questions obtain missing source Facts; they do not decide eligibility. The rule engine determines
when a Fact is needed.

For a Question that deterministically supplies more than one source Fact, configure its resolved
Facts through the Question editing surface. The primary Fact must still be part of the resolved
set.

### 4.4 Create the Procedure, then attach it as a Service candidate

Create the stable **Procedure** and select its primary Service.

Return to the Service and add that Procedure to the candidate list with the correct selection
predicate. This ordering is useful because the candidate inline can only select Procedures that
belong to the Service.

Once a Procedure has published or withdrawn versions, its stable semantic identity and primary
Service are protected from casual reassignment.

### 4.5 Add Service contradictions when needed

Contradictions are Service-level case invariants: combinations of submitted Facts that cannot
coherently describe one case.

The Service page shows existing contradictions as a read-only inline. Create or edit them through
the dedicated **Service Contradictions** Admin surface, where the condition and implicated Facts
can be validated together.

A contradiction rule should identify genuinely incoherent input. It is not a substitute for a
negative eligibility rule, and UNKNOWN contradiction conditions do not ask Questions.

### 4.6 Create the draft Procedure Version

Create a **Procedure Version** for the Procedure. New semantic content must start in
`draft`.

Configure the version's:

- stable semantic ID;
- effective interval;
- bilingual version text;
- rules-contract version; and
- version-specific applicability.

Lifecycle fields such as publication/withdrawal actor and timestamps are controlled by lifecycle
services and are read-only in Admin.

The Procedure Version page is the main navigation hub for version-owned content. It shows links
to:

1. Checklist Items
2. Steps
3. Warnings
4. Eligibility Bases
5. Fees
6. Procedure Dependencies
7. Procedure-Service Point Associations

The compact inlines are intentionally not a replacement for each item's full editing screen.
Use the change link to edit detailed rules, bilingual text, evidence, scope, temporal metadata,
and other fields.

### 4.7 Enter checklist material

Use **Checklist Items** for document requirements and practical preparation.

Each item owns its own:

- semantic ID;
- bilingual text;
- classification;
- applicability;
- optional Eligibility Basis scope;
- Document Type and quantity information;
- display order;
- verification/trust metadata; and
- Evidence Links.

A Document Type is only the reusable identity of a document. Whether it is required, how many
copies are needed, and under what conditions are properties of the version-owned Checklist Item.

### 4.8 Enter Steps

Use **Steps** for material actions the user must take.

Pay attention to deterministic ordering:

- phase;
- phase order;
- slot; and
- semantic ID.

A Step may be procedure-wide or scoped to an Eligibility Basis. Add claim-specific Evidence Links
for material administrative assertions.

### 4.9 Enter Warnings

Warnings have a kind, severity, role, display order, and bilingual text.

Administrative warnings make external claims and therefore require evidence. Product-level safety
or regeneration wording is presentation policy and must not be given Evidence Links simply to
make publication pass.

### 4.10 Enter Eligibility Bases

Use **Eligibility Bases** for alternative legal or administrative qualification grounds.

Every Basis requires a **qualification** rule. **Reachability** may be omitted when the Basis is
always worth investigating.

Keep the two stages separate:

- reachability answers whether the route is still relevant enough to investigate;
- qualification answers whether a reachable case matches the Basis.

Do not put downstream qualification Facts into reachability just to force an interview order.
The planner already asks only for Facts needed by the current stage.

A matched Basis is a candidate alternative, not a legal determination or ranking.

### 4.11 Enter Fees

Use **Fees** for structured monetary claims. Preserve the distinction between:

- known amount;
- range;
- unknown; and
- unverified.

Do not invent a number because an editor believes one is likely. An explicit unknown value is
valid and safer than unsupported certainty.

Fee applicability is separate from the monetary value itself and can require its own Question
coverage.

### 4.12 Enter Procedure dependencies

Use a **Procedure Dependency** only when research supports a real direct relationship. Version 1
supports the bounded direct dependency contract rather than arbitrary workflow graphs.

Do not add a dependency merely because another government transaction would be useful or commonly
performed first.

### 4.13 Enter routing

Routing has three layers:

1. **Service Point** — stable destination identity;
2. **Service Point Version** — time-bounded address/availability details;
3. **Procedure-Service Point Association** — the Procedure Version's rule for using that material
   destination.

The applicability rule belongs to the association, not the Service Point identity.

Evidence may be required both for material Service Point details and for the Procedure-specific
routing assertion. Do not infer nationwide coverage, nearest-office behavior, or ranking from a
small set of researched offices.

### 4.14 Add Evidence Links and Sources

Evidence is claim-specific.

For every material claim that requires support:

1. create or select the preserved Source;
2. open the Checklist Item, Step, administrative Warning, Fee, Eligibility Basis, dependency,
   Service Point Version, or routing association;
3. add an **Evidence Link** with the exact relied-upon passage/context, location where useful,
   applicability context, verification state, and support status;
4. open the Evidence Link if necessary and attach its Source records.

One Source can support many claims, but each Evidence Link exists because a particular claim
relies on that source material.

Official Requirements must rely on appropriate official evidence. Field Reports need sufficient
observation provenance before they can support Field Guidance.

### 4.15 Record discrepancies instead of hiding conflicts

When sources conflict, are stale, or have the wrong applicability, use the
**Evidence Discrepancy** workflow.

Create a discrepancy around the affected evidence subject, record a concise rationale, attach the
relevant Evidence Links, and preserve the resulting trust consequence. Resolve the discrepancy
only when the conflict is actually resolved; resolved discrepancy history remains auditable.

Do not silently delete inconvenient evidence or relabel a source to force a desired result.

### 4.16 Add Planning Scenarios

Create **Planning Scenarios** for the draft before publication.

Scenarios should cover the behavior that matters for that Procedure, including applicable
combinations of:

- positive/plan behavior;
- negative/non-applicable behavior;
- missing-Fact/UNKNOWN behavior;
- contradictory input;
- version/effective-date boundaries;
- high-risk alternative branches; and
- important routing, fee, checklist, or trust edges.

The scenario behavior signature is generated by the system. Treat scenario changes as
meaningful reviewed-state changes.

### 4.17 Configure the Review Policy

Every publishable draft needs exactly one **Procedure Version Review Policy**.

Set:

- the accountable author; and
- each specialist risk that actually applies:
  - legal;
  - military;
  - custody/guardianship;
  - contested identity.

Do not enable specialist flags merely as a generic "extra safety" checkbox; they define required
independent approvals. Conversely, do not omit a real high-risk category to make publication
easier.

Changing the author or risk policy changes the reviewed-state signature and invalidates prior
approvals.

### 4.18 Do an editor self-check before requesting review

Before asking reviewers to approve the version, inspect the draft as one coherent unit.

Check at least:

- Arabic and English text convey the same meaning;
- all referenced Fact keys exist and have the correct types;
- consequential source Facts have Service Questions;
- applicability rules are attached at the correct ownership level;
- ordering is deterministic;
- effective dates are correct and non-overlapping where required;
- official claims have appropriate evidence;
- unknowns remain explicit;
- trust/verification state matches the evidence;
- scenarios describe the intended behavior;
- specialist-risk flags are correct; and
- no editor has filled a research gap with an unsupported assumption.

Saving individual Admin forms catches many local validation errors. Publication is the final
whole-version validation boundary and may still find cross-record problems.

### 4.19 Record independent review

From the **Procedure Versions** changelist:

1. select the draft;
2. choose **Record independent review or specialist approval**;
3. choose the review dimension;
4. submit the action.

Ordinary review dimensions are:

- Evidence/source
- Rule/logic
- Scenario/behavior
- Arabic/English semantic
- Discrepancy, when required

The reviewer must have `knowledge.review_procedureversion`.

Approval records bind to a SHA-256 signature of the coherent reviewed draft state. If an editor
changes consequential content afterward, the old approval remains in history but becomes stale.
Request a fresh approval for the new state.

### 4.20 Record specialist approval

Use the same Procedure Version action and choose the required specialist approval.

The reviewer must hold the matching specialist permission. Specialist approval is separate from
ordinary review: a military specialist approval does not automatically approve evidence,
rule/logic, scenarios, or bilingual meaning.

### 4.21 Publish

When review is complete, a publisher with `knowledge.publish_procedureversion` selects the draft
on the Procedure Versions changelist and chooses **Publish selected drafts**.

Publication is not a simple state-field edit. The canonical publication service:

- locks the relevant state;
- runs the complete publication gates;
- checks review independence/freshness;
- validates temporal overlap;
- changes lifecycle state atomically; and
- records immutable audit history.

If publication is rejected, Admin reports diagnostics in the form:

```text
gate: code (detail)
```

Fix the draft based on the diagnostic, then obtain fresh approvals whenever the fix changed the
reviewed state.

After a successful publish, semantic material becomes read-only.

## 5. Editing something that is already published

Never try to "unlock" or directly update published semantic rows.

For a meaning-changing correction:

1. select the published Procedure Version;
2. choose **Clone selected published versions to editable successor drafts**;
3. open the newly created draft;
4. make the correction;
5. update evidence/scenarios/review policy as needed;
6. obtain fresh independent review;
7. publish the successor.

The clone copies the coherent editable aggregate but deliberately does not copy historical review
approvals, publication events, discrepancy transitions, or re-verification history.

Stable shared provenance and identities may be reused when they still mean exactly the same thing.

## 6. Evidence re-verification without a meaning change

If research confirms or refreshes evidence without changing public meaning, use the
**Evidence Links** changelist rather than cloning a new Procedure Version.

Select an Evidence Link and choose **Re-verify selected evidence subjects**. Enter:

- verification state;
- verified date;
- optional next re-verification date; and
- rationale.

The action reviews the complete current evidence set for that semantic subject and records an
immutable re-verification event.

If the research changes the claim's public meaning, applicability, amount, routing, translation
meaning, or other semantics, re-verification is the wrong tool. Clone a successor Procedure
Version instead.

## 7. Withdrawing a published version

A staff member with `knowledge.withdraw_procedureversion` can select a published Procedure
Version and choose **Withdraw selected published versions**.

Withdrawal removes the version from ordinary new planning selection. It does not delete the
version or its evidence, reviews, or audit history.

Use withdrawal for a version that should no longer be selected, not as a substitute for editing
or deleting history.

## 8. Programmatic editorial workflow

### 8.1 What "programmatic" means today

Bardi does not currently expose a generic editorial CSV/JSON upload API or bulk CMS interface.

The supported pattern for repeatable programmatic data entry is a **deterministic production
importer**, normally paired with a Django management command. This is appropriate when:

- a researched Procedure contains many related rows;
- the source pack is maintained in code/reviewed data;
- repeatable environments need the same draft;
- integrity must be checked exactly; or
- manual entry would be error-prone.

For small editorial corrections or ordinary day-to-day updates, Admin is usually simpler.

### 8.2 Existing examples

The current production importers are:

```bash
uv run python backend/manage.py import_passport_renewal --author <username> \
  --settings=bardi.settings.development

uv run python backend/manage.py import_national_id_renewal --author <username> \
  --settings=bardi.settings.development

uv run python backend/manage.py import_temporary_family_exemption --author <username> \
  --settings=bardi.settings.development
```

Each command requires an existing staff user. It does not create users, approvals, or publication
metadata.

A successful rerun verifies or returns the same intended state rather than silently creating a
second copy.

### 8.3 Rules for a new importer

A production importer should be:

- **deterministic** — the same researched input produces the same semantic state;
- **idempotent** — a repeat run verifies/returns the intended rows rather than duplicating them;
- **atomic** — importer writes and final integrity verification succeed or roll back together;
- **fail-closed** — unexpected existing semantic drift is rejected rather than overwritten;
- **actor-accountable** — the draft has a real saved staff author;
- **draft-only** — the importer does not manufacture review approvals or publication;
- **evidence-preserving** — Sources and claim-specific evidence are explicit;
- **contract-aware** — it uses current production models and services, not hand-written database
  SQL or historical prototype shapes.

The public importer should own the outer atomic importer-plus-verifier boundary. The current
pattern is conceptually:

```python
@transaction.atomic
def _import_example(*, author: models.Model) -> ProcedureVersion:
    # Create or verify the researched draft and related records.
    ...
    return version


@transaction.atomic
def import_example(*, author: models.Model) -> ProcedureVersion:
    version = _import_example(author=author)

    from .example_integrity import verify_example_import

    verify_example_import(version)
    return version
```

The verifier must run exactly once for every public importer invocation, including idempotent
existing-row paths. If verification fails, the entire call must roll back.

### 8.4 Add a management command

Prefer a small management command as the operator-facing entry point. It should:

1. require `--author`;
2. resolve an existing staff user;
3. reject an unknown/non-staff author;
4. call the public importer; and
5. print the resulting semantic ID/state.

Keep command logic thin. Domain construction and verification belong in importer/integrity code,
not in argument handling.

### 8.5 Direct importer use

For developer-assisted work, the same public importer may be called from a Django-aware script or
shell after resolving a real staff user:

```python
from django.contrib.auth import get_user_model
from knowledge.importers.passport_renewal import import_passport_renewal

author = get_user_model().objects.get(username="editor", is_staff=True)
version = import_passport_renewal(author=author)
print(version.semantic_id, version.state)
```

Prefer the management command for routine operator use because it is easier to reproduce and
audit operationally.

Do not use one-off ORM scripts that call `.update()` on published/version-owned rows to bypass
model validation, immutability, or publication services.

### 8.6 Programmatic review, publication, withdrawal, and re-verification

Canonical service functions exist for lifecycle operations, including:

- `approve_review_dimension()`;
- `approve_specialist_risk()`;
- `publish_procedure_version()`;
- `withdraw_procedure_version()`;
- `record_evidence_reverification()`; and
- `clone_published_procedure_version()`.

These services preserve domain and transactional invariants, but custom tooling still needs an
explicit authorization boundary around who is allowed to invoke it. Django Admin already provides
that permission boundary and is the preferred staff interface.

Do not build an ad-hoc script that calls lifecycle services under a generic superuser simply to
skip the normal separation of author, reviewer, specialist, and publisher responsibilities.

If a future bulk-editor tool is added, it should call these same canonical services rather than
reimplementing state transitions.

## 9. Choosing Admin vs an importer

Use **Admin** when:

- an editor is researching or correcting a small number of records;
- human review of each field/evidence link is useful;
- the change is exploratory but still within a draft;
- the update is a normal successor-version edit; or
- the operation is review, publication, withdrawal, or semantic-preserving re-verification.

Use a **programmatic importer** when:

- a complete researched data set should be reproducible;
- many related rows must be constructed consistently;
- idempotent verification matters;
- the same data must be loaded into multiple environments; or
- a reviewed code/data change is safer than repetitive manual entry.

Both paths meet at the same draft/review/publication lifecycle. Programmatic import is not a
shortcut around editorial review.

## 10. Common mistakes

### Editing a published row

**Symptom:** Admin fields are read-only or a save/delete is rejected.

**Meaning:** The version or shared provenance is part of immutable history.

**Action:** Clone a successor draft for semantic changes. Create new provenance where the source
itself has changed.

### Publication says review is missing or stale

**Symptom:** Publication reports missing/stale review diagnostics.

**Meaning:** A required approval was never recorded, the reviewer is ineligible, or the reviewed
state changed after approval.

**Action:** Finish editing first, then request fresh independent approvals.

### A specialist approval does not satisfy ordinary review

**Meaning:** Specialist and general review are separate capabilities.

**Action:** Record the required ordinary review dimensions as well.

### A rule refers to a Fact but planning cannot ask for it

**Meaning:** The source Fact may lack an appropriate Service Question, or the rule/Fact ownership
is wrong.

**Action:** Check the stable Fact Definition, Service Question coverage, and whether the rule
belongs at Service candidate, Procedure Version, Basis, Fee, checklist, step, or routing scope.

### Evidence exists but publication still rejects the claim

**Meaning:** Merely attaching a Source is not always sufficient. Classification, passage/context,
support status, verification state, temporal applicability, Field Report provenance, or
discrepancy state may be invalid.

**Action:** Follow the exact publication diagnostic instead of weakening the claim.

### An unknown value feels inconvenient

**Meaning:** Research is incomplete.

**Action:** Keep it explicitly unknown/unverified. Do not guess to make the plan look complete.

## 11. Suggested first-week exercise for a new editor

Before editing a new real Service, practice on a disposable development database:

1. inspect one of the imported researched drafts;
2. trace Service -> Procedure -> Procedure Version -> Checklist/Steps/Fees/Evidence;
3. inspect its Review Policy and Planning Scenarios;
4. create a small draft-only change on a cloned successor;
5. observe how that change makes old approvals inapplicable;
6. record a review using a separate reviewer account;
7. intentionally attempt publication before all requirements are met and read the diagnostics;
8. finish the required review and publish;
9. confirm the published material becomes read-only; and
10. try evidence re-verification on a semantic-preserving evidence update.

Use only disposable/local data for this exercise. Do not publish training edits into a shared
catalog.

## 12. Editor checklist

Before handing a draft to reviewers:

- [ ] Service and Procedure identities are correct.
- [ ] Candidate selection and version applicability are at the correct levels.
- [ ] Fact Definitions are reused where semantics are truly shared.
- [ ] Consequential source Facts have bilingual Service Questions.
- [ ] Arabic and English public text are semantically aligned.
- [ ] Requirements, steps, fees, warnings, Bases, dependencies, and routing contain no invented
      claims.
- [ ] Unknown/unverified values are explicit.
- [ ] Material claims have claim-specific Evidence Links.
- [ ] Sources are classified and preserved correctly.
- [ ] Discrepancies are recorded rather than hidden.
- [ ] Effective dates and ordering are intentional.
- [ ] Planning Scenarios cover meaningful outcomes and edges.
- [ ] Review Policy names the accountable author and correct specialist risks.
- [ ] Editing is complete before reviewers approve the state.

Before publication:

- [ ] Required ordinary review dimensions are fresh.
- [ ] Required specialist approvals are fresh.
- [ ] Reviewers are independent of the accountable author and publisher.
- [ ] Publication diagnostics are clear.
- [ ] The publisher is prepared for the version to become immutable.

After publication:

- [ ] Meaning-changing corrections use a successor draft.
- [ ] Semantic-preserving evidence refreshes use re-verification.
- [ ] Obsolete published versions are withdrawn rather than deleted.
