"""Immutable input for separate, non-routable research-suite draft imports.

These records are not an administrative rule engine. Conditions stay in researched
text until the compatibility design and each family's evidence gates are closed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

RESEARCH_DATE = date(2026, 9, 12)
RESEARCH_COMMIT = "6b6de168a5372b8b7105a983245f71723f0248c1"
type ClaimKind = Literal["checklist", "step", "fee", "note"]


@dataclass(frozen=True, slots=True)
class SourceSpec:
    alias: str
    authority: str
    authority_ar: str
    authority_en: str
    title: str
    locator: str
    context: str
    published_on: date | None = None
    effective_from: date | None = None


@dataclass(frozen=True, slots=True)
class ClaimSpec:
    id: str
    kind: ClaimKind
    text_ar: str
    text_en: str
    sources: tuple[str, ...]
    context: str
    amount: int | None = None
    currency: str = "EGP"


@dataclass(frozen=True, slots=True)
class DraftScope:
    key: str
    label_ar: str
    label_en: str
    claims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FamilySpec:
    row: str
    procedure_id: str | None
    title_ar: str
    title_en: str
    boundary: str
    blockers: tuple[str, ...]
    scopes: tuple[DraftScope, ...] = ()
    risks: tuple[str, ...] = ("legal",)
    # Existing Procedure labels are stable and differ from the new research titles.
    identity_ar: str | None = None
    identity_en: str | None = None


@dataclass(frozen=True, slots=True)
class SuiteSpec:
    key: str
    service_id: str
    service_ar: str
    service_en: str
    sources: tuple[SourceSpec, ...]
    claims: tuple[ClaimSpec, ...]
    families: tuple[FamilySpec, ...]

    @property
    def fingerprint(self) -> str:
        payload = {"research_date": RESEARCH_DATE.isoformat(), "suite": asdict(self)}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate(self) -> None:
        """Fail before any writes for duplicate, dangling or cross-suite records."""
        if self.key not in {"passport", "national_id"}:
            raise ValueError("Unsupported suite.")
        expected_service = {
            "passport": "get_egyptian_passport",
            "national_id": "get_egyptian_national_id",
        }[self.key]
        if self.service_id != expected_service:
            raise ValueError("Suite Service identity must remain canonical.")
        if not self.service_ar.strip() or not self.service_en.strip():
            raise ValueError("Suite Service must have bilingual text.")
        aliases = [source.alias for source in self.sources]
        claims = [claim.id for claim in self.claims]
        rows = [family.row for family in self.families]
        for name, values in (("Source", aliases), ("Claim", claims), ("Family", rows)):
            if len(values) != len(set(values)) or any(not value.strip() for value in values):
                raise ValueError(f"Duplicate or blank {name} identity.")
        expected_rows = [
            f"{'P' if self.key == 'passport' else 'N'}{index:02}"
            for index in range(1, 15 if self.key == "passport" else 16)
        ]
        if rows != expected_rows:
            raise ValueError("Every catalog row must appear exactly once, in catalog order.")
        for source in self.sources:
            parsed = urlsplit(source.locator)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError(f"Invalid source locator: {source.alias}.")
            if not all((source.authority_ar, source.authority_en, source.title, source.context)):
                raise ValueError(f"Incomplete Source: {source.alias}.")
        for claim in self.claims:
            if claim.kind not in {"checklist", "step", "fee", "note"}:
                raise ValueError(f"Invalid claim kind: {claim.id}.")
            if not claim.sources or len(set(claim.sources)) != len(claim.sources):
                raise ValueError(f"Invalid source references: {claim.id}.")
            if not set(claim.sources) <= set(aliases):
                raise ValueError(f"Unknown Source: {claim.id}.")
            if not all((claim.text_ar.strip(), claim.text_en.strip(), claim.context.strip())):
                raise ValueError(f"Incomplete bilingual claim: {claim.id}.")
            if claim.amount is not None and (
                claim.kind != "fee" or type(claim.amount) is not int or claim.amount < 0
            ):
                raise ValueError(f"Invalid monetary shape: {claim.id}.")
        versions: set[str] = set()
        procedures: set[str] = set()
        for family in self.families:
            if not family.blockers or not all((family.title_ar, family.title_en, family.boundary)):
                raise ValueError(f"Incomplete family: {family.row}.")
            if not set(family.risks) <= {
                "legal",
                "military",
                "custody_guardianship",
                "contested_identity",
            }:
                raise ValueError(f"Unknown review risk: {family.row}.")
            if family.procedure_id is None and family.scopes:
                raise ValueError(f"Cannot stage an unresolved Procedure identity: {family.row}.")
            if family.procedure_id is not None:
                if not family.scopes:
                    raise ValueError(f"Named family has no draft scope: {family.row}.")
                if not family.procedure_id.strip() or family.procedure_id in procedures:
                    raise ValueError("Duplicate or blank Procedure identity.")
                procedures.add(family.procedure_id)
            if (family.identity_ar is None) != (family.identity_en is None):
                raise ValueError("Existing Procedure identity text must be bilingual.")
            for scope in family.scopes:
                if not scope.key or not scope.label_ar or not scope.label_en or not scope.claims:
                    raise ValueError(f"Incomplete scope: {family.row}.")
                if not set(scope.claims) <= set(claims):
                    raise ValueError(f"Unknown Claim: {family.row}:{scope.key}.")
                if len(scope.claims) != len(set(scope.claims)):
                    raise ValueError(f"Duplicate Claim: {family.row}:{scope.key}.")
                identity = version_id(self, family, scope)
                if len(identity) > 128 or identity in versions:
                    raise ValueError("Duplicate or excessive draft version identity.")
                versions.add(identity)


def version_id(suite: SuiteSpec, family: FamilySpec, scope: DraftScope) -> str:
    return f"{suite.key}.suite.{family.row}.{scope.key}.research-2026-09-12"


def load_suite(key: str) -> SuiteSpec:
    """Read only the packaged, allow-listed manifest; no Markdown parsing or network."""
    from pathlib import Path

    if key not in {"passport", "national_id"}:
        raise ValueError("Unsupported suite.")
    path = Path(__file__).with_name("suite_data") / f"{key}_2026_09_12.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.pop("research_date") != RESEARCH_DATE.isoformat() or data.get("key") != key:
        raise ValueError("Unexpected suite research identity/date.")
    sources = []
    for raw in data.pop("sources"):
        for name in ("published_on", "effective_from"):
            if raw.get(name) is not None:
                value = raw[name]
                raw[name] = date.fromisoformat(value)
                if raw[name].isoformat() != value:
                    raise ValueError("Noncanonical source date.")
        sources.append(SourceSpec(**raw))
    claims = tuple(
        ClaimSpec(**{**raw, "sources": tuple(raw["sources"])}) for raw in data.pop("claims")
    )
    families = []
    for raw in data.pop("families"):
        scopes = tuple(
            DraftScope(**{**scope, "claims": tuple(scope["claims"])})
            for scope in raw.pop("scopes")
        )
        raw["blockers"] = tuple(raw["blockers"])
        raw["risks"] = tuple(raw["risks"])
        families.append(FamilySpec(**raw, scopes=scopes))
    spec = SuiteSpec(**data, sources=tuple(sources), claims=claims, families=tuple(families))
    spec.validate()
    return spec
