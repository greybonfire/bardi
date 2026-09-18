"""National-ID-suite research staging, independent of passport-suite completion."""

from __future__ import annotations

from django.db import models

from .suite_drafts import SuiteImportResult, import_suite_drafts
from .suite_specs import load_suite


def import_national_id_suite(
    *, author: models.Model, check_only: bool = False, dry_run: bool = False
) -> SuiteImportResult:
    return import_suite_drafts(
        load_suite("national_id"), author=author, check_only=check_only, dry_run=dry_run
    )
