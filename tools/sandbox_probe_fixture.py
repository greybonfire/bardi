"""Synthetic all-base-gates fixture; never called against an authoring database.

Translated from DraftPreviewTests' generic pack and three scenario setup, without
TestCase lifecycle, test settings, or publication-gate overrides.
"""

import sys
from typing import Any


def pack(prefix: str = "") -> dict[str, Any]:
    def identity(value: str) -> str:
        return prefix + value

    rule = {"op": "eq", "fact": "synthetic_ready", "value": True}
    return {
        "format": "bardi.draft-pack",
        "format_version": 1,
        "base_revision": None,
        "catalog": {
            "services": [
                {"semantic_id": identity("research"), "text_ar": "بحث", "text_en": "Research"}
            ],
            "procedures": [
                {
                    "semantic_id": identity("procedure"),
                    "text_ar": "بحث",
                    "text_en": "Research",
                    "primary_service": identity("research"),
                }
            ],
            "facts": [{"key": "synthetic_ready", "kind": "boolean"}],
            "authorities": [],
            "sources": [],
            "document_types": [],
        },
        "version": {
            "semantic_id": identity("draft"),
            "procedure": identity("procedure"),
            "text_ar": "بحث",
            "text_en": "Research",
            "applicability": rule,
        },
        "risks": dict.fromkeys(
            ("legal", "military", "custody_guardianship", "contested_identity"), bool(prefix)
        ),
        "service_setup": {
            "service": identity("research"),
            "questions": [
                {
                    "semantic_id": identity("ready"),
                    "fact": "synthetic_ready",
                    "text_ar": "بحث؟",
                    "text_en": "Synthetic ready?",
                    "priority": 1,
                }
            ],
            "candidates": [{"procedure": identity("procedure"), "selection_predicate": rule}],
            "contradictions": [],
        },
        **dict.fromkeys(
            (
                "bases",
                "checklist_items",
                "steps",
                "warnings",
                "fees",
                "dependencies",
                "routing_associations",
                "scenarios",
                "evidence_links",
            ),
            [],
        ),
    }


def main(action: str) -> None:
    import django

    django.setup()
    from bardi.settings.base import PROCEDURE_VERSION_PUBLICATION_GATES
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.db import connection
    from knowledge import models as m
    from knowledge.draft_packs import import_draft_pack
    from knowledge.planning_scenarios import PlanningScenario
    from knowledge.publication import (
        PublicationRejected,
        publish_procedure_version,
        withdraw_procedure_version,
    )

    assert settings.PROCEDURE_VERSION_PUBLICATION_GATES == PROCEDURE_VERSION_PUBLICATION_GATES
    assert settings.SELECTION_QUESTIONS_REQUIRED and settings.PLANNING_SCENARIOS_REQUIRED
    assert settings.PROCEDURE_VERSION_REVIEW_MODE == "solo"
    assert connection.settings_dict["NAME"].startswith(("bardi_probe", "bardi_restore_"))
    if action == "seed":
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
            assert cursor.fetchone()[0] == 0
        call_command("migrate", verbosity=0, interactive=False)
        actor = User.objects.create_superuser("sandbox-probe", password="synthetic-probe-only")
        for prefix in ("", "risk-"):
            import_draft_pack(pack(prefix), actor=actor)
            version = m.ProcedureVersion.objects.get(semantic_id=prefix + "draft")
            for kind, facts, family, identifiers in (
                (
                    "positive",
                    {"synthetic_ready": True},
                    "plan",
                    {"procedure_version_id": prefix + "draft"},
                ),
                (
                    "negative",
                    {"synthetic_ready": False},
                    "inconclusive",
                    {"reason": "no_matching_researched_procedure"},
                ),
                ("unknown", {}, "next_question", {"question_id": prefix + "ready"}),
            ):
                PlanningScenario.objects.create(
                    procedure_version=version,
                    name=kind,
                    kind=kind,
                    evaluation_context={"evaluation_date": "2026-01-01", "locale": "ar"},
                    source_facts=facts,
                    expected_result_family=family,
                    expected_identifiers=identifiers,
                    expected_diagnostics=[],
                )
        m.Service.objects.update(is_active=True)
        m.FactDefinition.objects.filter(key="synthetic_ready").update(is_published=True)
        assert not m.ProcedureVersion.objects.exclude(state="draft").exists()
        return
    actor = User.objects.get(username="sandbox-probe")
    version = m.ProcedureVersion.objects.get(semantic_id="draft")
    if action == "publish":
        publish_procedure_version(version.pk, actor=actor)
    elif action == "withdraw":
        withdraw_procedure_version(version.pk, actor=actor)
    elif action == "blocked":
        blocked = m.ProcedureVersion.objects.get(semantic_id="risk-draft")
        try:
            publish_procedure_version(blocked.pk, actor=actor)
        except PublicationRejected as error:
            assert {
                d.detail for d in error.diagnostics if d.code == "missing_specialist_approval"
            } == {"legal", "military", "custody_guardianship", "contested_identity"}
        else:
            raise AssertionError("high risk publication accepted")
        blocked.refresh_from_db()
        assert blocked.state == "draft" and not blocked.audit_events.exists()
    else:
        raise ValueError("unknown fixture action")


if __name__ == "__main__":
    main(sys.argv[1])
