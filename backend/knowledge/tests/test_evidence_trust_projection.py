from __future__ import annotations

import os
import subprocess
import sys
import unittest
from collections.abc import Iterator
from dataclasses import fields, replace
from datetime import UTC, date, datetime
from typing import Any, cast

from planning import Predicate, PreparedFacts
from planning.catalog import (
    AuthoritySnapshot,
    ChecklistItemSnapshot,
    EligibilityBasisSnapshot,
    EvidenceLinkSnapshot,
    FeeSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    ProcedureDependencySnapshot,
    ProcedureServicePointAssociationSnapshot,
    ProcedureVersionSnapshot,
    ServicePointVersionSnapshot,
    SourceSnapshot,
    StepSnapshot,
    WarningSnapshot,
)
from planning.fees import select_fees
from planning.trust import VerificationState

from knowledge.evidence_trust_projection import (
    DiscrepancyTransition,
    Reverification,
    project_evidence_trust,
)

DAY = date(2026, 9, 5)
AT = datetime(2026, 9, 5, 12, tzinfo=UTC)
DUE = date(2026, 10, 1)
TEXT = LocalizedText("نص", "Text")
KEY = ("fee", "v", "item")


def snapshot() -> KnowledgeSnapshot:
    source = SourceSnapshot(
        "source",
        AuthoritySnapshot("authority", TEXT),
        "Title",
        "https://example.org",
        "official",
        DAY,
    )
    link = EvidenceLinkSnapshot(
        "passage",
        "page",
        "context",
        "supports",
        "unknown",
        (source,),
        verified_on=DAY,
        reverify_on=DUE,
        semantic_id="link",
    )
    common: dict[str, Any] = dict(
        semantic_id="item",
        effective_from=None,
        effective_to=None,
        verification_state="unknown",
        verified_on=DAY,
        reverify_on=DUE,
        evidence_links=(link, replace(link, semantic_id="second")),
    )
    fee = FeeSnapshot(
        **common,
        text=TEXT,
        value_state="unverified",
        amount=900,
        minimum_amount=None,
        maximum_amount=None,
        currency="EGP",
        fee_type="ordinary",
        display_order=0,
        applicability=Predicate("eq", "overlay_fee_applies", True),
        scope="procedure",
        eligibility_basis_id=None,
    )
    version = ProcedureVersionSnapshot(
        "v",
        "procedure",
        TEXT,
        Predicate("eq", "x", True),
        "1",
        "published",
        None,
        None,
        fees=(fee,),
        checklist_items=(
            ChecklistItemSnapshot(
                **common,
                text=TEXT,
                classification="official",
                document_type_id=None,
                quantity=1,
                original_quantity=1,
                copy_quantity=0,
                display_order=0,
                applicability=None,
                scope="procedure",
                scope_reference="",
            ),
        ),
        eligibility_bases=(EligibilityBasisSnapshot(**common, text=TEXT),),
        steps=(
            StepSnapshot(
                **common,
                text=TEXT,
                phase="apply",
                phase_order=0,
                slot=0,
                applicability=None,
                scope="procedure",
                eligibility_basis_id=None,
            ),
        ),
        warnings=(
            WarningSnapshot(
                **common,
                text=TEXT,
                severity="warning",
                kind="administrative",
                role="guidance",
                display_order=0,
                applicability=None,
            ),
        ),
        dependencies=(
            ProcedureDependencySnapshot(
                **common,
                text=TEXT,
                target_procedure_id="target",
                target_procedure_text=TEXT,
                relation="blocking",
                applicability=None,
                satisfied_when=None,
                display_order=0,
            ),
        ),
        service_point_associations=(
            ProcedureServicePointAssociationSnapshot(
                **common, service_point_version_id="item", applicability=Predicate("eq", "x", True)
            ),
        ),
    )
    material = ServicePointVersionSnapshot(
        **common, service_point_id="office", address=TEXT, availability="available"
    )
    return KnowledgeSnapshot({}, (), (version,), service_point_versions=(material,))


def transition(
    state: VerificationState = "disputed",
    *,
    key: tuple[str, str, str] = KEY,
    id: int = 1,
    event: str = "opened",
) -> DiscrepancyTransition:
    return DiscrepancyTransition(key, AT, id, event, state)


def review(*, verified: date = DAY, due: date | None = None) -> Reverification:
    return Reverification(KEY, AT, "current", verified, due)


class EvidenceTrustProjectionTests(unittest.TestCase):
    def test_all_families_locality_and_authored_fields(self) -> None:
        original = snapshot()
        families = (
            ("checklist", "checklist_items"),
            ("eligibility_basis", "eligibility_bases"),
            ("step", "steps"),
            ("warning", "warnings"),
            ("fee", "fees"),
            ("procedure_dependency", "dependencies"),
            ("procedure_service_point_association", "service_point_associations"),
            ("service_point_version", ""),
        )
        for kind, attribute in families:
            with self.subTest(kind=kind):
                key = (kind, "v" if attribute else "", "item")
                result = project_evidence_trust(original, [transition(key=key)])
                before = (
                    getattr(original.procedure_versions[0], attribute)[0]
                    if attribute
                    else original.service_point_versions[0]
                )
                after = (
                    getattr(result.procedure_versions[0], attribute)[0]
                    if attribute
                    else result.service_point_versions[0]
                )
                self.assertEqual(after, replace(before, verification_state="disputed"))
                for _, other in families:
                    if other and other != attribute:
                        self.assertIs(
                            getattr(result.procedure_versions[0], other)[0],
                            getattr(original.procedure_versions[0], other)[0],
                        )
                self.assertEqual(original, snapshot())

    def test_structural_keys_do_not_collide(self) -> None:
        original = snapshot()
        first = replace(
            original.procedure_versions[0],
            semantic_id="a:b",
            fees=(replace(original.procedure_versions[0].fees[0], semantic_id="c"),),
        )
        second = replace(first, semantic_id="a", fees=(replace(first.fees[0], semantic_id="b:c"),))
        original = replace(original, procedure_versions=(first, second))
        result = project_evidence_trust(
            original,
            [
                transition(key=("fee", "a:b", "c")),
                transition(key=("service_point_version", "wrong", "item")),
            ],
        )
        self.assertEqual(result.procedure_versions[0].fees[0].verification_state, "disputed")
        self.assertIs(result.procedure_versions[1].fees[0], second.fees[0])
        self.assertIs(result.service_point_versions[0], original.service_point_versions[0])

    def test_open_precedence_partial_and_full_resolution(self) -> None:
        events: list[DiscrepancyTransition | Reverification] = [
            transition("unknown", id=100),
            transition("disputed", id=1),
            transition("needs_reverification", id=2),
            review(),
        ]
        for extra, expected in (
            ([], "disputed"),
            ([transition("current", id=1, event="resolved")], "needs_reverification"),
            (
                [
                    transition("current", id=1, event="resolved"),
                    transition("current", id=2, event="resolved"),
                ],
                "unknown",
            ),
            ([transition("current", id=i, event="resolved") for i in (1, 2, 100)], "current"),
        ):
            result = (
                project_evidence_trust(snapshot(), [*events, *extra]).procedure_versions[0].fees[0]
            )
            self.assertEqual(result.verification_state, expected)
            self.assertTrue(
                all(link.verification_state == "current" for link in result.evidence_links)
            )

    def test_reviews_assign_dates_and_preserve_provenance(self) -> None:
        original = snapshot()
        future = date(2027, 1, 1)
        result = (
            project_evidence_trust(original, [review(verified=future, due=DUE), review()])
            .procedure_versions[0]
            .fees[0]
        )
        self.assertEqual(result.verified_on, DAY)
        self.assertIsNone(result.reverify_on)
        for before, after in zip(
            original.procedure_versions[0].fees[0].evidence_links,
            result.evidence_links,
            strict=True,
        ):
            self.assertEqual(
                after,
                replace(before, verification_state="current", verified_on=DAY, reverify_on=None),
            )
            self.assertIs(after.sources[0], before.sources[0])
        authored = replace(original.procedure_versions[0].fees[0], verified_on=future)
        original = replace(
            original,
            procedure_versions=(replace(original.procedure_versions[0], fees=(authored,)),),
        )
        self.assertEqual(
            project_evidence_trust(original, [review()]).procedure_versions[0].fees[0].verified_on,
            future,
        )
        self.assertEqual(
            project_evidence_trust(original, [transition()])
            .procedure_versions[0]
            .fees[0]
            .reverify_on,
            DUE,
        )
        for field in fields(authored):
            if field.name not in {
                "verification_state",
                "verified_on",
                "reverify_on",
                "evidence_links",
            }:
                self.assertEqual(getattr(authored, field.name), getattr(result, field.name))

    def test_establishment_dates_and_single_pass_order(self) -> None:
        later = datetime(2026, 9, 9, 12, tzinfo=UTC)
        events = [
            replace(transition("unknown", event="resolved"), occurred_at=later),
            transition("current", event="resolved"),
        ]
        result = project_evidence_trust(snapshot(), iter(events)).procedure_versions[0].fees[0]
        self.assertEqual(result.verification_state, "current")
        self.assertEqual(result.verified_on, later.date())
        result = (
            project_evidence_trust(snapshot(), [replace(review(), occurred_at=later)])
            .procedure_versions[0]
            .fees[0]
        )
        self.assertEqual(result.verified_on, later.date())
        self.assertEqual(result.evidence_links[0].verified_on, later.date())

    def test_empty_and_unmatched_history(self) -> None:
        original = snapshot()
        self.assertIs(project_evidence_trust(original, iter(())), original)
        self.assertEqual(
            project_evidence_trust(original, [transition(key=("fee", "absent", "item"))]), original
        )
        with self.assertRaises(StopIteration):
            project_evidence_trust(original, [transition("current", key=("fee", "absent", "item"))])

    def test_incremental_replay_and_iterator_errors(self) -> None:
        failure = RuntimeError("iterator failed")

        def broken() -> Iterator[Reverification]:
            yield review()
            raise failure

        with self.assertRaises(RuntimeError) as caught:
            project_evidence_trust(snapshot(), broken())
        self.assertIs(caught.exception, failure)

        def malformed() -> Iterator[Reverification]:
            yield replace(review(), verified_on=cast(date, None))
            self.fail("history must not be consumed before replay")

        with self.assertRaises(TypeError):
            project_evidence_trust(snapshot(), malformed())

    def test_unknown_events_and_states_are_not_normalized(self) -> None:
        result = project_evidence_trust(
            snapshot(), [transition(cast(VerificationState, " CURRENT "), event="other")]
        )
        self.assertEqual(result.procedure_versions[0].fees[0].verification_state, " CURRENT ")
        result = project_evidence_trust(
            snapshot(), [transition(cast(VerificationState, ""), event="other")]
        )
        self.assertEqual(result.procedure_versions[0].fees[0].verification_state, "unknown")

    def test_current_projection_never_exposes_authored_unverified_amount(self) -> None:
        original = snapshot()
        authored = original.procedure_versions[0].fees[0]
        # Keep support usable: an unavailable-evidence fallback must not be what
        # protects this researched amount when owner trust becomes current.
        authored = replace(
            authored,
            verification_state="needs_reverification",
            evidence_links=tuple(
                replace(link, verification_state="current") for link in authored.evidence_links
            ),
        )
        original = replace(
            original,
            procedure_versions=(replace(original.procedure_versions[0], fees=(authored,)),),
        )
        projected = project_evidence_trust(original, [transition("current", event="resolved")])
        version = projected.procedure_versions[0]
        self.assertEqual(version.fees[0].value_state, "unverified")
        unknown = select_fees(version, PreparedFacts({}, frozenset(), {}), DAY)
        self.assertEqual(unknown.missing_facts, frozenset({"overlay_fee_applies"}))
        self.assertFalse(unknown.items)
        fee = select_fees(
            version,
            PreparedFacts({"overlay_fee_applies": True}, frozenset({"overlay_fee_applies"}), {}),
            DAY,
        ).items[0]
        self.assertEqual(fee.value_state, "unverified")
        self.assertIsNone(fee.amount)
        self.assertIsNone(fee.minimum_amount)
        self.assertIsNone(fee.maximum_amount)
        self.assertTrue(fee.current_value_unknown)
        self.assertEqual(fee.sources[0].id, "source")
        self.assertEqual(fee.freshness.state, "current")
        self.assertEqual(version.fees[0].amount, 900)

    def test_import_does_not_load_django(self) -> None:
        env = dict(os.environ)
        env.pop("DJANGO_SETTINGS_MODULE", None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import knowledge.evidence_trust_projection; "
                "assert not any(n == 'django' or n.startswith('django.') for n in sys.modules)",
            ],
            env=env,
            check=True,
        )
