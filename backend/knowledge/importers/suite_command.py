"""Shared CLI plumbing only; the two research manifests remain independent."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management.base import BaseCommand, CommandError

from .suite_drafts import import_suite_drafts
from .suite_specs import load_suite


class SuiteDraftCommand(BaseCommand):
    suite_key = ""
    help = (
        "Stage non-routable, non-publishable research drafts. Does not activate Services, "
        "add Questions/candidates or publish guidance. Unresolved identities are reported."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--author", help="Existing active staff username; no users created.")
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--check", action="store_true", help="Verify only; do not create rows.")
        mode.add_argument(
            "--dry-run", action="store_true", help="Validate an import and roll back."
        )
        mode.add_argument(
            "--list", action="store_true", help="Print catalog disposition; no writes."
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        spec = load_suite(self.suite_key)
        if options["list"]:
            return json.dumps(
                {
                    "suite": spec.key,
                    "mode": "research_draft_only",
                    "rows": [
                        {
                            "row": family.row,
                            "procedure_id": family.procedure_id,
                            "draft_scopes": [scope.key for scope in family.scopes],
                            "blockers": list(family.blockers),
                            "publishable": False,
                        }
                        for family in spec.families
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        if not options["author"]:
            raise CommandError("--author is required except with --list.")
        user_model = get_user_model()
        try:
            author = user_model._default_manager.get(
                **{user_model.USERNAME_FIELD: options["author"]}, is_active=True, is_staff=True
            )
        except user_model.DoesNotExist as exc:
            raise CommandError("An existing active staff author is required.") from exc
        try:
            result = import_suite_drafts(
                spec, author=author, check_only=options["check"], dry_run=options["dry_run"]
            )
        except (ValidationError, ObjectDoesNotExist, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            "Research drafts only: no live procedures, Questions, approvals or publication."
        )
        return json.dumps(asdict(result), ensure_ascii=False, indent=2)
