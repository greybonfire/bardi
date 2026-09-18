"""Passport-suite research staging; distinct from the supported renewal importer."""

from __future__ import annotations

from django.db import models

from .suite_drafts import SuiteImportResult, import_suite_drafts
from .suite_specs import load_suite


def import_passport_suite(
    *, author: models.Model, check_only: bool = False, dry_run: bool = False
) -> SuiteImportResult:
    return import_suite_drafts(
        load_suite("passport"), author=author, check_only=check_only, dry_run=dry_run
    )
