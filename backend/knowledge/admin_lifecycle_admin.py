"""Permission-controlled Django Admin actions for the safe knowledge lifecycle."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from planning.trust import VERIFICATION_CHOICES

from .admin import EvidenceLinkAdmin, ProcedureVersionAdmin
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


@admin.action(
    description="Clone selected published versions to editable successor drafts",
    permissions=["clone_procedureversion"],
)
def clone_selected_to_draft(
    model_admin: ProcedureVersionAdmin,
    request: HttpRequest,
    queryset: models.QuerySet[ProcedureVersion],
) -> None:
    actor = cast(User, request.user)
    for version in queryset.order_by("semantic_id"):
        try:
            successor = clone_published_procedure_version(version.pk, actor=actor)
        except ValidationError as exc:
            model_admin.message_user(
                request,
                f"{version.semantic_id}: {_validation_text(exc)}",
                level=messages.ERROR,
            )
            continue
        model_admin.message_user(
            request,
            f"{version.semantic_id}: cloned to editable draft {successor.semantic_id}.",
            level=messages.SUCCESS,
        )


def has_clone_procedureversion_permission(
    model_admin: ProcedureVersionAdmin,
    request: HttpRequest,
) -> bool:
    del model_admin
    return request.user.has_perm("knowledge.add_procedureversion") and request.user.has_perm(
        "knowledge.change_procedureversion"
    )


@admin.action(
    description="Record independent review or specialist approval",
    permissions=["review_version"],
)
def approve_selected_versions(
    model_admin: ProcedureVersionAdmin,
    request: HttpRequest,
    queryset: models.QuerySet[ProcedureVersion],
) -> HttpResponse | None:
    form = ReviewActionForm(request.POST if "apply" in request.POST else None)
    if "apply" not in request.POST or not form.is_valid():
        return _render_action_form(
            model_admin,
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
            model_admin.message_user(
                request,
                f"{version.semantic_id}: {_validation_text(exc)}",
                level=messages.ERROR,
            )
            continue
        model_admin.message_user(
            request,
            f"{version.semantic_id}: recorded {value} approval by {actor.get_username()}.",
            level=messages.SUCCESS,
        )
    return None


def has_review_version_permission(
    model_admin: ProcedureVersionAdmin,
    request: HttpRequest,
) -> bool:
    del model_admin
    return request.user.has_perm(_REVIEW_PERMISSION) or any(
        request.user.has_perm(permission) for permission in _SPECIALIST_PERMISSIONS.values()
    )


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


@admin.action(
    description="Re-verify selected evidence subjects",
    permissions=["reverify_evidence"],
)
def reverify_selected_evidence(
    model_admin: EvidenceLinkAdmin,
    request: HttpRequest,
    queryset: models.QuerySet[EvidenceLink],
) -> HttpResponse | None:
    form = ReverificationActionForm(request.POST if "apply" in request.POST else None)
    if "apply" not in request.POST or not form.is_valid():
        return _render_action_form(
            model_admin,
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
            model_admin.message_user(
                request,
                f"{link.owner}: {_validation_text(exc)}",
                level=messages.ERROR,
            )
            continue
        model_admin.message_user(
            request,
            f"{link.owner}: re-verification recorded by {actor.get_username()}.",
            level=messages.SUCCESS,
        )
    return None


def has_reverify_evidence_permission(
    model_admin: EvidenceLinkAdmin,
    request: HttpRequest,
) -> bool:
    del model_admin
    return request.user.has_perm(_REVERIFY_PERMISSION)


def _append_actions(existing: Iterable[str], *names: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*existing, *names)))


_procedure_version_admin = cast(Any, ProcedureVersionAdmin)
_procedure_version_admin.clone_selected_to_draft = clone_selected_to_draft
_procedure_version_admin.has_clone_procedureversion_permission = (
    has_clone_procedureversion_permission
)
_procedure_version_admin.approve_selected_versions = approve_selected_versions
_procedure_version_admin.has_review_version_permission = has_review_version_permission
_procedure_version_admin.actions = _append_actions(
    getattr(_procedure_version_admin, "actions", ()),
    "clone_selected_to_draft",
    "approve_selected_versions",
)

_evidence_link_admin = cast(Any, EvidenceLinkAdmin)
_evidence_link_admin.reverify_selected_evidence = reverify_selected_evidence
_evidence_link_admin.has_reverify_evidence_permission = has_reverify_evidence_permission
_evidence_link_admin.actions = _append_actions(
    getattr(_evidence_link_admin, "actions", ()),
    "reverify_selected_evidence",
)


__all__ = (
    "ReviewActionForm",
    "ReverificationActionForm",
    "approve_selected_versions",
    "clone_selected_to_draft",
    "reverify_selected_evidence",
)
