"""Private Admin transport/security and real importer integration regressions."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.html import escape
from planning.catalog import LocalizedText
from planning.public import (
    InvalidResult,
    NextQuestionResult,
    PlanResult,
    PublicDiagnostic,
    PublicQuestion,
    PublicSource,
    PublicStep,
)
from planning.trust import Freshness

from knowledge.draft_pack_admin import PURPOSE, SALT, confirmation_token, verify_token
from knowledge.draft_pack_upload import MAX_BYTES, DraftPackUploadHandler
from knowledge.draft_packs import export_draft_context, export_draft_pack, import_draft_pack
from knowledge.draft_packs.errors import Diagnostic, DraftPackError
from knowledge.models import FactDefinition, ProcedureVersion
from knowledge.planning_scenarios import PlanningScenario
from knowledge.publication import publish_procedure_version
from knowledge.tests.test_draft_packs import pack


class DraftPackAdminTests(TestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_superuser("editor", password="unused")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.actor)
        self.url = reverse("admin:knowledge_procedureversion_pack_new")
        self.raw = json.dumps(pack()).encode()
        self.client.get(self.url)
        self.csrf = self.client.cookies["csrftoken"].value

    def post(self, *, raw: bytes | None = None, url: str | None = None, **fields: Any) -> Any:
        return self.client.post(
            url or self.url,
            {
                "csrfmiddlewaretoken": self.csrf,
                "pack": SimpleUploadedFile("anything.bin", self.raw if raw is None else raw),
                "action": "inspect",
                **fields,
            },
        )

    def test_new_confirm_and_noop_retry_without_raw_retention(self) -> None:
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProcedureVersion.objects.exists())
        token = response.context["token"]
        self.assertLess(len(token), 1500)
        self.assertNotIn("catalog", signing.loads(token, salt=SALT))
        response = self.post(action="confirm", token=token)
        self.assertEqual(response.status_code, 302)
        version = ProcedureVersion.objects.get()
        self.assertEqual(version.state, "draft")
        response = self.post(action="confirm", token=token)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProcedureVersion.objects.count(), 1)
        self.assertNotIn(self.raw.decode(), str(dict(self.client.session)))

    def test_csrf_missing_cannot_inspect_and_handler_precedes_middleware_parser(self) -> None:
        with patch("knowledge.draft_packs.inspect_draft_pack") as inspect:
            response = self.client.post(
                self.url,
                {
                    "pack": SimpleUploadedFile("pack.json", self.raw),
                    "action": "inspect",
                },
            )
        self.assertEqual(response.status_code, 403)
        inspect.assert_not_called()
        received = cast(DraftPackUploadHandler, response.wsgi_request.upload_handlers[0]).received
        self.assertIsInstance(received, int)
        self.assertEqual(received, len(self.raw))

    def test_actual_stream_limit_exact_boundary_and_multiple_files(self) -> None:
        padded = self.raw + b" " * (MAX_BYTES - len(self.raw))
        self.assertEqual(self.post(raw=padded).status_code, 200)
        with patch("knowledge.draft_packs.inspect_draft_pack") as inspect:
            response = self.post(raw=padded + b" ")
            self.assertIn(response.status_code, (400, 403))
            inspect.assert_not_called()
            for files in ([SimpleUploadedFile("a", self.raw), SimpleUploadedFile("b", b"")],):
                response = self.client.post(
                    self.url, {"csrfmiddlewaretoken": self.csrf, "action": "inspect", "pack": files}
                )
                self.assertIn(response.status_code, (400, 403))
                inspect.assert_not_called()
            response = self.client.post(
                self.url,
                {
                    "csrfmiddlewaretoken": self.csrf,
                    "action": "inspect",
                    "pack": SimpleUploadedFile("a", self.raw),
                    "extra": SimpleUploadedFile("b", b""),
                },
            )
            self.assertIn(response.status_code, (400, 403))
            inspect.assert_not_called()

    def test_tampered_expired_wrong_file_and_actor_tokens(self) -> None:
        token = self.post().context["token"]
        for candidate in (token + "x", "", signing.dumps({"purpose": PURPOSE}, salt=SALT)):
            self.assertEqual(self.post(action="confirm", token=candidate).status_code, 400)
        self.assertEqual(
            self.post(raw=self.raw + b" ", action="confirm", token=token).status_code, 400
        )
        with patch("django.core.signing.time.time", return_value=1):
            expired = confirmation_token(
                SimpleNamespace(precondition="x", requires_deletions=False),
                actor_id=self.actor.pk,
                target=None,
                digest=hashlib.sha256(self.raw).hexdigest(),
            )
        self.assertEqual(self.post(action="confirm", token=expired).status_code, 400)
        data = signing.loads(token, salt=SALT)
        for key, value in (
            ("actor_id", self.actor.pk + 1),
            ("target", "other"),
            ("purpose", "other"),
            ("requires_deletions", 1),
            ("precondition", []),
        ):
            altered = signing.dumps({**data, key: value}, salt=SALT)
            with self.assertRaises(signing.BadSignature):
                verify_token(
                    altered, actor_id=self.actor.pk, target=None, digest=data["file_sha256"]
                )
        self.assertFalse(ProcedureVersion.objects.exists())

    def test_permissions_revocation_and_anonymous_endpoints(self) -> None:
        token = self.post().context["token"]
        self.actor.is_superuser = False
        self.actor.save()
        self.assertEqual(self.post(action="confirm", token=token).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.actor.user_permissions.add(Permission.objects.get(codename="view_procedureversion"))
        self.assertEqual(
            self.client.get(reverse("admin:knowledge_procedureversion_pack_template")).status_code,
            200,
        )
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        for url in (
            self.url,
            reverse("admin:knowledge_procedureversion_pack_template"),
            reverse("admin:knowledge_procedureversion_pack_tool", args=[1, "readiness"]),
        ):
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_configuration_changes_invalidate_inspection(self) -> None:
        for initial, changed in (("independent", "solo"), ("solo", "independent")):
            with (
                self.subTest(initial=initial),
                self.settings(PROCEDURE_VERSION_REVIEW_MODE=initial),
            ):
                token = self.post().context["token"]
                with self.settings(PROCEDURE_VERSION_REVIEW_MODE=changed):
                    response = self.post(action="confirm", token=token)
                self.assertContains(response, "stale_inspection", status_code=400)
                self.assertFalse(ProcedureVersion.objects.exists())

    def test_aggregate_permissions_and_readonly_staff(self) -> None:
        self.actor.is_superuser = False
        self.actor.save()
        self.actor.user_permissions.add(Permission.objects.get(codename="add_procedureversion"))
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("token", response.context)
        self.assertFalse(ProcedureVersion.objects.exists())
        self.actor.is_superuser = True
        self.actor.save()
        import_draft_pack(pack(), actor=self.actor)
        version = ProcedureVersion.objects.get()
        self.actor.is_superuser = False
        self.actor.save()
        self.actor.user_permissions.add(Permission.objects.get(codename="view_procedureversion"))
        url = reverse("admin:knowledge_procedureversion_pack_import", args=[version.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        for operation in ("export", "context", "readiness", "scenarios"):
            endpoint = reverse(
                "admin:knowledge_procedureversion_pack_tool", args=[version.pk, operation]
            )
            self.assertEqual(self.client.get(endpoint).status_code, 200)
            self.assertEqual(
                self.client.post(endpoint, {"csrfmiddlewaretoken": self.csrf}).status_code, 405
            )
        self.actor.user_permissions.clear()
        endpoint = reverse(
            "admin:knowledge_procedureversion_pack_tool", args=[version.pk, "readiness"]
        )
        self.assertEqual(self.client.get(endpoint).status_code, 403)

    def test_global_context_before_first_version(self) -> None:
        url = reverse("admin:knowledge_procedureversion_pack_context")
        self.assertFalse(ProcedureVersion.objects.exists())
        self.actor.is_superuser = False
        self.actor.save()
        self.actor.user_permissions.add(Permission.objects.get(codename="view_procedureversion"))
        response = self.client.get(reverse("admin:knowledge_procedureversion_changelist"))
        self.assertContains(response, f'href="{url}"')
        self.assertContains(response, "Download global vocabulary context")
        with patch(
            "knowledge.draft_packs.export_draft_context", wraps=export_draft_context
        ) as export:
            response = self.client.get(url)
        export.assert_called_once_with(actor=self.actor)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), export_draft_context(actor=self.actor))
        self.assertEqual(response.json()["status"], "read_only")
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response["Content-Disposition"], 'attachment; filename="draft-pack-context.json"'
        )
        self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(ProcedureVersion.objects.exists())
        with patch("knowledge.draft_packs.export_draft_context") as export:
            self.assertEqual(
                self.client.post(url, {"csrfmiddlewaretoken": self.csrf}).status_code, 405
            )
            self.actor.user_permissions.clear()
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
        export.assert_not_called()

    def test_global_context_concurrency_diagnostic(self) -> None:
        error = DraftPackError(
            (Diagnostic("concurrent_edit", (), "Concurrent editing detected; reload and retry."),)
        )
        with patch("knowledge.draft_packs.export_draft_context", side_effect=error):
            response = self.client.get(reverse("admin:knowledge_procedureversion_pack_context"))
        self.assertContains(response, "concurrent_edit", status_code=400)
        self.assertContains(response, "reload and retry", status_code=400)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(ProcedureVersion.objects.exists())

    def test_download_template_parity_and_safe_headers(self) -> None:
        response = self.client.get(reverse("admin:knowledge_procedureversion_pack_template"))
        expected = (
            Path(__file__).resolve().parents[3] / "docs/draft-packs/examples/minimal-research.json"
        )
        self.assertEqual(response.content, expected.read_bytes())
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            response["Content-Disposition"], 'attachment; filename="draft-pack-template.json"'
        )

    def test_update_staleness_deletion_consent_and_target_binding(self) -> None:
        initial = pack()
        initial["warnings"] = [
            {
                "semantic_id": "note",
                "text_ar": "بحث",
                "text_en": "Research",
                "kind": "product",
                "role": "limitation",
            }
        ]
        import_draft_pack(initial, actor=self.actor)
        version = ProcedureVersion.objects.get()
        url = reverse("admin:knowledge_procedureversion_pack_import", args=[version.pk])
        data = export_draft_pack(version.semantic_id, actor=self.actor)
        data["warnings"] = []
        raw = json.dumps(data).encode()
        inspected = self.post(raw=raw, url=url)
        self.assertEqual(inspected.status_code, 200)
        self.assertTrue(inspected.context["inspection"].requires_deletions)
        token = inspected.context["token"]
        self.assertEqual(
            self.post(raw=raw, url=url, action="confirm", token=token).status_code, 400
        )
        self.assertEqual(
            self.post(raw=raw, action="confirm", token=token, allow_deletions="on").status_code, 400
        )
        self.assertEqual(
            self.post(
                raw=raw, url=url, action="confirm", token=token, allow_deletions="on"
            ).status_code,
            302,
        )
        self.assertFalse(version.warnings.exists())
        data = export_draft_pack(version.semantic_id, actor=self.actor)
        data["version"]["text_en"] = "Updated"
        raw = json.dumps(data).encode()
        token = self.post(raw=raw, url=url).context["token"]
        ProcedureVersion.objects.filter(pk=version.pk).update(text_ar="تغيير")
        response = self.post(raw=raw, url=url, action="confirm", token=token)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "stale_inspection", status_code=400)

    def test_escaped_diff_and_no_token_on_invalid_pack(self) -> None:
        data = pack()
        data["version"]["text_en"] = '<script>alert("x")</script>'
        response = self.post(raw=json.dumps(data).encode())
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("x")</script>')
        response = self.post(raw=b"not-json")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("token", response.context)

    def test_inspection_preserves_json_types_and_exact_nested_keys(self) -> None:
        data = pack()
        data["scenarios"] = [
            {
                "name": "typed",
                "kind": "negative",
                "evaluation_context": {"evaluation_date": "2026-01-01", "locale": "en"},
                "expected_result_family": "plan",
                "expected_identifiers": {
                    "procedure_version_id": "draft",
                    "dependency_statuses": {},
                },
                "source_facts": {
                    "synthetic_ready": {
                        "Case_Key": {"case_Key": None, "<Exact_Key>": [True, 1, "1", False, ""]}
                    }
                },
            }
        ]
        import_draft_pack(data, actor=self.actor)
        version = ProcedureVersion.objects.get()
        before = export_draft_pack(version.semantic_id, actor=self.actor)
        data = export_draft_pack(version.semantic_id, actor=self.actor)
        data["scenarios"][0]["expected_identifiers"]["dependency_statuses"] = []
        url = reverse("admin:knowledge_procedureversion_pack_import", args=[version.pk])
        response = self.post(raw=json.dumps(data).encode(), url=url)
        for text in (
            "<dt>dependency_statuses</dt><dd><span>{}</span>",
            "<dt>dependency_statuses</dt><dd><span>[]</span>",
            "<dt>Case_Key</dt>",
            "<dt>case_Key</dt>",
            "<dt>&lt;Exact_Key&gt;</dt>",
            "<span>null</span>",
            "<span>true</span>",
            "<span>false</span>",
            "<span>1</span>",
            "<span>&quot;1&quot;</span>",
            "<span>&quot;&quot;</span>",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "<Exact_Key>")
        self.assertEqual(export_draft_pack(version.semantic_id, actor=self.actor), before)

    def test_deep_pack_inspection_and_stored_preview_are_bounded_and_readonly(self) -> None:
        nested: Any = {"Exact_Leaf": "<script>deep</script>"}
        for _ in range(150):
            nested = [nested]
        data = pack()
        data["scenarios"] = [
            {
                "name": "deep",
                "kind": "contradictory",
                "evaluation_context": {"evaluation_date": "2026-01-01", "locale": "en"},
                "expected_result_family": "invalid",
                "source_facts": {"synthetic_ready": nested},
                "expected_diagnostics": ["invalid_fact"],
            }
        ]
        raw = json.dumps(data).encode()
        # Real shared importer accepts this supported JSON, not a mocked inspection.
        import_draft_pack(raw, actor=self.actor, dry_run=True)
        response = self.post(raw=raw)
        self.assertContains(response, "Inspection — not saved")
        self.assertContains(response, "&lt;script&gt;deep&lt;/script&gt;")
        self.assertNotContains(response, "<script>deep</script>")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(ProcedureVersion.objects.exists())
        self.assertFalse(PlanningScenario.objects.exists())
        # Verify fallback is complete JSON, including the deepest leaf.

        fallbacks = re.findall(r"<pre>(.*?)</pre>", response.content.decode(), re.DOTALL)
        self.assertTrue(fallbacks)
        tail = json.loads(unescape(fallbacks[0]))
        depth = 0
        while isinstance(tail, list):
            depth += 1
            tail = tail[0]
        self.assertGreaterEqual(depth, 140)
        self.assertEqual(tail, {"Exact_Leaf": "<script>deep</script>"})

        import_draft_pack(raw, actor=self.actor)
        version = ProcedureVersion.objects.get()
        before = export_draft_pack(version.semantic_id, actor=self.actor)
        scenario = PlanningScenario.objects.get()
        url = reverse("admin:knowledge_procedureversion_pack_tool", args=[version.pk, "scenarios"])
        response = self.client.get(url, {"scenario": scenario.pk})
        self.assertContains(response, "deep")
        # Exercise the same bound for arbitrarily deep production projection data.
        preview = SimpleNamespace(
            scenario_name=scenario.name,
            evaluation_date="2026-01-01",
            authored_locale="en",
            stale=False,
            matches_expectations=False,
            diagnostics=(),
            result=InvalidResult(()),
        )
        with (
            patch("knowledge.draft_preview.preview_draft_scenario", return_value=preview),
            patch("api.application.project_result", return_value={"message": nested}),
        ):
            response = self.client.get(url, {"scenario": scenario.pk})
        self.assertContains(response, escape(json.dumps(nested[0][0][0][0][0][0][0][0])))
        self.assertNotContains(response, "<script>deep</script>")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(export_draft_pack(version.semantic_id, actor=self.actor), before)

    def test_preview_production_projection_bilingual_and_unavailable(self) -> None:
        import_draft_pack(pack(), actor=self.actor)
        version = ProcedureVersion.objects.get()
        url = reverse("admin:knowledge_procedureversion_pack_tool", args=[version.pk, "scenarios"])
        result = PlanResult(
            "research",
            "procedure",
            "draft",
            LocalizedText("إرشادات بحثية", "Research guidance"),
            steps=(
                PublicStep(
                    "step",
                    LocalizedText("خطوة بحثية", "Research step"),
                    "submit",
                    (
                        PublicSource(
                            "source",
                            "authority",
                            "<img src=x onerror=alert(1)>",
                            "javascript:alert(1)",
                            "official",
                            date(2026, 1, 1),
                        ),
                    ),
                    Freshness("stale", date(2026, 1, 1)),
                ),
            ),
        )
        preview = SimpleNamespace(
            scenario_name="<script>scenario</script>",
            evaluation_date="2026-09-01",
            authored_locale="ar",
            stale=True,
            matches_expectations=False,
            result=result,
            diagnostics=(),
        )
        with patch("knowledge.draft_preview.preview_draft_scenario", return_value=preview):
            response = self.client.get(url, {"scenario": 1})
        self.assertContains(response, 'lang="ar" dir="rtl"')
        self.assertContains(response, 'lang="en" dir="ltr"')
        for text in (
            "إرشادات بحثية",
            "Research guidance",
            "Checklist",
            "Fees",
            "Where to go",
            "Unresolved sections",
            "Stale",
            "Do not match",
            "&lt;script&gt;scenario",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "<script>scenario")
        self.assertContains(response, "Research step")
        self.assertContains(response, "خطوة بحثية")
        self.assertContains(response, "Freshness")
        self.assertContains(response, "2026-01-01")
        self.assertContains(response, "&lt;img src=x")
        self.assertNotContains(response, 'href="javascript:')
        preview.result = None
        preview.matches_expectations = None
        with patch("knowledge.draft_preview.preview_draft_scenario", return_value=preview):
            response = self.client.get(url, {"scenario": 1})
        self.assertContains(response, "Preview unavailable")
        self.assertContains(response, "Expectations: Unavailable")

    def test_question_and_invalid_production_results(self) -> None:
        import_draft_pack(pack(), actor=self.actor)
        version = ProcedureVersion.objects.get()
        url = reverse("admin:knowledge_procedureversion_pack_tool", args=[version.pk, "scenarios"])
        results = (
            (
                NextQuestionResult(
                    "research",
                    PublicQuestion("question", LocalizedText("سؤال بحثي", "Research question"), ()),
                ),
                "Research question",
                "سؤال بحثي",
            ),
            (
                InvalidResult((PublicDiagnostic("invalid_fact", ("facts", "unknown")),)),
                "invalid_fact",
                "unknown",
            ),
        )
        for result, english, arabic_or_detail in results:
            preview = SimpleNamespace(
                scenario_name="Research",
                evaluation_date="2026-09-01",
                authored_locale="en",
                stale=False,
                matches_expectations=True,
                result=result,
                diagnostics=(),
            )
            with patch("knowledge.draft_preview.preview_draft_scenario", return_value=preview):
                response = self.client.get(url, {"scenario": 1})
            self.assertContains(response, english)
            self.assertContains(response, arabic_or_detail)
            self.assertContains(response, 'dir="rtl"')
            self.assertContains(response, "Expectations: Match")

    def test_bounded_metadata_and_fragment_response(self) -> None:
        response = self.post(token="x" * 4097)
        self.assertEqual(response.status_code, 400)
        response = self.post(action=["inspect", "confirm"])
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self.url,
            {
                "csrfmiddlewaretoken": self.csrf,
                "pack": SimpleUploadedFile("pack.json", self.raw),
                "action": "inspect",
            },
            headers={"X-Draft-Pack-Fragment": "1"},
        )
        self.assertContains(response, "Inspection — not saved")
        self.assertNotContains(response, '<input type="file"')
        self.assertNotContains(response, "<html")

    def test_real_stored_scenario_and_finalized_import_rejected(self) -> None:
        data = pack()
        data["version"]["applicability"] = {"op": "eq", "fact": "synthetic_ready", "value": True}
        import_draft_pack(data, actor=self.actor)
        FactDefinition.objects.update(is_published=True)
        version = ProcedureVersion.objects.get()
        scenario = PlanningScenario.objects.create(
            procedure_version=version,
            name="Stored research",
            kind="unknown",
            evaluation_context={"evaluation_date": "2026-09-01", "locale": "ar"},
            expected_result_family="inconclusive",
            expected_identifiers={"reason": "inactive_service"},
        )
        url = reverse("admin:knowledge_procedureversion_pack_tool", args=[version.pk, "scenarios"])
        response = self.client.get(url, {"scenario": scenario.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stored research")
        self.assertContains(response, "inconclusive")
        self.assertFalse(version.procedure.primary_service.is_active)
        version.text_ar = "بحث"
        version.text_en = "Research"
        version.save()
        publish_procedure_version(version.pk, actor=self.actor)
        response = self.post(
            url=reverse("admin:knowledge_procedureversion_pack_import", args=[version.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_links_and_checks_are_explicit_not_change_page_side_effects(self) -> None:
        import_draft_pack(pack(), actor=self.actor)
        version = ProcedureVersion.objects.get()
        with patch("knowledge.draft_preview.check_draft_publication") as readiness:
            response = self.client.get(
                reverse("admin:knowledge_procedureversion_change", args=[version.pk])
            )
            self.assertContains(response, "Check publication readiness")
            readiness.assert_not_called()
        response = self.client.get(
            reverse("admin:knowledge_procedureversion_pack_tool", args=[version.pk, "readiness"])
        )
        self.assertContains(response, "Prospective publisher")
        self.assertContains(response, "advisory")
        response = self.client.get(
            reverse("admin:knowledge_procedureversion_pack_tool", args=[version.pk, "scenarios"])
        )
        self.assertContains(response, "No stored scenarios")
        for operation in ("export", "context"):
            response = self.client.get(
                reverse("admin:knowledge_procedureversion_pack_tool", args=[version.pk, operation])
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
