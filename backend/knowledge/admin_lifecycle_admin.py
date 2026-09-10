"""Permission-controlled Django Admin behavior for the safe knowledge lifecycle."""

from __future__ import annotations

from typing import Any, cast

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from planning.trust import VERIFICATION_CHOICES

from .admin_lifecycle import clone_published_procedure_version
from .evidence_workflow import record_evidence_reverification
from .models import EvidenceLink, ProcedureVersion
from .review_workflow import (
    ProcedureVersionReviewApproval,
    approve_review_dimension,
    approve_specialist_risk,
)

_REVIEW_PERMISSION = "knowledge.review_procedureversion"
_SPECIALIST_PERMISSIONS = {
    "legal": "knowledge.specialist_approve_legal",
    "military": "knowledge.specialist_approve_military",
    "custody_guardianship": "knowledge.specialist_approve_custody_guardianship",
    "contested_identity": "knowledge.specialist_approve_contested_identity",
}
_REVERIFY_PERMISSION = "knowledge.add_evidencereverificationevent"

_REVIEW_CHOICES = tuple(
    (f"dimension:{value}", f"Review dimension — {label}")
    for value, label in ProcedureVersionReviewApproval.Dimension.choices
) + tuple(
    (f"specialist:{value}", f"Specialist approval — {label}")
    for value, label in ProcedureVersionReviewApproval.SpecialistRisk.choices
)


class ReviewActionForm(forms.Form):
    approval = forms.ChoiceField(choices=_REVIEW_CHOICES)


class ReverificationActionForm(forms.Form):
    verification_state = forms.ChoiceField(choices=VERIFICATION_CHOICES)
    verified_on = forms.DateField()
    reverify_on = forms.DateField(required=False)
    rationale = forms.CharField(widget=forms.Textarea(attrs={"rows": 5, "cols": 70}))


def _render_action_form(
    model_admin: admin.ModelAdmin[Any],
    request: HttpRequest,
    queryset: models.QuerySet[Any],
    *,
    title: str,
    action_name: str,
    form: forms.Form,
) -> TemplateResponse:
    context = {
        **model_admin.admin_site.each_context(request),
        "title": title,
        "opts": model_admin.model._meta,
        "queryset": queryset,
        "action_name": action_name,
        "action_checkbox_name": ACTION_CHECKBOX_NAME,
        "form": form,
        "media": model_admin.media + form.media,
    }
    return TemplateResponse(request, "admin/knowledge/workflow_action.html", context)


def _validation_text(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{field}: {', '.join(messages_)}" for field, messages_ in exc.message_dict.items()
        )
    return "; ".join(exc.messages)


def _reject_unavailable_action(
    model_admin: admin.ModelAdmin[Any],
    request: HttpRequest,
    protected_actions: frozenset[str],
) -> HttpResponseRedirect | None:
    if request.method != "POST":
        return None
    action_name = request.POST.get("action")
    if action_name not in protected_actions or action_name in model_admin.get_actions(request):
        return None
    model_admin.message_user(
        request,
        "You do not have permission to perform that lifecycle action.",
        level=messages.ERROR,
    )
    return HttpResponseRedirect(request.path)


class ProcedureVersionLifecycleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    @admin.action(
        description="Clone selected published versions to editable successor drafts",
        permissions=["clone_procedureversion"],
    )
    def clone_selected_to_draft(
        self,
        request: HttpRequest,
        queryset: models.QuerySet[ProcedureVersion],
    ) -> None:
        actor = cast(User, request.user)
        for version in queryset.order_by("semantic_id"):
            try:
                successor = clone_published_procedure_version(version.pk, actor=actor)
            except ValidationError as exc:
                self.message_user(
                    request,
                    f"{version.semantic_id}: {_validation_text(exc)}",
                    level=messages.ERROR,
                )
                continue
            self.message_user(
                request,
                f"{version.semantic_id}: cloned to editable draft {successor.semantic_id}.",
                level=messages.SUCCESS,
            )

    def has_clone_procedureversion_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm("knowledge.add_procedureversion") and request.user.has_perm(
            "knowledge.change_procedureversion"
        )

    @admin.action(
        description="Record independent review or specialist approval",
        permissions=["review_version"],
    )
    def approve_selected_versions(
        self,
        request: HttpRequest,
        queryset: models.QuerySet[ProcedureVersion],
    ) -> HttpResponse | None:
        form = ReviewActionForm(request.POST if "apply" in request.POST else None)
        if "apply" not in request.POST or not form.is_valid():
            return _render_action_form(
                self,
                request,
                queryset,
                title="Record Procedure Version review",
                action_name="approve_selected_versions",
                form=form,
            )

        actor = cast(User, request.user)
        approval_kind, value = cast(str, form.cleaned_data["approval"]).split(":", 1)
        for version in queryset.order_by("semantic_id"):
            try:
                if approval_kind == "dimension":
                    approve_review_dimension(version.pk, dimension=value, actor=actor)
                else:
                    approve_specialist_risk(version.pk, risk_kind=value, actor=actor)
            except ValidationError as exc:
                self.message_user(
                    request,
                    f"{version.semantic_id}: {_validation_text(exc)}",
                    level=messages.ERROR,
                )
                continue
            self.message_user(
                request,
                f"{version.semantic_id}: recorded {value} approval by {actor.get_username()}.",
                level=messages.SUCCESS,
            )
        return None

    def has_review_version_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm(_REVIEW_PERMISSION) or any(
            request.user.has_perm(permission) for permission in _SPECIALIST_PERMISSIONS.values()
        )

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        rejected = _reject_unavailable_action(
            self,
            request,
            frozenset({"clone_selected_to_draft", "approve_selected_versions"}),
        )
        if rejected is not None:
            return rejected
        return super().changelist_view(request, extra_context)


def _owner_key(link: EvidenceLink) -> tuple[str, int]:
    owner = link.owner
    if owner.pk is None:
        raise ValidationError("Evidence owner must be saved before re-verification.")
    return owner._meta.label_lower, owner.pk


def _complete_owner_evidence(link: EvidenceLink) -> tuple[EvidenceLink, ...]:
    manager = getattr(link.owner, "evidence_links", None)
    if manager is None:
        raise ValidationError("Evidence owner does not expose its evidence set.")
    return tuple(manager.order_by("pk"))


class EvidenceLinkLifecycleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    @admin.action(
        description="Re-verify selected evidence subjects",
        permissions=["reverify_evidence"],
    )
    def reverify_selected_evidence(
        self,
        request: HttpRequest,
        queryset: models.QuerySet[EvidenceLink],
    ) -> HttpResponse | None:
        form = ReverificationActionForm(request.POST if "apply" in request.POST else None)
        if "apply" not in request.POST or not form.is_valid():
            return _render_action_form(
                self,
                request,
                queryset,
                title="Record evidence re-verification",
                action_name="reverify_selected_evidence",
                form=form,
            )

        actor = cast(User, request.user)
        seen: set[tuple[str, int]] = set()
        for link in queryset.order_by("pk"):
            try:
                key = _owner_key(link)
                if key in seen:
                    continue
                seen.add(key)
                reviewed = _complete_owner_evidence(link)
                record_evidence_reverification(
                    anchor_evidence_link=link,
                    reviewed_evidence_links=reviewed,
                    verification_state=cast(Any, form.cleaned_data["verification_state"]),
                    verified_on=form.cleaned_data["verified_on"],
                    reverify_on=form.cleaned_data["reverify_on"],
                    rationale=form.cleaned_data["rationale"],
                    actor=actor,
                )
            except ValidationError as exc:
                self.message_user(
                    request,
                    f"{link.owner}: {_validation_text(exc)}",
                    level=messages.ERROR,
                )
                continue
            self.message_user(
                request,
                f"{link.owner}: re-verification recorded by {actor.get_username()}.",
                level=messages.SUCCESS,
            )
        return None

    def has_reverify_evidence_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm(_REVERIFY_PERMISSION)

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        rejected = _reject_unavailable_action(
            self,
            request,
            frozenset({"reverify_selected_evidence"}),
        )
        if rejected is not None:
            return rejected
        return super().changelist_view(request, extra_context)


__all__ = (
    "EvidenceLinkLifecycleAdmin",
    "ProcedureVersionLifecycleAdmin",
    "ReviewActionForm",
    "ReverificationActionForm",
)
