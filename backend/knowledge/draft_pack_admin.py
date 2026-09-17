"""Private native Admin transport. Raw uploads live for this request only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from .draft_pack_upload import DraftPackUploadHandler
from .draft_packs.errors import DraftPackError
from .models import ProcedureVersion

SALT = "knowledge.admin.draft-pack.confirm.v1"
PURPOSE = "draft-import-v1"


def confirmation_token(inspection: Any, *, actor_id: int, target: str | None, digest: str) -> str:
    return signing.dumps(
        {
            "purpose": PURPOSE,
            "actor_id": actor_id,
            "target": target,
            "file_sha256": digest,
            "precondition": inspection.precondition,
            "requires_deletions": inspection.requires_deletions,
        },
        salt=SALT,
    )


def verify_token(token: str, *, actor_id: int, target: str | None, digest: str) -> dict[str, Any]:
    if len(token) > 4096:
        raise signing.BadSignature("Oversized confirmation")
    data = signing.loads(token, salt=SALT, max_age=900)
    if (
        not isinstance(data, dict)
        or set(data)
        != {"purpose", "actor_id", "target", "file_sha256", "precondition", "requires_deletions"}
        or data["purpose"] != PURPOSE
        or type(data["actor_id"]) is not int
        or data["actor_id"] != actor_id
        or data["target"] != target
        or data["file_sha256"] != digest
        or not isinstance(data["precondition"], str)
        or not data["precondition"]
        or len(data["precondition"]) > 256
        or type(data["requires_deletions"]) is not bool
    ):
        raise signing.BadSignature("Invalid confirmation")
    return data


TREE_DEPTH_LIMIT = 8


def display_tree(value: Any, *, typed: bool = False) -> dict[str, Any]:
    """Bound template recursion; deep subtrees remain complete, escaped JSON."""

    def build(node: Any, depth: int) -> dict[str, Any]:
        if isinstance(node, (dict, tuple, list)):
            if depth >= TREE_DEPTH_LIMIT:
                return {"json": json.dumps(node, ensure_ascii=False)}
            if not node:
                return {"value": "{}" if isinstance(node, dict) else "[]"}
            if isinstance(node, dict):
                return {
                    "pairs": [
                        (
                            str(k) if typed else str(k).replace("_", " ").capitalize(),
                            build(v, depth + 1),
                        )
                        for k, v in node.items()
                    ]
                }
            return {"children": [build(item, depth + 1) for item in node]}
        if typed:
            return {"value": json.dumps(node, ensure_ascii=False)}
        return {"value": "Not supplied" if node is None else str(node)}

    return build(value, 0)


def guidance_sections(projected: dict[str, object], locale: str) -> list[dict[str, Any]]:
    labels = {
        "type": ("Result", "النتيجة"),
        "title": ("Procedure", "الإجراء"),
        "question": ("Next question", "السؤال التالي"),
        "message": ("What this means", "معنى النتيجة"),
        "eligibility_bases": ("Eligibility alternatives", "أسس الأهلية البديلة"),
        "dependencies": ("Prerequisites", "المتطلبات المسبقة"),
        "checklist_items": ("Checklist", "قائمة المستندات"),
        "steps": ("Steps", "الخطوات"),
        "fees": ("Fees", "الرسوم"),
        "warnings": ("Warnings and limits", "تحذيرات وحدود الإرشادات"),
        "routing": ("Where to go", "مكان تقديم الطلب"),
        "inconclusive_sections": ("Unresolved sections", "أقسام غير محسومة"),
        "inconclusive_basis_ids": ("Unresolved eligibility", "أهلية غير محسومة"),
    }
    return [
        {
            "label": labels.get(key, (key.replace("_", " ").capitalize(), key))[locale == "ar"],
            "tree": display_tree(value),
        }
        for key, value in projected.items()
    ]


class DraftPackAdminMixin(admin.ModelAdmin):  # type: ignore[type-arg]
    change_list_template = "admin/knowledge/procedureversion/change_list.html"
    change_form_template = "admin/knowledge/procedureversion/change_form.html"

    def get_urls(self) -> list[URLPattern]:
        @csrf_exempt
        def upload(request: HttpRequest, object_id: int | None = None) -> HttpResponse:
            request.upload_handlers = [DraftPackUploadHandler(request)]
            # File bytes are separately bounded by the handler. Bound text fields locally.
            return csrf_protect(self.pack_upload)(request, object_id)

        routes = [
            path(
                "draft-pack/import/",
                self.admin_site.admin_view(upload),
                name="knowledge_procedureversion_pack_new",
            ),
            path(
                "draft-pack/context/",
                self.admin_site.admin_view(self.pack_global_context),
                name="knowledge_procedureversion_pack_context",
            ),
            path(
                "draft-pack/template/",
                self.admin_site.admin_view(self.pack_template),
                name="knowledge_procedureversion_pack_template",
            ),
            path(
                "<int:object_id>/draft-pack/import/",
                self.admin_site.admin_view(upload),
                name="knowledge_procedureversion_pack_import",
            ),
            path(
                "<int:object_id>/draft-pack/<str:operation>/",
                self.admin_site.admin_view(self.pack_tool),
                name="knowledge_procedureversion_pack_tool",
            ),
        ]
        return routes + super().get_urls()

    def pack_context(self, request: HttpRequest, **values: Any) -> dict[str, Any]:
        return {**self.admin_site.each_context(request), "opts": self.model._meta, **values}

    def pack_authorize(
        self, request: HttpRequest, object_id: int | None = None, *, importing: bool = False
    ) -> tuple[Any, ProcedureVersion | None]:
        # Fresh database authorization: do not rely on cached request permission sets.
        if request.user.pk is None:
            raise PermissionDenied
        actor = get_user_model().objects.get(pk=request.user.pk)
        if not actor.is_active or not actor.is_staff:
            raise PermissionDenied
        permission = "change" if object_id is not None else "add"
        if not actor.has_perm(f"knowledge.{permission if importing else 'view'}_procedureversion"):
            raise PermissionDenied
        version = (
            get_object_or_404(ProcedureVersion, pk=object_id) if object_id is not None else None
        )
        if importing and version and version.state != "draft":
            raise PermissionDenied
        return actor, version

    def pack_upload(self, request: HttpRequest, object_id: int | None = None) -> HttpResponse:
        from .draft_packs import import_draft_pack, inspect_draft_pack

        if request.method not in {"GET", "POST"}:
            return HttpResponseNotAllowed(["GET", "POST"])
        actor, version = self.pack_authorize(request, object_id, importing=True)
        target = version.semantic_id if version else None
        context = self.pack_context(
            request, title="Import research draft", target=target, version=version
        )
        status = 200
        if request.method == "POST":
            try:
                handler = cast(DraftPackUploadHandler, request.upload_handlers[0])
                fields = request.POST
                files = request.FILES
                if (
                    handler.error
                    or len(fields) > 4
                    or set(fields) - {"csrfmiddlewaretoken", "action", "token", "allow_deletions"}
                    or any(
                        len(values) != 1 or len(values[0]) > 4096 for _, values in fields.lists()
                    )
                    or set(files) != {"pack"}
                    or len(files.getlist("pack")) != 1
                ):
                    raise ValueError("Upload one JSON file, at most 8 MiB, then inspect it again.")
                raw = cast("UploadedFile[Any]", files["pack"]).read()
                digest = hashlib.sha256(raw).hexdigest()
                if fields.get("action") == "confirm":
                    data = verify_token(
                        fields.get("token", ""), actor_id=actor.pk, target=target, digest=digest
                    )
                    consent = fields.get("allow_deletions") == "on"
                    if data["requires_deletions"] and not consent:
                        raise ValueError(
                            "Confirm the proposed deletions before importing. Inspect again."
                        )
                    result = import_draft_pack(
                        raw,
                        actor=actor,
                        target_version=target,
                        allow_deletions=consent,
                        inspection_precondition=data["precondition"],
                    )
                    saved = ProcedureVersion.objects.get(semantic_id=result["version"])
                    self.message_user(
                        request,
                        "Draft unchanged (exact retry). Nothing published."
                        if result["status"] == "noop"
                        else "Draft imported. Nothing published or approved.",
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(
                        reverse("admin:knowledge_procedureversion_change", args=[saved.pk])
                    )
                if fields.get("action") != "inspect":
                    raise ValueError("Choose Inspect before confirming an import.")
                inspection = inspect_draft_pack(raw, actor=actor, target_version=target)
                context.update(
                    inspection=inspection,
                    readiness=inspection.publication,
                    changes=[
                        {
                            "kind": row.kind,
                            "path": " / ".join(map(str, row.path)),
                            "fields": row.fields,
                            "before": display_tree(row.before, typed=True),
                            "after": display_tree(row.after, typed=True),
                        }
                        for row in inspection.diff
                    ],
                    token=confirmation_token(
                        inspection, actor_id=actor.pk, target=target, digest=digest
                    ),
                )
            except DraftPackError as exc:
                context["diagnostics"] = exc.diagnostics
                status = 400
            except signing.BadSignature:
                context["error"] = (
                    "Confirmation expired or does not match this file, editor or target. "
                    "Inspect again."
                )
                status = 400
            except (ValueError, SuspiciousOperation) as exc:
                context["error"] = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "Invalid upload. Inspect one JSON file again."
                )
                status = 400
        template = (
            "admin/knowledge/pack_inspection.html"
            if request.headers.get("X-Draft-Pack-Fragment") == "1"
            else "admin/knowledge/pack_upload.html"
        )
        return TemplateResponse(request, template, context, status=status)

    def pack_template(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        self.pack_authorize(request)
        return self.pack_download(
            Path(__file__).with_name("draft_pack_template.json").read_bytes(),
            "draft-pack-template.json",
        )

    def pack_global_context(self, request: HttpRequest) -> HttpResponse:
        from .draft_packs import export_draft_context

        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        actor, _ = self.pack_authorize(request)
        try:
            data = export_draft_context(actor=actor)
        except DraftPackError as exc:
            return TemplateResponse(
                request,
                "admin/knowledge/pack_context_error.html",
                self.pack_context(
                    request, title="Vocabulary context unavailable", diagnostics=exc.diagnostics
                ),
                status=400,
            )
        return self.pack_download(
            json.dumps(data, ensure_ascii=False, indent=2), "draft-pack-context.json"
        )

    @staticmethod
    def pack_download(content: bytes | str, filename: str) -> HttpResponse:
        response = HttpResponse(content, content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response

    def pack_tool(self, request: HttpRequest, object_id: int, operation: str) -> HttpResponse:
        from api.application import project_result

        from .draft_packs import export_draft_context, export_draft_pack
        from .draft_preview import check_draft_publication, preview_draft_scenario

        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        actor, version = self.pack_authorize(request, object_id)
        assert version is not None
        context = self.pack_context(
            request,
            title="Draft checks and scenario previews",
            version=version,
            target=version.semantic_id,
        )
        try:
            if operation in {"export", "context"}:
                data = (
                    export_draft_pack(version.semantic_id, actor=actor)
                    if operation == "export"
                    else export_draft_context(
                        version.procedure.primary_service.semantic_id, actor=actor
                    )
                )
                return self.pack_download(
                    json.dumps(data, ensure_ascii=False, indent=2), f"draft-pack-{operation}.json"
                )
            if version.state != "draft":
                raise PermissionDenied
            if operation == "readiness":
                context["readiness"] = check_draft_publication(version.pk, actor=actor)
            elif operation == "scenarios":
                context["scenarios"] = version.planning_scenarios.order_by("name", "pk")
                if "scenario" in request.GET:
                    try:
                        scenario_id = int(request.GET["scenario"])
                    except ValueError:
                        raise SuspiciousOperation("Invalid scenario") from None
                    preview = preview_draft_scenario(version.pk, scenario_id, actor=actor)
                    context["preview"] = preview
                    if preview.result is not None:
                        context["projections"] = [
                            (
                                locale,
                                guidance_sections(project_result(preview.result, locale), locale),
                            )
                            for locale in ("ar", "en")
                        ]
            else:
                return HttpResponse(status=404)
        except DraftPackError as exc:
            context["diagnostics"] = exc.diagnostics
        return TemplateResponse(request, "admin/knowledge/pack_tools.html", context)
