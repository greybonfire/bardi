"""Atomic, strict imports of research dossiers into existing editorial draft models.

No Service activation, candidates, Questions, Fact publication, scenario signatures,
rule predicates, approvals, or live guidance are created by this staging layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import connection, models, transaction

from knowledge.fees import Fee
from knowledge.models import (
    Authority,
    ChecklistItem,
    EvidenceLink,
    Procedure,
    ProcedureVersion,
    Service,
    Source,
    Step,
    Warning,
)
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.services import set_evidence_link_sources

from .suite_specs import (
    RESEARCH_COMMIT,
    RESEARCH_DATE,
    ClaimSpec,
    DraftScope,
    FamilySpec,
    SuiteSpec,
    version_id,
)

type VersionClaim = ChecklistItem | Step | Fee | Warning


@dataclass(frozen=True, slots=True)
class FamilyImportResult:
    row: str
    versions: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SuiteImportResult:
    suite: str
    fingerprint: str
    families: tuple[FamilyImportResult, ...]
    created_versions: int
    checked_only: bool
    dry_run: bool


def _fields(instance: models.Model) -> dict[str, Any]:
    return {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
        if not field.primary_key
    }


def _expect(instance: models.Model, expected: models.Model) -> None:
    if _fields(instance) != _fields(expected):
        # Report identity, never a potentially sensitive wider object or raw field value.
        identity = getattr(instance, "semantic_id", instance._meta.label_lower)
        raise ValidationError(f"{identity}: suite draft semantic conflict.")


def _reject_extra_relations(instance: models.Model, allowed: set[str]) -> None:
    """Pristine staging aggregates cannot acquire unverified workflow/feature children."""
    for relation in instance._meta.related_objects:
        accessor = relation.get_accessor_name()
        if accessor is None or accessor in allowed:
            continue
        if relation.one_to_many or relation.many_to_many:
            if getattr(instance, accessor).exists():
                raise ValidationError(f"Unexpected suite draft relation: {accessor}.")
        elif relation.one_to_one:
            try:
                getattr(instance, accessor)
            except ObjectDoesNotExist:
                continue
            raise ValidationError(f"Unexpected suite draft relation: {accessor}.")


def _save_new(instance: models.Model) -> models.Model:
    instance.full_clean()
    instance.save()
    return instance


def _source_id(suite: SuiteSpec, alias: str) -> str:
    return f"{suite.key}.suite.source.{alias}.2026-09-12"


def _shared_sources(suite: SuiteSpec, *, check_only: bool) -> dict[str, Source]:
    result: dict[str, Source] = {}
    for spec in suite.sources:
        authority_id = f"{suite.key}.suite.authority.{spec.authority}"
        expected_authority = Authority(
            semantic_id=authority_id, name_ar=spec.authority_ar, name_en=spec.authority_en
        )
        authority = Authority.objects.filter(semantic_id=authority_id).first()
        if authority is None:
            if check_only:
                raise ValidationError(f"Missing suite Authority: {authority_id}.")
            authority = cast(Authority, _save_new(expected_authority))
        else:
            _expect(authority, expected_authority)
        expected_source = Source(
            semantic_id=_source_id(suite, spec.alias),
            authority=authority,
            title=spec.title,
            locator=spec.locator,
            classification="official",
            retrieved_on=RESEARCH_DATE,
            published_on=spec.published_on,
            effective_from=spec.effective_from,
            observation_context=spec.context,
        )
        source = Source.objects.filter(semantic_id=expected_source.semantic_id).first()
        if source is None:
            if check_only:
                raise ValidationError(f"Missing suite Source: {spec.alias}.")
            source = cast(Source, _save_new(expected_source))
        else:
            _expect(source, expected_source)
        result[spec.alias] = source
    return result


def _service(suite: SuiteSpec, *, check_only: bool) -> Service:
    service = Service.objects.filter(semantic_id=suite.service_id).first()
    if service is None:
        if check_only:
            raise ValidationError("Missing suite Service.")
        service = cast(
            Service,
            _save_new(
                Service(
                    semantic_id=suite.service_id,
                    text_ar=suite.service_ar,
                    text_en=suite.service_en,
                    is_active=False,
                )
            ),
        )
    if (service.text_ar, service.text_en) != (suite.service_ar, suite.service_en):
        raise ValidationError("Suite Service identity/text conflicts with existing knowledge.")
    # Activation is deliberately not compared or changed; it is an editorial decision.
    return service


def _procedure(service: Service, family: FamilySpec, *, check_only: bool) -> Procedure:
    procedure_id = family.procedure_id
    if procedure_id is None:
        raise ValidationError(f"Unresolved suite Procedure identity: {family.row}.")
    expected = Procedure(
        semantic_id=procedure_id,
        text_ar=family.identity_ar or family.title_ar,
        text_en=family.identity_en or family.title_en,
        primary_service=service,
    )
    procedure = Procedure.objects.filter(semantic_id=procedure_id).first()
    if procedure is None:
        if check_only:
            raise ValidationError(f"Missing suite Procedure: {family.row}.")
        return cast(Procedure, _save_new(expected))
    _expect(procedure, expected)
    return procedure


def _claim_instance(version: ProcedureVersion, claim: ClaimSpec, position: int) -> VersionClaim:
    values: dict[str, Any] = {
        "procedure_version": version,
        "semantic_id": claim.id,
        "text_ar": claim.text_ar,
        "text_en": claim.text_en,
        "verification_state": "needs_reverification",
        "verified_on": None,
        "reverify_on": None,
        "applicability": {},
    }
    if claim.kind == "checklist":
        # Research quantities/alternatives remain text, not asserted original/copy requirements.
        return ChecklistItem(**values, classification="candidate", display_order=position)
    if claim.kind == "step":
        return Step(**values, phase="submit", phase_order=0, slot=position)
    if claim.kind == "fee":
        return Fee(
            **values,
            value_state="unverified" if claim.amount is not None else "unknown",
            amount=claim.amount,
            currency=claim.currency,
            display_order=position,
        )
    # Compound observations, discrepancies and discovery are not documentary requirements.
    return Warning(
        **values,
        kind="administrative",
        severity="important",
        role="limitation",
        display_order=position,
    )


def _evidence_instance(
    owner: VersionClaim,
    claim: ClaimSpec,
    suite: SuiteSpec,
    family: FamilySpec,
    scope: DraftScope,
) -> EvidenceLink:
    model_name = owner._meta.model_name
    if model_name is None:
        raise ValidationError("Suite evidence requires a concrete claim owner.")
    owner_field = {
        "checklistitem": "checklist_item",
        "step": "step",
        "fee": "fee",
        "warning": "warning",
    }[model_name]
    return EvidenceLink(
        **{owner_field: owner},
        semantic_id=f"{claim.id}.research-context",
        passage=f"Research summary, not a verbatim primary-source quotation: {claim.context}",
        location=f"docs/evidence-packs/{suite.key.replace('_', '-')}-suite/claims.md :: {claim.id}",
        applicability_context=(
            f"Catalog {family.row}; scope {scope.key}. {family.boundary}\n"
            "Conditions and proof alternatives are NOT compiled into executable rules. "
            "Preserve scope; obtain and review exact primary passages before asserting support."
        ),
        retrieved_on=RESEARCH_DATE,
        verification_state="needs_reverification",
        support_status="context",
    )


def _marker(
    version: ProcedureVersion, suite: SuiteSpec, family: FamilySpec, scope: DraftScope
) -> Warning:
    return Warning(
        procedure_version=version,
        semantic_id="suite.research_draft",
        text_ar=(
            "مسودة بحثية غير قابلة للنشر أو الاستخدام كإرشادات. يلزم استكمال القواعد والأدلة "
            "والسيناريوهات والمراجعة المستقلة. نطاق البحث: " + scope.label_ar
        ),
        text_en=(
            "Non-routable research draft; not administrative guidance. "
            f"Catalog {family.row}; {scope.label_en}. {family.boundary}\n"
            f"Open gates: {', '.join(family.blockers)}; I02; executable rules/scenarios; "
            "independent source/bilingual/specialist review.\n"
            f"Research commit: {RESEARCH_COMMIT}; manifest: {suite.fingerprint}."
        ),
        kind="product",
        severity="important",
        role="limitation",
        verification_state="unknown",
        display_order=0,
    )


def _policy(
    version: ProcedureVersion, family: FamilySpec, author: models.Model
) -> ProcedureVersionReviewPolicy:
    return ProcedureVersionReviewPolicy(
        procedure_version=version,
        author_id=author.pk,
        legal_risk="legal" in family.risks,
        military_risk="military" in family.risks,
        custody_guardianship_risk="custody_guardianship" in family.risks,
        contested_identity_risk="contested_identity" in family.risks,
    )


def _build_version(
    suite: SuiteSpec,
    family: FamilySpec,
    scope: DraftScope,
    procedure: Procedure,
    author: models.Model,
    sources: dict[str, Source],
) -> ProcedureVersion:
    version = cast(
        ProcedureVersion,
        _save_new(
            ProcedureVersion(
                semantic_id=version_id(suite, family, scope),
                procedure=procedure,
                text_ar=f"{family.title_ar} — {scope.label_ar}",
                text_en=f"{family.title_en} — {scope.label_en}",
                # Incomplete authoring, never a fabricated True/False rule.
                # Mandatory ApplicabilityGate rejects publication of this draft.
                applicability={},
                effective_from=None,
                effective_to=None,
            )
        ),
    )
    _save_new(_marker(version, suite, family, scope))
    _save_new(_policy(version, family, author))
    claims = {claim.id: claim for claim in suite.claims}
    for position, claim_id in enumerate(scope.claims, start=1):
        claim = claims[claim_id]
        owner = cast(VersionClaim, _save_new(_claim_instance(version, claim, position)))
        evidence = cast(
            EvidenceLink, _save_new(_evidence_instance(owner, claim, suite, family, scope))
        )
        set_evidence_link_sources(evidence, tuple(sources[alias] for alias in claim.sources))
    return version


def _verify_version(
    version: ProcedureVersion,
    suite: SuiteSpec,
    family: FamilySpec,
    scope: DraftScope,
    procedure: Procedure,
    author: models.Model,
    sources: dict[str, Source],
) -> None:
    _expect(
        version,
        ProcedureVersion(
            semantic_id=version_id(suite, family, scope),
            procedure=procedure,
            text_ar=f"{family.title_ar} — {scope.label_ar}",
            text_en=f"{family.title_en} — {scope.label_en}",
            applicability={},
        ),
    )
    _reject_extra_relations(
        version, {"checklist_items", "steps", "fees", "warnings", "review_policy"}
    )
    try:
        _expect(version.review_policy, _policy(version, family, author))
    except ProcedureVersionReviewPolicy.DoesNotExist as exc:
        raise ValidationError("Missing suite review policy.") from exc
    claims = {claim.id: claim for claim in suite.claims}
    expected_rows: dict[type[VersionClaim], list[VersionClaim]] = {
        ChecklistItem: [],
        Step: [],
        Fee: [],
        Warning: [_marker(version, suite, family, scope)],
    }
    for position, claim_id in enumerate(scope.claims, start=1):
        expected_claim = _claim_instance(version, claims[claim_id], position)
        expected_rows[type(expected_claim)].append(expected_claim)
    for model, expected_claims in expected_rows.items():
        actual = {
            row.semantic_id: row
            for row in cast(Any, model).objects.filter(procedure_version=version)
        }
        if set(actual) != {row.semantic_id for row in expected_claims}:
            raise ValidationError(f"{version.semantic_id}: unexpected {model.__name__} set.")
        for row in expected_claims:
            stored = actual[row.semantic_id]
            _expect(stored, row)
            _reject_extra_relations(stored, {"evidence_links"})
            links = list(stored.evidence_links.all())
            if row.semantic_id == "suite.research_draft":
                if links:
                    raise ValidationError("Product draft warning unexpectedly has evidence.")
                continue
            claim = claims[row.semantic_id]
            if len(links) != 1:
                raise ValidationError(f"{row.semantic_id}: suite Evidence Link set conflict.")
            _expect(links[0], _evidence_instance(stored, claim, suite, family, scope))
            _reject_extra_relations(links[0], {"source_links"})
            actual_sources = tuple(
                links[0].source_links.order_by("position").values_list("source_id", "position")
            )
            expected_sources = tuple(
                (sources[alias].pk, position)
                for position, alias in enumerate(claim.sources, start=1)
            )
            if actual_sources != expected_sources:
                raise ValidationError(f"{row.semantic_id}: suite Source order/content conflict.")


def _verify_suite(suite: SuiteSpec, author: models.Model) -> None:
    """One final verification entry, called exactly once by the atomic public operation."""
    service = _service(suite, check_only=True)
    sources = _shared_sources(suite, check_only=True)
    expected_ids: set[str] = set()
    for family in suite.families:
        if family.procedure_id is None:
            continue
        procedure = _procedure(service, family, check_only=True)
        for scope in family.scopes:
            identity = version_id(suite, family, scope)
            expected_ids.add(identity)
            version = (
                ProcedureVersion.objects.select_for_update().filter(semantic_id=identity).first()
            )
            if version is None:
                raise ValidationError(f"Missing suite draft: {identity}.")
            _verify_version(version, suite, family, scope, procedure, author, sources)
    actual_ids = set(
        ProcedureVersion.objects.filter(
            semantic_id__startswith=f"{suite.key}.suite.",
            semantic_id__endswith=".research-2026-09-12",
        ).values_list("semantic_id", flat=True)
    )
    if actual_ids != expected_ids:
        raise ValidationError("Unexpected suite draft versions.")
    expected_sources = {_source_id(suite, source.alias) for source in suite.sources}
    actual_sources = set(
        Source.objects.filter(
            semantic_id__startswith=f"{suite.key}.suite.source.",
            semantic_id__endswith=".2026-09-12",
        ).values_list("semantic_id", flat=True)
    )
    if actual_sources != expected_sources:
        raise ValidationError("Unexpected suite Source set.")


@transaction.atomic
def import_suite_drafts(
    suite: SuiteSpec,
    *,
    author: models.Model,
    check_only: bool = False,
    dry_run: bool = False,
) -> SuiteImportResult:
    """Stage a whole family atomically, or verify it; never repair edited imported drafts."""
    suite.validate()
    if check_only and dry_run:
        raise ValidationError("Choose either check-only or dry-run.")
    user_model = get_user_model()
    if not isinstance(author, user_model) or author.pk is None:
        raise ValidationError("A saved, active staff author is required.")
    if not user_model._default_manager.filter(pk=author.pk, is_active=True, is_staff=True).exists():
        raise ValidationError("A saved, active staff author is required.")
    if connection.vendor != "postgresql":
        raise ValidationError("Suite imports require PostgreSQL.")
    # Same lock for these two imports protects shared Service creation. Existing import
    # commands are not changed; do not run legacy and new imports concurrently.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [2026091201])
    created = 0
    # A namespace containing any of this import's Sources or versions is an existing
    # aggregate, not a partially completed import to repair. Atomic first imports
    # cannot leave a partial aggregate. Missing rows on rerun must fail verification.
    exists = (
        ProcedureVersion.objects.filter(
            semantic_id__startswith=f"{suite.key}.suite.",
            semantic_id__endswith=".research-2026-09-12",
        ).exists()
        or Source.objects.filter(
            semantic_id__startswith=f"{suite.key}.suite.source.",
            semantic_id__endswith=".2026-09-12",
        ).exists()
    )
    if not check_only and not exists:
        service = _service(suite, check_only=False)
        sources = _shared_sources(suite, check_only=False)
        for family in suite.families:
            if family.procedure_id is None:
                continue
            procedure = _procedure(service, family, check_only=False)
            for scope in family.scopes:
                _build_version(suite, family, scope, procedure, author, sources)
                created += 1
    _verify_suite(suite, author)
    result = SuiteImportResult(
        suite=suite.key,
        fingerprint=suite.fingerprint,
        families=tuple(
            FamilyImportResult(
                family.row,
                tuple(version_id(suite, family, scope) for scope in family.scopes),
                family.blockers,
            )
            for family in suite.families
        ),
        created_versions=created,
        checked_only=check_only,
        dry_run=dry_run,
    )
    if dry_run:
        transaction.set_rollback(True)
    return result
